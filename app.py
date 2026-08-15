from __future__ import annotations

import base64
import os
import re
import tempfile

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from langchain_core.messages import HumanMessage, SystemMessage

from src import calculos
from src import geo
from src import llm as groq

load_dotenv()

app = Flask(__name__)

# Los endpoints que llaman a Groq se pagan por uso y no piden credenciales:
# sin tope, cualquiera puede agotar la cuota del proyecto. El almacenamiento en
# memoria basta para un solo proceso; con varios workers (ver Dockerfile, 6.4)
# hay que apuntar a Redis con RATELIMIT_STORAGE_URI.
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
    enabled=os.getenv("RATELIMIT_ENABLED", "1") == "1",
)

# Configuración de subida de archivos
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB máximo
EXTENSIONES_PERMITIDAS = {"png", "jpg", "jpeg", "webp", "pdf"}


def extension_permitida(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in EXTENSIONES_PERMITIDAS


# Topes de plausibilidad para lo que se extrae de una boleta. Son holgados a
# propósito: solo descartan lo absurdo, no lo inusual. La tarifa admite valores
# grandes porque hay monedas con tarifas de tres cifras por kWh (PYG, COP).
LIMITE_KWH_MES = 100_000.0
LIMITE_TARIFA = 100_000.0


def _numero_de_boleta(texto: str) -> float | None:
    """
    Convierte a float un número tal como aparece impreso en una boleta.

    El código anterior hacía `float(texto.replace(",", "."))`, que convierte
    "1.234,5" en "1.234.5" y revienta con ValueError: una boleta con separador
    de miles tumbaba la subida con un 500.

    Regla: cuando hay dos separadores distintos, el último es el decimal. Cuando
    hay uno solo, es separador de miles si le siguen exactamente tres dígitos
    (1.234 → 1234) y decimal en cualquier otro caso (1,5 → 1.5).
    """
    if not texto:
        return None

    limpio = re.sub(r"[^\d.,]", "", str(texto))
    if not limpio:
        return None

    ultima_coma = limpio.rfind(",")
    ultimo_punto = limpio.rfind(".")

    if ultima_coma >= 0 and ultimo_punto >= 0:
        if ultima_coma > ultimo_punto:
            # Formato "1.234,56": el punto agrupa miles y la coma es decimal.
            limpio = limpio.replace(".", "").replace(",", ".")
        else:
            # Formato "1,234.56": al revés.
            limpio = limpio.replace(",", "")
    else:
        separador = "," if ultima_coma >= 0 else ("." if ultimo_punto >= 0 else "")
        if separador:
            partes = limpio.split(separador)
            es_miles = len(partes) > 2 or len(partes[-1]) == 3
            limpio = "".join(partes) if es_miles else ".".join(partes)

    try:
        return float(limpio)
    except ValueError:
        return None


SYSTEM_PROMPT_NARRADOR = """Eres "VólticvS", un asesor energético inteligente y amigable.
Ya se calcularon con exactitud el consumo y el ahorro potencial del hogar del usuario;
tu única tarea es redactar un resumen breve (4 a 6 frases) explicando los resultados de
forma cálida, clara y con un toque de humor.

REGLA ABSOLUTA: no inventes ni cambies ningún número. Usa EXACTAMENTE los valores en
kWh y la moneda/símbolo que te entrego (DOP, CLP, USD, etc.).
Destaca cuál es la mayor oportunidad de ahorro y da recomendaciones concretas.
"""


def _narrativa_de_respaldo(resumen: dict) -> str:
    """Texto determinista para cuando Groq no está disponible o falla."""
    simbolo = resumen.get("simbolo_moneda", "$")
    moneda = resumen.get("moneda", "")
    costo_val = resumen.get("total_clp_mes") or resumen.get("costo_estimado_mes") or 0
    ahorro_val = resumen.get("ahorro_potencial_clp_mes") or resumen.get("ahorro_potencial_mes") or 0

    costo_str = f"{simbolo} {costo_val:,.0f} {moneda}".strip() if isinstance(costo_val, (int, float)) else str(costo_val)
    ahorro_str = f"{simbolo} {ahorro_val:,.0f} {moneda}".strip() if isinstance(ahorro_val, (int, float)) else str(ahorro_val)

    return (
        f"Tu consumo estimado es de {resumen.get('total_kwh_mes', 0)} kWh al mes "
        f"(~{costo_str}). Podrías ahorrar hasta "
        f"{ahorro_str} al mes aplicando los cambios sugeridos."
    )


def generar_narrativa(resumen: dict) -> dict:
    """
    Devuelve {"texto", "fuente"}, donde `fuente` distingue el texto del modelo
    del de respaldo.

    Antes esto era un `except Exception` mudo que devolvía el respaldo como si
    fuera la respuesta buena: con una clave inválida se pagaban tres llamadas
    fallidas por request y nadie se enteraba nunca.
    """
    if not groq.disponible():
        app.logger.warning("GROQ_API_KEY no configurada: se usa la narrativa de respaldo.")
        return {"texto": _narrativa_de_respaldo(resumen), "fuente": "respaldo_sin_api_key"}

    try:
        llm = groq.obtener_llm(temperatura=0.5)
        mensaje = f"Estos son los resultados calculados para este hogar: {resumen}"
        respuesta = llm.invoke([SystemMessage(content=SYSTEM_PROMPT_NARRADOR), HumanMessage(content=mensaje)])
        return {"texto": respuesta.content.strip(), "fuente": "llm"}
    except Exception as error:
        app.logger.warning("Groq falló al generar la narrativa: %s", error, exc_info=True)
        return {"texto": _narrativa_de_respaldo(resumen), "fuente": "respaldo_error"}


def generar_recomendaciones(desglose: list) -> list:
    """
    Convierte el desglose numérico en frases de recomendación concretas,
    cada una con el ahorro mensual y anual ya calculado (determinista, sin IA).
    Ordenadas de mayor a menor impacto de ahorro.
    """
    candidatas = []
    for item in desglose:
        ahorro_mes = item.get("ahorro_clp_mes", 0)
        if not ahorro_mes or ahorro_mes <= 0:
            continue
        ahorro_anio = round(ahorro_mes * 12)
        nombre = item["nombre"]

        if "kwh_mes_si_fuera_led" in item:
            frase = f"Cambia tu {nombre.lower()} a LED"
        elif "kwh_mes_llenado_habitual" in item:
            frase = "Hierve solo el agua que necesitas en vez de llenar el hervidor completo"
        elif "kwh_mes_optimo" in item:
            frase = f"Desconecta {nombre.lower()} cuando no lo estés usando"
        else:
            frase = f"Optimiza el uso de {nombre.lower()}"

        texto = f"{frase}: ahorras ${ahorro_mes:,.0f}/mes (${ahorro_anio:,.0f} al año)."
        candidatas.append((ahorro_mes, texto))

    candidatas.sort(key=lambda par: par[0], reverse=True)
    return [texto for _, texto in candidatas]


@app.errorhandler(413)
def _archivo_demasiado_grande(error):
    """El tope de MAX_CONTENT_LENGTH devolvia la pagina HTML de error de Werkzeug."""
    limite_mb = app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)
    return jsonify({"error": f"El archivo supera el maximo de {limite_mb:.0f} MB."}), 413


@app.errorhandler(calculos.PaisNoSoportado)
def _pais_no_soportado(error):
    return jsonify({"error": str(error), "paises_soportados": sorted(calculos.PAISES)}), 400


def _resolver_tarifa(datos: dict) -> tuple[float, dict]:
    """
    Resuelve la tarifa a aplicar y la ficha del país. Prioridad:
      1. tarifa explícita del payload (la que el usuario leyó de su boleta)
      2. tarifa referencial del país declarado

    Antes esto lo hacía `_get_tarifa`, que leía de un dict `_TARIFAS` local
    discrepante con el JSON en 14 de los 17 países, y cuyo fallback consultaba
    una clave (`tarifa_kwh`) que el JSON no tiene: siempre caía a 0.18 USD.
    """
    pais = (datos.get("pais") or "CL").strip() or "CL"
    ficha = calculos.obtener_pais(pais)

    explicita = datos.get("tarifa_kwh") or datos.get("tarifa_clp_kwh")
    try:
        tarifa = float(explicita) if explicita else float(ficha["tarifa_kwh_referencial"])
    except (TypeError, ValueError):
        tarifa = float(ficha["tarifa_kwh_referencial"])

    return tarifa, ficha


@app.route("/health")
@limiter.exempt
def health():
    """
    Sonda de vida para el HEALTHCHECK del contenedor y el balanceador.

    Deliberadamente NO llama a Groq ni a Nominatim: una sonda que se ejecuta
    cada 30 s no puede gastar cuota de un servicio de pago ni de uno gratuito
    ajeno. Solo comprueba que la aplicación levantó y que la tabla de
    referencia se cargó, que es lo que de verdad puede fallar al arrancar.

    Queda exenta del límite de tasa: si no, el propio healthcheck acabaría
    recibiendo 429 y el orquestador daría el contenedor por muerto.
    """
    try:
        paises_cargados = len(calculos.PAISES)
        artefactos = len(calculos.REFERENCIA["electrodomesticos"])
    except Exception as error:
        app.logger.exception("La tabla de referencia no está disponible: %s", error)
        return jsonify({"estado": "error", "detalle": "datos de referencia no disponibles"}), 503

    if not paises_cargados or not artefactos:
        return jsonify({"estado": "error", "detalle": "datos de referencia vacíos"}), 503

    return jsonify({
        "estado": "ok",
        "paises": paises_cargados,
        "artefactos": artefactos,
        # Informativo: permite ver desde fuera qué funciones opcionales están
        # configuradas, sin exponer ninguna credencial.
        "groq_configurado": groq.disponible(),
        "geocodificacion_configurada": geo.disponible(),
    })


@app.route("/api/paises")
def paises():
    return jsonify(calculos.PAISES)


@app.route("/api/ubicacion")
@limiter.limit("30 per hour")
def ubicacion():
    """
    Geocodificación inversa: coordenadas → ciudad, región y código de país.

    Actúa de intermediario ante Nominatim para poder identificar la aplicación
    como exige su política de uso, cachear las respuestas y devolver el código
    ISO del país en vez de su nombre localizado. Antes lo llamaba el navegador
    directamente (ver docs/PLAN.md, tarea 5.8).
    """
    lat = groq.numero_valido(request.args.get("lat"), -90, 90)
    lon = groq.numero_valido(request.args.get("lon"), -180, 180)

    if lat is None or lon is None:
        return jsonify({"error": "Coordenadas inválidas."}), 400

    if not geo.disponible():
        app.logger.warning("NOMINATIM_CONTACTO sin configurar: no se geocodifica.")
        return jsonify({"error": "La detección automática de ubicación no está configurada."}), 503

    try:
        return jsonify(geo.ubicacion_desde_coordenadas(lat, lon))
    except geo.GeocodificacionNoDisponible as error:
        app.logger.warning("Nominatim no respondió: %s", error)
        return jsonify({"error": "No pudimos determinar tu ubicación."}), 503


@app.route("/api/interpretar-campo", methods=["POST"])
@limiter.limit("20 per hour")
def interpretar_campo():
    """
    Llamada Opcional #1 (solo cuando el usuario escribe "Otro" en tipo de inmueble).
    Recibe { campo: "tipo_inmueble", texto: "..." } y mapea el texto libre a uno
    de los valores conocidos del sistema usando el LLM.
    Máximo 1 llamada LLM por campo libre ingresado.
    """
    data = request.get_json(force=True) or {}
    campo = data.get("campo", "")
    texto = (data.get("texto") or "").strip()

    # 'campo' se documentaba pero se ignoraba: cualquier valor terminaba mapeado
    # contra la lista de tipos de inmueble. Hoy es el único campo soportado, así
    # que se rechaza explícitamente el resto en vez de devolver un valor inventado.
    if campo != "tipo_inmueble":
        return jsonify({"error": f"Campo '{campo}' no soportado. Solo se admite 'tipo_inmueble'."}), 400

    if not texto:
        return jsonify({"valor_mapeado": "Casa", "fuente": "fallback_vacio"})

    VALORES_INMUEBLE = ["Casa", "Casa pareada", "Departamento", "Casa móvil", "Otro"]

    if not groq.disponible():
        # Antes se devolvía `texto[:50]`, es decir el texto crudo del usuario:
        # el llamador recibía una cadena arbitraria donde esperaba uno de los
        # cinco valores. "Otro" sí pertenece a la lista y conserva el sentido.
        app.logger.warning("GROQ_API_KEY no configurada: no se puede interpretar el texto libre.")
        return jsonify({"valor_mapeado": "Otro", "fuente": "fallback_sin_api", "texto_original": texto[:50]})

    try:
        llm = groq.obtener_llm(temperatura=0, max_tokens=16)
        prompt = (
            f"El usuario describió su tipo de vivienda como: '{texto}'.\n"
            f"Mapea esto al valor MÁS CERCANO de esta lista exacta: {VALORES_INMUEBLE}.\n"
            f"Responde SOLO con el valor exacto de la lista, sin explicaciones ni puntos."
        )
        respuesta = llm.invoke([HumanMessage(content=prompt)])
        valor = respuesta.content.strip().strip("\"'.")
        # Validar que el valor esté en la lista permitida
        if valor not in VALORES_INMUEBLE:
            app.logger.info("El modelo devolvió un valor fuera de la lista: %r", valor[:80])
            valor = "Casa"
        return jsonify({"valor_mapeado": valor, "fuente": "llm"})
    except Exception as error:
        # El detalle va al log del servidor, no al cliente.
        app.logger.warning("Groq falló al interpretar el campo libre: %s", error, exc_info=True)
        return jsonify({"valor_mapeado": "Casa", "fuente": "fallback_error"})


@app.route("/api/comparar", methods=["POST"])
def comparar():
    datos = request.get_json(force=True) or {}
    tarifa, _ficha = _resolver_tarifa(datos)
    try:
        resultado = calculos.comparar_categoria(
            datos["categoria"], float(datos["horas_uso_diario"]), tarifa
        )
        return jsonify(resultado)
    except KeyError as e:
        return jsonify({"error": f"Falta el campo obligatorio {e}."}), 400
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400



@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/calcular", methods=["POST"])
@limiter.limit("60 per hour")
def calcular():
    datos = request.get_json(force=True)
    tarifa, ficha_pais = _resolver_tarifa(datos)

    desglose = []
    total_kwh_mes = 0.0
    ahorro_potencial_clp_mes = 0.0

    # Electrodomésticos de la tabla de referencia
    for item in datos.get("electrodomesticos", []):
        try:
            resultado = calculos.consumo_mensual_standby(
                item["clave"],
                float(item["horas"]),
                tarifa,
                cantidad=int(item.get("cantidad", 1)),
                queda_conectado=bool(item.get("queda_conectado", True)),
                veces_semana=float(item.get("veces_semana", 7)),
            )
            resultado["tarifa_aplicada"] = tarifa
            desglose.append(resultado)
            total_kwh_mes += resultado["kwh_mes_actual"]
            ahorro_potencial_clp_mes += resultado.get("ahorro_clp_mes", 0)
        except ValueError:
            continue  # clave desconocida, se ignora en vez de romper el cálculo

    # Iluminación (puede haber varios tipos a la vez: LED + fluorescente, etc.)
    for item in datos.get("iluminacion", []):
        try:
            resultado = calculos.consumo_iluminacion(
                item["tipo"], int(item["cantidad"]), float(item["horas"]), tarifa
            )
            desglose.append(resultado)
            total_kwh_mes += resultado["kwh_mes_actual"]
            ahorro_potencial_clp_mes += resultado.get("ahorro_clp_mes", 0)
        except (ValueError, KeyError):
            continue

    # Hervidor de agua
    hervidor = datos.get("hervidor")
    if hervidor and hervidor.get("tiene"):
        resultado = calculos.ahorro_hervidor(
            float(hervidor["litros_habitual"]),
            float(hervidor["litros_necesario"]),
            tarifa,
            usos_por_dia=int(hervidor.get("usos_dia", 1)),
        )
        resultado["nombre"] = "Hervidor de agua"
        desglose.append(resultado)
        total_kwh_mes += resultado["kwh_mes_llenado_habitual"]
        ahorro_potencial_clp_mes += resultado.get("ahorro_clp_mes", 0)

    # Artefactos personalizados (mueblista, arquitecto, médico, etc.)
    for item in datos.get("personalizados", []):
        resultado = calculos.consumo_personalizado(
            item.get("nombre", "Artefacto personalizado"),
            float(item["watts"]),
            float(item["horas"]),
            tarifa,
            cantidad=int(item.get("cantidad", 1)),
        )
        desglose.append(resultado)
        total_kwh_mes += resultado["kwh_mes_actual"]

    total_clp_mes = calculos.kwh_a_dinero(total_kwh_mes, tarifa)

    resumen = {
        "moneda": ficha_pais["moneda"],
        "simbolo_moneda": ficha_pais["simbolo"],
        "tarifa_aplicada": tarifa,
        "total_kwh_mes": round(total_kwh_mes, 2),
        "total_clp_mes": round(total_clp_mes, 0),
        "ahorro_potencial_clp_mes": round(ahorro_potencial_clp_mes, 0),
        "desglose": desglose,
        "recomendaciones": generar_recomendaciones(desglose),
        "proyeccion": {
            "ahorro_1_mes": round(ahorro_potencial_clp_mes, 0),
            "ahorro_6_meses": round(ahorro_potencial_clp_mes * 6, 0),
            "ahorro_1_anio": round(ahorro_potencial_clp_mes * 12, 0),
            "ahorro_5_anios": round(ahorro_potencial_clp_mes * 60, 0),
        },
    }

    narrativa = generar_narrativa(resumen)
    resumen["narrativa"] = narrativa["texto"]
    resumen["narrativa_fuente"] = narrativa["fuente"]
    return jsonify(resumen)

@app.route("/api/subir-boleta", methods=["POST"])
@limiter.limit("10 per hour")
def subir_boleta():
    """
    Recibe una imagen (PNG/JPG/WEBP) o PDF de la boleta eléctrica.
    - PDF: extrae el texto con pdfplumber y lo analiza con Groq.
    - Imagen: codifica en base64 y usa el modelo de visión de Groq.
    Devuelve: {kwh_mes, tarifa_kwh, moneda, simbolo, confianza, nota}
    """
    if "boleta" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo."}), 400

    archivo = request.files["boleta"]
    pais_codigo = request.form.get("pais", "CL")

    if archivo.filename == "":
        return jsonify({"error": "Nombre de archivo vacío."}), 400

    if not extension_permitida(archivo.filename):
        return jsonify({"error": "Solo se aceptan imágenes (PNG, JPG, WEBP) o PDF."}), 400

    # La extensión ya pasó por la lista blanca de extension_permitida.
    extension = archivo.filename.rsplit(".", 1)[1].lower()

    # Nombre generado por el sistema, no derivado del que envía el cliente.
    # Antes se guardaba en uploads/<nombre_original>: dos personas subiendo
    # "boleta.pdf" a la vez se pisaban el archivo, y el bloque `finally` de la
    # primera borraba el de la segunda mientras aún se estaba analizando.
    # De paso elimina cualquier posibilidad de path traversal por el nombre.
    with tempfile.NamedTemporaryFile(
        dir=app.config["UPLOAD_FOLDER"], suffix=f".{extension}", delete=False
    ) as destino:
        archivo.save(destino)
        ruta_temp = destino.name

    # Obtener info del país
    datos_pais = calculos.PAISES.get(pais_codigo, {})
    moneda  = datos_pais.get("moneda",  "local")
    simbolo = datos_pais.get("simbolo", "")
    nombre_pais = datos_pais.get("nombre", "tu país")

    try:
        prompt_extraccion = f"""Analiza esta boleta eléctrica de {nombre_pais} (moneda: {moneda}).

Extrae con precisión:
1. El CONSUMO TOTAL en kWh del período facturado (busca: kWh, consumo, energía activa, kwh consumidos).
2. El PRECIO POR kWh en {moneda} (busca: tarifa, precio unitario, costo por kWh, valor kWh).

RESPONDE SOLO con este JSON exacto, sin texto adicional:
{{"kwh_mes": NÚMERO_O_NULL, "tarifa_kwh": NÚMERO_O_NULL, "confianza": "alta|media|baja", "nota": "explicación breve"}}"""

        # ── CASO PDF: extraer texto con pdfplumber ──────────────────
        if extension == "pdf":
            import pdfplumber
            texto_pdf = ""
            with pdfplumber.open(ruta_temp) as pdf:
                for pagina in pdf.pages:
                    texto_pagina = pagina.extract_text()
                    if texto_pagina:
                        texto_pdf += texto_pagina + "\n"

            if not texto_pdf.strip():
                return jsonify({
                    "error": "No se pudo extraer texto del PDF. Puede ser un PDF escaneado sin texto. Prueba subiendo una foto (JPG/PNG)."
                }), 422

            # Intentar extraer con regex primero (rápido, sin API)
            kwh_regex   = re.search(r'(\d[\d.,]+)\s*kWh', texto_pdf, re.IGNORECASE)
            tarifa_regex = re.search(
                r'(?:tarifa|precio|costo|valor)\s*(?:por\s*)?kWh[^0-9]*(\d[\d.,]+)',
                texto_pdf, re.IGNORECASE
            )

            kwh_extraido = _numero_de_boleta(kwh_regex.group(1)) if kwh_regex else None
            tarifa_extraida = _numero_de_boleta(tarifa_regex.group(1)) if tarifa_regex else None

            # Si no tenemos ambos valores, usar Groq con texto
            if groq.disponible() and (kwh_extraido is None or tarifa_extraida is None):
                llm = groq.obtener_llm(temperatura=0, json_mode=True)
                contenido_prompt = f"{prompt_extraccion}\n\nTEXTO DE LA BOLETA:\n{texto_pdf[:4000]}"
                respuesta = llm.invoke([HumanMessage(content=contenido_prompt)])
                datos = groq.extraer_json(respuesta.content)

                if datos:
                    # Validación explícita: lo que devuelve el modelo puede ser una
                    # cadena, un negativo o una cifra absurda. Antes salía tal cual
                    # hacia el cliente y de ahí al cálculo.
                    del_modelo_kwh = groq.numero_valido(datos.get("kwh_mes"), 0.1, LIMITE_KWH_MES)
                    del_modelo_tarifa = groq.numero_valido(datos.get("tarifa_kwh"), 0.0001, LIMITE_TARIFA)

                    # Comprobación explícita contra None: con `or`, un 0 legítimo
                    # devuelto por el modelo se descartaba como si fuera ausencia.
                    if del_modelo_kwh is not None:
                        kwh_extraido = del_modelo_kwh
                    if del_modelo_tarifa is not None:
                        tarifa_extraida = del_modelo_tarifa

                    confianza = datos.get("confianza", "media")
                    nota = datos.get("nota", "")
                    if confianza not in ("alta", "media", "baja"):
                        confianza = "media"
                else:
                    app.logger.warning("El modelo no devolvió un JSON interpretable para el PDF.")
                    confianza, nota = "baja", "Extracción automática parcial."
            else:
                confianza = "alta" if (kwh_extraido and tarifa_extraida) else "media"
                nota = "Datos extraídos del texto del PDF."

            return jsonify({
                "kwh_mes":    kwh_extraido,
                "tarifa_kwh": tarifa_extraida,
                "moneda":     moneda,
                "simbolo":    simbolo,
                "confianza":  confianza,
                "nota":       str(nota)[:300],
            })

        # ── CASO IMAGEN: enviar en base64 al modelo de visión ──────
        if not groq.disponible():
            return jsonify({
                "error": "El análisis de imágenes no está disponible: falta configurar la clave de la API."
            }), 503

        tamano_mb = os.path.getsize(ruta_temp) / (1024 * 1024)
        if tamano_mb > groq.MAX_IMAGEN_MB:
            # Se corta antes de codificar y enviar: base64 infla el archivo ~33%
            # y la API la rechazaría igual, ya gastada la llamada.
            return jsonify({
                "error": (
                    f"La imagen pesa {tamano_mb:.1f} MB y el máximo para análisis es "
                    f"{groq.MAX_IMAGEN_MB:.0f} MB. Súbela con menor resolución o en PDF."
                )
            }), 413

        with open(ruta_temp, "rb") as f:
            imagen_b64 = base64.b64encode(f.read()).decode("utf-8")

        tipo_mime = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png",  "webp": "image/webp"
        }.get(extension, "image/jpeg")

        # Modelo de visión configurable: antes estaba fijo en el código,
        # ignorando GROQ_MODEL y sin variable propia.
        llm = groq.obtener_llm(modelo=groq.MODELO_VISION, temperatura=0)

        mensaje = HumanMessage(content=[
            {"type": "text",      "text": prompt_extraccion},
            {"type": "image_url", "image_url": {"url": f"data:{tipo_mime};base64,{imagen_b64}"}}
        ])

        respuesta = llm.invoke([mensaje])
        datos = groq.extraer_json(respuesta.content)

        if not datos:
            app.logger.warning("El modelo de visión no devolvió un JSON interpretable.")
            return jsonify({"error": "No se pudieron extraer datos de la imagen."}), 422

        confianza = datos.get("confianza", "media")
        return jsonify({
            "kwh_mes":    groq.numero_valido(datos.get("kwh_mes"), 0.1, LIMITE_KWH_MES),
            "tarifa_kwh": groq.numero_valido(datos.get("tarifa_kwh"), 0.0001, LIMITE_TARIFA),
            "moneda":     moneda,
            "simbolo":    simbolo,
            "confianza":  confianza if confianza in ("alta", "media", "baja") else "media",
            "nota":       str(datos.get("nota", ""))[:300],
        })

    except groq.GroqNoConfigurado:
        return jsonify({"error": "El análisis de boletas no está disponible en este momento."}), 503
    except Exception as error:
        # El detalle va al log, no al cliente: el mensaje de excepción puede
        # incluir rutas del servidor o fragmentos de la petición a la API.
        app.logger.exception("Error al procesar la boleta: %s", error)
        return jsonify({"error": "No se pudo procesar la boleta. Intenta con otro archivo."}), 500
    finally:
        if os.path.exists(ruta_temp):
            os.remove(ruta_temp)

# ══════════════════════════════════════════════════════════════════════════════
#  ENGINE DE CÁLCULO ENERGÉTICO — Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _sanitizar(data: dict) -> dict:
    """
    Convierte cada campo del payload a su tipo correcto.
    Cualquier valor None / null / "" / ausente → 0 / "" seguro.
    """
    def _f(key, *aliases):
        for k in (key, *aliases):
            v = data.get(k)
            if v not in (None, "", False):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        return 0.0

    def _i(key, *aliases):
        return int(_f(key, *aliases))

    def _s(key, default=""):
        v = data.get(key)
        return str(v).strip() if v else default

    return {
        # Consumo (admite tanto 'consumo' como 'consumo_kwh')
        "consumo":                _f("consumo", "consumo_kwh"),
        "flag_anual":             _i("flag_anual"),
        # Tarifa que el usuario leyó de su propia boleta. Sin esto, el dato que
        # extrae /api/subir-boleta no llegaría nunca al cálculo.
        "tarifa_kwh":             _f("tarifa_kwh", "tarifa_clp_kwh"),
        # Ubicación
        "pais":                   _s("pais", "CL"),
        "estado_provincia":       _s("estado_provincia"),
        "tipo_inmueble":          _s("tipo_inmueble", "Casa"),
        # Vivienda
        "dormitorios":            _i("dormitorios"),
        "ventanas":               _i("ventanas"),
        "habitantes_mayores":     _i("habitantes_mayores"),
        "habitantes_menores":     _i("habitantes_menores"),
        # Equipos con switch
        "aire_acondicionado":     _i("aire_acondicionado"),
        "calefaccion_electrica":  _i("calefaccion_electrica"),
        "agua_caliente_electrica":_i("agua_caliente_electrica"),
        "secarropas_electrico":   _i("secarropas_electrico"),
        "horno_electrico":        _i("horno_electrico"),
        # Equipos con contador
        "refrigerador":           _i("refrigerador"),
        "freezer":                _i("freezer"),
        "tv":                     _i("tv"),
        "tv_frecuencia":          _f("tv_frecuencia"),
        "lavado_frecuencia":      _i("lavado_frecuencia"),
        # Auxiliares
        "luces_interior":         _i("luces_interior"),
        "luces_exterior":         _i("luces_exterior"),
        "flag_galones":           _i("flag_galones"),
    }


def _clasificar(kwh: float) -> str:
    if kwh < 250:
        return "Eficiente"
    if kwh < 450:
        return "Moderado"
    return "Ineficiente"


def _recomendaciones_contextuales(categoria: str, d: dict) -> list[str]:
    """Genera recomendaciones concretas según categoría y artefactos presentes."""
    recs: list[str] = []

    if categoria == "Eficiente":
        recs.append("¡Excelente! Tu hogar tiene un consumo eficiente. ¡Sigue así!")
    elif categoria == "Moderado":
        recs.append("Tu consumo es moderado. Con pequeños ajustes puedes alcanzar la categoría Eficiente.")
    else:
        recs.append("Tu consumo es elevado. Implementa las recomendaciones para reducirlo significativamente.")

    if d["aire_acondicionado"]:
        recs.append("Mantén el A/C a 24°C y limpia los filtros mensualmente para reducir hasta un 20% su consumo.")
    if d["calefaccion_electrica"]:
        recs.append("Usa timer en calefactores y aísla puertas y ventanas para retener el calor el mayor tiempo posible.")
    if d["agua_caliente_electrica"]:
        recs.append("Configura el termotanque a 50°C y revisa el aislamiento del depósito; así evitas pérdidas de calor.")
    if d["refrigerador"] > 1:
        recs.append("Consolida alimentos en un solo refrigerador y desconecta el segundo cuando no sea necesario.")
    if d["tv_frecuencia"] > 6:
        recs.append("Activa el modo ahorro de energía en el TV y evita dejarlo en stand-by durante la noche.")
    if d["lavado_frecuencia"] > 4:
        recs.append("Agrupa la ropa y lava con agua fría; ahorras hasta el 90% de la energía del ciclo de lavado.")
    if d["horno_electrico"]:
        recs.append("Precalienta el horno solo cuando sea necesario y aprovecha el calor residual apagándolo antes de terminar.")

    recs.append("Desconecta cargadores y aparatos en stand-by; pueden representar hasta el 10% de tu factura mensual.")
    recs.append("Usa bombillas LED en toda la vivienda y aprovecha la luz natural durante el día.")

    return recs[:7]  # máximo 7 recomendaciones


@app.route("/api/analisis-energetico", methods=["POST"])
@limiter.limit("60 per hour")
def analisis_energetico_mvp():
    """Endpoint principal de cálculo energético — v2.0."""
    data = request.get_json(force=True) or {}

    # ── 1. Sanitización completa de entradas ────────────────────────────────
    d = _sanitizar(data)

    # ── 2. Tarifa, moneda y símbolo desde la fuente única ───────────────────
    tarifa_kwh, ficha_pais = _resolver_tarifa(d)
    simbolo_moneda = ficha_pais["simbolo"]
    moneda_iso = ficha_pais["moneda"]

    # ── 3. Desglose por artefacto con el motor determinista ─────────────────
    # Se calcula SIEMPRE, incluso cuando el usuario declara el consumo de su
    # boleta: el consumo declarado es más fiable, pero sin desglose no hay
    # forma de saber dónde está el ahorro.
    perfil = calculos.estimar_desde_perfil(d, tarifa_kwh)

    # ── 4. Consumo en kWh: declarado (convertido a mensual) o estimado ──────
    consumo_declarado = d["consumo"] / 12 if d["flag_anual"] == 1 and d["consumo"] > 0 else d["consumo"]

    if consumo_declarado > 0:
        consumo_kwh = round(consumo_declarado, 1)
        fuente_consumo = "declarado"
        desglose = {"Consumo declarado en recibo": consumo_kwh}
    elif perfil["consumo_kwh"] > 0:
        consumo_kwh = perfil["consumo_kwh"]
        fuente_consumo = "estimado"
        desglose = perfil["desglose"]
    else:
        # El usuario no declaró consumo ni artefactos: no hay nada que estimar.
        consumo_kwh = 0.0
        fuente_consumo = "sin_datos"
        desglose = {}

    costo_estimado = round(consumo_kwh * tarifa_kwh, 2)

    # ── 5. Ahorro REAL, sumado artefacto por artefacto ──────────────────────
    # Antes era `costo_estimado * 0.20`: un 20% fijo, idéntico para todos los
    # hogares e independiente de los equipos declarados.
    ahorro_estimado = perfil["ahorro_dinero_mes"]
    fuente_ahorro = "desglose_artefactos" if perfil["items"] else "sin_artefactos_declarados"

    # ── 6. Clasificación y recomendaciones ──────────────────────────────────
    categoria = _clasificar(consumo_kwh)
    recomendaciones = _recomendaciones_contextuales(categoria, d)

    # ── 7. Narrativa con LLM ────────────────────────────────────────────────
    narrativa = generar_narrativa({
        "total_kwh_mes": consumo_kwh,
        "total_clp_mes": costo_estimado,
        "ahorro_potencial_clp_mes": ahorro_estimado,
        "simbolo_moneda": simbolo_moneda,
        "moneda": moneda_iso,
    })

    # ── 8. Respuesta estructurada ────────────────────────────────────────────
    return jsonify({
        # Campos primarios (nuevos nombres que el frontend ya consume)
        "status":          "success",
        "consumo_kwh":     consumo_kwh,
        "costo_estimado":  costo_estimado,
        "ahorro_estimado": ahorro_estimado,
        "simbolo_moneda":  simbolo_moneda,
        "moneda":          moneda_iso,
        "tarifa_aplicada": tarifa_kwh,
        "categoria":       categoria,
        "fuente_consumo":  fuente_consumo,
        "fuente_ahorro":   fuente_ahorro,
        "desglose":        desglose,
        "recomendaciones": recomendaciones,
        "narrativa":       narrativa["texto"],
        "narrativa_fuente": narrativa["fuente"],
        # Aliases de compatibilidad (versiones previas del frontend los esperan).
        # Marcados como deprecados en la tarea 7.3 del plan; se retiran cuando el
        # frontend deje de leerlos.
        "costo_estimado_mensual":   costo_estimado,
        "total_kwh_mes":            consumo_kwh,
        "total_clp_mes":            costo_estimado,
        "ahorro_potencial_clp_mes": ahorro_estimado,
    })

if __name__ == "__main__":
    puerto = int(os.getenv("PORT", 5000))
    modo_debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=puerto, debug=modo_debug)
import base64
import os
import re

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from werkzeug.utils import secure_filename

from src import calculos

load_dotenv()

app = Flask(__name__)

# Configuración de subida de archivos
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB máximo
EXTENSIONES_PERMITIDAS = {"png", "jpg", "jpeg", "webp", "pdf"}


def extension_permitida(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in EXTENSIONES_PERMITIDAS


SYSTEM_PROMPT_NARRADOR = """Eres "VólticvS", un asesor energético inteligente y amigable.
Ya se calcularon con exactitud el consumo y el ahorro potencial del hogar del usuario;
tu única tarea es redactar un resumen breve (4 a 6 frases) explicando los resultados de
forma cálida, clara y con un toque de humor.

REGLA ABSOLUTA: no inventes ni cambies ningún número. Usa EXACTAMENTE los valores en
kWh y la moneda/símbolo que te entrego (DOP, CLP, USD, etc.).
Destaca cuál es la mayor oportunidad de ahorro y da recomendaciones concretas.
"""


def generar_narrativa(resumen: dict) -> str:
    simbolo = resumen.get("simbolo_moneda", "$")
    moneda = resumen.get("moneda", "")
    costo_val = resumen.get("total_clp_mes") or resumen.get("costo_estimado_mes") or 0
    ahorro_val = resumen.get("ahorro_potencial_clp_mes") or resumen.get("ahorro_potencial_mes") or 0

    costo_str = f"{simbolo} {costo_val:,.0f} {moneda}".strip() if isinstance(costo_val, (int, float)) else str(costo_val)
    ahorro_str = f"{simbolo} {ahorro_val:,.0f} {moneda}".strip() if isinstance(ahorro_val, (int, float)) else str(ahorro_val)

    try:
        llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            temperature=0.5,
            api_key=os.getenv("GROQ_API_KEY"),
        )
        mensaje = f"Estos son los resultados calculados para este hogar: {resumen}"
        respuesta = llm.invoke([SystemMessage(content=SYSTEM_PROMPT_NARRADOR), HumanMessage(content=mensaje)])
        return respuesta.content
    except Exception:
        return (
            f"Tu consumo estimado es de {resumen.get('total_kwh_mes', 0)} kWh al mes "
            f"(~{costo_str}). Podrías ahorrar hasta "
            f"{ahorro_str} al mes aplicando los cambios sugeridos."
        )


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


@app.route("/api/paises")
def paises():
    datos = {k: v for k, v in calculos.REFERENCIA["paises"].items() if not k.startswith("_")}
    return jsonify(datos)


@app.route("/api/interpretar-campo", methods=["POST"])
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
    groq_api_key = os.getenv("GROQ_API_KEY")

    if not groq_api_key:
        # Sin API key: devolvemos el texto tal cual como fallback limpio
        return jsonify({"valor_mapeado": texto[:50], "fuente": "fallback_sin_api"})

    try:
        llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            temperature=0,
            api_key=groq_api_key,
        )
        prompt = (
            f"El usuario describió su tipo de vivienda como: '{texto}'.\n"
            f"Mapea esto al valor MÁS CERCANO de esta lista exacta: {VALORES_INMUEBLE}.\n"
            f"Responde SOLO con el valor exacto de la lista, sin explicaciones ni puntos."
        )
        respuesta = llm.invoke([HumanMessage(content=prompt)])
        valor = respuesta.content.strip().strip("\"'.")
        # Validar que el valor esté en la lista permitida
        if valor not in VALORES_INMUEBLE:
            valor = "Casa"
        return jsonify({"valor_mapeado": valor, "fuente": "llm"})
    except Exception as e:
        return jsonify({"valor_mapeado": "Casa", "fuente": "fallback_error", "detalle": str(e)})


@app.route("/api/comparar", methods=["POST"])
def comparar():
    datos = request.get_json(force=True)
    try:
        resultado = calculos.comparar_categoria(
            datos["categoria"], float(datos["horas_uso_diario"]), float(datos.get("tarifa_clp_kwh", 230))
        )
        return jsonify(resultado)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400



@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/calcular", methods=["POST"])
def calcular():
    datos = request.get_json(force=True)
    tarifa = float(datos.get("tarifa_clp_kwh", 150))

    desglose = []
    total_kwh_mes = 0.0
    ahorro_potencial_clp_mes = 0.0

    # Electrodomésticos de la tabla de referencia
    for item in datos.get("electrodomesticos", []):
        try:
            resultado = calculos.consumo_mensual_standby(
                item["clave"],
                float(item["horas"]),
                int(item.get("cantidad", 1)),
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
            resultado = calculos.consumo_iluminacion(item["tipo"], int(item["cantidad"]), float(item["horas"]))
            desglose.append(resultado)
            total_kwh_mes += resultado["kwh_mes_actual"]
            ahorro_potencial_clp_mes += resultado.get("ahorro_clp_mes", 0)
        except (ValueError, KeyError):
            continue

    # Hervidor de agua
    hervidor = datos.get("hervidor")
    if hervidor and hervidor.get("tiene"):
        resultado = calculos.ahorro_hervidor(
            float(hervidor["litros_habitual"]), float(hervidor["litros_necesario"]), int(hervidor.get("usos_dia", 1))
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
            cantidad=int(item.get("cantidad", 1)),
        )
        desglose.append(resultado)
        total_kwh_mes += resultado["kwh_mes_actual"]

    total_clp_mes = calculos.kwh_a_clp(total_kwh_mes, tarifa)

    resumen = {
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

    resumen["narrativa"] = generar_narrativa(resumen)
    return jsonify(resumen)

@app.route("/api/subir-boleta", methods=["POST"])
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

    # Guardar temporalmente
    nombre_seguro = secure_filename(archivo.filename)
    ruta_temp = os.path.join(app.config["UPLOAD_FOLDER"], nombre_seguro)
    archivo.save(ruta_temp)

    # Obtener info del país
    datos_pais = calculos.REFERENCIA["paises"].get(pais_codigo, {})
    moneda  = datos_pais.get("moneda",  "local")
    simbolo = datos_pais.get("simbolo", "")
    nombre_pais = datos_pais.get("nombre", "tu país")

    try:
        import json as _json
        extension = nombre_seguro.rsplit(".", 1)[1].lower()
        groq_api_key = os.getenv("GROQ_API_KEY")

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

            kwh_extraido   = float(kwh_regex.group(1).replace(",", "."))   if kwh_regex   else None
            tarifa_extraida = float(tarifa_regex.group(1).replace(",", ".")) if tarifa_regex else None

            # Si no tenemos ambos valores, usar Groq con texto
            if groq_api_key and (kwh_extraido is None or tarifa_extraida is None):
                llm = ChatGroq(
                    model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                    temperature=0,
                    api_key=groq_api_key,
                )
                contenido_prompt = f"{prompt_extraccion}\n\nTEXTO DE LA BOLETA:\n{texto_pdf[:4000]}"
                respuesta = llm.invoke([HumanMessage(content=contenido_prompt)])
                texto_resp = respuesta.content.strip()
                match = re.search(r'\{[^{}]+\}', texto_resp, re.DOTALL)
                if match:
                    datos = _json.loads(match.group())
                    kwh_extraido    = datos.get("kwh_mes")    or kwh_extraido
                    tarifa_extraida = datos.get("tarifa_kwh") or tarifa_extraida
                    confianza       = datos.get("confianza",  "media")
                    nota            = datos.get("nota",       "")
                else:
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
                "nota":       nota,
            })

        # ── CASO IMAGEN: enviar en base64 al modelo de visión ──────
        if not groq_api_key:
            return jsonify({"error": "Clave API no configurada. Configura GROQ_API_KEY en el archivo .env para analizar imágenes."}), 500

        with open(ruta_temp, "rb") as f:
            imagen_b64 = base64.b64encode(f.read()).decode("utf-8")

        tipo_mime = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png",  "webp": "image/webp"
        }.get(extension, "image/jpeg")

        llm = ChatGroq(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=0,
            api_key=groq_api_key,
        )

        mensaje = HumanMessage(content=[
            {"type": "text",      "text": prompt_extraccion},
            {"type": "image_url", "image_url": {"url": f"data:{tipo_mime};base64,{imagen_b64}"}}
        ])

        respuesta = llm.invoke([mensaje])
        texto = respuesta.content.strip()

        match = re.search(r'\{[^{}]+\}', texto, re.DOTALL)
        if match:
            datos = _json.loads(match.group())
            return jsonify({
                "kwh_mes":    datos.get("kwh_mes"),
                "tarifa_kwh": datos.get("tarifa_kwh"),
                "moneda":     moneda,
                "simbolo":    simbolo,
                "confianza":  datos.get("confianza", "media"),
                "nota":       datos.get("nota", ""),
            })
        else:
            return jsonify({"error": "No se pudieron extraer datos de la imagen.", "texto_extraido": texto}), 422

    except Exception as e:
        return jsonify({"error": f"Error al procesar la boleta: {str(e)}"}), 500
    finally:
        if os.path.exists(ruta_temp):
            os.remove(ruta_temp)

# ══════════════════════════════════════════════════════════════════════════════
#  ENGINE DE CÁLCULO ENERGÉTICO — Helpers
# ══════════════════════════════════════════════════════════════════════════════

# ── Tarifas promedio por kWh en moneda local (actualizables) ──────────────────
_TARIFAS: dict[str, tuple[float, str]] = {
    "DO": (11.5,  "RD$"),   # Rep. Dominicana  – DOP
    "CL": (145.0, "$"),     # Chile            – CLP
    "AR": (75.0,  "$"),     # Argentina        – ARS
    "MX": (1.20,  "$"),     # México           – MXN
    "CO": (650.0, "$"),     # Colombia         – COP
    "PE": (0.45,  "S/"),    # Perú             – PEN
    "EC": (0.10,  "$"),     # Ecuador          – USD
    "BO": (0.08,  "Bs"),    # Bolivia          – BOB
    "PY": (150.0, "₲"),     # Paraguay         – PYG
    "UY": (6.50,  "$"),     # Uruguay          – UYU
    "VE": (0.05,  "Bs.D"),  # Venezuela        – VES
    "CR": (130.0, "₡"),     # Costa Rica       – CRC
    "PA": (0.17,  "$"),     # Panamá           – USD
    "GT": (1.50,  "Q"),     # Guatemala        – GTQ
    "HN": (3.50,  "L"),     # Honduras         – HNL
    "SV": (0.19,  "$"),     # El Salvador      – USD
    "NI": (7.50,  "C$"),    # Nicaragua        – NIO
    "US": (0.18,  "$"),     # EE.UU.           – USD
    "PR": (0.22,  "$"),     # Puerto Rico      – USD
    "ES": (0.25,  "€"),     # España           – EUR
    "BR": (0.65,  "R$"),    # Brasil           – BRL
    "CU": (0.09,  "$"),     # Cuba             – CUP
    "HT": (0.14,  "G"),     # Haití            – HTG
    "JM": (0.35,  "J$"),    # Jamaica          – JMD
}
_TARIFA_DEFAULT: tuple[float, str] = (0.18, "$")  # Fallback: USD


def _get_tarifa(pais_codigo: str) -> tuple[float, str]:
    """Devuelve (tarifa_kwh, simbolo_moneda) para el código ISO del país."""
    if pais_codigo in _TARIFAS:
        return _TARIFAS[pais_codigo]
    # Fallback: intentar leer tarifa de calculos.REFERENCIA
    datos_pais = calculos.REFERENCIA.get("paises", {}).get(pais_codigo, {})
    tarifa = float(datos_pais.get("tarifa_kwh") or 0)
    simbolo = datos_pais.get("simbolo") or _TARIFA_DEFAULT[1]
    if tarifa > 0:
        return tarifa, simbolo
    return _TARIFA_DEFAULT


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


def _estimar_consumo(d: dict) -> dict:
    """
    Si d['consumo'] > 0 → usa ese valor (convierte de anual a mensual si aplica).
    Si d['consumo'] == 0 → suma el consumo de cada artefacto declarado.

    Retorna: {consumo_kwh, fuente, desglose}
    """
    consumo_declarado = d["consumo"]

    # Convertir anual → mensual
    if d["flag_anual"] == 1 and consumo_declarado > 0:
        consumo_declarado = consumo_declarado / 12

    if consumo_declarado > 0:
        return {
            "consumo_kwh": round(consumo_declarado, 1),
            "fuente": "declarado",
            "desglose": {"Consumo declarado en recibo": round(consumo_declarado, 1)},
        }

    # ── Estimación desde artefactos ────────────────────────────────────────
    desglose: dict[str, float] = {}

    base = (d["habitantes_mayores"] * 30) + (d["habitantes_menores"] * 15)
    if base:
        desglose["Iluminación y uso base por habitantes"] = round(base, 1)

    ac = d["aire_acondicionado"] * 120
    if ac:
        desglose["Aire Acondicionado"] = round(ac, 1)

    calef = d["calefaccion_electrica"] * 150
    if calef:
        desglose["Calefacción Eléctrica"] = round(calef, 1)

    agua = d["agua_caliente_electrica"] * 180
    if agua:
        desglose["Termotanque / Calentador Eléctrico"] = round(agua, 1)

    seca = d["secarropas_electrico"] * 40
    if seca:
        desglose["Secarropas Eléctrico"] = round(seca, 1)

    horno = d["horno_electrico"] * 30
    if horno:
        desglose["Horno / Anafe Eléctrico"] = round(horno, 1)

    frio = (d["refrigerador"] * 35) + (d["freezer"] * 45)
    if frio:
        desglose["Refrigeración (heladera + freezer)"] = round(frio, 1)

    tv_kwh = d["tv"] * d["tv_frecuencia"] * 0.1 * 4.33
    if tv_kwh:
        desglose["Televisores"] = round(tv_kwh, 1)

    lavado_kwh = d["lavado_frecuencia"] * 3.5 * 4.33
    if lavado_kwh:
        desglose["Lavadora de Ropa"] = round(lavado_kwh, 1)

    total = sum(desglose.values())

    # Mínimo plausible si el usuario no declaró nada relevante
    if total <= 0:
        total = 50.0
        desglose["Consumo base estimado (datos insuficientes)"] = 50.0

    return {
        "consumo_kwh": round(total, 1),
        "fuente": "estimado",
        "desglose": desglose,
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
def analisis_energetico_mvp():
    """Endpoint principal de cálculo energético — v2.0."""
    data = request.get_json(force=True) or {}

    # ── 1. Sanitización completa de entradas ────────────────────────────────
    d = _sanitizar(data)

    # ── 2. Consumo en kWh (declarado o estimado por artefactos) ─────────────
    resultado_consumo = _estimar_consumo(d)
    consumo_kwh = resultado_consumo["consumo_kwh"]

    # ── 3. Tarifa y moneda según país ───────────────────────────────────────
    tarifa_kwh, simbolo_moneda = _get_tarifa(d["pais"])
    costo_estimado = round(consumo_kwh * tarifa_kwh, 2)
    ahorro_estimado = round(costo_estimado * 0.20, 2)

    # ── 4. Clasificación energética ─────────────────────────────────────────
    categoria = _clasificar(consumo_kwh)

    # ── 5. Recomendaciones contextuales ─────────────────────────────────────
    recomendaciones = _recomendaciones_contextuales(categoria, d)

    # ── 6. Código ISO de moneda y Narrativa con LLM ─────────────────────────
    moneda_iso = (
        calculos.REFERENCIA.get("paises", {})
        .get(d["pais"], {})
        .get("moneda", "")
    )

    resumen_para_llm = {
        "total_kwh_mes": consumo_kwh,
        "total_clp_mes": costo_estimado,
        "ahorro_potencial_clp_mes": ahorro_estimado,
        "simbolo_moneda": simbolo_moneda,
        "moneda": moneda_iso,
    }
    narrativa = generar_narrativa(resumen_para_llm)

    # ── 8. Respuesta estructurada ────────────────────────────────────────────
    return jsonify({
        # Campos primarios (nuevos nombres que el frontend ya consume)
        "status":          "success",
        "consumo_kwh":     round(consumo_kwh, 1),
        "costo_estimado":  costo_estimado,
        "ahorro_estimado": ahorro_estimado,
        "simbolo_moneda":  simbolo_moneda,
        "moneda":          moneda_iso,
        "categoria":       categoria,
        "fuente_consumo":  resultado_consumo["fuente"],
        "desglose":        resultado_consumo["desglose"],
        "recomendaciones": recomendaciones,
        "narrativa":       narrativa,
        # Aliases de compatibilidad (versiones previas del frontend los esperan)
        "costo_estimado_mensual":   costo_estimado,
        "total_kwh_mes":            round(consumo_kwh, 1),
        "total_clp_mes":            costo_estimado,
        "ahorro_potencial_clp_mes": ahorro_estimado,
        "probabilidad":             0.90 if categoria == "Eficiente" else 0.75 if categoria == "Moderado" else 0.82,
    })

if __name__ == "__main__":
    puerto = int(os.getenv("PORT", 5000))
    modo_debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=puerto, debug=modo_debug)
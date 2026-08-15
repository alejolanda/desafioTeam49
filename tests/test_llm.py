"""
Tests de la capa de acceso a Groq (Fase 3 del plan).

Ninguno llama a la API: se prueba la configuración del cliente, el parseo de
respuestas y la validación de lo que devuelve el modelo, que es donde estaban
los defectos.
"""
import pytest

import app as aplicacion
from src import llm


# ── Configuración del cliente (3.1) ───────────────────────────────────────────

def test_sin_api_key_no_se_construye_cliente(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert llm.disponible() is False
    with pytest.raises(llm.GroqNoConfigurado):
        llm.obtener_llm()


def test_el_cliente_lleva_timeout_y_un_solo_reintento(monkeypatch):
    """
    Regresión de 3.1: langchain-groq deja request_timeout=None y max_retries=2,
    así que una petición colgada bloqueaba el worker sin límite.
    """
    monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
    cliente = llm.obtener_llm()

    assert cliente.request_timeout is not None
    assert cliente.request_timeout == llm.TIMEOUT_S
    assert cliente.max_retries == 1
    assert cliente.max_tokens == llm.MAX_TOKENS


def test_el_cliente_se_reutiliza_entre_llamadas(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
    assert llm.obtener_llm(temperatura=0.5) is llm.obtener_llm(temperatura=0.5)
    assert llm.obtener_llm(temperatura=0.5) is not llm.obtener_llm(temperatura=0.0)


def test_json_mode_se_pide_a_la_api(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
    cliente = llm.obtener_llm(json_mode=True)
    assert cliente.model_kwargs["response_format"] == {"type": "json_object"}


def test_modelo_de_vision_configurable():
    """Regresión de 3.6: estaba fijo en el código, ignorando el entorno."""
    assert llm.MODELO_VISION
    assert llm.MODELO_TEXTO != llm.MODELO_VISION


# ── Parseo de la respuesta (3.3) ──────────────────────────────────────────────

def test_extrae_json_plano():
    assert llm.extraer_json('{"kwh_mes": 320}') == {"kwh_mes": 320}


def test_extrae_json_con_texto_alrededor():
    texto = 'Claro, aquí tienes:\n{"kwh_mes": 320, "confianza": "alta"}\n¡Espero que ayude!'
    assert llm.extraer_json(texto)["kwh_mes"] == 320


def test_extrae_json_envuelto_en_bloque_de_codigo():
    assert llm.extraer_json('```json\n{"kwh_mes": 42}\n```') == {"kwh_mes": 42}


def test_extrae_json_anidado():
    """
    Regresión de 3.3: el patrón anterior era r'\\{[^{}]+\\}', que excluye las
    llaves de la clase de caracteres y por tanto no puede casar un objeto que
    contenga otro objeto.
    """
    resultado = llm.extraer_json('{"kwh_mes": 320, "detalle": {"periodo": "mayo", "dias": 30}}')
    assert resultado["detalle"]["dias"] == 30


def test_extrae_json_con_llaves_dentro_de_cadenas():
    resultado = llm.extraer_json('{"nota": "el importe {total} no aparece", "kwh_mes": 1}')
    assert resultado["kwh_mes"] == 1


@pytest.mark.parametrize("basura", ["", None, "no hay json aquí", "{roto", "[1, 2, 3]"])
def test_respuestas_no_parseables_devuelven_none(basura):
    assert llm.extraer_json(basura) is None


# ── Validación de lo que devuelve el modelo (3.4) ─────────────────────────────

@pytest.mark.parametrize("valor", [None, True, False, "hola", "", [], {}, float("nan"), float("inf")])
def test_valores_no_numericos_se_descartan(valor):
    assert llm.numero_valido(valor) is None


def test_valores_fuera_de_rango_se_descartan():
    assert llm.numero_valido(-5, minimo=0) is None
    assert llm.numero_valido(999_999, maximo=1000) is None


def test_valores_validos_pasan():
    assert llm.numero_valido(320.5, 0.1, 100_000) == 320.5
    assert llm.numero_valido("320.5", 0.1, 100_000) == 320.5


def test_el_cero_es_un_valor_valido_si_esta_en_rango():
    """
    Regresión de 3.5: el código usaba `datos.get("kwh_mes") or respaldo`, y con
    `or` un 0 legítimo se descartaba como si fuera ausencia.
    """
    assert llm.numero_valido(0, minimo=0) == 0.0
    assert llm.numero_valido(0, minimo=0) is not None


# ── Números impresos en boletas (5.1, adelantada) ─────────────────────────────

@pytest.mark.parametrize(
    "impreso,esperado",
    [
        ("320", 320.0),
        ("320,5", 320.5),          # decimal con coma (es)
        ("320.5", 320.5),          # decimal con punto (en)
        ("1.234", 1234.0),         # miles con punto
        ("1,234", 1234.0),         # miles con coma
        ("1.234,56", 1234.56),     # miles punto + decimal coma
        ("1,234.56", 1234.56),     # miles coma + decimal punto
        ("1.234.567", 1234567.0),  # dos separadores de miles
        ("$ 1.234,56", 1234.56),   # con símbolo de moneda
    ],
)
def test_numeros_de_boleta_en_ambos_formatos(impreso, esperado):
    assert aplicacion._numero_de_boleta(impreso) == esperado


@pytest.mark.parametrize("basura", ["", None, "sin dígitos"])
def test_numeros_de_boleta_invalidos_devuelven_none(basura):
    assert aplicacion._numero_de_boleta(basura) is None


def test_el_parseo_ya_no_revienta_con_separador_de_miles():
    """
    Regresión de 5.1: `float("1.234,5".replace(",", "."))` da "1.234.5" y lanza
    ValueError, que el handler convertía en un 500.
    """
    assert aplicacion._numero_de_boleta("1.234,5") == 1234.5


# ── Degradación sin clave (3.2) ───────────────────────────────────────────────

def test_la_narrativa_de_respaldo_se_marca_como_tal(monkeypatch):
    """
    Regresión de 3.2: el respaldo se servía como si fuera la respuesta del
    modelo, así que un fallo de Groq era invisible.
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    resultado = aplicacion.generar_narrativa({"total_kwh_mes": 300, "simbolo_moneda": "$"})

    assert resultado["fuente"] == "respaldo_sin_api_key"
    assert "300" in resultado["texto"]


def test_un_fallo_de_groq_no_rompe_la_respuesta(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")

    def explota(*args, **kwargs):
        raise RuntimeError("la API no responde")

    monkeypatch.setattr(aplicacion.groq, "obtener_llm", explota)
    resultado = aplicacion.generar_narrativa({"total_kwh_mes": 300, "simbolo_moneda": "$"})

    assert resultado["fuente"] == "respaldo_error"
    assert resultado["texto"]


def test_interpretar_campo_sin_clave_devuelve_un_valor_de_la_lista(monkeypatch):
    """
    Regresión: el respaldo devolvía `texto[:50]`, o sea el texto crudo del
    usuario, saltándose la lista blanca que sí aplica la rama con LLM.
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    aplicacion.limiter.enabled = False
    aplicacion.app.config["TESTING"] = True
    cliente = aplicacion.app.test_client()

    respuesta = cliente.post(
        "/api/interpretar-campo",
        json={"campo": "tipo_inmueble", "texto": "un galpón reconvertido en loft"},
    )
    cuerpo = respuesta.get_json()

    assert respuesta.status_code == 200
    assert cuerpo["valor_mapeado"] in ["Casa", "Casa pareada", "Departamento", "Casa móvil", "Otro"]


# ── Clave rechazada: configuración, no excepción ──────────────────────────────

class ErrorDeAutenticacion(Exception):
    """Imita el 401 que devuelve el SDK de Groq."""
    status_code = 401


@pytest.mark.parametrize(
    "error,esperado",
    [
        (ErrorDeAutenticacion("Error code: 401 - invalid_api_key"), True),
        (Exception("Error code: 401 - {'code': 'invalid_api_key'}"), True),
        (Exception("Invalid API Key"), True),
        (TimeoutError("la API no responde"), False),
        (Exception("rate limit exceeded"), False),
    ],
)
def test_se_distingue_la_clave_invalida_de_otros_fallos(error, esperado):
    assert llm.es_error_de_credenciales(error) is esperado


def test_una_clave_rechazada_se_marca_aparte_y_no_rompe_el_calculo(monkeypatch, caplog):
    """
    Un 401 se repite en CADA petición: volcar la traza completa cada vez entierra
    el mensaje accionable. Se registra una línea clara y el diagnóstico sigue.
    """
    monkeypatch.setenv("GROQ_API_KEY", "clave-caducada")

    def rechaza(*args, **kwargs):
        raise ErrorDeAutenticacion("Error code: 401 - invalid_api_key")

    monkeypatch.setattr(aplicacion.groq, "obtener_llm", rechaza)

    with caplog.at_level("ERROR"):
        resultado = aplicacion.generar_narrativa({"total_kwh_mes": 300, "simbolo_moneda": "$"})

    assert resultado["fuente"] == "respaldo_credencial_invalida"
    assert resultado["texto"], "el usuario debe recibir su diagnóstico igual"
    assert ".env" in caplog.text, "el log debe decir cómo arreglarlo"
    assert "Traceback" not in caplog.text, "un 401 no necesita traza en cada petición"


def test_el_limite_de_tasa_corta_el_abuso(monkeypatch):
    """
    Regresión de 3.8: los endpoints que gastan cuota de Groq no pedían
    credenciales ni tenían tope, así que cualquiera podía agotar la cuenta.
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    aplicacion.app.config["TESTING"] = True
    cliente = aplicacion.app.test_client()

    aplicacion.limiter.enabled = True
    try:
        payload = {"campo": "tipo_inmueble", "texto": "una casa"}
        codigos = [cliente.post("/api/interpretar-campo", json=payload).status_code for _ in range(25)]
    finally:
        aplicacion.limiter.enabled = False
        aplicacion.limiter.reset()

    assert 429 in codigos, "el endpoint aceptó 25 llamadas seguidas sin limitar"
    assert codigos.count(200) <= 20


def test_los_errores_no_filtran_detalle_al_cliente(monkeypatch):
    """Regresión de 3.8: se devolvía str(e) en el cuerpo de la respuesta."""
    monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
    aplicacion.limiter.enabled = False
    aplicacion.app.config["TESTING"] = True

    def explota(*args, **kwargs):
        raise RuntimeError("/ruta/interna/secreta del servidor")

    monkeypatch.setattr(aplicacion.groq, "obtener_llm", explota)
    respuesta = aplicacion.app.test_client().post(
        "/api/interpretar-campo", json={"campo": "tipo_inmueble", "texto": "algo raro"}
    )
    cuerpo = respuesta.get_json()

    assert "detalle" not in cuerpo
    assert "secreta" not in str(cuerpo)

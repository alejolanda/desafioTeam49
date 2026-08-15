"""
Tests de `/api/subir-boleta` y `/api/calcular`.

Se cubren los caminos que no necesitan a Groq: validación del archivo,
degradación sin clave y aplicación de la tarifa. Las rutas de extracción con
modelo quedan para cuando la 4.2 conecte el endpoint a la interfaz.
"""
import io

import pytest

import app as aplicacion


@pytest.fixture(autouse=True)
def entorno_de_prueba(monkeypatch):
    aplicacion.app.config["TESTING"] = True
    aplicacion.limiter.enabled = False
    monkeypatch.setattr(
        aplicacion, "generar_narrativa", lambda resumen: {"texto": "narrativa de prueba", "fuente": "test"}
    )


@pytest.fixture
def cliente():
    return aplicacion.app.test_client()


def subir(cliente, nombre="boleta.jpg", contenido=b"contenido falso", pais="CL"):
    return cliente.post(
        "/api/subir-boleta",
        data={"boleta": (io.BytesIO(contenido), nombre), "pais": pais},
        content_type="multipart/form-data",
    )


# ── Validación del archivo ────────────────────────────────────────────────────

def test_sin_archivo_devuelve_400(cliente):
    respuesta = cliente.post("/api/subir-boleta", data={}, content_type="multipart/form-data")
    assert respuesta.status_code == 400


def test_extension_no_permitida_devuelve_400(cliente):
    respuesta = subir(cliente, nombre="boleta.exe")
    assert respuesta.status_code == 400
    assert "PDF" in respuesta.get_json()["error"]


def test_nombre_vacio_devuelve_400(cliente):
    respuesta = subir(cliente, nombre="")
    assert respuesta.status_code == 400


# ── Degradación y límites (3.6, 3.7) ──────────────────────────────────────────

def test_sin_clave_de_api_la_imagen_devuelve_503(cliente, monkeypatch):
    """Antes devolvía 500 y el mensaje mencionaba el archivo .env del servidor."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    respuesta = subir(cliente)

    assert respuesta.status_code == 503
    assert ".env" not in respuesta.get_json()["error"]


def test_imagen_demasiado_grande_se_rechaza_antes_de_llamar_a_la_api(cliente, monkeypatch):
    """
    Regresión de 3.7: se aceptaban hasta 10 MB y se enviaban en base64 (un ~33%
    más), por encima del tope de la API. La llamada se gastaba para nada.
    """
    monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
    monkeypatch.setattr(aplicacion.groq, "MAX_IMAGEN_MB", 0.00001)

    def no_debe_llamarse(*args, **kwargs):
        raise AssertionError("no se debe construir el cliente para una imagen fuera de tamaño")

    monkeypatch.setattr(aplicacion.groq, "obtener_llm", no_debe_llamarse)
    respuesta = subir(cliente, contenido=b"x" * 5000)

    assert respuesta.status_code == 413
    assert "MB" in respuesta.get_json()["error"]


def test_el_archivo_temporal_se_borra_siempre(cliente, monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setitem(aplicacion.app.config, "UPLOAD_FOLDER", str(tmp_path))

    subir(cliente)
    assert list(tmp_path.iterdir()) == [], "quedó basura en el directorio de subidas"


# ── /api/calcular: la tarifa del país (2.1) ───────────────────────────────────

def test_calcular_usa_la_tarifa_del_pais(cliente):
    from src import calculos

    payload = {"electrodomesticos": [{"clave": "television", "horas": 4}]}

    chile = cliente.post("/api/calcular", json={**payload, "pais": "CL"}).get_json()
    dominicana = cliente.post("/api/calcular", json={**payload, "pais": "DO"}).get_json()

    assert chile["tarifa_aplicada"] == calculos.tarifa_de("CL")
    assert dominicana["tarifa_aplicada"] == calculos.tarifa_de("DO")
    assert chile["moneda"] == "CLP"
    assert dominicana["moneda"] == "DOP"

    # Mismo consumo, distinto dinero: antes ambos salían en CLP.
    assert chile["total_kwh_mes"] == dominicana["total_kwh_mes"]
    assert chile["total_clp_mes"] != dominicana["total_clp_mes"]
    assert chile["desglose"][0]["ahorro_clp_mes"] != dominicana["desglose"][0]["ahorro_clp_mes"]


def test_calcular_ignora_artefactos_desconocidos_sin_romperse(cliente):
    respuesta = cliente.post(
        "/api/calcular",
        json={"pais": "CL", "electrodomesticos": [{"clave": "teletransportador", "horas": 2}]},
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json()["total_kwh_mes"] == 0


def test_comparar_con_payload_incompleto_devuelve_400(cliente):
    """Regresión de 5.4: un KeyError se convertía en 500."""
    respuesta = cliente.post("/api/comparar", json={"pais": "CL"})
    assert respuesta.status_code == 400

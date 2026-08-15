"""
Tests del proxy de geocodificación inversa (tarea 5.8).

Ninguno sale a la red: se sustituye la consulta a Nominatim por un doble.
"""
import pytest

import app as aplicacion
from src import geo


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    aplicacion.app.config["TESTING"] = True
    aplicacion.limiter.enabled = False
    geo._consultar.cache_clear()


@pytest.fixture
def cliente():
    return aplicacion.app.test_client()


def respuesta_nominatim(codigo="cl", pais="Chile", ciudad="Santiago", estado="Región Metropolitana"):
    return {"address": {"country_code": codigo, "country": pais, "city": ciudad, "state": estado}}


# ── Identificación exigida por la política de uso ─────────────────────────────

def test_sin_contacto_configurado_no_se_llama_al_servicio(monkeypatch, cliente):
    """
    La política de Nominatim exige un User-Agent que identifique la aplicación.
    Sin contacto configurado no se hace la petición: se degrada a ingreso manual.
    """
    monkeypatch.setattr(geo, "CONTACTO", "")

    def no_debe_llamarse(*args, **kwargs):
        raise AssertionError("no se debe consultar Nominatim sin identificación")

    monkeypatch.setattr(geo.urllib.request, "urlopen", no_debe_llamarse)

    respuesta = cliente.get("/api/ubicacion?lat=-33.45&lon=-70.66")
    assert respuesta.status_code == 503
    assert geo.disponible() is False


def test_el_user_agent_incluye_el_contacto(monkeypatch):
    monkeypatch.setattr(geo, "CONTACTO", "equipo@ejemplo.org")
    monkeypatch.setattr(geo, "NOMBRE_APP", "VolticvS/1.0")
    assert geo._user_agent() == "VolticvS/1.0 (equipo@ejemplo.org)"


# ── Mapeo del país ────────────────────────────────────────────────────────────

def test_devuelve_el_codigo_iso_y_el_nombre_propio(monkeypatch, cliente):
    """
    Regresión de 5.8: el frontend comparaba el nombre traducido de Nominatim
    contra la lista en español y no encontraba la opción.
    """
    monkeypatch.setattr(geo, "CONTACTO", "equipo@ejemplo.org")
    monkeypatch.setattr(geo, "_consultar", lambda lat, lon: respuesta_nominatim("us", "United States", "Austin", "Texas"))

    datos = cliente.get("/api/ubicacion?lat=30.27&lon=-97.74").get_json()

    assert datos["pais_codigo"] == "US"
    # El nombre viene de la lista propia, no de la respuesta traducida.
    assert datos["pais_nombre"] == "Estados Unidos"
    assert datos["soportado"] is True
    assert datos["region"] == "Texas"
    assert datos["comuna"] == "Austin"


def test_pais_no_soportado_se_marca_en_vez_de_fallar(monkeypatch, cliente):
    monkeypatch.setattr(geo, "CONTACTO", "equipo@ejemplo.org")
    monkeypatch.setattr(geo, "_consultar", lambda lat, lon: respuesta_nominatim("jp", "Japón", "Kioto", "Kansai"))

    datos = cliente.get("/api/ubicacion?lat=35.01&lon=135.76").get_json()

    assert datos["soportado"] is False
    assert datos["pais_codigo"] is None
    # Se conserva lo que sí se sabe para que el asistente pueda mostrarlo.
    assert datos["comuna"] == "Kioto"


# ── Validación de entrada ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "consulta",
    ["", "?lat=abc&lon=1", "?lat=95&lon=0", "?lat=0&lon=200", "?lat=-33.45", "?lon=-70.66"],
)
def test_coordenadas_invalidas_devuelven_400(monkeypatch, cliente, consulta):
    monkeypatch.setattr(geo, "CONTACTO", "equipo@ejemplo.org")
    assert cliente.get(f"/api/ubicacion{consulta}").status_code == 400


# ── Caché y precisión ─────────────────────────────────────────────────────────

def test_las_coordenadas_se_redondean_antes_de_salir(monkeypatch):
    """Se consulta a ~1 km, coherente con el zoom=10 que resuelve a nivel de ciudad."""
    monkeypatch.setattr(geo, "CONTACTO", "equipo@ejemplo.org")
    vistas = []
    monkeypatch.setattr(geo, "_consultar", lambda lat, lon: vistas.append((lat, lon)) or respuesta_nominatim())

    geo.ubicacion_desde_coordenadas(-33.456789, -70.661234)
    assert vistas == [(-33.46, -70.66)]


def test_la_misma_coordenada_no_se_consulta_dos_veces(monkeypatch):
    """Nominatim es un servicio comunitario gratuito: cachear no es opcional."""
    monkeypatch.setattr(geo, "CONTACTO", "equipo@ejemplo.org")
    llamadas = []

    class RespuestaFalsa:
        def read(self):
            llamadas.append(1)
            return b'{"address": {"country_code": "cl", "country": "Chile", "city": "Santiago"}}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(geo.urllib.request, "urlopen", lambda *a, **k: RespuestaFalsa())
    monkeypatch.setattr(geo, "INTERVALO_MINIMO_S", 0)

    geo.ubicacion_desde_coordenadas(-33.45, -70.66)
    geo.ubicacion_desde_coordenadas(-33.451, -70.662)  # redondea a lo mismo

    assert len(llamadas) == 1, "la segunda consulta debió salir de la caché"


def test_un_fallo_del_servicio_no_rompe_la_aplicacion(monkeypatch, cliente):
    monkeypatch.setattr(geo, "CONTACTO", "equipo@ejemplo.org")

    def explota(*args, **kwargs):
        raise TimeoutError("el servicio no responde")

    monkeypatch.setattr(geo.urllib.request, "urlopen", explota)
    monkeypatch.setattr(geo, "INTERVALO_MINIMO_S", 0)

    respuesta = cliente.get("/api/ubicacion?lat=-33.45&lon=-70.66")
    assert respuesta.status_code == 503
    assert "no responde" not in str(respuesta.get_json()), "no debe filtrarse el detalle interno"

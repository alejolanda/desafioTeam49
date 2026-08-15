"""
Smoke tests: verifican que la app levanta y que los endpoints deterministas
responden. Ninguno de estos tests llama a Groq, por lo que corren sin GROQ_API_KEY.

La bateria real de `src/calculos.py` llega en la tarea 2.6 del plan.
"""
import pytest

import app as aplicacion
from src import calculos


@pytest.fixture
def cliente():
    aplicacion.app.config["TESTING"] = True
    return aplicacion.app.test_client()


def test_datos_de_referencia_cargan():
    assert "electrodomesticos" in calculos.REFERENCIA
    assert "paises" in calculos.REFERENCIA
    assert calculos.REFERENCIA["electrodomesticos"], "la tabla de artefactos no puede estar vacia"


def test_index_responde(cliente):
    assert cliente.get("/").status_code == 200


def test_paises_excluye_claves_de_metadatos(cliente):
    respuesta = cliente.get("/api/paises")
    assert respuesta.status_code == 200

    paises = respuesta.get_json()
    assert paises, "se esperaba al menos un pais configurado"
    assert not [clave for clave in paises if clave.startswith("_")], "no deben filtrarse las claves _nota"


def test_artefacto_desconocido_es_rechazado():
    with pytest.raises(ValueError):
        calculos.consumo_mensual_standby("artefacto_que_no_existe", horas_uso_diario=1, tarifa=150)


# ── Sonda de salud (tarea 6.6) ────────────────────────────────────────────────

def test_health_responde_sin_llamar_a_servicios_externos(cliente, monkeypatch):
    """
    La sonda corre cada 30 s desde el HEALTHCHECK del contenedor: no puede
    gastar cuota de Groq ni pegarle a Nominatim.
    """
    def no_debe_llamarse(*args, **kwargs):
        raise AssertionError("/health no debe consultar servicios externos")

    monkeypatch.setattr(aplicacion.groq, "obtener_llm", no_debe_llamarse)
    monkeypatch.setattr(aplicacion.geo, "ubicacion_desde_coordenadas", no_debe_llamarse)

    respuesta = cliente.get("/health")
    datos = respuesta.get_json()

    assert respuesta.status_code == 200
    assert datos["estado"] == "ok"
    assert datos["paises"] > 0
    assert datos["artefactos"] > 0


def test_health_no_expone_credenciales(cliente):
    cuerpo = cliente.get("/health").get_data(as_text=True)
    assert "gsk_" not in cuerpo
    # Informa si estan configuradas, nunca su valor.
    assert isinstance(cliente.get("/health").get_json()["groq_configurado"], bool)


def test_health_esta_exenta_del_limite_de_tasa(cliente):
    """Si la sonda recibiera 429, el orquestador daria el contenedor por muerto."""
    aplicacion.limiter.enabled = True
    try:
        codigos = [cliente.get("/health").status_code for _ in range(40)]
    finally:
        aplicacion.limiter.enabled = False
        aplicacion.limiter.reset()

    assert set(codigos) == {200}, "la sonda de salud no debe estar limitada"

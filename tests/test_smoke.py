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
        calculos.consumo_mensual_standby("artefacto_que_no_existe", horas_uso_diario=1)

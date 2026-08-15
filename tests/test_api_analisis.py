"""
Tests del endpoint principal `/api/analisis-energetico`.

La narrativa se sustituye por un doble para que la batería no llame a Groq:
sin esto cada test consumiría cuota y dependería de la red.
"""
import pytest

import app as aplicacion


@pytest.fixture(autouse=True)
def sin_llamadas_al_llm(monkeypatch):
    monkeypatch.setattr(aplicacion, "generar_narrativa", lambda resumen: "narrativa de prueba")


@pytest.fixture
def cliente():
    aplicacion.app.config["TESTING"] = True
    return aplicacion.app.test_client()


def analizar(cliente, **campos):
    respuesta = cliente.post("/api/analisis-energetico", json=campos)
    assert respuesta.status_code == 200, respuesta.get_data(as_text=True)
    return respuesta.get_json()


# ── Tarifa y moneda ───────────────────────────────────────────────────────────

def test_cada_pais_usa_su_moneda_y_su_tarifa():
    """Regresión de 2.1/2.2: todo se valorizaba con la tarifa chilena."""
    import src.calculos as calculos

    aplicacion.app.config["TESTING"] = True
    cliente = aplicacion.app.test_client()

    # Se usa el televisor y no el refrigerador: el refrigerador funciona 24 h,
    # así que no tiene horas de standby y su ahorro es legítimamente 0.
    chile = analizar(cliente, pais="CL", tv=1, tv_frecuencia=21)
    dominicana = analizar(cliente, pais="DO", tv=1, tv_frecuencia=21)

    assert chile["moneda"] == "CLP" and chile["simbolo_moneda"] == "$"
    assert dominicana["moneda"] == "DOP" and dominicana["simbolo_moneda"] == "RD$"

    assert chile["tarifa_aplicada"] == calculos.tarifa_de("CL")
    assert dominicana["tarifa_aplicada"] == calculos.tarifa_de("DO")

    # Mismo hogar, mismo consumo, distinto dinero.
    assert chile["consumo_kwh"] == dominicana["consumo_kwh"]
    assert chile["costo_estimado"] != dominicana["costo_estimado"]
    assert chile["ahorro_estimado"] != dominicana["ahorro_estimado"]


def test_pais_desconocido_devuelve_400(cliente):
    respuesta = cliente.post("/api/analisis-energetico", json={"pais": "XX"})
    assert respuesta.status_code == 400
    assert "paises_soportados" in respuesta.get_json()


def test_tarifa_explicita_de_la_boleta_gana_a_la_referencial(cliente):
    referencial = analizar(cliente, pais="CL", consumo=100)
    propia = analizar(cliente, pais="CL", consumo=100, tarifa_kwh=999)

    assert propia["tarifa_aplicada"] == 999
    assert propia["costo_estimado"] > referencial["costo_estimado"]


# ── Consumo declarado vs estimado ─────────────────────────────────────────────

def test_consumo_declarado_se_respeta(cliente):
    resultado = analizar(cliente, pais="CL", consumo=350)
    assert resultado["consumo_kwh"] == 350
    assert resultado["fuente_consumo"] == "declarado"


def test_consumo_anual_se_convierte_a_mensual(cliente):
    resultado = analizar(cliente, pais="CL", consumo=1200, flag_anual=1)
    assert resultado["consumo_kwh"] == 100
    assert resultado["fuente_consumo"] == "declarado"


def test_sin_datos_no_se_inventa_un_consumo_minimo(cliente):
    """
    El motor anterior devolvía 50 kWh de 'consumo base estimado' cuando no había
    ningún dato. Presentar una cifra inventada como estimación es peor que decir
    que no hay datos suficientes.
    """
    resultado = analizar(cliente, pais="CL")
    assert resultado["consumo_kwh"] == 0
    assert resultado["fuente_consumo"] == "sin_datos"


def test_consumo_estimado_desde_artefactos(cliente):
    resultado = analizar(cliente, pais="CL", refrigerador=1, habitantes_mayores=2)
    assert resultado["fuente_consumo"] == "estimado"
    assert resultado["consumo_kwh"] > 0
    assert resultado["desglose"]


# ── Ahorro real, no un 20% fijo ───────────────────────────────────────────────

def test_el_ahorro_ya_no_es_el_20_por_ciento_del_costo(cliente):
    """Regresión de 2.4."""
    resultado = analizar(cliente, pais="CL", tv=2, tv_frecuencia=21)
    assert resultado["ahorro_estimado"] != pytest.approx(resultado["costo_estimado"] * 0.20, rel=1e-6)
    assert resultado["fuente_ahorro"] == "desglose_artefactos"


def test_sin_artefactos_declarados_el_ahorro_es_cero(cliente):
    resultado = analizar(cliente, pais="CL", consumo=400)
    assert resultado["ahorro_estimado"] == 0
    assert resultado["fuente_ahorro"] == "sin_artefactos_declarados"


def test_declarar_boleta_y_artefactos_da_consumo_declarado_y_ahorro_real(cliente):
    """El consumo de la boleta es más fiable, pero el ahorro necesita el desglose."""
    resultado = analizar(cliente, pais="CL", consumo=400, tv=2, tv_frecuencia=21)
    assert resultado["consumo_kwh"] == 400
    assert resultado["fuente_consumo"] == "declarado"
    assert resultado["ahorro_estimado"] > 0
    assert resultado["fuente_ahorro"] == "desglose_artefactos"


# ── Contrato de la respuesta ──────────────────────────────────────────────────

def test_probabilidad_ya_no_se_expone(cliente):
    """Regresión de 2.5: eran 0.90/0.75/0.82 sin significado medible."""
    assert "probabilidad" not in analizar(cliente, pais="CL", consumo=300)


def test_los_alias_de_compatibilidad_coinciden_con_los_campos_primarios(cliente):
    r = analizar(cliente, pais="CL", refrigerador=1)
    assert r["total_kwh_mes"] == r["consumo_kwh"]
    assert r["total_clp_mes"] == r["costo_estimado"]
    assert r["costo_estimado_mensual"] == r["costo_estimado"]
    assert r["ahorro_potencial_clp_mes"] == r["ahorro_estimado"]


@pytest.mark.parametrize(
    "consumo,categoria",
    [(100, "Eficiente"), (300, "Moderado"), (600, "Ineficiente")],
)
def test_clasificacion_por_tramos(cliente, consumo, categoria):
    assert analizar(cliente, pais="CL", consumo=consumo)["categoria"] == categoria


def test_payload_basura_no_rompe_el_endpoint(cliente):
    resultado = analizar(cliente, pais="CL", refrigerador=None, tv="", consumo="abc", dormitorios=[])
    assert resultado["status"] == "success"
    assert resultado["consumo_kwh"] == 0

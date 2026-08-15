"""
Tests del motor de cálculo (tarea 2.6 del plan).

`src/calculos.py` es matemática pura y determinista: es la parte del sistema
que se puede verificar de forma exacta, incluso contra la física en el caso del
hervidor. Estos tests fijan ese comportamiento antes de que la Fase 3 y la
Fase 4 empiecen a mover el resto de la aplicación.
"""
import pytest

from src import calculos

TARIFA_CL = 150.0


# ── Tarifas y países: fuente única ────────────────────────────────────────────

def test_todos_los_paises_tienen_los_campos_obligatorios():
    for codigo, pais in calculos.PAISES.items():
        for campo in ("nombre", "moneda", "simbolo", "tarifa_kwh_referencial", "fuente"):
            assert campo in pais, f"{codigo} no declara '{campo}'"
        assert float(pais["tarifa_kwh_referencial"]) > 0, f"{codigo} tiene tarifa no positiva"


def test_paises_no_expone_las_notas_del_json():
    assert not [c for c in calculos.PAISES if c.startswith("_")]


def test_pais_desconocido_falla_en_vez_de_cobrar_en_dolares():
    # Antes `_get_tarifa` caía silenciosamente a 0.18 USD para cualquier código.
    with pytest.raises(calculos.PaisNoSoportado):
        calculos.obtener_pais("XX")


def test_tarifa_de_devuelve_la_del_json():
    assert calculos.tarifa_de("CL") == calculos.PAISES["CL"]["tarifa_kwh_referencial"]
    assert calculos.tarifa_de("DO") == calculos.PAISES["DO"]["tarifa_kwh_referencial"]


def test_kwh_a_dinero_exige_tarifa():
    with pytest.raises(ValueError):
        calculos.kwh_a_dinero(100, None)


def test_la_tarifa_del_pais_se_aplica_de_verdad():
    """Regresión de la tarea 2.1: el ahorro se calculaba siempre en CLP."""
    kwh = 100
    assert calculos.kwh_a_dinero(kwh, calculos.tarifa_de("CL")) == 15000.0
    assert calculos.kwh_a_dinero(kwh, calculos.tarifa_de("DO")) == 1250.0


# ── Consumo con standby ───────────────────────────────────────────────────────

def test_standby_suma_consumo_fantasma():
    conectado = calculos.consumo_mensual_standby("television", 4, TARIFA_CL)
    desconectado = calculos.consumo_mensual_standby("television", 4, TARIFA_CL, queda_conectado=False)

    assert conectado["kwh_mes_actual"] > desconectado["kwh_mes_actual"]
    assert conectado["ahorro_kwh_mes"] > 0
    # Sin standby no hay nada que ahorrar desconectando.
    assert desconectado["ahorro_kwh_mes"] == 0
    assert desconectado["kwh_mes_actual"] == desconectado["kwh_mes_optimo"]


def test_consumo_escala_con_la_cantidad():
    uno = calculos.consumo_mensual_standby("television", 4, TARIFA_CL)
    tres = calculos.consumo_mensual_standby("television", 4, TARIFA_CL, cantidad=3)
    assert tres["kwh_mes_actual"] == pytest.approx(uno["kwh_mes_actual"] * 3, rel=1e-6)


def test_veces_semana_no_infla_el_consumo_mensual():
    """Una secadora usada 2 veces por semana no puede consumir como si fuera diaria."""
    diaria = calculos.consumo_mensual_standby("secadora_ropa", 1.87, TARIFA_CL)
    dos_veces = calculos.consumo_mensual_standby("secadora_ropa", 1.87, TARIFA_CL, veces_semana=2)
    # rel holgado a propósito: el motor redondea a 2 decimales antes de devolver.
    assert dos_veces["kwh_mes_actual"] == pytest.approx(diaria["kwh_mes_actual"] * 2 / 7, rel=1e-3)


def test_valor_conocido_television():
    # 100 W en uso, 1 W en standby, 4 h/día, 30 días:
    # (100*4 + 1*20) * 30 / 1000 = 12.6 kWh/mes
    assert calculos.consumo_mensual_standby("television", 4, TARIFA_CL)["kwh_mes_actual"] == 12.6


def test_artefacto_desconocido_lanza_error():
    with pytest.raises(ValueError):
        calculos.consumo_mensual_standby("teletransportador", 1, TARIFA_CL)


def test_refrigerador_tiene_consumo_domestico_plausible():
    """
    Regresión: con 150 W aplicados 24/7 daban 108 kWh/mes, unas 3 veces el
    consumo real. El JSON declaraba la potencia del compresor en marcha, no la
    media con el ciclado.
    """
    kwh = calculos.consumo_mensual_standby("refrigerador", 24, TARIFA_CL)["kwh_mes_actual"]
    assert 25 <= kwh <= 60, f"{kwh} kWh/mes está fuera del rango doméstico razonable"


# ── Iluminación ───────────────────────────────────────────────────────────────

def test_led_no_ahorra_contra_si_mismo():
    resultado = calculos.consumo_iluminacion("led", 10, 5, TARIFA_CL)
    assert resultado["ahorro_kwh_mes"] == 0


def test_incandescente_ahorra_al_pasar_a_led():
    resultado = calculos.consumo_iluminacion("incandescente", 10, 5, TARIFA_CL)
    # (60-9) W * 10 ampolletas * 5 h * 30 días / 1000 = 76.5 kWh/mes
    assert resultado["ahorro_kwh_mes"] == 76.5
    assert resultado["ahorro_clp_anual"] == pytest.approx(resultado["ahorro_clp_mes"] * 12, rel=1e-3)


def test_tipo_de_iluminacion_desconocido_lanza_error():
    with pytest.raises(ValueError):
        calculos.consumo_iluminacion("antorcha", 1, 1, TARIFA_CL)


def test_ahorro_iluminacion_led_compara_incandescente_contra_led():
    resultado = calculos.ahorro_iluminacion_led(10, 5, TARIFA_CL)
    assert resultado["kwh_mes_incandescente"] == 90.0   # 60 W * 10 * 5 h * 30 / 1000
    assert resultado["kwh_mes_led"] == 13.5             #  9 W * 10 * 5 h * 30 / 1000
    assert resultado["ahorro_kwh_mes"] == 76.5


# ── Artefactos fuera de la tabla de referencia ────────────────────────────────

def test_consumo_personalizado_usa_los_watts_del_usuario():
    # 300 W * 8 h * 30 días / 1000 = 72 kWh/mes
    resultado = calculos.consumo_personalizado("Máquina de café profesional", 300, 8, TARIFA_CL)
    assert resultado["kwh_mes_actual"] == 72.0
    assert resultado["clp_mes_actual"] == calculos.kwh_a_dinero(72.0, TARIFA_CL)


def test_consumo_personalizado_cuenta_el_standby():
    sin_standby = calculos.consumo_personalizado("Equipo", 300, 8, TARIFA_CL)
    con_standby = calculos.consumo_personalizado("Equipo", 300, 8, TARIFA_CL, watts_standby=10)
    assert con_standby["kwh_mes_actual"] > sin_standby["kwh_mes_actual"]


# ── Hervidor: verificable contra la física ────────────────────────────────────

def test_hervidor_coincide_con_la_termodinamica():
    """
    Calentar 1 L de 20 °C a 100 °C con 90% de eficiencia:
    1 kg * 4186 J/kg°C * 80 °C / 0.9 = 372 089 J = 0.1034 kWh
    """
    resultado = calculos.ahorro_hervidor(1.0, 0.0, TARIFA_CL, usos_por_dia=1)
    esperado_mes = (1 * 4186 * 80 / 0.9) / 3_600_000 * 30
    assert resultado["kwh_mes_llenado_habitual"] == pytest.approx(esperado_mes, rel=1e-3)


def test_hervir_solo_lo_necesario_ahorra():
    resultado = calculos.ahorro_hervidor(1.7, 0.25, TARIFA_CL, usos_por_dia=3)
    assert resultado["ahorro_kwh_mes"] > 0
    assert resultado["kwh_mes_llenado_habitual"] > resultado["kwh_mes_solo_lo_necesario"]


def test_hervidor_sin_exceso_no_ahorra():
    resultado = calculos.ahorro_hervidor(0.5, 0.5, TARIFA_CL)
    assert resultado["ahorro_kwh_mes"] == 0


# ── Perfil de hogar: el motor único que alimenta el wizard ────────────────────

def test_perfil_vacio_no_inventa_consumo():
    resultado = calculos.estimar_desde_perfil({}, TARIFA_CL)
    assert resultado["consumo_kwh"] == 0
    assert resultado["items"] == []
    assert resultado["desglose"] == {}


def test_perfil_suma_equipos_y_habitantes():
    resultado = calculos.estimar_desde_perfil(
        {"refrigerador": 1, "habitantes_mayores": 2, "habitantes_menores": 1}, TARIFA_CL
    )
    # 2 adultos * 30 + 1 menor * 15 = 75 kWh de base
    assert resultado["desglose"]["Iluminación y uso base por habitantes"] == 75
    assert "Refrigerador" in resultado["desglose"]
    assert resultado["consumo_kwh"] == pytest.approx(75 + 36, rel=1e-2)


def test_perfil_ignora_valores_no_numericos():
    resultado = calculos.estimar_desde_perfil({"refrigerador": "dos", "tv": None}, TARIFA_CL)
    assert resultado["consumo_kwh"] == 0


def test_perfil_escala_con_la_cantidad_de_equipos():
    uno = calculos.estimar_desde_perfil({"refrigerador": 1}, TARIFA_CL)["consumo_kwh"]
    dos = calculos.estimar_desde_perfil({"refrigerador": 2}, TARIFA_CL)["consumo_kwh"]
    assert dos == pytest.approx(uno * 2, rel=1e-6)


def test_perfil_respeta_la_tarifa_del_pais():
    chile = calculos.estimar_desde_perfil({"tv": 1, "tv_frecuencia": 21}, calculos.tarifa_de("CL"))
    dominicana = calculos.estimar_desde_perfil({"tv": 1, "tv_frecuencia": 21}, calculos.tarifa_de("DO"))

    assert chile["consumo_kwh"] == dominicana["consumo_kwh"]  # el consumo no depende del país
    assert chile["ahorro_dinero_mes"] != dominicana["ahorro_dinero_mes"]  # el dinero sí


def test_el_ahorro_sale_del_desglose_y_no_de_un_porcentaje_fijo():
    """
    Regresión de la tarea 2.4: el ahorro era `costo * 0.20`, idéntico para todos.
    Ahora un hogar con equipos que quedan en standby tiene ahorro, y uno sin
    equipos declarados no tiene ninguno.
    """
    con_standby = calculos.estimar_desde_perfil({"tv": 2, "tv_frecuencia": 21}, TARIFA_CL)
    solo_habitantes = calculos.estimar_desde_perfil({"habitantes_mayores": 3}, TARIFA_CL)

    assert con_standby["ahorro_dinero_mes"] > 0
    assert solo_habitantes["ahorro_dinero_mes"] == 0
    assert solo_habitantes["consumo_kwh"] == 90


def test_perfil_acota_las_horas_de_television():
    """tv_frecuencia son horas por semana; nunca deben superar 24 h/día."""
    absurdo = calculos.estimar_desde_perfil({"tv": 1, "tv_frecuencia": 1000}, TARIFA_CL)
    tope = calculos.consumo_mensual_standby("television", 24, TARIFA_CL)
    assert absurdo["consumo_kwh"] <= tope["kwh_mes_actual"] + 0.01


# ── Comparador y factura ──────────────────────────────────────────────────────

def test_comparar_ordena_de_menor_a_mayor_consumo():
    resultado = calculos.comparar_categoria("aspiradora", 1, TARIFA_CL)
    kwh = [o["kwh_mes"] for o in resultado["opciones"]]
    assert kwh == sorted(kwh)
    assert resultado["es_catalogo_ejemplo"] is True


def test_categoria_desconocida_lanza_error():
    with pytest.raises(ValueError):
        calculos.comparar_categoria("nave_espacial", 1, TARIFA_CL)


def test_estimar_factura_total_suma_y_valoriza():
    resultado = calculos.estimar_factura_total([10, 20, 30], TARIFA_CL)
    assert resultado["kwh_mes_total_estimado"] == 60
    assert resultado["clp_mes_total_estimado"] == 9000.0

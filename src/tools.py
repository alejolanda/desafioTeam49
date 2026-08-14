from langchain_core.tools import tool
from src import calculos


@tool
def consultar_electrodomesticos_disponibles() -> str:
    """Devuelve la lista de electrodomésticos que el sistema reconoce, con su clave interna."""
    claves = list(calculos.REFERENCIA["electrodomesticos"].keys())
    nombres = {k: v["nombre"] for k, v in calculos.REFERENCIA["electrodomesticos"].items()}
    return "\n".join(f"- {k}: {nombres[k]}" for k in claves)


@tool
def calcular_consumo_artefacto(clave_artefacto: str, horas_uso_diario: float, cantidad: int = 1) -> dict:
    """
    Calcula el consumo mensual (kWh y CLP) de un artefacto y el ahorro potencial
    si se desconecta del standby cuando no está en uso.

    Args:
        clave_artefacto: clave interna del artefacto (ver consultar_electrodomesticos_disponibles)
        horas_uso_diario: horas al día que el artefacto está realmente en uso activo
        cantidad: cuántas unidades tiene el usuario de ese artefacto
    """
    return calculos.consumo_mensual_standby(clave_artefacto, horas_uso_diario, cantidad)


@tool
def calcular_ahorro_iluminacion(cantidad_ampolletas: int, horas_uso_diario: float) -> dict:
    """
    Calcula el ahorro mensual y anual (kWh y CLP) de cambiar ampolletas
    incandescentes por LED equivalentes.

    Args:
        cantidad_ampolletas: número de ampolletas incandescentes que tiene el usuario
        horas_uso_diario: horas promedio al día que están encendidas
    """
    return calculos.ahorro_iluminacion_led(cantidad_ampolletas, horas_uso_diario)


@tool
def calcular_ahorro_hervidor(litros_llenado_habitual: float, litros_necesarios: float, usos_por_dia: int = 1) -> dict:
    """
    Calcula el ahorro de hervir solo el agua necesaria (ej. una taza) en vez
    de llenar el hervidor completo, en kWh y CLP, mensual y anual.

    Args:
        litros_llenado_habitual: litros que el usuario suele hervir de una vez
        litros_necesarios: litros que realmente necesita (ej. 0.25 para una taza)
        usos_por_dia: cuántas veces al día hierve agua
    """
    return calculos.ahorro_hervidor(litros_llenado_habitual, litros_necesarios, usos_por_dia)


@tool
def estimar_factura_total(items_kwh_mes: list) -> dict:
    """
    Suma el consumo estimado (en kWh) de varios ítems para dar una proyección
    de la factura mensual total en CLP.

    Args:
        items_kwh_mes: lista de valores de consumo mensual en kWh de cada artefacto/uso analizado
    """
    return calculos.estimar_factura_total(items_kwh_mes)


HERRAMIENTAS = [
    consultar_electrodomesticos_disponibles,
    calcular_consumo_artefacto,
    calcular_ahorro_iluminacion,
    calcular_ahorro_hervidor,
    estimar_factura_total,
]

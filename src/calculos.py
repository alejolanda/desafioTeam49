"""
Motor de cálculo energético.

IMPORTANTE: Estas funciones son deterministas (matemática pura).
El LLM NUNCA debe calcular estos números por su cuenta; solo debe
extraer las variables de la conversación y llamar a estas funciones
como "tools". Esto evita alucinaciones en los montos de ahorro.
"""
import json
import os

RUTA_DATOS = os.path.join(os.path.dirname(__file__), "..", "data", "consumo_referencia.json")

with open(RUTA_DATOS, "r", encoding="utf-8") as f:
    REFERENCIA = json.load(f)


def kwh_a_clp(kwh: float, tarifa_clp_kwh: float = None) -> float:
    tarifa = tarifa_clp_kwh or REFERENCIA["tarifa"]["clp_por_kwh"]
    return round(kwh * tarifa, 1)


def consumo_mensual_standby(clave_artefacto: str, horas_uso_diario: float, cantidad: int = 1, queda_conectado: bool = True, veces_semana: float = 7) -> dict:
    """
    Calcula el consumo mensual de un artefacto considerando:
    - horas en uso activo (ej. horas reales de carga de un celular)
    - el resto del día en modo standby/fantasma, SOLO SI queda_conectado=True
      (si el usuario desconecta el cargador cuando no lo usa, no hay consumo fantasma)
    - veces_semana: cuántos días a la semana se usa (7 = todos los días, valor por
      defecto, mantiene el comportamiento anterior). Para lavadora/secadora/etc. que
      se usan 1-2 veces por semana, este valor evita inflar el consumo mensual.
    """
    ref = REFERENCIA["electrodomesticos"].get(clave_artefacto)
    if not ref:
        raise ValueError(f"Artefacto '{clave_artefacto}' no está en la tabla de referencia.")

    dias_al_mes = veces_semana * (30 / 7)
    horas_standby = max(0, 24 - horas_uso_diario) if queda_conectado else 0
    wh_dia = (ref["watts_uso"] * horas_uso_diario) + (ref["watts_standby"] * horas_standby)
    kwh_mes = (wh_dia * cantidad * dias_al_mes) / 1000

    # Escenario "ahorro": desconectar cuando no se usa (standby = 0)
    wh_dia_optimo = ref["watts_uso"] * horas_uso_diario
    kwh_mes_optimo = (wh_dia_optimo * cantidad * dias_al_mes) / 1000

    return {
        "nombre": ref["nombre"],
        "kwh_mes_actual": round(kwh_mes, 2),
        "kwh_mes_optimo": round(kwh_mes_optimo, 2),
        "ahorro_kwh_mes": round(kwh_mes - kwh_mes_optimo, 2),
        "ahorro_clp_mes": kwh_a_clp(kwh_mes - kwh_mes_optimo),
    }


def consumo_iluminacion(tipo: str, cantidad: int, horas_uso_diario: float) -> dict:
    """
    Calcula el consumo mensual de un tipo de iluminación (incandescente,
    fluorescente, neón, etc.) y lo compara contra el equivalente en LED
    para mostrar el ahorro potencial de cambiarse.
    """
    tipos = REFERENCIA["tipos_iluminacion"]
    ref = tipos.get(tipo)
    if not ref:
        raise ValueError(f"Tipo de iluminación '{tipo}' no está en la tabla de referencia.")

    watts_led = tipos["led"]["watts"]
    kwh_mes_actual = (ref["watts"] * cantidad * horas_uso_diario * 30) / 1000
    kwh_mes_si_fuera_led = (watts_led * cantidad * horas_uso_diario * 30) / 1000
    ahorro_kwh = max(0.0, kwh_mes_actual - kwh_mes_si_fuera_led)

    return {
        "nombre": f"Iluminación {ref['nombre']}",
        "kwh_mes_actual": round(kwh_mes_actual, 2),
        "kwh_mes_si_fuera_led": round(kwh_mes_si_fuera_led, 2),
        "ahorro_kwh_mes": round(ahorro_kwh, 2),
        "ahorro_clp_mes": kwh_a_clp(ahorro_kwh),
        "ahorro_clp_anual": kwh_a_clp(ahorro_kwh * 12),
    }


def ahorro_iluminacion_led(cantidad_ampolletas: int, horas_uso_diario: float) -> dict:
    incandescente = REFERENCIA["iluminacion"]["incandescente_60w"]["watts"]
    led = REFERENCIA["iluminacion"]["led_equivalente"]["watts"]

    kwh_mes_incandescente = (incandescente * cantidad_ampolletas * horas_uso_diario * 30) / 1000
    kwh_mes_led = (led * cantidad_ampolletas * horas_uso_diario * 30) / 1000
    ahorro_kwh = kwh_mes_incandescente - kwh_mes_led

    return {
        "kwh_mes_incandescente": round(kwh_mes_incandescente, 2),
        "kwh_mes_led": round(kwh_mes_led, 2),
        "ahorro_kwh_mes": round(ahorro_kwh, 2),
        "ahorro_clp_mes": kwh_a_clp(ahorro_kwh),
        "ahorro_clp_anual": kwh_a_clp(ahorro_kwh * 12),
    }


def ahorro_hervidor(litros_llenado_habitual: float, litros_necesarios: float, usos_por_dia: int = 1) -> dict:
    """
    Compara la energía usada al hervir de más (llenado habitual) vs.
    hervir solo el agua necesaria (ej. una taza).
    """
    datos = REFERENCIA["agua_caliente"]
    delta_t = datos["temp_final_c"] - datos["temp_inicial_c"]
    calor_esp = datos["calor_especifico_agua_j_kg_c"]
    eficiencia = datos["eficiencia_hervidor"]

    def energia_kwh(litros):
        masa_kg = litros  # 1 litro de agua ≈ 1 kg
        joules = masa_kg * calor_esp * delta_t / eficiencia
        return joules / 3_600_000  # J -> kWh

    kwh_habitual_dia = energia_kwh(litros_llenado_habitual) * usos_por_dia
    kwh_necesario_dia = energia_kwh(litros_necesarios) * usos_por_dia

    kwh_mes_habitual = kwh_habitual_dia * 30
    kwh_mes_necesario = kwh_necesario_dia * 30
    ahorro_kwh_mes = kwh_mes_habitual - kwh_mes_necesario

    return {
        "kwh_mes_llenado_habitual": round(kwh_mes_habitual, 2),
        "kwh_mes_solo_lo_necesario": round(kwh_mes_necesario, 2),
        "ahorro_kwh_mes": round(ahorro_kwh_mes, 2),
        "ahorro_clp_mes": kwh_a_clp(ahorro_kwh_mes),
        "ahorro_clp_anual": kwh_a_clp(ahorro_kwh_mes * 12),
    }


def consumo_personalizado(nombre: str, watts_uso: float, horas_uso_diario: float, watts_standby: float = 0, cantidad: int = 1) -> dict:
    """
    Igual que consumo_mensual_standby, pero para artefactos que el usuario
    describe con su propia potencia (W) en vez de usar una clave de la
    tabla de referencia. Sirve para casos particulares: máquina de café
    profesional, herramientas de taller, equipo médico de consulta, etc.
    """
    horas_standby = max(0, 24 - horas_uso_diario)
    wh_dia = (watts_uso * horas_uso_diario) + (watts_standby * horas_standby)
    kwh_mes = (wh_dia * cantidad * 30) / 1000

    return {
        "nombre": nombre,
        "kwh_mes_actual": round(kwh_mes, 2),
        "clp_mes_actual": kwh_a_clp(kwh_mes),
    }


def comparar_categoria(categoria: str, horas_uso_diario: float, tarifa_clp_kwh: float = None) -> dict:
    """
    Compara las opciones de una categoría de artefacto (ej. aspiradoras, aires
    acondicionados) por consumo mensual estimado.

    IMPORTANTE: el catálogo en 'categorias_comparables' es de EJEMPLO. Los
    modelos, watts y precios deben reemplazarse por datos reales de retailers
    (o conectarse a una API de shopping) antes de presentar esto como
    recomendación real a un usuario final.
    """
    cat = REFERENCIA.get("categorias_comparables", {}).get(categoria)
    if not cat:
        raise ValueError(f"Categoría '{categoria}' no está en el catálogo de comparación.")

    resultados = []
    for opcion in cat["opciones"]:
        kwh_mes = (opcion["watts"] * horas_uso_diario * 30) / 1000
        resultados.append({
            "nombre": opcion["nombre"],
            "watts": opcion["watts"],
            "precio_referencial": opcion["precio_referencial"],
            "kwh_mes": round(kwh_mes, 2),
            "clp_mes": kwh_a_clp(kwh_mes, tarifa_clp_kwh),
        })

    resultados.sort(key=lambda r: r["kwh_mes"])
    return {"categoria": categoria, "opciones": resultados, "es_catalogo_ejemplo": True}


def obtener_tarifa_pais(codigo_pais: str) -> dict:
    """
    Devuelve la tarifa referencial y moneda de un país. Estos valores NO están
    verificados en tiempo real: siempre se debe indicar al usuario que confirme
    el valor vigente en la fuente oficial o use el de su propia boleta.
    """
    pais = REFERENCIA["paises"].get(codigo_pais)
    if not pais:
        raise ValueError(f"País '{codigo_pais}' no está configurado.")
    return pais


def estimar_factura_total(items_kwh_mes: list) -> dict:
    """Suma el consumo estimado de varios ítems y lo compara con una boleta declarada."""
    total_kwh = round(sum(items_kwh_mes), 2)
    return {
        "kwh_mes_total_estimado": total_kwh,
        "clp_mes_total_estimado": kwh_a_clp(total_kwh),
    }

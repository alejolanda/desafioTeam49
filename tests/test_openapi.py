"""
Contrato de la API contra su especificación (tarea 7.3).

Una especificación escrita a mano se despega del código a la primera semana.
Estos tests la anclan: si se añade un endpoint sin documentarlo, o se documenta
uno que ya no existe, falla la CI en vez de descubrirse en producción.
"""
from pathlib import Path

import pytest

import app as aplicacion

yaml = pytest.importorskip("yaml", reason="pyyaml viene con requirements-dev")

RAIZ = Path(__file__).resolve().parent.parent
ESPECIFICACION = yaml.safe_load((RAIZ / "docs" / "openapi.yaml").read_text(encoding="utf-8"))

# Rutas que no forman parte de la API pública: la página del asistente, los
# archivos estáticos y la propia documentación.
NO_DOCUMENTADAS = {"/", "/static/<path:filename>", "/openapi.yaml", "/apidocs/", "/apispec.json"}


def rutas_de_la_aplicacion() -> set:
    return {
        regla.rule
        for regla in aplicacion.app.url_map.iter_rules()
        if regla.rule not in NO_DOCUMENTADAS and not regla.rule.startswith("/flasgger")
    }


def test_la_especificacion_es_valida():
    assert ESPECIFICACION["openapi"].startswith("3.")
    assert ESPECIFICACION["info"]["title"]
    assert ESPECIFICACION["paths"]


def test_todos_los_endpoints_estan_documentados():
    faltan = sorted(rutas_de_la_aplicacion() - set(ESPECIFICACION["paths"]))
    assert not faltan, f"endpoints sin documentar en docs/openapi.yaml: {faltan}"


def test_no_se_documentan_endpoints_inexistentes():
    sobran = sorted(set(ESPECIFICACION["paths"]) - rutas_de_la_aplicacion())
    assert not sobran, f"documentados pero ya no existen: {sobran}"


def test_los_metodos_coinciden_con_los_registrados():
    for regla in aplicacion.app.url_map.iter_rules():
        if regla.rule in NO_DOCUMENTADAS or regla.rule.startswith("/flasgger"):
            continue
        reales = {m.lower() for m in regla.methods} - {"head", "options"}
        documentados = set(ESPECIFICACION["paths"][regla.rule])
        assert reales == documentados, f"{regla.rule}: el código expone {reales}, la spec dice {documentados}"


def test_cada_operacion_declara_respuestas_y_resumen():
    for ruta, operaciones in ESPECIFICACION["paths"].items():
        for metodo, operacion in operaciones.items():
            assert operacion.get("summary"), f"{metodo.upper()} {ruta} no tiene resumen"
            assert operacion.get("responses"), f"{metodo.upper()} {ruta} no declara respuestas"
            assert "200" in operacion["responses"], f"{metodo.upper()} {ruta} no documenta el caso correcto"


def test_los_alias_de_compatibilidad_estan_marcados_como_deprecados():
    """
    Los cuatro alias duplican campos primarios. Si no se marcan y se les pone
    fecha de retiro, el contrato crece indefinidamente.
    """
    propiedades = ESPECIFICACION["components"]["schemas"]["RespuestaAnalisis"]["properties"]
    for alias in ("costo_estimado_mensual", "total_kwh_mes", "total_clp_mes", "ahorro_potencial_clp_mes"):
        assert propiedades[alias].get("deprecated") is True, f"{alias} debería estar marcado como deprecado"


def test_el_campo_probabilidad_no_reaparece():
    """Regresión de 2.5: eran 0.90/0.75/0.82 sin significado medible."""
    assert "probabilidad" not in ESPECIFICACION["components"]["schemas"]["RespuestaAnalisis"]["properties"]


def test_la_documentacion_esta_apagada_por_defecto():
    """
    Publicar el catálogo de endpoints que consumen servicios de pago facilita
    el abuso que mitiga el límite de tasa.
    """
    import os

    assert os.getenv("ENABLE_API_DOCS", "0") != "1" or aplicacion.DOCS_HABILITADAS
    if not aplicacion.DOCS_HABILITADAS:
        assert aplicacion.app.test_client().get("/openapi.yaml").status_code == 404


def test_el_catalogo_de_comparacion_se_declara_como_ejemplo():
    """El endpoint devuelve precios nulos: la spec debe advertirlo, no ocultarlo."""
    descripcion = ESPECIFICACION["paths"]["/api/comparar"]["post"]["description"]
    assert "ejemplo" in descripcion.lower()

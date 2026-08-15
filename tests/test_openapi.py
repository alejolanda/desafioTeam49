"""
Contrato de la API contra su especificación (tarea 7.3).

Una especificación escrita a mano se despega del código a la primera semana.
Estos tests la anclan: si se añade un endpoint sin documentarlo, o se documenta
uno que ya no existe, falla la CI en vez de descubrirse en producción.
"""
import re
from pathlib import Path

import pytest

import app as aplicacion

yaml = pytest.importorskip("yaml", reason="pyyaml viene con requirements-dev")

RAIZ = Path(__file__).resolve().parent.parent
ESPECIFICACION = yaml.safe_load((RAIZ / "docs" / "openapi.yaml").read_text(encoding="utf-8"))

# Rutas que no forman parte de la API pública: la página del asistente, los
# archivos estáticos y la propia especificación.
NO_DOCUMENTADAS = {"/", "/static/<path:filename>", "/openapi.yaml"}


def es_de_la_api(regla) -> bool:
    """
    Filtra por el ORIGEN del endpoint, no por la ruta.

    Flasgger registra `/apidocs/`, `/apispec.json` y `/oauth2-redirect.html`,
    ninguna de las cuales empieza por `/flasgger`: filtrar por prefijo de ruta
    dejaba pasar las suyas y hacía que estos tests fallaran solo cuando
    ENABLE_API_DOCS estaba activado. Todos sus endpoints sí cuelgan del
    blueprint `flasgger`, que es un criterio estable.
    """
    return regla.rule not in NO_DOCUMENTADAS and not regla.endpoint.startswith("flasgger")


def rutas_de_la_aplicacion() -> set:
    return {regla.rule for regla in aplicacion.app.url_map.iter_rules() if es_de_la_api(regla)}


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
        if not es_de_la_api(regla):
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


@pytest.mark.skipif(not aplicacion.DOCS_HABILITADAS, reason="requiere ENABLE_API_DOCS=1")
def test_la_interfaz_visual_no_pisa_los_archivos_estaticos_de_la_app():
    """
    Regresión: pasar un `config` propio a flasgger SUSTITUYE su configuración
    por defecto, no la completa. Al omitir `static_url_path`, su blueprint se
    registraba en `/static` y chocaba con el de Flask, que gana por estar
    registrado antes. La página de Swagger cargaba pero sus activos daban 404.
    """
    rutas_flasgger = {
        regla.rule
        for regla in aplicacion.app.url_map.iter_rules()
        if regla.endpoint.startswith("flasgger")
    }
    assert "/static/<path:filename>" not in rutas_flasgger, "flasgger volvió a pisar /static"


@pytest.mark.skipif(not aplicacion.DOCS_HABILITADAS, reason="requiere ENABLE_API_DOCS=1")
def test_todos_los_activos_de_la_interfaz_visual_se_sirven():
    """No basta con que /apidocs devuelva 200: sin sus activos, la página está en blanco."""
    cliente = aplicacion.app.test_client()
    pagina = cliente.get("/apidocs/")
    if pagina.status_code == 501:
        pytest.skip("flasgger no está instalado en este entorno")

    assert pagina.status_code == 200
    activos = re.findall(r'(?:src|href)="(/[^"]+\.(?:css|js))"', pagina.get_data(as_text=True))
    assert activos, "la página de Swagger no referencia ningún activo"

    for ruta in activos:
        assert cliente.get(ruta).status_code == 200, f"activo no servido: {ruta}"


@pytest.mark.skipif(not aplicacion.DOCS_HABILITADAS, reason="requiere ENABLE_API_DOCS=1")
def test_el_documento_servido_es_openapi3_intacto():
    """
    Regresión: flasgger trabaja en modo Swagger 2.0 por defecto y añadía
    `swagger: "2.0"` junto al `openapi` de la plantilla. Swagger UI rechazaba el
    documento entero —los dos campos no pueden coexistir— y la página mostraba
    "Unable to render this definition" en vez de la API.

    Se comprueba además que no recorte el contrato al procesarlo.
    """
    cliente = aplicacion.app.test_client()
    respuesta = cliente.get("/apispec.json")
    if respuesta.status_code == 404:
        pytest.skip("flasgger no está instalado en este entorno")

    servido = respuesta.get_json()

    assert "swagger" not in servido, "volvió a colarse el campo swagger 2.0"
    assert servido.get("openapi", "").startswith("3."), "el documento servido no se declara OpenAPI 3"
    assert "definitions" not in servido, "se coló el contenedor de esquemas de Swagger 2.0"

    assert set(servido["paths"]) == set(ESPECIFICACION["paths"]), "se perdieron rutas al servir"
    assert set(servido["components"]["schemas"]) == set(ESPECIFICACION["components"]["schemas"]), \
        "se perdieron esquemas al servir"


def test_el_catalogo_de_comparacion_se_declara_como_ejemplo():
    """El endpoint devuelve precios nulos: la spec debe advertirlo, no ocultarlo."""
    descripcion = ESPECIFICACION["paths"]["/api/comparar"]["post"]["description"]
    assert "ejemplo" in descripcion.lower()

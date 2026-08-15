"""
Contrato entre el HTML y el JavaScript.

`denji.js` navega la interfaz de otra persona por los IDs de sus campos, y
`app.js` lee y escribe esos mismos elementos. Nada de eso está tipado: si
alguien renombra un ID en la plantilla, el asistente deja de encontrar el campo
y se pone a deambular, o el formulario envía ceros, y en ninguno de los dos
casos falla nada de forma visible.

Estos tests convierten ese acuerdo implícito en algo que se rompe en CI.
"""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
HTML = (RAIZ / "templates" / "index.html").read_text(encoding="utf-8")
APP_JS = (RAIZ / "static" / "js" / "app.js").read_text(encoding="utf-8")
DENJI_JS = (RAIZ / "static" / "js" / "denji.js").read_text(encoding="utf-8")

IDS_HTML = set(re.findall(r'id="([^"]+)"', HTML))

# Se crean en tiempo de ejecución desde JavaScript, no viven en la plantilla.
IDS_DINAMICOS = {"avisoGlobal"}
# Nombre alternativo heredado: el código lo consulta como respaldo del actual.
IDS_HEREDADOS = {"selectPais"}


def test_los_ids_que_usa_denji_existen_en_la_plantilla():
    """
    denji.js resuelve cada campo en tres niveles: ID real, `data-denji-target`
    y, como último recurso, buscar por el texto de la etiqueta. Hoy el primer
    nivel cubre el 100%, así que la búsqueda por texto nunca se ejecuta. Este
    test protege esa situación: si un ID desaparece, el asistente pasaría en
    silencio al frágil emparejamiento por texto.
    """
    bloque = re.search(r"const MAPEO_CAMPOS = \{(.*?)\n  \};", DENJI_JS, re.S)
    assert bloque, "no se encontró MAPEO_CAMPOS en denji.js"

    referenciados = set(re.findall(r"id:\s*'([^']+)'", bloque.group(1)))
    referenciados |= set(re.findall(r"contenedor:\s*'([^']+)'", bloque.group(1)))
    assert referenciados, "MAPEO_CAMPOS no declaró ningún id"

    faltan = sorted(referenciados - IDS_HTML)
    assert not faltan, f"denji.js apunta a IDs que ya no existen en la plantilla: {faltan}"


def test_los_ids_que_usa_app_js_existen_en_la_plantilla():
    referenciados = set(re.findall(r"getElementById\('([^']+)'\)", APP_JS))
    faltan = sorted(referenciados - IDS_HTML - IDS_DINAMICOS - IDS_HEREDADOS)
    assert not faltan, f"app.js apunta a IDs que ya no existen en la plantilla: {faltan}"


def test_la_pagina_no_depende_de_ningun_servidor_externo():
    """
    Regresión de 5.5: la plantilla cargaba Lucide desde unpkg con la etiqueta
    `@latest` y sin `integrity`, y la tipografía desde Google Fonts. Sin red la
    interfaz se quedaba sin iconos y sin la fuente pensada para lectura
    accesible, y `@latest` es una dependencia de terceros sin fijar.
    """
    externas = re.findall(r'(?:src|href)="(https?://[^"]+)"', HTML)
    assert not externas, f"la plantilla volvió a depender de recursos externos: {externas}"


def test_los_recursos_vendorizados_estan_presentes():
    for recurso in (
        "static/vendor/lucide.min.js",
        "static/vendor/atkinson-hyperlegible.css",
    ):
        assert (RAIZ / recurso).is_file(), f"falta el recurso vendorizado {recurso}"

    css = (RAIZ / "static" / "vendor" / "atkinson-hyperlegible.css").read_text(encoding="utf-8")
    assert "https://" not in css, "el CSS de la fuente sigue apuntando a fonts.gstatic.com"

    fuentes = list((RAIZ / "static" / "vendor" / "fonts").glob("*.woff2"))
    assert fuentes, "no se vendorizó ningún archivo de fuente"


def test_no_quedan_llamadas_a_endpoints_inexistentes():
    """Regresión de 4.4: se reintentaba contra /calcular, que no existe."""
    llamadas = re.findall(r"fetch(?:ConTimeout)?\(\s*'(/[^']*)'", APP_JS)
    assert "/calcular" not in llamadas
    assert "/api/calcular" not in llamadas, "el frontend volvió a usar el endpoint con otro contrato"


@pytest.mark.parametrize(
    "control",
    ["inputBoleta", "boletaEstado", "grupoInmuebleOtro", "inputInmuebleOtro", "fptNarrativa"],
)
def test_los_controles_cableados_en_la_fase_4_siguen_en_la_plantilla(control):
    assert control in IDS_HTML


def test_el_periodo_de_consumo_por_defecto_es_mensual():
    """
    Regresión de 4.7: el campo pide el consumo MENSUAL pero el interruptor
    "El consumo es anual" venía marcado, así que quien escribía 250 pensando en
    su mes terminaba con 20,8 kWh.
    """
    etiqueta = re.search(r'<input type="checkbox" id="flagAnual"([^>]*)>', HTML)
    assert etiqueta, "no se encontró el interruptor flagAnual"
    assert "checked" not in etiqueta.group(1)

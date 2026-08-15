"""
Geocodificación inversa (coordenadas → ciudad, región, país).

Antes esto lo hacía el navegador llamando directamente a
`nominatim.openstreetmap.org`. Se trae al backend por cuatro razones:

1. **Política de uso.** Nominatim exige un `User-Agent` que identifique la
   aplicación y permita contactar al responsable. Un navegador no puede fijar
   esa cabecera; un servidor sí. Si no hay contacto configurado, este módulo se
   niega a llamar en vez de hacer peticiones anónimas.
2. **Código de país en vez de nombre.** Nominatim devuelve el nombre del país
   en el idioma del lugar ("United States"), y el frontend lo comparaba contra
   la lista en español ("Estados Unidos"): para varios países no encontraba
   nada y el selector se quedaba vacío sin avisar. `country_code` es un ISO
   3166-1 alpha-2 que mapea directo a las claves de `calculos.PAISES`.
3. **Caché.** Es un servicio comunitario gratuito. A nivel de ciudad, muchas
   consultas distintas caen en la misma coordenada redondeada.
4. **Privacidad.** El usuario acepta compartir su ubicación con esta
   aplicación, no con un tercero.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
import urllib.request
from functools import lru_cache

from src import calculos

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

# Identificación exigida por la política de uso. Sin esto no se llama.
CONTACTO = os.getenv("NOMINATIM_CONTACTO", "").strip()
NOMBRE_APP = os.getenv("NOMINATIM_APP", "VolticvS/1.0")

TIMEOUT_S = float(os.getenv("NOMINATIM_TIMEOUT_S", "8"))

# La política pide como máximo una petición por segundo para toda la aplicación.
INTERVALO_MINIMO_S = float(os.getenv("NOMINATIM_INTERVALO_S", "1"))

# ~1 km. La consulta se hace con zoom=10, que resuelve a nivel de ciudad, así
# que más precisión no mejora el resultado y sí expone al usuario.
DECIMALES = 2

_candado = threading.Lock()
_ultima_llamada = 0.0


class GeocodificacionNoDisponible(RuntimeError):
    """No hay contacto configurado, o el servicio no respondió."""


def disponible() -> bool:
    return bool(CONTACTO)


def _user_agent() -> str:
    return f"{NOMBRE_APP} ({CONTACTO})"


def _esperar_turno() -> None:
    """Serializa las llamadas salientes para respetar el límite de 1 por segundo."""
    global _ultima_llamada
    with _candado:
        espera = INTERVALO_MINIMO_S - (time.monotonic() - _ultima_llamada)
        if espera > 0:
            time.sleep(min(espera, INTERVALO_MINIMO_S))
        _ultima_llamada = time.monotonic()


@lru_cache(maxsize=512)
def _consultar(lat: float, lon: float) -> dict:
    """Consulta cacheada por coordenada ya redondeada."""
    if not disponible():
        raise GeocodificacionNoDisponible(
            "NOMINATIM_CONTACTO no está configurado: no se hacen peticiones sin identificar."
        )

    parametros = urllib.parse.urlencode({
        "format": "json",
        "lat": lat,
        "lon": lon,
        "zoom": 10,
        "addressdetails": 1,
        # Fuerza los nombres en español para que coincidan con la lista propia
        # cuando haya que mostrarlos.
        "accept-language": "es",
    })

    peticion = urllib.request.Request(
        f"{NOMINATIM_URL}?{parametros}",
        headers={"User-Agent": _user_agent()},
    )

    _esperar_turno()
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_S) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except Exception as error:
        raise GeocodificacionNoDisponible(str(error)) from error


def ubicacion_desde_coordenadas(lat: float, lon: float) -> dict:
    """
    Devuelve {pais_codigo, pais_nombre, region, comuna, soportado}.

    `pais_codigo` es la clave de `calculos.PAISES` o None si el país no está
    entre los soportados; en ese caso `soportado` es False y el frontend deja
    que el usuario elija a mano en vez de dejar el selector vacío en silencio.
    """
    datos = _consultar(round(float(lat), DECIMALES), round(float(lon), DECIMALES))
    direccion = datos.get("address") or {}

    codigo = (direccion.get("country_code") or "").upper() or None
    ficha = calculos.PAISES.get(codigo) if codigo else None

    return {
        "pais_codigo": codigo if ficha else None,
        # Se prefiere el nombre propio: es el que aparece en el <select>.
        "pais_nombre": ficha["nombre"] if ficha else direccion.get("country", ""),
        "region": direccion.get("state") or direccion.get("region") or "",
        "comuna": (
            direccion.get("city")
            or direccion.get("town")
            or direccion.get("village")
            or direccion.get("municipality")
            or direccion.get("county")
            or ""
        ),
        "soportado": bool(ficha),
    }

"""
Capa de acceso a Groq.

Concentra en un solo sitio lo que antes estaba repartido en cuatro
instanciaciones de `ChatGroq` dentro de `app.py`, cada una con sus propios
parámetros y ninguna con timeout.

Tres decisiones deliberadas:

1. **Timeout explícito.** `langchain-groq` deja `request_timeout=None` por
   defecto, así que una petición colgada bloquea el worker de Flask
   indefinidamente. Aquí siempre hay tope.
2. **Un reintento, no dos.** El default de la librería son 2 reintentos: con
   una clave inválida son 3 llamadas fallidas por request antes de rendirse.
3. **Los fallos se ven.** Este módulo no captura excepciones: las deja subir
   para que quien llama decida si degrada y lo registre. El silencio era el
   problema original.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache

from langchain_groq import ChatGroq

MODELO_TEXTO = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MODELO_VISION = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

TIMEOUT_S = float(os.getenv("GROQ_TIMEOUT_S", "10"))
MAX_REINTENTOS = int(os.getenv("GROQ_MAX_RETRIES", "1"))
MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "300"))

# Límite de tamaño para imágenes enviadas en base64. El transporte en base64
# infla el archivo ~33%, y la API rechaza las que superan su propio tope, así
# que conviene cortar antes de gastar la llamada.
MAX_IMAGEN_MB = float(os.getenv("GROQ_MAX_IMAGEN_MB", "4"))


class GroqNoConfigurado(RuntimeError):
    """No hay GROQ_API_KEY en el entorno."""


def disponible() -> bool:
    """True si hay clave configurada. Permite degradar antes de intentar la llamada."""
    return bool(os.getenv("GROQ_API_KEY"))


@lru_cache(maxsize=8)
def _cliente(modelo: str, temperatura: float, max_tokens: int, json_mode: bool, api_key: str) -> ChatGroq:
    """
    Clientes cacheados por configuración. Antes se construía uno nuevo en cada
    request, descartando el pool de conexiones subyacente.

    La api_key entra en la clave de caché a propósito: si se rota la clave en
    caliente, se obtiene un cliente nuevo en vez de seguir usando el viejo.
    """
    return ChatGroq(
        model=modelo,
        temperature=temperatura,
        api_key=api_key,
        max_tokens=max_tokens,
        timeout=TIMEOUT_S,
        max_retries=MAX_REINTENTOS,
        model_kwargs={"response_format": {"type": "json_object"}} if json_mode else {},
    )


def obtener_llm(
    modelo: str | None = None,
    temperatura: float = 0.0,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> ChatGroq:
    """
    Devuelve un cliente listo para usar.

    json_mode fuerza a la API a responder un objeto JSON válido. Groq exige que
    el prompt mencione la palabra "JSON" cuando se activa.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise GroqNoConfigurado("GROQ_API_KEY no está configurada.")

    return _cliente(
        modelo or MODELO_TEXTO,
        temperatura,
        max_tokens or MAX_TOKENS,
        json_mode,
        api_key,
    )


def es_error_de_credenciales(error: Exception) -> bool:
    """
    Distingue "la clave no sirve" de "la llamada falló".

    Son problemas de naturaleza distinta y merecen tratamiento distinto en el
    log: un 401 es de configuración, se repite en cada petición y se arregla
    editando el `.env`. Volcar la traza completa cada vez solo entierra el
    mensaje accionable bajo treinta líneas de pila que siempre son iguales.

    Se detecta por el código de estado y el texto en vez de importar la
    excepción del SDK de Groq, que es una dependencia transitiva.
    """
    if getattr(error, "status_code", None) == 401:
        return True
    texto = str(error).lower()
    return "invalid_api_key" in texto or "invalid api key" in texto


def extraer_json(texto: str) -> dict | None:
    """
    Extrae el primer objeto JSON de una respuesta del modelo.

    Sustituye a `re.search(r'\\{[^{}]+\\}')`, que por construcción no puede
    encontrar un objeto con otro objeto dentro: la clase de caracteres excluye
    las llaves. Aquí se hace balanceo real de llaves, respetando las que
    aparecen dentro de cadenas, y se toleran los bloques ```json``` con los que
    algunos modelos envuelven la respuesta.

    Devuelve None si no hay ningún objeto JSON válido; nunca lanza.
    """
    if not texto:
        return None

    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = re.sub(r"^```[a-zA-Z]*\s*", "", limpio)
        limpio = re.sub(r"\s*```$", "", limpio).strip()

    try:
        directo = json.loads(limpio)
        if isinstance(directo, dict):
            return directo
    except json.JSONDecodeError:
        pass

    inicio = limpio.find("{")
    while inicio != -1:
        profundidad = 0
        en_cadena = False
        escapado = False

        for i in range(inicio, len(limpio)):
            caracter = limpio[i]

            if en_cadena:
                if escapado:
                    escapado = False
                elif caracter == "\\":
                    escapado = True
                elif caracter == '"':
                    en_cadena = False
                continue

            if caracter == '"':
                en_cadena = True
            elif caracter == "{":
                profundidad += 1
            elif caracter == "}":
                profundidad -= 1
                if profundidad == 0:
                    try:
                        candidato = json.loads(limpio[inicio:i + 1])
                        if isinstance(candidato, dict):
                            return candidato
                    except json.JSONDecodeError:
                        pass
                    break

        inicio = limpio.find("{", inicio + 1)

    return None


def numero_valido(valor, minimo: float = 0.0, maximo: float = float("inf")) -> float | None:
    """
    Valida un número que viene del modelo antes de dejarlo entrar al sistema.

    Un LLM puede devolver una cadena, un booleano, un negativo o una cifra
    absurda. Sin este filtro esos valores llegaban tal cual al cliente y de ahí
    al cálculo. Devuelve None cuando el valor no sirve, para que quien llama
    decida (pedir el dato al usuario, marcar confianza baja, etc.).
    """
    if valor is None or isinstance(valor, bool):
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None

    # NaN e infinitos sobreviven a float() y envenenan cualquier cálculo posterior.
    if numero != numero or numero in (float("inf"), float("-inf")):
        return None

    if not (minimo <= numero <= maximo):
        return None

    return numero

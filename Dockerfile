# syntax=docker/dockerfile:1

# ══════════════════════════════════════════════════════════════════════════════
#  Etapa 1 — Construccion de dependencias
#  Se compila aparte para que los compiladores no lleguen a la imagen final.
# ══════════════════════════════════════════════════════════════════════════════
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# pdfplumber arrastra pillow y cryptography. Normalmente hay rueda precompilada,
# pero si falta para alguna plataforma el build fallaria sin compilador.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Se instala desde el lock, no desde requirements.txt: este ultimo usa
# restricciones >=, asi que dos builds del mismo commit podian instalar
# versiones distintas de LangChain y romperse entre si.
COPY requirements.lock ./
RUN pip install --require-virtualenv -r requirements.lock

# Interfaz visual de la API (Swagger UI), opcional. Son ~9 MB de activos que no
# tienen nada que hacer en produccion, donde ademas la documentacion va apagada.
# Para levantarla en desarrollo:
#     docker compose build --build-arg INSTALAR_DOCS=1
ARG INSTALAR_DOCS=0
RUN if [ "$INSTALAR_DOCS" = "1" ]; then pip install flasgger pyyaml; fi


# ══════════════════════════════════════════════════════════════════════════════
#  Etapa 2 — Imagen de ejecucion
# ══════════════════════════════════════════════════════════════════════════════
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=5000

COPY --from=builder /opt/venv /opt/venv

# Usuario sin privilegios: si alguien escapa del proceso, no es root.
RUN useradd --create-home --shell /usr/sbin/nologin volticvs
WORKDIR /app

# El codigo va despues de las dependencias para que un cambio de fuente no
# invalide la capa de instalacion, que es la cara.
COPY --chown=volticvs:volticvs app.py ./
COPY --chown=volticvs:volticvs src/ ./src/
COPY --chown=volticvs:volticvs data/ ./data/
COPY --chown=volticvs:volticvs static/ ./static/
COPY --chown=volticvs:volticvs templates/ ./templates/

# El contrato de la API: la aplicacion lo sirve en /openapi.yaml cuando
# ENABLE_API_DOCS esta activo. La interfaz visual de Swagger NO viaja en la
# imagen (flasgger son ~9 MB y es dependencia de desarrollo), pero el contrato
# no necesita nada para servirse.
COPY --chown=volticvs:volticvs docs/openapi.yaml ./docs/openapi.yaml

# Las boletas son efimeras (el codigo las borra en el bloque finally). En
# docker-compose este directorio se monta como tmpfs para que no toquen disco.
RUN mkdir -p /app/uploads && chown volticvs:volticvs /app/uploads

USER volticvs
EXPOSE 5000

# Sin curl en la imagen slim; la sonda usa el propio interprete. Consulta
# /health, que no llama a Groq ni a Nominatim: una sonda cada 30 s no puede
# gastar cuota de un servicio de pago.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','5000')+'/health', timeout=4).status==200 else 1)"

# El servidor de desarrollo de Werkzeug no atiende trafico real.
#
# --timeout 60: tiene que ser MAYOR que el tiempo maximo que puede tardar una
#   peticion contra Groq (GROQ_TIMEOUT_S x reintentos, mas la subida de una
#   imagen de boleta). Con el default de 30 s, gunicorn mataria al worker antes
#   de que el modelo alcanzara a responder.
#
# 1 worker con hilos, no varios procesos: el limite de tasa y las caches de
#   geocodificacion viven en la memoria del proceso. Con varios workers cada uno
#   tendria las suyas y en conjunto superarian el limite de 1 peticion/segundo
#   que exige Nominatim. Para escalar a mas workers hay que apuntar antes
#   RATELIMIT_STORAGE_URI a Redis (ver docs/PLAN.md, 6.4).
CMD ["sh", "-c", "exec gunicorn app:app \
  --bind 0.0.0.0:${PORT:-5000} \
  --workers ${GUNICORN_WORKERS:-1} \
  --threads ${GUNICORN_THREADS:-8} \
  --worker-class gthread \
  --timeout ${GUNICORN_TIMEOUT:-60} \
  --graceful-timeout 30 \
  --access-logfile - \
  --error-logfile -"]

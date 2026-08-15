# ⚡ VólticvS — Asesor Energético Inteligente

Plataforma web para diagnosticar el consumo eléctrico de un hogar, estimar su ahorro potencial y dar
recomendaciones concretas. Soporta **24 países** de América y España, cada uno con su moneda y tarifa.

> **Los números son deterministas.** El cálculo lo hace [`src/calculos.py`](src/calculos.py) con
> física básica —potencia × tiempo, calor específico del agua— y el modelo de lenguaje **solo redacta
> la narrativa y lee las boletas**. Ningún importe sale de un LLM. Esta separación es deliberada:
> evita que el sistema alucine cifras de ahorro.

---

## Arranque rápido

### Con Docker (recomendado)

```bash
git clone https://github.com/alejolanda/desafioTeam49.git
cd desafioTeam49
cp .env.example .env      # y edita las claves, ver más abajo
docker compose up --build
```

La app queda en **http://localhost:5000**.

> **En macOS el puerto 5000 lo ocupa el receptor de AirPlay.** Usa otro puerto para el host sin tocar
> el interno: `HOST_PORT=5001 docker compose up`, o desactiva *Ajustes → General → AirDrop y Handoff →
> Receptor AirPlay*.

Comandos habituales:

```bash
docker compose logs -f              # ver los logs
docker compose down                 # detener
docker compose up -d --force-recreate   # recargar tras cambiar el .env
```

El código va montado en solo lectura con recarga automática: al editar `app.py` o `src/`, gunicorn se
reinicia solo. Ahora bien:

- **Cambiaste el `.env`** → `docker compose up -d --force-recreate`. El entorno se lee al crear el
  contenedor, no en cada petición, y la recarga automática solo vigila el código.
- **Cambiaste `requirements.lock` o el `Dockerfile`** → hace falta `--build`.

### Sin Docker

Requiere **Python 3.12+**.

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

---

## Configuración

Todas las variables viven en `.env`, que **nunca** se versiona ni entra en la imagen de Docker.
[`.env.example`](.env.example) las documenta una a una; estas son las que importan:

| Variable | Qué hace | ¿Obligatoria? |
|---|---|---|
| `GROQ_API_KEY` | Narrativa y lectura de boletas | No, pero sin ella se degrada |
| `NOMINATIM_CONTACTO` | Correo de contacto del equipo | Para detectar la ubicación |
| `GROQ_TIMEOUT_S` | Segundos antes de abandonar una llamada al modelo | No (10) |
| `RATELIMIT_STORAGE_URI` | Redis, si se usa más de un worker | No (memoria) |
| `ENABLE_API_DOCS` | Sirve el contrato en `/openapi.yaml` | No (apagado) |
| `HOST_PORT` | Puerto del host, separado del interno | No (5000) |
| `INSTALAR_DOCS` | Mete Swagger UI en la imagen al construirla | No (0) |
| `FLASK_DEBUG` | **Dejar en 0.** El depurador de Werkzeug permite ejecución remota de código | No (0) |

**La aplicación funciona sin ninguna clave.** Sin `GROQ_API_KEY` el diagnóstico se calcula igual —es
determinista— y la narrativa cae a un texto de respaldo, marcado como tal en el campo
`narrativa_fuente`. Sin `NOMINATIM_CONTACTO` no se detecta la ubicación y se pide a mano; es
deliberado: su política de uso exige identificar la aplicación, y es preferible perder la función
antes que hacer peticiones sin identificar contra un servicio comunitario gratuito.

---

## Cómo funciona

```
┌─ Navegador ────────────────────────────────────────────────┐
│  index.html + app.js         asistente Denji (denji.js)    │
│  Asistente de 4 pasos        guía y rellena el formulario  │
└───────────────────────────┬────────────────────────────────┘
                            │  JSON
┌───────────────────────────▼────────────────────────────────┐
│  Flask (app.py)                                            │
│                                                            │
│   src/calculos.py    Motor determinista. Toda cifra sale   │
│                      de aquí. Tarifa por país obligatoria. │
│   src/llm.py         Acceso a Groq: timeout, validación    │
│                      de la salida, degradación explícita.  │
│   src/geo.py         Intermediario ante OpenStreetMap.     │
│                                                            │
│   data/consumo_referencia.json                             │
│      Fuente única: potencias, tarifas y suposiciones       │
│      de uso, cada una con su procedencia anotada.          │
└────────────────────────────────────────────────────────────┘
```

### Dos formas de estimar el consumo

1. **Declarado.** Escribes los kWh de tu boleta, o la subes y se extraen solos.
2. **Estimado.** Declaras tu equipamiento y se calcula artefacto por artefacto.

Si no das ninguno de los dos, el resultado es 0 con `fuente_consumo: "sin_datos"`. No se inventa una
cifra de relleno.

### De dónde sale el ahorro

De la suma real del consumo evitable de cada artefacto: lo que gasta un equipo en modo de espera
frente a lo que gastaría desconectado. Se calcula siempre, incluso cuando declaras el consumo de tu
boleta, porque sin desglose no hay forma de saber dónde está el ahorro.

> **Limitación conocida.** Hoy solo se monetiza el consumo fantasma. Las recomendaciones textuales
> sugieren ahorros mayores —bajar el aire acondicionado a 24 °C, lavar en frío, cambiar a LED— y
> ninguno de ellos entra todavía en la cifra. El `ahorro_estimado` es, por tanto, conservador.

---

## API

El contrato completo está en [`docs/openapi.yaml`](docs/openapi.yaml). Con `ENABLE_API_DOCS=1` se
sirve además en `/openapi.yaml`.

La interfaz visual de Swagger en `/apidocs` no viaja en la imagen por defecto —son ~9 MB de activos
que no pintan nada en producción, donde además la documentación va apagada. Para levantarla:

```bash
INSTALAR_DOCS=1 docker compose build && docker compose up -d   # con Docker
pip install -r requirements-dev.txt                            # sin Docker
```

y `ENABLE_API_DOCS=1` en el `.env`.

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/health` | Sonda de vida. No llama a servicios externos |
| `GET` | `/api/paises` | Países soportados con su moneda y tarifa |
| `GET` | `/api/ubicacion` | Coordenadas → ciudad y código de país |
| `POST` | `/api/analisis-energetico` | Análisis del hogar. **El endpoint principal** |
| `POST` | `/api/calcular` | Cálculo por artefacto. Payload **distinto** al anterior |
| `POST` | `/api/subir-boleta` | Extrae consumo y tarifa de una boleta |
| `POST` | `/api/interpretar-campo` | Mapea texto libre a un tipo de vivienda |
| `POST` | `/api/comparar` | Compara artefactos. Catálogo de ejemplo |

Los endpoints que consumen servicios de pago tienen límite de tasa por IP y no piden credenciales;
sin tope, cualquiera podría agotar la cuota.

---

## Desarrollo

```bash
pip install -r requirements-dev.txt
ruff check .          # linter
pytest                # toda la batería
pytest --cov=src --cov=app --cov-report=term
```

La CI ejecuta linter y tests en cada PR, construye la imagen de Docker, la arranca y sondea
`/health`, y falla si alguien versiona un `.env` o un `.zip`.

### Datos de referencia

[`data/consumo_referencia.json`](data/consumo_referencia.json) es la fuente única de potencias,
tarifas y suposiciones de uso. Cada valor lleva anotada su procedencia, y los que no están
verificados lo dicen explícitamente:

- **Tarifas por país:** referenciales, con el regulador de origen anotado. No están verificadas en
  tiempo real — envía `tarifa_kwh` con el valor de tu propia boleta para obtener importes exactos.
- **`perfil_hogar`:** las horas de uso al día y las veces por semana de cada equipo. Antes eran
  constantes escondidas en el código; ahora se pueden auditar y corregir aquí.
- **Marcados `SIN VERIFICAR`:** la potencia media de la lavadora y las tarifas de siete países.
  Sustituirlos por datos reales antes de presentar esto como asesoría.
- **`categorias_comparables`:** catálogo **de ejemplo**, con todos los precios en `null`.

---

## Estructura

```
desafioTeam49/
├── app.py                      Servidor Flask y endpoints
├── src/
│   ├── calculos.py             Motor determinista
│   ├── llm.py                  Acceso a Groq
│   └── geo.py                  Geocodificación inversa
├── data/consumo_referencia.json
├── templates/index.html
├── static/
│   ├── css/style.css
│   ├── js/app.js               Lógica del asistente
│   ├── js/denji.js             Asistente guiado
│   ├── img/
│   └── vendor/                 Lucide y la tipografía, servidos localmente
├── tests/                      Batería de pruebas
├── docs/
│   ├── openapi.yaml            Contrato de la API
│   ├── PLAN.md                 Plan de la auditoría de código
│   └── DECISIONES.md           Decisiones técnicas y su porqué
├── Dockerfile                  Multi-stage, sin privilegios
├── docker-compose.yml
├── requirements.txt            Dependencias directas
├── requirements.lock           Árbol completo fijado (build reproducible)
└── requirements-dev.txt
```

---

## Tecnologías

| Capa | Stack |
|---|---|
| **Backend** | Python 3.12, Flask 3, gunicorn, flask-limiter |
| **Modelo** | LangChain + Groq (Llama 3.3 70B; visión con Llama 4 Scout) |
| **Frontend** | HTML5, CSS3, JavaScript ES6+ — sin framework ni CDN |
| **Datos** | JSON de referencia, cálculo determinista |
| **Infra** | Docker multi-stage, GitHub Actions |

La interfaz **no hace ninguna petición a servidores externos**: los iconos y la tipografía se sirven
desde el propio proyecto. Funciona sin conexión a internet salvo por las funciones que requieren
modelo.

---

VólticvS © 2026 — Equipo Volti

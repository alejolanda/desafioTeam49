# Plan de acción — VólticvS

Consolida los hallazgos de la auditoría de código en 7 fases ordenadas por dependencia:
cada fase deja el terreno listo para la siguiente. Las estimaciones son gruesas y asumen
una persona trabajando.

- **Fecha de auditoría:** 2026-08-14
- **Commit auditado:** `e4cf47e` (`origin/main`)
- **Alcance:** `app.py`, `src/`, `static/`, `templates/`, `data/`, configuración y repositorio

---

## Decisiones — resueltas 2026-08-14

Las seis se resolvieron por la opción recomendada.

| # | Decisión | Resolución |
|---|---|---|
| D-1 | ¿Reescribir el historial o solo rotar la clave? | **Ambas.** Rotar (0.1) y reescribir con `git filter-repo` (1.2) avisando al equipo — el zip son 44 MB muertos |
| D-2 | La narrativa del LLM: ¿se muestra o se elimina? | **Se muestra en la factura impresa**, no en pantalla |
| D-3 | Motor de cálculo único | **`calculos.py`.** Los helpers de `app.py` pasan a ser un adaptador del payload del wizard |
| D-4 | Reemplazo del ahorro fijo del 20% | **Suma real de `ahorro_clp_mes`** del desglose |
| D-5 | El agente conversacional (`agente.py` + `tools.py`) | **Fuera del scope actual**, se conserva en una rama |
| D-6 | Versión de Python objetivo | **3.12**, unificada en devcontainer, imagen Docker, CI y README |

---

## Estado de ejecución

| Tarea | Estado |
|---|---|
| 0.1 Rotar la clave de Groq | ⛔ **Bloqueada** — sin acceso a la consola de Groq. **Es la única mitigación real del incidente** |
| 0.2 Default de debug a `0` | ✅ Hecha |
| 0.3 Comunicar al equipo | ⬜ Pendiente |
| 1.1 Versionar el código | ✅ Hecha — rama `vllanten`, commit `b20282c` |
| 1.2 Purgar los zips del historial | ⚠️ **Reabierta** — ver nota |
| 1.3 Blindar el `.gitignore` | ✅ Hecha |
| 1.4 Piso de calidad (ruff + pytest + CI) | ✅ Hecha — `ruff check` limpio |
| 2.1 Tarifa del país en los ahorros | ✅ Hecha |
| 2.2 Fuente única de tarifas | ✅ Hecha — 24 países en el JSON, `_TARIFAS` eliminado |
| 2.3 Motor único | ✅ Hecha — `_estimar_consumo` sustituido por `calculos.estimar_desde_perfil` |
| 2.4 Ahorro real en vez del 20% fijo | ✅ Hecha |
| 2.5 Eliminar `probabilidad` | ✅ Hecha |
| 2.6 Tests de `calculos.py` | ✅ Hecha — 51 tests, 99% de cobertura (objetivo era 80%) |
| 3.1 Un cliente con timeout | ✅ Hecha — nuevo módulo `src/llm.py` |
| 3.2 Los fallos de Groq se registran | ✅ Hecha — campo `narrativa_fuente` en la respuesta |
| 3.3 JSON mode y parser con balanceo de llaves | ✅ Hecha |
| 3.4 Validar la salida del modelo | ✅ Hecha — `llm.numero_valido` |
| 3.5 El `or` que descartaba el 0 | ✅ Hecha |
| 3.6 Modelo de visión configurable | ✅ Hecha — `GROQ_VISION_MODEL` |
| 3.7 Tope de tamaño de imagen | ✅ Hecha — 413 antes de gastar la llamada |
| 3.8 Rate-limit y sin fugas de error | ✅ Hecha — `flask-limiter` |
| 4.1 Narrativa a la factura impresa | ✅ Hecha |
| 4.2 Cablear la subida de boleta | ✅ Hecha — uploader en el Paso 1 |
| 4.3 Cablear `interpretar-campo` | ✅ Hecha — campo libre al elegir "Otro" |
| 4.4 Eliminar la cadena de fallback | ✅ Hecha |
| 4.5 Timeout y estado de carga en el cliente | ✅ Hecha |
| 4.6 Retirar el agente CLI (D-5) | ✅ Hecha — `agente.py` y `tools.py` usaban las firmas viejas |
| 4.6b `/api/comparar` | ⏸️ En espera deliberada — ver nota |
| 5.1 Parseo de números latinoamericanos | ✅ Adelantada — el bug estaba en la ruta que tocaba 3.x |
| 5.2 Colisión de archivos subidos | ✅ Hecha — `tempfile.NamedTemporaryFile` |
| 5.3 Handler de 413 | ✅ Hecha |
| 5.4 `/api/comparar` con payload incompleto | ✅ Adelantada |
| 5.5 Fijar el CDN | ✅ Hecha — **vendorizado**: la página ya no hace ninguna petición externa |
| 5.6 Desacoplar `denji.js` | ✅ Resuelta de otra forma — ver nota |
| 5.8 Geolocalización a un tercero | ✅ Hecha — proxy en el backend; falta poner `NOMINATIM_CONTACTO` |
| 5.7 Sincronizar el README | → movida a la Fase 7 |
| 6.1 Lockfile y versión de Python única | ✅ Hecha — 53 paquetes fijados, build reproducible |
| 6.2 Dockerfile multi-stage | ✅ Hecha — 288 MB, sin compiladores, usuario sin privilegios |
| 6.3 `.dockerignore` | ✅ Hecha |
| 6.4 gunicorn como entrypoint | ✅ Hecha |
| 6.5 Configuración por entorno | ✅ Hecha — verificado que la imagen no contiene secretos |
| 6.6 `/health` y `HEALTHCHECK` | ✅ Hecha — Docker reporta `healthy` |
| 6.7 `uploads/` como tmpfs | ✅ Hecha |
| 6.8 `docker-compose.yml` | ✅ Hecha |
| 6.9 Build de la imagen en CI | ✅ Hecha — construye, arranca y sondea |
| 6.10 Devcontainer alineado a 3.12 | ✅ Hecha |
| 7.1 README — corregir lo falso | ✅ Hecha |
| 7.2 README — añadir lo que falta | ✅ Hecha |
| 7.3 Swagger / OpenAPI | ✅ Hecha — `docs/openapi.yaml` + test de deriva |
| 7.4 `.env.example` | ✅ Hecha — 19 variables documentadas |
| 7.5 `UI_DESIGN.md` | ✅ Hecha |
| 7.6 Registrar las decisiones | ✅ Hecha — `docs/DECISIONES.md` |

> **Sobre 0.1 y 1.2.** El trabajo se aisló en la rama `vllanten` para no forzar un re-clone al equipo.
> Eso resuelve la 1.1 pero **no** la 1.2: los zips viven en `e4cf47e`, ancestro de `main` y de
> `vllanten`, así que el blob con el `.env` sigue en la historia. La rama solo los saca del árbol de
> aquí en adelante. Purgarlos de verdad exige reescribir `main`, con el re-clone que se quería evitar
> — decisión a tomar al mergear.
>
> En cualquier caso, purgar el historial **no** protege la clave: lleva pública desde `e4cf47e` y hay
> que darla por comprometida. GitHub además conserva los objetos huérfanos accesibles por SHA tras un
> force-push, salvo purga explícita del soporte. La única mitigación es la **0.1**.

---

## Fase 0 — Contención (~1 h) 🔴

Nada de esto espera a una decisión.

### 0.1 Rotar la clave de Groq
La clave `gsk_GWqr…` viaja dentro de `Team45-G9.zip`, commit `e4cf47e`, ya publicado en
`origin/main` de un repositorio de GitHub. El `.gitignore` protege el `.env` suelto, pero no
sirve cuando el archivo va dentro de un zip. Es la misma clave que sigue activa en el `.env` local.

- Revocar en console.groq.com, emitir una nueva, actualizar el `.env` local.
- **Aceptación:** la clave anterior devuelve 401.

### 0.2 Invertir el default de debug
[`app.py:665`](../app.py#L665) usa `os.getenv("FLASK_DEBUG", "1")` — el default es *activado*, al
revés de lo que documentan el README y el `.env.example`. Un clone limpio expone el depurador de
Werkzeug (ejecución remota de código) en `0.0.0.0`.

- Cambiar el default a `"0"`.
- **Aceptación:** `python app.py` sin variables de entorno arranca sin depurador.

### 0.3 Comunicar al equipo
No volver a subir zips del proyecto; el `.env` no sale nunca de la máquina local.

---

## Fase 1 — Convertirlo en un repositorio de verdad (~2 h) 🔴

### 1.1 Versionar el código
Hoy `git ls-files` devuelve dos zips y nada más: **todo el fuente está sin trackear**. No hay
historia, no hay diffs, no hay revisión posible. Commitear `app.py`, `src/`, `static/`,
`templates/`, `data/`, `docs/` y la configuración.

### 1.2 Purgar los zips del historial *(requiere D-1)*
```bash
git filter-repo --path Team45-G9.zip --path Team45-G9-Prueba_2.zip --invert-paths
```
Force-push y re-clone por parte de todo el equipo. Elimina de paso el `venv/` de Windows
(3.907 archivos) y el directorio `.git/` anidado que van dentro del zip.

- **Aceptación:** `git log --all --stat` no menciona ningún `.zip` ni `.env`.

### 1.3 Blindar el `.gitignore`
Añadir `*.zip`, y un hook de pre-commit que rechace `.env` y cualquier binario mayor a 5 MB.

### 1.4 Piso de calidad
`ruff` + `pytest` en `requirements-dev.txt`, y un workflow de GitHub Actions que corra ambos en
cada PR. Sin esto, las fases siguientes no tienen red de seguridad.

---

## Fase 2 — Que los números sean ciertos (~1 día) 🟠

*Depende de D-3 y D-4.*

### 2.1 La tarifa del usuario se ignora en los ahorros
[`app.py:182`](../app.py#L182) asigna `resultado["tarifa_aplicada"] = tarifa` **después** de que
`consumo_mensual_standby` ya calculó `ahorro_clp_mes` llamando a `kwh_a_clp()` sin tarifa, con lo
que cae al valor CLP fijo del JSON. Para cualquier país que no sea Chile, los ahorros en dinero
están mal.

- Propagar `tarifa` como parámetro a lo largo de toda la cadena de `calculos.py`.
- **Aceptación:** el mismo hogar con `pais=DO` y `pais=CL` produce ahorros en monedas distintas y coherentes.

### 2.2 Una sola fuente de tarifas
El dict `_TARIFAS` de [`app.py:393`](../app.py#L393) duplica —con valores distintos— las tarifas de
`data/consumo_referencia.json`.

- Borrar el dict, dejar el JSON como única fuente y ampliarlo a los 24 países que hoy solo existen en `app.py`.

### 2.3 Un solo motor de cálculo
`/api/calcular` usa `calculos.py` (modelo físico: watts, standby, calor específico del agua),
mientras `/api/analisis-energetico` —el que realmente consume el frontend— usa helpers propios con
constantes gruesas (`aire_acondicionado * 120`, `refrigerador * 35`).

- Convertir `_estimar_consumo` en un traductor payload-del-wizard → llamadas a `calculos.py`.

### 2.4 Eliminar el ahorro fijo del 20%
[`app.py:617`](../app.py#L617): `ahorro_estimado = costo_estimado * 0.20` es constante e
independiente de los artefactos declarados, y contradice el "cálculo determinista" que promete el README.

- Sustituir por la suma de ahorros reales del desglose.

### 2.5 Eliminar el campo `probabilidad`
Los valores 0.90 / 0.75 / 0.82 de [`app.py:660`](../app.py#L660) no representan ninguna magnitud
medible. Sacarlos del contrato de la API.

### 2.6 Tests de `calculos.py`
Es matemática pura y determinista —el candidato ideal para tests unitarios— y hoy no tiene ninguno.
Casos mínimos: standby con y sin desconexión, `veces_semana`, iluminación vs LED, hervidor
(verificable contra la física), tarifa por país, clave de artefacto inexistente.

- **Aceptación:** ≥80% de cobertura en `src/calculos.py`.

---

### 2.7 Hallazgos abiertos por la Fase 2

Tres cosas que salieron al ejecutar el trabajo y que necesitan decisión, no código:

**a) El ahorro honesto es mucho menor que el inventado.** Un hogar tipo en Chile (4 habitantes,
refrigerador, freezer, 2 TV, A/C, 4 lavados semanales) daba **$9.792/mes** con el 20% fijo y da
**$277/mes** con la suma real. Son 35 veces menos. La cifra nueva es la correcta, pero solo monetiza
el consumo fantasma (standby), que es lo único que el motor modela como evitable. Las
recomendaciones contextuales sí prometen ahorros mayores —bajar el A/C a 24 °C, lavar en frío,
cambiar a LED— y ninguno entra en el número. **Modelar el ahorro de esas acciones es trabajo de
producto pendiente**, y hasta entonces el `ahorro_estimado` subestima.

**b) Dos potencias del JSON estaban mal y se corrigieron.** El refrigerador declaraba 150 W, que es
la potencia del compresor en marcha, no la media con el ciclado: aplicada 24/7 daba 108 kWh/mes,
unas 3 veces el consumo doméstico real. Igual la congeladora con 200 W. Ahora son 50 W y 62 W.
Esto **cambia los resultados de `/api/calcular`**, no solo los del wizard.

**c) La lavadora quedó en un valor no verificado.** El modelo viejo asumía 3.5 kWh por ciclo (muy
alto) y el JSON declaraba 500 W, que a 1 h por ciclo da 0.5 kWh (bajo, corresponde a lavado en frío
sin calentar agua). Se fijó en 1000 W → **~1 kWh por ciclo**, dentro del rango habitual de 0.5-2 kWh.
Es una estimación razonada, no un dato: **sustituir por la etiqueta energética de un equipo real.**

---

## Fase 3 — Endurecer la conexión con Groq (~4 h) 🟠

### 3.1 Un cliente, no cuatro
`ChatGroq(...)` se construye dentro de cada handler: [`app.py:50`](../app.py#L50),
[`125`](../app.py#L125), [`312`](../app.py#L312) y [`354`](../app.py#L354).
`langchain-groq 1.1.3` deja `request_timeout=None` y `max_retries=2` por defecto, y el código no los
sobreescribe: hoy un Groq colgado bloquea el worker de Flask indefinidamente.

- Factoría a nivel de módulo con `request_timeout=10`, `max_retries=1`, `max_tokens=300`.

### 3.2 Dejar de tragarse los errores
El `except Exception` mudo de [`app.py:58`](../app.py#L58) hace que una clave inválida cueste tres
intentos por request y que el fallback se sirva como si todo hubiera funcionado.

- Loguear con `app.logger.warning` y marcar la respuesta con `narrativa_fuente: "fallback"`.

### 3.3 JSON mode en vez de regex
Usar `response_format={"type": "json_object"}` y eliminar `re.search(r'\{[^{}]+\}')`
([`app.py:320`](../app.py#L320) y [`368`](../app.py#L368)), que rompe con cualquier objeto anidado.

### 3.4 Validar la salida del modelo en la boleta
`kwh_mes` y `tarifa_kwh` salen al cliente sin comprobar tipo, signo ni rango. `interpretar-campo` sí
valida contra lista blanca ([`app.py:138`](../app.py#L138)) — aplicar el mismo criterio: numérico,
mayor que cero y con tope plausible.

### 3.5 El `or` que trata el 0 como ausente
[`app.py:323`](../app.py#L323): `datos.get("kwh_mes") or kwh_extraido`. Cambiar a comprobación
explícita de `None`.

### 3.6 Modelo de visión configurable
`meta-llama/llama-4-scout-17b-16e-instruct` está hardcodeado en [`app.py:355`](../app.py#L355)
ignorando `GROQ_MODEL`. Introducir `GROQ_VISION_MODEL`.

### 3.7 Alinear el límite de subida
`MAX_CONTENT_LENGTH` acepta 10 MB y todo se manda en base64, por encima del límite real de imagen de
Groq. Verificar la cifra en su documentación y rechazar antes de gastar la llamada.

### 3.8 Rate-limit y fugas de error
`flask-limiter` en los tres endpoints que tocan Groq —hoy cualquiera puede agotar la cuota— y quitar
los `str(e)` que se devuelven al cliente en [`app.py:142`](../app.py#L142) y
[`app.py:383`](../app.py#L383).

---

## Fase 4 — Cablear lo que ya existe (~1-2 días) 🟡

Es la fase de mayor retorno: hay tres funcionalidades construidas y no alcanzables desde la interfaz.

| Endpoint | ¿Usa Groq? | ¿Lo llama el frontend? |
|---|---|---|
| `/api/analisis-energetico` | sí (narrativa) | sí, es el flujo real |
| `/api/calcular` | sí (narrativa) | solo como fallback roto |
| `/api/subir-boleta` | sí (texto + visión) | **no** |
| `/api/interpretar-campo` | sí | **no** |
| `/api/comparar` | no | **no** |
| `/api/paises` | no | sí |

### 4.1 La narrativa a la factura *(requiere D-2)*
[`templates/index.html:494`](../templates/index.html#L494) la deja en `hidden aria-hidden="true"`, y
aunque `poblarFactura` la desestructura en [`static/js/app.js:512`](../static/js/app.js#L512), **no la
usa en ninguna línea**: la factura imprime `res.recomendaciones`, que son deterministas. Cada submit
paga latencia y cuota de Groq para escribir en un div invisible.

- **Aceptación:** o la narrativa aparece en la vista de impresión, o la llamada al LLM desaparece del endpoint.

### 4.2 Cablear la subida de boleta
`/api/subir-boleta` —pdfplumber, regex, modelo de visión, ~145 líneas— no tiene ningún caller: no
existe un `<input type="file">` en toda la interfaz. Es la funcionalidad que el README vende.

- Añadir el uploader en el Paso 2, con estados de carga, error y nivel de confianza.

### 4.3 Cablear `interpretar-campo`
Conectarlo al caso "Otro" del tipo de inmueble, que es exactamente para lo que se escribió.

Al montar el linter (1.4) aparecieron dos defectos en este endpoint, ambos por no tener callers que
los expusieran:

- El parámetro `campo` se documentaba y se ignoraba: cualquier valor terminaba mapeado contra la lista
  de tipos de inmueble. **Corregido en 1.4** — ahora devuelve 400 ante un campo no soportado.
- El fallback sin API key ([`app.py:128`](../app.py#L128)) devuelve `texto[:50]`, es decir **el texto
  crudo del usuario**, saltándose la lista blanca que sí aplica la rama con LLM
  ([`app.py:144`](../app.py#L144)). El caller recibe una cadena arbitraria donde espera uno de cinco
  valores. Corregir al cablear.

### 4.4 Eliminar la cadena de fallback
[`static/js/app.js:379-390`](../static/js/app.js#L379-L390) reintenta contra `/api/calcular` y
`/calcular` con el payload del wizard, que tiene otra forma. `/api/calcular` no falla: responde 200
con todo en 0, gasta una llamada al LLM narrando ceros, y el usuario ve "0 kWh" como si fuera un
resultado válido. `/calcular` ni siquiera existe.

- Dejar una sola llamada con manejo de error real.

### 4.5 Timeout en el cliente
`AbortController` y timeout de 15 s en el `fetch`, con estado de carga y botón deshabilitado. Hoy no
hay ninguno: si el backend tarda, el navegador se queda colgado sin feedback.

### 4.6 Resolver el código huérfano *(requiere D-5)*
El agente CLI de `src/agente.py` + `src/tools.py` se retiró: usaba las firmas anteriores del motor y
quedó recuperable en el commit `b20282c`.

**`/api/comparar` se deja sin cablear a propósito**, y esta es la razón para que no quede en limbo:
su catálogo `categorias_comparables` está marcado en el propio JSON como *"DE EJEMPLO... reemplázalos
por datos reales de retailers antes de usar en producción"*, y todos los `precio_referencial` son
`null`. Conectarlo hoy pondría recomendaciones de compra con datos inventados delante del usuario,
que es peor que no ofrecer la función. El endpoint queda vivo y con tests; se cablea cuando haya un
catálogo real detrás.

### 4.7 Hallazgo abierto por la Fase 4

**El interruptor de periodo venía al revés.** El campo pide *"Consumo eléctrico mensual (kWh)"* con
marcador de posición "Ej: 250", pero el interruptor "El consumo es anual" estaba `checked` por
defecto. Quien escribía 250 pensando en su mes obtenía 20,8 kWh, porque el backend lo dividía por 12.
Corregido: el valor por defecto es mensual, que es lo que pide la etiqueta.

---

## Fase 5 — Robustez y deuda (~1 día) 🟡

### 5.1 Parseo de números latinoamericanos
[`app.py:307`](../app.py#L307): `float("1.234,5".replace(",", "."))` → `"1.234.5"` → `ValueError` →
500. Una boleta con separador de miles rompe la subida.

- Normalizador que detecte el formato por la posición del último separador.

### 5.2 Colisión de archivos subidos
[`app.py:262`](../app.py#L262) guarda en `uploads/<nombre_original>`: dos usuarios subiendo
`boleta.pdf` a la vez se pisan, y el `finally` del primero borra el archivo del segundo.

- Usar `tempfile.NamedTemporaryFile`.

### 5.3 Handler de 413
El límite de 10 MB devuelve HTML en vez de JSON. Añadir `@app.errorhandler(413)`.

### 5.4 `/api/comparar` responde 500 ante payload incompleto
[`app.py:153`](../app.py#L153) solo captura `ValueError`; un `KeyError` por falta de `categoria` u
`horas_uso_diario` se convierte en 500. Validar el payload.

### 5.5 Fijar el CDN
`unpkg.com/lucide@latest` sin SRI ni versión ([`templates/index.html:19`](../templates/index.html#L19))
es una dependencia de terceros sin pinnear. Fijar versión con `integrity`, o vendorizar el archivo.

### 5.6 Desacoplar `denji.js` — el hallazgo estaba sobredimensionado
Al ir a corregirlo resultó que `denji.js` **no** navega por texto: resuelve cada campo en tres
niveles —ID real en `MAPEO_CAMPOS`, atributo `data-denji-target`, y solo como último recurso el texto
de la etiqueta— y **los 21 IDs del primer nivel existen todos en la plantilla**, así que la búsqueda
por texto nunca llega a ejecutarse. La nota de cabecera del archivo describe el tercer nivel, no el
mecanismo real.

Añadir atributos `data-denji-*` habría sido un tercer mecanismo redundante. La fragilidad de verdad
es otra: ese acuerdo de IDs vive en dos archivos distintos, sin nada que lo verifique, y si alguien
renombra un ID el asistente cae en silencio al emparejamiento por texto. Se resolvió con
`tests/test_contrato_frontend.py`, que falla en CI si `denji.js` o `app.js` apuntan a un ID que ya no
está en la plantilla.

### 5.9 El micrófono del asistente no funcionaba *(hallazgo nuevo — cerrado)*

Reportado al usar la aplicación. Cuatro defectos acumulados en el mismo camino:

1. **Chrome devuelve el texto con puntuación y mayúscula** —`"Sí."`, `"Dos."`— y el código comparaba
   con igualdad exacta contra `'si'` o contra la etiqueta completa del botón. `['si'].includes('si.')`
   es `false`: **responder "sí" no funcionó nunca**. Se añade `normalizarVoz()`, que quita la
   puntuación, y las comparaciones pasan a ser por palabras y con sinónimos.
2. **El botón se quedaba en "Escuchando…" para siempre.** No había manejador `onend`, que es el único
   que se dispara en todos los finales; si la escucha terminaba sin resultado ni error, nada
   restauraba el botón. Además `rec.start()` lanza `InvalidStateError` de forma síncrona si ya había
   un reconocimiento en curso, y la excepción escapaba del `onclick`.
3. **No se podía cancelar.** El botón se deshabilitaba a sí mismo, así que una escucha colgada solo
   se salvaba recargando la página. Ahora alterna: el segundo toque cancela.
4. **El asistente se escuchaba a sí mismo.** No se detenía la síntesis de voz al abrir el micrófono.

Añadidos: tope de 12 s, reintento con otro idioma ante `language-not-supported` —Chrome puede
rechazar `es-419`, que era el que se pedía— y mensajes que dicen qué se entendió en vez de un
"no te entendí" genérico.

### 5.8 Geolocalización a un tercero *(hallazgo nuevo — cerrada)*
`denji.js` enviaba las coordenadas del usuario directamente a
`nominatim.openstreetmap.org` para resolver la ciudad. La consulta pasa ahora por el backend
([`src/geo.py`](../src/geo.py) + `GET /api/ubicacion`), lo que resuelve cinco cosas de una vez:

- **Identificación.** La política de uso de Nominatim exige un `User-Agent` que identifique la
  aplicación y dé una vía de contacto; un navegador no puede fijar esa cabecera y un servidor sí.
- **El país ya se autocompleta.** Nominatim devuelve el nombre del país en el idioma del lugar, y
  `fijarPaisPorNombre()` lo comparaba contra la lista en español: para "United States" contra
  "Estados Unidos" no encontraba la opción y **el selector se quedaba vacío sin avisar**. Ahora se
  devuelve el `country_code` ISO, que mapea directo a las claves de `calculos.PAISES`.
- **Caché** por coordenada redondeada, sobre un servicio comunitario gratuito.
- **Un tope de una petición por segundo** para toda la aplicación, como pide la política.
- **Privacidad.** El usuario acepta compartir su ubicación con esta aplicación, no con un tercero.
  Se sigue redondeando a 2 decimales (~1 km), coherente con el `zoom=10` que resuelve a nivel de
  ciudad, y se avisa en la interfaz.

> **Falta un valor para que funcione.** `NOMINATIM_CONTACTO` está vacío en `.env.example` y hay que
> poner ahí el alias de correo del equipo. Mientras no esté, el backend **no llama** al servicio:
> responde 503 y la aplicación pide la ubicación a mano. Es deliberado — es preferible perder la
> autodetección a hacer peticiones sin identificar contra un servicio gratuito ajeno.

---

## Fase 6 — Dockerización (~4-6 h) 🟢

*Depende de la Fase 1 (el código tiene que estar versionado) y se beneficia de la 0.2 y la 3.1.*

Hoy el único empaquetado es [`.devcontainer/devcontainer.json`](../.devcontainer/devcontainer.json),
que sirve para desarrollo en Codespaces pero no produce una imagen desplegable, y además fija
Python 3.11 mientras el README pide 3.12+ y los `.pyc` del repo son 3.13.

### 6.1 Reproducibilidad de dependencias *(requiere D-6)*
`requirements.txt` usa solo restricciones `>=`, así que dos builds del mismo commit pueden instalar
versiones distintas de LangChain y romperse entre sí.

- Fijar versiones exactas (`pip-compile` o `uv pip compile`) generando un `requirements.lock`.
- Unificar la versión de Python en un solo lugar y alinear devcontainer, README e imagen.
- **Aceptación:** dos builds del mismo commit producen el mismo árbol de dependencias.

### 6.2 `Dockerfile` multi-stage
- Base `python:3.12-slim`; stage de build para compilar wheels, stage final solo con el runtime.
- Usuario no-root (`USER app`), sin shell de login.
- `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`.
- **Aceptación:** la imagen final pesa menos de 300 MB y no contiene compiladores.

### 6.3 `.dockerignore`
Crítico dado el estado actual del directorio: `venv/` (un venv de Windows inservible en Linux),
`*.zip` (44 MB), `.git/`, `__pycache__/`, `uploads/`, `.env`, `docs/`.

- **Aceptación:** el contexto de build es menor a 5 MB.

### 6.4 Servidor de producción
`app.run()` es el servidor de desarrollo de Werkzeug y no debe atender tráfico real.

- `gunicorn` como entrypoint, con workers configurables por variable de entorno.
- Los timeouts de gunicorn deben ser mayores que el `request_timeout` de Groq definido en 3.1,
  o la petición se cortará antes de que el LLM responda.

### 6.5 Configuración por entorno, nunca horneada
El `.env` no entra en la imagen bajo ninguna circunstancia: `GROQ_API_KEY`, `GROQ_MODEL`,
`GROQ_VISION_MODEL`, `PORT` y `FLASK_DEBUG` se inyectan en tiempo de ejecución.

- **Aceptación:** `docker history` y `docker run --rm img env` no revelan ningún secreto.

### 6.6 Endpoint `/health` y `HEALTHCHECK`
No existe hoy. Debe responder sin llamar a Groq —solo verificar que la app y
`data/consumo_referencia.json` cargaron— para que el healthcheck no consuma cuota.

### 6.7 `uploads/` efímero
El código ya borra los archivos en el `finally`, así que el directorio no necesita persistencia.

- Montarlo como `tmpfs` para que nada quede en la capa de escritura del contenedor.

### 6.8 `docker-compose.yml` para desarrollo local
Un solo servicio, `env_file: .env`, `PORT` mapeado, y bind-mount del código con recarga automática
para que el ciclo de desarrollo no exija reconstruir la imagen.

### 6.9 Build en CI
Extender el workflow de la Fase 1.4 para construir la imagen en cada PR (sin publicarla) y así
detectar builds rotos antes del merge.

### 6.10 Documentar el arranque con Docker
Añadir la sección al README junto a la instalación con `venv`, y decidir si el devcontainer se
mantiene o se reemplaza por el `docker-compose` para no sostener dos definiciones divergentes.

---

## Fase 7 — Documentación (~3 h) 🟢

*Se ejecuta al final: documenta el estado real después de las fases anteriores, no el previsto.*

La documentación actual describe un sistema que no existe. Corregirla antes de terminar las fases 2-6
obligaría a reescribirla dos veces.

### 7.1 `README.md` — corregir lo que hoy es falso
- **URL de clone equivocada:** apunta a `alejolanda/challengerRagAlura`; el remoto real es
  `alejolanda/desafioTeam49`. Cualquiera que siga el README clona otro proyecto.
- **`FLASK_DEBUG`:** la tabla dice que el default es `0`; el código usa `1`
  ([`app.py:665`](../app.py#L665)). Se corrige en 0.2 — reflejarlo aquí.
- **Lectura de boletas:** el stack menciona `pdfplumber`, pero la funcionalidad no está cableada a la
  interfaz hasta la 4.2. Documentarla solo cuando exista.
- **"Mapeo Directo sin Sobrecarga de LLM":** describe una optimización que no ocurre — hoy se hace una
  llamada a Groq por cada submit cuyo resultado nadie ve (4.1).
- **Estructura del proyecto:** el árbol omite `src/agente.py`, `src/tools.py`, `static/js/denji.js`,
  `static/img/`, `.devcontainer/` y `docs/`. Regenerarlo.
- **Versión de Python:** dice 3.12+ mientras el devcontainer fija 3.11 (ver D-6).

### 7.2 `README.md` — añadir lo que falta
- Sección de arranque con Docker (`docker compose up`), junto a la instalación con `venv` (6.10).
- Enlace a la documentación Swagger (7.3) en lugar de una tabla de endpoints mantenida a mano, que
  se desincroniza del código a la primera semana.
- Variables nuevas: `GROQ_VISION_MODEL` (3.6) y las de gunicorn (6.4).
- Cómo correr los tests (`pytest`) y el linter (`ruff`), tras la 1.4.
- Nota explícita de que las tarifas por país son **referenciales y no verificadas**, tal como ya
  advierten los campos `_nota` y `es_catalogo_ejemplo` de `data/consumo_referencia.json`. Hoy el
  README las presenta sin ese matiz.

### 7.3 Documentación Swagger / OpenAPI de la API
Hoy no existe ninguna especificación: el contrato de los endpoints solo se deduce leyendo `app.py` y
`static/js/app.js`, y ambos discrepan (ver 4.4). Es la causa de que el frontend intente tres rutas
distintas con el mismo payload.

**Herramienta.** `flasgger` sobre las rutas `@app.route` existentes, que genera la spec desde
docstrings y sirve Swagger UI sin reestructurar el código. *Excepción:* si la validación de entrada de
3.4 se implementa con esquemas (pydantic o marshmallow), usar `flask-smorest` en su lugar y obtener
validación y especificación de una sola fuente, en vez de mantener dos.

**Qué documentar** — los 6 endpoints reales más `/health` (6.6):

| Endpoint | Detalle que no puede faltar |
|---|---|
| `/api/analisis-energetico` | Los ~20 campos del payload del wizard y qué pasa con los ausentes (`_sanitizar` los convierte a 0) |
| `/api/subir-boleta` | `multipart/form-data` con el campo `boleta` y el campo `pais`; extensiones aceptadas y límite de tamaño (3.7) |
| `/api/calcular` | Payload por artefactos, **distinto** al del wizard — precisamente la confusión que causó 4.4 |
| `/api/interpretar-campo` | Los valores de la lista blanca que puede devolver ([`app.py:117`](../app.py#L117)) |
| `/api/comparar` | Categorías válidas y la marca `es_catalogo_ejemplo` |
| `/api/paises` | Forma del diccionario de países |

**Puntos que la spec debe reflejar explícitamente:**
- Los **alias de compatibilidad** de la respuesta de `/api/analisis-energetico`
  ([`app.py:655-660`](../app.py#L655-L660)): `costo_estimado_mensual`, `total_kwh_mes`,
  `total_clp_mes`, `ahorro_potencial_clp_mes` duplican campos primarios. Marcarlos `deprecated: true`
  y fijar fecha de retiro, o el contrato crece indefinidamente.
- Todos los códigos de error reales: 400, 413 (6.3… tras 5.3), 422 y 500, con su cuerpo JSON. Hoy el
  413 devuelve HTML y el 422 solo aparece en la ruta de boleta.
- Los campos que la Fase 2 elimina (`probabilidad`) **no** deben documentarse.

**Exposición.** Servir Swagger UI en `/apidocs` detrás de una variable de entorno
(`ENABLE_API_DOCS`), desactivada por defecto en producción: publicar el catálogo de endpoints que
consumen Groq facilita justamente el abuso que mitiga 3.8.

**Versionado.** Exportar `docs/openapi.json` y regenerarlo en CI (1.4), fallando el build si difiere
del commiteado. Así todo cambio de contrato aparece como diff en el PR en vez de descubrirse en producción.

- **Aceptación:** la spec valida contra OpenAPI 3.0, cubre los 7 endpoints, y cada ejemplo de request
  documentado devuelve 200 al ejecutarse contra la app real.

### 7.4 `.env.example`
Debe listar todas las variables que el código lee, en el mismo orden que la tabla del README:
`GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_VISION_MODEL`, `PORT`, `FLASK_DEBUG`. Hoy faltan las nuevas y el
valor de `FLASK_DEBUG` contradice al código.

### 7.5 `UI_DESIGN.md`
Son cuatro líneas que muestran una única pantalla ("Ubicación & Tarifa") sobre un wizard que ya tiene
cuatro pasos, resultados y factura imprimible. Ampliarlo o fusionarlo con el README: mantener un
documento desactualizado de cuatro líneas cuesta más de lo que aporta.

### 7.6 Documentar las decisiones tomadas
Registrar en `docs/` el resultado de D-1 a D-6, con su justificación. Sin esto, dentro de tres meses
nadie recordará por qué se eligió `calculos.py` como motor único o por qué se borró el agente CLI.

- **Aceptación:** alguien ajeno al equipo clona el repositorio, sigue el README y llega a la app
  funcionando —con Docker y sin Docker— sin preguntar nada.

---

## Resumen

| Fase | Ítems | Esfuerzo | Depende de |
|---|---|---|---|
| 0 · Contención | 3 | 1 h | — |
| 1 · Repositorio real | 4 | 2 h | D-1 |
| 2 · Números ciertos | 6 | 1 día | Fase 1, D-3, D-4 |
| 3 · Groq robusto | 8 | 4 h | Fase 1 |
| 4 · Cableado y función real | 6 | 1-2 días | Fase 2/3, D-2, D-5 |
| 5 · Robustez y deuda | 6 | 1 día | Fase 1 |
| 6 · Dockerización | 10 | 4-6 h | Fase 1, D-6 |
| 7 · Documentación | 6 | 5 h | Fases 2-6 |

**Ruta crítica:** Fase 0 → Fase 1 → (Fase 2 ∥ Fase 3) → Fase 4 → (Fase 5 ∥ Fase 6) → Fase 7.
Las fases 2 y 3 son independientes entre sí, igual que la 5 y la 6. La 7 va al final a propósito:
documentar antes obliga a reescribir.

**Si solo hubiera medio día:** 0.1, 0.2, 4.1 y 4.4. Eso cierra la fuga de credenciales, la ejecución
remota de código, el gasto inútil en Groq y el bug que muestra ceros como si fueran un resultado válido.

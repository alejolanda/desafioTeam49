# Decisiones técnicas

Por qué el código es como es. Sin esto, dentro de tres meses nadie recordará por qué se eligió un
motor de cálculo sobre otro, o por qué la detección de ubicación se apaga sola.

Las tareas que se citan (`2.3`, `5.8`…) están en [PLAN.md](PLAN.md).

---

## D-1 · Rotar la clave y reescribir el historial

**Contexto.** El commit inicial subía dos `.zip` del proyecto. Dentro iba un `.env` con la clave de
Groq en claro, además del `venv/` completo y un `.git/` anidado. El `.gitignore` protegía el `.env`
suelto, pero no sirve de nada cuando el archivo viaja dentro de un zip.

**Decisión.** Rotar la clave **y** purgar los zips del historial.

**Por qué.** Son cosas distintas y solo una protege: purgar el historial no desprotege una clave que
ya fue pública, porque GitHub conserva los objetos huérfanos accesibles por su SHA aun después de un
force-push. La rotación es la mitigación; la purga es limpieza de 44 MB de peso muerto.

**Estado.** El trabajo se aisló en una rama para no forzar un re-clone al equipo, lo que resuelve el
versionado pero deja los zips en `e4cf47e`, ancestro de todas las ramas. **La rotación sigue
pendiente** y es lo único que de verdad cierra el incidente.

---

## D-2 · La narrativa del modelo va a la factura impresa

**Contexto.** Se generaba en cada cálculo y se escribía en un `<div hidden aria-hidden="true">`. La
función que arma la factura la recibía y no la usaba en ninguna línea. Es decir: cada envío del
formulario pagaba latencia y cuota de Groq para producir un texto que **ningún usuario veía jamás**.

**Decisión.** Mostrarla en la factura imprimible, no en pantalla.

**Por qué.** En pantalla ya están las métricas destacadas, que comunican lo mismo de forma más
directa. En un documento impreso, en cambio, un párrafo en prosa que explique las cifras sí aporta.
La alternativa —eliminar la llamada— habría sido igual de defendible; se eligió conservarla porque el
valor estaba construido y solo faltaba enchufarlo.

---

## D-3 · `calculos.py` es el único motor

**Contexto.** Había dos motores en paralelo. `/api/calcular` usaba `calculos.py`, con un modelo
físico real. `/api/analisis-energetico` —el que consumía la web— usaba helpers propios dentro de
`app.py` con constantes gruesas del tipo `aire_acondicionado * 120`.

**Decisión.** `calculos.py` gana. Los helpers pasan a ser un traductor del formulario a llamadas del
motor, y las suposiciones de uso viven en `perfil_hogar` dentro del JSON de referencia.

**Por qué.** Es física verificable y se puede probar; las constantes no. Y sacar las suposiciones a
datos las hace auditables: antes, que un aire acondicionado consumiera 120 kWh al mes era un número
sin origen dentro del código; ahora es "900 W durante 4,4 h al día", que cualquiera puede discutir.

**Consecuencia.** La migración conservó los totales dentro del ±3%, salvo dos casos donde los datos
estaban mal y se corrigieron (ver más abajo).

---

## D-4 · El ahorro se suma artefacto por artefacto

**Contexto.** Era `costo_estimado * 0.20`. Un 20% fijo, idéntico para todos los hogares e
independiente de los equipos declarados.

**Decisión.** Sumar el ahorro real de cada artefacto del desglose.

**Por qué.** El README prometía cálculo determinista y aquello era una constante. Presentar una cifra
inventada como diagnóstico es peor que no darla.

**Consecuencia incómoda.** La cifra honesta es **mucho menor**. Un hogar tipo en Chile pasó de
$9.792/mes a $277/mes: unas 35 veces menos. El motivo es que hoy solo se modela como evitable el
consumo fantasma. Las recomendaciones textuales prometen más —bajar el aire acondicionado, lavar en
frío, cambiar a LED— y nada de eso entra aún en el número. **Modelar esos ahorros es trabajo de
producto pendiente**, y hasta entonces la cifra es conservadora.

---

## D-5 · El agente conversacional sale del alcance

**Contexto.** `src/agente.py` y `src/tools.py` implementaban un agente con *tool-calling*: la parte
técnicamente más interesante del proyecto. Nunca estuvo montado en Flask, era un CLI huérfano, y su
prompt decía "ayuda a personas en Chile" mientras la app soportaba 24 países.

**Decisión.** Retirarlos del árbol de trabajo. Quedan recuperables en el commit `b20282c`.

**Por qué.** Al hacer obligatoria la tarifa en el motor, sus firmas quedaron rotas. Arreglarlas para
código que nadie ejecuta era mantener una deuda sin contrapartida. Montar el agente de verdad es un
proyecto aparte, no una corrección.

---

## D-6 · Python 3.12 en todas partes

**Contexto.** Convivían tres versiones: el devcontainer fijaba 3.11, el README pedía 3.12+, y los
`.pyc` versionados eran 3.13.

**Decisión.** 3.12 en el `Dockerfile`, la CI y el devcontainer.

**Por qué.** Da igual cuál, mientras sea una sola. Se eligió 3.12 por ser lo que el README ya pedía y
tener soporte largo.

---

## Decisiones que surgieron al implementar

### El JSON manda sobre el código, para las tarifas

Había dos tablas de tarifas: un diccionario en `app.py` y el JSON de referencia. **Discrepaban en 14
de 17 países** (Bolivia 7,5×, Venezuela 5×). Peor: el selector del formulario se poblaba desde el
JSON pero el precio salía del diccionario, así que el usuario elegía un país y se le cobraba con otra
tarifa. Gana el JSON, porque documenta el regulador de origen de cada valor. Los siete países que
solo existían en el código se migraron marcados `SIN VERIFICAR`.

### Un país desconocido falla en vez de cobrar en dólares

El código anterior caía en silencio a 0,18 USD/kWh para cualquier código no reconocido. Ahora se
devuelve 400 con la lista de países soportados. Un error visible es mejor que un importe convincente
y equivocado.

### La tarifa es un parámetro obligatorio, sin valor por defecto

`kwh_a_clp()` tenía un valor de reserva de 150 CLP que se aplicaba en silencio a los 24 países, así
que un usuario dominicano recibía sus ahorros en pesos chilenos. No se restauró el valor por defecto
a propósito: si falta la tarifa es un error de programación, no algo que deba resolverse adivinando.

### `/api/comparar` se deja sin conectar

Su catálogo está marcado en el propio JSON como de ejemplo y todos los precios son `null`.
Conectarlo pondría recomendaciones de compra inventadas delante del usuario, que es peor que no
ofrecer la función. El endpoint queda vivo y con tests, listo para cuando haya un catálogo real.

### Dos potencias del JSON estaban mal

El refrigerador declaraba 150 W, que es la potencia del compresor **en marcha**, no la media con el
ciclado: aplicada 24/7 daba 108 kWh al mes, unas tres veces el consumo doméstico real. Igual la
congeladora con 200 W. Ahora son 50 W y 62 W. La lavadora pasó de 500 W (solo motor, lavado en frío)
a 1000 W como media de un ciclo mixto; ese valor **es una estimación razonada, no un dato**, y está
marcado para sustituir por la etiqueta energética de un equipo real.

### La geocodificación pasa por el backend, y se apaga sola si no está identificada

El navegador llamaba directo a Nominatim. Ahora va por `src/geo.py`, lo que permite identificar la
aplicación como exige su política de uso, cachear, y respetar el límite de una petición por segundo.
De paso arregló un fallo silencioso: Nominatim devuelve el país en el idioma del lugar ("United
States") y el frontend lo comparaba contra la lista en español ("Estados Unidos"), así que para
varios países el selector se quedaba vacío sin avisar. Ahora se usa el código ISO.

Si `NOMINATIM_CONTACTO` no está configurado, **no se llama al servicio**. Es preferible perder la
autodetección a hacer peticiones sin identificar contra un servicio comunitario gratuito.

### La documentación de la API está apagada por defecto

Publicar el catálogo de endpoints que consumen servicios de pago facilita justo el abuso que mitiga
el límite de tasa. Se activa con `ENABLE_API_DOCS=1`. La interfaz visual de Swagger empaqueta ~9 MB,
así que `flasgger` es dependencia de desarrollo: el contrato en `openapi.yaml` se sirve igual sin
ella.

### Un worker con hilos, no varios procesos

El límite de tasa y la caché de geocodificación viven en la memoria del proceso. Con varios workers
cada uno tendría las suyas y en conjunto superarían el límite que exige Nominatim. Escalar requiere
apuntar antes `RATELIMIT_STORAGE_URI` a Redis; la sección está lista para descomentar en el
`docker-compose.yml`.

### El linter arranca permisivo a propósito

`ruff` selecciona solo `E4`, `E7`, `E9` y `F`: errores reales, sin reglas de estilo. Con un límite de
longitud de línea estricto, la CI habría nacido en rojo por 17 líneas heredadas, que es la forma más
rápida de que un equipo aprenda a ignorarla. Se endurece cuando el código esté cubierto por tests.

### El devcontainer y `docker-compose` se mantienen separados

Sirven para cosas distintas: uno es para editar (necesita escritura y dependencias de desarrollo), el
otro para ejecutar como en producción (código en solo lectura). Lo único que no pueden divergir es la
versión de Python, y ya no divergen.

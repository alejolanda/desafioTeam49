# Plan de cumplimiento — EnergiAI

Qué falta para que VólticvS cumpla las bases del hackathon *EnergiAI – Inteligencia para el Consumo
Energético*, y en qué orden hacerlo.

Es un plan distinto al de [PLAN.md](PLAN.md): aquel corregía defectos del código existente; este
añade lo que las bases exigen y el proyecto no tiene.

- **Fecha:** 2026-08-15
- **Bases:** [`EnergiAI.pdf`](EnergiAI.pdf) — 5 páginas, versionado junto al código para que este plan
  se pueda contrastar con la fuente sin salir del repositorio
- **Estado del proyecto:** auditoría cerrada, 150 tests, imagen Docker verificada

> Todo lo que sigue se contrasta contra ese PDF. Cuando el plan dice "las bases piden", es cita de
> ahí. El `.dockerignore` lo excluye de la imagen: es documentación del equipo, no algo que la
> aplicación necesite en ejecución.

---

## Veredicto

**No cumple.** La ingeniería está muy por encima de lo que piden en varios frentes —API documentada,
contenedorización, pruebas, front-end— pero faltan **dos entregables obligatorios completos** y el
contrato del endpoint principal no coincide con el especificado.

| Requisito mínimo | Estado |
|---|---|
| Modelo entrenado y cargado correctamente | ❌ no existe |
| Clasificación funcional | ✅ Eficiente / Moderado / Ineficiente |
| Generación de recomendaciones | ✅ |
| Estimación del costo energético | ✅ la tarifa de Brasil ya es exactamente 0,75 BRL |
| API documentada | ✅ OpenAPI 3 + Swagger |
| Integración con OCI | ❌ cero referencias |
| Mínimo 3 ejemplos de utilización | ⚠️ hay 3 en el contrato; probablemente piden más |

**Entregable de Ciencia de Datos:** un notebook con EDA, análisis de patrones, transformación de
variables, entrenamiento supervisado, evaluación con métricas y serialización del modelo. **No hay
nada**: 0 notebooks, 0 datasets, sin scikit-learn.

**Contrato del endpoint.** Las bases especifican `POST /analisis-energetico`:

| | Especificado | Hoy |
|---|---|---|
| Ruta | `/analisis-energetico` | `/api/analisis-energetico` |
| `consumo_kwh` | entrada | ✅ |
| `tipo_inmueble` | entrada | ✅ |
| `uso_horario_pico` | entrada | ❌ se descarta |
| `cantidad_equipos` | entrada | ❌ se descarta |
| `horas_alto_consumo` | entrada | ❌ se descarta |
| `categoria` | salida | ✅ |
| `probabilidad` | salida | ❌ **se eliminó en la tarea 2.5** |
| `recomendaciones` | salida | ✅ |
| `costo_estimado_mensual` | salida | ✅ |

Falta además el **endpoint de consulta de resultados**: no hay persistencia de ningún tipo.

---

## Lo que NO bloquea

- **"Preferentemente en Java con Spring Boot"** es una preferencia declarada, no un requisito. Flask
  cumple lo que sí se exige: API REST, validación de entrada, manejo de errores y documentación.
- **El front-end es opcional** y ya está hecho, con asistente guiado por voz.
- De los recursos opcionales ya hay **contenedorización con Docker** y **pruebas automatizadas**.

---

## El punto delicado: `probabilidad`

Se eliminó en la auditoría porque era `0.90 / 0.75 / 0.82`, tres constantes asignadas por categoría
sin ninguna magnitud detrás. Hay incluso un test que impide que reaparezca.

**Esa decisión sigue siendo correcta, y restaurar los números inventados sería un retroceso.** Las
bases piden ese campo porque asumen un clasificador entrenado, donde la cifra es la salida real de
`predict_proba()`. Es decir: el hueco de ciencia de datos y el campo que falta **son el mismo
problema**, y se resuelven juntos. El test se actualizará para exigir lo contrario —que la
probabilidad exista y venga del modelo— en lugar de borrarse.

## La arquitectura no cambia de identidad

El proyecto se sostiene sobre una decisión: **el dinero y los kWh son deterministas**, nadie los
inventa. Añadir un modelo no la contradice si se respeta el reparto:

| Qué | Quién lo produce |
|---|---|
| kWh de consumo | `calculos.py` — física, determinista |
| Costo y ahorro | `calculos.py` — tarifa por país |
| **Categoría de eficiencia y su probabilidad** | **modelo entrenado** |
| Recomendaciones | reglas deterministas sobre el desglose |
| Narrativa | modelo de lenguaje, sin tocar ninguna cifra |

El clasificador sustituye a `_clasificar()`, que hoy son tres umbrales fijos (250 / 450 kWh) sin
justificación documentada. Las bases piden exactamente eso: *"los equipos deberán definir y
justificar los criterios para caracterizar los diferentes perfiles"*.

---

## Decisiones pendientes

| # | Decisión | Recomendación |
|---|---|---|
| H-1 | **¿Hay cuenta de OCI?** Sin ella no se cumple, por buena que sea la ingeniería | Averiguarlo **hoy**. El *Always Free* de Oracle incluye 20 GB de Object Storage, suficiente para el modelo |
| H-2 | ¿Se cambia la ruta a `/analisis-energetico` o se mantiene `/api/`? | **Ambas.** Añadir la ruta que piden como alias; romper el frontend por un prefijo sería absurdo |
| H-3 | ¿Se usa la tarifa fija de 0,75 BRL o se mantienen los 24 países? | **Mantener los 24.** Es un superconjunto de lo pedido; basta con que los ejemplos usen Brasil |
| H-4 | ¿Qué modelo? | **Random Forest**, con Regresión Logística como línea base para comparar. Ambos están entre los sugeridos |
| H-5 | ¿De dónde sale el dataset? | **Simulado y documentado**, que es una de las tres vías que permiten las bases. La generación debe ser reproducible y quedar en el notebook |
| H-6 | ¿Qué fecha límite hay? | Desconocida. Cambia por completo el orden: si son días, las fases A y E son lo único que importa |

---

## Fase A — Ciencia de datos (~1 día) 🔴

Es el entregable que más pesa y del que dependen los demás.

### A.1 Generar el dataset
Construir un generador reproducible —semilla fija— de perfiles de hogar con las variables que el
contrato exige: `consumo_kwh`, `uso_horario_pico`, `cantidad_equipos`, `tipo_inmueble`,
`horas_alto_consumo`.

Ventaja de este proyecto: **el consumo no hace falta inventarlo**. `calculos.estimar_desde_perfil()`
ya convierte un hogar en kWh con física real, así que el dataset se genera muestreando hogares
plausibles y calculando su consumo con el motor. Los datos quedan internamente coherentes en vez de
ser ruido aleatorio, y eso se puede defender ante un jurado.

- Guardar en `data/consumo_hogares.csv`, versionado.
- **Aceptación:** el notebook regenera el CSV byte a byte desde la semilla.

### A.2 Definir y justificar las etiquetas
Las bases lo piden explícitamente. Los umbrales de hoy (250 / 450 kWh) no tienen origen documentado.

- Derivar los cortes de la distribución del propio dataset (terciles) o de una referencia citable, y
  **escribir el porqué** en el notebook.

### A.3 Notebook `notebooks/energiai.ipynb`
Con las seis secciones que exigen las bases: EDA, análisis de patrones de consumo, tratamiento y
transformación de variables, entrenamiento supervisado, evaluación con métricas y serialización.

- Línea base con Regresión Logística, modelo final Random Forest.
- Métricas: exactitud, precisión, exhaustividad, F1 por clase y matriz de confusión. Con tres clases
  desbalanceadas, la exactitud sola no dice nada.
- **Aceptación:** el notebook corre de principio a fin sin intervención y deja el modelo en disco.

### A.4 Serializar el modelo
`joblib` a `modelos/clasificador_energetico.joblib`, junto a un `metadatos.json` con la versión de
scikit-learn, la fecha, las métricas obtenidas y el orden de las features.

> Sin ese orden guardado, el modelo produce predicciones erróneas en silencio si alguien reordena las
> columnas. Es el fallo clásico de poner un modelo en producción.

---

## Fase B — El modelo dentro de la API (~3 h) 🔴

### B.1 `src/modelo.py`
Carga perezosa y cacheada del modelo, misma forma que `src/llm.py` y `src/geo.py`: si el archivo no
está, se degrada a los umbrales actuales y se declara en la respuesta.

### B.2 Sustituir `_clasificar()`
La categoría y la probabilidad pasan a salir de `predict()` y `predict_proba()`.

- Nuevo campo `fuente_clasificacion`: `modelo` | `umbrales`, coherente con `narrativa_fuente` y
  `fuente_consumo`, que ya distinguen de dónde viene cada cosa.
- **Aceptación:** `probabilidad` corresponde a la clase devuelta y está entre 0 y 1.

### B.3 Actualizar el test que la prohibía
`test_probabilidad_ya_no_se_expone` se invierte: ahora debe **exigir** que exista, que sea coherente
con la categoría y que no sea una constante por categoría —justamente lo que era antes—.

---

## Fase C — Contrato del endpoint (~1 h) 🟠

### C.1 Aceptar las cinco variables especificadas
`uso_horario_pico`, `cantidad_equipos` y `horas_alto_consumo` hoy se descartan en `_sanitizar()`.

Las dos últimas se pueden **derivar** de lo que el asistente ya recoge —la suma de equipos
declarados y las horas del perfil—, así que se aceptan explícitas y se calculan cuando falten.
`uso_horario_pico` no se pregunta en ninguna parte: hay que añadir el interruptor al Paso 1.

### C.2 Alias de ruta
Registrar `POST /analisis-energetico` además de `/api/analisis-energetico` (H-2).

### C.3 Actualizar el contrato OpenAPI
Los tests de deriva fallarán solos si no se hace, que es justo para lo que están.

---

## Fase D — Persistencia y consulta (~3 h) 🟠

Las bases piden un *"endpoint para consulta de resultados"* que hoy no existe.

- SQLite por defecto —sin servicio extra que desplegar—, con la ruta configurable por entorno.
- `POST /analisis-energetico` guarda cada análisis y devuelve su identificador.
- `GET /analisis-energetico/<id>` lo recupera; `GET /analisis-energetico` lista los últimos.
- Cuidado con el contenedor: hoy el único directorio escribible es un `tmpfs`. La base necesita un
  volumen persistente o los datos se pierden al reiniciar.

Desbloquea de paso el **historial de análisis**, que figura entre los opcionales.

---

## Fase E — Integración con OCI (~3 h) 🔴 *bloqueada por H-1*

**Es obligatoria y no puedo resolverla sin credenciales.** Enfoque propuesto, el más barato y el que
menos ata el proyecto:

- **Object Storage** para el modelo serializado y el dataset. La API descarga el modelo al arrancar
  si no lo tiene en local, con `oci-sdk`.
- Credenciales por variables de entorno, **nunca en el código** ni en la imagen, igual que el resto.
- **Degradación explícita**, como con Nominatim: sin credenciales usa el modelo local y lo dice en
  `/health`. Así el proyecto sigue funcionando para quien lo clone sin cuenta de Oracle.
- Documentar la arquitectura, que las bases piden expresamente.

> Si no hubiera cuenta a tiempo, la alternativa es **OCI Compute** alojando el contenedor, que ya
> está listo para desplegarse. Sigue exigiendo cuenta: no hay forma de cumplir este punto sin ella.

---

## Fase F — Ejemplos y documentación (~2 h) 🟡

- **Mínimo tres ejemplos de utilización** en un documento propio: petición, respuesta e
  interpretación. Conviene que sean casos contrastantes —un hogar eficiente, uno moderado y uno
  ineficiente— y que usen la tarifa de Brasil de las bases.
- Documentar la arquitectura elegida, exigido tanto en las directrices de back-end como en las de OCI.
- Actualizar el README con el modelo, el notebook y OCI.

---

## Resumen

| Fase | Esfuerzo | Bloquea |
|---|---|---|
| A · Ciencia de datos | 1 día | B, y es entregable en sí |
| B · Modelo en la API | 3 h | C |
| C · Contrato del endpoint | 1 h | — |
| D · Persistencia y consulta | 3 h | — |
| E · OCI | 3 h | **H-1: hace falta cuenta** |
| F · Ejemplos y documentación | 2 h | todas las anteriores |

**Ruta crítica:** A → B → C → F, con D y E en paralelo.

**Si el plazo fuera de un día:** A, B y E. Son los dos entregables obligatorios que faltan; el
contrato y la persistencia se pueden defender como incompletos, la ausencia de modelo y de OCI no.

**Lo primero de todo, antes que cualquier código:** resolver H-1. Es el único punto que ninguna
cantidad de trabajo por mi parte puede suplir.

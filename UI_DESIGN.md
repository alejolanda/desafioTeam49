# Diseño de interfaz — VólticvS

## Principio

Reducir la carga cognitiva. La persona que llega no sabe cuántos vatios consume su refrigerador y no
tiene por qué saberlo: se le pregunta lo que sí sabe —cuántos equipos tiene, cuántas horas ve
televisión— y el sistema traduce eso a energía.

![Propuesta de interfaz](./docs/inferfaz_volticvs.png)

> La imagen corresponde a la propuesta inicial de la pantalla "Ubicación & Tarifa". La interfaz
> implementada creció desde entonces: son cuatro pasos más resultados y factura imprimible.

---

## Recorrido

| Paso | Qué se pide | Por qué ahí |
|---|---|---|
| **1 · Ubicación y tarifa** | País, región, consumo (o subir la boleta) | El país determina moneda y tarifa: sin él nada se puede valorizar |
| **2 · Mi vivienda** | Tipo de inmueble, habitaciones, habitantes | Datos que la persona conoce de memoria, sin esfuerzo |
| **3 · Equipamiento** | Interruptores de los equipos de alto consumo | Preguntas de sí/no, las más rápidas de responder |
| **4 · Detalle** | Contadores de refrigeradores, televisores, lavados | Lo más específico al final, cuando ya hay compromiso |
| **Resultados** | Métricas, recomendaciones, factura imprimible | — |

Ningún paso es obligatorio salvo el país. Un formulario a medias produce un diagnóstico a medias,
nunca un error.

---

## Decisiones de interfaz

**Tres formas de ingresar el consumo, por orden de precisión.** Subir la boleta (se extraen consumo y
tarifa reales), escribir los kWh a mano, o no dar ninguno y dejar que se estime desde el
equipamiento. La tarifa de la boleta tiene prioridad sobre la referencial del país.

**Tarjetas con imagen solo para el tipo de vivienda.** Es la única pregunta donde una imagen desambigua
más rápido que una etiqueta. En el resto del formulario las imágenes serían ruido.

**El interruptor de periodo coincide con la etiqueta del campo.** El campo pide el consumo *mensual*,
así que el valor por defecto es mensual. Venía al revés: quien escribía 250 pensando en su mes
terminaba con 20,8 kWh sin enterarse.

**Los errores tienen sitio propio.** Un fallo de red o un tiempo agotado muestran un aviso con texto,
no solo un cambio de gesto en el asistente. Antes, cuando algo fallaba, Volti ponía cara de error y
el usuario no sabía qué había pasado ni qué hacer.

**Estado de carga explícito.** El botón se deshabilita y anuncia que está calculando. Las peticiones
tienen tiempo máximo (15 s el cálculo, 30 s la boleta): sin él, el navegador esperaba indefinidamente.

---

## Accesibilidad

- **Tipografía Atkinson Hyperlegible**, diseñada para lectura con baja visión. Se sirve desde el
  propio proyecto, no desde una CDN: sin conexión se perdía justo la fuente que no conviene perder.
- Los avisos usan `role="status"` y `role="alert"` para que los lectores de pantalla los anuncien.
- Los mensajes de error acompañan al campo que los provoca, no a un cajón general.
- El asistente Denji es **opcional y desactivable**: la interfaz se puede completar sin él.

---

## Impresión

La vista de impresión (`@media print`) genera un reporte con folio y fecha, desglose por equipo,
diagnóstico y recomendaciones. Es donde aparece la narrativa redactada por el modelo, que en pantalla
no se muestra porque las métricas destacadas ya comunican lo mismo de forma más directa.

---

## Sistema visual

Definido en [`static/css/style.css`](static/css/style.css).

| Rol | Color |
|---|---|
| Principal | `#009E73` verde |
| Secundario | `#2F80ED` azul |
| Atención | `#FFC83D` amarillo |
| Error | `#E53E3E` |
| Texto | `#333333` |
| Fondo | `#F8F9F4` |

El verde y el azul son distinguibles por la mayoría de los tipos de daltonismo, y ningún estado se
comunica solo por color: siempre hay texto o icono acompañando.

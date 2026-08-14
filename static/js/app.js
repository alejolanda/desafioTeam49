/* ═══════════════════════════════════════════════════════════
   VólticvS — app.js v9.0  |  BOLETA ENERGÉTICA + RESET TOTAL
   Engine del Wizard, Avatar, Factura de Impresión
   ═══════════════════════════════════════════════════════════ */

'use strict';

let currentStep = 1;
const TOTAL_STEPS = 4;
let _paisesCache = null;
const PAIS_DEFAULT = 'CL';

/* ── Todos los contadores arrancan en 0 al iniciar/resetear ── */
const COUNTER_ZEROS = {
  inputDormitorios: 0,
  inputVentanas:    0,
  inputMayores:     0,
  inputMenores:     0,
  lavadoFrecuencia: 0,
  refrigerador:     0,
  freezer:          0,
  tv:               0,
  tvFrecuencia:     0
};

/* Lista de equipos con toggle para construir el desglose */
const EQUIPOS_TOGGLE = [
  { id: 'aireAcondicionado',    payloadKey: 'aire_acondicionado',       nombre: 'Aire Acondicionado / Climatización', detalle: 'Equipos de refrigeración o calefacción eléctrica' },
  { id: 'calefaccionElectrica', payloadKey: 'calefaccion_electrica',    nombre: 'Calefacción Eléctrica',              detalle: 'Estufas, radiadores, calefactores' },
  { id: 'aguaCalienteElectrica',payloadKey: 'agua_caliente_electrica',  nombre: 'Calentador de Agua / Termotanque (Eléctrico)', detalle: 'Uso de electricidad para calentar agua' },
  { id: 'secarropasElectrico',  payloadKey: 'secarropas_electrico',     nombre: 'Secarropas Eléctrico',               detalle: 'Secado de prendas' },
  { id: 'hornoElectrico',       payloadKey: 'horno_electrico',          nombre: 'Horno / Anafe Eléctrico',            detalle: 'Cocción eléctrica' }
];

// ── 1. DOM REFERENCES ───────────────────────────────────────
const wizardSteps    = document.querySelectorAll('.wizard-step');
const progressSteps  = document.querySelectorAll('.progress-step');
const progressFill   = document.getElementById('progressFill');
const voltiFrame     = document.getElementById('voltiFrame');
const voltiAvatarImg = document.getElementById('voltiAvatarImg');
const voltiBubble    = document.getElementById('voltiBubble');
const voltiBubbleText= document.getElementById('voltiBubbleText');
const voltiMood      = document.getElementById('voltiMood');
const resultadosSeccion = document.getElementById('resultados');

// ── 2. ESTADOS DE VOLTI ──────────────────────────────────────
// Nota: saludando.png no existe en el proyecto; usamos impatado.png para el inicio.
const VOLTI_ASSETS = {
  1:       '/static/img/volti/impatado.png',
  2:       '/static/img/volti/preguntas.png',
  3:       '/static/img/volti/bien.png',
  4:       '/static/img/volti/bien.png',
  submit:  '/static/img/volti/preguntas.png',
  results: '/static/img/volti/felicidades.png',
  error:   '/static/img/volti/error.png'
};

const VOLTI_MESSAGES = {
  1:       '¡Hola! Soy <strong>Volti</strong>, tu asesor energético. Indícame tu ubicación y tarifa para comenzar.',
  2:       '¡Excelente! Ahora cuéntame sobre tu tipo de vivienda y la cantidad de habitantes.',
  3:       'Selecciona los artefactos de mayor consumo que utilizas en tu hogar.',
  4:       'Indica la frecuencia con la que usas tus electrodomésticos.',
  submit:  '⚡ Calculando tu consumo estimado... ¡Dame un momento!',
  results: '¡Aquí están tus resultados! Revisa las recomendaciones para ahorrar más.',
  error:   'Oops, parece que faltan algunos datos. Por favor, revisa la información.'
};

const VOLTI_MOODS = {
  1: 'Saludando', 2: 'Analizando', 3: 'Atento', 4: 'Entusiasmado',
  submit: 'Calculando', results: 'Celebrando', error: 'Preocupado'
};

// ── 3. AVATAR ────────────────────────────────────────────────
function updateVoltiMessage(key) {
  const message = VOLTI_MESSAGES[key] || VOLTI_MESSAGES[1];
  const imgSrc  = VOLTI_ASSETS[key]   || VOLTI_ASSETS[1];
  const mood    = VOLTI_MOODS[key]    || VOLTI_MOODS[1];

  if (voltiAvatarImg) {
    voltiAvatarImg.style.opacity = '0';
    setTimeout(() => {
      voltiAvatarImg.src = imgSrc;
      voltiAvatarImg.style.opacity = '1';
    }, 150);
  }
  if (voltiFrame) {
    voltiFrame.classList.remove('pop');
    void voltiFrame.offsetWidth;
    voltiFrame.classList.add('pop');
    setTimeout(() => voltiFrame.classList.remove('pop'), 400);
  }
  if (voltiBubble && voltiBubbleText) {
    voltiBubble.classList.remove('pulse');
    void voltiBubble.offsetWidth;
    voltiBubble.classList.add('pulse');
    voltiBubbleText.innerHTML = message;
    setTimeout(() => voltiBubble.classList.remove('pulse'), 450);
  }
  if (voltiMood) voltiMood.textContent = mood;
}

// ── 4. WIZARD Y PROGRESS BAR ─────────────────────────────────
function updateProgressBar() {
  const percent = ((currentStep - 1) / (TOTAL_STEPS - 1)) * 100;
  if (progressFill) progressFill.style.width = percent + '%';

  progressSteps.forEach((step, index) => {
    const stepNum = index + 1;
    step.classList.remove('progress-step--active', 'progress-step--done');
    if (stepNum === currentStep)       step.classList.add('progress-step--active');
    else if (stepNum < currentStep)    step.classList.add('progress-step--done');
  });
}

function showStep(stepNumber) {
  wizardSteps.forEach(step => {
    step.classList.toggle('wizard-step--active', parseInt(step.dataset.step) === stepNumber);
  });
  if (resultadosSeccion) resultadosSeccion.hidden = true;
  updateProgressBar();
  updateVoltiMessage(stepNumber);
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ── 4B. VALIDACIÓN ──────────────────────────────────────────
function clearError(el) {
  if (!el) return;
  el.classList.remove('input-error', 'shake');
  el.parentNode?.querySelector('.error-msg')?.remove();
}

function showError(el, mensaje) {
  if (!el) return;
  el.classList.add('input-error', 'shake');
  let msg = el.parentNode?.querySelector('.error-msg');
  if (!msg && el.parentNode) {
    msg = document.createElement('span');
    msg.className = 'error-msg';
    el.parentNode.appendChild(msg);
  }
  if (msg) msg.textContent = mensaje;
  setTimeout(() => el.classList.remove('shake'), 400);
}

function validarPaso(pasoActual) {
  let valido = true;
  document.querySelector(`.wizard-step[data-step="${pasoActual}"]`)
    ?.querySelectorAll('.input-error').forEach(clearError);

  if (pasoActual === 1) {
    const sel = document.getElementById('pais') || document.getElementById('selectPais');
    if (sel && sel.hasAttribute('required') && !sel.value?.trim()) {
      showError(sel, 'Por favor, selecciona un país.');
      valido = false;
    }
  }
  if (!valido) updateVoltiMessage('error');
  return valido;
}

function nextStep() {
  if (currentStep >= TOTAL_STEPS) return;
  if (!validarPaso(currentStep)) return;
  currentStep++;
  showStep(currentStep);
  saveState();
}

function prevStep() {
  if (currentStep <= 1) return;
  currentStep--;
  showStep(currentStep);
}

// ── 5. INTERACTIVIDAD DE COMPONENTES ────────────────────────
let tipoInmuebleSeleccionado = 'Casa';

document.querySelectorAll('.vivienda-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.vivienda-card').forEach(c => c.classList.remove('vivienda-card--active'));
    card.classList.add('vivienda-card--active');
    tipoInmuebleSeleccionado = card.dataset.value;
  });
});

document.querySelectorAll('.equip-toggle').forEach(toggle => {
  toggle.addEventListener('change', e => {
    e.target.closest('.equip-item')
      ?.classList.toggle('equip-item--on', e.target.checked);
  });
});

document.querySelectorAll('.counter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const input = document.getElementById(btn.dataset.target);
    if (!input) return;
    let val = parseInt(input.value) || 0;
    const min = parseInt(input.min) || 0;
    const max = parseInt(input.max) || 999;
    if (btn.classList.contains('counter-btn--plus') && val < max) val++;
    else if (btn.classList.contains('counter-btn--minus') && val > min) val--;
    input.value = val;
    clearError(input);
  });
});

// ── 6. PAÍSES ────────────────────────────────────────────────
async function cargarPaises() {
  const selectPais = document.getElementById('pais') || document.getElementById('selectPais');
  if (!selectPais) return;
  try {
    const res   = await fetch('/api/paises');
    const paises = await res.json();
    _paisesCache = paises;

    selectPais.innerHTML = '<option value="">Selecciona un país...</option>';
    Object.entries(paises).forEach(([codigo, datos]) => {
      const opt = document.createElement('option');
      opt.value = codigo;
      opt.textContent = `${datos.nombre} (${datos.moneda})`;
      selectPais.appendChild(opt);
    });

    // Siempre aplicar default al iniciar (resetearTodo ya limpió estado)
    selectPais.value = PAIS_DEFAULT;
    actualizarInfoPais(paises, PAIS_DEFAULT);

    selectPais.addEventListener('change', () => {
      actualizarInfoPais(paises, selectPais.value);
      saveState();
    });
  } catch {
    selectPais.innerHTML = '<option value="">No se pudo cargar la lista de países</option>';
  }
}

function actualizarInfoPais(paises, codigo) {
  const datos = paises[codigo];
  if (!datos) return;
  window._monedaActiva     = datos.moneda  || '';
  window._simboloActivo    = datos.simbolo || '';
  window._paisActivo       = codigo;
  window._nombrePaisActivo = datos.nombre  || codigo;

  // Galones para sistema imperial (US, PR), Litros para métrico
  const esImperial = (codigo === 'US' || codigo === 'PR');
  window._flagGalones = esImperial ? 1 : 2;
  window._unidadAgua  = esImperial ? 'Galones' : 'Litros';

  // Actualizar dinámicamente en la UI si hay elementos de moneda o unidades
  document.querySelectorAll('.simbolo-moneda').forEach(el => (el.textContent = window._simboloActivo));
  document.querySelectorAll('.codigo-moneda').forEach(el => (el.textContent = window._monedaActiva));
  document.querySelectorAll('.unidad-agua').forEach(el => (el.textContent = window._unidadAgua));
}

// ════════════════════════════════════════════════════════════
//  ── 7. RESET TOTAL (DOMContentLoaded + Nuevo Cálculo) ──
// ════════════════════════════════════════════════════════════
function resetearTodo() {
  // 1. Limpiar localStorage
  localStorage.removeItem('volticvs_state');

  // 2. Resetear todos los inputs de texto a vacío
  document.querySelectorAll('input[type="text"]').forEach(el => (el.value = ''));

  // 3. Resetear número libre (consumo kWh)
  const inputConsumo = document.getElementById('inputConsumo');
  if (inputConsumo) inputConsumo.value = '';

  // 4. Resetear select de país al default (se aplicará tras cargar países)
  const selectPais = document.getElementById('pais') || document.getElementById('selectPais');
  if (selectPais) {
    selectPais.value = PAIS_DEFAULT;
    if (_paisesCache) actualizarInfoPais(_paisesCache, PAIS_DEFAULT);
  }

  // 5. Toggle anual en ON (flag_anual = 1) por defecto
  const flagAnual = document.getElementById('flagAnual');
  if (flagAnual) {
    flagAnual.checked = true;
    const flagAnualLabel = document.getElementById('flagAnualLabel');
    if (flagAnualLabel) flagAnualLabel.textContent = 'El consumo es anual';
  }

  // 6. TODOS los contadores a CERO
  Object.entries(COUNTER_ZEROS).forEach(([id, val]) => {
    const el = document.getElementById(id);
    if (el) el.value = val;
  });

  // 7. Desmarcar todos los checkboxes excepto flagAnual (marcado en el paso 5)
  document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    if (cb.id !== 'flagAnual') {
      cb.checked = false;
      cb.closest('.equip-item')?.classList.remove('equip-item--on');
    }
  });

  // 8. Restablecer tipo de inmueble a "Casa"
  tipoInmuebleSeleccionado = 'Casa';
  document.querySelectorAll('.vivienda-card').forEach(card => {
    card.classList.toggle('vivienda-card--active', card.dataset.value === 'Casa');
  });

  // 9. Limpiar errores de validación
  document.querySelectorAll('.input-error').forEach(clearError);
  document.querySelectorAll('.error-msg').forEach(el => el.remove());

  // 10. Limpiar estado interno de resultados
  window._lastPayload  = null;
  window._lastResultado = null;

  // 11. Ocultar sección de resultados
  if (resultadosSeccion) {
    resultadosSeccion.hidden = true;
    resultadosSeccion.style.display = '';
  }

  // 12. Volver al Paso 1
  currentStep = 1;
  showStep(1);             // Incluye updateProgressBar() + updateVoltiMessage(1)

  // 13. Scroll al inicio
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── 8. EVENT LISTENERS ───────────────────────────────────────
document.getElementById('btnNext1')?.addEventListener('click', nextStep);
document.getElementById('btnNext2')?.addEventListener('click', nextStep);
document.getElementById('btnNext3')?.addEventListener('click', nextStep);
document.getElementById('btnPrev2')?.addEventListener('click', prevStep);
document.getElementById('btnPrev3')?.addEventListener('click', prevStep);
document.getElementById('btnPrev4')?.addEventListener('click', prevStep);

document.getElementById('btnNuevoCalculo')?.addEventListener('click', resetearTodo);
document.getElementById('flagAnual')?.addEventListener('change', e => {
  const label = document.getElementById('flagAnualLabel');
  if (label) label.textContent = e.target.checked ? 'El consumo es anual' : 'El consumo es mensual';
});

// ── 8A. SUBMIT: CALCULAR CONSUMO ─────────────────────────────
document.getElementById('btnSubmit')?.addEventListener('click', async () => {
  updateVoltiMessage('submit');

  const v = id => document.getElementById(id);
  const horasDiariasTv = parseFloat(v('tvFrecuencia')?.value) || 0;

  const datosPayload = {
    consumo:               parseInt(v('inputConsumo')?.value || '0') || 0,
    consumo_kwh:           parseInt(v('inputConsumo')?.value || '0') || 0,
    flag_anual:            v('flagAnual')?.checked ? 1 : 0,
    pais:                  v('pais')?.value || v('selectPais')?.value || window._paisActivo || 'CL',
    estado_provincia:      v('selectProvincia')?.value || '',
    dormitorios:           parseInt(v('inputDormitorios')?.value) || 0,
    ventanas:              parseInt(v('inputVentanas')?.value) || 0,
    habitantes_mayores:    parseInt(v('inputMayores')?.value) || 0,
    habitantes_menores:    parseInt(v('inputMenores')?.value) || 0,
    aire_acondicionado:    v('aireAcondicionado')?.checked ? 1 : 0,
    calefaccion_electrica: v('calefaccionElectrica')?.checked ? 1 : 0,
    agua_caliente_electrica: v('aguaCalienteElectrica')?.checked ? 1 : 0,
    secarropas_electrico:  v('secarropasElectrico')?.checked ? 1 : 0,
    horno_electrico:       v('hornoElectrico')?.checked ? 1 : 0,
    agua_caliente_tamano:  0,
    flag_galones:          window._flagGalones || 2,
    lavado_frecuencia:     parseInt(v('lavadoFrecuencia')?.value) || 0,
    refrigerador:          parseInt(v('refrigerador')?.value) || 0,
    freezer:               parseInt(v('freezer')?.value) || 0,
    luces_exterior:        0,
    luces_interior:        0,
    tv:                    parseInt(v('tv')?.value) || 0,
    tv_frecuencia:         horasDiariasTv * 7,
    tipo_inmueble:         tipoInmuebleSeleccionado
  };

  window._lastPayload = datosPayload;
  console.log('Payload enviado:', datosPayload);

  try {
    let res = await fetch('/api/analisis-energetico', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datosPayload)
    });
    if (!res.ok) res = await fetch('/api/calcular', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datosPayload)
    });
    if (!res.ok) res = await fetch('/calcular', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datosPayload)
    });

    if (res.ok) {
      const resultado = await res.json();
      mostrarResultados(resultado, datosPayload);
      updateVoltiMessage('results');
    } else {
      updateVoltiMessage('error');
    }
  } catch (e) {
    console.error('Error conectando con la API:', e);
    updateVoltiMessage('error');
  }
});

// ── 8B. MOSTRAR RESULTADOS EN DOM ────────────────────────────
function mostrarResultados(res, payload) {
  if (resultadosSeccion) resultadosSeccion.hidden = false;

  // ── Moneda: priorizar lo que devuelve el backend (ya calculado por tarifa) ──
  const simbolo = res.simbolo_moneda || res.simbolo || window._simboloActivo || '$';
  const moneda  = res.moneda         || window._monedaActiva || '';

  // ── Valores numéricos con cadena de fallback robusta ──
  const consumoVal = res.consumo_kwh
    ?? res.consumo_mensual_estimado
    ?? res.total_kwh_mes
    ?? payload?.consumo_kwh
    ?? payload?.consumo
    ?? 0;

  const costoVal = res.costo_estimado
    ?? res.costo_estimado_mensual
    ?? res.total_clp_mes
    ?? 0;

  const ahorroVal = res.ahorro_estimado
    ?? res.ahorro_potencial_clp_mes
    ?? res.ahorro_potencial
    ?? (typeof costoVal === 'number' ? Math.round(costoVal * 0.2) : 0);

  const categoria = res.categoria || 'Moderado';
  let narrativa = (res.narrativa || '').replace(/CLP/g, moneda || window._monedaActiva || '');
  if (!narrativa) {
    narrativa = `Categoría: ${categoria}. Consumo estimado: ${consumoVal} kWh, costo aprox. ${simbolo} ${fmt(costoVal)} ${moneda}.`;
  }

  const fmt = val => (typeof val === 'number' ? val.toLocaleString('es') : val);
  const sufijo = moneda ? ` ${moneda}` : '';

  // ── Narrativa LLM (oculta en pantalla, disponible para imprimir) ──
  const narrativaEl = document.getElementById('narrativa');
  if (narrativaEl) narrativaEl.textContent = narrativa;

  // ── Tarjetas de resultados (con moneda correcta) ──
  const el = id => document.getElementById(id);
  if (el('totalKwh'))  el('totalKwh').textContent  = `${consumoVal} kWh`;
  if (el('totalClp'))  el('totalClp').textContent  = `${simbolo} ${fmt(costoVal)}${sufijo}`.trim();
  if (el('ahorroClp')) el('ahorroClp').textContent = `${simbolo} ${fmt(ahorroVal)}${sufijo}`.trim();

  // ── 3 Métricas de resumen visual ──
  const ahorroAnual   = typeof ahorroVal === 'number' ? Math.round(ahorroVal * 12) : 0;
  const primeraAccion = (res.recomendaciones || [])[0]
    || 'Desconecta artefactos en stand-by para reducir tu factura.';

  if (el('metricaKwh'))    el('metricaKwh').textContent    = `${consumoVal} kWh`;
  if (el('metricaAhorro')) el('metricaAhorro').textContent = `${simbolo} ${fmt(ahorroAnual)}${sufijo}`.trim();
  if (el('metricaAccion')) el('metricaAccion').textContent = primeraAccion;

  // ── Lista de recomendaciones ──
  const lista = el('listaRecomendaciones');
  if (lista) {
    lista.innerHTML = '';
    (res.recomendaciones || ['Revisa los artefactos conectados en horario pico.']).forEach(r => {
      const li = document.createElement('li');
      li.textContent = r;
      lista.appendChild(li);
    });
  }

  // Guardar estado para la factura
  window._lastResultado = {
    res, consumoVal, costoVal, ahorroVal, ahorroAnual,
    categoria, simbolo, moneda, narrativa
  };

  resultadosSeccion?.scrollIntoView({ behavior: 'smooth' });
}

// ── 8C. FACTURA IMPRIMIBLE ───────────────────────────────────

/** Genera un folio único tipo #VOLT-2026-XXXX */
function generarFolio() {
  const rnd = Math.floor(1000 + Math.random() * 9000);
  return `#VOLT-2026-${rnd}`;
}

/** Construye las filas de desglose desde el payload */
function construirFilasDesglose(payload) {
  const filas = [];
  const addFila = (concepto, cantidad, estado = 'Activo') => filas.push({ concepto, cantidad, estado });

  if (payload.consumo_kwh > 0) addFila('Consumo Declarado', `${payload.consumo_kwh} kWh/mes`, 'Base');
  if (payload.refrigerador > 0) addFila('Refrigerador / Heladera', `${payload.refrigerador} unidad(es)`, 'Activo');
  if (payload.freezer > 0) addFila('Freezer / Congelador', `${payload.freezer} unidad(es)`, 'Activo');
  if (payload.tv > 0) {
    const hDiarias = payload.tv_frecuencia ? (payload.tv_frecuencia / 7).toFixed(1).replace('.0', '') : 0;
    addFila('Televisor', `${payload.tv} TV · ${hDiarias} h/día`, 'Activo');
  }
  if (payload.lavado_frecuencia > 0) addFila('Lavadora', `${payload.lavado_frecuencia} lavados/sem`, 'Activo');

  EQUIPOS_TOGGLE.forEach(({ payloadKey, nombre, detalle }) => {
    if (payload[payloadKey] === 1) addFila(nombre, detalle, 'Activo');
  });

  return filas;
}

/** Puebla el template #factura-print-template y llama window.print() */
function poblarFactura() {
  const payload  = window._lastPayload   || {};
  const resultado = window._lastResultado || {};
  const { res = {}, consumoVal = 0, costoVal = 0, ahorroVal = 0, categoria = '—', simbolo = '$', moneda = '', narrativa = '' } = resultado;

  const el  = id => document.getElementById(id);
  const fmt = val => (typeof val === 'number' ? val.toLocaleString() : val);

  if (el('fptFolio')) el('fptFolio').textContent = generarFolio();
  if (el('fptFecha')) {
    const ahora = new Date();
    el('fptFecha').textContent = 'Fecha: ' + ahora.toLocaleDateString('es-ES', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
  }

  // ── Barra de cliente ──
  if (el('fptPais'))         el('fptPais').textContent        = window._nombrePaisActivo || payload.pais || '—';
  if (el('fptRegion'))       el('fptRegion').textContent      = payload.estado_provincia || '(sin especificar)';
  if (el('fptInmuebleBadge')) el('fptInmuebleBadge').textContent = tipoInmuebleSeleccionado || '—';
  const totalHab = (parseInt(payload.habitantes_mayores) || 0) + (parseInt(payload.habitantes_menores) || 0);
  if (el('fptHabBadge'))     el('fptHabBadge').textContent    = `${totalHab} personas`;

  // ── Sección 1: Inmueble ──
  if (el('fptTipoVivienda'))   el('fptTipoVivienda').textContent   = tipoInmuebleSeleccionado || '—';
  if (el('fptDormitorios'))    el('fptDormitorios').textContent    = payload.dormitorios ?? '—';
  if (el('fptVentanas'))       el('fptVentanas').textContent       = payload.ventanas ?? '—';
  if (el('fptAdultosMenores')) el('fptAdultosMenores').textContent =
    `${payload.habitantes_mayores ?? 0} adultos / ${payload.habitantes_menores ?? 0} menores`;

  // ── Sección 2: Desglose dinámico ──
  const tbody = el('fptDesglose');
  if (tbody) {
    tbody.innerHTML = '';
    const filas = construirFilasDesglose(payload);

    if (filas.length === 0) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td colspan="3" style="text-align:center;font-style:italic;">Sin equipos declarados</td>';
      tbody.appendChild(tr);
    } else {
      filas.forEach(({ concepto, cantidad, estado }) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${concepto}</td>
          <td>${cantidad}</td>
          <td><span class="fpt-estado-activo">${estado}</span></td>
        `;
        tbody.appendChild(tr);
      });
    }
  }

  // ── Sección 3: Totales ──
  const sufijo = moneda ? ` ${moneda}` : '';
  if (el('fptCategoria')) el('fptCategoria').textContent = categoria;
  if (el('fptKwh'))       el('fptKwh').textContent       = `${consumoVal} kWh`;
  if (el('fptCosto'))     el('fptCosto').textContent     = `${simbolo} ${fmt(costoVal)}${sufijo}`;
  if (el('fptAhorro'))    el('fptAhorro').textContent    = `${simbolo} ${fmt(ahorroVal)}${sufijo}`;

  // ── Recomendaciones ──
  const recsList = el('fptRecs');
  if (recsList) {
    recsList.innerHTML = '';
    const recs = res.recomendaciones?.length
      ? res.recomendaciones
      : ['Aplica buenas prácticas de consumo para reducir tu huella energética y ahorrar dinero.'];
    recs.forEach(r => {
      const li = document.createElement('li');
      li.textContent = r;
      recsList.appendChild(li);
    });
  }
}

// ── 8D. BOTÓN IMPRIMIR ───────────────────────────────────────
document.getElementById('btnImprimir')?.addEventListener('click', () => {
  poblarFactura();
  setTimeout(() => window.print(), 150);
});

// ── 9. PERSISTENCIA (ENTRE PASOS) ────────────────────────────
function saveState() {
  const state = {
    step: currentStep,
    tipoInmueble: tipoInmuebleSeleccionado,
    inputs: {}, checkboxes: {}
  };
  document.querySelectorAll('input[type="text"], input[type="number"], select').forEach(el => {
    if (el.id) state.inputs[el.id] = el.value;
  });
  document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    if (cb.id) state.checkboxes[cb.id] = cb.checked;
  });
  localStorage.setItem('volticvs_state', JSON.stringify(state));
}

// Autoguardado y limpieza de errores en tiempo real
document.querySelectorAll('input, select, textarea').forEach(el => {
  const handler = e => { saveState(); clearError(e.target); };
  el.addEventListener('change', handler);
  el.addEventListener('input', handler);
});
document.querySelectorAll('.vivienda-card, .counter-btn').forEach(el => {
  el.addEventListener('click', () => setTimeout(saveState, 50));
});

// ── 10. INICIALIZACIÓN ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  /* Siempre arrancar desde cero en cada carga de página */
  resetearTodo();

  /* Cargar países (establece el select al país default) */
  await cargarPaises();

  /* Mostrar el paso 1 con el avatar de bienvenida */
  currentStep = 1;
  showStep(1);
});
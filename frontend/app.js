/* =============================================================================
   ZeroMerma AI — Frontend (Vanilla JS)
   Archivo: /frontend/app.js

   Resiliencia dual:
     1. Modo conectado: cada acción llama a la API (/api/*) del backend FastAPI.
     2. Modo demo autónoma: si no hay servidor (por ejemplo, index.html abierto con
        doble clic), usa window.DATOS_DEMO, respuestas precalculadas por el mismo
        backend y modelo (scripts/exportar_datos_demo.py). La página nunca se rompe.

   Todos los datos son SIMULADOS.
   ============================================================================= */
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Utilidades
  // ---------------------------------------------------------------------------
  const $ = (sel, raiz = document) => raiz.querySelector(sel);
  const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));
  const DEMO = window.DATOS_DEMO || null;
  const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
  const COLORES = { slate900: '#0f172a', slate500: '#64748b', slate300: '#cbd5e1', slate200: '#e2e8f0',
                    emerald600: '#059669', emerald400: '#34d399' };

  const num = (n, d = 1) => new Intl.NumberFormat('es-MX', { minimumFractionDigits: d, maximumFractionDigits: d }).format(n);
  const mxn = (n) => '$' + new Intl.NumberFormat('es-MX', { maximumFractionDigits: 0 }).format(Math.round(n)) + ' MXN';
  const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const iconos = () => { if (window.lucide) window.lucide.createIcons(); };
  const hayChart = () => typeof window.Chart !== 'undefined';
  const espera = (ms) => new Promise((r) => setTimeout(r, ms));

  function hora12(h) {
    const hh = Math.floor(h), mm = Math.round((h - hh) * 60);
    return `${hh % 12 === 0 ? 12 : hh % 12}:${String(mm).padStart(2, '0')} ${hh >= 12 ? 'PM' : 'AM'}`;
  }
  const hora24 = (h) => `${String(Math.floor(h)).padStart(2, '0')}:${String(Math.round((h % 1) * 60)).padStart(2, '0')}`;
  const textoAHora = (t) => { const [h, m] = t.split(':').map(Number); return h + m / 60; };

  function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  function toast(mensaje, tipo = 'ok') {
    const el = document.createElement('div');
    el.setAttribute('role', 'status');
    el.className = 'toast-in max-w-sm rounded-xl shadow-xl px-4 py-3 text-sm font-medium text-white ' +
      (tipo === 'ok' ? 'bg-emerald-600' : tipo === 'aviso' ? 'bg-amber-600' : 'bg-rose-600');
    el.textContent = mensaje;
    $('#toasts').appendChild(el);
    setTimeout(() => { el.style.transition = 'opacity .3s'; el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 4500);
  }

  function mostrarError(id, mensaje) {
    const el = $(id);
    el.textContent = mensaje || '';
    el.classList.toggle('hidden', !mensaje);
  }

  // ---------------------------------------------------------------------------
  // Capa de conexión: API real con respaldo local automático
  // ---------------------------------------------------------------------------
  class SinServidor extends Error {}
  class ErrorApi extends Error {
    constructor(estado, detalle) { super(detalle); this.estado = estado; }
  }

  const conexion = { modo: 'detectando' };   // 'api' | 'demo'

  function pintarConexion() {
    const boton = $('#estadoConexion');
    const punto = boton.querySelector('span');
    const texto = boton.querySelectorAll('span')[1];
    if (conexion.modo === 'api') {
      boton.className = 'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium ring-1 ring-emerald-500/50 text-emerald-300';
      punto.className = 'h-2 w-2 rounded-full bg-emerald-400';
      texto.textContent = 'API conectada';
    } else if (conexion.modo === 'demo') {
      boton.className = 'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium ring-1 ring-amber-500/50 text-amber-300';
      punto.className = 'h-2 w-2 rounded-full bg-amber-400';
      texto.textContent = 'Modo demo autónoma';
    }
    $('#bannerDemo').classList.toggle('hidden', conexion.modo !== 'demo');
  }

  function activarDemo(motivo) {
    if (conexion.modo === 'demo') return;
    conexion.modo = 'demo';
    if (!DEMO) $('#bannerDemoTexto').textContent = 'No hay servidor ni datos de respaldo (falta datos_demo.js). Inicia el backend con: python backend/main.py';
    pintarConexion();
    if (motivo) toast(motivo, 'aviso');
  }

  async function detectarServidor() {
    if (location.protocol === 'file:') { activarDemo(); return; }
    const control = new AbortController();
    const temporizador = setTimeout(() => control.abort(), 2500);
    try {
      const r = await fetch('/api/salud', { signal: control.signal });
      conexion.modo = r.ok ? 'api' : 'demo';
    } catch (_) {
      conexion.modo = 'demo';
    } finally {
      clearTimeout(temporizador);
    }
    pintarConexion();
  }

  async function api(ruta, opciones = {}) {
    if (conexion.modo === 'demo') throw new SinServidor();
    let r;
    try {
      r = await fetch(ruta, { headers: { 'Content-Type': 'application/json' }, ...opciones });
    } catch (_) {
      activarDemo('Se perdió la conexión con el servidor: se usa el modo demo autónoma.');
      throw new SinServidor();
    }
    if (!r.ok) {
      const cuerpo = await r.json().catch(() => ({}));
      const detalle = Array.isArray(cuerpo.detail) ? cuerpo.detail.map((d) => d.msg).join('; ') : cuerpo.detail;
      if (r.status === 503) { activarDemo('El servidor no tiene datos listos: se usa el modo demo autónoma.'); throw new SinServidor(); }
      throw new ErrorApi(r.status, detalle || `Error ${r.status}`);
    }
    return r.json();
  }
  const post = (ruta, cuerpo) => api(ruta, { method: 'POST', body: JSON.stringify(cuerpo) });

  /** Ejecuta la llamada a la API; si no hay servidor, el respaldo local. Devuelve { datos, fuente }. */
  async function conRespaldo(llamada, respaldo) {
    try {
      return { datos: await llamada(), fuente: 'api' };
    } catch (err) {
      if (!(err instanceof SinServidor)) throw err;
      if (!DEMO) throw new Error('Sin servidor y sin datos de respaldo. Inicia el backend: python backend/main.py');
      return { datos: await respaldo(), fuente: 'demo' };
    }
  }

  // ---------------------------------------------------------------------------
  // Respaldos locales (modo demo): reproducen las respuestas de la API
  // ---------------------------------------------------------------------------
  const local = {
    catalogo: () => DEMO.catalogo,

    predecir(e) {
      const clave = `${e.dia_semana}${+e.es_quincena}${+e.lluvia}${+e.evento}${+e.temporada_vacacional}`;
      const fila = DEMO.predicciones[clave];
      const idx = DEMO.insumos.findIndex((i) => i.clave === e.insumo);
      if (!fila || idx < 0) throw new Error('Combinación no disponible en el modo demo.');
      const ins = DEMO.insumos[idx];
      const demanda = Math.max(0, fila[idx + 1]);
      const compra = demanda * (1 + e.margen_seguridad);
      const tradicional = ins.tradicional_por_dia[e.dia_semana];
      const mermaTrad = Math.max(0, tradicional - demanda) * ins.factor_caducidad;
      const mermaZm = Math.max(0, compra - demanda) * ins.factor_caducidad;
      const evitada = Math.max(0, mermaTrad - mermaZm);
      return {
        insumo: { clave: ins.clave, nombre: ins.nombre, unidad: ins.unidad },
        clientes_estimados: Math.round(fila[0]),
        demanda_base: demanda, margen_seguridad: e.margen_seguridad, margen_recomendado: ins.margen_recomendado,
        compra_sugerida: compra, unidad: ins.unidad, costo_estimado_mxn: compra * ins.precio,
        compra_tradicional: tradicional, costo_tradicional_mxn: tradicional * ins.precio,
        merma_evitada: evitada, merma_evitada_mxn: evitada * ins.precio,
        riesgo_desabasto: e.margen_seguridad < 0.04,
        importancia_variables: DEMO.importancias, es_simulado: true,
      };
    },

    inventario: () => DEMO.inventario,

    async optimizar() {
      await espera(800);
      return { ...DEMO.optimizar, modo: 'fallback',
               motivo_fallback: 'Modo demo sin servidor: promociones precalculadas por las reglas locales del backend.' };
    },

    alerta(e) {
      const A = DEMO.alerta;
      const p = A.platillos[e.platillo];
      const h = textoAHora(e.hora_actual);
      const esperado = p.ventas_por_dia[(new Date().getDay() + 6) % 7];
      const preparadas = e.porciones_preparadas ?? Math.ceil(esperado * A.colchon);
      const f = Math.pow(Math.min(Math.max((h - A.apertura) / (A.cierre - A.apertura), 0), 1), A.exponente);
      const factor = A.ritmos[e.ritmo_ventas];
      const vendidas = Math.round(esperado * factor * f);
      const cierre = Math.max(vendidas, Math.round(esperado * factor));
      const sobrante = Math.max(0, preparadas - cierre);
      let agotamiento = null;
      if (cierre > preparadas && esperado * factor > 0) {
        const avance = Math.pow(preparadas / (esperado * factor), 1 / A.exponente);
        agotamiento = hora24(A.apertura + avance * (A.cierre - A.apertura));
      }
      const r = {
        modo: 'fallback', motivo_fallback: 'Modo demo sin servidor: cálculo local con los mismos supuestos.',
        platillo: { clave: e.platillo, nombre: p.nombre }, hora_actual: e.hora_actual, ritmo: e.ritmo_ventas,
        factor_ritmo: factor, confianza: f < 0.35 ? 'baja' : f < 0.6 ? 'media' : 'alta',
        proyeccion: { porciones_preparadas: preparadas, vendidas_hasta_ahora: vendidas,
                      ventas_esperadas_al_cierre: cierre, porciones_sobrantes: sobrante, hora_agotamiento_estimada: agotamiento },
        alerta_activa: sobrante >= A.sobrante_minimo, ficha: null, alerta_id: null, es_simulado: true,
      };
      if (r.alerta_activa && e.generar_ficha) {
        let inicio = Math.ceil((h + 1.5) * 4 - 1e-9) / 4;
        let fin = Math.min(Math.max(A.cierre - 1.5, inicio + 1), A.cierre - 0.25);
        if (fin <= inicio) { inicio = Math.ceil((h + 0.25) * 4 - 1e-9) / 4; fin = A.cierre; }
        const nota = p.refrigerar
          ? 'Mantener en refrigeración a 4 °C o menos hasta la entrega; transportar en contenedor cerrado y consumir el mismo día. No recalentar más de una vez.'
          : 'Conservar tapado y en lugar fresco; consumir el mismo día.';
        const kg = Math.round(sobrante * p.peso_porcion_kg * 10) / 10;
        r.ficha = {
          alimento: `${sobrante} porciones de ${p.nombre}`, platillo: p.nombre, porciones: sobrante, cantidad_aprox_kg: kg,
          ventana_recoleccion: { inicio: hora24(inicio), fin: hora24(fin), horas_antes_del_cierre: A.cierre - inicio },
          nota_inocuidad: nota, destinatario_sugerido: 'Comedor comunitario / Red Campus',
          mensaje: `Hola, somos Cafetería La Esquina. Hoy tendremos ${sobrante} porciones de ${p.nombre} (aprox. ${kg} kg) ` +
                   `disponibles para donación. Pueden recogerlas entre ${hora24(inicio)} y ${hora24(fin)}. ${nota}`,
        };
      }
      return r;
    },

    auditoria(insumo) {
      const a = DEMO.auditoria;
      const s = a.por_insumo[insumo] || a.por_insumo.pollo;
      return { insumo: s.insumo, serie: s.serie, periodo: a.periodo, totales: a.totales, metodologia: a.metodologia, es_simulado: true };
    },
  };

  // ---------------------------------------------------------------------------
  // Navegación por pestañas
  // ---------------------------------------------------------------------------
  const graficas = { importancia: null, auditoria: null };
  const cargado = { rescate: false, alerta: false, auditoria: false };

  function mostrarVista(nombre) {
    $$('[role="tab"]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === nombre)));
    $$('[data-vista]').forEach((v) => v.classList.toggle('hidden', v.id !== `vista-${nombre}`));
    try { history.replaceState(null, '', `#${nombre}`); } catch (_) { /* file:// u otros */ }
    // Las gráficas se dibujan cuando su contenedor es visible (Chart.js mide el canvas).
    requestAnimationFrame(() => {
      if (nombre === 'planeador' && graficas.importancia) graficas.importancia.resize();
      if (nombre === 'rescate' && !cargado.rescate) { cargado.rescate = true; cargarInventario(); }
      if (nombre === 'alerta' && !cargado.alerta) { cargado.alerta = true; actualizarAlerta(); }
      if (nombre === 'auditoria') { if (!cargado.auditoria) { cargado.auditoria = true; cargarAuditoria(); } else if (graficas.auditoria) graficas.auditoria.resize(); }
    });
  }
  $$('[role="tab"]').forEach((b) => b.addEventListener('click', () => mostrarVista(b.dataset.tab)));

  // ---------------------------------------------------------------------------
  // Catálogo (llena los selectores)
  // ---------------------------------------------------------------------------
  async function cargarCatalogo() {
    const { datos } = await conRespaldo(() => api('/api/catalogo'), local.catalogo);
    const grupos = {};
    datos.insumos.forEach((i) => { (grupos[i.categoria] = grupos[i.categoria] || []).push(i); });
    const opcionesInsumo = Object.keys(grupos).sort().map((cat) =>
      `<optgroup label="${esc(cat[0].toUpperCase() + cat.slice(1))}">` +
      grupos[cat].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
        .map((i) => `<option value="${esc(i.clave)}">${esc(i.nombre)} (${esc(i.unidad)})</option>`).join('') +
      '</optgroup>').join('');
    $('#insumo').innerHTML = opcionesInsumo;
    $('#insumoAuditoria').innerHTML = opcionesInsumo;
    $('#insumo').value = 'pollo';
    $('#insumoAuditoria').value = 'pollo';

    const platos = datos.platillos.filter((p) => !['bebida'].includes(p.categoria))
      .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
    $('#platilloAlerta').innerHTML = platos.map((p) => `<option value="${esc(p.clave)}">${esc(p.nombre)}</option>`).join('');
    $('#platilloAlerta').value = 'enchiladas_suizas';
  }

  // ---------------------------------------------------------------------------
  // VISTA 1 · Planeador de compras
  // ---------------------------------------------------------------------------
  const ESCENARIOS = {
    quincena: { dia: 4, quincena: true, lluvia: true, evento: false, vacaciones: false },
    martes:   { dia: 1, quincena: false, lluvia: false, evento: false, vacaciones: false },
    baja:     { dia: 0, quincena: false, lluvia: false, evento: false, vacaciones: true },
  };

  function aplicarEscenario() {
    const e = ESCENARIOS[$('#escenario').value];
    if (!e) return;
    $('#dia').value = String(e.dia);
    ['quincena', 'lluvia', 'evento', 'vacaciones'].forEach((k) => { $('#' + k).checked = e[k]; });
  }

  function marcarPersonalizado() {
    const actual = { dia: +$('#dia').value, quincena: $('#quincena').checked, lluvia: $('#lluvia').checked,
                     evento: $('#evento').checked, vacaciones: $('#vacaciones').checked };
    const coincide = Object.entries(ESCENARIOS).find(([, e]) => Object.keys(e).every((k) => e[k] === actual[k]));
    $('#escenario').value = coincide ? coincide[0] : 'personalizado';
  }

  let ultimoPlan = 0;
  async function actualizarPlan() {
    const margen = Number($('#margen').value) / 100;
    $('#margenEtiqueta').textContent = `${$('#margen').value}%`;
    $('#margenEtiqueta').className = 'tabular text-sm font-semibold px-2 py-0.5 rounded-md ' +
      (margen < 0.04 ? 'bg-rose-50 text-rose-700' : 'bg-emerald-50 text-emerald-700');
    $('#bannerDesabasto').classList.toggle('hidden', margen >= 0.04);

    const entrada = {
      insumo: $('#insumo').value, dia_semana: Number($('#dia').value),
      es_quincena: $('#quincena').checked, lluvia: $('#lluvia').checked, evento: $('#evento').checked,
      temporada_vacacional: $('#vacaciones').checked, margen_seguridad: margen,
    };
    if (!entrada.insumo) return;
    const turno = ++ultimoPlan;  // descarta respuestas que lleguen fuera de orden
    try {
      const { datos: r, fuente } = await conRespaldo(() => post('/api/predecir', entrada), () => local.predecir(entrada));
      if (turno !== ultimoPlan) return;
      mostrarError('#errorPlaneador', '');
      pintarPlan(r, fuente);
    } catch (err) {
      if (turno === ultimoPlan) mostrarError('#errorPlaneador', `No se pudo calcular la predicción: ${err.message}`);
    }
  }
  const actualizarPlanPronto = debounce(actualizarPlan, 120);

  function pintarPlan(r, fuente) {
    const u = r.unidad;
    $('#kpiClientes').textContent = `${r.clientes_estimados} clientes`;
    $('#kpiClientesSub').textContent = `${DIAS[Number($('#dia').value)]} · predicción del modelo`;
    $('#kpiCompra').textContent = `${num(r.compra_sugerida)} ${u}`;
    $('#kpiCompraSub').textContent = `Demanda ${num(r.demanda_base)} ${u} × (1 + ${Math.round(r.margen_seguridad * 100)}%)`;
    $('#kpiCosto').textContent = mxn(r.costo_estimado_mxn);
    $('#kpiCostoSub').textContent = `Compra habitual: ${num(r.compra_tradicional)} ${u} · ${mxn(r.costo_tradicional_mxn)}`;
    $('#kpiMerma').textContent = `${num(r.merma_evitada, 2)} ${u}`;
    $('#kpiMermaSub').textContent = r.merma_evitada > 0
      ? `${mxn(r.merma_evitada_mxn)} que no se tiran`
      : 'La compra habitual no deja sobrante que caduque este día.';

    const rec = Math.round(r.margen_recomendado * 1000) / 10;
    $('#margenRecomendado').innerHTML =
      `Margen recomendado para ${esc(r.insumo.nombre.toLowerCase())}: <strong>${num(rec)}%</strong> (cubre 9 de cada 10 días). ` +
      `<button type="button" id="usarRecomendado" class="text-emerald-700 underline font-medium">Usar</button>`;
    $('#usarRecomendado').addEventListener('click', () => { $('#margen').value = String(Math.round(rec)); actualizarPlan(); });

    $('#fuentePlaneador').innerHTML = fuente === 'api'
      ? '<i data-lucide="cpu" class="w-3.5 h-3.5"></i> API · Random Forest en vivo'
      : '<i data-lucide="hard-drive" class="w-3.5 h-3.5"></i> Demo · predicción precalculada del mismo modelo';
    iconos();
    pintarImportancia(r.importancia_variables);
  }

  function pintarImportancia(lista) {
    if (!hayChart()) return;
    const etiquetas = lista.map((i) => i.nombre);
    const valores = lista.map((i) => i.porcentaje);
    const colores = valores.map((_, k) => (k === 0 ? COLORES.emerald600 : COLORES.emerald400));
    if (graficas.importancia) {
      Object.assign(graficas.importancia.data, { labels: etiquetas });
      Object.assign(graficas.importancia.data.datasets[0], { data: valores, backgroundColor: colores });
      graficas.importancia.update();
      return;
    }
    graficas.importancia = new Chart($('#graficaImportancia'), {
      type: 'bar',
      data: { labels: etiquetas, datasets: [{ label: 'Importancia (%)', data: valores, backgroundColor: colores, borderRadius: 4, barThickness: 22 }] },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${num(c.parsed.x)} % de la importancia total` } } },
        scales: {
          x: { min: 0, max: 100, ticks: { callback: (v) => v + '%', color: COLORES.slate500 }, grid: { color: COLORES.slate200 } },
          y: { ticks: { color: COLORES.slate900 }, grid: { display: false } },
        },
      },
    });
  }

  $('#escenario').addEventListener('change', () => { aplicarEscenario(); actualizarPlan(); });
  $('#margen').addEventListener('input', actualizarPlanPronto);
  $('#insumo').addEventListener('change', actualizarPlan);
  ['#dia', '#quincena', '#lluvia', '#evento', '#vacaciones'].forEach((id) =>
    $(id).addEventListener('change', () => { marcarPersonalizado(); actualizarPlan(); }));

  // ---------------------------------------------------------------------------
  // VISTA 2 · Rescate rentable en menú
  // ---------------------------------------------------------------------------
  const ESTILO_ESTADO = {
    CRITICO:    { clase: 'bg-rose-50 text-rose-700 ring-rose-600/20', punto: 'bg-rose-600', texto: 'Crítico' },
    PRECAUCION: { clase: 'bg-amber-50 text-amber-700 ring-amber-500/30', punto: 'bg-amber-500', texto: 'Precaución' },
    OPTIMO:     { clase: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20', punto: 'bg-emerald-600', texto: 'Óptimo' },
  };
  let inventarioCompleto = [];
  let verTodo = false;

  function textoHoras(h) {
    if (h <= 0) return 'Caducado';
    if (h < 48) return `${num(h)} h`;
    return `${num(h / 24)} días`;
  }

  async function cargarInventario() {
    try {
      const { datos } = await conRespaldo(() => api('/api/inventario'), local.inventario);
      inventarioCompleto = datos.lotes;
      const r = datos.resumen;
      $('#resumenInventario').textContent = `${r.CRITICO} críticos · ${r.PRECAUCION} en precaución · ${r.OPTIMO} óptimos`;
      if (datos.advertencia) toast(datos.advertencia, 'aviso');
      pintarInventario();
    } catch (err) {
      $('#tablaInventario').innerHTML = `<tr><td colspan="5" class="px-5 py-6 text-center text-rose-700">${esc(err.message)}</td></tr>`;
    }
  }

  function pintarInventario() {
    const filas = verTodo ? inventarioCompleto : inventarioCompleto.filter((l) => l.estado !== 'OPTIMO');
    $('#verTodoInventario').textContent = verTodo ? 'Solo por caducar' : `Ver todo (${inventarioCompleto.length})`;
    $('#tablaInventario').innerHTML = filas.map((l) => {
      const e = ESTILO_ESTADO[l.estado];
      return `<tr class="hover:bg-slate-50">
        <td class="px-5 py-3 font-medium">${esc(l.insumo)}</td>
        <td class="px-5 py-3 text-right tabular">${num(l.cantidad)} ${esc(l.unidad)}</td>
        <td class="px-5 py-3 tabular text-slate-600">${textoHoras(l.horas_restantes)}</td>
        <td class="px-5 py-3"><span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ring-1 ${e.clase}">
          <span class="h-1.5 w-1.5 rounded-full ${e.punto}"></span>${e.texto}${l.caducado ? ' · vencido' : ''}</span></td>
        <td class="px-5 py-3 text-right tabular text-slate-600">${mxn(l.valor_mxn)}</td></tr>`;
    }).join('') || '<tr><td colspan="5" class="px-5 py-6 text-center text-slate-400">No hay insumos por caducar.</td></tr>';
  }
  $('#verTodoInventario').addEventListener('click', () => { verTodo = !verTodo; pintarInventario(); });

  $('#botonOptimizar').addEventListener('click', async () => {
    const boton = $('#botonOptimizar');
    boton.disabled = true;
    mostrarError('#errorRescate', '');
    $('#resultadoOptimizar').classList.add('hidden');
    $('#cargandoOptimizar').classList.remove('hidden');
    try {
      const { datos: r } = await conRespaldo(() => post('/api/optimizar-menu', { horas_umbral: 24 }), local.optimizar);
      pintarOptimizacion(r);
    } catch (err) {
      mostrarError('#errorRescate', `No se pudo optimizar el menú: ${err.message}`);
    } finally {
      $('#cargandoOptimizar').classList.add('hidden');
      boton.disabled = false;
    }
  });

  function pintarOptimizacion(r) {
    const esGemini = r.modo === 'gemini';
    const t = r.totales || {};
    $('#modoOptimizar').innerHTML = `
      <div class="rounded-xl border ${esGemini ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-white'} p-4 flex flex-col sm:flex-row sm:items-center gap-3">
        <span class="inline-flex items-center gap-1.5 self-start px-2.5 py-1 rounded-full text-xs font-semibold ${esGemini ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-white'}">
          <i data-lucide="${esGemini ? 'sparkles' : 'list-checks'}" class="w-3.5 h-3.5"></i>${esGemini ? 'Generado con Gemini' : 'Reglas locales (fallback)'}</span>
        <p class="text-sm text-slate-600 flex-1">${esGemini ? 'Gemini eligió platillos y redactó el texto; el backend validó y recalculó todas las cifras.' : esc(r.motivo_fallback || '')}</p>
        <p class="text-sm tabular"><span class="text-slate-500">Insumos críticos:</span> <strong>${mxn(t.valor_critico_total_mxn || 0)}</strong></p>
      </div>`;

    if (!r.estrategias.length) {
      $('#tarjetasEstrategia').innerHTML = `<p class="text-sm text-slate-500">${esc(r.motivo_fallback || 'No hay promociones que sugerir.')}</p>`;
    } else {
      $('#tarjetasEstrategia').innerHTML = r.estrategias.map(tarjetaEstrategia).join('');
    }
    pintarMenuTelefono(r.estrategias);
    $('#resultadoOptimizar').classList.remove('hidden');
    iconos();
  }

  function tarjetaEstrategia(e, k) {
    const max = Math.max(e.perdida_si_se_tira_mxn, e.margen_recuperado_mxn, 1);
    const rescatados = e.insumos_rescatados.map((i) => `${esc(i.nombre)} ${num(i.cantidad, 2)} ${esc(i.unidad)}`).join(' · ');
    return `
      <article class="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 fade-in">
        <p class="text-[11px] uppercase tracking-wide text-slate-400 font-medium">Platillo del menú actual · Estrategia ${k + 1}</p>
        <div class="flex items-start justify-between gap-3">
          <h4 class="text-lg font-semibold">${esc(e.platillo)}</h4>
          <span class="shrink-0 px-2.5 py-1 rounded-lg bg-amber-500 text-white text-sm font-semibold">−${num(e.descuento_pct, 0)}% hoy</span>
        </div>
        <p class="text-sm text-slate-500 mt-1">Precio normal <s>$${num(e.precio_normal_mxn, 0)}</s> → <strong class="text-slate-900">Oferta $${num(e.precio_oferta_mxn, 0)}</strong>
          · costo de insumos $${num(e.costo_insumos_porcion_mxn, 2)} por porción</p>
        <p class="text-sm text-slate-600 mt-2">Meta: <strong>${e.porciones_objetivo} porciones</strong> · rescata ${rescatados}</p>
        <div class="mt-4 space-y-3">
          <div>
            <div class="flex justify-between text-xs mb-1 gap-2"><span class="text-slate-600">Pérdida si se tira a la basura</span><span class="tabular font-semibold text-rose-600">−${mxn(e.perdida_si_se_tira_mxn)}</span></div>
            <div class="h-3 rounded-full bg-slate-100 overflow-hidden"><div class="h-full bg-rose-600 rounded-full" style="width:${(e.perdida_si_se_tira_mxn / max) * 100}%"></div></div>
          </div>
          <div>
            <div class="flex justify-between text-xs mb-1 gap-2"><span class="text-slate-600">Margen recuperado con la promoción</span><span class="tabular font-semibold text-emerald-600">+${mxn(e.margen_recuperado_mxn)}</span></div>
            <div class="h-3 rounded-full bg-slate-100 overflow-hidden"><div class="h-full bg-emerald-600 rounded-full" style="width:${(e.margen_recuperado_mxn / max) * 100}%"></div></div>
          </div>
        </div>
      </article>`;
  }

  function pintarMenuTelefono(estrategias) {
    const especiales = estrategias.map((e) => `
      <div class="rounded-xl bg-white border border-amber-200 p-3 shadow-sm">
        <div class="flex justify-between items-start gap-2">
          <p class="font-semibold text-sm leading-tight">${esc(e.platillo)}</p>
          <div class="text-right shrink-0"><p class="text-[10px] text-slate-400 line-through">$${num(e.precio_normal_mxn, 0)}</p>
            <p class="text-sm font-bold text-emerald-600">$${num(e.precio_oferta_mxn, 0)}</p></div>
        </div>
        <p class="text-[11px] text-slate-500 mt-1 leading-snug">${esc(e.copy_promocional)}</p>
      </div>`).join('');
    $('#menuTelefono').innerHTML = `
      <div class="rounded-xl bg-gradient-to-r from-amber-500 to-rose-600 text-white p-3">
        <p class="font-bold">🔥 Especiales del Chef Hoy</p>
        <p class="text-[11px] opacity-90">Solo hoy, hasta agotar existencias</p>
      </div>
      ${especiales || '<p class="text-xs text-slate-500">Sin especiales hoy.</p>'}
      <p class="text-[10px] text-center text-slate-400 pt-1">♻️ Al pedir un especial ayudas a reducir el desperdicio de alimentos</p>`;
  }

  // ---------------------------------------------------------------------------
  // VISTA 3 · Alerta temprana de excedentes
  // ---------------------------------------------------------------------------
  let ultimaAlerta = 0;
  function entradaAlerta(generarFicha) {
    const prep = $('#preparadas').value.trim();
    return {
      hora_actual: hora24(Number($('#hora').value)), ritmo_ventas: $('#ritmo').value,
      platillo: $('#platilloAlerta').value || 'enchiladas_suizas',
      porciones_preparadas: prep === '' ? null : Math.max(0, Math.round(Number(prep))),
      generar_ficha: generarFicha,
    };
  }

  async function actualizarAlerta() {
    $('#horaEtiqueta').textContent = hora12(Number($('#hora').value));
    $('#panelDespacho').classList.add('hidden');
    const entrada = entradaAlerta(false);
    const turno = ++ultimaAlerta;
    try {
      const { datos: r } = await conRespaldo(() => post('/api/alerta-excedente', entrada), () => local.alerta(entrada));
      if (turno !== ultimaAlerta) return;
      mostrarError('#errorAlerta', '');
      pintarAlerta(r);
    } catch (err) {
      if (turno === ultimaAlerta) mostrarError('#errorAlerta', `No se pudo proyectar: ${err.message}`);
    }
  }
  const actualizarAlertaPronto = debounce(actualizarAlerta, 150);

  function pintarAlerta(r) {
    const p = r.proyeccion;
    $('#tituloAvance').textContent = `Avance de ventas · ${r.platillo.nombre}`;
    $('#vendidasEtiqueta').textContent = `${p.vendidas_hasta_ahora} / ${p.porciones_preparadas}`;
    $('#barraVendidas').style.width = `${Math.min(100, (p.vendidas_hasta_ahora / Math.max(p.porciones_preparadas, 1)) * 100)}%`;
    $('#preparadasEtiqueta').textContent = p.porciones_preparadas;
    $('#cierreEtiqueta').textContent = p.ventas_esperadas_al_cierre;
    $('#sobranteEtiqueta').textContent = p.porciones_sobrantes;
    $('#sobranteEtiqueta').className = 'tabular font-semibold ' + (r.alerta_activa ? 'text-orange-600' : 'text-slate-900');

    let html;
    if (r.alerta_activa) {
      html = `
        <div class="rounded-2xl border border-orange-300 bg-orange-50 p-5 fade-in">
          <div class="flex gap-3 items-start">
            <span class="h-10 w-10 shrink-0 rounded-xl bg-orange-500 text-white grid place-items-center"><i data-lucide="siren" class="w-5 h-5"></i></span>
            <div class="flex-1 min-w-0">
              <p class="text-xs font-semibold uppercase tracking-wide text-orange-700">Alerta preventiva · ${hora12(textoAHora(r.hora_actual))} · confianza ${esc(r.confianza)}</p>
              <p class="mt-1 text-orange-950"><strong>Proyección de cierre:</strong> sobrarán <strong>${p.porciones_sobrantes} porciones</strong> de ${esc(r.platillo.nombre)} que no se venderán antes de las 8:00 PM.</p>
              <p class="mt-1 text-sm text-orange-800">Ritmo de ventas al ${Math.round(r.factor_ritmo * 100)} % de lo habitual. Avisar ahora deja más tiempo para recoger.</p>
              <button id="botonFicha" type="button" class="mt-4 inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-sm font-semibold focus:outline-none focus:ring-4 focus:ring-orange-300 transition disabled:opacity-60">
                📢 Generar Ficha de Rescate Temprano</button>
            </div>
          </div>
        </div>`;
    } else if (p.hora_agotamiento_estimada) {
      html = `
        <div class="rounded-2xl border border-slate-300 bg-white p-5 fade-in flex gap-3 items-start">
          <i data-lucide="flame" class="w-5 h-5 text-rose-600 shrink-0 mt-0.5"></i>
          <div><p class="font-semibold">Alta rotación: se agotaría cerca de las ${hora12(textoAHora(p.hora_agotamiento_estimada))}</p>
            <p class="text-sm text-slate-600 mt-1">Sin excedente proyectado. Si el ritmo sigue, conviene preparar ${p.ventas_esperadas_al_cierre - p.porciones_preparadas} porciones más.</p></div>
        </div>`;
    } else {
      html = `
        <div class="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 fade-in flex gap-3 items-start">
          <i data-lucide="check-circle-2" class="w-5 h-5 text-emerald-600 shrink-0 mt-0.5"></i>
          <div><p class="font-semibold text-emerald-900">Operación dentro de tolerancia</p>
            <p class="text-sm text-emerald-800 mt-1">Sobrarían ${p.porciones_sobrantes} porciones al cierre: se aprovechan como comida del personal. No hace falta aviso.</p></div>
        </div>`;
    }
    $('#estadoAlerta').innerHTML = html;
    const boton = $('#botonFicha');
    if (boton) boton.addEventListener('click', generarFicha);
    iconos();
  }

  async function generarFicha() {
    const boton = $('#botonFicha');
    boton.disabled = true;
    const entrada = entradaAlerta(true);
    try {
      const { datos: r, fuente } = await conRespaldo(() => post('/api/alerta-excedente', entrada), () => local.alerta(entrada));
      if (!r.ficha) { toast('Con estos datos ya no hay excedente suficiente para una ficha.', 'aviso'); return; }
      pintarDespacho(r, fuente);
    } catch (err) {
      mostrarError('#errorAlerta', `No se pudo generar la ficha: ${err.message}`);
    } finally {
      boton.disabled = false;
    }
  }

  function pintarDespacho(r, fuente) {
    const f = r.ficha;
    const v = f.ventana_recoleccion;
    const panel = $('#panelDespacho');
    panel.innerHTML = `
      <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden fade-in">
        <div class="px-5 py-3 bg-slate-900 text-white flex items-center justify-between gap-3 flex-wrap">
          <p class="font-semibold flex items-center gap-2"><i data-lucide="clipboard-list" class="w-4 h-4 text-emerald-400"></i> Ficha de Rescate Temprano</p>
          <span class="text-xs text-slate-400">${r.alerta_id ? `Folio #${r.alerta_id}` : 'Folio local (demo)'} · ${r.modo === 'gemini' ? 'mensaje redactado con Gemini' : 'mensaje por plantilla'}</span>
        </div>
        <dl class="divide-y divide-slate-100 text-sm">
          <div class="px-5 py-3 grid sm:grid-cols-3 gap-1"><dt class="text-slate-500 flex items-center gap-2"><i data-lucide="utensils" class="w-4 h-4"></i> Alimento disponible</dt>
            <dd class="sm:col-span-2 font-medium">${esc(f.alimento)} (aprox. ${num(f.cantidad_aprox_kg)} kg)</dd></div>
          <div class="px-5 py-3 grid sm:grid-cols-3 gap-1"><dt class="text-slate-500 flex items-center gap-2"><i data-lucide="truck" class="w-4 h-4"></i> Ventana de recolección</dt>
            <dd class="sm:col-span-2 font-medium">Hoy entre ${hora12(textoAHora(v.inicio))} y ${hora12(textoAHora(v.fin))}
              <span class="text-slate-500 font-normal">(${num(v.horas_antes_del_cierre)} h antes del cierre)</span></dd></div>
          <div class="px-5 py-3 grid sm:grid-cols-3 gap-1"><dt class="text-slate-500 flex items-center gap-2"><i data-lucide="shield-check" class="w-4 h-4"></i> Nota de inocuidad</dt>
            <dd class="sm:col-span-2 font-medium">${esc(f.nota_inocuidad)}</dd></div>
          <div class="px-5 py-3 grid sm:grid-cols-3 gap-1"><dt class="text-slate-500 flex items-center gap-2"><i data-lucide="users" class="w-4 h-4"></i> Destinatario</dt>
            <dd class="sm:col-span-2 font-medium">${esc(f.destinatario_sugerido)}</dd></div>
          <div class="px-5 py-3 grid sm:grid-cols-3 gap-1"><dt class="text-slate-500 flex items-center gap-2"><i data-lucide="message-square" class="w-4 h-4"></i> Mensaje</dt>
            <dd class="sm:col-span-2 text-slate-700 select-all">${esc(f.mensaje)}</dd></div>
        </dl>
        <div class="px-5 py-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row sm:items-center gap-3">
          <button id="botonEnviar" type="button" class="inline-flex justify-center items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold focus:outline-none focus:ring-4 focus:ring-emerald-300 transition disabled:opacity-60">
            <i data-lucide="send" class="w-4 h-4"></i> Enviar Aviso a Comedor Comunitario / Red Campus</button>
          <span class="text-xs text-slate-500">En este prototipo el envío es SIMULADO: queda registrado, no se contacta a nadie.</span>
        </div>
      </div>`;
    panel.classList.remove('hidden');
    iconos();
    $('#botonEnviar').addEventListener('click', async (ev) => {
      const b = ev.currentTarget;
      b.disabled = true;
      try {
        if (fuente === 'api' && r.alerta_id) await api(`/api/alerta-excedente/${r.alerta_id}/enviar`, { method: 'POST' });
        b.innerHTML = '<i data-lucide="check" class="w-4 h-4"></i> Aviso registrado';
        iconos();
        toast('✅ Aviso registrado. Envío SIMULADO: en producción llegaría al comedor comunitario.');
      } catch (err) {
        b.disabled = false;
        toast(`No se pudo registrar el aviso: ${err.message}`, 'error');
      }
    });
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  $('#hora').addEventListener('input', () => { $('#horaEtiqueta').textContent = hora12(Number($('#hora').value)); actualizarAlertaPronto(); });
  ['#ritmo', '#platilloAlerta'].forEach((id) => $(id).addEventListener('change', actualizarAlerta));
  $('#preparadas').addEventListener('input', actualizarAlertaPronto);

  // ---------------------------------------------------------------------------
  // VISTA 4 · Auditoría y backtesting
  // ---------------------------------------------------------------------------
  async function cargarAuditoria() {
    const insumo = $('#insumoAuditoria').value || 'pollo';
    try {
      const { datos: r } = await conRespaldo(() => api(`/api/auditoria?dias=7&insumo=${encodeURIComponent(insumo)}`),
                                              () => local.auditoria(insumo));
      mostrarError('#errorAuditoria', '');
      pintarAuditoria(r);
    } catch (err) {
      mostrarError('#errorAuditoria', `No se pudo cargar la auditoría: ${err.message}`);
    }
  }

  function pintarAuditoria(r) {
    const t = r.totales;
    $('#audReduccion').textContent = `${t.reduccion_merma_pct > 0 ? '+' : ''}${num(t.reduccion_merma_pct)}%`;
    $('#audKg').textContent = `${num(t.merma_evitada_kg)} kg`;
    $('#audMxn').textContent = mxn(t.merma_evitada_mxn);
    $('#audCobertura').textContent = `${num(t.zeromerma.demanda_no_cubierta_pct, 2)}%`;
    $('#audCoberturaSub').textContent = `Compra tradicional: ${num(t.tradicional.demanda_no_cubierta_pct, 2)}% · menos es mejor`;
    $('#periodoAuditoria').textContent =
      `Backtesting del ${r.periodo.desde} al ${r.periodo.hasta}: el modelo se entrenó solo hasta el ${r.periodo.modelo_entrenado_hasta}.`;
    $('#metodologiaAuditoria').textContent = r.metodologia;
    $('#tituloGraficaAuditoria').textContent = `Comparativa diaria: ${r.insumo.nombre} (${r.insumo.unidad}) · margen ${num(r.insumo.margen_aplicado * 100)}%`;
    pintarGraficaAuditoria(r);
  }

  function pintarGraficaAuditoria(r) {
    if (!hayChart()) return;
    const etiquetas = r.serie.map((p) => {
      const d = new Date(p.fecha + 'T12:00:00');
      return `${DIAS[(d.getDay() + 6) % 7].slice(0, 3)} ${d.getDate()}`;
    });
    const u = r.insumo.unidad;
    const series = [
      { type: 'bar', label: 'Compra Tradicional', data: r.serie.map((p) => p.compra_tradicional), backgroundColor: COLORES.slate300, borderRadius: 4, order: 3 },
      { type: 'bar', label: 'Compra Sugerida por ZeroMerma AI', data: r.serie.map((p) => p.compra_sugerida), backgroundColor: COLORES.emerald600, borderRadius: 4, order: 2 },
      { type: 'line', label: 'Demanda Real', data: r.serie.map((p) => p.demanda_real), borderColor: COLORES.slate900, backgroundColor: COLORES.slate900,
        borderWidth: 2, pointRadius: 4, tension: 0.3, order: 1 },
    ];
    if (graficas.auditoria) graficas.auditoria.destroy();
    graficas.auditoria = new Chart($('#graficaAuditoria'), {
      data: { labels: etiquetas, datasets: series },
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, color: COLORES.slate900 } },
          tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${num(c.parsed.y, 2)} ${u}` } },
        },
        scales: {
          y: { beginAtZero: true, ticks: { callback: (v) => `${v} ${u}`, color: COLORES.slate500 }, grid: { color: COLORES.slate200 } },
          x: { ticks: { color: COLORES.slate500 }, grid: { display: false } },
        },
      },
    });
  }
  $('#insumoAuditoria').addEventListener('change', cargarAuditoria);

  // ---------------------------------------------------------------------------
  // Reintentar conexión y arranque
  // ---------------------------------------------------------------------------
  $('#reintentarConexion').addEventListener('click', async () => {
    conexion.modo = 'detectando';
    await detectarServidor();
    if (conexion.modo === 'api') {
      toast('Conectado con el servidor.');
      Object.keys(cargado).forEach((k) => { cargado[k] = false; });
      await iniciarDatos();
    } else {
      toast('El servidor sigue sin responder. Inícialo con: python backend/main.py', 'aviso');
    }
  });
  $('#estadoConexion').addEventListener('click', () => { if (conexion.modo === 'demo') $('#reintentarConexion').click(); });

  async function iniciarDatos() {
    try {
      await cargarCatalogo();
    } catch (err) {
      mostrarError('#errorPlaneador', err.message);
      return;
    }
    await actualizarPlan();
    const vista = (location.hash || '#planeador').slice(1);
    mostrarVista(['planeador', 'rescate', 'alerta', 'auditoria'].includes(vista) ? vista : 'planeador');
  }

  async function iniciar() {
    iconos();
    aplicarEscenario();
    await detectarServidor();
    await iniciarDatos();
  }

  window.addEventListener('resize', () => Object.values(graficas).forEach((g) => { if (g && g.canvas.offsetParent) g.resize(); }));
  iniciar();
})();

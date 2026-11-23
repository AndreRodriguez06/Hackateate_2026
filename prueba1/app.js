/* ==========================================================================
   ZeroMerma AI — Prototipo frontend (prueba1)
   Toda la lógica corre en el navegador con datos simulados (Vanilla JS).
   ========================================================================== */
(function () {
  'use strict';

  // ---------- Utilidades ----------
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const fmtNum = (n, d = 1) => new Intl.NumberFormat('es-MX', { minimumFractionDigits: d, maximumFractionDigits: d }).format(n);
  const fmtMXN = (n) => '$' + new Intl.NumberFormat('es-MX', { maximumFractionDigits: 0 }).format(Math.round(n)) + ' MXN';
  const fmtHour = (h) => {
    const hh = Math.floor(h);
    const mm = Math.round((h - hh) * 60);
    const suffix = hh >= 12 ? 'PM' : 'AM';
    const h12 = hh % 12 === 0 ? 12 : hh % 12;
    return `${h12}:${String(mm).padStart(2, '0')} ${suffix}`;
  };
  const refreshIcons = () => { if (window.lucide) window.lucide.createIcons(); };
  const hasChart = () => typeof window.Chart !== 'undefined';

  const COLORS = {
    slate900: '#0f172a', slate500: '#64748b', slate300: '#cbd5e1', slate200: '#e2e8f0',
    emerald600: '#059669', emerald400: '#34d399', amber500: '#f59e0b', rose600: '#e11d48'
  };

  // ---------- Datos simulados ----------
  const SCENARIOS = {
    quincena: {
      base: 150,
      preset: { quincena: true, lluvia: true, evento: false },
      dayWeight: 48,
      note: 'Escenario: viernes de quincena con lluvia. El modelo eleva la demanda por mayor poder adquisitivo y clientes que se refugian de la lluvia.'
    },
    martes: {
      base: 145,
      preset: { quincena: false, lluvia: false, evento: false },
      dayWeight: 45,
      note: 'Escenario: martes regular. Demanda estándar basada en el flujo histórico de las últimas 12 semanas.'
    },
    semestre: {
      base: 96,
      preset: { quincena: false, lluvia: false, evento: false },
      dayWeight: 42,
      note: 'Escenario: fin de semestre. La afluencia del campus cae ~34%; comprar "como siempre" genera la mayor merma.'
    }
  };

  // Consumo por comensal, precio de referencia y compra tradicional habitual
  const INSUMOS = {
    pollo:    { nombre: 'Pechuga de pollo', unidad: 'kg', porCliente: 0.130, precio: 135, tradicional: 28 },
    crema:    { nombre: 'Crema ácida',      unidad: 'L',  porCliente: 0.034, precio: 72,  tradicional: 7.5 },
    tortilla: { nombre: 'Tortilla de maíz', unidad: 'kg', porCliente: 0.160, precio: 24,  tradicional: 34 },
    queso:    { nombre: 'Queso manchego',   unidad: 'kg', porCliente: 0.038, precio: 189, tradicional: 8 }
  };

  const UPLIFT = { quincena: 0.12, lluvia: 0.09, evento: 0.15 };

  const INVENTARIO = [
    { insumo: 'Pechuga de pollo', cantidad: '7.5 kg',  caduca: 'Caduca en 18 hrs',  nivel: 'rojo' },
    { insumo: 'Crema ácida',      cantidad: '4.0 L',   caduca: 'Caduca en 22 hrs',  nivel: 'rojo' },
    { insumo: 'Jitomate saladet', cantidad: '6.0 kg',  caduca: 'Caduca en 48 hrs',  nivel: 'amarillo' },
    { insumo: 'Arroz blanco',     cantidad: '12.0 kg', caduca: 'Caduca en 15 días', nivel: 'verde' }
  ];

  const ESTRATEGIAS = [
    {
      platillo: 'Enchiladas Suizas',
      receta: 'Usa 180 g pollo + 60 ml crema por orden',
      tipo: '25% de descuento hoy',
      icono: 'percent',
      precioNormal: 120, precioOferta: 90,
      meta: 'Meta: 22 órdenes antes de las 6:00 PM → consume 4.0 kg de pollo y 1.3 L de crema.',
      perdida: 525, recuperado: 1140,
      copy: 'Gratinadas con manchego, salsa verde cremosa y pollo deshebrado al momento. Solo hoy a precio especial.'
    },
    {
      platillo: 'Chilaquiles Especiales con Pollo',
      receta: 'Usa 150 g pollo + 40 ml crema por orden',
      tipo: 'Combo con bebida incluida',
      icono: 'cup-soda',
      precioNormal: 145, precioOferta: 125,
      precioNota: 'Chilaquiles $110 + agua fresca $35 → combo $125',
      meta: 'Meta: 16 combos en comida y merienda → consume 2.4 kg de pollo y 0.64 L de crema.',
      perdida: 370, recuperado: 1376,
      copy: 'Totopos crujientes bañados en salsa roja, pollo, crema y queso fresco + agua fresca de temporada.'
    }
  ];

  const BACKTEST = {
    dias: ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'],
    tradicional: [28, 28, 28, 28, 28, 30, 30],
    real:        [18.2, 19.5, 20.1, 21.4, 25.8, 23.0, 16.4],
    sugerida:    [19.8, 20.9, 21.5, 23.3, 27.6, 24.9, 17.9]
  };

  // ======================================================================
  // PASO 1: Navegación por pestañas
  // ======================================================================
  const charts = { feature: null, backtest: null };

  function showTab(name) {
    $$('[role="tab"]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === name)));
    $$('[data-view]').forEach((v) => v.classList.toggle('hidden', v.id !== `view-${name}`));
    // Las gráficas se crean/redimensionan cuando su contenedor es visible
    requestAnimationFrame(() => {
      if (name === 'planeador') renderFeatureChart();
      if (name === 'auditoria') renderBacktestChart();
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  $$('[role="tab"]').forEach((btn) => btn.addEventListener('click', () => showTab(btn.dataset.tab)));

  // ======================================================================
  // PASO 2: Vista 1 — Planeador de compras
  // ======================================================================
  const ui = {
    scenario: $('#scenarioSelect'),
    margin: $('#marginSlider'),
    marginLabel: $('#marginLabel'),
    q: $('#chkQuincena'), l: $('#chkLluvia'), e: $('#chkEvento'),
    insumo: $('#insumoSelect')
  };

  function applyScenarioPreset() {
    const s = SCENARIOS[ui.scenario.value];
    ui.q.checked = s.preset.quincena;
    ui.l.checked = s.preset.lluvia;
    ui.e.checked = s.preset.evento;
    $('#scenarioNote').textContent = s.note;
  }

  function computePlan() {
    const s = SCENARIOS[ui.scenario.value];
    const ins = INSUMOS[ui.insumo.value];
    const margin = Number(ui.margin.value) / 100;

    const uplift = 1 + (ui.q.checked ? UPLIFT.quincena : 0) + (ui.l.checked ? UPLIFT.lluvia : 0) + (ui.e.checked ? UPLIFT.evento : 0);
    const comensales = Math.round(s.base * uplift);
    const prediccionBase = comensales * ins.porCliente;
    const sugerida = prediccionBase * (1 + margin);
    const inversion = sugerida * ins.precio;
    const mermaEvitada = ins.tradicional - sugerida;

    return { s, ins, margin, comensales, prediccionBase, sugerida, inversion, mermaEvitada, uplift };
  }

  function featureWeights() {
    const s = SCENARIOS[ui.scenario.value];
    const raw = [
      ['Día de la semana', s.dayWeight],
      ['Flujo histórico', 30],
      ['Quincena', ui.q.checked ? 15 : 4],
      ['Clima', ui.l.checked ? 10 : 3],
      ['Evento universitario', ui.e.checked ? 12 : 2]
    ];
    const total = raw.reduce((a, [, v]) => a + v, 0);
    return raw.map(([k, v]) => [k, Math.round((v / total) * 1000) / 10]).sort((a, b) => b[1] - a[1]);
  }

  function renderPlan() {
    const r = computePlan();
    const m = Number(ui.margin.value);
    ui.marginLabel.textContent = `${m}%`;
    ui.marginLabel.className = 'tabular text-sm font-semibold px-2 py-0.5 rounded-md ' +
      (m < 4 ? 'bg-rose-50 text-rose-700' : 'bg-emerald-50 text-emerald-700');

    $('#kpiComensales').textContent = `${r.comensales} clientes`;
    const delta = Math.round((r.uplift - 1) * 100);
    $('#kpiComensalesSub').textContent = delta > 0 ? `Base ${r.s.base} + ${delta}% por contexto` : `Base histórica del escenario`;

    $('#kpiCompra').textContent = `${fmtNum(r.sugerida)} ${r.ins.unidad}`;
    $('#kpiCompraSub').textContent = `Predicción ${fmtNum(r.prediccionBase)} ${r.ins.unidad} × (1 + ${m}%)`;

    $('#kpiInversion').textContent = fmtMXN(r.inversion);
    $('#kpiInversionSub').textContent = `${fmtMXN(r.ins.precio)} / ${r.ins.unidad} · Tradicional: ${fmtMXN(r.ins.tradicional * r.ins.precio)}`;

    if (r.mermaEvitada > 0) {
      $('#kpiMerma').textContent = `${fmtNum(r.mermaEvitada)} ${r.ins.unidad}`;
      $('#kpiMermaSub').textContent = `${fmtMXN(r.mermaEvitada * r.ins.precio)} ahorrados vs. ${fmtNum(r.ins.tradicional)} ${r.ins.unidad} habituales`;
    } else {
      $('#kpiMerma').textContent = `0 ${r.ins.unidad}`;
      $('#kpiMermaSub').textContent = `Demanda alta: la compra habitual (${fmtNum(r.ins.tradicional)} ${r.ins.unidad}) se quedaría corta.`;
    }

    $('#stockoutBanner').classList.toggle('hidden', m >= 4);
    renderFeatureChart();
  }

  function renderFeatureChart() {
    if (!hasChart()) return;
    const canvas = $('#featureChart');
    if (!canvas.offsetParent) return; // vista oculta: se dibuja al mostrarla
    const data = featureWeights();
    if (!charts.feature) {
      charts.feature = new Chart(canvas, {
        type: 'bar',
        data: {
          labels: data.map((d) => d[0]),
          datasets: [{
            label: 'Importancia (%)',
            data: data.map((d) => d[1]),
            backgroundColor: data.map((_, i) => (i === 0 ? COLORS.emerald600 : COLORS.emerald400)),
            borderRadius: 4,
            barThickness: 22
          }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 350 },
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (c) => ` ${fmtNum(c.parsed.x)}% de la predicción` } }
          },
          scales: {
            x: { min: 0, max: 60, ticks: { callback: (v) => v + '%', color: COLORS.slate500 }, grid: { color: COLORS.slate200 } },
            y: { ticks: { color: COLORS.slate900, font: { size: 12 } }, grid: { display: false } }
          }
        }
      });
    } else {
      charts.feature.data.labels = data.map((d) => d[0]);
      charts.feature.data.datasets[0].data = data.map((d) => d[1]);
      charts.feature.data.datasets[0].backgroundColor = data.map((_, i) => (i === 0 ? COLORS.emerald600 : COLORS.emerald400));
      charts.feature.resize();
      charts.feature.update();
    }
  }

  ui.scenario.addEventListener('change', () => { applyScenarioPreset(); renderPlan(); });
  [ui.margin].forEach((el) => el.addEventListener('input', renderPlan));
  [ui.q, ui.l, ui.e, ui.insumo].forEach((el) => el.addEventListener('change', renderPlan));

  // ======================================================================
  // PASO 3: Vista 2 — Rescate rentable (Gemini simulado)
  // ======================================================================
  const BADGE = {
    rojo: 'bg-rose-50 text-rose-700 ring-rose-600/20',
    amarillo: 'bg-amber-50 text-amber-700 ring-amber-500/30',
    verde: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20'
  };
  const BADGE_TXT = { rojo: 'Crítico', amarillo: 'Vigilar', verde: 'Estable' };

  function renderInventory() {
    $('#inventoryBody').innerHTML = INVENTARIO.map((i) => `
      <tr class="hover:bg-slate-50">
        <td class="px-5 py-3 font-medium">${i.insumo}</td>
        <td class="px-5 py-3 text-right tabular">${i.cantidad}</td>
        <td class="px-5 py-3 text-slate-600">${i.caduca}</td>
        <td class="px-5 py-3">
          <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ring-1 ${BADGE[i.nivel]}">
            <span class="h-1.5 w-1.5 rounded-full ${i.nivel === 'rojo' ? 'bg-rose-600' : i.nivel === 'amarillo' ? 'bg-amber-500' : 'bg-emerald-600'}"></span>
            ${i.caduca.replace('Caduca en ', '')} · ${BADGE_TXT[i.nivel]}
          </span>
        </td>
      </tr>`).join('');
  }

  function strategyCard(e, idx) {
    const max = Math.max(e.perdida, e.recuperado);
    const wLoss = Math.round((e.perdida / max) * 100);
    const wGain = Math.round((e.recuperado / max) * 100);
    return `
      <article class="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 fade-in" style="animation-delay:${idx * 120}ms">
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-[11px] uppercase tracking-wide text-slate-400 font-medium">Platillo existente · Tarjeta ${idx + 1}</p>
            <h4 class="text-lg font-semibold">${e.platillo}</h4>
            <p class="text-xs text-slate-500">${e.receta}</p>
          </div>
          <span class="shrink-0 h-10 w-10 rounded-xl bg-emerald-50 text-emerald-600 grid place-items-center"><i data-lucide="${e.icono}" class="w-5 h-5"></i></span>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-3">
          <span class="px-2.5 py-1 rounded-lg bg-amber-500 text-white text-sm font-semibold">${e.tipo}</span>
          <span class="text-sm text-slate-500">Precio normal <s>$${e.precioNormal}</s> → <strong class="text-slate-900">Oferta $${e.precioOferta}</strong></span>
        </div>
        ${e.precioNota ? `<p class="text-xs text-slate-500 mt-1">${e.precioNota}</p>` : ''}
        <p class="text-sm text-slate-600 mt-3">${e.meta}</p>

        <div class="mt-4 space-y-3">
          <div>
            <div class="flex justify-between text-xs mb-1"><span class="text-slate-600">Si se tira a la basura</span><span class="tabular font-semibold text-rose-600">-${fmtMXN(e.perdida)} pérdida</span></div>
            <div class="h-3 rounded-full bg-slate-100 overflow-hidden"><div class="h-full bg-rose-600 rounded-full" style="width:${wLoss}%"></div></div>
          </div>
          <div>
            <div class="flex justify-between text-xs mb-1"><span class="text-slate-600">Con promoción Gemini</span><span class="tabular font-semibold text-emerald-600">+${fmtMXN(e.recuperado)} margen neto recuperado</span></div>
            <div class="h-3 rounded-full bg-slate-100 overflow-hidden"><div class="h-full bg-emerald-600 rounded-full" style="width:${wGain}%"></div></div>
          </div>
        </div>
        <p class="mt-3 text-xs text-slate-500 flex items-center gap-1"><i data-lucide="arrow-up-right" class="w-3.5 h-3.5 text-emerald-600"></i>
          Diferencia a favor: <strong class="text-slate-800">${fmtMXN(e.perdida + e.recuperado)}</strong></p>
      </article>`;
  }

  function renderPhoneMenu() {
    const especiales = ESTRATEGIAS.map((e) => `
      <div class="rounded-xl bg-white border border-amber-200 p-3 shadow-sm">
        <div class="flex justify-between items-start gap-2">
          <p class="font-semibold text-sm leading-tight">${e.platillo}</p>
          <div class="text-right shrink-0">
            <p class="text-[10px] text-slate-400 line-through">$${e.precioNormal}</p>
            <p class="text-sm font-bold text-emerald-600">$${e.precioOferta}</p>
          </div>
        </div>
        <p class="text-[11px] text-slate-500 mt-1 leading-snug">${e.copy}</p>
        <span class="inline-block mt-2 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">${e.tipo}</span>
      </div>`).join('');

    const regulares = [
      ['Molletes con pico de gallo', 75], ['Torta de milanesa', 95], ['Café americano', 35], ['Agua fresca del día', 35]
    ].map(([n, p]) => `
      <div class="flex justify-between text-xs py-1.5 border-b border-slate-100 last:border-0">
        <span class="text-slate-700">${n}</span><span class="tabular text-slate-500">$${p}</span>
      </div>`).join('');

    $('#phoneMenu').innerHTML = `
      <div class="rounded-xl bg-gradient-to-r from-amber-500 to-rose-600 text-white p-3">
        <p class="font-bold">🔥 Especiales del Chef Hoy</p>
        <p class="text-[11px] opacity-90">Preparados con ingredientes frescos del día · disponibles hasta agotar existencias</p>
      </div>
      ${especiales}
      <div class="rounded-xl bg-white border border-slate-200 p-3">
        <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Menú regular</p>
        ${regulares}
      </div>
      <p class="text-[10px] text-center text-slate-400 pt-1">♻️ Al pedir un especial ayudas a reducir el desperdicio de alimentos</p>`;
  }

  $('#geminiBtn').addEventListener('click', () => {
    const btn = $('#geminiBtn');
    btn.disabled = true;
    $('#geminiResult').classList.add('hidden');
    $('#geminiLoading').classList.remove('hidden');
    setTimeout(() => {
      $('#geminiLoading').classList.add('hidden');
      $('#strategyCards').innerHTML = ESTRATEGIAS.map(strategyCard).join('');
      renderPhoneMenu();
      $('#geminiResult').classList.remove('hidden');
      btn.disabled = false;
      refreshIcons();
    }, 1200);
  });

  // ======================================================================
  // PASO 4: Vista 3 — Alerta temprana de excedentes
  // ======================================================================
  const PREPARADAS = 64;
  const CIERRE = 20; // 8:00 PM
  const RITMO = {
    lentas:   { totalVentas: 46 },
    normales: { totalVentas: 61 },
    rapidas:  { totalVentas: 72 }
  };
  const fraccionVendida = (h) => Math.pow(Math.max(0, h - 12) / (CIERRE - 12), 0.8);

  function computeAlert() {
    const h = Number($('#hourSlider').value);
    const pace = $('#paceSelect').value;
    const total = RITMO[pace].totalVentas;
    const vendidas = Math.min(PREPARADAS, Math.round(total * fraccionVendida(h)));
    const sobrante = Math.max(0, PREPARADAS - total);
    let agotamiento = null;
    if (total > PREPARADAS) {
      agotamiento = 12 + (CIERRE - 12) * Math.pow(PREPARADAS / total, 1 / 0.8);
      agotamiento = Math.round(agotamiento * 4) / 4;
    }
    return { h, pace, vendidas, sobrante, agotamiento };
  }

  function renderAlert() {
    const a = computeAlert();
    $('#hourLabel').textContent = fmtHour(a.h);
    $('#soldLabel').textContent = `${a.vendidas} / ${PREPARADAS}`;
    $('#soldBar').style.width = `${(a.vendidas / PREPARADAS) * 100}%`;
    $('#remainingLabel').textContent = PREPARADAS - a.vendidas;
    $('#leftoverLabel').textContent = a.sobrante;
    $('#leftoverLabel').className = 'tabular font-semibold ' + (a.sobrante >= 10 ? 'text-orange-600' : 'text-slate-900');

    const box = $('#alertStatus');
    let html = '';
    const isAlert = a.pace === 'lentas' && a.h >= 15;

    if (isAlert) {
      html = `
        <div class="rounded-2xl border border-orange-300 bg-orange-50 p-5 fade-in">
          <div class="flex gap-3 items-start">
            <span class="h-10 w-10 shrink-0 rounded-xl bg-orange-500 text-white grid place-items-center"><i data-lucide="siren" class="w-5 h-5"></i></span>
            <div class="flex-1">
              <p class="text-xs font-semibold uppercase tracking-wide text-orange-700">Alerta preventiva · ${fmtHour(a.h)}</p>
              <p class="mt-1 text-orange-950"><strong>Proyección de cierre:</strong> Sobrarán <strong>${a.sobrante} porciones</strong> de Enchiladas / Pechuga preparada que no se venderán antes de las 8:00 PM.</p>
              <p class="mt-1 text-sm text-orange-800">El ritmo de ventas va 30% por debajo de lo esperado. Avisar ahora maximiza la ventana de recolección.</p>
              <button id="genFichaBtn" class="mt-4 inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-sm font-semibold focus:outline-none focus:ring-4 focus:ring-orange-300 transition">
                📢 Generar Ficha de Rescate Temprano
              </button>
            </div>
          </div>
        </div>`;
    } else if (a.pace === 'lentas') {
      html = `
        <div class="rounded-2xl border border-amber-200 bg-amber-50 p-5 fade-in flex gap-3 items-start">
          <i data-lucide="hourglass" class="w-5 h-5 text-amber-600 shrink-0 mt-0.5"></i>
          <div>
            <p class="font-semibold text-amber-900">Monitoreando: ventas por debajo de lo esperado</p>
            <p class="text-sm text-amber-800 mt-1">El modelo confirma la proyección de excedentes a partir de las 3:00 PM, cuando termina la hora pico de comida. Mueve el slider de hora para continuar la simulación.</p>
          </div>
        </div>`;
    } else if (a.pace === 'normales') {
      html = `
        <div class="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 fade-in flex gap-3 items-start">
          <i data-lucide="check-circle-2" class="w-5 h-5 text-emerald-600 shrink-0 mt-0.5"></i>
          <div>
            <p class="font-semibold text-emerald-900">Operación dentro de tolerancia</p>
            <p class="text-sm text-emerald-800 mt-1">Proyección de cierre: sobrarían <strong>${a.sobrante} porciones</strong>, aprovechables como comida del personal. No se requiere aviso de rescate.</p>
          </div>
        </div>`;
    } else {
      html = `
        <div class="rounded-2xl border border-slate-300 bg-white p-5 fade-in flex gap-3 items-start">
          <i data-lucide="flame" class="w-5 h-5 text-rose-600 shrink-0 mt-0.5"></i>
          <div>
            <p class="font-semibold">Alta rotación: posible agotamiento cerca de las ${fmtHour(a.agotamiento)}</p>
            <p class="text-sm text-slate-600 mt-1">Sin excedentes proyectados. Si el ritmo continúa, considera preparar ${RITMO.rapidas.totalVentas - PREPARADAS} porciones adicionales antes de las 5:00 PM.</p>
          </div>
        </div>`;
    }
    box.innerHTML = html;
    if (!isAlert) $('#dispatchPanel').classList.add('hidden');
    const gen = $('#genFichaBtn');
    if (gen) gen.addEventListener('click', () => renderDispatch(a));
    refreshIcons();
  }

  function renderDispatch(a) {
    const inicio = Math.max(16.5, a.h + 1.5);
    const fin = inicio <= 17.5 ? 18.5 : Math.min(CIERRE, inicio + 1);
    const horasAntes = CIERRE - inicio;
    const kg = (a.sobrante * 0.25).toFixed(1);
    const folio = 'ZM-' + new Date().toISOString().slice(2, 10).replace(/-/g, '') + '-' + String(Math.round(a.h * 10)).padStart(3, '0');

    const panel = $('#dispatchPanel');
    panel.innerHTML = `
      <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden fade-in">
        <div class="px-5 py-3 bg-slate-900 text-white flex items-center justify-between gap-3 flex-wrap">
          <p class="font-semibold flex items-center gap-2"><i data-lucide="clipboard-list" class="w-4 h-4 text-emerald-400"></i> Ficha de Rescate Temprano</p>
          <span class="text-xs text-slate-400 tabular">Folio ${folio}</span>
        </div>
        <dl class="divide-y divide-slate-100 text-sm">
          <div class="px-5 py-3 grid sm:grid-cols-3 gap-1"><dt class="text-slate-500 flex items-center gap-2"><i data-lucide="utensils" class="w-4 h-4"></i> Alimento disponible</dt>
            <dd class="sm:col-span-2 font-medium">${a.sobrante} porciones de Pechuga / Enchiladas Suizas (aprox. ${kg} kg)</dd></div>
          <div class="px-5 py-3 grid sm:grid-cols-3 gap-1"><dt class="text-slate-500 flex items-center gap-2"><i data-lucide="truck" class="w-4 h-4"></i> Ventana de recolección óptima</dt>
            <dd class="sm:col-span-2 font-medium">Hoy entre ${fmtHour(inicio)} y ${fmtHour(fin)} <span class="text-slate-500 font-normal">(${fmtNum(horasAntes)} horas antes del cierre)</span></dd></div>
          <div class="px-5 py-3 grid sm:grid-cols-3 gap-1"><dt class="text-slate-500 flex items-center gap-2"><i data-lucide="shield-check" class="w-4 h-4"></i> Nota de inocuidad</dt>
            <dd class="sm:col-span-2 font-medium">Mantener en refrigeración; consumir el mismo día.</dd></div>
          <div class="px-5 py-3 grid sm:grid-cols-3 gap-1"><dt class="text-slate-500 flex items-center gap-2"><i data-lucide="map-pin" class="w-4 h-4"></i> Punto de entrega</dt>
            <dd class="sm:col-span-2 font-medium">Cafetería La Esquina · acceso por andén de servicio</dd></div>
        </dl>
        <div class="px-5 py-4 bg-slate-50 border-t border-slate-200">
          <button id="sendAvisoBtn" class="w-full sm:w-auto inline-flex justify-center items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold focus:outline-none focus:ring-4 focus:ring-emerald-300 transition disabled:opacity-60">
            <i data-lucide="send" class="w-4 h-4"></i> Enviar Aviso a Comedor Comunitario / Red Campus
          </button>
        </div>
      </div>`;
    panel.classList.remove('hidden');
    refreshIcons();
    $('#sendAvisoBtn').addEventListener('click', (ev) => {
      const b = ev.currentTarget;
      b.disabled = true;
      b.innerHTML = '<i data-lucide="check" class="w-4 h-4"></i> Aviso enviado';
      refreshIcons();
      toast('✅ Aviso enviado con éxito. Tiempo estimado de respuesta: 15 min.');
    });
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  $('#hourSlider').addEventListener('input', renderAlert);
  $('#paceSelect').addEventListener('change', renderAlert);

  // ---------- Toast ----------
  function toast(msg) {
    const el = document.createElement('div');
    el.setAttribute('role', 'status');
    el.className = 'toast-enter max-w-sm rounded-xl bg-emerald-600 text-white shadow-xl px-4 py-3 text-sm font-medium';
    el.textContent = msg;
    $('#toastContainer').appendChild(el);
    setTimeout(() => {
      el.style.transition = 'opacity .3s, transform .3s';
      el.style.opacity = '0';
      el.style.transform = 'translateY(8px)';
      setTimeout(() => el.remove(), 300);
    }, 4000);
  }

  // ======================================================================
  // PASO 5: Vista 4 — Auditoría y backtesting
  // ======================================================================
  function renderBacktestChart() {
    if (!hasChart()) return;
    const canvas = $('#backtestChart');
    if (!canvas.offsetParent) return;
    if (charts.backtest) { charts.backtest.resize(); charts.backtest.update(); return; }
    charts.backtest = new Chart(canvas, {
      data: {
        labels: BACKTEST.dias,
        datasets: [
          { type: 'bar', label: 'Compra Tradicional del Restaurante', data: BACKTEST.tradicional, backgroundColor: COLORS.slate300, borderRadius: 4, order: 3 },
          { type: 'bar', label: 'Compra Sugerida por ZeroMerma AI', data: BACKTEST.sugerida, backgroundColor: COLORS.emerald600, borderRadius: 4, order: 2 },
          { type: 'line', label: 'Demanda Real Ocurrida', data: BACKTEST.real, borderColor: COLORS.slate900, backgroundColor: COLORS.slate900,
            borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, tension: 0.3, order: 1 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, color: COLORS.slate900 } },
          tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${fmtNum(c.parsed.y)} kg` } }
        },
        scales: {
          y: { beginAtZero: true, ticks: { callback: (v) => v + ' kg', color: COLORS.slate500 }, grid: { color: COLORS.slate200 } },
          x: { ticks: { color: COLORS.slate500 }, grid: { display: false } }
        }
      }
    });
  }

  // Redimensionar gráficas visibles al cambiar el tamaño de ventana
  window.addEventListener('resize', () => {
    Object.values(charts).forEach((c) => { if (c && c.canvas.offsetParent) c.resize(); });
  });

  // ---------- Inicio ----------
  applyScenarioPreset();
  renderInventory();
  renderPlan();
  renderAlert();
  refreshIcons();
})();

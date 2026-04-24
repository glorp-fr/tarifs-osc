/* Client API Outscale Estimateur — fallback localStorage → défauts codés */
window.OSApi = (() => {

  const BASE = '/api';
  const LS   = { catalog:'osc:catalog', regions:'osc:regions', formulas:'osc:formulas' };

  /* Valeurs par défaut embarquées (utilisées uniquement si l'API ET le cache localStorage sont absents) */
  const DEFAULT_REGIONS = [
    {id:"eu-west-2",           flag:"FR", short:"EU-W2",  name:"Europe Ouest (France)",    active:true},
    {id:"cloudgouv-eu-west-1", flag:"FR", short:"GOUV",   name:"Cloud Souverain (France)", active:true},
    {id:"us-west-1",           flag:"US", short:"US-W1",  name:"US Ouest",                 active:true},
    {id:"us-east-2",           flag:"US", short:"US-E2",  name:"US Est",                   active:true},
    {id:"ap-northeast-1",      flag:"JP", short:"AP-NE1", name:"Asie (Japon)",             active:true},
  ];

  const DEFAULT_ENGAGEMENTS = [
    {id:"on-demand",       label:"A la demande",                 discount:0.00, active:true},
    {id:"ri-1m-upfront",   label:"RI 1 mois upfront (-30%)",     discount:0.30, active:true},
    {id:"ri-1y-upfront",   label:"RI 1 an upfront (-40%)",       discount:0.40, active:true},
    {id:"ri-2y-upfront",   label:"RI 2 ans upfront (-50%)",      discount:0.50, active:true},
    {id:"ri-3y-upfront",   label:"RI 3 ans upfront (-60%)",      discount:0.60, active:true},
    {id:"ri-1y-quarterly", label:"RI 1 an trimestriel (-37%)",   discount:0.37, active:true},
    {id:"ri-2y-quarterly", label:"RI 2 ans trimestriel (-45%)",  discount:0.45, active:true},
    {id:"ri-3y-quarterly", label:"RI 3 ans trimestriel (-53%)",  discount:0.53, active:true},
    {id:"ri-2y-yearly",    label:"RI 2 ans annuel (-48%)",       discount:0.48, active:true},
    {id:"ri-3y-yearly",    label:"RI 3 ans annuel (-56%)",       discount:0.56, active:true},
  ];

  async function fetchJson(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  function lsGet(key) {
    try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : null; } catch { return null; }
  }

  function lsSet(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
  }

  async function loadCatalog() {
    try {
      const data = await fetchJson(`${BASE}/catalog`);
      lsSet(LS.catalog, data);
      return data;
    } catch {
      const cached = lsGet(LS.catalog);
      if (cached) return cached;
      return null; // App will use embedded fallback
    }
  }

  async function loadRegions() {
    try {
      const data = await fetchJson(`${BASE}/regions`);
      lsSet(LS.regions, data);
      return (data.regions || data).filter(r => r.active !== false);
    } catch {
      const cached = lsGet(LS.regions);
      if (cached) return (cached.regions || cached).filter(r => r.active !== false);
      return DEFAULT_REGIONS;
    }
  }

  async function loadEngagements() {
    try {
      const data = await fetchJson(`${BASE}/formulas`);
      lsSet(LS.formulas, data);
      return (data.engagements || data).filter(e => e.active !== false);
    } catch {
      const cached = lsGet(LS.formulas);
      if (cached) return (cached.engagements || cached).filter(e => e.active !== false);
      return DEFAULT_ENGAGEMENTS;
    }
  }

  async function loadAll() {
    const [catalog, regions, engagements] = await Promise.all([
      loadCatalog(),
      loadRegions(),
      loadEngagements(),
    ]);
    return { catalog, regions, engagements };
  }

  return { loadAll, DEFAULT_REGIONS, DEFAULT_ENGAGEMENTS };
})();

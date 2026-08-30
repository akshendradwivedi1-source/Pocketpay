// ========== PocketPay: Core Application State & Router ==========
window.PP = {
  state: {
    user: null,
    pockets: [],
    transactions: [],
    budgets: [],
    notifications: [],
    distributionRules: [],
    currentRoute: 'dashboard',
    icons: [],
    colors: [],
    viewData: {},
    initialized: false,
  },
  cache: {},
  listeners: {},
};

PP.$ = (sel, root = document) => root.querySelector(sel);
PP.$$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
PP.el = (tag, attrs = {}, children = []) => {
  const e = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (k === 'class') e.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(e.style, v);
    else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v !== null && v !== undefined) e.setAttribute(k, v);
  });
  (Array.isArray(children) ? children : [children]).forEach(c => {
    if (c == null) return;
    if (typeof c === 'string' || typeof c === 'number') e.appendChild(document.createTextNode(String(c)));
    else e.appendChild(c);
  });
  return e;
};
PP.fmt = (n, curr = '₹') => {
  try { n = Number(n) || 0; } catch { n = 0; }
  const neg = n < 0;
  n = Math.abs(n);
  let s = n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${neg ? '-' : ''}${curr}${s}`;
};
PP.formatDate = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
};
PP.formatDateTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};
PP.formatTimeAgo = (iso) => {
  if (!iso) return '';
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return PP.formatDate(iso);
};
PP.uid = () => Math.random().toString(36).slice(2, 10);
PP.debounce = (fn, ms = 250) => {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
};
PP.on = (evt, fn) => { (PP.listeners[evt] = PP.listeners[evt] || []).push(fn); };
PP.emit = (evt, data) => (PP.listeners[evt] || []).forEach(fn => { try { fn(data); } catch(e){ console.error(e); } });

PP.navigate = (route, params = {}) => {
  PP.state.currentRoute = route;
  PP.state.viewData = params;
  PP.renderView();
  PP.updateNavState();
  window.scrollTo({ top: 0, behavior: 'smooth' });
  try { history.pushState({ route, params }, '', `#${route}`); } catch {}
  PP.emit('route:change', { route, params });
};

PP.updateNavState = () => {
  const route = PP.state.currentRoute;
  PP.$$('.nav-item, .bottom-item').forEach(el => {
    const r = el.getAttribute('data-route');
    if (r) el.classList.toggle('active', r === route);
  });
};

PP.renderView = () => {
  const container = PP.$('#viewContainer');
  if (!container) return;
  container.innerHTML = '';
  container.classList.remove('page-enter');
  void container.offsetWidth;
  container.classList.add('page-enter');
  const route = PP.state.currentRoute;
  const renderers = {
    dashboard: PP.Dashboard?.render,
    pockets: PP.Pockets?.render,
    'pocket-detail': PP.Pockets?.renderDetail,
    transactions: PP.Transactions?.render,
    analytics: PP.Analytics?.render,
    wallet: PP.Wallet?.render,
    budgets: PP.Analytics?.renderBudgets,
    premium: PP.Premium?.render,
    profile: PP.Wallet?.render,
    settings: PP.Wallet?.render,
    login: PP.renderAuth,
  };
  const fn = renderers[route] || (PP.state.user ? PP.Dashboard.render : PP.renderAuth);
  try { fn(container, PP.state.viewData || {}); }
  catch (e) { console.error('View render error:', e); container.innerHTML = `<div class="empty-state"><p class="text-muted">Error loading view.</p></div>`; }
  PP.refreshIcons();
  PP.emit('view:rendered', route);
};

PP.ICONS = {
  'bell': '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  'bell-ring': '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/><path d="M4 2C2.8 3.7 2 5.7 2 8"/><path d="M22 8c0-2.3-.8-4.3-2-6"/>',
  'bell-off': '<path d="M8.7 3A6 6 0 0 1 18 8a21.3 21.3 0 0 0 .6 5"/><path d="M17 17H3s3-2 3-9a4.67 4.67 0 0 1 .3-1.7"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/><path d="m2 2 20 20"/>',
  'x': '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  'x-circle': '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
  'check': '<path d="M20 6 9 17l-5-5"/>',
  'check-circle': '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
  'check-circle-2': '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
  'plus': '<path d="M5 12h14"/><path d="M12 5v14"/>',
  'plus-circle': '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/>',
  'minus': '<path d="M5 12h14"/>',
  'minus-circle': '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
  'search': '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  'moon': '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  'menu': '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
  'chevron-down': '<path d="m6 9 6 6 6-6"/>',
  'chevron-up': '<path d="m18 15-6-6-6 6"/>',
  'chevron-left': '<path d="m15 18-6-6 6-6"/>',
  'chevron-right': '<path d="m9 18 6-6-6-6"/>',
  'arrow-left': '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
  'arrow-right': '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  'arrow-down-left': '<path d="M17 7 7 17"/><path d="M17 17H7V7"/>',
  'arrow-up-right': '<path d="M7 17 17 7"/><path d="M7 7h10v10"/>',
  'arrow-left-right': '<path d="m16 3 4 4-4 4"/><path d="M20 7H4"/><path d="m8 21-4-4 4-4"/><path d="M4 17h16"/>',
  'arrow-up-down': '<path d="m21 16-4 4-4-4"/><path d="M17 20V4"/><path d="m3 8 4-4 4 4"/><path d="M7 4v16"/>',
  'refresh-cw': '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  'refresh-ccw': '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/>',
  'layout-dashboard': '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
  'wallet': '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
  'wallet-cards': '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2"/><path d="M3 11h18"/><path d="M8 15h.01"/><path d="M16 15h.01"/>',
  'shield': '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
  'shield-check': '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  'shield-alert': '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
  'user': '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  'users': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  'settings': '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  'log-out': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
  'sparkles': '<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>',
  'send': '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  'download': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  'upload': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
  'qr-code': '<rect width="5" height="5" x="3" y="3" rx="1"/><rect width="5" height="5" x="16" y="3" rx="1"/><rect width="5" height="5" x="3" y="16" rx="1"/><path d="M21 16h-3a2 2 0 0 0-2 2v3"/><path d="M21 21v.01"/><path d="M12 7v3a2 2 0 0 1-2 2H7"/><path d="M3 12h.01"/><path d="M12 3h.01"/><path d="M12 16v.01"/><path d="M16 12h1"/><path d="M21 12v.01"/><path d="M12 21v-1"/>',
  'copy': '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  'trash-2': '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
  'pencil': '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
  'edit-3': '<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>',
  'target': '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  'pie-chart': '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
  'bar-chart-2': '<line x1="18" x2="18" y1="20" y2="10"/><line x1="12" x2="12" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="14"/>',
  'bar-chart-3': '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
  'bar-chart': '<line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/>',
  'smartphone': '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>',
  'folder': '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 8 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  'folder-open': '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
  'folder-plus': '<path d="M12 10v6"/><path d="M9 13h6"/><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 8 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  'folders': '<path d="M2 11V4a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v5"/><path d="M4 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z"/>',
  'archive': '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
  'archive-restore': '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h2"/><path d="M20 8v11a2 2 0 0 1-2 2h-2"/><path d="m9 15 3-3 3 3"/><path d="M12 12v9"/>',
  'receipt': '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
  'trending-up': '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
  'trending-down': '<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
  'landmark': '<line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/>',
  'link': '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  'link-2': '<path d="M9 17H7A5 5 0 0 1 7 7h2"/><path d="M15 7h2a5 5 0 1 1 0 10h-2"/><line x1="8" x2="16" y1="12" y2="12"/>',
  'mail': '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
  'phone': '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
  'tag': '<path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z"/><circle cx="7" cy="7" r=".5" fill="currentColor"/>',
  'calendar': '<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
  'file-text': '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/>',
  'filter': '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  'info': '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  'triangle-alert': '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  'alert-circle': '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
  'alert-triangle': '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  'octagon-alert': '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
  'credit-card': '<rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/>',
  'activity': '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
  'building': '<rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M8 10h.01"/><path d="M16 10h.01"/><path d="M8 14h.01"/><path d="M16 14h.01"/>',
  'hand-coins': '<path d="M11 15h2a2 2 0 1 0 0-4h-3c-.6 0-1.1.2-1.4.6L3 17"/><path d="m7 21 1.6-1.4c.3-.4.8-.6 1.4-.6h4c1.1 0 2.1-.4 2.8-1.2l4.6-4.4a2 2 0 0 0-2.75-2.91l-4.2 3.9"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="6" r="3"/>',
  'inbox': '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  'mail-check': '<path d="M22 13V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v12c0 1.1.9 2 2 2h9"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/><path d="m16 19 2 2 4-4"/>',
  'key-round': '<path d="M2 18v3c0 .6.4 1 1 1h4v-3h3v-3h2l1.4-1.4a6.5 6.5 0 1 0-4-4Z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',
  'key': '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/><path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>',
  'piggy-bank': '<path d="M19 5c-1.5 0-2.8 1.4-3 2-3.5-1.5-11-.3-11 5 0 1.8 0 3 2 4.5V20h4v-2h3v2h4v-4c1-.5 1.7-1 2-2h2v-4h-2c0-1-.5-1.5-1-2V5z"/><path d="M2 9v1c0 1.1.9 2 2 2h1"/><circle cx="7" cy="11" r="1"/>',
  'lock': '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  'unlock': '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
  'eye': '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  'eye-off': '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/>',
  'clock': '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  'history': '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><polyline points="12 7 12 12 15 15"/>',
  'more-horizontal': '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
  'loader': '<line x1="12" x2="12" y1="2" y2="6"/><line x1="12" x2="12" y1="18" y2="22"/><line x1="4.93" x2="7.76" y1="4.93" y2="7.76"/><line x1="16.24" x2="19.07" y1="16.24" y2="19.07"/><line x1="2" x2="6" y1="12" y2="12"/><line x1="18" x2="22" y1="12" y2="12"/><line x1="4.93" x2="7.76" y1="19.07" y2="16.24"/><line x1="16.24" x2="19.07" y1="7.76" y2="4.93"/>',
  'loader-2': '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
  'scan-line': '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><line x1="7" x2="17" y1="12" y2="12"/>',
  'shopping-bag': '<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><line x1="3" x2="21" y1="6" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/>',
  'gift': '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13"/><path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7"/><path d="M7.5 8a2.5 2.5 0 0 1 0-5A4.8 8 0 0 1 12 8a4.8 8 0 0 1 4.5-5 2.5 2.5 0 0 1 0 5"/>',
  'coffee': '<path d="M17 8h1a4 4 0 1 1 0 8h-1"/><path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z"/><line x1="6" x2="6" y1="2" y2="4"/><line x1="10" x2="10" y1="2" y2="4"/><line x1="14" x2="14" y1="2" y2="4"/>',
  'home': '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
  'car': '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C2.1 10.7 2 11.3 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
  'plane': '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
  'heart': '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
  'tv': '<rect width="20" height="15" x="2" y="7" rx="2"/><polyline points="17 2 12 7 7 2"/>',
  'music': '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  'delete': '<path d="M20 5H9l-7 7 7 7h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2Z"/><line x1="18" x2="12" y1="9" y2="15"/><line x1="12" x2="18" y1="9" y2="15"/>'
};

PP.createSvgIcon = (name, extraClass = '', extraStyle = '') => {
  const path = PP.ICONS[name] || PP.ICONS['info'] || '';
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('class', `lucide lucide-${name} ${extraClass}`.trim());
  if (extraStyle) svg.setAttribute('style', extraStyle);
  svg.innerHTML = path;
  return svg;
};

PP.refreshIcons = () => {
  try {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
  } catch (e) {
    console.warn('[Lucide]', e);
  }
  
  // Fallback scanner to guarantee 100% SVG render even if CDN is offline or missed by library
  try {
    const unrendered = document.querySelectorAll('i[data-lucide]');
    unrendered.forEach(iEl => {
      const name = iEl.getAttribute('data-lucide');
      if (!name) return;
      const cls = iEl.className || '';
      const style = iEl.getAttribute('style') || '';
      const svg = PP.createSvgIcon(name, cls, style);
      if (iEl.parentNode) {
        iEl.parentNode.replaceChild(svg, iEl);
      }
    });
  } catch (e) {
    console.warn('[Icon Fallback]', e);
  }
};

PP.renderAuth = (container) => {
  if (!container) container = PP.$('#viewContainer');
  const appEl = document.getElementById('app');
  if (appEl) appEl.classList.add('auth-mode');
  const tpl = `
  <div class="auth-layout">
    <div class="auth-brand">
      <div class="auth-brand-logo">
        <div class="logo-mark">
          <svg viewBox="0 0 32 32" fill="none">
            <defs>
              <linearGradient id="agBg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                <stop stop-color="#0F172A"/>
                <stop offset="1" stop-color="#18132A"/>
              </linearGradient>
              <linearGradient id="agSpine" x1="0" y1="0" x2="0" y2="32">
                <stop stop-color="#818CF8"/>
                <stop offset="0.6" stop-color="#6366F1"/>
                <stop offset="1" stop-color="#06B6D4"/>
              </linearGradient>
              <linearGradient id="agLoop" x1="0" y1="0" x2="32" y2="16">
                <stop stop-color="#8B5CF6"/>
                <stop offset="1" stop-color="#EC4899"/>
              </linearGradient>
            </defs>
            <rect width="32" height="32" rx="9" fill="url(#agBg)" stroke="#6366F1" stroke-width="1" stroke-opacity="0.5"/>
            <rect x="9" y="8" width="3.6" height="16" rx="1.8" fill="url(#agSpine)"/>
            <path d="M10.8 8H19C21.76 8 24 10.24 24 13C24 15.76 21.76 18 19 18H10.8V14.6H19C19.88 14.6 20.6 13.88 20.6 13C20.6 12.12 19.88 11.4 19 11.4H10.8V8Z" fill="url(#agLoop)"/>
            <polygon points="14,15.5 20.8,15.5 17,21 13,21" fill="#38BDF8"/>
          </svg>
        </div>
        <div><h1>PocketPay</h1><p>Smart Pocket System</p></div>
      </div>
      <div class="auth-brand-content">
        <h2>Organize every rupee, across every pocket.</h2>
        <p>Create unlimited custom pockets, split income intelligently, and watch your savings grow with beautiful analytics.</p>
        <div class="auth-brand-features stagger">
          <div class="auth-feature">
            <div class="auth-feature-icon"><i data-lucide="wallet-cards"></i></div>
            <div><h4>Unlimited Custom Pockets</h4><p>Name, color, icon — completely your call.</p></div>
          </div>
          <div class="auth-feature">
            <div class="auth-feature-icon"><i data-lucide="pie-chart"></i></div>
            <div><h4>Smart Income Splits</h4><p>Percentages, fixed amounts, saved rules — all automatic.</p></div>
          </div>
          <div class="auth-feature">
            <div class="auth-feature-icon"><i data-lucide="shield-check"></i></div>
            <div><h4>Transaction PIN Security</h4><p>Every payment secured with a 4-digit PIN.</p></div>
          </div>
        </div>
      </div>
      <div class="auth-footnote">© ${new Date().getFullYear()} PocketPay. All rights reserved.</div>
    </div>
    <div class="auth-main">
      <div class="auth-main-inner">
        <div class="auth-top-toggle" role="tablist">
          <button id="tabLogin" class="active">Sign In</button>
          <button id="tabRegister">Create Account</button>
        </div>
        <div id="authFormWrapper"></div>
      </div>
    </div>
  </div>`;
  const topNav = document.getElementById('topNav');
  if (topNav) topNav.style.display = 'none';
  const botNav = document.querySelector('.bottom-nav');
  if (botNav) botNav.style.display = 'none';
  const sb = document.querySelector('.sidebar');
  if (sb) sb.style.display = 'none';
  container.innerHTML = tpl;
  PP.refreshIcons();
  PP.Auth.renderForm('login');
  PP.$('#tabLogin').onclick = () => { PP.$('#tabLogin').classList.add('active'); PP.$('#tabRegister').classList.remove('active'); PP.Auth.renderForm('login'); };
  PP.$('#tabRegister').onclick = () => { PP.$('#tabRegister').classList.add('active'); PP.$('#tabLogin').classList.remove('active'); PP.Auth.renderForm('register'); };
};

PP.showAppChrome = () => {
  const appEl = document.getElementById('app');
  if (appEl) appEl.classList.remove('auth-mode');
  const topNav = document.getElementById('topNav');
  if (topNav) topNav.style.display = '';
  const botNav = document.querySelector('.bottom-nav');
  if (botNav) botNav.style.display = '';
  const sb = document.querySelector('.sidebar');
  if (sb) sb.style.display = '';
};

PP.hideLoader = () => {
  const a = PP.$('#app'); a && a.classList.remove('hidden');
  const l = PP.$('#appLoader');
  l && l.classList.add('loaded');
  setTimeout(() => l && (l.style.display = 'none'), 500);
};

PP.setTheme = (theme) => {
  theme = (theme === 'light' ? 'light' : 'dark');
  document.documentElement.setAttribute('data-theme', theme);
  try { localStorage.setItem('pp:theme', theme); } catch {}
  PP.emit('theme:change', theme);
};

PP.initTheme = () => {
  let saved = null;
  try { saved = localStorage.getItem('pp:theme'); } catch {}
  let t = saved;
  if (!t) {
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    t = prefersDark ? 'dark' : 'light';
  }
  PP.setTheme(t);
  try {
    window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', (e) => {
      try {
        if (!localStorage.getItem('pp:theme')) PP.setTheme(e.matches ? 'dark' : 'light');
      } catch {}
    });
  } catch {}
};

PP.initRouter = () => {
  PP._routesReady = true;
  window.addEventListener('hashchange', () => {
    PP.handleRoute();
  });
  window.addEventListener('popstate', (e) => {
    if (e.state && e.state.route) {
      PP.state.currentRoute = e.state.route;
      PP.state.viewData = e.state.params || {};
      PP.renderView();
      PP.updateNavState();
    } else {
      PP.handleRoute();
    }
  });
};

PP.currentRoute = () => (PP.state.currentRoute || 'dashboard');

PP.handleRoute = () => {
  let hash = (window.location.hash || '#dashboard').replace(/^#/, '');
  if (!hash) hash = 'dashboard';
  const [route, ...rest] = hash.split('/');
  PP.state.currentRoute = route;
  PP.state.viewData = PP.state.viewData || {};
  if (!PP.state.initialized) {
    return;
  }
  PP.renderView();
  PP.updateNavState();
  PP.emit('pp:route', route);
};

PP.refreshCurrentView = () => {
  PP.renderView();
};

PP.refreshUserChrome = () => {
  const u = PP.state.user;
  if (!u) return;
  const initials = (u.full_name || u.email || 'U').trim().split(/\s+/).map(s => s[0]).filter(Boolean).slice(0, 2).join('').toUpperCase() || 'U';
  
  const topAvatar = PP.$('#avatarBtn .avatar');
  if (topAvatar) topAvatar.textContent = initials;
  
  const dropAvatar = PP.$('#dropAvatar');
  if (dropAvatar) dropAvatar.textContent = initials;
  
  const topName = PP.$('#topAvatarName');
  if (topName) topName.textContent = u.full_name || u.email || 'User';
  
  const topRole = PP.$('#topAvatarRole');
  if (topRole) topRole.textContent = u.is_admin ? 'Admin' : (u.is_premium ? 'Premium' : 'Standard');
  
  const adminLink = PP.$('#adminPortalLink');
  if (adminLink) {
    adminLink.style.display = u.is_admin ? 'flex' : 'none';
  }
  
  const dropName = PP.$('#dropName');
  if (dropName) dropName.textContent = u.full_name || 'User';
  
  const dropEmail = PP.$('#dropEmail');
  if (dropEmail) dropEmail.textContent = u.email || '';
  
  const notifBadge = PP.$('#notifBadge');
  if (notifBadge) {
    const unread = u.unread_notifications || 0;
    notifBadge.textContent = String(unread);
    notifBadge.classList.toggle('hidden', unread <= 0);
  }
};

PP.logout = async () => {
  try {
    try { await PP.Auth.logout(); } catch {}
    PP.state.user = null;
    PP.state.pockets = [];
    PP.state.transactions = [];
    PP.state.budgets = [];
    PP.state.notifications = [];
    PP.state.distributionRules = [];
    PP.state.initialized = false;
    try { localStorage.removeItem('pp:remember'); } catch {}
    PP.navigate('login');
    PP.renderAuth();
    PP.hideLoader();
  } catch (e) { console.warn(e); }
};

PP.bootstrap = async (afterAuth = false) => {
  try {
    const meRes = await PP.Auth.me();
    const user = meRes?.data?.user;
    if (!user) throw new Error('Not authenticated');
    PP.state.user = user;
    try {
      const [iconsRes, colorsRes] = await Promise.all([
        PP.MiscAPI.icons().catch(() => null),
        PP.MiscAPI.colors().catch(() => null),
      ]);
      PP.state.icons = iconsRes?.data?.icons || [];
      PP.state.colors = colorsRes?.data?.colors || [];
    } catch (e) { console.warn('icons/colors load failed', e); }
    try {
      const [pocketsRes, rulesRes, budgetsRes, notifRes, txRes] = await Promise.allSettled([
        PP.PocketsAPI.list({ archived: false, stats: true, per_page: 200 }),
        PP.WalletAPI.rules({ per_page: 200 }),
        PP.AnalyticsAPI.listBudgets(),
        PP.AnalyticsAPI.notifications({ limit: 20 }),
        PP.TxAPI.list({ per_page: 50 }),
      ]);
      if (pocketsRes.status === 'fulfilled') PP.state.pockets = pocketsRes.value?.data?.items || [];
      if (rulesRes.status === 'fulfilled') PP.state.distributionRules = rulesRes.value?.data?.items || rulesRes.value?.data || [];
      if (budgetsRes.status === 'fulfilled') PP.state.budgets = budgetsRes.value?.data?.items || budgetsRes.value?.data || [];
      if (notifRes.status === 'fulfilled') PP.state.notifications = notifRes.value?.data?.items || [];
      if (txRes.status === 'fulfilled') PP.state.transactions = txRes.value?.data?.items || [];
    } catch (e) { console.warn('state hydrate partial', e); }
    PP.state.initialized = true;
    PP.showAppChrome();
    if (!PP.state.currentRoute || PP.state.currentRoute === 'login') PP.state.currentRoute = 'dashboard';
    PP.renderView();
    PP.updateNavState();
    PP.refreshUserChrome();
    PP.hideLoader();
    PP.emit('bootstrap:done', PP.state.user);
  } catch (e) {
    PP.state.user = null;
    PP.state.initialized = false;
    PP.renderAuth();
    PP.hideLoader();
  }
};

PP.on('pockets:changed', async () => {
  try {
    const res = await PP.PocketsAPI.list({ archived: false, stats: true, per_page: 200 });
    PP.state.pockets = res?.data?.items || [];
    const meRes = await PP.Auth.me();
    if (meRes?.data?.user) PP.state.user = meRes.data.user;
    PP.refreshUserChrome();
  } catch (e) { console.warn(e); }
});

PP.on('transactions:changed', async () => {
  try {
    const meRes = await PP.Auth.me();
    if (meRes?.data?.user) PP.state.user = meRes.data.user;
    PP.refreshUserChrome();
  } catch (e) { console.warn(e); }
});


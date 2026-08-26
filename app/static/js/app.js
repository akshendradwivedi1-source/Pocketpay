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

PP.refreshIcons = () => { try { if (window.lucide) window.lucide.createIcons(); } catch (e) { console.warn(e); } };

PP.renderAuth = (container) => {
  if (!container) container = PP.$('#viewContainer');
  const appEl = document.getElementById('app');
  if (appEl) appEl.classList.add('auth-mode');
  const tpl = `
  <div class="auth-layout">
    <div class="auth-brand">
      <div class="auth-brand-logo">
        <div class="logo-mark">
          <svg viewBox="0 0 32 32" fill="none"><defs><linearGradient id="ag" x1="0" y1="0" x2="32" y2="32"><stop stop-color="#6366f1"/><stop offset="1" stop-color="#ec4899"/></linearGradient></defs><rect width="32" height="32" rx="9" fill="url(#ag)"/><path d="M9 20L14 15L17 18L23 11" stroke="white" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
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
  if (topRole) topRole.textContent = u.is_premium ? 'Premium' : 'Standard';
  
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


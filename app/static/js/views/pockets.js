// ========== Pockets View ==========
PP.Pockets = {
  async render(container, params) {
    container.innerHTML = '';
    const wrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.5rem' });
    container.appendChild(wrap);

    const showArchived = PP.state.viewData?.archived || false;
    wrap.appendChild(PP.el('div', { class: 'page-header' }, [
      PP.el('div', {}, [
        PP.el('p', { class: 'page-eyebrow' }, ['Organizer']),
        PP.el('h2', { class: 'page-title' }, [`Smart Pockets`]),
        PP.el('p', { class: 'page-sub' }, [`${showArchived ? 'Archived pockets' : 'Create unlimited pockets, drag to reorder, and track every rupee.'}`]),
      ]),
      PP.el('div', { class: 'page-actions' }, [
        PP.el('button', {
          class: `btn ${showArchived ? 'btn-outline' : 'btn-ghost'}`,
          onclick: () => { PP.state.viewData = { archived: !showArchived }; PP.Pockets.render(container); },
        }, [PP.el('i', { 'data-lucide': showArchived ? 'folders' : 'archive' }), showArchived ? 'Active' : 'Archived']),
        PP.el('button', {
          class: 'btn btn-primary glow-pulse',
          onclick: () => PP.Modals.createPocket(),
        }, [PP.el('i', { 'data-lucide': 'folder-plus' }), 'New Pocket']),
      ]),
    ]));

    // toolbar
    const toolbar = PP.el('div', { class: 'toolbar' }, [
      PP.el('div', { class: 'toolbar-chips' }, [
        PP.el('span', { class: 'chip active', 'data-sort': 'sort_order' }, ['Custom Order']),
        PP.el('span', { class: 'chip', 'data-sort': 'balance' }, ['By Balance']),
        PP.el('span', { class: 'chip', 'data-sort': 'name' }, ['A → Z']),
        PP.el('span', { class: 'chip', 'data-sort': 'spent' }, ['By Spent']),
      ]),
      PP.el('div', { class: 'toolbar-right' }, [
        PP.el('div', { class: 'toolbar-search' }, [
          PP.el('i', { 'data-lucide': 'search', style: 'width:14px;height:14px' }),
          Object.assign(PP.el('input', { placeholder: 'Search pockets…', type: 'search' }), {
            oninput: (e) => PP.Pockets.applyFilter(e.target.value),
          }),
        ]),
        PP.el('button', {
          class: 'btn btn-ghost btn-sm',
          onclick: () => PP.Modals.reorderPockets(),
          title: 'Reorder pockets',
        }, [PP.el('i', { 'data-lucide': 'arrow-up-down' })]),
      ]),
    ]);
    wrap.appendChild(toolbar);
    setTimeout(() => PP.$$('.toolbar-chips .chip').forEach(c => c.onclick = () => {
      PP.$$('.toolbar-chips .chip').forEach(x => x.classList.remove('active'));
      c.classList.add('active');
      PP.Pockets.applySort(c.dataset.sort);
    }), 0);

    const listWrap = PP.el('div', { id: 'pocketsListContainer' });
    wrap.appendChild(listWrap);

    try {
      const res = await PP.PocketsAPI.list({ archived: showArchived, stats: true, per_page: 200 });
      PP.state.pockets = res?.data?.items || [];
      const summary = res?.data?.summary || {};

      if (!PP.state.pockets.length && !showArchived) {
        listWrap.appendChild(PP.el('div', { class: 'empty-state' }, [
          PP.el('div', { class: 'empty-icon' }, [PP.el('i', { 'data-lucide': 'folder-plus' })]),
          PP.el('h3', {}, ['No pockets yet']),
          PP.el('p', {}, ['Create your first pocket to start organizing your finances the smart way.']),
          PP.el('div', { style: 'display:flex;gap:.75rem;margin-top:1.25rem;flex-wrap:wrap;justify-content:center' }, [
            PP.el('button', { class: 'btn btn-primary', onclick: () => PP.Modals.createPocket() }, [PP.el('i', { 'data-lucide': 'plus' }), 'Create Pocket']),
            PP.el('button', { class: 'btn btn-ghost', onclick: () => PP.Pockets.createStarterSet() }, [PP.el('i', { 'data-lucide': 'sparkles' }), 'Add Starter Set']),
          ]),
        ]));
        PP.refreshIcons();
        return;
      }

      PP.Pockets.renderGrid(listWrap, PP.state.pockets);
    } catch (e) { PP.UI.toast('Could not load pockets', e.message, 'error'); }
  },

  renderGrid(container, pockets) {
    container.innerHTML = '';
    const grid = PP.el('div', { class: 'pockets-grid stagger', id: 'pocketsGrid' });
    pockets.forEach((p, idx) => {
      const card = PP.Pockets.renderPocketCardFull(p, idx);
      grid.appendChild(card);
    });
    if (!PP.state.viewData?.archived) {
      grid.appendChild(PP.el('div', { class: 'add-pocket-card', onclick: () => PP.Modals.createPocket() }, [
        PP.el('div', { class: 'add-pocket-icon' }, [PP.el('i', { 'data-lucide': 'plus' })]),
        PP.el('span', {}, ['Add Pocket']),
      ]));
    }
    container.appendChild(grid);
    PP.Pockets.attachDrag(grid);
    PP.refreshIcons();
  },

  renderPocketCardFull(p, idx) {
    const vars = PP.UI.pocketStyleVars(p);
    const usage = p.budget_usage_percent || 0;
    const card = PP.el('div', {
      class: `pocket-card glass-card ${p.archived ? 'archived' : ''}`,
      style: Object.entries(vars).map(([k, v]) => `${k}:${v}`).join(';'),
      'data-id': p.id,
      draggable: !p.archived,
      onclick: () => PP.Pockets.openDetail(p.id),
    });
    card.innerHTML = `
      <div class="pocket-card-bg"></div>
      <div class="pocket-card-inner">
        <div class="pocket-card-top">
          <div class="pocket-icon-wrap"><i data-lucide="${p.icon || 'wallet'}"></i></div>
          <button class="pocket-menu-btn" data-id="${p.id}" aria-label="Pocket actions">
            <i data-lucide="more-horizontal"></i>
          </button>
        </div>
        <div class="pocket-card-name">${p.name}</div>
        ${p.description ? `<div class="pocket-card-desc">${p.description.slice(0, 50)}${p.description.length > 50 ? '…' : ''}</div>` : ''}
        <div class="pocket-card-balance">
          <div class="pocket-balance-label">Balance</div>
          <div class="pocket-balance-value">${PP.fmt(p.current_balance)}</div>
        </div>
        ${(p.monthly_limit || p.budget_amount) ? `
          <div class="pocket-progress"><div class="pocket-progress-fill" style="width:${Math.min(100, usage)}%"></div></div>
          <div class="pocket-meta">
            <span>${usage.toFixed(0)}% used</span>
            <span>${p.archived ? 'Archived' : (PP.fmt(p.monthly_limit || p.budget_amount)) + ' limit'}</span>
          </div>` : (p.archived ? `<div class="pocket-meta"><span>Archived</span><span>${PP.formatDate(p.archived_at)}</span></div>` : '')}
      </div>`;
    setTimeout(() => {
      const btn = card.querySelector('.pocket-menu-btn');
      if (btn) btn.addEventListener('click', ev => { ev.stopPropagation(); PP.Modals.pocketActions(p); });
    }, 0);
    return card;
  },

  attachDrag(grid) {
    let dragged = null;
    grid.addEventListener('dragstart', (e) => {
      const t = e.target.closest('.pocket-card');
      if (!t || t.classList.contains('archived')) return;
      dragged = t;
      t.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    grid.addEventListener('dragover', (e) => {
      e.preventDefault();
      const t = e.target.closest('.pocket-card');
      if (t && t !== dragged && !t.classList.contains('archived')) t.classList.add('drag-over');
    });
    grid.addEventListener('dragleave', (e) => {
      const t = e.target.closest('.pocket-card');
      if (t) t.classList.remove('drag-over');
    });
    grid.addEventListener('drop', async (e) => {
      e.preventDefault();
      const t = e.target.closest('.pocket-card');
      grid.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
      if (!dragged || !t || t === dragged) return;
      const cards = Array.from(grid.querySelectorAll('.pocket-card'));
      const from = cards.indexOf(dragged);
      const to = cards.indexOf(t);
      cards.splice(from, 1);
      cards.splice(to, 0, dragged);
      cards.forEach(c => grid.appendChild(c));
      dragged.classList.remove('dragging');
      const newOrder = cards.filter(c => !c.classList.contains('archived')).map(c => Number(c.dataset.id));
      try { await PP.PocketsAPI.reorder(newOrder); PP.UI.toast('Order saved', '', 'success'); }
      catch (err) { PP.UI.toast('Could not reorder', err.message, 'error'); }
      dragged = null;
    });
    grid.addEventListener('dragend', () => {
      grid.querySelectorAll('.dragging, .drag-over').forEach(el => el.classList.remove('dragging', 'drag-over'));
      dragged = null;
    });
  },

  applyFilter(q) {
    q = (q || '').toLowerCase().trim();
    const grid = PP.$('#pocketsGrid');
    if (!grid) return;
    PP.$$('.pocket-card', grid).forEach(card => {
      const name = card.querySelector('.pocket-card-name')?.textContent.toLowerCase() || '';
      const desc = card.querySelector('.pocket-card-desc')?.textContent.toLowerCase() || '';
      const show = !q || name.includes(q) || desc.includes(q);
      card.style.display = show ? '' : 'none';
    });
  },

  applySort(sortKey) {
    const pockets = [...PP.state.pockets];
    if (sortKey === 'balance') pockets.sort((a, b) => b.current_balance - a.current_balance);
    else if (sortKey === 'name') pockets.sort((a, b) => a.name.localeCompare(b.name));
    else if (sortKey === 'spent') pockets.sort((a, b) => b.total_spent - a.total_spent);
    else pockets.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    const cont = PP.$('#pocketsListContainer');
    if (cont) PP.Pockets.renderGrid(cont, pockets);
  },

  async createStarterSet() {
    const preset = [
      { name: 'Savings', icon: 'piggy-bank', color: '#22c55e', budget: 50000, monthly: 10000, initial: 5000, desc: 'Long-term savings & goals' },
      { name: 'Food', icon: 'utensils', color: '#f97316', budget: 12000, monthly: 12000, initial: 2500, desc: 'Meals, groceries & snacks' },
      { name: 'Rent', icon: 'home', color: '#6366f1', budget: 0, monthly: 25000, initial: 0, desc: 'Monthly rent & maintenance' },
      { name: 'Entertainment', icon: 'gamepad-2', color: '#ec4899', budget: 5000, monthly: 5000, initial: 1500, desc: 'Fun, games & subscriptions' },
      { name: 'Transport', icon: 'car', color: '#0ea5e9', budget: 6000, monthly: 6000, initial: 1800, desc: 'Commute & travel' },
    ];
    const yes = await PP.UI.confirm('Create Starter Pockets?', 'This will create 5 pre-configured pockets with suggested budgets.');
    if (!yes) return;
    const created = [];
    for (const p of preset) {
      try {
        const res = await PP.PocketsAPI.create({
          name: p.name, description: p.desc, color: p.color, icon: p.icon,
          budget_amount: p.budget, monthly_limit: p.monthly, initial_balance: p.initial,
        });
        if (res?.success) created.push(p.name);
      } catch (e) { console.warn(e); }
    }
    PP.UI.toast(`${created.length} pockets created`, created.join(', '), 'success');
    PP.navigate('pockets');
  },

  async openDetail(id) {
    try {
      const res = await PP.PocketsAPI.get(id);
      if (!res?.success) return;
      const p = res.data.pocket;
      const txs = res.data.recent_transactions || [];
      PP.navigate('pocket-detail', { pocket: p, transactions: txs });
      PP.Pockets.renderDetail(PP.$('#viewContainer'), p, txs);
    } catch (e) { PP.UI.toast('Could not open pocket', e.message, 'error'); }
  },

  renderDetail(container, p, txs = []) {
    if (p && !p.id && p.pocket) { const viewData = p; p = viewData.pocket; txs = viewData.transactions || []; }
    if (!p || !p.id) { PP.navigate('pockets'); return; }
    container.innerHTML = '';
    const vars = PP.UI.pocketStyleVars(p);
    const darken = p.color;
    const lighter = PP.UI.hexToRgba(p.color, .6);
    const wrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.5rem' });
    container.appendChild(wrap);
    wrap.appendChild(PP.el('button', {
      class: 'btn btn-ghost btn-sm', style: 'align-self:flex-start',
      onclick: () => PP.navigate('pockets'),
    }, [PP.el('i', { 'data-lucide': 'arrow-left' }), 'Back to Pockets']));

    const header = PP.el('div', {
      class: 'pocket-detail-header',
      style: `--pd-color-1:${darken};--pd-color-2:${lighter};`,
    });
    header.innerHTML = `
      <div class="pd-content">
        <div class="pd-top">
          <div class="pd-title-wrap">
            <div class="pd-icon"><i data-lucide="${p.icon || 'wallet'}"></i></div>
            <div>
              <div class="pd-title">${p.name}</div>
              ${p.description ? `<div class="pd-desc">${p.description}</div>` : ''}
            </div>
          </div>
          <div class="pd-actions">
            <button class="btn btn-outline" style="background:rgba(255,255,255,.08);color:white;border-color:rgba(255,255,255,.2)" onclick='PP.Modals.addIncomeForPocket(${p.id})'><i data-lucide="plus"></i> Deposit</button>
            <button class="btn btn-outline" style="background:rgba(255,255,255,.08);color:white;border-color:rgba(255,255,255,.2)" onclick='PP.Modals.addExpenseForPocket(${p.id})'><i data-lucide="minus"></i> Pay</button>
            <button class="btn btn-outline" style="background:rgba(255,255,255,.08);color:white;border-color:rgba(255,255,255,.2)" onclick='PP.Modals.transfer({ fromPocketId: ${p.id} })'><i data-lucide="refresh-ccw"></i> Transfer</button>
            <button class="btn btn-ghost" style="background:rgba(255,255,255,.08);color:white;border-color:rgba(255,255,255,.2)" onclick='PP.Modals.pocketActions(${JSON.stringify(p).replace(/"/g, "&quot;")})'><i data-lucide="more-horizontal"></i></button>
          </div>
        </div>
        <div class="pd-balance">
          <div class="pd-balance-label">Current Balance</div>
          <div class="pd-balance-value">${PP.fmt(p.current_balance)}</div>
        </div>
        <div class="pd-stats">
          <div class="pd-stat"><div class="pd-stat-label">Total Received</div><div class="pd-stat-value">${PP.fmt(p.total_received || 0)}</div></div>
          <div class="pd-stat"><div class="pd-stat-label">Total Spent</div><div class="pd-stat-value">${PP.fmt(p.total_spent || 0)}</div></div>
          <div class="pd-stat"><div class="pd-stat-label">Monthly Spent</div><div class="pd-stat-value">${PP.fmt(p.monthly_spending || 0)}</div></div>
          <div class="pd-stat"><div class="pd-stat-label">Priority</div><div class="pd-stat-value">${p.priority || 0}/5</div></div>
        </div>
      </div>`;
    wrap.appendChild(header);

    const grid = PP.el('div', { class: 'three-col-grid' });
    const budgetCard = PP.el('div', { class: 'section-card' }, [
      PP.el('h3', { style: 'font-size:1rem;font-weight:700;margin-bottom:.75rem' }, [PP.el('i', { 'data-lucide': 'target', style: 'display:inline;margin-right:.45rem;color:var(--accent)' }), 'Budget']),
      PP.el('div', { class: 'savings-gauge' }, [
        (() => {
          const limit = p.monthly_limit || p.budget_amount || 0;
          const used = p.monthly_spending || 0;
          const pct = Math.min(100, limit ? (used / limit) * 100 : 0);
          const wrap = PP.el('div');
          wrap.innerHTML = `<svg viewBox="0 0 220 120">
            <defs><linearGradient id="gaugeGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#22c55e"/><stop offset="60%" stop-color="#f59e0b"/><stop offset="100%" stop-color="#ef4444"/>
            </linearGradient></defs>
            <path class="gauge-track" d="M 20 100 A 90 90 0 0 1 200 100"/>
            <path class="gauge-fill" stroke-dasharray="282.7" stroke-dashoffset="${282.7 * (1 - pct / 100)}" d="M 20 100 A 90 90 0 0 1 200 100"/>
          </svg>`;
          return wrap;
        })(),
        PP.el('div', { class: 'gauge-value' }, [
          PP.el('div', { class: 'label' }, ['Used of Limit']),
          PP.el('div', { class: 'num' }, [`${Math.min(100, (p.budget_usage_percent || 0)).toFixed(0)}%`]),
        ]),
      ]),
      PP.el('div', { style: 'margin-top:1rem;display:flex;justify-content:space-between;font-size:.85rem' }, [
        PP.el('span', { class: 'text-muted' }, ['Remaining']),
        PP.el('span', { style: 'font-weight:700' }, [PP.fmt(Math.max(0, (p.monthly_limit || p.budget_amount || 0) - (p.monthly_spending || 0)))]),
      ]),
    ]);
    const infoCard = PP.el('div', { class: 'section-card' }, [
      PP.el('h3', { style: 'font-size:1rem;font-weight:700;margin-bottom:.75rem' }, [PP.el('i', { 'data-lucide': 'info', style: 'display:inline;margin-right:.45rem;color:var(--accent-3)' }), 'Details']),
      PP.el('div', { style: 'display:flex;flex-direction:column;gap:.75rem' }, [
        PP.el('div', { class: 'flex justify-between' }, [PP.el('span', { class: 'text-muted' }, ['Budget']), PP.el('b', {}, [PP.fmt(p.budget_amount || 0)])]),
        PP.el('div', { class: 'flex justify-between' }, [PP.el('span', { class: 'text-muted' }, ['Monthly Limit']), PP.el('b', {}, [PP.fmt(p.monthly_limit || 0)])]),
        PP.el('div', { class: 'flex justify-between' }, [PP.el('span', { class: 'text-muted' }, ['Sort Order']), PP.el('b', {}, [String(p.sort_order || 0)])]),
        PP.el('div', { class: 'flex justify-between' }, [PP.el('span', { class: 'text-muted' }, ['Created']), PP.el('b', {}, [PP.formatDate(p.created_at)])]),
      ]),
    ]);
    const qrCard = PP.el('div', { class: 'section-card' }, [
      PP.el('h3', { style: 'font-size:1rem;font-weight:700;margin-bottom:.75rem' }, [PP.el('i', { 'data-lucide': 'qr-code', style: 'display:inline;margin-right:.45rem;color:var(--success)' }), 'Pocket QR']),
      PP.el('div', { style: 'text-align:center;padding:1rem;background:var(--surface);border-radius:var(--radius-lg);border:1px solid var(--border)' }, [
        (() => {
          const wrap = PP.el('div');
          PP.MiscAPI.generateQR(`pocketpay://pocket/${p.id}`, 180).then(res => {
            if (res?.data?.qr_code_url) wrap.innerHTML = `<img src="${res.data.qr_code_url}" alt="QR" style="width:180px;height:180px;margin:0 auto;border-radius:var(--radius-md)"><p style="margin-top:.75rem;font-size:.8rem;color:var(--text-muted)">Scan to view pocket</p>`;
          }).catch(() => wrap.innerHTML = '<p style="padding:2rem">Loading QR…</p>');
          return wrap;
        })(),
      ]),
    ]);
    grid.append(budgetCard, infoCard, qrCard);
    wrap.appendChild(grid);

    // Recent transactions
    const txCard = PP.el('div', { class: 'section-card' }, [
      PP.el('div', { class: 'section-title' }, [
        PP.el('h3', {}, [PP.el('i', { 'data-lucide': 'history', style: 'display:inline;margin-right:.5rem' }), `Recent Activity in ${p.name}`]),
        PP.el('button', { onclick: () => PP.navigate('transactions', { pocket_id: p.id }) }, ['All txns', PP.el('i', { 'data-lucide': 'arrow-right' })]),
      ]),
    ]);
    if (!txs.length) {
      txCard.appendChild(PP.el('div', { class: 'empty-state' }, [
        PP.el('div', { class: 'empty-icon' }, [PP.el('i', { 'data-lucide': 'receipt' })]),
        PP.el('h3', {}, ['No activity yet']),
      ]));
    } else {
      const l = PP.el('div', { class: 'tx-list' });
      const grouped = PP.Transactions.groupByDay(txs);
      Object.entries(grouped).forEach(([date, items]) => {
        l.appendChild(PP.el('div', { class: 'tx-day-header' }, [date]));
        items.forEach(t => l.appendChild(PP.Transactions.renderRow(t)));
      });
      txCard.appendChild(l);
    }
    wrap.appendChild(txCard);
    PP.refreshIcons();
  },
};

PP.renderPocketCardFull = PP.Pockets.renderPocketCardFull;

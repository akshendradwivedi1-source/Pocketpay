// ========== Transactions View ==========
PP.formatTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
};

PP.Transactions = {
  async render(container, params) {
    container.innerHTML = '';
    const wrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.5rem' });
    container.appendChild(wrap);

    const pocketId = params?.pocket_id;
    const fType = params?.type || '';

    wrap.appendChild(PP.el('div', { class: 'page-header' }, [
      PP.el('div', {}, [
        PP.el('p', { class: 'page-eyebrow' }, ['Ledger']),
        PP.el('h2', { class: 'page-title' }, ['Transactions']),
        PP.el('p', { class: 'page-sub' }, [pocketId ? `Filtered by pocket · All time` : 'Every rupee in and out of your pockets.']),
      ]),
      PP.el('div', { class: 'page-actions' }, [
        PP.el('button', { class: 'btn btn-outline', onclick: () => PP.Modals.addExpense() }, [PP.el('i', { 'data-lucide': 'arrow-up-right' }), 'Expense']),
        PP.el('button', { class: 'btn btn-primary', onclick: () => PP.Modals.addIncome() }, [PP.el('i', { 'data-lucide': 'arrow-down-left' }), 'Income']),
      ]),
    ]));

    const toolbar = PP.el('div', { class: 'toolbar' });
    const chips = PP.el('div', { class: 'toolbar-chips' });
    [
      ['all', 'All'],
      ['expense', 'Expenses'],
      ['income', 'Income'],
      ['peer_send,peer_receive', 'P2P / Peer'],
      ['transfer', 'Transfers'],
      ['topup,withdraw,refund', 'Other'],
    ].forEach(([v, l]) => {
      const c = PP.el('span', { class: `chip ${fType === v ? 'active' : ''}`, 'data-filter': v }, [l]);
      c.onclick = () => PP.Transactions.setFilter('type', v);
      chips.appendChild(c);
    });
    const right = PP.el('div', { class: 'toolbar-right' });
    const search = PP.el('div', { class: 'toolbar-search' });
    search.innerHTML = `<i data-lucide="search" style="width:14px;height:14px"></i><input placeholder="Search…" />`;
    const inp = search.querySelector('input');
    inp.oninput = PP.debounce(() => PP.Transactions.loadList({ search: inp.value }), 300);
    right.appendChild(search);
    const exportBtn = PP.el('button', {
      class: 'btn btn-ghost btn-sm',
      onclick: async () => {
        try {
          const res = await PP.TxAPI.list({ per_page: 500 });
          const items = res?.data?.items || [];
          if (!items.length) return PP.UI.toast('Export', 'No transactions found to export', 'info');
          const headers = ['Transaction ID', 'Date', 'Type', 'Category', 'Merchant', 'Amount', 'Currency', 'Status', 'From Pocket', 'To Pocket', 'Description'];
          const rows = items.map(t => [
            t.transaction_id || t.id,
            t.created_at,
            t.type,
            `"${(t.category || '').replace(/"/g, '""')}"`,
            `"${(t.merchant || '').replace(/"/g, '""')}"`,
            t.amount,
            t.currency || 'INR',
            t.status,
            `"${(t.from_pocket?.name || '').replace(/"/g, '""')}"`,
            `"${(t.to_pocket?.name || '').replace(/"/g, '""')}"`,
            `"${(t.description || '').replace(/"/g, '""')}"`
          ]);
          const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
          const encodedUri = encodeURI(csvContent);
          const link = document.createElement('a');
          link.setAttribute('href', encodedUri);
          link.setAttribute('download', `pocketpay_transactions_${new Date().toISOString().slice(0, 10)}.csv`);
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          PP.UI.toast('Export Complete', 'Transactions downloaded as CSV', 'success');
        } catch (e) {
          PP.UI.toast('Export Failed', e.message, 'error');
        }
      }
    }, [PP.el('i', { 'data-lucide': 'download' }), 'CSV']);
    right.appendChild(exportBtn);
    toolbar.append(chips, right);
    wrap.appendChild(toolbar);

    const listWrap = PP.el('div', { id: 'txsContainer', class: 'section-card' });
    listWrap.appendChild(PP.el('div', { class: 'skeleton', style: 'height:360px;width:100%' }));
    wrap.appendChild(listWrap);

    const summaryWrap = PP.el('div', { class: 'stats-grid stagger' });
    wrap.insertBefore(summaryWrap, toolbar.nextSibling);
    PP.Transactions.loadSummary(summaryWrap);
    PP.Transactions.state = { pocketId, type: fType, search: '', page: 1 };
    PP.Transactions.loadList();
    PP.refreshIcons();
  },

  state: {},

  async loadSummary(container) {
    try {
      const res = await PP.AnalyticsAPI.overview();
      const d = res?.data || {};
      const items = [
        { label: 'Income (MoM)', value: PP.fmt(d.current_month?.income || 0), icon: 'arrow-down-left', cls: 'income', delta: d.month_over_month?.income_change_pct, up: d.month_over_month?.income_increased },
        { label: 'Spent (MoM)', value: PP.fmt(d.current_month?.expense || 0), icon: 'arrow-up-right', cls: 'expense', delta: d.month_over_month?.expense_change_pct, up: !d.month_over_month?.expense_increased, inv: true },
        { label: 'Net Saved', value: PP.fmt(d.current_month?.net_savings || 0), icon: 'wallet', cls: 'savings', delta: d.month_over_month?.savings_change_pct, up: d.month_over_month?.savings_increased },
        { label: 'Savings Rate', value: `${d.current_month?.savings_rate || 0}%`, icon: 'target', cls: 'pockets', delta: d.balances?.pockets_count || 0, up: true, deltaIsCount: true },
      ];
      container.innerHTML = '';
      items.forEach(s => {
        const delta = s.deltaIsCount ? `${s.delta} pockets` : (s.delta == null ? '—' : `${Math.abs(s.delta)}% ${s.up ? '↑' : '↓'}`);
        const cls = s.inv ? (s.up ? 'up' : 'down') : (s.up ? 'up' : 'down');
        container.appendChild(PP.el('div', { class: 'stat-card glass-card' }, [
          PP.el('div', { class: `stat-icon ${s.cls}` }, [PP.el('i', { 'data-lucide': s.icon })]),
          PP.el('div', { class: 'stat-label' }, [s.label]),
          PP.el('div', { class: 'stat-value' }, [s.value]),
          PP.el('div', { class: `stat-change ${cls}` }, [PP.el('i', { 'data-lucide': s.up ? 'trending-up' : 'trending-down' }), delta]),
        ]));
      });
      PP.refreshIcons();
    } catch (e) { console.warn(e); }
  },

  async loadList(extraParams = {}) {
    const cont = PP.$('#txsContainer');
    if (!cont) return;
    Object.assign(PP.Transactions.state, extraParams);
    const s = PP.Transactions.state;
    cont.innerHTML = `<div class="skeleton" style="height:360px;width:100%"></div>`;
    try {
      const params = { per_page: 25, page: s.page };
      if (s.type && s.type !== 'all') params.type = s.type;
      if (s.pocketId) params.pocket_id = s.pocketId;
      if (s.search) params.search = s.search;
      const res = await PP.TxAPI.list(params);
      const items = res?.data?.items || [];
      const summary = res?.data?.summary || {};
      cont.innerHTML = '';
      cont.appendChild(PP.el('div', { class: 'section-title' }, [
        PP.el('h3', {}, ['All Transactions']),
        PP.el('div', { style: 'display:flex;gap:.75rem;align-items:center' }, [
          PP.el('span', { class: 'chip success' }, [`+${PP.fmt(summary.total_income || 0)} in`]),
          PP.el('span', { class: 'chip danger' }, [`-${PP.fmt(summary.total_expense || 0)} out`]),
          PP.el('span', { class: 'chip' }, [`${summary.total_count || items.length} total`]),
        ]),
      ]));
      if (!items.length) {
        cont.appendChild(PP.el('div', { class: 'empty-state' }, [
          PP.el('div', { class: 'empty-icon' }, [PP.el('i', { 'data-lucide': 'receipt' })]),
          PP.el('h3', {}, ['No transactions found']),
          PP.el('p', {}, [s.search ? `No results for "${s.search}".` : 'Create your first transaction to get started.']),
        ]));
      } else {
        const grouped = PP.Transactions.groupByDay(items);
        const list = PP.el('div', { class: 'tx-list' });
        Object.entries(grouped).forEach(([day, dayItems]) => {
          const dayTotals = dayItems.reduce((acc, t) => {
            if (t.type === 'expense') acc.out += t.amount;
            else if (t.type === 'income' || t.type === 'topup' || t.type === 'refund') acc.in += t.amount;
            return acc;
          }, { in: 0, out: 0 });
          list.appendChild(PP.el('div', { class: 'tx-day-header' }, [
            day,
            PP.el('span', { style: 'display:flex;gap:.5rem' }, [
              dayTotals.in > 0 ? PP.el('span', { class: 'chip success' }, [`+${PP.fmt(dayTotals.in)}`]) : null,
              dayTotals.out > 0 ? PP.el('span', { class: 'chip danger' }, [`-${PP.fmt(dayTotals.out)}`]) : null,
            ]),
          ]));
          dayItems.forEach(t => list.appendChild(PP.Transactions.renderRow(t)));
        });
        cont.appendChild(list);
      }
      PP.refreshIcons();
    } catch (e) { PP.UI.toast('Error loading', e.message, 'error'); }
  },

  setFilter(key, value) {
    PP.$$('.toolbar-chips .chip').forEach(x => x.classList.toggle('active', x.dataset.filter === value));
    PP.Transactions.loadList({ [key]: value, page: 1 });
  },

  groupByDay(txs) {
    const groups = {};
    txs.forEach(t => {
      const d = new Date(t.created_at);
      const today = new Date();
      const y = new Date(); y.setDate(y.getDate() - 1);
      let key = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
      if (d.toDateString() === today.toDateString()) key = `Today · ${key}`;
      else if (d.toDateString() === y.toDateString()) key = `Yesterday · ${key}`;
      (groups[key] = groups[key] || []).push(t);
    });
    return groups;
  },

  renderRow(t) {
    const isExpense = t.type === 'expense';
    const isIncome = ['income', 'topup', 'refund'].includes(t.type);
    const isTransfer = t.type === 'transfer';
    const icon = isExpense ? 'arrow-up-right' : (isIncome ? 'arrow-down-left' : 'refresh-ccw');
    const iconClass = isExpense ? 'expense' : (isIncome ? 'income' : 'transfer');
    const amountCls = isIncome ? 'income' : 'expense';
    const amountSign = isIncome ? '+' : (isExpense ? '-' : '');
    const pocket = t.from_pocket || t.to_pocket;

    const row = PP.el('div', { class: 'tx-item', onclick: () => PP.Modals.transactionDetail(t) });
    row.innerHTML = `
      <div class="tx-icon ${iconClass}"><i data-lucide="${icon}"></i></div>
      <div class="tx-info">
        <div class="tx-title">${t.merchant || t.category || (isTransfer ? 'Transfer' : (isIncome ? 'Money Received' : 'Payment'))}</div>
        <div class="tx-sub">
          ${pocket ? `<span class="tx-pocket-chip" style="--chip-color:${pocket.color || '#6366f1'}">${pocket.name}</span>` : ''}
          <span>${t.category || t.type}</span>
          <span>${PP.formatTimeAgo(t.created_at)}</span>
        </div>
      </div>
      <div class="tx-right">
        <div class="tx-amount ${amountCls}">${amountSign}${PP.fmt(t.amount).replace('₹', '₹')}</div>
        <div class="tx-time">${PP.formatTime(t.created_at)}</div>
        ${t.status !== 'completed' ? `<div class="tx-status-chip ${t.status}">${t.status}</div>` : ''}
      </div>
    `;
    return row;
  },

  categoryIcon(category) {
    const map = {
      'Food & Dining': 'utensils',
      'Shopping': 'shopping-bag',
      'Transportation': 'car',
      'Entertainment': 'gamepad-2',
      'Bills & Utilities': 'zap',
      'Healthcare': 'heart-pulse',
      'Education': 'graduation-cap',
      'Groceries': 'shopping-cart',
      'Rent': 'home',
      'Insurance': 'shield-check',
      'Investments': 'line-chart',
      'Subscriptions': 'repeat',
      'Gifts & Donations': 'gift',
      'Sports & Fitness': 'dumbbell',
      'Travel': 'plane',
      'Gaming': 'gamepad-2',
      'Salary': 'briefcase',
    };
    for (const k of Object.keys(map)) if (category?.includes(k)) return map[k];
    return 'wallet';
  },
};

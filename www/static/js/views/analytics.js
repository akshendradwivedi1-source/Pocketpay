// ========== Analytics / Budgets View ==========
PP.Analytics = {
  async render(container, params) {
    container.innerHTML = '';
    const wrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.5rem' });
    container.appendChild(wrap);

    wrap.appendChild(PP.el('div', { class: 'page-header' }, [
      PP.el('div', {}, [
        PP.el('p', { class: 'page-eyebrow' }, ['Insights']),
        PP.el('h2', { class: 'page-title' }, ['Analytics & Reports']),
        PP.el('p', { class: 'page-sub' }, ['Deep dive into your spending patterns, income, and savings habits.']),
      ]),
      PP.el('div', { class: 'page-actions' }, [
        PP.el('select', {
          class: 'form-input', style: 'width:auto;padding:.6rem .9rem',
          id: 'analPeriod',
          onchange: () => PP.Analytics.loadPeriod(),
        }, [
          PP.el('option', { value: '1' }, ['Last 30 days']),
          PP.el('option', { value: '3' }, ['Last 90 days']),
          PP.el('option', { value: '6' }, ['Last 6 months']),
          PP.el('option', { value: '12' }, ['Last 12 months']),
        ]),
      ]),
    ]));

    // Summary
    const summaryGrid = PP.el('div', { class: 'stats-grid stagger' });
    wrap.appendChild(summaryGrid);
    PP.AnalyticsAPI.overview().then(res => {
      const d = res?.data || {};
      const cards = [
        { label: 'Income', value: PP.fmt(d.current_month?.income || 0), icon: 'trending-up', cls: 'income', delta: d.month_over_month?.income_change_pct, up: d.month_over_month?.income_increased },
        { label: 'Expense', value: PP.fmt(d.current_month?.expense || 0), icon: 'trending-down', cls: 'expense', delta: d.month_over_month?.expense_change_pct, up: !d.month_over_month?.expense_increased, inv: true },
        { label: 'Net Savings', value: PP.fmt(d.current_month?.net_savings || 0), icon: 'wallet', cls: 'savings', delta: d.month_over_month?.savings_change_pct, up: d.month_over_month?.savings_increased },
        { label: 'Total Assets', value: PP.fmt(d.balances?.total_assets || 0), icon: 'landmark', cls: 'pockets', delta: d.balances?.total_pockets, deltaIsCount: true, up: true },
      ];
      summaryGrid.innerHTML = '';
      cards.forEach(c => {
        const delta = c.deltaIsCount ? `${c.delta} pockets` : `${Math.abs(c.delta || 0)}% ${c.up ? '↑' : '↓'}`;
        const cls = c.inv ? (c.up ? 'up' : 'down') : (c.up ? 'up' : 'down');
        summaryGrid.appendChild(PP.el('div', { class: 'stat-card glass-card' }, [
          PP.el('div', { class: `stat-icon ${c.cls}` }, [PP.el('i', { 'data-lucide': c.icon })]),
          PP.el('div', { class: 'stat-label' }, [c.label]),
          PP.el('div', { class: 'stat-value' }, [c.value]),
          PP.el('div', { class: `stat-change ${cls}` }, [PP.el('i', { 'data-lucide': c.up ? 'trending-up' : 'trending-down' }), delta]),
        ]));
      });
      PP.refreshIcons();
    });

    // Category + Pocket split
    const splitRow = PP.el('div', { class: 'two-col-grid', id: 'splitRow' });
    wrap.appendChild(splitRow);
    PP.Analytics.loadPeriod();

    // Insights
    const insCard = PP.el('div', { class: 'section-card' }, [
      PP.el('div', { class: 'section-title' }, [
        PP.el('h3', {}, [PP.el('i', { 'data-lucide': 'sparkles', style: 'display:inline;margin-right:.5rem;color:var(--accent-3)' }), 'Smart Insights']),
        PP.el('span', { class: 'chip' }, ['AI generated']),
      ]),
    ]);
    wrap.appendChild(insCard);
    PP.AnalyticsAPI.insights().then(res => {
      const list = res?.data?.insights || [];
      if (!list.length) return insCard.appendChild(PP.el('p', { class: 'text-muted text-sm' }, ['No insights right now. Keep adding transactions!']));
      const grid = PP.el('div', { class: 'insights-grid stagger' });
      list.forEach(ins => grid.appendChild(PP.Analytics.renderInsight(ins)));
      insCard.appendChild(grid);
      PP.refreshIcons();
    });

    // Timeline
    const timeCard = PP.el('div', { class: 'section-card' });
    timeCard.appendChild(PP.el('div', { class: 'section-title' }, [
      PP.el('h3', {}, [PP.el('i', { 'data-lucide': 'calendar', style: 'display:inline;margin-right:.5rem;color:var(--info)' }), 'Monthly Timeline']),
    ]));
    wrap.appendChild(timeCard);
    PP.TxAPI.timeline(6).then(res => {
      const tl = res?.data?.timeline || {};
      const months = Object.keys(tl).sort().reverse();
      const mWrap = PP.el('div', { class: 'tx-list' });
      months.forEach(m => {
        const t = tl[m];
        const header = PP.el('div', { class: 'tx-day-header', style: 'position:static;background:transparent;padding:.75rem 0' }, [
          PP.el('div', {}, [t.month]),
          PP.el('div', { style: 'display:flex;gap:.6rem' }, [
            PP.el('span', { class: 'chip success' }, [`+${PP.fmt(t.income)}`]),
            PP.el('span', { class: 'chip danger' }, [`-${PP.fmt(t.expense)}`]),
            PP.el('b', { style: (t.net_savings >= 0 ? 'color:var(--success)' : 'color:var(--danger)') + ';font-size:.8rem' }, [`Net ${PP.fmt(t.net_savings)}`]),
          ]),
        ]);
        mWrap.appendChild(header);
        const byCat = Object.entries(t.by_category || {}).sort((a, b) => b[1] - a[1]).slice(0, 5);
        if (byCat.length) {
          const bd = PP.el('div', { class: 'breakdown-list', style: 'padding:.5rem 0 1rem' });
          const max = Math.max(...byCat.map(x => x[1]));
          byCat.forEach(([c, v], i) => bd.appendChild(PP.el('div', { class: 'breakdown-row' }, [
            PP.el('div', { class: 'breakdown-row-left' }, [
              PP.el('div', { class: 'breakdown-icon', style: `background:rgba(99,102,241,.12);color:var(--chart-${(i % 6) + 1})` }, [PP.el('i', { 'data-lucide': PP.Transactions.categoryIcon(c) })]),
              PP.el('div', { class: 'breakdown-name' }, [c]),
            ]),
            PP.el('div', { class: 'breakdown-bar-wrap' }, [PP.el('div', { class: 'breakdown-bar-fill', style: `width:${(v / max * 100).toFixed(0)}%;background:linear-gradient(90deg,var(--chart-${(i % 6) + 1}), var(--chart-2))` })]),
            PP.el('div', { class: 'breakdown-value' }, [PP.fmt(v)]),
          ])));
          mWrap.appendChild(bd);
        }
        (t.transactions || []).slice(0, 3).forEach(tx => mWrap.appendChild(PP.Transactions.renderRow(tx)));
      });
      if (!months.length) mWrap.appendChild(PP.el('p', { class: 'text-muted' }, ['No timeline data yet.']));
      timeCard.appendChild(mWrap);
      PP.refreshIcons();
    });
  },

  renderInsight(ins) {
    const type = ins.type || '';
    const priority = ins.priority || 'info';
    const iconMap = {
      top_category: 'star',
      category_spike: 'trending-up',
      category_drop: 'trending-down',
      budget_nearly_full: 'alert-triangle',
      budget_exceeded: 'octagon-alert',
      low_savings: 'piggy-bank',
      high_savings: 'trophy',
    };
    return PP.el('div', { class: `insight-card ${priority}` }, [
      PP.el('div', { class: 'insight-top' }, [
        PP.el('div', { class: 'insight-icon' }, [PP.el('i', { 'data-lucide': iconMap[type] || 'lightbulb' })]),
        PP.el('span', { class: 'insight-priority' }, [priority]),
      ]),
      PP.el('h4', {}, [ins.title]),
      PP.el('p', {}, [ins.message]),
      type === 'budget_nearly_full' && ins.pocket_id ? PP.el('button', {
        class: 'insight-cta', onclick: () => PP.Pockets.openDetail(ins.pocket_id),
      }, ['View pocket', PP.el('i', { 'data-lucide': 'arrow-right' })]) : null,
    ]);
  },

  async loadPeriod() {
    const months = Number(PP.$('#analPeriod')?.value || 1);
    const row = PP.$('#splitRow');
    if (!row) return;
    row.innerHTML = `<div class="skeleton" style="height:400px;width:100%"></div><div class="skeleton" style="height:400px;width:100%"></div>`;
    try {
      const [cat, pockets, daily] = await Promise.all([
        PP.AnalyticsAPI.spendingByCategory(months),
        PP.AnalyticsAPI.spendingByPocket(months),
        PP.AnalyticsAPI.dailyTrend(Math.min(30, months * 30)),
      ]);
      row.innerHTML = '';
      const catCard = PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [PP.el('h3', {}, ['By Category']), PP.el('span', { class: 'chip' }, [`${months} month${months > 1 ? 's' : ''}`])]),
      ]);
      const catSplit = PP.el('div', { style: 'display:grid;grid-template-columns:minmax(180px,.9fr) 1.1fr;gap:1.25rem;align-items:center' });
      const catSegs = (cat?.data?.categories || []).slice(0, 6).map((c, i) => ({
        label: c.category, value: c.amount, color: `var(--chart-${(i % 6) + 1})`,
      }));
      const dw = PP.el('div'); PP.Charts.donut(dw, catSegs, 'Total Spent');
      const legend = PP.el('div');
      PP.Charts.breakdown(legend, (cat?.data?.categories || []).slice(0, 6).map((c, i) => ({
        label: c.category, value: c.amount, color: `var(--chart-${(i % 6) + 1})`,
        icon: PP.Transactions.categoryIcon(c.category),
        iconColor: '#6366f1',
      })), { showPct: true });
      catSplit.append(dw, legend);
      catCard.appendChild(catSplit);

      const pockCard = PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [PP.el('h3', {}, ['By Pocket'])]),
      ]);
      const pl = PP.el('div');
      PP.Charts.breakdown(pl, (pockets?.data?.pockets || []).filter(p => !p.archived).slice(0, 6).map(p => ({
        label: p.name, value: p.spent, color: p.color, icon: p.icon, iconColor: p.color,
      })));
      pockCard.appendChild(pl);

      row.append(catCard, pockCard);

      // Daily chart below
      const dailyCard = PP.el('div', { class: 'section-card', style: 'grid-column:1/-1' }, [
        PP.el('div', { class: 'section-title' }, [PP.el('h3', {}, ['Daily Flow (Income vs Expense)'])]),
      ]);
      const dailyBars = PP.el('div');
      const max = Math.max(...(daily?.data?.daily || []).map(d => Math.max(d.income, d.expense)), 1);
      const barData = (daily?.data?.daily || []).map(d => ({
        label: d.day_num,
        value: Math.max(d.income, d.expense),
        tooltip: `${d.day_name}: Inc ${PP.fmt(d.income)} / Exp ${PP.fmt(d.expense)}`,
        color: 'linear-gradient(180deg, rgba(34,197,94,.5), #6366f1)',
      }));
      PP.Charts.bars(dailyBars, barData);
      dailyCard.appendChild(dailyBars);
      row.appendChild(dailyCard);
      PP.refreshIcons();
    } catch (e) { console.warn(e); }
  },

  async renderBudgets(container) {
    container.innerHTML = '';
    const wrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.5rem' });
    container.appendChild(wrap);
    wrap.appendChild(PP.el('div', { class: 'page-header' }, [
      PP.el('div', {}, [
        PP.el('p', { class: 'page-eyebrow' }, ['Planning']),
        PP.el('h2', { class: 'page-title' }, ['Budgets & Alerts']),
        PP.el('p', { class: 'page-sub' }, ['Set smart limits and get notified before you overspend.']),
      ]),
      PP.el('div', { class: 'page-actions' }, [
        PP.el('button', { class: 'btn btn-primary', onclick: () => PP.Modals.createBudget() }, [PP.el('i', { 'data-lucide': 'plus' }), 'New Budget']),
      ]),
    ]));
    try {
      const res = await PP.AnalyticsAPI.budgetPerformance();
      const data = res?.data || {};
      const grid = PP.el('div', { class: 'stats-grid stagger' });
      ['healthy', 'warnings', 'at_risk', 'over_budget'].forEach(k => {
        const card = PP.el('div', { class: 'stat-card glass-card' }, [
          PP.el('div', { class: 'stat-icon ' + (k === 'over_budget' ? 'expense' : (k === 'healthy' ? 'income' : 'savings')) }, [
            PP.el('i', { 'data-lucide': k === 'healthy' ? 'shield-check' : (k === 'over_budget' ? 'octagon-alert' : 'alert-triangle') }),
          ]),
          PP.el('div', { class: 'stat-label' }, [k.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())]),
          PP.el('div', { class: 'stat-value' }, [String(data[k] || 0)]),
        ]);
        grid.appendChild(card);
      });
      wrap.appendChild(grid);

      const listCard = PP.el('div', { class: 'section-card' });
      listCard.appendChild(PP.el('div', { class: 'section-title' }, [PP.el('h3', {}, ['Active Budgets'])]));
      const items = data.budgets || [];
      if (!items.length) {
        listCard.appendChild(PP.el('div', { class: 'empty-state' }, [
          PP.el('div', { class: 'empty-icon' }, [PP.el('i', { 'data-lucide': 'target' })]),
          PP.el('h3', {}, ['No budgets yet']),
          PP.el('button', { class: 'btn btn-primary', style: 'margin-top:.75rem', onclick: () => PP.Modals.createBudget() }, [PP.el('i', { 'data-lucide': 'plus' }), 'Create First Budget']),
        ]));
      } else {
        const inner = PP.el('div', { class: 'breakdown-list', style: 'gap:1.1rem' });
        items.forEach(b => {
          const pct = b.budget?.percentage_used || 0;
          const status = b.status || 'healthy';
          const row = PP.el('div', { class: 'glass-card', style: 'padding:1.1rem;display:flex;flex-direction:column;gap:.75rem' }, [
            PP.el('div', { class: 'flex justify-between items-center' }, [
              PP.el('div', { style: 'display:flex;align-items:center;gap:.75rem' }, [
                PP.el('div', {
                  class: 'pocket-icon-wrap',
                  style: 'width:36px;height:36px;border-radius:10px;background:' + (b.budget?.limit_amount ? 'var(--accent-gradient)' : '#888'),
                }, [PP.el('i', { 'data-lucide': 'target', style: 'width:18px;height:18px;color:white' })]),
                PP.el('div', {}, [
                  PP.el('div', { style: 'font-weight:700;font-size:.95rem' }, [b.budget?.name || 'Budget']),
                  PP.el('div', { style: 'font-size:.75rem;color:var(--text-muted)' }, [`${b.budget?.period || 'monthly'} · ${PP.formatDate(b.budget?.start_date)} – ${PP.formatDate(b.budget?.end_date)}`]),
                ]),
              ]),
              PP.el('span', { class: `chip ${status === 'healthy' ? 'success' : (status === 'over' ? 'danger' : 'warning')}` }, [
                pct.toFixed(0) + '%'
              ]),
            ]),
            PP.el('div', { class: 'pocket-progress', style: 'height:8px' }, [
              PP.el('div', { class: 'pocket-progress-fill', style: `width:${Math.min(100, pct)}%;background:${status === 'over' ? 'var(--danger)' : (status === 'at_risk' ? 'var(--warning)' : 'var(--success)')}` }),
            ]),
            PP.el('div', { class: 'flex justify-between text-sm' }, [
              PP.el('span', { class: 'text-muted' }, [`Spent ${PP.fmt(b.budget?.spent || 0)} / ${PP.fmt(b.budget?.limit_amount || 0)}`]),
              PP.el('span', { style: 'font-weight:600;color:' + ((b.budget?.remaining || 0) < 0 ? 'var(--danger)' : 'var(--success)') }, [
                `${(b.budget?.remaining || 0) < 0 ? 'Over' : 'Remaining'} ${PP.fmt(Math.abs(b.budget?.remaining || 0))}`
              ]),
            ]),
            PP.el('div', { style: 'display:flex;gap:.5rem;justify-content:flex-end' }, [
              PP.el('button', { class: 'btn btn-outline btn-sm', onclick: () => PP.Modals.createBudget(b.budget) }, [
                PP.el('i', { 'data-lucide': 'pencil', style: 'width:13px;height:13px' }), 'Edit',
              ]),
              PP.el('button', { class: 'btn btn-outline btn-danger btn-sm', onclick: async () => {
                const ok = await PP.UI.confirm('Delete this budget?', `Remove "${b.budget?.name || 'Budget'}" budget permanently. This cannot be undone.`, { icon: 'trash-2', iconClass: 'bg-danger', okLabel: 'Delete', okClass: 'btn-danger' });
                if (!ok) return;
                try {
                  await PP.AnalyticsAPI.deleteBudget(b.budget.id);
                  PP.UI.toast('Deleted', 'Budget has been removed', 'success');
                  PP.refreshCurrentView();
                } catch (e) { PP.UI.toast('Delete failed', e.message, 'error'); }
              } }, [
                PP.el('i', { 'data-lucide': 'trash-2', style: 'width:13px;height:13px' }), 'Delete',
              ]),
            ]),
          ]);
          inner.appendChild(row);
        });
        listCard.appendChild(inner);
      }
      wrap.appendChild(listCard);
      PP.refreshIcons();
    } catch (e) { PP.UI.toast('Could not load budgets', e.message, 'error'); }
  },
};

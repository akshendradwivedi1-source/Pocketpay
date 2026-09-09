// ========== Dashboard View ==========
PP.Dashboard = {
  async render(container, params = {}) {
    container.innerHTML = `<div class="stagger" style="display:flex;flex-direction:column;gap:1.5rem">
      ${PP.Skeletons.card(4).outerHTML}
      ${PP.Skeletons.card(5).outerHTML}
    </div>`;
    PP.refreshIcons();
    let data, analytics, txs, insights, budgets;
    try {
      [data, analytics, txs, insights, budgets] = await Promise.all([
        PP.MiscAPI.dashboard(),
        PP.AnalyticsAPI.overview(),
        PP.TxAPI.list({ per_page: 8 }),
        PP.AnalyticsAPI.insights().catch(() => null),
        PP.WalletAPI.rules().catch(() => null),
      ]);
    } catch (e) { return PP.UI.toast('Error loading dashboard', e.message, 'error'); }

    const u = data?.data?.user || PP.state.user || {};
    const b = data?.data?.balances || {};
    const w = analytics?.data?.weekly || {};
    const m = analytics?.data?.monthly || {};
    const mc = analytics?.data?.month_over_month || {};
    const pockets = data?.data?.pockets || [];
    const transactions = txs?.data?.items || [];
    PP.state.distributionRules = budgets?.data?.rules || PP.state.distributionRules || [];

    const savedThisMonth = m.income - m.expense;

    container.innerHTML = '';
    const wrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.5rem' });
    container.appendChild(wrap);

    // ---------- Header ----------
    const greet = (() => {
      const h = new Date().getHours();
      if (h < 12) return 'Good morning';
      if (h < 18) return 'Good afternoon';
      return 'Good evening';
    })();
    wrap.appendChild(PP.el('div', { class: 'page-header' }, [
      PP.el('div', {}, [
        PP.el('p', { class: 'page-eyebrow' }, ['Dashboard']),
        PP.el('h2', { class: 'page-title' }, [`${greet}, ${(u.full_name || 'there').split(' ')[0]} 👋`]),
        PP.el('p', { class: 'page-sub' }, [`Organize every rupee across your custom pockets.`]),
      ]),
      PP.el('div', { class: 'page-actions' }, [
        PP.el('button', {
          class: 'btn btn-ghost',
          onclick: () => PP.navigate('analytics'),
        }, [PP.el('i', { 'data-lucide': 'bar-chart-3' }), 'View Reports']),
        PP.el('button', {
          class: 'btn btn-primary',
          onclick: () => PP.Modals.createPocket(),
        }, [PP.el('i', { 'data-lucide': 'plus' }), 'Create Pocket']),
      ]),
    ]));

    // ---------- Post-Login Onboarding (if no bank connected) ----------
    const linkedBanks = u.linked_banks || [];
    const hasBank = linkedBanks.length > 0;
    const primaryBank = hasBank ? linkedBanks[0] : null;

    if (!hasBank) {
      const onboardCard = PP.el('div', {
        class: 'glass-card',
        style: 'background:linear-gradient(135deg,rgba(99,102,241,0.12) 0%,rgba(139,92,246,0.08) 100%);border:1px solid rgba(99,102,241,0.3);border-radius:20px;padding:24px 28px;display:flex;align-items:center;justify-content:space-between;gap:1.5rem;flex-wrap:wrap;box-shadow:0 8px 30px rgba(99,102,241,0.12);'
      });
      onboardCard.innerHTML = `
        <div style="display:flex;align-items:center;gap:1.25rem">
          <div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;color:#fff;font-size:24px;box-shadow:0 4px 15px rgba(99,102,241,0.4)">
            <i data-lucide="landmark"></i>
          </div>
          <div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap">
              <h3 style="margin:0;font-size:1.1rem;font-weight:700;color:#fff">Connect your bank account to get started</h3>
              <span class="chip" style="background:rgba(99,102,241,0.25);color:#a5b4fc;border:1px solid rgba(99,102,241,0.4);font-size:0.72rem;padding:2px 8px">Demo Sandbox</span>
            </div>
            <p style="margin:0;color:var(--text-muted);font-size:0.85rem">Link your account to retrieve simulated available balance (₹25,000) and start allocating to custom pockets.</p>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:0.75rem">
          <button class="btn btn-primary" id="onboardConnectBankBtn" style="font-weight:600">
            <i data-lucide="link"></i> Connect Bank Account
          </button>
        </div>
      `;
      wrap.appendChild(onboardCard);
      setTimeout(() => {
        onboardCard.querySelector('#onboardConnectBankBtn')?.addEventListener('click', () => {
          PP.Modals.linkBankAccount();
        });
      }, 0);
    } else {
      // Connected Bank Status Banner
      const bankBanner = PP.el('div', {
        class: 'glass-card',
        style: 'background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.25);border-radius:18px;padding:18px 24px;display:flex;align-items:center;justify-content:space-between;gap:1.25rem;flex-wrap:wrap;'
      });
      const lastSyncStr = primaryBank.last_synced_at ? new Date(primaryBank.last_synced_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Recently';
      bankBanner.innerHTML = `
        <div style="display:flex;align-items:center;gap:1rem">
          <div style="width:44px;height:44px;border-radius:12px;background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);display:flex;align-items:center;justify-content:center;color:#10b981">
            <i data-lucide="landmark" style="width:22px;height:22px"></i>
          </div>
          <div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:2px">
              <span style="font-weight:700;color:#fff;font-size:0.95rem">${primaryBank.bank_name || 'Bank Account'} (${primaryBank.account_mask || '•••• 4821'})</span>
              <span class="chip success" style="font-size:0.7rem;padding:1px 6px">Sandbox Connected</span>
            </div>
            <div style="font-size:0.78rem;color:var(--text-muted)">
              <span style="color:#10b981;font-weight:600">Simulated Balance: ₹${(primaryBank.balance || 25000).toLocaleString('en-IN')}</span> &bull; Last synced: ${lastSyncStr}
            </div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:0.5rem">
          <button class="btn btn-sm btn-ghost" id="syncBankBalanceBtn" style="border:1px solid rgba(255,255,255,0.1);color:#fff">
            <i data-lucide="refresh-cw"></i> Sync Balance
          </button>
          <button class="btn btn-sm btn-ghost" id="manageBankBtn" style="color:var(--text-dim)">
            <i data-lucide="settings"></i> Manage
          </button>
        </div>
      `;
      wrap.appendChild(bankBanner);
      setTimeout(() => {
        bankBanner.querySelector('#syncBankBalanceBtn')?.addEventListener('click', async (ev) => {
          const btn = ev.currentTarget;
          btn.disabled = true;
          btn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Syncing…';
          PP.refreshIcons();
          try {
            const res = await PP.Auth.syncBankBalance();
            PP.UI.toast('Balance Synced', res.message || 'Latest sandbox balance retrieved successfully.', 'success');
            setTimeout(() => { PP.refreshCurrentView(); }, 400);
          } catch (e) {
            PP.UI.toast('Sync Failed', e.message, 'error');
            btn.disabled = false;
            btn.innerHTML = '<i data-lucide="refresh-cw"></i> Sync Balance';
          }
        });
        bankBanner.querySelector('#manageBankBtn')?.addEventListener('click', () => {
          PP.Modals.linkBankAccount();
        });
      }, 0);
    }

    // ---------- Security Onboarding Prompt (if PIN not set) ----------
    if (u.security_setup_required || (!u.security_setup_completed && !u.has_transaction_pin)) {
      const secCard = PP.el('div', {
        class: 'glass-card',
        id: 'securitySetupDisclaimerCard',
        style: 'background:linear-gradient(135deg,rgba(245,158,11,0.12) 0%,rgba(217,119,6,0.08) 100%);border:1px solid rgba(245,158,11,0.35);border-radius:18px;padding:16px 22px;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;box-shadow:0 4px 20px rgba(245,158,11,0.1);'
      });
      secCard.innerHTML = `
        <div style="display:flex;align-items:center;gap:1rem">
          <div style="width:42px;height:42px;border-radius:12px;background:rgba(245,158,11,0.2);border:1px solid rgba(245,158,11,0.4);display:flex;align-items:center;justify-content:center;color:#f59e0b;font-size:20px">
            <i data-lucide="shield-alert"></i>
          </div>
          <div>
            <div style="display:flex;align-items:center;gap:8px">
              <h4 style="margin:0;font-size:0.95rem;font-weight:700;color:#fff">Security setup required</h4>
              <span class="chip" style="background:rgba(245,158,11,0.25);color:#fde68a;font-size:0.68rem;padding:1px 6px">Action Needed</span>
            </div>
            <p style="margin:4px 0 0;color:var(--text-muted);font-size:0.82rem">Before using PocketPay transfers and other banking features, please create your required security credentials.</p>
          </div>
        </div>
        <button class="btn btn-sm btn-primary" id="setupPinBannerBtn" style="background:#f59e0b;color:#18181b;font-weight:700;border:none">
          <i data-lucide="shield-check"></i> Create Security Credentials
        </button>
      `;
      wrap.appendChild(secCard);
      setTimeout(() => {
        secCard.querySelector('#setupPinBannerBtn')?.addEventListener('click', () => {
          if (PP.Modals.securitySetup) PP.Modals.securitySetup();
          else PP.Modals.setupPin();
        });
      }, 0);
    }

    // ---------- Balance Card & Quick Actions ----------
    const totalNetWorth = b.total || ((b.wallet || 0) + (b.pockets || 0));
    const availableUnallocated = b.wallet || 0;
    const inPockets = b.pockets || 0;

    const balanceCard = PP.el('div', { class: 'balance-card' }, [
      PP.el('div', { class: 'balance-card-inner' }, [
        PP.el('div', {}, [
          PP.el('div', { class: 'balance-label' }, [
            PP.el('i', { 'data-lucide': 'wallet' }),
            'Total Funds (Available + Pockets)',
            hasBank ? PP.el('span', { class: 'chip', style: 'margin-left:8px;font-size:0.65rem;background:rgba(99,102,241,0.2)' }, ['Demo Sandbox']) : null
          ].filter(Boolean)),
          PP.el('div', { class: 'balance-amount' }, [PP.el('span', { class: 'symbol' }, ['₹']), PP.fmt(totalNetWorth).replace('₹', '')]),
          PP.el('div', { class: 'balance-sub' }, [
            PP.el('div', { title: 'Funds available to allocate or spend' }, [
              PP.el('i', { 'data-lucide': 'check-circle-2', style: 'color:#10b981' }),
              `Available: ${PP.fmt(availableUnallocated)}`
            ]),
            PP.el('div', { title: 'Allocated across custom pockets' }, [
              PP.el('i', { 'data-lucide': 'folder-kanban', style: 'color:#818cf8' }),
              `In Pockets: ${PP.fmt(inPockets)}`
            ]),
            PP.el('div', {}, [
              PP.el('i', { 'data-lucide': 'folders' }),
              `${pockets.length} Active Pockets`
            ]),
          ]),
        ]),
        PP.el('div', { class: 'balance-actions' }, [
          PP.el('button', { class: 'balance-action', onclick: () => PP.Modals.scanAndPay() }, [
            PP.el('div', { class: 'balance-action-icon expense' }, [PP.el('i', { 'data-lucide': 'qr-code' })]),
            PP.el('div', { class: 'balance-action-label' }, [PP.el('div', {}, ['Scan & Pay']), PP.el('div', {}, ['UPI / QR Code'])]),
          ]),
          PP.el('button', { class: 'balance-action', onclick: () => PP.Modals.transferToBank() }, [
            PP.el('div', { class: 'balance-action-icon income' }, [PP.el('i', { 'data-lucide': 'landmark' })]),
            PP.el('div', { class: 'balance-action-label' }, [PP.el('div', {}, ['Transfer to Bank']), PP.el('div', {}, ['IMPS / Payout'])]),
          ]),
          PP.el('button', { class: 'balance-action', onclick: () => PP.Modals.transfer() }, [
            PP.el('div', { class: 'balance-action-icon transfer' }, [PP.el('i', { 'data-lucide': 'refresh-ccw' })]),
            PP.el('div', { class: 'balance-action-label' }, [PP.el('div', {}, ['Transfer']), PP.el('div', {}, ['Between pockets'])]),
          ]),
          PP.el('button', { class: 'balance-action', onclick: () => PP.Modals.createPocket() }, [
            PP.el('div', { class: 'balance-action-icon wallet' }, [PP.el('i', { 'data-lucide': 'folder-plus' })]),
            PP.el('div', { class: 'balance-action-label' }, [PP.el('div', {}, ['Create Pocket']), PP.el('div', {}, ['Allocate funds'])]),
          ]),
        ]),
      ]),
    ]);

    const statCards = PP.el('div', { class: 'stats-grid stagger' });
    const stats = [
      { label: 'This Month Income', value: PP.fmt(m.income || 0), icon: 'trending-up', cls: 'income', change: mc.income_change_pct, up: mc.income_increased },
      { label: 'This Month Spent', value: PP.fmt(m.expense || 0), icon: 'credit-card', cls: 'expense', change: mc.expense_change_pct, up: !mc.expense_increased, invert: true },
      { label: 'Net Saved (MoM)', value: PP.fmt(savedThisMonth), icon: 'piggy-bank', cls: 'savings', change: mc.savings_change_pct, up: mc.savings_increased },
      { label: 'Savings Rate', value: `${m.savings_rate || 0}%`, icon: 'target', cls: 'pockets', change: m.savings_rate, up: (m.savings_rate || 0) >= 20 },
    ];
    stats.forEach(s => {
      const delta = s.change == null ? '—' : `${Math.abs(s.change)}% ${s.up ? '↑' : '↓'}`;
      const cls = s.invert ? (s.up ? 'up' : 'down') : (s.up ? 'up' : 'down');
      statCards.appendChild(PP.el('div', { class: 'stat-card glass-card' }, [
        PP.el('div', { class: `stat-icon ${s.cls}` }, [PP.el('i', { 'data-lucide': s.icon })]),
        PP.el('div', { class: 'stat-label' }, [s.label]),
        PP.el('div', { class: 'stat-value' }, [s.value]),
        PP.el('div', { class: `stat-change ${cls}` }, [
          PP.el('i', { 'data-lucide': s.up ? 'trending-up' : 'trending-down' }),
          delta,
          PP.el('span', { style: 'color:var(--text-dim);margin-left:.25rem;font-weight:400' }, ['vs last month']),
        ]),
      ]));
    });

    wrap.appendChild(PP.el('div', { class: 'two-col-grid' }, [
      balanceCard, statCards,
    ]));

    // ---------- Insights strip ----------
    const inList = insights?.data?.insights?.slice(0, 4) || [];
    if (inList.length) {
      const inWrap = PP.el('div', { class: 'insights-grid stagger' });
      inList.forEach(ins => {
        const card = PP.el('div', { class: `insight-card ${ins.priority || ''}` }, [
          PP.el('div', { class: 'insight-top' }, [
            PP.el('div', { class: 'insight-icon' }, [PP.el('i', { 'data-lucide': PP.insightIcon(ins) })]),
            PP.el('span', { class: 'insight-priority' }, [ins.priority || 'info']),
          ]),
          PP.el('h4', {}, [ins.title]),
          PP.el('p', {}, [ins.message]),
        ]);
        inWrap.appendChild(card);
      });
      wrap.appendChild(PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [
          PP.el('h3', {}, [PP.el('i', { 'data-lucide': 'sparkles', style: 'display:inline;margin-right:.5rem;color:var(--accent-3)' }), 'Smart Insights']),
          PP.el('button', { onclick: () => PP.navigate('analytics') }, ['See all', PP.el('i', { 'data-lucide': 'arrow-right' })]),
        ]),
        inWrap,
      ]));
    }

    // ---------- Pockets + Recent ----------
    const main2Col = PP.el('div', { class: 'two-col-grid' });

    // Pockets card
    const pocketsWrap = PP.el('div', { class: 'section-card' });
    pocketsWrap.appendChild(PP.el('div', { class: 'section-title' }, [
      PP.el('h3', {}, [PP.el('i', { 'data-lucide': 'wallet-cards', style: 'display:inline;margin-right:.5rem;color:var(--accent)' }), 'Your Pockets']),
      PP.el('button', { onclick: () => PP.navigate('pockets') }, ['Manage', PP.el('i', { 'data-lucide': 'arrow-right' })]),
    ]));
    if (!pockets.length) {
      pocketsWrap.appendChild(PP.el('div', { class: 'empty-state' }, [
        PP.el('div', { class: 'empty-icon' }, [PP.el('i', { 'data-lucide': 'folder-open' })]),
        PP.el('h3', {}, ['No pockets yet']),
        PP.el('p', {}, ['Create unlimited custom pockets to organize every rupee.']),
        PP.el('button', { class: 'btn btn-primary btn-sm', onclick: () => PP.Modals.createPocket(), style: 'margin-top:1rem' },
          [PP.el('i', { 'data-lucide': 'plus' }), 'Create First Pocket']),
      ]));
    } else {
      const pgrid = PP.el('div', { class: 'pockets-grid stagger' });
      pockets.slice(0, 6).forEach(p => pgrid.appendChild(PP.Dashboard.renderPocketCard(p)));
      pgrid.appendChild(PP.el('div', { class: 'add-pocket-card', onclick: () => PP.Modals.createPocket() }, [
        PP.el('div', { class: 'add-pocket-icon' }, [PP.el('i', { 'data-lucide': 'plus' })]),
        PP.el('span', {}, ['Add Pocket']),
      ]));
      pocketsWrap.appendChild(pgrid);
    }

    // Recent transactions
    const recentWrap = PP.el('div', { class: 'section-card' });
    recentWrap.appendChild(PP.el('div', { class: 'section-title' }, [
      PP.el('h3', {}, [PP.el('i', { 'data-lucide': 'arrow-left-right', style: 'display:inline;margin-right:.5rem;color:var(--accent)' }), 'Recent Transactions']),
      PP.el('button', { onclick: () => PP.navigate('transactions') }, ['View all', PP.el('i', { 'data-lucide': 'arrow-right' })]),
    ]));
    if (!transactions.length) {
      recentWrap.appendChild(PP.el('div', { class: 'empty-state' }, [
        PP.el('div', { class: 'empty-icon' }, [PP.el('i', { 'data-lucide': 'receipt' })]),
        PP.el('h3', {}, ['No transactions yet']),
        PP.el('p', {}, ['Track every payment and deposit right here.']),
      ]));
    } else {
      const tlist = PP.el('div', { class: 'tx-list' });
      const byDay = PP.Transactions.groupByDay(transactions);
      Object.entries(byDay).forEach(([day, items]) => {
        tlist.appendChild(PP.el('div', { class: 'tx-day-header' }, [day]));
        items.forEach(t => tlist.appendChild(PP.Transactions.renderRow(t)));
      });
      recentWrap.appendChild(tlist);
    }

    main2Col.append(pocketsWrap, recentWrap);
    wrap.appendChild(main2Col);

    // ---------- Savings Goals Section (Phase 11) ----------
    const goalsWrap = PP.el('div', { class: 'section-card' });
    goalsWrap.innerHTML = `
      <div class="section-title">
        <h3 style="display:flex;align-items:center;gap:0.5rem">
          <i data-lucide="target" style="color:var(--accent)"></i>
          <span>Savings Goals</span>
        </h3>
        <button class="btn btn-sm btn-ghost" id="createGoalDashBtn">
          <i data-lucide="plus"></i> New Goal
        </button>
      </div>
      <div id="dashGoalsContainer" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:1rem;margin-top:0.75rem">
        <div class="empty-state" style="padding:1.5rem">
          <p style="color:var(--text-muted);font-size:0.85rem">Loading your savings targets...</p>
        </div>
      </div>
    `;
    wrap.appendChild(goalsWrap);

    setTimeout(async () => {
      const createBtn = goalsWrap.querySelector('#createGoalDashBtn');
      if (createBtn) createBtn.onclick = () => PP.Modals.createGoal();

      const containerEl = goalsWrap.querySelector('#dashGoalsContainer');
      if (!containerEl) return;

      try {
        const goalsRes = await PP.GoalsAPI.list();
        const goals = goalsRes.data?.items || [];
        if (!goals.length) {
          containerEl.innerHTML = `
            <div class="empty-state" style="grid-column:1/-1;padding:1.5rem;text-align:center">
              <p style="color:var(--text-muted);font-size:0.88rem;margin-bottom:0.75rem">No active savings goals. Set a target to save for a laptop, trip, or emergency fund.</p>
              <button class="btn btn-primary btn-sm" id="emptyCreateGoalBtn"><i data-lucide="plus"></i> Set First Savings Goal</button>
            </div>
          `;
          containerEl.querySelector('#emptyCreateGoalBtn')?.addEventListener('click', () => PP.Modals.createGoal());
          PP.refreshIcons();
          return;
        }

        containerEl.innerHTML = '';
        goals.forEach(g => {
          const pct = g.progress_percentage || 0;
          const card = PP.el('div', {
            class: 'glass-card',
            style: 'border:1px solid var(--border);border-radius:16px;padding:1.25rem;display:flex;flex-direction:column;gap:0.75rem;background:var(--surface)'
          });
          const isCompleted = Boolean(g.is_completed);
          const hasUnreleased = isCompleted && Number(g.current_amount || 0) > 0;
          const displayAmount = (isCompleted && g.released_amount) ? g.released_amount : g.current_amount;

          card.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:space-between">
              <div style="display:flex;align-items:center;gap:0.6rem">
                <div style="width:36px;height:36px;border-radius:10px;background:${isCompleted ? 'rgba(16,185,129,0.15)' : 'rgba(99,102,241,0.15)'};color:${isCompleted ? 'var(--success)' : 'var(--accent)'};display:flex;align-items:center;justify-content:center">
                  <i data-lucide="${isCompleted ? 'award' : 'target'}"></i>
                </div>
                <div>
                  <h4 style="margin:0;font-size:0.95rem;font-weight:700">${g.name}</h4>
                  <span style="font-size:0.75rem;color:var(--text-dim)">${g.category} ${isCompleted ? '• 🎉 Completed' : (g.days_remaining >= 0 ? `• ${g.days_remaining}d left` : '')}</span>
                </div>
              </div>
              <span class="chip ${isCompleted ? 'success' : ''}" style="font-size:0.72rem">${isCompleted ? '🎉 Goal Achieved' : pct + '%'}</span>
            </div>
            <div>
              <div style="display:flex;justify-content:space-between;font-size:0.82rem;margin-bottom:0.35rem">
                <span style="color:var(--text-muted)">${isCompleted ? 'Released to Balance:' : 'Saved:'} <b style="color:${isCompleted ? 'var(--success)' : 'var(--text)'}">₹${Number(displayAmount || 0).toLocaleString('en-IN')}</b></span>
                <span style="color:var(--text-dim)">Target: ₹${Number(g.target_amount || 0).toLocaleString('en-IN')}</span>
              </div>
              <div style="height:8px;border-radius:4px;background:rgba(255,255,255,0.08);overflow:hidden">
                <div style="height:100%;width:${isCompleted ? 100 : pct}%;background:linear-gradient(90deg, #6366f1, #10b981);border-radius:4px;transition:width 0.4s ease"></div>
              </div>
            </div>
            <div style="display:flex;gap:0.5rem;margin-top:0.25rem">
              ${hasUnreleased
                ? `<button class="btn btn-sm btn-success release-goal-btn" style="flex:1"><i data-lucide="unlock"></i> Release ₹${Number(g.current_amount).toLocaleString('en-IN')} to Balance</button>`
                : (isCompleted
                  ? `<div style="flex:1;text-align:center;font-size:0.78rem;color:var(--success);font-weight:600;padding:4px 0;background:rgba(16,185,129,0.08);border-radius:6px"><i data-lucide="check-circle" style="width:14px;height:14px;vertical-align:-2px;margin-right:4px"></i>Funds Added to Available Balance</div>`
                  : `<button class="btn btn-sm btn-outline deposit-goal-btn" style="flex:1"><i data-lucide="plus-circle"></i> Add Money</button>`
                )
              }
              <button class="btn btn-sm btn-ghost edit-goal-btn" title="Edit"><i data-lucide="pencil"></i></button>
            </div>
          `;
          card.querySelector('.deposit-goal-btn')?.addEventListener('click', () => PP.Modals.depositGoal(g));
          card.querySelector('.release-goal-btn')?.addEventListener('click', async () => {
            try {
              const res = await PP.GoalsAPI.release(g.id);
              const rel = res?.released_amount || res?.data?.released_amount || g.current_amount;
              PP.UI.toast('Funds Released', `₹${Number(rel).toLocaleString('en-IN')} released to your available balance!`, 'success');
              await PP.loadState?.();
              PP.renderView?.();
            } catch (err) {
              PP.UI.toast('Release Failed', err.message || 'Could not release goal funds', 'error');
            }
          });
          card.querySelector('.edit-goal-btn')?.addEventListener('click', () => PP.Modals.createGoal(g));
          containerEl.appendChild(card);
        });
        PP.refreshIcons();
      } catch (err) {
        console.warn('Goals load error:', err);
      }
    }, 0);

    // ---------- Analytics row: by category + daily ----------
    const catP = PP.AnalyticsAPI.spendingByCategory(1);
    const dailyP = PP.AnalyticsAPI.dailyTrend(14);
    Promise.all([catP, dailyP]).then(([cat, daily]) => {
      const analRow = PP.el('div', { class: 'two-col-grid' });

      const byCatCard = PP.el('div', { class: 'section-card' });
      byCatCard.appendChild(PP.el('div', { class: 'section-title' }, [
        PP.el('h3', {}, [PP.el('i', { 'data-lucide': 'pie-chart', style: 'display:inline;margin-right:.5rem;color:var(--chart-2)' }), 'Spending by Category']),
        PP.el('span', { class: 'chip' }, ['This month']),
      ]));
      const catInner = PP.el('div', { style: 'display:grid;grid-template-columns:1fr 1.3fr;gap:1.5rem;align-items:center' });
      const donutSegs = (cat?.data?.categories || []).slice(0, 6).map((c, i) => ({
        label: c.category, value: c.amount, color: `var(--chart-${(i % 6) + 1})`,
      }));
      const donutWrap = PP.el('div');
      PP.Charts.donut(donutWrap, donutSegs, 'Spent', 'this month');
      const legend = PP.el('div');
      PP.Charts.breakdown(legend, (cat?.data?.categories || []).slice(0, 6).map((c, i) => ({
        label: c.category, value: c.amount, color: `var(--chart-${(i % 6) + 1})`,
        icon: PP.Transactions.categoryIcon(c.category),
        iconColor: getComputedStyle(document.documentElement).getPropertyValue(`--chart-${(i % 6) + 1}`).trim() || '#6366f1',
      })), { showPct: true });
      catInner.append(donutWrap, legend);
      byCatCard.appendChild(catInner);

      const dailyCard = PP.el('div', { class: 'section-card' });
      dailyCard.appendChild(PP.el('div', { class: 'section-title' }, [
        PP.el('h3', {}, [PP.el('i', { 'data-lucide': 'activity', style: 'display:inline;margin-right:.5rem;color:var(--success)' }), 'Daily Cash Flow']),
        PP.el('span', { class: 'chip' }, ['Last 14 days']),
      ]));
      const areaWrap = PP.el('div', { style: 'margin-bottom:1rem' });
      const points = (daily?.data?.daily || []).map(d => ({ label: d.day_name, value: d.income - d.expense }));
      PP.Charts.area(areaWrap, points);
      const legend2 = PP.el('div', { class: 'chart-legend', style: 'justify-content:space-between' });
      legend2.appendChild(PP.el('div', { class: 'legend-item' }, [PP.el('div', { class: 'legend-dot', style: 'background:var(--success)' }), PP.el('span', {}, ['Net flow'])]));
      dailyCard.append(areaWrap, legend2);

      analRow.append(byCatCard, dailyCard);
      wrap.appendChild(analRow);
      PP.refreshIcons();
    }).catch(e => console.warn(e));
  },

  renderPocketCard(p) {
    const vars = PP.UI.pocketStyleVars(p);
    const usage = p.budget_usage_percent || 0;
    const statusChip = usage >= 100 ? 'danger' : usage >= 75 ? 'warning' : null;
    const card = PP.el('div', {
      class: 'pocket-card glass-card',
      style: Object.entries(vars).map(([k, v]) => `${k}:${v}`).join(';'),
      onclick: () => PP.Pockets.openDetail(p.id),
    });
    card.innerHTML = `
      <div class="pocket-card-bg"></div>
      <div class="pocket-card-inner">
        <div class="pocket-card-top">
          <div class="pocket-icon-wrap"><i data-lucide="${p.icon || 'wallet'}"></i></div>
          <button class="pocket-menu-btn" data-id="${p.id}" aria-label="Pocket menu"><i data-lucide="more-horizontal"></i></button>
        </div>
        <div class="pocket-card-name">${p.name}</div>
        ${p.description ? `<div class="pocket-card-desc">${p.description.slice(0, 50)}</div>` : ''}
        <div class="pocket-card-balance">
          <div class="pocket-balance-label">Balance</div>
          <div class="pocket-balance-value">${PP.fmt(p.current_balance)}</div>
        </div>
        ${(p.monthly_limit || p.budget_amount) ? `
          <div class="pocket-progress"><div class="pocket-progress-fill" style="width:${Math.min(100, usage)}%"></div></div>
          <div class="pocket-meta">
            <span>${statusChip ? `<span class="chip ${statusChip}" style="padding:1px 7px">${usage.toFixed(0)}%</span>` : `${usage.toFixed(0)}% used`}</span>
            <span>${(p.monthly_limit ? PP.fmt(p.monthly_limit) : PP.fmt(p.budget_amount))} limit</span>
          </div>` : ''}
      </div>`;
    setTimeout(() => {
      const btn = card.querySelector('.pocket-menu-btn');
      if (btn) btn.addEventListener('click', (ev) => { ev.stopPropagation(); PP.Modals.pocketActions(p); });
    }, 0);
    return card;
  },
};

PP.insightIcon = (ins) => {
  const t = ins.type || '';
  if (t.includes('budget')) return 'alert-triangle';
  if (t.includes('spike')) return 'trending-up';
  if (t.includes('drop')) return 'trending-down';
  if (t.includes('saving')) return 'piggy-bank';
  if (t.includes('top')) return 'star';
  return 'lightbulb';
};

// ========== PocketPay Premium Suite & Showcase (Parts 1, 2, 3, 4, 6) ==========
window.PP = window.PP || {};

PP.Premium = {
  currentTab: 'rules',

  async render(container) {
    let statusData = { is_premium: false, subscription: null };
    try {
      const res = await (PP.PremiumAPI ? PP.PremiumAPI.getStatus() : PP.API.get('/api/premium/status'));
      statusData = res.data || res;
    } catch (e) {
      statusData = { is_premium: !!PP.state.user?.is_premium, subscription: null };
    }

    const isPrem = !!(statusData.is_premium || PP.state.user?.is_premium);
    const sub = statusData.subscription;

    container.innerHTML = `
      <div class="stagger" style="display:flex;flex-direction:column;gap:1.5rem">
        <!-- Header -->
        <div class="page-header" style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem">
          <div>
            <p class="page-eyebrow" style="color:var(--accent);font-weight:600;letter-spacing:0.5px">EXECUTIVE INTELLIGENCE</p>
            <h2 class="page-title" style="display:flex;align-items:center;gap:0.5rem">
              PocketPay Premium <span style="font-size:1.4rem">👑</span>
            </h2>
            <p class="page-sub">Next-generation financial automation, smart pocket rules, predictive balance forecasting, and executive concierge.</p>
          </div>
          <div class="page-actions">
            <span class="chip ${isPrem ? 'success' : 'warning'}" style="font-size:0.85rem;padding:6px 14px;font-weight:600">
              ${isPrem ? '✨ Premium Active' : 'Standard Tier'}
            </span>
          </div>
        </div>

        <!-- Active Subscription Status Banner -->
        ${isPrem ? `
          <div class="glass-card" style="background:linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(16,185,129,0.12) 100%);border:1px solid rgba(99,102,241,0.35);border-radius:20px;padding:1.75rem 2rem;box-shadow:0 10px 30px rgba(0,0,0,0.2)">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;margin-bottom:1rem">
              <div style="display:flex;align-items:center;gap:0.85rem">
                <div style="width:48px;height:48px;border-radius:14px;background:linear-gradient(135deg,#6366f1,#10b981);display:flex;align-items:center;justify-content:center;color:white;font-size:1.35rem;box-shadow:0 4px 12px rgba(99,102,241,0.4)">
                  👑
                </div>
                <div>
                  <h3 style="margin:0;font-size:1.25rem;font-weight:700">PocketPay Premium Active</h3>
                  <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">Plan: <b>${(sub?.plan || 'MONTHLY').toUpperCase()}</b> · Status: <span class="chip success" style="font-size:0.75rem">${sub?.status || 'ACTIVE'}</span></p>
                </div>
              </div>
              <div style="display:flex;gap:0.75rem">
                <button class="btn btn-outline" style="border-color:var(--accent);color:var(--accent)" onclick="PP.navigate('analytics')">
                  <i data-lucide="bar-chart-2"></i> Analytics
                </button>
                <button class="btn btn-ghost" id="cancelSubBtn" style="color:var(--danger)">
                  <i data-lucide="x-circle"></i> Cancel Subscription
                </button>
              </div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:1rem;padding-top:1rem;border-top:1px solid rgba(255,255,255,0.08);font-size:0.85rem">
              <div>
                <div style="color:var(--text-dim);font-size:0.75rem;text-transform:uppercase">Valid From</div>
                <div style="font-weight:600;color:var(--text);margin-top:2px">${sub?.start_date ? new Date(sub.start_date).toLocaleDateString() : 'Active'}</div>
              </div>
              <div>
                <div style="color:var(--text-dim);font-size:0.75rem;text-transform:uppercase">Renews / Expires</div>
                <div style="font-weight:600;color:var(--accent);margin-top:2px">${sub?.expiry_date ? new Date(sub.expiry_date).toLocaleDateString() : 'Active Billing Cycle'}</div>
              </div>
              <div>
                <div style="color:var(--text-dim);font-size:0.75rem;text-transform:uppercase">Gateway Order ID</div>
                <div style="font-family:monospace;font-size:0.8rem;color:var(--text-muted);margin-top:2px">${sub?.provider_order_id || sub?.order_id || 'ORDER_ACTIVE'}</div>
              </div>
            </div>
          </div>
        ` : ''}

        ${!isPrem ? `
          <!-- Pricing & Upgrade Cards -->
          <div class="glass-card" style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:16px;padding:1rem 1.5rem;display:flex;align-items:center;gap:1rem">
            <i data-lucide="shield-check" style="color:var(--accent);width:26px;height:26px;flex-shrink:0"></i>
            <p style="margin:0;font-size:0.85rem;color:var(--text-muted);line-height:1.4">
              <b style="color:var(--text)">Bank-Grade Payment Infrastructure:</b> All checkouts are securely processed via Razorpay gateway with backend HMAC-SHA256 signature verification. In sandbox/development environments, full cryptographic receipts are generated seamlessly.
            </p>
          </div>

          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(310px, 1fr));gap:1.5rem">
            <!-- Free Plan -->
            <div class="glass-card" style="border:1px solid var(--border);border-radius:20px;padding:2rem;display:flex;flex-direction:column;justify-content:space-between;background:var(--surface)">
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                  <h3 style="margin:0;font-size:1.25rem;font-weight:700">Standard Tier</h3>
                  <span class="chip" style="font-size:0.75rem">Current Plan</span>
                </div>
                <div style="margin-bottom:1.5rem">
                  <span style="font-size:2.25rem;font-weight:800;color:var(--text)">₹0</span>
                  <span style="color:var(--text-dim);font-size:0.9rem"> / forever</span>
                </div>
                <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">Essential budgeting and basic money movements for everyday personal expense tracking.</p>

                <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:0.75rem;font-size:0.85rem">
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check" style="color:var(--success);width:16px"></i> Standard Smart Pockets</li>
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check" style="color:var(--success);width:16px"></i> P2P Transfers & Universal QR</li>
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check" style="color:var(--success);width:16px"></i> 4-Digit PIN & 2FA Security</li>
                  <li style="display:flex;align-items:center;gap:0.5rem;color:var(--text-dim)"><i data-lucide="x" style="color:var(--text-dim);width:16px"></i> Automated Pocket Rules Engine</li>
                  <li style="display:flex;align-items:center;gap:0.5rem;color:var(--text-dim)"><i data-lucide="x" style="color:var(--text-dim);width:16px"></i> Vault Pocket Lock Enforcement</li>
                  <li style="display:flex;align-items:center;gap:0.5rem;color:var(--text-dim)"><i data-lucide="x" style="color:var(--text-dim);width:16px"></i> 30-Day Future Balance Forecast</li>
                </ul>
              </div>

              <button class="btn btn-outline" style="width:100%;margin-top:2rem" disabled>
                Current Tier
              </button>
            </div>

            <!-- Monthly Plan -->
            <div class="glass-card" style="border:1px solid rgba(99,102,241,0.4);border-radius:20px;padding:2rem;display:flex;flex-direction:column;justify-content:space-between;background:var(--surface)">
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                  <h3 style="margin:0;font-size:1.25rem;font-weight:700">Premium Pro</h3>
                  <span class="chip success" style="font-size:0.75rem">Monthly</span>
                </div>
                <div style="margin-bottom:1.5rem">
                  <span style="font-size:2.25rem;font-weight:800;color:var(--accent)">₹99</span>
                  <span style="color:var(--text-dim);font-size:0.9rem"> / month</span>
                </div>
                <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">Full access to automated rules, pocket locks, predictive balance run-rate, and smart concierge.</p>

                <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:0.75rem;font-size:0.85rem">
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>IF → THEN Automation Engine</b></li>
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Locked Pockets with Goal & Date Protection</b></li>
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Future Balance Run-Rate Forecast</b></li>
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Recurring Subscription Detector</b></li>
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>High-Value Payment Approval Mode</b></li>
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Multi-Pocket Payment Routing</b></li>
                </ul>
              </div>

              <button class="btn btn-outline" id="subscribeMonthlyBtn" style="width:100%;margin-top:2rem;border-color:var(--accent);color:var(--accent)">
                <i data-lucide="sparkles"></i> Upgrade Plan (₹99/mo)
              </button>
            </div>

            <!-- Yearly Plan (Best Value) -->
            <div class="glass-card" style="border:2px solid var(--accent);border-radius:20px;padding:2rem;display:flex;flex-direction:column;justify-content:space-between;background:linear-gradient(180deg, rgba(99,102,241,0.08) 0%, var(--surface) 100%);position:relative;box-shadow:0 12px 40px rgba(99,102,241,0.18)">
              <div style="position:absolute;top:-12px;right:24px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;padding:3px 12px;border-radius:20px;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">
                Best Value (Save 33%)
              </div>

              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                  <h3 style="margin:0;font-size:1.25rem;font-weight:700;color:var(--accent)">Pro Annual</h3>
                  <span class="chip success" style="font-size:0.75rem">VIP 👑</span>
                </div>
                <div style="margin-bottom:1.5rem">
                  <span style="font-size:2.25rem;font-weight:800;color:var(--text)">₹799</span>
                  <span style="color:var(--text-dim);font-size:0.9rem"> / year</span>
                </div>
                <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">Full 365-day access to all premium features, priority concierge, and custom financial export.</p>

                <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:0.75rem;font-size:0.85rem">
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>All Monthly Features Included</b></li>
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Unlimited Pocket Automation Rules</b></li>
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Dedicated Executive Concierge AI</b></li>
                  <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Priority Webhook & Real-Time Sync</b></li>
                </ul>
              </div>

              <button class="btn btn-primary" id="subscribeYearlyBtn" style="width:100%;margin-top:2rem;font-weight:700">
                <i data-lucide="crown"></i> Upgrade Plan (₹799/yr)
              </button>
            </div>
          </div>
        ` : ''}

        <!-- Interactive Premium Features Suite -->
        <div class="glass-card" style="border-radius:20px;padding:1.5rem;border:1px solid rgba(255,255,255,0.08);background:var(--surface)">
          <!-- Navigation Tabs -->
          <div style="display:flex;gap:0.5rem;overflow-x:auto;padding-bottom:1rem;border-bottom:1px solid var(--border)">
            ${[
              { id: 'rules', label: '⚡ Rules Engine', icon: 'zap' },
              { id: 'lock', label: '🔒 Pocket Lock', icon: 'lock' },
              { id: 'forecast', label: '📈 Forecast', icon: 'trending-up' },
              { id: 'subscriptions', label: '🕵️ Subscriptions', icon: 'repeat' },
              { id: 'approval', label: '🛡️ Approval Mode', icon: 'shield-alert' },
              { id: 'simulator', label: '🧮 Simulator', icon: 'calculator' },
              { id: 'routing', label: '🔀 Routing', icon: 'git-merge' },
              { id: 'concierge', label: '🤖 Concierge', icon: 'bot' }
            ].map(tab => `
              <button class="btn ${PP.Premium.currentTab === tab.id ? 'btn-primary' : 'btn-ghost'} premium-tab-btn" data-tab="${tab.id}" style="white-space:nowrap;font-size:0.85rem;padding:6px 14px">
                ${tab.label}
              </button>
            `).join('')}
          </div>

          <!-- Feature Container -->
          <div id="premiumFeatureContainer" style="padding-top:1.5rem">
            <div style="text-align:center;padding:2rem"><i data-lucide="loader" class="spin"></i> Loading feature...</div>
          </div>
        </div>
      </div>
    `;

    PP.refreshIcons();

    // Bind subscribe buttons
    const monthlyBtn = container.querySelector('#subscribeMonthlyBtn');
    const yearlyBtn = container.querySelector('#subscribeYearlyBtn');
    const cancelBtn = container.querySelector('#cancelSubBtn');

    if (monthlyBtn && !isPrem) {
      monthlyBtn.onclick = () => PP.Premium.startCheckout('monthly', 99, container);
    }
    if (yearlyBtn && !isPrem) {
      yearlyBtn.onclick = () => PP.Premium.startCheckout('yearly', 799, container);
    }

    if (cancelBtn) {
      cancelBtn.onclick = async () => {
        if (!confirm('Are you sure you want to cancel your PocketPay Premium subscription? You retain access until the end of your billing cycle.')) return;
        try {
          cancelBtn.disabled = true;
          await PP.PremiumAPI.cancel();
          PP.UI.toast('Subscription Cancelled', 'Your subscription will not renew.', 'info');
          await PP.loadState?.();
          PP.Premium.render(container);
        } catch (e) {
          PP.UI.toast('Cancellation Failed', e.message || 'Error cancelling subscription', 'error');
          cancelBtn.disabled = false;
        }
      };
    }

    // Bind tab clicks
    container.querySelectorAll('.premium-tab-btn').forEach(btn => {
      btn.onclick = () => {
        PP.Premium.currentTab = btn.dataset.tab;
        container.querySelectorAll('.premium-tab-btn').forEach(b => {
          b.className = b.dataset.tab === PP.Premium.currentTab ? 'btn btn-primary premium-tab-btn' : 'btn btn-ghost premium-tab-btn';
        });
        PP.Premium.renderActiveTab(container, isPrem);
      };
    });

    // Render initial active tab
    PP.Premium.renderActiveTab(container, isPrem);
  },

  async renderActiveTab(container, isPrem) {
    const featContainer = container.querySelector('#premiumFeatureContainer');
    if (!featContainer) return;

    if (!isPrem) {
      featContainer.innerHTML = `
        <div style="text-align:center;padding:3rem 1.5rem;background:rgba(99,102,241,0.05);border-radius:16px;border:1px dashed rgba(99,102,241,0.3)">
          <span style="font-size:2.5rem">👑</span>
          <h3 style="margin:0.75rem 0 0.5rem;font-size:1.25rem;font-weight:700">Premium Feature Locked</h3>
          <p style="margin:0 auto 1.5rem;max-width:460px;font-size:0.85rem;color:var(--text-muted)">
            This executive tool is available exclusively on the PocketPay Premium plan. Upgrade now to unlock real-time financial automation and predictive analytics.
          </p>
          <button class="btn btn-primary" onclick="document.querySelector('#subscribeMonthlyBtn')?.scrollIntoView({behavior:'smooth'})">
            <i data-lucide="sparkles"></i> Upgrade Plan to Unlock
          </button>
        </div>
      `;
      PP.refreshIcons();
      return;
    }

    switch (PP.Premium.currentTab) {
      case 'rules':
        await PP.Premium.renderRulesTab(featContainer);
        break;
      case 'lock':
        await PP.Premium.renderLockTab(featContainer);
        break;
      case 'forecast':
        await PP.Premium.renderForecastTab(featContainer);
        break;
      case 'subscriptions':
        await PP.Premium.renderSubscriptionsTab(featContainer);
        break;
      case 'approval':
        await PP.Premium.renderApprovalTab(featContainer);
        break;
      case 'simulator':
        await PP.Premium.renderSimulatorTab(featContainer);
        break;
      case 'routing':
        await PP.Premium.renderRoutingTab(featContainer);
        break;
      case 'concierge':
        await PP.Premium.renderConciergeTab(featContainer);
        break;
      default:
        await PP.Premium.renderRulesTab(featContainer);
    }
  },

  // ========== 1. RULES ENGINE ==========
  async renderRulesTab(featContainer) {
    featContainer.innerHTML = `<div style="text-align:center;padding:2rem"><i data-lucide="loader" class="spin"></i> Loading automation rules...</div>`;
    PP.refreshIcons();

    try {
      const res = await PP.PremiumAPI.getRules();
      const rules = res.data?.rules || res.rules || [];
      const pockets = PP.state.pockets || [];

      featContainer.innerHTML = `
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;flex-wrap:wrap;gap:1rem">
            <div>
              <h3 style="margin:0;font-size:1.15rem;font-weight:700">⚡ Pocket Rules Automation Engine</h3>
              <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">Create IF → THEN rules to automatically allocate income and manage balances.</p>
            </div>
            <button class="btn btn-primary" id="openCreateRuleBtn">
              <i data-lucide="plus"></i> Create Automation Rule
            </button>
          </div>

          ${rules.length === 0 ? `
            <div style="text-align:center;padding:3rem 1rem;background:var(--surface-hover);border-radius:16px;border:1px dashed var(--border)">
              <i data-lucide="zap-off" style="width:36px;height:36px;color:var(--text-dim);margin-bottom:0.75rem"></i>
              <p style="margin:0;font-weight:600">No automation rules configured yet</p>
              <p style="margin:0.25rem 0 1rem;font-size:0.85rem;color:var(--text-muted)">Example: "IF income is received → allocate 30% to Emergency Pocket"</p>
            </div>
          ` : `
            <div style="display:flex;flex-direction:column;gap:1rem">
              ${rules.map(r => `
                <div class="glass-card" style="padding:1.25rem 1.5rem;border:1px solid var(--border);border-radius:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem">
                  <div>
                    <div style="display:flex;align-items:center;gap:0.5rem">
                      <h4 style="margin:0;font-size:1rem;font-weight:700">${r.name}</h4>
                      <span class="chip ${r.is_active ? 'success' : ''}" style="font-size:0.75rem">${r.is_active ? 'Active' : 'Disabled'}</span>
                    </div>
                    <p style="margin:0.35rem 0 0;font-size:0.85rem;color:var(--text-muted)">
                      <b>IF:</b> ${r.trigger_type.replace(/_/g, ' ')} ${r.trigger_threshold ? `(> ₹${r.trigger_threshold:,.2f})` : ''} 
                      → <b>THEN:</b> ${r.action_type === 'ALLOCATE_PERCENT' ? `Allocate ${r.action_value}%` : `Move ₹${r.action_value:,.2f}`} to <b>${r.target_pocket_name || 'Target Pocket'}</b>
                    </p>
                    <div style="display:flex;gap:1.5rem;font-size:0.75rem;color:var(--text-dim);margin-top:0.4rem">
                      <span>Executions: <b>${r.execution_count || 0}</b></span>
                      <span>Last executed: <b>${r.last_executed_at ? new Date(r.last_executed_at).toLocaleString() : 'Never'}</b></span>
                      <span>Status: <b>${r.last_status || 'READY'}</b></span>
                    </div>
                  </div>
                  <div style="display:flex;gap:0.5rem">
                    <button class="btn btn-outline toggle-rule-btn" data-id="${r.id}" data-active="${r.is_active}" style="padding:6px 12px;font-size:0.8rem">
                      ${r.is_active ? 'Disable' : 'Enable'}
                    </button>
                    <button class="btn btn-ghost delete-rule-btn" data-id="${r.id}" style="color:var(--danger);padding:6px">
                      <i data-lucide="trash-2"></i>
                    </button>
                  </div>
                </div>
              `).join('')}
            </div>
          `}
        </div>
      `;
      PP.refreshIcons();

      // Bind events
      const createBtn = featContainer.querySelector('#openCreateRuleBtn');
      if (createBtn) {
        createBtn.onclick = () => PP.Premium.showCreateRuleModal(pockets, () => PP.Premium.renderRulesTab(featContainer));
      }

      featContainer.querySelectorAll('.toggle-rule-btn').forEach(b => {
        b.onclick = async () => {
          const ruleId = b.dataset.id;
          const currentActive = b.dataset.active === 'true';
          try {
            await PP.PremiumAPI.toggleRule(ruleId, !currentActive);
            PP.UI.toast('Rule Updated', `Rule is now ${!currentActive ? 'Active' : 'Disabled'}`, 'success');
            PP.Premium.renderRulesTab(featContainer);
          } catch (e) {
            PP.UI.toast('Error', e.message || 'Could not toggle rule', 'error');
          }
        };
      });

      featContainer.querySelectorAll('.delete-rule-btn').forEach(b => {
        b.onclick = async () => {
          if (!confirm('Are you sure you want to delete this automation rule?')) return;
          try {
            await PP.PremiumAPI.deleteRule(b.dataset.id);
            PP.UI.toast('Rule Deleted', 'Automation rule removed.', 'info');
            PP.Premium.renderRulesTab(featContainer);
          } catch (e) {
            PP.UI.toast('Error', e.message || 'Could not delete rule', 'error');
          }
        };
      });
    } catch (e) {
      featContainer.innerHTML = `<div class="error-banner">${e.message || 'Failed to load rules'}</div>`;
    }
  },

  showCreateRuleModal(pockets, onSuccess) {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:9999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(6px);padding:1rem';

    modal.innerHTML = `
      <div class="glass-card" style="width:100%;max-width:480px;background:var(--surface);border:1px solid rgba(99,102,241,0.4);border-radius:24px;padding:2rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem">
          <h3 style="margin:0;font-size:1.2rem;font-weight:700">⚡ New Automation Rule</h3>
          <button id="closeModal" class="btn btn-ghost" style="padding:4px"><i data-lucide="x"></i></button>
        </div>

        <form id="createRuleForm" style="display:flex;flex-direction:column;gap:1.25rem">
          <div>
            <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">Rule Name</label>
            <input type="text" id="ruleName" class="form-input" placeholder="e.g. 30% Salary to Emergency Pocket" required style="width:100%">
          </div>

          <div>
            <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">IF Trigger Condition</label>
            <select id="ruleTriggerType" class="form-input" style="width:100%">
              <option value="INCOME_RECEIVED">IF salary or income is received</option>
              <option value="BALANCE_EXCEEDS">IF wallet balance exceeds threshold</option>
              <option value="RECURRING_INCOME">IF recurring deposit arrives</option>
            </select>
          </div>

          <div id="thresholdGroup" style="display:none">
            <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">Balance Threshold (₹)</label>
            <input type="number" id="ruleThreshold" class="form-input" placeholder="e.g. 50000" min="1" step="1" style="width:100%">
          </div>

          <div>
            <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">THEN Action</label>
            <select id="ruleActionType" class="form-input" style="width:100%">
              <option value="ALLOCATE_PERCENT">Allocate percentage of incoming amount (%)</option>
              <option value="MOVE_FIXED_AMOUNT">Move fixed amount (₹)</option>
            </select>
          </div>

          <div>
            <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem" id="actionValLabel">Percentage (%)</label>
            <input type="number" id="ruleActionVal" class="form-input" placeholder="e.g. 30" min="1" step="0.5" required style="width:100%">
          </div>

          <div>
            <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">Target Pocket</label>
            <select id="ruleTargetPocket" class="form-input" required style="width:100%">
              ${pockets.filter(p => !p.archived).map(p => `
                <option value="${p.id}">${p.name} (Current: ₹${p.current_balance:,.2f})</option>
              `).join('')}
            </select>
          </div>

          <button type="submit" class="btn btn-primary" style="width:100%;margin-top:0.5rem;font-weight:700">
            Create Automation Rule
          </button>
        </form>
      </div>
    `;

    document.body.appendChild(modal);
    PP.refreshIcons();

    modal.querySelector('#closeModal').onclick = () => modal.remove();

    const triggerSelect = modal.querySelector('#ruleTriggerType');
    const thresholdGroup = modal.querySelector('#thresholdGroup');
    triggerSelect.onchange = () => {
      thresholdGroup.style.display = triggerSelect.value === 'BALANCE_EXCEEDS' ? 'block' : 'none';
    };

    const actionSelect = modal.querySelector('#ruleActionType');
    const actionLabel = modal.querySelector('#actionValLabel');
    actionSelect.onchange = () => {
      actionLabel.innerText = actionSelect.value === 'ALLOCATE_PERCENT' ? 'Percentage (%)' : 'Amount to Move (₹)';
    };

    modal.querySelector('#createRuleForm').onsubmit = async (e) => {
      e.preventDefault();
      try {
        const payload = {
          name: modal.querySelector('#ruleName').value.trim(),
          trigger_type: triggerSelect.value,
          trigger_threshold: modal.querySelector('#ruleThreshold').value ? parseFloat(modal.querySelector('#ruleThreshold').value) : null,
          action_type: actionSelect.value,
          action_value: parseFloat(modal.querySelector('#ruleActionVal').value),
          target_pocket_id: parseInt(modal.querySelector('#ruleTargetPocket').value, 10)
        };
        await PP.PremiumAPI.createRule(payload);
        modal.remove();
        PP.UI.toast('Automation Rule Created', 'Your smart rule is active.', 'success');
        onSuccess?.();
      } catch (err) {
        PP.UI.toast('Failed to Create Rule', err.message || 'Validation error', 'error');
      }
    };
  },

  // ========== 2. POCKET LOCK ==========
  async renderLockTab(featContainer) {
    const pockets = PP.state.pockets || [];
    featContainer.innerHTML = `
      <div>
        <div style="margin-bottom:1.5rem">
          <h3 style="margin:0;font-size:1.15rem;font-weight:700">🔒 Pocket Lock & Savings Protection</h3>
          <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">
            Lock specific pockets until a target date or goal amount. Locked funds remain visible in your total balance but cannot be accidentally spent.
          </p>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:1rem">
          ${pockets.filter(p => !p.archived).map(p => `
            <div class="glass-card" style="padding:1.5rem;border:1px solid ${p.is_currently_locked ? 'rgba(239,68,68,0.4)' : 'var(--border)'};border-radius:18px;display:flex;flex-direction:column;justify-content:space-between;background:var(--surface)">
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem">
                  <div style="display:flex;align-items:center;gap:0.5rem">
                    <span style="font-size:1.2rem">${p.icon === 'piggy-bank' ? '🐷' : '💼'}</span>
                    <h4 style="margin:0;font-size:1.05rem;font-weight:700">${p.name}</h4>
                  </div>
                  <span class="chip ${p.is_currently_locked ? 'danger' : 'success'}" style="font-size:0.75rem">
                    ${p.is_currently_locked ? '🔒 LOCKED' : '🔓 Unlocked'}
                  </span>
                </div>

                <div style="margin:1rem 0">
                  <span style="font-size:1.75rem;font-weight:800;color:var(--text)">₹${(p.current_balance || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
                </div>

                ${p.is_currently_locked ? `
                  <div style="background:rgba(239,68,68,0.08);border-radius:12px;padding:0.75rem 1rem;margin-bottom:1rem;font-size:0.8rem;line-height:1.4">
                    <div style="color:var(--danger);font-weight:600">Reason: ${p.lock_reason || 'Protected savings'}</div>
                    ${p.locked_until_date ? `<div style="color:var(--text-muted);margin-top:2px">Unlock date: ${new Date(p.locked_until_date).toLocaleDateString()}</div>` : ''}
                    ${p.locked_goal_amount ? `<div style="color:var(--text-muted);margin-top:2px">Goal amount: ₹${p.locked_goal_amount:,.2f}</div>` : ''}
                  </div>
                ` : `
                  <p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:1rem">
                    Normal spending permitted. Lock to enforce goal commitment.
                  </p>
                `}
              </div>

              <div>
                ${p.is_currently_locked ? `
                  <button class="btn btn-outline unlock-pocket-btn" data-id="${p.id}" style="width:100%;border-color:var(--accent);color:var(--accent)">
                    <i data-lucide="unlock"></i> Unlock Pocket
                  </button>
                ` : `
                  <button class="btn btn-primary lock-pocket-btn" data-id="${p.id}" data-name="${p.name}" style="width:100%">
                    <i data-lucide="lock"></i> Lock This Pocket
                  </button>
                `}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
    PP.refreshIcons();

    featContainer.querySelectorAll('.lock-pocket-btn').forEach(b => {
      b.onclick = () => PP.Premium.showLockModal(b.dataset.id, b.dataset.name, async () => {
        await PP.loadState?.();
        PP.Premium.renderLockTab(featContainer);
      });
    });

    featContainer.querySelectorAll('.unlock-pocket-btn').forEach(b => {
      b.onclick = async () => {
        if (!confirm('Unlock this pocket? Its funds will once again be available for normal payments.')) return;
        try {
          await PP.PremiumAPI.unlockPocket(b.dataset.id);
          PP.UI.toast('Pocket Unlocked', 'Funds are now spendable.', 'success');
          await PP.loadState?.();
          PP.Premium.renderLockTab(featContainer);
        } catch (e) {
          PP.UI.toast('Unlock Failed', e.message || 'Error', 'error');
        }
      };
    });
  },

  showLockModal(pocketId, pocketName, onSuccess) {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:9999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(6px);padding:1rem';

    modal.innerHTML = `
      <div class="glass-card" style="width:100%;max-width:440px;background:var(--surface);border:1px solid rgba(99,102,241,0.4);border-radius:24px;padding:2rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.25rem">
          <h3 style="margin:0;font-size:1.2rem;font-weight:700">🔒 Lock "${pocketName}"</h3>
          <button id="closeLockModal" class="btn btn-ghost" style="padding:4px"><i data-lucide="x"></i></button>
        </div>

        <form id="lockPocketForm" style="display:flex;flex-direction:column;gap:1.25rem">
          <div>
            <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">Lock Reason / Goal Name</label>
            <input type="text" id="lockReason" class="form-input" placeholder="e.g. Vacation Fund or Emergency Stash" required style="width:100%">
          </div>

          <div>
            <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">Lock Until Date (Optional)</label>
            <input type="date" id="lockDate" class="form-input" style="width:100%">
          </div>

          <div>
            <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">Lock Until Goal Amount (₹) (Optional)</label>
            <input type="number" id="lockGoal" class="form-input" placeholder="e.g. 25000" min="1" step="1" style="width:100%">
          </div>

          <p style="font-size:0.75rem;color:var(--text-muted);margin:0;line-height:1.4">
            <b>Protection Guarantee:</b> When locked, PocketPay payment endpoints will strictly prohibit spending from this pocket until it is unlocked.
          </p>

          <button type="submit" class="btn btn-primary" style="width:100%;font-weight:700">
            Confirm & Lock Pocket
          </button>
        </form>
      </div>
    `;

    document.body.appendChild(modal);
    PP.refreshIcons();

    modal.querySelector('#closeLockModal').onclick = () => modal.remove();

    modal.querySelector('#lockPocketForm').onsubmit = async (e) => {
      e.preventDefault();
      try {
        const payload = {
          reason: modal.querySelector('#lockReason').value.trim(),
          until_date: modal.querySelector('#lockDate').value || null,
          goal_amount: modal.querySelector('#lockGoal').value ? parseFloat(modal.querySelector('#lockGoal').value) : null
        };
        await PP.PremiumAPI.lockPocket(pocketId, payload);
        modal.remove();
        PP.UI.toast('Pocket Locked', `"${pocketName}" is now locked.`, 'success');
        onSuccess?.();
      } catch (err) {
        PP.UI.toast('Lock Failed', err.message || 'Error locking pocket', 'error');
      }
    };
  },

  // ========== 3. FUTURE BALANCE FORECAST ==========
  async renderForecastTab(featContainer) {
    featContainer.innerHTML = `<div style="text-align:center;padding:2rem"><i data-lucide="loader" class="spin"></i> Calculating forecast...</div>`;
    PP.refreshIcons();

    try {
      const res = await PP.PremiumAPI.getForecast(30);
      const f = res.data || res;

      featContainer.innerHTML = `
        <div>
          <div style="margin-bottom:1.5rem">
            <h3 style="margin:0;font-size:1.15rem;font-weight:700">📈 30-Day Future Balance Forecast</h3>
            <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">
              Data-backed run-rate forecast analyzing historical income, recurring subscriptions, and daily spend rate.
            </p>
          </div>

          <!-- Forecast Breakdown Cards Grid -->
          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:1rem;margin-bottom:1.5rem">
            <div class="glass-card" style="padding:1.25rem;border-radius:16px">
              <div style="font-size:0.75rem;color:var(--text-dim);text-transform:uppercase">Actual Liquid Balance</div>
              <div style="font-size:1.5rem;font-weight:800;color:var(--text);margin-top:4px">₹${f.actual_balance.toLocaleString('en-IN', {minimumFractionDigits: 2})}</div>
              <div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px">Wallet: ₹${f.wallet_balance:,.2f} · Pockets: ₹${f.pockets_balance:,.2f}</div>
            </div>

            <div class="glass-card" style="padding:1.25rem;border-radius:16px">
              <div style="font-size:0.75rem;color:var(--text-dim);text-transform:uppercase">Expected 30D Income</div>
              <div style="font-size:1.5rem;font-weight:800;color:var(--success);margin-top:4px">+ ₹${f.expected_income.toLocaleString('en-IN', {minimumFractionDigits: 2})}</div>
              <div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px">Based on recent credit cadence</div>
            </div>

            <div class="glass-card" style="padding:1.25rem;border-radius:16px">
              <div style="font-size:0.75rem;color:var(--text-dim);text-transform:uppercase">Expected Expenses</div>
              <div style="font-size:1.5rem;font-weight:800;color:var(--danger);margin-top:4px">- ₹${f.expected_expenses.toLocaleString('en-IN', {minimumFractionDigits: 2})}</div>
              <div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px">Daily burn-rate extrapolation</div>
            </div>

            <div class="glass-card" style="padding:1.25rem;border-radius:16px">
              <div style="font-size:0.75rem;color:var(--text-dim);text-transform:uppercase">Upcoming Commitments</div>
              <div style="font-size:1.5rem;font-weight:800;color:var(--accent);margin-top:4px">- ₹${f.upcoming_commitments.toLocaleString('en-IN', {minimumFractionDigits: 2})}</div>
              <div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px">Known recurring subscriptions</div>
            </div>
          </div>

          <!-- Projected Outcome Banner -->
          <div class="glass-card" style="background:linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(16,185,129,0.1) 100%);border:1px solid rgba(99,102,241,0.3);border-radius:18px;padding:1.5rem 2rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem">
            <div>
              <p style="margin:0;font-size:0.85rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px">Projected 30-Day Net Balance</p>
              <h2 style="margin:0.25rem 0 0;font-size:2.2rem;font-weight:800;color:var(--accent)">
                ₹${f.projected_balance.toLocaleString('en-IN', {minimumFractionDigits: 2})}
              </h2>
            </div>
            <div style="text-align:right">
              <span class="chip ${f.projected_balance > f.actual_balance ? 'success' : 'warning'}" style="font-size:0.85rem;padding:6px 14px">
                ${f.projected_balance > f.actual_balance ? '📈 Positive Growth Trend' : '⚠️ Net Outflow Trend'}
              </span>
            </div>
          </div>

          <p style="font-size:0.75rem;color:var(--text-dim);margin-top:1rem;line-height:1.4">
            <i>Notice: ${f.disclaimer}</i>
          </p>
        </div>
      `;
      PP.refreshIcons();
    } catch (e) {
      featContainer.innerHTML = `<div class="error-banner">${e.message || 'Error loading forecast'}</div>`;
    }
  },

  // ========== 4. SUBSCRIPTION DETECTOR ==========
  async renderSubscriptionsTab(featContainer) {
    featContainer.innerHTML = `<div style="text-align:center;padding:2rem"><i data-lucide="loader" class="spin"></i> Scanning subscriptions...</div>`;
    PP.refreshIcons();

    try {
      const res = await PP.PremiumAPI.getDetectedSubscriptions();
      const subs = res.data?.subscriptions || res.subscriptions || [];

      featContainer.innerHTML = `
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;flex-wrap:wrap;gap:1rem">
            <div>
              <h3 style="margin:0;font-size:1.15rem;font-weight:700">🕵️ Recurring Subscription Detector</h3>
              <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">Identifies recurring merchant patterns and tracks expected renewals automatically.</p>
            </div>
          </div>

          ${subs.length === 0 ? `
            <div style="text-align:center;padding:3rem 1rem;background:var(--surface-hover);border-radius:16px;border:1px dashed var(--border)">
              <i data-lucide="repeat" style="width:36px;height:36px;color:var(--text-dim);margin-bottom:0.75rem"></i>
              <p style="margin:0;font-weight:600">No recurring subscriptions detected yet</p>
              <p style="margin:0.25rem 0 1rem;font-size:0.85rem;color:var(--text-muted)">PocketPay will automatically detect recurring Netflix, Spotify, Amazon Prime, or broadband charges as you make payments.</p>
            </div>
          ` : `
            <div class="table-responsive" style="border-radius:16px;border:1px solid var(--border);overflow:hidden">
              <table class="table" style="width:100%;margin:0">
                <thead>
                  <tr style="background:rgba(255,255,255,0.02)">
                    <th>Service</th>
                    <th>Estimated Amount</th>
                    <th>Frequency</th>
                    <th>Last Payment</th>
                    <th>Next Expected</th>
                    <th>Status</th>
                    <th style="text-align:right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${subs.map(s => `
                    <tr>
                      <td style="font-weight:600">${s.service || s.merchant_name}</td>
                      <td style="font-weight:700;color:var(--accent)">₹${s.amount:,.2f}</td>
                      <td><span class="chip" style="font-size:0.75rem">${s.frequency}</span></td>
                      <td style="font-size:0.85rem;color:var(--text-muted)">${s.last_payment_date ? new Date(s.last_payment_date).toLocaleDateString() : 'Recent'}</td>
                      <td style="font-size:0.85rem;color:var(--text)">${s.next_expected_date ? new Date(s.next_expected_date).toLocaleDateString() : 'Recurring'}</td>
                      <td>
                        <span class="chip ${s.is_confirmed ? 'success' : 'warning'}" style="font-size:0.75rem">
                          ${s.is_confirmed ? 'Subscription' : 'Ignored'}
                        </span>
                      </td>
                      <td style="text-align:right">
                        ${s.is_confirmed ? `
                          <button class="btn btn-ghost update-sub-btn" data-id="${s.id}" data-action="ignore" style="font-size:0.75rem;padding:4px 8px;color:var(--text-muted)">
                            Not a subscription
                          </button>
                        ` : `
                          <button class="btn btn-outline update-sub-btn" data-id="${s.id}" data-action="confirm" style="font-size:0.75rem;padding:4px 8px;color:var(--success);border-color:var(--success)">
                            Mark Subscription
                          </button>
                        `}
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `}
        </div>
      `;
      PP.refreshIcons();

      featContainer.querySelectorAll('.update-sub-btn').forEach(b => {
        b.onclick = async () => {
          const subId = b.dataset.id;
          const action = b.dataset.action;
          try {
            await PP.PremiumAPI.updateDetectedSub(subId, {
              is_confirmed: action === 'confirm',
              is_ignored: action === 'ignore'
            });
            PP.UI.toast('Preference Saved', 'Subscription classification updated.', 'success');
            PP.Premium.renderSubscriptionsTab(featContainer);
          } catch (e) {
            PP.UI.toast('Error', e.message || 'Could not update preference', 'error');
          }
        };
      });
    } catch (e) {
      featContainer.innerHTML = `<div class="error-banner">${e.message || 'Error scanning subscriptions'}</div>`;
    }
  },

  // ========== 5. PAYMENT APPROVAL MODE ==========
  async renderApprovalTab(featContainer) {
    featContainer.innerHTML = `<div style="text-align:center;padding:2rem"><i data-lucide="loader" class="spin"></i> Loading settings...</div>`;
    PP.refreshIcons();

    try {
      const res = await PP.PremiumAPI.getApprovalSettings();
      const s = res.data || res;

      featContainer.innerHTML = `
        <div style="max-width:540px">
          <div style="margin-bottom:1.5rem">
            <h3 style="margin:0;font-size:1.15rem;font-weight:700">🛡️ High-Value Payment Approval Mode</h3>
            <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">
              Protects against accidental or unauthorized large transfers by enforcing explicit dual-step confirmation at the backend layer.
            </p>
          </div>

          <form id="approvalModeForm" class="glass-card" style="padding:1.75rem;border-radius:18px;display:flex;flex-direction:column;gap:1.25rem">
            <div style="display:flex;align-items:center;justify-content:space-between;padding-bottom:1rem;border-bottom:1px solid var(--border)">
              <div>
                <h4 style="margin:0;font-size:0.95rem;font-weight:700">Require High-Value Confirmation</h4>
                <p style="margin:2px 0 0;font-size:0.8rem;color:var(--text-muted)">Block unconfirmed payments above threshold</p>
              </div>
              <input type="checkbox" id="approvalEnabled" ${s.require_payment_approval ? 'checked' : ''} style="width:20px;height:20px;accent-color:var(--accent);cursor:pointer">
            </div>

            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">
                Approval Threshold Amount (₹)
              </label>
              <input type="number" id="approvalThreshold" class="form-input" value="${s.payment_approval_threshold || 5000}" min="100" step="100" required style="width:100%">
              <p style="font-size:0.75rem;color:var(--text-dim);margin:4px 0 0">
                Any payment equal to or exceeding this threshold will require explicit high-value confirmation before funds are deducted.
              </p>
            </div>

            <button type="submit" class="btn btn-primary" style="font-weight:700;margin-top:0.5rem">
              Save Approval Settings
            </button>
          </form>
        </div>
      `;
      PP.refreshIcons();

      featContainer.querySelector('#approvalModeForm').onsubmit = async (e) => {
        e.preventDefault();
        try {
          const enabled = featContainer.querySelector('#approvalEnabled').checked;
          const threshold = parseFloat(featContainer.querySelector('#approvalThreshold').value);
          await PP.PremiumAPI.updateApprovalSettings({
            require_payment_approval: enabled,
            payment_approval_threshold: threshold
          });
          PP.UI.toast('Settings Saved', 'High-value payment approval mode updated.', 'success');
          await PP.loadState?.();
        } catch (err) {
          PP.UI.toast('Save Failed', err.message || 'Error updating settings', 'error');
        }
      };
    } catch (e) {
      featContainer.innerHTML = `<div class="error-banner">${e.message || 'Error loading approval settings'}</div>`;
    }
  },

  // ========== 6. POCKET SIMULATOR ==========
  async renderSimulatorTab(featContainer) {
    featContainer.innerHTML = `
      <div>
        <div style="margin-bottom:1.5rem">
          <h3 style="margin:0;font-size:1.15rem;font-weight:700">🧮 Pocket Allocation Simulator</h3>
          <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">
            Model hypothetical income and fixed expenses to generate recommended pocket distribution targets.
          </p>
        </div>

        <div class="glass-card" style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:14px;padding:0.75rem 1.25rem;margin-bottom:1.5rem;font-size:0.8rem;color:var(--text-muted)">
          <b>Hypothetical Mode:</b> Calculations are purely demonstrative and will NOT modify your live account balance unless you explicitly choose to apply the budget targets.
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:1.5rem">
          <form id="simForm" class="glass-card" style="padding:1.5rem;border-radius:18px;display:flex;flex-direction:column;gap:1rem">
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.3rem">Monthly Income (₹)</label>
              <input type="number" id="simIncome" class="form-input" value="40000" min="1000" step="500" required style="width:100%">
            </div>
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.3rem">Rent & Housing (₹)</label>
              <input type="number" id="simRent" class="form-input" value="12000" min="0" step="500" style="width:100%">
            </div>
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.3rem">Food & Groceries (₹)</label>
              <input type="number" id="simFood" class="form-input" value="6000" min="0" step="500" style="width:100%">
            </div>
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.3rem">Travel & Commute (₹)</label>
              <input type="number" id="simTravel" class="form-input" value="4000" min="0" step="500" style="width:100%">
            </div>
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.3rem">Other Fixed Expenses (₹)</label>
              <input type="number" id="simOther" class="form-input" value="2000" min="0" step="500" style="width:100%">
            </div>

            <button type="submit" class="btn btn-primary" style="font-weight:700;margin-top:0.5rem">
              Run Financial Simulation
            </button>
          </form>

          <div id="simResultsContainer" class="glass-card" style="padding:1.5rem;border-radius:18px;display:flex;flex-direction:column;justify-content:space-between">
            <div>
              <h4 style="margin:0 0 1rem;font-size:1rem;font-weight:700">Proposed Allocation Plan</h4>
              <div id="simResultsContent" style="font-size:0.85rem;color:var(--text-muted)">
                Click "Run Financial Simulation" to view calculated breakdown.
              </div>
            </div>
            <button id="applySimBtn" class="btn btn-outline" style="width:100%;margin-top:1.5rem;display:none;border-color:var(--accent);color:var(--accent)">
              Apply Targets to My Pockets
            </button>
          </div>
        </div>
      </div>
    `;
    PP.refreshIcons();

    let lastSimResult = null;

    const runSim = async () => {
      const income = parseFloat(featContainer.querySelector('#simIncome').value || 0);
      const fixed = {
        rent: parseFloat(featContainer.querySelector('#simRent').value || 0),
        food: parseFloat(featContainer.querySelector('#simFood').value || 0),
        travel: parseFloat(featContainer.querySelector('#simTravel').value || 0),
        other: parseFloat(featContainer.querySelector('#simOther').value || 0)
      };

      try {
        const res = await PP.PremiumAPI.calculateSimulation({ income, fixed_expenses: fixed });
        lastSimResult = res.data || res;
        const s = lastSimResult;

        featContainer.querySelector('#simResultsContent').innerHTML = `
          <div style="display:flex;flex-direction:column;gap:0.75rem">
            <div style="display:flex;justify-content:space-between;padding-bottom:0.5rem;border-bottom:1px solid var(--border)">
              <span>Total Income:</span>
              <span style="font-weight:700;color:var(--text)">₹${s.income:,.2f}</span>
            </div>
            <div style="display:flex;justify-content:space-between;color:var(--danger)">
              <span>Fixed Expenses Total:</span>
              <span style="font-weight:700">- ₹${s.fixed_expenses.total:,.2f}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding-bottom:0.5rem;border-bottom:1px solid var(--border);color:var(--success)">
              <span>Net Disposable Surplus:</span>
              <span style="font-weight:700">₹${s.net_surplus:,.2f}</span>
            </div>

            <div style="background:var(--surface-hover);border-radius:12px;padding:0.75rem 1rem;display:flex;flex-direction:column;gap:0.4rem;font-size:0.85rem">
              <div style="display:flex;justify-content:space-between">
                <span>🐷 Suggested Savings:</span>
                <span style="font-weight:700;color:var(--accent)">₹${s.suggested_allocation.savings:,.2f}</span>
              </div>
              <div style="display:flex;justify-content:space-between">
                <span>🛡️ Suggested Emergency:</span>
                <span style="font-weight:700;color:var(--accent)">₹${s.suggested_allocation.emergency:,.2f}</span>
              </div>
              <div style="display:flex;justify-content:space-between">
                <span>🎬 Suggested Entertainment:</span>
                <span style="font-weight:700;color:var(--accent)">₹${s.suggested_allocation.entertainment:,.2f}</span>
              </div>
              <div style="display:flex;justify-content:space-between">
                <span>💼 Unallocated Buffer:</span>
                <span style="font-weight:700;color:var(--text-muted)">₹${s.suggested_allocation.buffer:,.2f}</span>
              </div>
            </div>
          </div>
        `;

        const applyBtn = featContainer.querySelector('#applySimBtn');
        if (applyBtn) {
          applyBtn.style.display = 'block';
        }
      } catch (err) {
        PP.UI.toast('Simulation Error', err.message || 'Calculation error', 'error');
      }
    };

    featContainer.querySelector('#simForm').onsubmit = (e) => {
      e.preventDefault();
      runSim();
    };

    // Auto-run initial simulation
    runSim();

    featContainer.querySelector('#applySimBtn').onclick = async () => {
      if (!lastSimResult) return;
      if (!confirm('Apply these suggested targets to your Pockets? This will set monthly budget limits for your Savings and Emergency pockets.')) return;
      try {
        await PP.PremiumAPI.applySimulation(lastSimResult);
        PP.UI.toast('Plan Applied', 'Pocket budget targets updated successfully.', 'success');
        await PP.loadState?.();
      } catch (e) {
        PP.UI.toast('Error', e.message || 'Could not apply simulation', 'error');
      }
    };
  },

  // ========== 7. PAYMENT ROUTING ==========
  async renderRoutingTab(featContainer) {
    const pockets = PP.state.pockets || [];
    featContainer.innerHTML = `
      <div>
        <div style="margin-bottom:1.5rem">
          <h3 style="margin:0;font-size:1.15rem;font-weight:700">🔀 Multi-Pocket Payment Routing</h3>
          <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">
            Preview and configure preferred pocket sources when spending across multiple smart pockets.
          </p>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:1.5rem">
          <div class="glass-card" style="padding:1.5rem;border-radius:18px;display:flex;flex-direction:column;gap:1.25rem">
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">Test Payment Amount (₹)</label>
              <input type="number" id="routingAmount" class="form-input" value="7000" min="1" step="100" style="width:100%">
            </div>

            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:0.4rem">Select Preferred Pocket Priority (Optional)</label>
              <div style="display:flex;flex-direction:column;gap:0.5rem;max-height:200px;overflow-y:auto;padding-right:0.5rem">
                ${pockets.filter(p => !p.archived).map(p => `
                  <label style="display:flex;align-items:center;gap:0.5rem;font-size:0.85rem;cursor:pointer">
                    <input type="checkbox" class="pref-pocket-cb" value="${p.id}" ${!p.is_currently_locked ? 'checked' : 'disabled'}>
                    <span>${p.name} (₹${(p.current_balance || 0).toLocaleString()}) ${p.is_currently_locked ? '🔒 Locked' : ''}</span>
                  </label>
                `).join('')}
              </div>
            </div>

            <button id="previewRoutingBtn" class="btn btn-primary" style="font-weight:700">
              Calculate Routing Plan
            </button>
          </div>

          <div id="routingResultCard" class="glass-card" style="padding:1.5rem;border-radius:18px">
            <h4 style="margin:0 0 1rem;font-size:1rem;font-weight:700">Routing Breakdown Preview</h4>
            <div id="routingResultContent" style="font-size:0.85rem;color:var(--text-muted)">
              Click "Calculate Routing Plan" to simulate multi-pocket deduction.
            </div>
          </div>
        </div>
      </div>
    `;
    PP.refreshIcons();

    const calculateRouting = async () => {
      const amount = parseFloat(featContainer.querySelector('#routingAmount').value || 0);
      const prefIds = Array.from(featContainer.querySelectorAll('.pref-pocket-cb:checked')).map(cb => parseInt(cb.value, 10));

      try {
        const res = await PP.PremiumAPI.previewRouting({ amount, preferred_pocket_ids: prefIds });
        const plan = res.data || res;

        featContainer.querySelector('#routingResultContent').innerHTML = `
          <div style="display:flex;flex-direction:column;gap:0.75rem">
            <div style="display:flex;justify-content:space-between;padding-bottom:0.5rem;border-bottom:1px solid var(--border)">
              <span>Total Requested:</span>
              <span style="font-weight:700">₹${plan.amount:,.2f}</span>
            </div>
            <div style="display:flex;justify-content:space-between;color:${plan.can_fulfill ? 'var(--success)' : 'var(--danger)'}">
              <span>Fulfillable Status:</span>
              <span style="font-weight:700">${plan.can_fulfill ? 'Fully Covered' : `Shortage of ₹${plan.shortage:,.2f}`}</span>
            </div>

            <div style="margin-top:0.5rem">
              <p style="font-size:0.8rem;color:var(--text-dim);text-transform:uppercase;margin:0 0 0.4rem">Calculated Pocket Sources:</p>
              ${plan.routes.length === 0 ? `
                <div style="font-size:0.8rem;color:var(--text-muted)">No eligible unlocked pockets with available balance.</div>
              ` : `
                <div style="display:flex;flex-direction:column;gap:0.5rem">
                  ${plan.routes.map(r => `
                    <div style="background:var(--surface-hover);border-radius:10px;padding:0.6rem 0.85rem;display:flex;justify-content:space-between;align-items:center">
                      <span><b>${r.pocket_name}</b> (Has ₹${r.available_balance:,.2f})</span>
                      <span style="font-weight:700;color:var(--accent)">Deduct ₹${r.amount_to_debit:,.2f}</span>
                    </div>
                  `).join('')}
                </div>
              `}
            </div>

            ${plan.locked_pockets_excluded && plan.locked_pockets_excluded.length > 0 ? `
              <div style="margin-top:0.5rem;background:rgba(239,68,68,0.06);border-radius:10px;padding:0.6rem 0.85rem;font-size:0.75rem;color:var(--danger)">
                <b>Protected Pockets Excluded:</b> ${plan.locked_pockets_excluded.map(lp => `${lp.name} (₹${lp.balance:,.2f})`).join(', ')}
              </div>
            ` : ''}
          </div>
        `;
      } catch (err) {
        PP.UI.toast('Routing Error', err.message || 'Error', 'error');
      }
    };

    featContainer.querySelector('#previewRoutingBtn').onclick = calculateRouting;
    calculateRouting();
  },

  // ========== 8. MONEY CONCIERGE ==========
  async renderConciergeTab(featContainer) {
    featContainer.innerHTML = `
      <div style="max-width:680px">
        <div style="margin-bottom:1.5rem">
          <h3 style="margin:0;font-size:1.15rem;font-weight:700">🤖 Premium Money Concierge</h3>
          <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">
            Ask questions about your finances and receive data-backed answers derived directly from your PocketPay ledger.
          </p>
        </div>

        <!-- Quick Prompts -->
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:1.25rem">
          ${[
            "Can I afford ₹8,000 this month?",
            "Which pocket am I spending the most from?",
            "Why did my balance decrease this month?",
            "How much did I spend on subscriptions?",
            "Show my upcoming commitments",
            "How much have I saved toward my goals?"
          ].map(q => `
            <button class="btn btn-ghost quick-concierge-btn" data-q="${q}" style="background:var(--surface-hover);font-size:0.75rem;padding:5px 12px;border-radius:20px;border:1px solid var(--border)">
              ${q}
            </button>
          `).join('')}
        </div>

        <!-- Query Form -->
        <form id="conciergeForm" style="display:flex;gap:0.5rem;margin-bottom:1.5rem">
          <input type="text" id="conciergeQuery" class="form-input" placeholder="Ask a financial question..." required style="flex:1">
          <button type="submit" class="btn btn-primary" style="font-weight:700;display:flex;align-items:center;gap:0.4rem">
            <i data-lucide="send"></i> Ask
          </button>
        </form>

        <!-- Response Container -->
        <div id="conciergeAnswerBox" class="glass-card" style="padding:1.5rem;border-radius:18px;min-height:120px;display:flex;align-items:center;justify-content:center;text-align:center;color:var(--text-muted)">
          Ask a question or pick one of the quick prompts above.
        </div>
      </div>
    `;
    PP.refreshIcons();

    const askQuery = async (queryText) => {
      const box = featContainer.querySelector('#conciergeAnswerBox');
      box.innerHTML = `<i data-lucide="loader" class="spin"></i> Analyzing your live PocketPay ledger...`;
      PP.refreshIcons();

      try {
        const res = await PP.PremiumAPI.askConcierge(queryText);
        const data = res.data || res;

        box.style.textAlign = 'left';
        box.style.display = 'block';
        box.innerHTML = `
          <div>
            <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem">
              <span style="font-size:1.25rem">🤖</span>
              <h4 style="margin:0;font-size:0.95rem;font-weight:700">Concierge Financial Analysis</h4>
            </div>
            <p style="margin:0;font-size:0.9rem;line-height:1.5;color:var(--text)">
              ${(data.answer || 'Analysis complete.').replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')}
            </p>
            ${data.disclaimer ? `
              <p style="font-size:0.75rem;color:var(--text-dim);margin:0.75rem 0 0">
                <i>${data.disclaimer}</i>
              </p>
            ` : ''}
          </div>
        `;
      } catch (err) {
        box.innerHTML = `<div style="color:var(--danger)">${err.message || 'Error communicating with Concierge'}</div>`;
      }
    };

    featContainer.querySelectorAll('.quick-concierge-btn').forEach(b => {
      b.onclick = () => {
        featContainer.querySelector('#conciergeQuery').value = b.dataset.q;
        askQuery(b.dataset.q);
      };
    });

    featContainer.querySelector('#conciergeForm').onsubmit = (e) => {
      e.preventDefault();
      const q = featContainer.querySelector('#conciergeQuery').value.trim();
      if (q) askQuery(q);
    };
  },

  // ========== CHECKOUT & VERIFICATION (PART 1 FIX) ==========
  async startCheckout(plan, amount, container) {
    try {
      PP.UI.toast('Initiating Checkout', `Setting up ${plan.toUpperCase()} subscription order...`, 'info');
      
      // Step 1: Create Order via PocketPay Backend
      const res = await PP.PremiumAPI.createCheckoutOrder(plan);
      const orderData = res.data || res;

      if (!orderData || !orderData.order_id) {
        throw new Error(res.message || 'Unable to generate order credentials from gateway.');
      }

      if (orderData.sandbox || orderData.is_sandbox || !window.Razorpay) {
        // Developer sandbox mode modal
        PP.Premium.showSandboxCheckout(orderData, plan, amount, container);
      } else {
        // Live Razorpay Checkout
        const rzpOptions = {
          key: orderData.key_id,
          amount: orderData.amount_paise || (amount * 100),
          currency: orderData.currency || 'INR',
          name: 'PocketPay Premium',
          description: `${plan.toUpperCase()} Subscription`,
          order_id: orderData.order_id,
          prefill: {
            name: PP.state.user?.full_name || PP.state.user?.name || '',
            email: PP.state.user?.email || ''
          },
          theme: {
            color: '#6366f1'
          },
          handler: async function (response) {
            await PP.Premium.completeVerification({
              order_id: response.razorpay_order_id,
              payment_id: response.razorpay_payment_id,
              signature: response.razorpay_signature
            }, plan, container);
          },
          modal: {
            ondismiss: function () {
              PP.UI.toast('Payment Cancelled', 'Your payment was cancelled.', 'warning');
            }
          }
        };
        const rzp = new window.Razorpay(rzpOptions);
        rzp.open();
      }
    } catch (err) {
      PP.UI.toast('Order Creation Error', err.message || 'Unable to create payment order. Please try again.', 'error');
    }
  },

  showSandboxCheckout(orderData, plan, amount, container) {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:9999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(6px);padding:1rem';

    modal.innerHTML = `
      <div class="glass-card" style="width:100%;max-width:440px;background:var(--surface);border:1px solid rgba(99,102,241,0.4);border-radius:24px;padding:2rem;box-shadow:0 24px 60px rgba(0,0,0,0.5)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.25rem">
          <div style="display:flex;align-items:center;gap:0.6rem">
            <span style="font-size:1.4rem">🛡️</span>
            <div>
              <h3 style="margin:0;font-size:1.15rem;font-weight:700">PocketPay Checkout</h3>
              <p style="margin:0;font-size:0.75rem;color:var(--text-muted)">Secure Gateway Mode</p>
            </div>
          </div>
          <button id="closeRzpModal" class="btn btn-ghost" style="padding:4px"><i data-lucide="x"></i></button>
        </div>

        <div style="background:rgba(99,102,241,0.08);border-radius:14px;padding:1rem;margin-bottom:1.5rem">
          <div style="display:flex;justify-content:space-between;margin-bottom:0.4rem;font-size:0.85rem">
            <span style="color:var(--text-muted)">Plan:</span>
            <span style="font-weight:600">${plan.toUpperCase()}</span>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:0.4rem;font-size:0.85rem">
            <span style="color:var(--text-muted)">Amount:</span>
            <span style="font-weight:700;color:var(--accent);font-size:1.1rem">₹${amount}</span>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:0.75rem;font-family:monospace;color:var(--text-dim)">
            <span>Order ID:</span>
            <span>${orderData.order_id}</span>
          </div>
        </div>

        <p style="font-size:0.8rem;color:var(--text-muted);line-height:1.4;margin-bottom:1.5rem">
          <b>Gateway Simulation:</b> Verifying payment signature end-to-end. This issues a cryptographically verified receipt and executes the activation handshake on the backend.
        </p>

        <div style="display:flex;flex-direction:column;gap:0.75rem">
          <button id="rzpSimulateSuccess" class="btn btn-primary" style="width:100%;font-weight:700">
            <i data-lucide="check-circle"></i> Complete Payment (₹${amount})
          </button>
          <button id="rzpSimulateFailure" class="btn btn-outline" style="width:100%;border-color:var(--danger);color:var(--danger)">
            <i data-lucide="x-circle"></i> Cancel Payment
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    PP.refreshIcons();

    modal.querySelector('#closeRzpModal').onclick = () => modal.remove();

    modal.querySelector('#rzpSimulateFailure').onclick = () => {
      modal.remove();
      PP.UI.toast('Payment Cancelled', 'Your payment was cancelled. Free tier maintained.', 'warning');
    };

    modal.querySelector('#rzpSimulateSuccess').onclick = async () => {
      const btn = modal.querySelector('#rzpSimulateSuccess');
      btn.disabled = true;
      btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Verifying Server Signature...';
      PP.refreshIcons();

      try {
        const testPaymentId = 'pay_sandbox_' + Date.now().toString(36);
        const testSig = 'sig_sandbox_' + orderData.order_id;
        
        modal.remove();
        await PP.Premium.completeVerification({
          order_id: orderData.order_id,
          payment_id: testPaymentId,
          signature: testSig
        }, plan, container);
      } catch (err) {
        modal.remove();
        PP.UI.toast('Verification Failed', err.message || 'Signature verification failed', 'error');
      }
    };
  },

  async completeVerification(verifyPayload, plan, container) {
    PP.UI.toast('Verifying Payment', 'Validating server signature and activating subscription...', 'info');

    try {
      const res = await PP.PremiumAPI.verifyPayment(verifyPayload);
      const result = res.data || res;

      if (res.success || result.success) {
        await PP.loadState?.();

        const sub = result.subscription || {};
        const expDate = sub.expiry_date ? new Date(sub.expiry_date).toLocaleDateString() : 'N/A';

        PP.UI.showSuccess({
          title: '🎉 Welcome to PocketPay Premium!',
          sub: 'Your Premium plan has been verified and activated.',
          meta: [
            { label: 'Plan', value: (sub.plan || plan).toUpperCase() },
            { label: 'Valid until', value: expDate },
            { label: 'Transaction Reference', value: sub.payment_id || verifyPayload.payment_id || 'CONFIRMED' }
          ]
        });

        PP.Premium.render(container);
      } else {
        PP.UI.toast('Verification Failed', res.message || 'Payment verification failed. Your Premium plan has not been activated.', 'error');
      }
    } catch (e) {
      PP.UI.toast('Verification Failed', e.message || 'Payment verification failed. Your Premium plan has not been activated.', 'error');
    }
  }
};

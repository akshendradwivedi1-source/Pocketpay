// ========== Premium Showcase & Subscription View (Phase 14) ==========
window.PP = window.PP || {};

PP.Premium = {
  async render(container) {
    const u = PP.state.user || {};
    const isPrem = !!u.is_premium;

    container.innerHTML = `
      <div class="stagger" style="display:flex;flex-direction:column;gap:1.5rem">
        <!-- Header -->
        <div class="page-header">
          <div>
            <p class="page-eyebrow">Subscription</p>
            <h2 class="page-title">PocketPay Premium 👑</h2>
            <p class="page-sub">Unlock powerful financial insights, unlimited savings targets, and advanced analytics.</p>
          </div>
          <div class="page-actions">
            <span class="chip ${isPrem ? 'success' : 'warning'}" style="font-size:0.85rem;padding:6px 14px">
              ${isPrem ? '✨ Premium Active' : 'Free Tier'}
            </span>
          </div>
        </div>

        <!-- Sandbox Demo Banner -->
        <div class="glass-card" style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.3);border-radius:16px;padding:1rem 1.5rem;display:flex;align-items:center;gap:1rem">
          <i data-lucide="info" style="color:var(--accent);width:24px;height:24px;flex-shrink:0"></i>
          <p style="margin:0;font-size:0.85rem;color:var(--text-muted);line-height:1.4">
            <b style="color:var(--text)">DEMO / TEST MODE:</b> PocketPay Premium is completely free to experience in this portfolio demonstration. Upgrading instantly enables all pro analytics and unlimited goal features without charging real money.
          </p>
        </div>

        <!-- Status Card if Active -->
        ${isPrem ? `
          <div class="glass-card" style="background:linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(16,185,129,0.1) 100%);border:1px solid rgba(99,102,241,0.35);border-radius:20px;padding:1.5rem 2rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem">
            <div>
              <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.35rem">
                <h3 style="margin:0;font-size:1.15rem;font-weight:700">You are on PocketPay Pro</h3>
                <span class="chip success" style="font-size:0.75rem">VIP Member</span>
              </div>
              <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">All premium features, advanced reports, and unlimited goals are unlocked on your account.</p>
            </div>
            <button class="btn btn-outline" style="border-color:var(--accent);color:var(--accent)" onclick="PP.navigate('analytics')">
              <i data-lucide="bar-chart-2"></i> Explore Pro Analytics
            </button>
          </div>
        ` : ''}

        <!-- Pricing Cards -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:1.5rem">
          <!-- Free Plan -->
          <div class="glass-card" style="border:1px solid var(--border);border-radius:20px;padding:2rem;display:flex;flex-direction:column;justify-content:space-between;background:var(--surface)">
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                <h3 style="margin:0;font-size:1.25rem;font-weight:700">Standard Free</h3>
                <span class="chip" style="font-size:0.75rem">Default</span>
              </div>
              <div style="margin-bottom:1.5rem">
                <span style="font-size:2rem;font-weight:800;color:var(--text)">₹0</span>
                <span style="color:var(--text-dim);font-size:0.9rem"> / forever</span>
              </div>
              <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">Essential budgeting and smart pockets for personal expense tracking.</p>

              <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:0.75rem;font-size:0.85rem">
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check" style="color:var(--success);width:16px"></i> Up to 5 Smart Pockets</li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check" style="color:var(--success);width:16px"></i> Standard P2P Transfers & Requests</li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check" style="color:var(--success);width:16px"></i> 4-Digit PIN Security</li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check" style="color:var(--success);width:16px"></i> Basic Monthly Spending Reports</li>
                <li style="display:flex;align-items:center;gap:0.5rem;color:var(--text-dim)"><i data-lucide="x" style="color:var(--text-dim);width:16px"></i> Advanced AI Financial Insights</li>
                <li style="display:flex;align-items:center;gap:0.5rem;color:var(--text-dim)"><i data-lucide="x" style="color:var(--text-dim);width:16px"></i> Unlimited Savings Targets</li>
              </ul>
            </div>

            <button class="btn btn-ghost" style="width:100%;margin-top:2rem" disabled>
              ${!isPrem ? 'Current Plan' : 'Free Tier'}
            </button>
          </div>

          <!-- Premium Pro Plan -->
          <div class="glass-card" style="border:2px solid var(--accent);border-radius:20px;padding:2rem;display:flex;flex-direction:column;justify-content:space-between;background:linear-gradient(180deg, rgba(99,102,241,0.08) 0%, var(--surface) 100%);position:relative;box-shadow:0 12px 40px rgba(99,102,241,0.18)">
            <div style="position:absolute;top:-12px;right:24px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;padding:3px 12px;border-radius:20px;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">
              Recommended
            </div>

            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                <h3 style="margin:0;font-size:1.25rem;font-weight:700;color:var(--accent)">PocketPay Pro</h3>
                <span class="chip success" style="font-size:0.75rem">VIP</span>
              </div>
              <div style="margin-bottom:1.5rem">
                <span style="font-size:2rem;font-weight:800;color:var(--text)">₹199</span>
                <span style="color:var(--text-dim);font-size:0.9rem"> / month <span style="font-size:0.78rem;color:#818cf8">(Free in Demo)</span></span>
              </div>
              <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">Complete financial super-app experience with pro tools and intelligence.</p>

              <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:0.75rem;font-size:0.85rem">
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Unlimited Smart Pockets & Goals</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Pro Conversational AI Assistant</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Interactive Spending Analytics & CSV Export</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Custom Pocket Gradients & Icons</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Automated Income Split Templates</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>TOTP 2-Factor Hardware Security</b></li>
              </ul>
            </div>

            <button class="btn btn-primary" id="upgradeDemoBtn" style="width:100%;margin-top:2rem;font-weight:700">
              ${isPrem ? '<i data-lucide="check"></i> Already Activated' : '<i data-lucide="sparkles"></i> Activate Demo Premium'}
            </button>
          </div>
        </div>
      </div>
    `;

    PP.refreshIcons();

    const btn = container.querySelector('#upgradeDemoBtn');
    if (btn && !isPrem) {
      btn.onclick = async () => {
        try {
          btn.disabled = true;
          btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Activating...';
          PP.refreshIcons();

          const res = await PP.API.post('/auth/upgrade-premium', { plan: 'annual' });
          PP.UI.showSuccess({
            title: '🎉 Premium Activated!',
            sub: 'You are now on PocketPay Premium (Demo Mode). All pro analytics, unlimited goals, and advanced themes are enabled.',
            meta: [
              { label: 'Tier', value: 'PocketPay Pro (Demo)' },
              { label: 'Status', value: 'Active' },
              { label: 'Cost', value: '₹0 (Demo Sandbox)' }
            ]
          });

          await PP.loadState?.();
          PP.Premium.render(container);
        } catch (err) {
          PP.UI.toast('Upgrade Failed', err.message || 'Could not activate demo premium', 'error');
          btn.disabled = false;
          btn.innerHTML = '<i data-lucide="sparkles"></i> Activate Demo Premium';
          PP.refreshIcons();
        }
      };
    }
  }
};

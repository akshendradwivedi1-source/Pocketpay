// ========== Premium Showcase & Subscription View (Part 9-13, 25) ==========
window.PP = window.PP || {};

PP.Premium = {
  async render(container) {
    let statusData = { is_premium: false, subscription: null };
    try {
      statusData = await PP.API.get('/premium/status');
    } catch (e) {
      statusData = { is_premium: !!PP.state.user?.is_premium, subscription: null };
    }

    const isPrem = !!statusData.is_premium;
    const sub = statusData.subscription;

    container.innerHTML = `
      <div class="stagger" style="display:flex;flex-direction:column;gap:1.5rem">
        <!-- Header -->
        <div class="page-header">
          <div>
            <p class="page-eyebrow">Membership & Intelligence</p>
            <h2 class="page-title">PocketPay Premium 👑</h2>
            <p class="page-sub">Next-generation financial intelligence, automated spending forecasts, smart pocket rules, and unlimited targets.</p>
          </div>
          <div class="page-actions">
            <span class="chip ${isPrem ? 'success' : 'warning'}" style="font-size:0.85rem;padding:6px 14px">
              ${isPrem ? '✨ Premium Active' : 'Free Tier'}
            </span>
          </div>
        </div>

        <!-- Active Subscription Status Banner -->
        ${isPrem ? `
          <div class="glass-card" style="background:linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(16,185,129,0.12) 100%);border:1px solid rgba(99,102,241,0.35);border-radius:20px;padding:1.75rem 2rem">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;margin-bottom:1rem">
              <div style="display:flex;align-items:center;gap:0.75rem">
                <div style="width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,#6366f1,#10b981);display:flex;align-items:center;justify-content:center;color:white;font-size:1.25rem">
                  👑
                </div>
                <div>
                  <h3 style="margin:0;font-size:1.2rem;font-weight:700">PocketPay Premium Pro Active</h3>
                  <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">Plan: <b>${sub?.plan ? sub.plan.toUpperCase() : 'MONTHLY'}</b> · Status: <span class="chip success" style="font-size:0.75rem">${sub?.status || 'ACTIVE'}</span></p>
                </div>
              </div>
              <div style="display:flex;gap:0.75rem">
                <button class="btn btn-outline" style="border-color:var(--accent);color:var(--accent)" onclick="PP.navigate('analytics')">
                  <i data-lucide="bar-chart-2"></i> Open Pro Analytics
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
                <div style="font-weight:600;color:var(--accent);margin-top:2px">${sub?.expiry_date ? new Date(sub.expiry_date).toLocaleDateString() : 'Recurring'}</div>
              </div>
              <div>
                <div style="color:var(--text-dim);font-size:0.75rem;text-transform:uppercase">Gateway Ref</div>
                <div style="font-family:monospace;font-size:0.8rem;color:var(--text-muted);margin-top:2px">${sub?.payment_id || sub?.order_id || 'RZP_PREM_SUB'}</div>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- Mode Notice Banner -->
        <div class="glass-card" style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:16px;padding:1rem 1.5rem;display:flex;align-items:center;gap:1rem">
          <i data-lucide="shield-check" style="color:var(--accent);width:24px;height:24px;flex-shrink:0"></i>
          <p style="margin:0;font-size:0.85rem;color:var(--text-muted);line-height:1.4">
            <b style="color:var(--text)">Secure Payment Gateway:</b> Integrated with Razorpay & Stripe with HMAC-SHA256 signature verification. In Sandbox / Test Mode, payment execution is fully simulated end-to-end with cryptographic receipt generation.
          </p>
        </div>

        <!-- Pricing Cards Grid -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(310px, 1fr));gap:1.5rem">
          <!-- Free Plan -->
          <div class="glass-card" style="border:1px solid var(--border);border-radius:20px;padding:2rem;display:flex;flex-direction:column;justify-content:space-between;background:var(--surface)">
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                <h3 style="margin:0;font-size:1.25rem;font-weight:700">PocketPay Basic</h3>
                <span class="chip" style="font-size:0.75rem">Free Tier</span>
              </div>
              <div style="margin-bottom:1.5rem">
                <span style="font-size:2.25rem;font-weight:800;color:var(--text)">₹0</span>
                <span style="color:var(--text-dim);font-size:0.9rem"> / forever</span>
              </div>
              <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">Essential budgeting and basic money movements for personal expense tracking.</p>

              <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:0.75rem;font-size:0.85rem">
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check" style="color:var(--success);width:16px"></i> Up to 5 Smart Pockets</li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check" style="color:var(--success);width:16px"></i> Standard P2P Transfers & Universal QR</li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check" style="color:var(--success);width:16px"></i> 4-Digit PIN Security</li>
                <li style="display:flex;align-items:center;gap:0.5rem;color:var(--text-dim)"><i data-lucide="x" style="color:var(--text-dim);width:16px"></i> Deep Financial Insights AI</li>
                <li style="display:flex;align-items:center;gap:0.5rem;color:var(--text-dim)"><i data-lucide="x" style="color:var(--text-dim);width:16px"></i> 30-Day Spending Run-Rate Forecast</li>
                <li style="display:flex;align-items:center;gap:0.5rem;color:var(--text-dim)"><i data-lucide="x" style="color:var(--text-dim);width:16px"></i> Monthly PocketPay Wrapped & Health Score</li>
                <li style="display:flex;align-items:center;gap:0.5rem;color:var(--text-dim)"><i data-lucide="x" style="color:var(--text-dim);width:16px"></i> Smart Automation Rules</li>
              </ul>
            </div>

            <button class="btn btn-ghost" style="width:100%;margin-top:2rem" disabled>
              ${!isPrem ? 'Current Plan' : 'Standard Tier'}
            </button>
          </div>

          <!-- Monthly Plan -->
          <div class="glass-card" style="border:1px solid rgba(99,102,241,0.4);border-radius:20px;padding:2rem;display:flex;flex-direction:column;justify-content:space-between;background:var(--surface);position:relative">
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                <h3 style="margin:0;font-size:1.25rem;font-weight:700;color:var(--accent)">Pro Monthly</h3>
                <span class="chip" style="font-size:0.75rem;background:rgba(99,102,241,0.15);color:var(--accent)">Flexible</span>
              </div>
              <div style="margin-bottom:1.5rem">
                <span style="font-size:2.25rem;font-weight:800;color:var(--text)">₹99</span>
                <span style="color:var(--text-dim);font-size:0.9rem"> / month</span>
              </div>
              <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">Monthly financial intelligence, spending forecasting, and unlimited targets.</p>

              <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:0.75rem;font-size:0.85rem">
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Unlimited Smart Pockets & Goals</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Financial Insights AI</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>30-Day Spending Forecast</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Recurring Subscription Detector</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Automated Smart Pocket Rules</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Financial Health Score (0-100)</b></li>
              </ul>
            </div>

            <button class="btn btn-outline" id="subscribeMonthlyBtn" style="width:100%;margin-top:2rem;border-color:var(--accent);color:var(--accent)" ${isPrem ? 'disabled' : ''}>
              ${isPrem ? 'Active' : '<i data-lucide="sparkles"></i> Upgrade Monthly (₹99)'}
            </button>
          </div>

          <!-- Yearly Plan (Recommended) -->
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
              <p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:1.5rem">Full 365-day access to all premium features, priority support, and custom export.</p>

              <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:0.75rem;font-size:0.85rem">
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>All Monthly Features Included</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Annual PocketPay Wrapped Retrospective</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>CSV/PDF Full Ledger Export</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>VIP Customer Support Routing</b></li>
                <li style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="check-circle" style="color:var(--accent);width:16px"></i> <b>Early Access to New FinTech Features</b></li>
              </ul>
            </div>

            <button class="btn btn-primary" id="subscribeYearlyBtn" style="width:100%;margin-top:2rem;font-weight:700" ${isPrem ? 'disabled' : ''}>
              ${isPrem ? '<i data-lucide="check"></i> Premium Active' : '<i data-lucide="crown"></i> Upgrade Annual (₹799)'}
            </button>
          </div>
        </div>
      </div>
    `;

    PP.refreshIcons();

    // Bind Subscribe Buttons
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
        if (!confirm('Are you sure you want to cancel your PocketPay Premium subscription? Your pro features will expire at the end of your billing cycle.')) return;
        try {
          cancelBtn.disabled = true;
          await PP.API.post('/premium/cancel', {});
          PP.UI.toast('Subscription Cancelled', 'Your subscription will not renew.', 'info');
          await PP.loadState?.();
          PP.Premium.render(container);
        } catch (e) {
          PP.UI.toast('Cancellation Failed', e.message || 'Error cancelling subscription', 'error');
          cancelBtn.disabled = false;
        }
      };
    }
  },

  async startCheckout(plan, amount, container) {
    try {
      PP.UI.toast('Initiating Checkout', `Setting up ${plan.toUpperCase()} subscription order...`, 'info');
      
      // Step 1: Create Order
      const orderData = await PP.API.post('/premium/create-checkout-order', {
        plan: plan,
        gateway: 'razorpay'
      });

      if (orderData.sandbox) {
        // Developer sandbox mode modal
        PP.Premium.showSandboxCheckout(orderData, plan, amount, container);
      } else if (window.Razorpay) {
        // Live Razorpay Checkout
        const rzpOptions = {
          key: orderData.key_id,
          amount: orderData.amount,
          currency: orderData.currency,
          name: 'PocketPay Premium',
          description: `${plan.toUpperCase()} Subscription`,
          order_id: orderData.order_id,
          prefill: {
            name: PP.state.user?.name || '',
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
              PP.UI.toast('Checkout Dismissed', 'Payment was cancelled.', 'warning');
            }
          }
        };
        const rzp = new window.Razorpay(rzpOptions);
        rzp.open();
      } else {
        // Fallback test sandbox
        PP.Premium.showSandboxCheckout(orderData, plan, amount, container);
      }
    } catch (err) {
      PP.UI.toast('Order Creation Failed', err.message || 'Could not start checkout', 'error');
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
              <p style="margin:0;font-size:0.75rem;color:var(--text-muted)">Razorpay Sandbox Mode</p>
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
          <b>Test Mode:</b> Simulating secure payment gateway flow. No real charges. This will issue a cryptographically signed HMAC payment response and verify it with the server.
        </p>

        <div style="display:flex;flex-direction:column;gap:0.75rem">
          <button id="rzpSimulateSuccess" class="btn btn-primary" style="width:100%;font-weight:700">
            <i data-lucide="check-circle"></i> Complete Test Payment (₹${amount})
          </button>
          <button id="rzpSimulateFailure" class="btn btn-outline" style="width:100%;border-color:var(--danger);color:var(--danger)">
            <i data-lucide="x-circle"></i> Simulate Payment Failure
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    PP.refreshIcons();

    modal.querySelector('#closeRzpModal').onclick = () => modal.remove();

    modal.querySelector('#rzpSimulateFailure').onclick = () => {
      modal.remove();
      PP.UI.toast('Payment Failed', 'The simulated payment was cancelled or declined. Free tier maintained.', 'error');
    };

    modal.querySelector('#rzpSimulateSuccess').onclick = async () => {
      const btn = modal.querySelector('#rzpSimulateSuccess');
      btn.disabled = true;
      btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Verifying HMAC Signature...';
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
        PP.UI.toast('Verification Failed', err.message || 'HMAC Signature Mismatch', 'error');
      }
    };
  },

  async completeVerification(verifyPayload, plan, container) {
    PP.UI.toast('Verifying Payment', 'Validating server signature and activating subscription...', 'info');

    const result = await PP.API.post('/premium/verify-payment', verifyPayload);

    if (result.success) {
      await PP.loadState?.();

      // Show Requirement Welcome Banner
      const sub = result.subscription || {};
      const expDate = sub.expiry_date ? new Date(sub.expiry_date).toLocaleDateString() : 'N/A';

      PP.UI.showSuccess({
        title: '🎉 Welcome to PocketPay Premium!',
        sub: 'Your Premium plan is now active.',
        meta: [
          { label: 'Plan', value: (sub.plan || plan).toUpperCase() },
          { label: 'Valid until', value: expDate },
          { label: 'Transaction Reference', value: sub.payment_id || verifyPayload.payment_id || 'CONFIRMED' }
        ]
      });

      PP.Premium.render(container);
    } else {
      PP.UI.toast('Verification Error', result.error || 'Could not verify payment', 'error');
    }
  }
};

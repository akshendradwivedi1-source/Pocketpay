// ========== Wallet / Profile View ==========
PP.Wallet = {
  async render(container) {
    container.innerHTML = '';
    const wrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.5rem' });
    container.appendChild(wrap);

    wrap.appendChild(PP.el('div', { class: 'page-header' }, [
      PP.el('div', {}, [
        PP.el('p', { class: 'page-eyebrow' }, ['Account']),
        PP.el('h2', { class: 'page-title' }, ['My Wallet']),
        PP.el('p', { class: 'page-sub' }, ['Virtual wallet ID, UPI, and account security.']),
      ]),
      PP.el('div', { class: 'page-actions' }, [
        PP.el('button', { class: 'btn btn-outline', onclick: () => PP.Modals.scanAndPay() }, [PP.el('i', { 'data-lucide': 'qr-code' }), 'Scan & Pay']),
        PP.el('button', { class: 'btn btn-primary', onclick: () => PP.Modals.transferToBank() }, [PP.el('i', { 'data-lucide': 'landmark' }), 'Transfer to Bank']),
      ]),
    ]));

    const twoCol = PP.el('div', { class: 'two-col-grid' });
    wrap.appendChild(twoCol);

    // Wallet card
    const leftCol = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.5rem' });
    const rightCol = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.5rem' });
    twoCol.append(leftCol, rightCol);

    try {
      const user = PP.state.user;
      const bal = await PP.WalletAPI.balance();
      const b = bal?.data || {};

      // Wallet card
      const wCard = PP.el('div', { class: 'wallet-card' });
      wCard.innerHTML = `
        <div class="wc-top">
          <div class="wc-brand">
            <div class="wc-logo"><i data-lucide="wallet"></i></div>
            <div>
              <div class="wc-name">PocketPay</div>
              <div class="wc-sub">${user.email_verified ? 'Verified' : 'Unverified'} Account</div>
            </div>
          </div>
          <div class="wc-chips"></div>
          <div class="wc-virtual"><span>VIRTUAL</span></div>
        </div>
        <div class="wc-middle">
          <div class="wc-number">${user.virtual_wallet_id || '— — — —'}</div>
          <div class="wc-number-fade">••••  ••••  ••••  ${(user.virtual_wallet_id || '0000').slice(-4)}</div>
          <div class="wc-chip"></div>
          <div class="wc-wave"></div>
        </div>
        <div class="wc-bottom">
          <div>
            <div class="wc-label">HOLDER</div>
            <div class="wc-value">${(user.full_name || 'YOU').toUpperCase()}</div>
          </div>
          <div>
            <div class="wc-label">UPI ID</div>
            <div class="wc-value">${user.virtual_upi_id || 'you@pocketpay'}</div>
          </div>
          <div>
            <div class="wc-label">BALANCE</div>
            <div class="wc-value">${PP.fmt(b.wallet_balance || 0)}</div>
          </div>
        </div>`;
      leftCol.appendChild(wCard);

      // Quick stats
      const statsCard = PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [PP.el('h3', {}, ['Overview'])]),
      ]);
      const statsGrid = PP.el('div', { class: 'two-col-grid', style: 'gap:.75rem' });
      [
        ['Pocket Balance', b.pocket_balance || 0, 'piggy-bank'],
        ['Wallet Balance', b.wallet_balance || 0, 'wallet'],
        ['Monthly Income', b.monthly_income || 0, 'trending-up'],
        ['Monthly Expense', b.monthly_expense || 0, 'trending-down'],
      ].forEach(s => {
        statsGrid.appendChild(PP.el('div', { class: 'glass-card', style: 'padding:1rem' }, [
          PP.el('div', { class: 'stat-label' }, [s[0]]),
          PP.el('div', { class: 'stat-value', style: 'margin:.25rem 0 .25rem' }, [PP.fmt(s[1])]),
          PP.el('i', { 'data-lucide': s[2], class: 'text-muted', style: 'width:14px;height:14px' }),
        ]));
      });
      statsCard.appendChild(statsGrid);
      leftCol.appendChild(statsCard);

      // Virtual IDs
      const idsCard = PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [PP.el('h3', {}, ['Virtual Identifiers'])]),
      ]);
      idsCard.appendChild(PP.el('div', { style: 'display:flex;flex-direction:column;gap:.75rem' }, [
        PP.Wallet.idRow('Wallet ID', user.virtual_wallet_id, 'credit-card'),
        PP.Wallet.idRow('UPI ID', user.virtual_upi_id, 'scan-line'),
        PP.Wallet.idRow('Email', user.email, 'mail', user.email_verified),
        PP.Wallet.idRow('Phone', user.phone || '—', 'smartphone', user.phone_verified),
      ]));
      leftCol.appendChild(idsCard);

      // QR
      const qrCard = PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [PP.el('h3', {}, ['Wallet QR']), PP.el('span', { class: 'chip success' }, ['Receive'])]),
      ]);
      const qrWrap = PP.el('div', { style: 'text-align:center;padding:1rem;background:linear-gradient(135deg,var(--surface),var(--surface));border-radius:var(--radius-lg);border:1px dashed var(--border)' });
      qrCard.appendChild(qrWrap);
      PP.Auth.walletQr().then(res => {
        if (res?.data?.qr_code_url) {
          qrWrap.innerHTML = `
            <img src="${res.data.qr_code_url}" alt="Wallet QR" style="width:200px;height:200px;border-radius:var(--radius-md);padding:6px;background:white"/>
            <p style="margin:1rem 0 .5rem;font-weight:700;font-size:1.05rem">${user.full_name || 'You'}</p>
            <p style="font-size:.8rem;color:var(--text-muted)">${user.virtual_upi_id || ''}</p>
            <div style="margin-top:1rem;display:flex;gap:.5rem;justify-content:center">
              <button class="btn btn-outline btn-sm" onclick="navigator.clipboard.writeText('${user.virtual_upi_id || ''}');PP.UI.toast('Copied','UPI ID copied to clipboard','success')"><i data-lucide="copy"></i> Copy UPI</button>
              <button class="btn btn-outline btn-sm" onclick="(() => {
                const link = document.createElement('a');
                link.href = '${res.data.qr_code_url}';
                link.download = 'pocketpay_qr_${user.virtual_upi_id || 'wallet'}.png';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                PP.UI.toast('QR Saved', 'Wallet QR image downloaded', 'success');
              })()"><i data-lucide="download"></i> Save QR</button>
            </div>`;
          PP.refreshIcons();
        }
      }).catch(() => qrWrap.innerHTML = '<p>Loading QR…</p>');
      rightCol.appendChild(qrCard);

      // Connected Banks
      const banksCard = PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [
          PP.el('h3', {}, [PP.el('i', { 'data-lucide': 'landmark', style: 'display:inline;margin-right:0.5rem;color:var(--accent)' }), 'Connected Bank Accounts']),
          PP.el('button', { class: 'link-btn', onclick: () => PP.Modals.linkBankAccount() }, ['+ Add Bank'])
        ]),
      ]);
      const banksList = user.linked_banks || [];
      if (!banksList.length) {
        banksCard.appendChild(PP.el('div', { class: 'empty-state', style: 'padding:1.5rem 1rem' }, [
          PP.el('div', { class: 'empty-icon' }, [PP.el('i', { 'data-lucide': 'landmark' })]),
          PP.el('h4', { style: 'margin:0.5rem 0 0.25rem' }, ['No bank connected']),
          PP.el('p', { class: 'text-sm text-muted' }, ['Connect a Sandbox Bank account to simulate balance sync.']),
          PP.el('button', { class: 'btn btn-primary btn-sm', style: 'margin-top:0.75rem', onclick: () => PP.Modals.linkBankAccount() }, ['Connect Demo Bank']),
        ]));
      } else {
        const bl = PP.el('div', { style: 'display:flex;flex-direction:column;gap:0.75rem' });
        banksList.forEach(bk => {
          const bRow = PP.el('div', { class: 'glass-card', style: 'padding:1rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap' }, [
            PP.el('div', { style: 'display:flex;align-items:center;gap:0.75rem' }, [
              PP.el('div', { style: 'width:38px;height:38px;border-radius:10px;background:rgba(16,185,129,0.12);color:#10b981;display:flex;align-items:center;justify-content:center' }, [
                PP.el('i', { 'data-lucide': 'landmark', style: 'width:18px;height:18px' })
              ]),
              PP.el('div', {}, [
                PP.el('div', { style: 'font-weight:700;font-size:0.95rem' }, [
                  bk.bank_name || 'Bank Account',
                  PP.el('span', { class: 'chip success', style: 'margin-left:6px;font-size:0.65rem' }, ['Sandbox'])
                ]),
                PP.el('div', { style: 'font-size:0.8rem;color:var(--text-muted)' }, [
                  `${bk.account_type || 'Savings'} &bull; ${bk.account_mask || '•••• 4821'} &bull; ${PP.fmt(bk.balance || 25000)}`
                ]),
              ])
            ]),
            PP.el('div', { style: 'display:flex;gap:0.5rem' }, [
              PP.el('button', {
                class: 'btn btn-sm btn-ghost',
                onclick: async () => {
                  try {
                    await PP.Auth.syncBankBalance();
                    PP.UI.toast('Synced', 'Bank balance synchronized', 'success');
                    PP.refreshCurrentView();
                  } catch (e) { PP.UI.toast('Sync failed', e.message, 'error'); }
                }
              }, [PP.el('i', { 'data-lucide': 'refresh-cw' }), 'Sync']),
              PP.el('button', {
                class: 'btn btn-sm btn-ghost',
                style: 'color:var(--danger)',
                onclick: async () => {
                  const ok = await PP.UI.confirm('Disconnect Bank Account?', `Are you sure you want to disconnect ${bk.bank_name}?`);
                  if (!ok) return;
                  try {
                    await PP.Auth.unlinkBankAccount(bk.id);
                    PP.UI.toast('Disconnected', 'Bank account unlinked', 'info');
                    if (PP.state.user) PP.state.user.linked_banks = (PP.state.user.linked_banks || []).filter(b => b.id !== bk.id);
                    PP.refreshCurrentView();
                  } catch (e) { PP.UI.toast('Error', e.message, 'error'); }
                }
              }, [PP.el('i', { 'data-lucide': 'trash-2' })]),
            ])
          ]);
          bl.appendChild(bRow);
        });
        banksCard.appendChild(bl);
      }
      leftCol.appendChild(banksCard);

      // Peer-to-Peer Payments & Transfers Card
      const p2pCard = PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [
          PP.el('h3', {}, ['Peer Payments & Transfers']),
          PP.el('span', { class: 'chip accent' }, ['P2P Instant'])
        ]),
        PP.el('p', { class: 'text-sm text-muted', style: 'margin-bottom:1rem' }, [
          'Send or request money with zero fees across all PocketPay accounts.'
        ]),
        PP.el('div', { style: 'display:grid;grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));gap:0.6rem;margin-bottom:0.75rem' }, [
          PP.el('button', {
            class: 'btn btn-primary btn-sm',
            style: 'display:flex;align-items:center;justify-content:center;gap:0.4rem;font-weight:600',
            onclick: () => PP.Modals.sendMoney()
          }, [PP.el('i', { 'data-lucide': 'send' }), 'Send Money']),
          PP.el('button', {
            class: 'btn btn-outline btn-sm',
            style: 'display:flex;align-items:center;justify-content:center;gap:0.4rem;font-weight:600',
            onclick: () => PP.Modals.requestMoney()
          }, [PP.el('i', { 'data-lucide': 'hand-coins' }), 'Request Money']),
          PP.el('button', {
            class: 'btn btn-outline btn-sm',
            style: 'display:flex;align-items:center;justify-content:center;gap:0.4rem;font-weight:600',
            onclick: () => PP.Modals.moneyRequests()
          }, [PP.el('i', { 'data-lucide': 'inbox' }), 'Requests List']),
          PP.el('button', {
            class: 'btn btn-outline btn-sm',
            style: 'display:flex;align-items:center;justify-content:center;gap:0.4rem;font-weight:600',
            onclick: () => PP.Modals.transferToBank()
          }, [PP.el('i', { 'data-lucide': 'landmark' }), 'Bank Payout']),
        ])
      ]);
      rightCol.appendChild(p2pCard);

      // Security & Danger Zone
      const hasPin = Boolean(user.has_transaction_pin || user.has_pin || user.transaction_pin_hash);
      const secCard = PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [
          PP.el('h3', {}, ['Security & Settings']),
          PP.el('span', { class: 'chip ' + (hasPin ? 'success' : 'warning') }, [hasPin ? 'PIN SET' : 'NO PIN'])
        ]),
      ]);
      secCard.appendChild(PP.el('div', { style: 'display:flex;flex-direction:column;gap:.6rem' }, [
        PP.Wallet.settingRow('Transaction PIN', hasPin ? 'Enabled (Configured)' : 'Not set', 'lock', () => hasPin ? PP.Modals.changePin() : PP.Modals.setupPin()),
        PP.Wallet.settingRow(
          'Two-Factor Auth (2FA / TOTP)',
          user.totp_enabled ? 'Enabled (Google / Microsoft Authenticator)' : 'Disabled — Tap to Enable Free 2FA',
          'shield-check',
          () => user.totp_enabled ? PP.Modals.disableTOTP() : PP.Modals.setupTOTP()
        ),
        user.totp_enabled ? PP.Wallet.settingRow(
          'Backup Recovery Codes',
          `${user.backup_codes_count || 8} codes remaining — Tap to Regenerate`,
          'key',
          () => PP.Modals.viewBackupCodes()
        ) : null,
        PP.Wallet.settingRow('Email Verification', user.email_verified ? 'Verified' : 'Verify now', 'mail-check', () => !user.email_verified && PP.Modals.verifyEmail()),
        PP.Wallet.settingRow('Change Password', '••••••••', 'key-round', () => PP.Modals.changePassword()),
        PP.Wallet.settingRow('Delete Account', 'Permanently close account (balance must be ₹0)', 'alert-triangle', () => PP.Modals.deleteAccountModal()),
      ].filter(Boolean)));
      rightCol.appendChild(secCard);

      // Notifications
      const notifCard = PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [PP.el('h3', {}, ['Notifications']), PP.el('button', {
          class: 'link-btn', onclick: async () => { try { await PP.AnalyticsAPI.readAll(); PP.UI.toast('Done', 'All marked read', 'success'); PP.Wallet.loadNotifs(); } catch (e) {} }
        }, ['Mark all read'])]),
      ]);
      const nWrap = PP.el('div', { id: 'notifWrap', style: 'max-height:340px;overflow:auto;display:flex;flex-direction:column;gap:.5rem' });
      notifCard.appendChild(nWrap);
      rightCol.appendChild(notifCard);
      PP.Wallet.loadNotifs(nWrap);

      // Theme toggle
      const prefCard = PP.el('div', { class: 'section-card' }, [
        PP.el('div', { class: 'section-title' }, [PP.el('h3', {}, ['Preferences'])]),
        PP.el('div', { style: 'display:flex;gap:.6rem;flex-wrap:wrap' }, [
          PP.el('button', {
            class: 'btn ' + (document.documentElement.dataset.theme !== 'light' ? 'btn-primary' : 'btn-outline'),
            onclick: () => PP.setTheme('dark'),
          }, [PP.el('i', { 'data-lucide': 'moon' }), 'Dark']),
          PP.el('button', {
            class: 'btn ' + (document.documentElement.dataset.theme === 'light' ? 'btn-primary' : 'btn-outline'),
            onclick: () => PP.setTheme('light'),
          }, [PP.el('i', { 'data-lucide': 'sun' }), 'Light']),
          PP.el('button', {
            class: 'btn btn-ghost', onclick: () => PP.logout(),
            style: 'margin-left:auto',
          }, [PP.el('i', { 'data-lucide': 'log-out' }), 'Sign out']),
        ]),
      ]);
      rightCol.appendChild(prefCard);
      PP.refreshIcons();
    } catch (e) { PP.UI.toast('Error', e.message, 'error'); }
  },

  idRow(label, value, icon, verified = false) {
    return PP.el('div', { class: 'glass-card', style: 'padding:1rem;display:flex;align-items:center;gap:1rem' }, [
      PP.el('div', { class: 'pocket-icon-wrap', style: 'background:var(--accent-alpha);color:var(--accent);width:40px;height:40px' }, [PP.el('i', { 'data-lucide': icon })]),
      PP.el('div', { style: 'flex:1;min-width:0' }, [
        PP.el('div', { class: 'text-muted text-sm' }, [label]),
        PP.el('div', { style: 'font-weight:700;word-break:break-all' }, [value || '—']),
      ]),
      PP.el('div', { style: 'display:flex;gap:.4rem' }, [
        verified !== undefined && PP.el('span', { class: 'chip ' + (verified ? 'success' : 'warning') }, [verified ? 'Verified' : 'Pending']),
        PP.el('button', {
          class: 'btn btn-ghost btn-sm', onclick: () => { navigator.clipboard?.writeText(value); PP.UI.toast('Copied', label + ' copied', 'success'); }
        }, [PP.el('i', { 'data-lucide': 'copy' })]),
      ]),
    ]);
  },

  settingRow(label, sub, icon, onClick) {
    return PP.el('button', { class: 'setting-row', onclick: onClick }, [
      PP.el('div', { class: 'setting-icon' }, [PP.el('i', { 'data-lucide': icon })]),
      PP.el('div', { class: 'setting-texts' }, [
        PP.el('div', { class: 'setting-label' }, [label]),
        PP.el('div', { class: 'setting-sub' }, [sub]),
      ]),
      PP.el('i', { 'data-lucide': 'chevron-right', style: 'width:18px;height:18px;color:var(--text-muted)' }),
    ]);
  },

  async loadNotifs(container) {
    const cont = container || PP.$('#notifWrap');
    if (!cont) return;
    cont.innerHTML = '<div class="skeleton" style="height:60px"></div>';
    try {
      const res = await PP.AnalyticsAPI.notifications();
      const items = res?.data?.items || [];
      cont.innerHTML = '';
      if (!items.length) {
        cont.appendChild(PP.el('p', { style: 'padding:1rem;text-align:center;color:var(--text-muted);font-size:.85rem' }, ['All caught up! No new notifications.']));
        return;
      }
      items.forEach(n => {
        const type = n.type || 'info';
        const colors = { success: 'var(--success)', warning: 'var(--warning)', danger: 'var(--danger)', info: 'var(--info)' };
        const icons = { success: 'check-circle', warning: 'alert-triangle', danger: 'octagon-alert', info: 'bell', budget: 'target', transaction: 'receipt', security: 'shield-check' };
        const col = colors[type] || colors.info;
        const ic = icons[type] || icons.info;
        cont.appendChild(PP.el('div', { class: `notif-item ${n.is_read ? 'read' : ''}` }, [
          PP.el('div', { class: 'notif-icon', style: `background:${PP.UI.hexToRgba(col, .14)};color:${col}` }, [PP.el('i', { 'data-lucide': ic })]),
          PP.el('div', { style: 'flex:1' }, [
            PP.el('div', { style: 'font-weight:600;font-size:.9rem' }, [n.title]),
            PP.el('div', { style: 'font-size:.78rem;color:var(--text-muted);line-height:1.45;margin-top:.2rem' }, [n.message]),
            PP.el('div', { style: 'font-size:.7rem;color:var(--text-muted);margin-top:.35rem' }, [PP.formatTimeAgo(n.created_at)]),
          ]),
        ]));
      });
      PP.refreshIcons();
    } catch (e) { console.warn(e); }
  },
};

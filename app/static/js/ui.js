// ========== UI Helpers: Toasts, Modals, PIN, etc ==========
PP.UI = {
  toast(title, message = '', type = 'info', duration = 4200) {
    const root = PP.$('#toastRoot');
    if (!root) return null;
    const id = PP.uid();
    const icons = {
      success: 'check-circle-2',
      error: 'x-circle',
      warning: 'triangle-alert',
      info: 'info',
    };
    const el = PP.el('div', { class: `toast toast-${type}`, id: `toast_${id}` }, [
      PP.el('div', { class: 'toast-icon' }, [PP.el('i', { 'data-lucide': icons[type] || 'info' })]),
      PP.el('div', { class: 'toast-content' }, [
        PP.el('div', { class: 'toast-title' }, [title]),
        message ? PP.el('div', { class: 'toast-msg' }, [message]) : null,
      ]),
      PP.el('button', {
        class: 'toast-close',
        'aria-label': 'Close',
        onclick: () => close(),
      }, [PP.el('i', { 'data-lucide': 'x' })]),
    ]);
    root.appendChild(el);
    PP.refreshIcons();
    const close = () => {
      el.classList.add('leave');
      setTimeout(() => el.remove(), 250);
    };
    const t = setTimeout(close, duration);
    el._close = close;
    return { el, close };
  },

  confirm(title, message, opts = {}) {
    return new Promise(resolve => {
      const modal = this.modal({
        title,
        subtitle: message,
        icon: opts.icon || 'alert-circle',
        iconClass: opts.iconClass || 'bg-danger',
        size: 'sm',
        body: opts.body || null,
        footer: [
          PP.el('button', { class: 'btn btn-ghost', onclick: () => { modal.close(); resolve(false); } }, [opts.cancelLabel || 'Cancel']),
          PP.el('button', {
            class: `btn ${opts.okClass || 'btn-danger'}`,
            onclick: () => { modal.close(); resolve(true); },
          }, [opts.okLabel || 'Confirm']),
        ],
      });
    });
  },

  prompt(title, label, opts = {}) {
    return new Promise(resolve => {
      let input;
      const body = PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, [label]),
        (input = PP.el('input', {
          class: 'form-input',
          type: opts.type || 'text',
          value: opts.default || '',
          placeholder: opts.placeholder || '',
        })),
      ]);
      const modal = this.modal({
        title,
        icon: 'pencil',
        iconClass: 'bg-accent',
        size: 'sm',
        body,
        footer: [
          PP.el('button', { class: 'btn btn-ghost', onclick: () => { modal.close(); resolve(null); } }, ['Cancel']),
          PP.el('button', {
            class: 'btn btn-primary',
            onclick: () => { modal.close(); resolve(input.value); },
          }, ['OK']),
        ],
      });
      setTimeout(() => { input.focus(); input.select(); }, 150);
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') modal.footer.lastChild.click(); });
    });
  },

  modal({ title, subtitle, icon = null, iconClass = '', size = '', body, footer, onClose, closable = true }) {
    const root = PP.$('#modalRoot');
    if (!root) return null;
    root.classList.add('modal-root');
    const backdrop = PP.el('div', { class: 'modal-backdrop' });
    const dialog = PP.el('div', { class: `modal modal-${size}`.trim() });
    const iconColors = {
      'bg-accent': 'background:rgba(99,102,241,.15);color:var(--accent)',
      'bg-success': 'background:rgba(16,185,129,.15);color:var(--success)',
      'bg-danger': 'background:rgba(239,68,68,.15);color:var(--danger)',
      'bg-warning': 'background:rgba(245,158,11,.15);color:var(--warning)',
      'bg-info': 'background:rgba(14,165,233,.15);color:var(--info)',
      'bg-pink': 'background:rgba(236,72,153,.15);color:var(--accent-3)',
    };
    const iconWrap = icon ? PP.el('div', {
      class: 'modal-icon',
      style: iconColors[iconClass] || iconColors['bg-accent'],
    }, [PP.el('i', { 'data-lucide': icon })]) : null;

    const header = PP.el('div', { class: 'modal-header' }, [
      PP.el('div', { class: 'modal-title-wrap' }, [
        iconWrap,
        PP.el('div', {}, [
          title ? PP.el('h3', { class: 'modal-title' }, [title]) : null,
          subtitle ? PP.el('p', { class: 'modal-subtitle' }, [subtitle]) : null,
        ]),
      ]),
      closable ? PP.el('button', {
        class: 'modal-close',
        'aria-label': 'Close',
        onclick: () => close(),
      }, [PP.el('i', { 'data-lucide': 'x' })]) : null,
    ]);
    const bodyEl = PP.el('div', { class: 'modal-body' }, [body || null]);
    const footerEl = PP.el('div', { class: 'modal-footer' }, (footer || []).filter(Boolean));

    dialog.append(header, bodyEl, footerEl);
    root.append(backdrop, dialog);
    PP.refreshIcons();

    const close = () => {
      dialog.style.animation = 'modalOut .22s ease both';
      backdrop.style.animation = 'fadeOut .22s ease both';
      setTimeout(() => {
        dialog.remove(); backdrop.remove();
        root.classList.remove('modal-root');
        onClose && onClose();
      }, 220);
    };
    if (closable) backdrop.addEventListener('click', close);
    document.addEventListener('keydown', esc);
    function esc(e) { if (e.key === 'Escape' && closable) { close(); document.removeEventListener('keydown', esc); } }

    return { close, el: dialog, body: bodyEl, header, footer: footerEl };
  },

  pinPrompt({ title = 'Enter Transaction PIN', subtitle = 'Enter your 4-digit PIN to confirm this action', allowCancel = true } = {}) {
    return new Promise((resolve) => {
      let entered = [];
      const update = () => {
        dots.forEach((d, i) => d.classList.toggle('filled', i < entered.length));
        amountEl && (amountEl.classList.toggle('shaking', entered.length >= 4 && result === false));
      };
      const dots = [];
      let result = null;
      let amountEl = null;

      const display = PP.el('div', { class: 'pin-display' },
        Array.from({ length: 4 }, () => { const d = PP.el('div', { class: 'pin-dot' }); dots.push(d); return d; })
      );
      const pad = PP.el('div', { class: 'pin-pad' });
      [1, 2, 3, 4, 5, 6, 7, 8, 9, null, 0, 'del'].forEach(n => {
        if (n === null) return pad.appendChild(PP.el('div', { style: 'width:1px;height:1px' }));
        const btn = PP.el('button', { class: 'pin-btn' }, [
          n === 'del' ? PP.el('i', { 'data-lucide': 'delete' }) : String(n),
        ]);
        btn.onclick = () => {
          if (n === 'del') { entered.pop(); return update(); }
          if (entered.length >= 4) return;
          entered.push(String(n));
          update();
          if (entered.length === 4) setTimeout(submit, 220);
        };
        pad.appendChild(btn);
      });

      const modal = this.modal({
        title,
        subtitle,
        icon: 'shield-check',
        iconClass: 'bg-accent',
        size: 'sm',
        body: PP.el('div', {}, [display, pad]),
        footer: allowCancel ? [PP.el('button', {
          class: 'btn btn-ghost',
          onclick: () => { modal.close(); resolve(null); }
        }, ['Cancel'])] : [],
      });

      async function submit() {
        try {
          const pinVal = entered.join('');
          const res = await PP.Auth.verifyPin(pinVal);
          if (res?.success) {
            result = true;
            modal.close();

            // If user has 2FA TOTP enabled, prompt for 6-digit authenticator code
            if (PP.state.user?.totp_enabled) {
              const totpCode = await PP.UI.totpPrompt({
                title: 'Two-Factor Authentication',
                subtitle: 'Enter the 6-digit code from your Authenticator app'
              });
              if (!totpCode) return resolve(null);
              
              const authResult = {
                pin: pinVal,
                totp_code: totpCode,
                toString() { return pinVal; }
              };
              return resolve(authResult);
            }

            const authResult = {
              pin: pinVal,
              totp_code: null,
              toString() { return pinVal; }
            };
            resolve(authResult);
          } else {
            result = false;
            entered = [];
            setTimeout(update, 200);
            PP.UI.toast('Incorrect PIN', res?.message || 'Please try again', 'error');
          }
        } catch (e) {
          result = false;
          entered = [];
          setTimeout(update, 200);
          if (e.status === 400 && e.data?.code === 'PIN_NOT_SET') {
            modal.close();
            const go = await PP.UI.confirm('PIN Not Set', 'You need to set a transaction PIN first. Open settings now?', { okClass: 'btn-primary', okLabel: 'Set PIN Now' });
            if (go) PP.Modals.setupPin();
            resolve(null);
          } else {
            PP.UI.toast('Incorrect PIN', e.message || '', 'error');
          }
        }
      }
      PP.refreshIcons();
    });
  },

  totpPrompt({ title = 'Two-Factor Authentication', subtitle = 'Enter the 6-digit code from your Authenticator app', allowCancel = true } = {}) {
    return new Promise((resolve) => {
      let isBackupMode = false;
      const modal = this.modal({
        title,
        subtitle,
        icon: 'key-round',
        iconClass: 'bg-accent',
        size: 'sm'
      });

      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.25rem' });
      
      const inputWrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.5rem' });
      const input = PP.el('input', {
        type: 'text',
        class: 'form-input',
        placeholder: '000000',
        maxlength: '6',
        autocomplete: 'one-time-code',
        inputmode: 'numeric',
        style: 'text-align:center;font-family:var(--font-mono);font-size:1.5rem;letter-spacing:.3em;font-weight:700'
      });
      inputWrap.appendChild(input);

      const toggleBackupBtn = PP.el('button', {
        type: 'button',
        class: 'btn btn-sm btn-ghost',
        style: 'align-self:center;font-size:.78rem;color:var(--text-muted)'
      }, ['Use a backup recovery code instead']);

      toggleBackupBtn.onclick = () => {
        isBackupMode = !isBackupMode;
        if (isBackupMode) {
          input.placeholder = 'XXXX-XXXX';
          input.removeAttribute('maxlength');
          input.setAttribute('maxlength', '12');
          input.style.fontSize = '1.15rem';
          input.style.letterSpacing = '.15em';
          toggleBackupBtn.textContent = 'Use 6-digit Authenticator app code';
        } else {
          input.placeholder = '000000';
          input.setAttribute('maxlength', '6');
          input.style.fontSize = '1.5rem';
          input.style.letterSpacing = '.3em';
          toggleBackupBtn.textContent = 'Use a backup recovery code instead';
        }
        input.value = '';
        input.focus();
      };

      body.append(inputWrap, toggleBackupBtn);
      modal.body.innerHTML = '';
      modal.body.appendChild(body);

      modal.footer.innerHTML = '';
      if (allowCancel) {
        modal.footer.appendChild(PP.el('button', {
          class: 'btn btn-ghost',
          onclick: () => { modal.close(); resolve(null); }
        }, ['Cancel']));
      }

      const confirmBtn = PP.el('button', {
        class: 'btn btn-primary',
        onclick: () => {
          const val = input.value.trim();
          if (!val) {
            return PP.UI.toast('Code Required', isBackupMode ? 'Enter recovery code' : 'Enter 6-digit code', 'warning');
          }
          modal.close();
          resolve(val);
        }
      }, ['Authorize']);
      modal.footer.appendChild(confirmBtn);

      input.onkeydown = (e) => {
        if (e.key === 'Enter') confirmBtn.click();
      };

      setTimeout(() => input.focus(), 150);
      PP.refreshIcons();
    });
  },

  showSuccess({ title = 'Success', subtitle = '', meta = {}, qrCode = null, qr_code_url = null, autoClose = 3200, onClick = null }) {
    const overlay = PP.$('#successOverlay');
    PP.$('#successTitle', overlay).textContent = title;
    PP.$('#successSub', overlay).textContent = subtitle;
    const metaEl = PP.$('#successMeta', overlay);
    metaEl.innerHTML = '';
    
    const qrUrl = qr_code_url || qrCode;
    if (qrUrl) {
      const qrWrap = PP.el('div', {
        style: 'display:flex;flex-direction:column;align-items:center;margin:0.75rem auto 1rem;padding:0.75rem;background:#ffffff;border-radius:14px;box-shadow:0 8px 24px rgba(0,0,0,0.35);max-width:180px'
      }, [
        PP.el('img', {
          src: qrUrl,
          alt: 'Transfer Receipt QR',
          style: 'width:140px;height:140px;display:block;border-radius:8px'
        }),
        PP.el('div', {
          style: 'font-size:0.7rem;font-weight:700;color:#0a0b14;margin-top:4px;text-align:center;letter-spacing:0.02em'
        }, ['Transfer Receipt QR'])
      ]);
      metaEl.appendChild(qrWrap);
    }
    
    Object.entries(meta).forEach(([k, v]) => metaEl.appendChild(PP.el('div', { class: 'success-meta-row' }, [
      PP.el('div', {}, [k]), PP.el('div', {}, [v]),
    ])));
    overlay.classList.remove('hidden');
    const close = () => {
      overlay.classList.add('hidden');
      onClick && onClick();
    };
    overlay.addEventListener('click', close, { once: true });
    if (autoClose) setTimeout(close, autoClose);
  },

  hexToRgba(hex, alpha = 1) {
    if (!hex || typeof hex !== 'string') return `rgba(99, 102, 241, ${alpha})`;
    if (hex.startsWith('var(') || hex.startsWith('rgb')) {
      return `color-mix(in srgb, ${hex} ${Math.round(alpha * 100)}%, transparent)`;
    }
    const h = hex.replace('#', '').trim();
    if (!/^[0-9a-fA-F]{3,8}$/.test(h)) {
      return hex;
    }
    const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h.slice(0, 6);
    const num = parseInt(full, 16);
    const r = (num >> 16) & 255, g = (num >> 8) & 255, b = num & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  },

  pocketStyleVars(pocket) {
    const c = pocket.color || '#6366f1';
    return {
      '--pc-color': c,
      '--pc-color-shadow': PP.UI.hexToRgba(c, .35),
      '--pc-color-alpha-1': PP.UI.hexToRgba(c, .20),
      '--pc-color-alpha-2': PP.UI.hexToRgba(c, .07),
    };
  },
};

PP.Skeletons = {
  card(lines = 3) {
    return PP.el('div', { class: 'glass-card pad-lg' },
      Array.from({ length: lines }).map((_, i) =>
        PP.el('div', { class: 'skeleton', style: { height: i === 0 ? '28px' : '14px', width: `${70 - i * 18}%`, marginTop: i ? '10px' : 0 } })
      )
    );
  },
};

PP.Charts = {
  donut(container, segments, centerLabel = 'Total', centerSub = '') {
    container.innerHTML = '';
    const size = 200;
    const radius = 88;
    const stroke = 22;
    const circumference = 2 * Math.PI * radius;
    const total = segments.reduce((s, v) => s + (v.value || 0), 0) || 1;

    let offset = 0;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${size} ${size}`);
    svg.innerHTML = `<defs><linearGradient id="donutGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#6366f1"/><stop offset="100%" stop-color="#ec4899"/></linearGradient></defs>`;

    const track = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    track.setAttribute('cx', size / 2); track.setAttribute('cy', size / 2);
    track.setAttribute('r', radius); track.setAttribute('class', 'donut-track');
    svg.appendChild(track);

    segments.forEach((seg) => {
      const pct = (seg.value || 0) / total;
      const dash = pct * circumference;
      if (dash <= 0) return;
      const el = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      el.setAttribute('cx', size / 2); el.setAttribute('cy', size / 2); el.setAttribute('r', radius);
      el.setAttribute('class', 'donut-segment');
      el.setAttribute('stroke', seg.color || '#6366f1');
      el.setAttribute('stroke-dasharray', `${dash} ${circumference - dash}`);
      el.setAttribute('stroke-dashoffset', -offset);
      el.addEventListener('mouseenter', () => {
        PP.UI.toast(seg.label || '', `${PP.fmt(seg.value)} (${(pct*100).toFixed(1)}%)`, 'info', 1500);
      });
      svg.appendChild(el);
      offset += dash;
    });

    const chartWrap = PP.el('div', { class: 'donut-chart' }, [
      svg,
      PP.el('div', { class: 'donut-center' }, [
        PP.el('div', { class: 'donut-center-label' }, [centerLabel]),
        PP.el('div', { class: 'donut-center-value' }, [PP.fmt(total)]),
        centerSub ? PP.el('div', { class: 'donut-center-sub' }, [centerSub]) : null,
      ]),
    ]);
    container.appendChild(chartWrap);
  },

  bars(container, data, opts = {}) {
    container.innerHTML = '';
    const max = Math.max(...data.map(d => d.value), 1);
    const wrap = PP.el('div', { class: 'bar-chart' });
    data.forEach((d, i) => {
      const h = Math.max(4, (d.value / max) * 100);
      const col = PP.el('div', { class: 'bar-col', style: { animationDelay: `${i * 30}ms` } });
      col.appendChild(PP.el('div', { class: 'bar-tooltip' }, [PP.fmt(d.value)]));
      const bar = PP.el('div', { class: 'bar', style: { height: `${h}%`, background: d.color || 'var(--accent-gradient)' } });
      col.appendChild(bar);
      col.appendChild(PP.el('div', { class: 'bar-label' }, [d.label || '']));
      wrap.appendChild(col);
    });
    container.appendChild(wrap);
  },

  breakdown(container, rows, opts = {}) {
    container.innerHTML = '';
    const max = Math.max(...rows.map(r => r.value || 0), 1);
    const wrap = PP.el('div', { class: 'breakdown-list' });
    rows.forEach((r, i) => {
      const pct = ((r.value || 0) / max) * 100;
      const row = PP.el('div', { class: 'breakdown-row', style: { animationDelay: `${i * 40}ms` } });
      const left = PP.el('div', { class: 'breakdown-row-left' });
      if (r.icon) {
        const iconWrap = PP.el('div', { class: 'breakdown-icon', style: r.iconColor ? `background:${PP.UI.hexToRgba(r.iconColor,.12)};color:${r.iconColor}` : {} },
          [PP.el('i', { 'data-lucide': r.icon })]);
        left.appendChild(iconWrap);
      }
      left.appendChild(PP.el('div', { class: 'breakdown-name' }, [r.label]));
      const barWrap = PP.el('div', { class: 'breakdown-bar-wrap' });
      barWrap.appendChild(PP.el('div', { class: 'breakdown-bar-fill', style: { width: `${pct}%`, background: r.color || 'var(--accent-gradient)' } }));
      const right = PP.el('div', {}, [
        PP.el('div', { class: 'breakdown-value' }, [PP.fmt(r.value)]),
        PP.el('div', { class: 'breakdown-pct' }, [opts.showPct ? `${r.pct || ((r.value / (rows.reduce((s, x) => s + x.value, 0)) * 100).toFixed(1))}%` : '']),
      ]);
      row.append(left, barWrap, right);
      wrap.appendChild(row);
    });
    container.appendChild(wrap);
    PP.refreshIcons();
  },

  area(container, points, opts = {}) {
    container.innerHTML = '';
    const w = 600, h = 200, pad = 28;
    const max = Math.max(...points.map(p => p.value), 1);
    const min = Math.min(0, ...points.map(p => p.value));
    const range = Math.max(max - min, 1);
    const xs = (i) => pad + (i * (w - 2 * pad) / Math.max(points.length - 1, 1));
    const ys = (v) => h - pad - ((v - min) / range) * (h - 2 * pad);
    const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xs(i)} ${ys(p.value)}`).join(' ');
    const areaD = `${pathD} L ${xs(points.length - 1)} ${h - pad} L ${xs(0)} ${h - pad} Z`;
    const wrap = PP.el('div', { class: 'area-chart' });
    const svgNs = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNs, 'svg');
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svg.innerHTML = `<defs>
      <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#6366f1" stop-opacity=".4"/>
        <stop offset="100%" stop-color="#6366f1" stop-opacity="0"/>
      </linearGradient>
    </defs>`;
    const area = document.createElementNS(svgNs, 'path');
    area.setAttribute('d', areaD); area.setAttribute('class', 'area-path'); svg.appendChild(area);
    const line = document.createElementNS(svgNs, 'path');
    line.setAttribute('d', pathD); line.setAttribute('class', 'line-path'); svg.appendChild(line);
    points.forEach((p, i) => {
      const c = document.createElementNS(svgNs, 'circle');
      c.setAttribute('cx', xs(i)); c.setAttribute('cy', ys(p.value)); c.setAttribute('r', 3.5);
      c.setAttribute('class', 'area-dot');
      const tip = document.createElementNS(svgNs, 'title');
      tip.textContent = `${p.label}: ${PP.fmt(p.value)}`;
      c.appendChild(tip);
      svg.appendChild(c);
    });
    wrap.appendChild(svg);
    container.appendChild(wrap);
  },
};

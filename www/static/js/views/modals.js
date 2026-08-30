PP.Modals = {
  async createPocket(existing = null, opts = {}) {
    const editing = !!existing;
    const colors = PP.state.colors?.length ? PP.state.colors : (await PP.MiscAPI.colors().then(r => r.data.colors).catch(() => []) || []);
    const icons = PP.state.icons?.length ? PP.state.icons : (await PP.MiscAPI.icons().then(r => r.data.icons).catch(() => []) || []);
    PP.state.colors = colors; PP.state.icons = icons;

    let selectedColor = editing ? existing.color : colors[0]?.value || '#6366f1';
    let selectedIcon = editing ? existing.icon : icons[0]?.name || 'wallet';
    let budgetAmount = editing ? existing.budget_amount || 0 : 0;
    let monthlyLimit = editing ? existing.monthly_limit || 0 : 0;
    let priority = editing ? existing.priority || 0 : 0;
    let initialBalance = 0;
    let descriptionVal = editing ? (existing.description || '') : '';
    let nameVal = editing ? existing.name : '';

    const modal = PP.UI.modal({
      title: editing ? 'Edit Pocket' : 'Create New Pocket',
      subtitle: editing ? 'Update your pocket details' : 'Organize your money with custom pockets',
      icon: editing ? 'pencil' : 'folder-plus',
      iconClass: editing ? 'bg-accent' : 'bg-success',
      size: 'lg'
    });

    const renderBody = () => {
      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.25rem' });
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Pocket Name *']),
        (() => {
          const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. Food, Savings, Europe Trip', maxlength: 100, value: nameVal });
          inp.oninput = () => nameVal = inp.value;
          return inp;
        })(),
      ]));
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Description (optional)']),
        (() => {
          const t = PP.el('textarea', { class: 'form-textarea', placeholder: 'What is this pocket for?', rows: 2 });
          t.value = descriptionVal;
          t.oninput = () => descriptionVal = t.value;
          return t;
        })(),
      ]));
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Color']),
        (() => {
          const g = PP.el('div', { class: 'color-grid' });
          colors.forEach(c => {
            const sw = PP.el('div', {
            class: 'color-swatch' + (selectedColor === c.value ? ' selected' : ''),
            style: `background:linear-gradient(135deg,${c.gradient?.[0] || c.value},${c.gradient?.[1] || c.value})`
          });
          sw.onclick = () => { selectedColor = c.value; renderBody(); };
          if (selectedColor === c.value) sw.appendChild(PP.el('i', { 'data-lucide': 'check', style: 'color:white;width:16px;height:16px' }));
          g.appendChild(sw);
          });
          return g;
        })(),
      ]));
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Icon']),
        (() => {
          const g = PP.el('div', { class: 'icon-grid' });
          icons.slice(0, 80).forEach(i => {
            const s = PP.el('div', {
              class: 'icon-swatch' + (selectedIcon === i.name ? ' selected' : ''),
              title: i.name
            }, [PP.el('i', { 'data-lucide': i.name })]);
            s.onclick = () => { selectedIcon = i.name; renderBody(); };
            g.appendChild(s);
          });
          return g;
        })(),
      ]));
      if (!editing) {
        body.appendChild(PP.el('div', { class: 'form-row' }, [
          PP.el('div', { class: 'form-group' }, [
            PP.el('label', { class: 'form-label' }, ['Initial Balance']),
            (() => {
              const inp = PP.el('input', { class: 'form-input', type: 'number', min: '0', step: '0.01', placeholder: '0.00', value: initialBalance || '' });
              inp.oninput = () => initialBalance = parseFloat(inp.value) || 0;
              return inp;
            })(),
          ]),
          PP.el('div', { class: 'form-group' }, [
            PP.el('label', { class: 'form-label' }, ['Priority']),
            (() => {
              const sel = PP.el('select', { class: 'form-select' });
              [{v:0,l:'Normal'},{v:1,l:'Low'},{v:2,l:'Medium'},{v:3,l:'High'},{v:4,l:'Critical'}].forEach(o => {
                const op = PP.el('option', { value: o.v }, [o.l]);
                if (priority == o.v) op.selected = true;
                sel.appendChild(op);
              });
              sel.onchange = () => priority = parseInt(sel.value);
              return sel;
            })(),
          ]),
        ]));
      }
      body.appendChild(PP.el('div', { class: 'form-row' }, [
        PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Total Budget (optional)']),
          (() => {
            const inp = PP.el('input', { class: 'form-input', type: 'number', min: '0', step: '0.01', placeholder: 'e.g. 50000', value: budgetAmount || '' });
            inp.oninput = () => budgetAmount = parseFloat(inp.value) || 0;
            return inp;
          })(),
        ]),
        PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Monthly Limit (optional)']),
          (() => {
            const inp = PP.el('input', { class: 'form-input', type: 'number', min: '0', step: '0.01', placeholder: 'e.g. 10000', value: monthlyLimit || '' });
            inp.oninput = () => monthlyLimit = parseFloat(inp.value) || 0;
            return inp;
          })(),
        ]),
      ]));

      modal.body.innerHTML = '';
      modal.body.appendChild(body);
      modal.footer.innerHTML = '';
      modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
      const saveBtn = PP.el('button', {
        class: 'btn btn-primary',
        onclick: async () => {
          if (!nameVal?.trim()) return PP.UI.toast('Name required', 'Please enter a pocket name', 'warning');
          saveBtn.disabled = true; saveBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Saving…';
          PP.refreshIcons();
          try {
            const payload = {
              name: nameVal.trim(),
              description: descriptionVal.trim() || null,
              color: selectedColor,
              icon: selectedIcon,
              icon_type: 'lucide',
              budget_amount: budgetAmount,
              monthly_limit: monthlyLimit,
              priority,
            };
            if (!editing) payload.initial_balance = initialBalance;
            const res = editing ? await PP.PocketsAPI.update(existing.id, payload) : await PP.PocketsAPI.create(payload);
            PP.UI.toast(editing ? 'Pocket updated' : 'Pocket created', res.message || '', 'success');
            modal.close();
            opts.onSaved?.(res?.data?.pocket);
            PP.emit('pockets:changed');
            PP.refreshCurrentView();
          } catch (e) { PP.UI.toast('Save failed', e.message, 'error'); }
          finally { saveBtn.disabled = false; saveBtn.innerHTML = editing ? 'Save Changes' : 'Create Pocket'; }
        },
      }, [editing ? 'Save Changes' : 'Create Pocket']);
      modal.footer.appendChild(saveBtn);
      PP.refreshIcons();
    };
    renderBody();
  },

  async addIncome(opts = {}) {
    const pockets = await PP.PocketsAPI.list({ per_page: 200 }).then(r => r.data.items).catch(() => PP.state.pockets || []) || [];
    PP.state.pockets = pockets;
    const rules = await PP.WalletAPI.rules({ active_only: true }).then(r => r.data?.rules || []).catch(() => []) || [];
    let step = 1; let totalAmount = 0;
    let strategy = opts.strategy || 'single';
    let singlePocketId = opts.singlePocketId || pockets[0]?.id;
    let source = 'Salary'; let descriptionVal = ''; let fromWallet = true;
    let percentages = pockets.reduce((acc, p, i) => { acc[p.id] = i === 0 ? 100 : 0; return acc; }, {});
    let fixedAmounts = pockets.reduce((acc, p) => { acc[p.id] = 0; return acc; }, {});
    let selectedRuleId = rules[0]?.id;
    let allocations = []; let summary = {};
    const modal = PP.UI.modal({ title: 'Add Income', subtitle: 'Distribute your income across pockets', icon: 'arrow-down-left', iconClass: 'bg-success', size: 'lg' });

    const renderStepper = () => PP.el('div', { class: 'stepper' },
      ['Amount','Strategy','Review'].map((label, i) => {
        const n = i + 1;
        const el = PP.el('div', { class: `step ${step === n ? 'active' : step > n ? 'done' : ''}` }, [
          PP.el('div', { class: 'step-circle' }, [step > n ? PP.el('i', { 'data-lucide': 'check', style: 'width:14px;height:14px' }) : String(n)]),
          PP.el('div', { class: 'step-label' }, [label]),
        ]);
        if (n < 3) el.appendChild(PP.el('div', { class: 'step-line' }));
        return el;
      })
    );

    const renderBody = async () => {
      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
      body.appendChild(renderStepper());
      if (step === 1) {
        body.appendChild(PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Income Amount *']),
          (() => {
            const inp = PP.el('input', { class: 'form-input', type: 'number', min: '1', step: '0.01', placeholder: 'e.g. 60000', value: totalAmount || '', style: 'font-size:1.25rem;font-weight:700' });
            inp.oninput = () => totalAmount = parseFloat(inp.value) || 0;
            setTimeout(() => inp.focus(), 50);
            return inp;
          })(),
        ]));
        body.appendChild(PP.el('div', { class: 'form-row' }, [
          PP.el('div', { class: 'form-group' }, [
            PP.el('label', { class: 'form-label' }, ['Source']),
            (() => {
              const s = PP.el('select', { class: 'form-select' });
              ['Salary','Freelance','Gift','Investment Returns','Business','Rent','Other'].forEach(opt => {
                const o = PP.el('option', {}, [opt]);
                if (source === opt) o.selected = true;
                s.appendChild(o);
              });
              s.onchange = () => source = s.value;
              return s;
            })(),
          ]),
          PP.el('div', { class: 'form-group' }, [
            PP.el('label', { class: 'form-label' }, ['Fund from']),
            (() => {
              const s = PP.el('select', { class: 'form-select' });
              const o1 = PP.el('option', { value: 'wallet' }, ['Wallet Balance']);
              const o2 = PP.el('option', { value: 'external' }, ['External (New Money)']);
              if (fromWallet) o1.selected = true; else o2.selected = true;
              s.append(o1, o2);
              s.onchange = () => fromWallet = s.value === 'wallet';
              return s;
            })(),
          ]),
        ]));
        body.appendChild(PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Notes (optional)']),
          (() => {
            const t = PP.el('textarea', { class: 'form-textarea', placeholder: 'Any details about this income?', rows: 2 });
            t.value = descriptionVal;
            t.oninput = () => descriptionVal = t.value;
            return t;
          })(),
        ]));
      }
      if (step === 2) {
        body.appendChild(PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Distribution Strategy']),
          (() => {
            const row = PP.el('div', { style: 'display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem' });
            [{v:'single',l:'Single Pocket',icon:'folder'},{v:'percentage',l:'By Percentage',icon:'percent'},{v:'fixed',l:'Fixed Amounts',icon:'coins'},{v:'rule',l:'Saved Rule',icon:'bookmark'}].forEach(o => {
              const b = PP.el('button', { type: 'button', class: `btn ${strategy === o.v ? 'btn-primary' : 'btn-outline'}`, style: 'flex-direction:column;gap:.3rem;height:auto;padding:1rem;align-items:center',
                onclick: () => { strategy = o.v; renderBody(); } }, [
                PP.el('i', { 'data-lucide': o.icon, style: 'width:22px;height:22px' }),
                PP.el('span', { style: 'font-size:.82rem' }, [o.l]),
              ]);
              row.appendChild(b);
            });
            return row;
          })(),
        ]));
        if (strategy === 'single') body.appendChild(PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Select Pocket']),
          (() => {
            const sel = PP.el('select', { class: 'form-select' });
            pockets.forEach(p => { const o = PP.el('option', { value: p.id }, [`${p.name} — ${PP.fmt(p.current_balance)}`]); if (p.id == singlePocketId) o.selected = true; sel.appendChild(o); });
            sel.onchange = () => singlePocketId = parseInt(sel.value);
            return sel;
          })(),
        ]));
        if (strategy === 'percentage') {
          const pctWrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.5rem;max-height:260px;overflow:auto;padding:.25rem' });
          let total = Object.values(percentages).reduce((a, b) => a + b, 0);
          body.appendChild(PP.el('div', { style: 'display:flex;justify-content:space-between;margin-bottom:.25rem' }, [
            PP.el('span', { class: 'form-label' }, ['Total Allocation']),
            PP.el('span', { class: 'font-semibold', style: `color:${total === 100 ? 'var(--success)' : total > 100 ? 'var(--danger)' : 'var(--warning)'}` }, [`${total.toFixed(0)}%`]),
          ]));
          pockets.forEach(p => {
            const r = PP.el('div', { style: 'display:grid;grid-template-columns:1fr 80px auto;gap:.5rem;align-items:center' });
            r.appendChild(PP.el('div', { style: 'display:flex;align-items:center;gap:.5rem' }, [
              PP.el('div', { style: `width:30px;height:30px;border-radius:8px;background:${p.color};color:white;display:flex;align-items:center;justify-content:center;flex-shrink:0` }, [PP.el('i', { 'data-lucide': p.icon, style: 'width:14px;height:14px' })]),
              PP.el('span', { style: 'font-weight:500' }, [p.name]),
            ]));
            const inp = PP.el('input', { class: 'form-input', type: 'number', min: '0', max: '100', step: '1', value: percentages[p.id] || 0, style: 'text-align:right;padding:.5rem;font-size:.85rem' });
            inp.oninput = () => { percentages[p.id] = parseFloat(inp.value) || 0; renderBody(); };
            r.appendChild(inp);
            const amt = ((percentages[p.id] || 0) / 100 )* (totalAmount || 0);
            r.appendChild(PP.el('span', { class: 'text-muted mono', style: 'font-size:.72rem;width:80px;text-align:right' }, [PP.fmt(amt)]));
            pctWrap.appendChild(r);
          });
          body.appendChild(pctWrap);
        }
        if (strategy === 'fixed') {
          const fixWrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.5rem;max-height:260px;overflow:auto;padding:.25rem' });
          let allocated = Object.values(fixedAmounts).reduce((a, b) => a + b, 0);
          fixWrap.appendChild(PP.el('div', { style: 'display:flex;justify-content:space-between;margin-bottom:.25rem' }, [
            PP.el('span', { class: 'form-label' }, ['Allocated']),
            PP.el('span', { class: 'font-semibold', style: `color:${Math.abs(allocated - totalAmount) < 0.01 ? 'var(--success)' : allocated > totalAmount ? 'var(--danger)' : 'var(--warning)'}` }, [`${PP.fmt(allocated)} / ${PP.fmt(totalAmount)}`]),
          ]));
          pockets.forEach(p => {
            const r = PP.el('div', { style: 'display:grid;grid-template-columns:1fr 110px;gap:.5rem;align-items:center' });
            r.appendChild(PP.el('div', { style: 'display:flex;align-items:center;gap:.5rem' }, [
              PP.el('div', { style: `width:30px;height:30px;border-radius:8px;background:${p.color};color:white;display:flex;align-items:center;justify-content:center;flex-shrink:0` }, [PP.el('i', { 'data-lucide': p.icon, style: 'width:14px;height:14px' })]),
              PP.el('span', { style: 'font-weight:500' }, [p.name]),
            ]));
            const inp = PP.el('input', { class: 'form-input', type: 'number', min: '0', step: '0.01', value: fixedAmounts[p.id] || '', style: 'text-align:right;padding:.5rem;font-size:.85rem' });
            inp.oninput = () => { fixedAmounts[p.id] = parseFloat(inp.value) || 0; renderBody(); };
            r.appendChild(inp);
            fixWrap.appendChild(r);
          });
          body.appendChild(fixWrap);
        }
        if (strategy === 'rule') {
          if (!rules.length) body.appendChild(PP.el('div', { class: 'empty-state', style: 'padding:1.5rem' }, [
            PP.el('div', { class: 'empty-icon' }, [PP.el('i', { 'data-lucide': 'bookmark-x' })]),
            PP.el('h3', {}, ['No saved rules yet']),
            PP.el('p', {}, ['Create a distribution rule in the Wallet section.']),
          ]));
          else {
            const rulesWrap = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.5rem;max-height:280px;overflow:auto;padding:.25rem' });
            rules.forEach(r => {
              const card = PP.el('div', { class: 'glass-card', style: `padding:.85rem;cursor:pointer;border:2px solid ${selectedRuleId === r.id ? 'var(--accent)' : 'var(--border)'};transition:all .18s;background:${selectedRuleId === r.id ? 'var(--hover-bg)' : ''}`,
                onclick: () => { selectedRuleId = r.id; renderBody(); } });
              card.appendChild(PP.el('div', { style: 'display:flex;justify-content:space-between;align-items:flex-start;gap:.5rem' }, [
                PP.el('div', {}, [
                  PP.el('div', { style: 'font-weight:700;display:flex;align-items:center;gap:.4rem' }, [
                    r.is_default && PP.el('span', { class: 'chip success', style: 'font-size:.6rem;padding:1px 6px' }, ['Default']),
                    r.name,
                  ]),
                  PP.el('div', { class: 'text-muted text-sm', style: 'margin-top:.2rem' }, [`${r.rule_type} • ${r.allocations?.length || 0} pockets • used ${r.usage_count || 0}x`]),
                ]),
                selectedRuleId === r.id && PP.el('i', { 'data-lucide': 'check-circle-2', style: 'color:var(--success);width:20px;height:20px;flex-shrink:0' }),
              ]));
              rulesWrap.appendChild(card);
            });
            body.appendChild(rulesWrap);
          }
        }
      }
      if (step === 3) {
        body.appendChild(PP.el('div', { style: 'text-align:center;padding:2rem' }, [
          PP.el('i', { 'data-lucide': 'loader-2', style: 'animation:slowSpin 1s linear infinite;width:32px;height:32px;color:var(--accent)' }),
          PP.el('p', { style: 'margin-top:.75rem;color:var(--text-muted)' }, ['Calculating distribution…']),
        ]));
        PP.refreshIcons();
        let extras = {};
        if (strategy === 'single') extras.pocket_id = singlePocketId;
        if (strategy === 'percentage') extras.splits = pockets.filter(p => percentages[p.id] > 0).map(p => ({ pocket_id: p.id, percentage: percentages[p.id] }));
        if (strategy === 'fixed') extras.splits = pockets.filter(p => fixedAmounts[p.id] > 0).map(p => ({ pocket_id: p.id, amount: fixedAmounts[p.id] }));
        if (strategy === 'rule') extras.rule_id = selectedRuleId;
        try {
          const prev = await PP.WalletAPI.previewDistribution(totalAmount, strategy, extras);
          allocations = prev?.data?.allocations || [];
          summary = prev?.data?.summary || {};
          body.innerHTML = '';
          body.appendChild(renderStepper());
          body.appendChild(PP.el('div', { class: 'glass-card', style: 'padding:1.25rem;margin-bottom:.5rem' }, [
            PP.el('div', { style: 'display:flex;justify-content:space-between;align-items:baseline;gap:.5rem' }, [
              PP.el('div', {}, [
                PP.el('div', { class: 'text-muted text-xs', style: 'text-transform:uppercase;letter-spacing:.08em;font-weight:700' }, [`${source || 'Income'} • ${summary.strategy}`]),
                PP.el('div', { style: 'font-family:var(--font-display);font-size:2rem;font-weight:800;margin-top:.25rem' }, [PP.fmt(totalAmount)]),
                descriptionVal && PP.el('div', { class: 'text-muted text-sm', style: 'margin-top:.25rem' }, [descriptionVal]),
              ]),
              fromWallet ? PP.el('span', { class: 'chip' }, ['From Wallet']) : PP.el('span', { class: 'chip success' }, ['External']),
            ]),
          ]));
          body.appendChild(PP.el('div', { style: 'display:flex;flex-direction:column;gap:.5rem;max-height:280px;overflow:auto;padding:.25rem' },
            allocations.map(a => PP.el('div', { class: 'glass-card', style: 'padding:.75rem .9rem;display:flex;align-items:center;gap:.75rem' }, [
              PP.el('div', { style: `width:38px;height:38px;border-radius:10px;background:${a.pocket_color};color:white;display:flex;align-items:center;justify-content:center;flex-shrink:0` }, [PP.el('i', { 'data-lucide': a.pocket_icon, style: 'width:18px;height:18px' })]),
              PP.el('div', { style: 'flex:1;min-width:0' }, [
                PP.el('div', { style: 'font-weight:600' }, [a.pocket_name]),
                a.percentage != null && PP.el('div', { class: 'text-muted text-xs' }, [`${a.percentage}%`]),
              ]),
              PP.el('div', { style: 'text-align:right' }, [PP.el('div', { style: 'font-weight:700;font-family:var(--font-display)' }, [PP.fmt(a.amount)])]),
            ]))
          ));
          if (summary.remaining > 0.01) body.appendChild(PP.el('div', { class: 'chip warning', style: 'width:max-content;margin-top:.5rem' }, [
            PP.el('i', { 'data-lucide': 'alert-triangle', style: 'width:14px;height:14px' }),
            `${PP.fmt(summary.remaining)} unallocated will remain.`,
          ]));
        } catch (e) { body.innerHTML = ''; body.appendChild(renderStepper()); body.appendChild(PP.el('div', { class: 'empty-state' }, [
          PP.el('div', { class: 'empty-icon' }, [PP.el('i', { 'data-lucide': 'alert-circle' })]), PP.el('h3', {}, ['Preview failed']), PP.el('p', {}, [e.message || 'Unable to calculate distribution'])])); }
      }
      modal.body.innerHTML = ''; modal.body.appendChild(body);
      modal.footer.innerHTML = '';
      modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
      let nextBtn;
      if (step < 3) {
        if (step > 1) modal.footer.appendChild(PP.el('button', { class: 'btn btn-outline', onclick: () => { step--; renderBody(); } }, [PP.el('i', { 'data-lucide': 'arrow-left', style: 'width:15px;height:15px' }), 'Back']));
        nextBtn = PP.el('button', { class: 'btn btn-primary', onclick: () => {
          if (step === 1 && !(totalAmount > 0)) return PP.UI.toast('Enter amount', 'Please enter a valid income amount', 'warning');
          if (step === 2 && strategy === 'percentage') {
            const total = Object.values(percentages).reduce((a, b) => a + b, 0);
            if (total > 100.01) return PP.UI.toast('Over 100%', `Percentages sum to ${total}%`, 'warning');
          }
          if (step === 2 && strategy === 'fixed') {
            const total = Object.values(fixedAmounts).reduce((a, b) => a + b, 0);
            if (total - 0.01 > totalAmount) return PP.UI.toast('Amount exceeded', `Fixed amounts (${PP.fmt(total)}) exceed ${PP.fmt(totalAmount)}`, 'warning');
          }
          step++; renderBody();
        }}, [step === 2 ? 'Review' : 'Next', PP.el('i', { 'data-lucide': 'arrow-right', style: 'width:15px;height:15px' })]);
        modal.footer.appendChild(nextBtn);
      } else {
        modal.footer.appendChild(PP.el('button', { class: 'btn btn-outline', onclick: () => { step = 2; renderBody(); } }, [PP.el('i', { 'data-lucide': 'arrow-left', style: 'width:15px;height:15px' }), 'Back']));
        const confirmBtn = PP.el('button', { class: 'btn btn-success', onclick: async () => {
          confirmBtn.disabled = true;
          confirmBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Processing…';
          PP.refreshIcons();
          try {
            let extras = {};
            if (strategy === 'single') extras.pocket_id = singlePocketId;
            if (strategy === 'percentage') extras.splits = pockets.filter(p => percentages[p.id] > 0).map(p => ({ pocket_id: p.id, percentage: percentages[p.id] }));
            if (strategy === 'fixed') extras.splits = pockets.filter(p => fixedAmounts[p.id] > 0).map(p => ({ pocket_id: p.id, amount: fixedAmounts[p.id] }));
            if (strategy === 'rule') extras.rule_id = selectedRuleId;
            extras.source = source; extras.description = descriptionVal || source;
            const res = await PP.WalletAPI.executeDistribution(totalAmount, strategy, extras);
            modal.close();
            PP.UI.showSuccess({ title: 'Income Distributed', subtitle: `${PP.fmt(summary?.total_allocated || totalAmount)} has been distributed`, meta: { 'Source': source, 'Pockets': `${res?.data?.pockets_updated || allocations?.length || 0} pockets`, 'Strategy': strategy } });
            opts.onDone?.();
            PP.emit('pockets:changed'); PP.emit('transactions:changed'); PP.refreshCurrentView();
          } catch (e) { PP.UI.toast('Distribution failed', e.message, 'error'); }
          finally { confirmBtn.disabled = false; confirmBtn.innerHTML = [PP.el('i', { 'data-lucide': 'check-circle-2', style: 'width:16px;height:16px' }), 'Confirm & Distribute']; }
        }}, [PP.el('i', { 'data-lucide': 'check-circle-2', style: 'width:16px;height:16px' }), 'Confirm & Distribute']);
        modal.footer.appendChild(confirmBtn);
      }
      PP.refreshIcons();
    };
    await renderBody();
  },

  async addExpense(preselectedPocketId = null, opts = {}) {
    const pockets = await PP.PocketsAPI.list({ per_page: 200 }).then(r => r.data.items).catch(() => PP.state.pockets || []) || [];
    PP.state.pockets = pockets;
    const categories = PP.state.categories?.length ? PP.state.categories : await PP.WalletAPI.categories().then(r => r.data.categories).catch(() => []) || [];
    PP.state.categories = categories;
    let step = 1; let pocketId = preselectedPocketId || pockets[0]?.id; let amount = 0;
    let category = categories[0] || 'Custom'; let descriptionVal = ''; let merchantVal = '';
    let prev;
    const modal = PP.UI.modal({ title: 'Make Payment', subtitle: 'Pay securely from your pocket', icon: 'arrow-up-right', iconClass: 'bg-danger', size: 'lg' });
    const stepper = () => PP.el('div', { class: 'stepper' },
      ['Pocket','Amount','Category','Review'].map((label, i) => {
        const n = i + 1;
        const s = PP.el('div', { class: `step ${step === n ? 'active' : step > n ? 'done' : ''}` }, [
          PP.el('div', { class: 'step-circle' }, [step > n ? PP.el('i', { 'data-lucide': 'check', style: 'width:14px;height:14px' }) : String(n)]),
          PP.el('div', { class: 'step-label' }, [label]),
        ]);
        if (n < 4) s.appendChild(PP.el('div', { class: 'step-line' }));
        return s;
      })
    );
    const renderBody = async () => {
      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
      body.appendChild(stepper());
      if (step === 1) {
        body.appendChild(PP.el('div', { class: 'form-group' }, [PP.el('label', { class: 'form-label' }, ['Select Pocket *'])]));
        const grid = PP.el('div', { style: 'display:grid;grid-template-columns:repeat(2,1fr);gap:.5rem;max-height:320px;overflow:auto;padding:.25rem' });
        pockets.forEach(p => {
          const card = PP.el('div', {
            class: 'glass-card pocket-card',
            style: Object.entries({ ...PP.UI.pocketStyleVars(p), padding: '.85rem', cursor: 'pointer',
              border: pocketId === p.id ? '2px solid var(--accent)' : '1px solid var(--border)',
              background: pocketId === p.id ? 'var(--hover-bg)' : '',
              opacity: p.archived ? '.5' : '1',
              pointerEvents: p.archived ? 'none' : 'auto',
            }).reduce((s, [k, v]) => `${s}${k}:${typeof v === 'number' ? v : v};`, ''),
            onclick: () => { pocketId = p.id; renderBody(); }
          });
          card.appendChild(PP.el('div', { class: 'pocket-card-inner' }, [
            PP.el('div', { style: 'display:flex;justify-content:space-between;align-items:center' }, [
              PP.el('div', { style: 'display:flex;align-items:center;gap:.5rem' }, [
                PP.el('div', { style: `width:34px;height:34px;border-radius:10px;background:${p.color};color:white;display:flex;align-items:center;justify-content:center` }, [PP.el('i', { 'data-lucide': p.icon, style: 'width:16px;height:16px' })]),
                PP.el('span', { style: 'font-weight:700' }, [p.name]),
              ]),
              pocketId === p.id && PP.el('i', { 'data-lucide': 'check-circle-2', style: 'color:var(--success);width:18px;height:18px' }),
            ]),
            PP.el('div', { style: 'margin-top:.5rem' }, [
              PP.el('div', { style: 'font-family:var(--font-display);font-weight:800;font-size:1.1rem' }, [PP.fmt(p.current_balance)]),
              p.monthly_limit > 0 && PP.el('div', { class: 'pocket-progress', style: 'margin-top:.5rem;height:5px' }, [
                PP.el('div', { class: 'pocket-progress-fill', style: `width:${Math.min(100, p.budget_usage_percent || 0)}%` }),
              ]),
            ]),
          ]));
          grid.appendChild(card);
        });
        body.appendChild(grid);
      }
      if (step === 2) {
        const pocket = pockets.find(p => p.id == pocketId);
        if (pocket) body.appendChild(PP.el('div', {
          class: 'glass-card',
          style: Object.entries(PP.UI.pocketStyleVars(pocket)).reduce((s, [k, v]) => `${s}${k}:${typeof v === 'number' ? v : v};`, '') + 'padding:1rem;display:flex;align-items:center;gap:.75rem',
        }, [
          PP.el('div', { style: `width:44px;height:44px;border-radius:12px;background:${pocket.color};color:white;display:flex;align-items:center;justify-content:center` }, [PP.el('i', { 'data-lucide': pocket.icon, style: 'width:20px;height:20px' })]),
          PP.el('div', { style: 'flex:1' }, [PP.el('div', { style: 'font-weight:700' }, [pocket.name]), PP.el('div', { class: 'text-muted text-sm' }, ['Available balance'])]),
          PP.el('div', { style: 'text-align:right' }, [
    PP.el('div', { style: 'font-family:var(--font-display);font-size:1.2rem;font-weight:800' }, [
        PP.fmt(pocket.current_balance)
    ])
          ])
        ]));

        body.appendChild(PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Amount *']),
          (() => {
            const inp = PP.el('input', { class: 'form-input', type: 'number', min: '0.01', step: '0.01', placeholder: '0.00', value: amount || '', style: 'font-size:1.5rem;font-weight:700;padding:1rem' });
            inp.oninput = () => amount = parseFloat(inp.value) || 0;
            setTimeout(() => inp.focus(), 50);
            return inp;
          })(),
        ]));
        body.appendChild(PP.el('div', { class: 'form-row' }, [
          PP.el('div', { class: 'form-group' }, [
            PP.el('label', { class: 'form-label' }, ['Merchant (optional)']),
            (() => {
              const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. Amazon, Starbucks', value: merchantVal });
              inp.oninput = () => merchantVal = inp.value;
              return inp;
            })(),
          ]),
          PP.el('div', { class: 'form-group' }, [
            PP.el('label', { class: 'form-label' }, ['Notes (optional)']),
            (() => {
              const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. Monthly groceries', value: descriptionVal });
              inp.oninput = () => descriptionVal = inp.value;
              return inp;
            })(),
          ]),
        ]));
      }
      if (step === 3) {
        body.appendChild(PP.el('div', { class: 'form-group' }, [PP.el('label', { class: 'form-label' }, ['Select Category'])]));
        const chips = PP.el('div', { style: 'display:flex;flex-wrap:wrap;gap:.4rem;max-height:320px;overflow:auto;padding:.25rem' });
        categories.forEach(c => {
          const chip = PP.el('button', { type: 'button', class: `chip ${category === c ? 'active' : ''}`, onclick: () => { category = c; renderBody(); } }, [c]);
          chips.appendChild(chip);
        });
        body.appendChild(chips);
      }
      if (step === 4) {
        body.appendChild(PP.el('div', { style: 'text-align:center;padding:2rem' }, [
          PP.el('i', { 'data-lucide': 'loader-2', style: 'animation:slowSpin 1s linear infinite;width:32px;height:32px;color:var(--accent)' }),
        ]));
        PP.refreshIcons();
        try {
          prev = await PP.TxAPI.previewExpense(pocketId, amount, { category, description: descriptionVal, merchant: merchantVal });
          const canAfford = prev?.data?.can_afford;
          const pocket = prev?.data?.pocket;
          const alt = prev?.data?.alternate_pockets || [];
          body.innerHTML = '';
          body.appendChild(stepper());
          body.appendChild(PP.el('div', { class: 'glass-card', style: `padding:1.25rem;border:2px solid ${canAfford ? 'var(--border-strong)' : 'var(--danger)'}` }, [
            PP.el('div', { style: 'display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;flex-wrap:wrap' }, [
              PP.el('div', { style: 'display:flex;align-items:center;gap:.75rem' }, [
                PP.el('div', { style: `width:48px;height:48px;border-radius:14px;background:${pocket?.color || '#6366f1'};color:white;display:flex;align-items:center;justify-content:center` }, [PP.el('i', { 'data-lucide': pocket?.icon || 'wallet', style: 'width:22px;height:22px' })]),
                PP.el('div', {}, [
                  PP.el('div', { style: 'font-size:.75rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;letter-spacing:.08em' }, ['From Pocket']),
                  PP.el('div', { style: 'font-size:1rem;font-weight:700' }, [pocket?.name || 'Pocket']),
                ]),
              ]),
              PP.el('div', { style: 'text-align:right' }, [
                PP.el('div', { style: 'font-size:.75rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;letter-spacing:.08em' }, ['Amount']),
                PP.el('div', { style: 'font-family:var(--font-display);font-size:2rem;font-weight:800;color:var(--danger)' }, [PP.fmt(amount)]),
              ]),
            ]),
            PP.el('div', { style: 'height:1px;background:var(--border);margin:1rem 0' }),
            PP.el('div', { style: 'display:grid;grid-template-columns:1fr 1fr;gap:.75rem' }, [
              PP.el('div', {}, [PP.el('div', { class: 'text-xs', style: 'text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--text-dim)' }, ['Balance Before']), PP.el('div', { style: 'font-family:var(--font-display);font-size:1.05rem;font-weight:700;margin-top:.15rem' }, [PP.fmt(prev?.data?.balance_before || 0)])]),
              PP.el('div', {}, [PP.el('div', { class: 'text-xs', style: 'text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--text-dim)' }, ['Balance After']), PP.el('div', { style: `font-family:var(--font-display);font-size:1.05rem;font-weight:700;margin-top:.15rem;color:${canAfford ? 'var(--text)' : 'var(--danger)'}` }, [PP.fmt(prev?.data?.balance_after || 0)])]),
              PP.el('div', {}, [PP.el('div', { class: 'text-xs', style: 'text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--text-dim)' }, ['Category']), PP.el('div', { style: 'font-weight:600;margin-top:.15rem' }, [category])]),
              merchantVal && PP.el('div', {}, [PP.el('div', { class: 'text-xs', style: 'text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--text-dim)' }, ['Merchant']), PP.el('div', { style: 'font-weight:600;margin-top:.15rem' }, [merchantVal])]),
            ]),
          ]));
          if (!canAfford) {
            body.appendChild(PP.el('div', { class: 'glass-card', style: 'padding:1rem;border:2px solid var(--danger);background:rgba(239,68,68,.08)' }, [
              PP.el('div', { style: 'display:flex;gap:.75rem;align-items:flex-start' }, [
                PP.el('div', { style: 'width:40px;height:40px;border-radius:12px;background:rgba(239,68,68,.15);color:var(--danger);display:flex;align-items:center;justify-content:center;flex-shrink:0' }, [PP.el('i', { 'data-lucide': 'alert-triangle', style: 'width:20px;height:20px' })]),
                PP.el('div', {}, [
                  PP.el('div', { style: 'font-weight:700;font-size:1rem' }, [`Your ${pocket?.name || ''} Pocket has only ${PP.fmt(pocket?.current_balance || 0)} remaining.`]),
                  PP.el('div', { class: 'text-muted text-sm', style: 'margin-top:.25rem' }, [`You need ${PP.fmt(prev?.data?.required_amount - prev?.data?.pocket_balance || 0)} more.`]),
                  PP.el('div', { style: 'display:flex;gap:.5rem;margin-top:.75rem;flex-wrap:wrap' }, [
                    alt.length > 0 && PP.el('button', { class: 'btn btn-primary btn-sm', onclick: () => { pocketId = alt[0].id; step = 1; renderBody(); } }, [PP.el('i', { 'data-lucide': 'wallet-cards', style: 'width:14px;height:14px' }), `Use ${alt[0].name} (${PP.fmt(alt[0].current_balance)})`]),
                    PP.el('button', { class: 'btn btn-outline btn-sm', onclick: () => { modal.close(); PP.Modals.transfer({ toPocketId: pocketId }); } }, [PP.el('i', { 'data-lucide': 'refresh-ccw', style: 'width:14px;height:14px' }), 'Transfer Money']),
                    PP.el('button', { class: 'btn btn-ghost btn-sm', onclick: () => { step = 1; renderBody(); } }, ['Change Pocket']),
                  ]),
                ]),
              ]),
            ]));
          }
        } catch (e) { body.innerHTML = ''; body.appendChild(stepper()); body.appendChild(PP.el('div', { class: 'empty-state' }, [PP.el('div', { class: 'empty-icon' }, [PP.el('i', { 'data-lucide': 'alert-circle' })]), PP.el('h3', {}, ['Preview failed']), PP.el('p', {}, [e.message || 'Error'])])); }
      }
      modal.body.innerHTML = ''; modal.body.appendChild(body);
      modal.footer.innerHTML = '';
      modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
      let nextBtn;
      if (step < 4) {
        if (step > 1) modal.footer.appendChild(PP.el('button', { class: 'btn btn-outline', onclick: () => { step--; renderBody(); } }, [PP.el('i', { 'data-lucide': 'arrow-left', style: 'width:15px;height:15px' }), 'Back']));
        const labels = ['Choose Amount', 'Pick Category', 'Review'];
        nextBtn = PP.el('button', { class: 'btn btn-primary', onclick: () => {
          if (step === 1 && !pocketId) return PP.UI.toast('Select pocket', 'Please choose a pocket', 'warning');
          if (step === 2 && !(amount > 0)) return PP.UI.toast('Enter amount', 'Please enter a valid amount', 'warning');
          step++; renderBody();
        }}, [labels[step - 1], PP.el('i', { 'data-lucide': 'arrow-right', style: 'width:15px;height:15px' })]);
        modal.footer.appendChild(nextBtn);
      } else {
        modal.footer.appendChild(PP.el('button', { class: 'btn btn-outline', onclick: () => { step = 3; renderBody(); } }, [PP.el('i', { 'data-lucide': 'arrow-left', style: 'width:15px;height:15px' }), 'Back']));
        const payBtn = PP.el('button', { class: 'btn btn-danger', disabled: !prev?.data?.can_afford, onclick: async () => {
          try {
            const pin = await PP.UI.pinPrompt({ title: 'Confirm Payment', subtitle: `Pay ${PP.fmt(amount)} from ${prev?.data?.pocket?.name || 'Pocket'}` });
            if (!pin) return;
            payBtn.disabled = true; payBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Processing…';
            PP.refreshIcons();
            const res = await PP.TxAPI.executeExpense(pocketId, amount, pin, { category, description: descriptionVal, merchant: merchantVal });
            modal.close();
            PP.UI.showSuccess({
              title: 'Payment Successful',
              subtitle: `${PP.fmt(amount)} paid from ${prev?.data?.pocket?.name || 'Pocket'}`,
              qr_code_url: res?.data?.receipt_qr || res?.data?.qr_code_url || res?.data?.transaction?.qr_code_url,
              meta: { 'Category': category, 'Merchant': merchantVal || '—', 'Pocket balance': PP.fmt(res?.data?.pocket_balance || 0) }
            });
            opts.onDone?.(); PP.emit('transactions:changed'); PP.emit('pockets:changed'); PP.refreshCurrentView();
          } catch (e) {
            if (e.status === 400 && e.data?.code === 'INSUFFICIENT_BALANCE') { PP.UI.toast('Insufficient balance', e.message, 'error'); step = 1; renderBody(); }
            else PP.UI.toast('Payment failed', e.message, 'error');
          } finally { payBtn.disabled = false; payBtn.innerHTML = [PP.el('i', { 'data-lucide': 'lock', style: 'width:16px;height:16px' }), 'Confirm & Pay']; }
        }}, [PP.el('i', { 'data-lucide': 'lock', style: 'width:16px;height:16px' }), 'Confirm & Pay']);
        modal.footer.appendChild(payBtn);
      }
      PP.refreshIcons();
    };
    await renderBody();
  },

  async transfer(opts = {}) {
    const pockets = await PP.PocketsAPI.list({ per_page: 200 }).then(r => r.data.items).catch(() => PP.state.pockets || []) || [];
    const active = pockets.filter(p => !p.archived);
    let fromId = opts.fromPocketId || active[0]?.id;
    let toId = opts.toPocketId || (active.find(p => p.id != fromId)?.id);
    let amount = 0; let desc = '';
    const modal = PP.UI.modal({ title: 'Transfer Between Pockets', subtitle: 'Move money instantly between your pockets', icon: 'refresh-ccw', iconClass: 'bg-info', size: 'md' });
    const renderBody = () => {
      const fromP = active.find(p => p.id == fromId);
      const toP = active.find(p => p.id == toId);
      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
      const swapRow = PP.el('div', { style: 'display:grid;grid-template-columns:1fr auto 1fr;gap:.5rem;align-items:end' });
      const pocketSel = (label, selected, onChange, exclude) => PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, [label]),
        (() => {
          const s = PP.el('select', { class: 'form-select', style: 'padding:.75rem;font-weight:600' });
          active.forEach(p => { if (p.id === exclude) return; const o = PP.el('option', { value: p.id }, [`${p.name} — ${PP.fmt(p.current_balance)}`]); if (p.id == selected) o.selected = true; s.appendChild(o); });
          s.onchange = () => onChange(parseInt(s.value));
          return s;
        })(),
      ]);
      swapRow.appendChild(pocketSel('From Pocket', fromId, (v) => { fromId = v; renderBody(); }, toId));
      swapRow.appendChild(PP.el('button', { class: 'btn-icon', style: 'margin-bottom:4px', title: 'Swap', onclick: () => { [fromId, toId] = [toId, fromId]; renderBody(); } }, [PP.el('i', { 'data-lucide': 'arrow-left-right', style: 'width:16px;height:16px' })]));
      swapRow.appendChild(pocketSel('To Pocket', toId, (v) => { toId = v; renderBody(); }, fromId));
      body.appendChild(swapRow);
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Amount *']),
        (() => { const inp = PP.el('input', { class: 'form-input', type: 'number', min: '0.01', step: '0.01', placeholder: '0.00', value: amount || '', style: 'font-size:1.25rem;font-weight:700' }); inp.oninput = () => amount = parseFloat(inp.value) || 0; setTimeout(() => inp.focus(), 50); return inp; })(),
      ]));
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Note (optional)']),
        (() => { const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. Reallocating budget', value: desc }); inp.oninput = () => desc = inp.value; return inp; })(),
      ]));
      if (fromP && amount > 0) {
        body.appendChild(PP.el('div', { class: 'glass-card', style: `padding:1rem;border:1px solid ${fromP.current_balance >= amount ? 'var(--border-strong)' : 'var(--danger)'}` }, [
          PP.el('div', { style: 'display:grid;grid-template-columns:1fr 1fr;gap:.75rem' }, [
            PP.el('div', {}, [PP.el('div', { class: 'text-xs', style: 'text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--text-dim)' }, [fromP.name + ' After']), PP.el('div', { style: 'font-family:var(--font-display);font-weight:800;font-size:1.1rem;margin-top:.15rem' }, [PP.fmt(fromP.current_balance - amount)])]),
            PP.el('div', {}, [PP.el('div', { class: 'text-xs', style: 'text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--text-dim)' }, [(toP?.name || 'Pocket') + ' After']), PP.el('div', { style: 'font-family:var(--font-display);font-weight:800;font-size:1.1rem;margin-top:.15rem;color:var(--success)' }, [PP.fmt((toP?.current_balance || 0) + amount)])]),
          ]),
          fromP.current_balance < amount && PP.el('div', { style: 'color:var(--danger);font-weight:600;margin-top:.5rem;font-size:.85rem;display:flex;align-items:center;gap:.3rem' }, [
            PP.el('i', { 'data-lucide': 'alert-triangle', style: 'width:14px;height:14px' }), `Insufficient balance: ${fromP.name} has only ${PP.fmt(fromP.current_balance)}`,
          ]),
        ]));
      }
      modal.body.innerHTML = ''; modal.body.appendChild(body);
      modal.footer.innerHTML = '';
      modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
      const txBtn = PP.el('button', { class: 'btn btn-primary', onclick: async () => {
        if (!(amount > 0)) return PP.UI.toast('Enter amount', 'Please enter a valid amount', 'warning');
        if (fromId == toId) return PP.UI.toast('Same pocket', 'Choose different pockets', 'warning');
        try {
          const pin = await PP.UI.pinPrompt({ title: 'Confirm Transfer', subtitle: `Transfer ${PP.fmt(amount)} between pockets` });
          if (!pin) return;
          txBtn.disabled = true; txBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Transferring…';
          PP.refreshIcons();
          const res = await PP.TxAPI.transferPockets(fromId, toId, amount, pin, desc || undefined);
          modal.close();
          PP.UI.showSuccess({
            title: 'Transfer Complete',
            subtitle: `${PP.fmt(amount)} transferred successfully`,
            qr_code_url: res?.data?.qr_code_url || res?.data?.receipt_qr || res?.data?.transaction?.qr_code_url,
            meta: {
              'From': active.find(p => p.id == fromId)?.name || '',
              'To': active.find(p => p.id == toId)?.name || ''
            }
          });
          PP.emit('pockets:changed'); PP.emit('transactions:changed'); PP.refreshCurrentView();
        } catch (e) { PP.UI.toast('Transfer failed', e.message, 'error'); }
        finally { txBtn.disabled = false; txBtn.innerHTML = [PP.el('i', { 'data-lucide': 'refresh-ccw', style: 'width:16px;height:16px' }), 'Confirm Transfer']; }
      }}, [PP.el('i', { 'data-lucide': 'refresh-ccw', style: 'width:16px;height:16px' }), 'Confirm Transfer']);
      modal.footer.appendChild(txBtn);
      PP.refreshIcons();
    };
    renderBody();
  },

  setupPin() {
    let pin1 = ''; let pin2 = ''; let step = 1;
    const modal = PP.UI.modal({ title: 'Set Transaction PIN', subtitle: 'Choose a 4-digit PIN for payments and transfers', icon: 'shield-check', iconClass: 'bg-accent', size: 'sm', closable: false });
    const renderBody = () => {
      const sub = modal.root?.querySelector('.modal-subtitle');
      if (sub) sub.textContent = step === 1 ? 'Choose a 4-digit PIN for payments and transfers' : 'Re-enter the same PIN to confirm';
      const dots = []; let entered = [];
      const display = PP.el('div', { class: 'pin-display' }, Array.from({ length: 4 }, (_, i) => { const d = PP.el('div', { class: 'pin-dot' }); dots.push(d); return d; }));
      const update = () => dots.forEach((d, i) => d.classList.toggle('filled', i < entered.length));
      const pad = PP.el('div', { class: 'pin-pad' });
      const body = PP.el('div', {}, [
        PP.el('div', { style: 'text-align:center;margin-bottom:.5rem;font-weight:600;font-size:1rem' }, [step === 1 ? 'Enter 4-digit PIN' : 'Confirm 4-digit PIN']),
        display, pad,
      ]);
      [1,2,3,4,5,6,7,8,9,null,0,'del'].forEach(n => {
        if (n === null) return pad.appendChild(PP.el('div', { style: 'width:1px;height:1px' }));
        const btn = PP.el('button', { class: 'pin-btn' }, [n === 'del' ? PP.el('i', { 'data-lucide': 'delete' }) : String(n)]);
        btn.onclick = () => {
          if (n === 'del') { entered.pop(); return update(); }
          if (entered.length >= 4) return;
          entered.push(String(n)); update();
          if (entered.length === 4) setTimeout(async () => {
            if (step === 1) { pin1 = entered.join(''); step = 2; entered = []; renderBody(); }
            else {
              pin2 = entered.join('');
              if (pin1 !== pin2) { PP.UI.toast('PINs do not match', 'Please try again', 'error'); step = 1; pin1 = ''; entered = []; renderBody(); }
              else {
                try { await PP.Auth.setupPin(pin1, pin2); PP.UI.toast('PIN set', 'Your transaction PIN has been configured', 'success'); modal.close(); PP.state.user = (await PP.Auth.me()).data.user; PP.refreshUserChrome(); }
                catch (e) { PP.UI.toast('PIN setup failed', e.message, 'error'); }
              }
            }
          }, 220);
        };
        pad.appendChild(btn);
      });
      modal.body.innerHTML = ''; modal.body.appendChild(body);
      modal.footer.innerHTML = '';
      if (step === 2) modal.footer.appendChild(PP.el('button', { class: 'btn btn-outline', onclick: () => { step = 1; entered = []; renderBody(); } }, ['Back']));
      modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
      PP.refreshIcons();
    };
    renderBody();
  },

  topup() {
    let amount = 0; let method = 'upi';
    const modal = PP.UI.modal({ title: 'Top Up Wallet', subtitle: 'Add money to your main wallet balance', icon: 'plus', iconClass: 'bg-success', size: 'md' });
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Amount']),
      (() => {
        const inp = PP.el('input', { class: 'form-input', type: 'number', min: '1', step: '0.01', placeholder: '0.00', value: '', style: 'font-size:1.25rem;font-weight:700' });
        inp.oninput = () => amount = parseFloat(inp.value) || 0; setTimeout(() => inp.focus(), 50); return inp;
      })(),
    ]));
    body.appendChild(PP.el('div', { style: 'display:flex;gap:.4rem;flex-wrap:wrap' }, [500, 1000, 2000, 5000, 10000].map(q => PP.el('button', { class: 'btn btn-outline btn-sm', type: 'button', onclick: () => { amount = q; body.querySelector('.form-input').value = q; } }, [PP.fmt(q)]))));
    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Payment Method']),
      (() => {
        const s = PP.el('select', { class: 'form-select' });
        [['upi', 'UPI'], ['card', 'Card'], ['netbanking', 'Net Banking'], ['wallet', 'External Wallet']].forEach(m => { const o = PP.el('option', { value: m[0] }, [m[1]]); s.appendChild(o); });
        s.onchange = () => method = s.value;
        return s;
      })(),
    ]));
    modal.body.innerHTML = ''; modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
    const addBtn = PP.el('button', { class: 'btn btn-success', onclick: async () => {
      if (!(amount > 0)) return PP.UI.toast('Invalid amount', 'Please enter a valid amount', 'warning');
      try {
        addBtn.disabled = true; addBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Processing…'; PP.refreshIcons();
        const res = await PP.WalletAPI.topup(amount, method);
        modal.close();
        PP.UI.showSuccess({ title: 'Wallet Topped Up', subtitle: `${PP.fmt(amount)} has been added to your wallet`, meta: { 'Method': method.toUpperCase(), 'New wallet balance': PP.fmt(res?.data?.new_balance || 0) } });
        PP.emit('transactions:changed'); PP.refreshCurrentView();
      } catch (e) { PP.UI.toast('Top-up failed', e.message, 'error'); }
      finally { addBtn.disabled = false; addBtn.innerHTML = ['Add Money']; }
    }}, ['Add Money']);
    modal.footer.appendChild(addBtn);
    PP.refreshIcons();
  },

  withdraw() {
    let amount = 0; let descriptionVal = '';
    const modal = PP.UI.modal({ title: 'Withdraw from Wallet', subtitle: `Available balance: ${PP.fmt(PP.state.user?.wallet_balance || 0)}`, icon: 'arrow-up-right', iconClass: 'bg-warning', size: 'md' });
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Withdraw Amount']),
      (() => { const inp = PP.el('input', { class: 'form-input', type: 'number', min: '1', step: '0.01', placeholder: '0.00', style: 'font-size:1.25rem;font-weight:700' }); inp.oninput = () => amount = parseFloat(inp.value) || 0; setTimeout(() => inp.focus(), 50); return inp; })(),
    ]));
    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Description (optional)']),
      (() => { const t = PP.el('textarea', { class: 'form-textarea', rows: 2, placeholder: 'e.g. Transfer to bank' }); t.oninput = () => descriptionVal = t.value; return t; })(),
    ]));
    modal.body.innerHTML = ''; modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
    const wdBtn = PP.el('button', { class: 'btn btn-warning', onclick: async () => {
      if (!(amount > 0)) return PP.UI.toast('Invalid amount', 'Please enter a valid amount', 'warning');
      try {
        const pin = await PP.UI.pinPrompt({ title: 'Confirm Withdrawal', subtitle: `Withdraw ${PP.fmt(amount)} from wallet` });
        if (!pin) return;
        wdBtn.disabled = true; wdBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Processing…'; PP.refreshIcons();
        const res = await PP.WalletAPI.withdraw(amount, descriptionVal.trim() || undefined, pin);
        modal.close();
        PP.UI.showSuccess({ title: 'Withdrawal Successful', subtitle: `${PP.fmt(amount)} withdrawn successfully`, meta: { 'New balance': PP.fmt(res?.data?.new_balance || 0) } });
        PP.emit('transactions:changed'); PP.refreshCurrentView();
      } catch (e) { PP.UI.toast('Withdrawal failed', e.message, 'error'); }
      finally { wdBtn.disabled = false; wdBtn.innerHTML = ['Withdraw']; }
    }}, ['Withdraw']);
    modal.footer.appendChild(wdBtn);
    PP.refreshIcons();
  },

  archivePocket(pocket) {
    return PP.UI.confirm(`Archive "${pocket.name}"?`, 'This pocket will be hidden but all transactions and history will be preserved.', { icon: 'archive', iconClass: 'bg-warning', okLabel: 'Archive', okClass: 'btn-warning' }).then(async ok => {
      if (!ok) return false;
      try { await PP.PocketsAPI.archive(pocket.id); PP.UI.toast('Archived', `${pocket.name} has been archived`, 'info'); PP.emit('pockets:changed'); PP.refreshCurrentView(); return true; }
      catch (e) { PP.UI.toast('Error', e.message, 'error'); return false; }
    });
  },

  restorePocket(pocket) {
    return PP.UI.confirm(`Restore "${pocket.name}"?`, 'This pocket will be un-archived and shown in your active pockets.', { icon: 'archive-restore', iconClass: 'bg-success', okLabel: 'Restore', okClass: 'btn-success' }).then(async ok => {
      if (!ok) return false;
      try { await PP.PocketsAPI.restore(pocket.id); PP.UI.toast('Restored', `${pocket.name} has been restored`, 'success'); PP.emit('pockets:changed'); PP.refreshCurrentView(); return true; }
      catch (e) { PP.UI.toast('Error', e.message, 'error'); return false; }
    });
  },

  deletePocket(pocket) {
    return PP.UI.confirm(`Delete "${pocket.name}" permanently?`, pocket.current_balance > 0
      ? `This pocket still has ${PP.fmt(pocket.current_balance)}. Transfer the balance first.`
      : 'All history will be removed and this cannot be undone.',
      { icon: 'trash-2', iconClass: 'bg-danger', okLabel: 'Delete', okClass: 'btn-danger' }).then(async ok => {
      if (!ok) return false;
      try { await PP.PocketsAPI.remove(pocket.id); PP.UI.toast('Deleted', `${pocket.name} has been deleted`, 'info'); PP.emit('pockets:changed'); PP.refreshCurrentView(); return true; }
      catch (e) { PP.UI.toast('Delete failed', e.message, 'error'); return false; }
    });
  },

  async showPocketQR(pocket) {
    const modal = PP.UI.modal({
      title: `${pocket.name} QR Code`,
      subtitle: 'Scannable with any phone camera or Google Lens',
      icon: 'qr-code',
      iconClass: 'bg-accent',
      size: 'md'
    });
    
    const wrap = PP.el('div', { style: 'text-align:center;padding:1rem' });
    wrap.innerHTML = '<p style="color:var(--text-muted);font-size:0.9rem">Generating scannable QR code…</p>';
    modal.body.appendChild(wrap);

    try {
      const res = await PP.PocketsAPI.qr(pocket.id);
      const qrData = res?.data;
      if (qrData?.qr_code_url) {
        wrap.innerHTML = `
          <div style="background:white;padding:12px;display:inline-block;border-radius:18px;box-shadow:0 8px 30px rgba(0,0,0,0.3);margin-bottom:1rem">
            <img src="${qrData.qr_code_url}" alt="Pocket QR" style="width:220px;height:220px;display:block;border-radius:8px"/>
          </div>
          <h3 style="font-size:1.15rem;font-weight:800;margin:0 0 0.25rem;color:var(--text-primary)">${pocket.name}</h3>
          <p style="font-size:0.85rem;color:var(--text-muted);margin:0 0 1.25rem">Direct pocket destination link</p>
          <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:12px;padding:0.75rem;margin-bottom:1.25rem;font-family:var(--font-mono);font-size:0.78rem;word-break:break-all;color:var(--accent)">
            ${qrData.scannable_url}
          </div>
          <div style="display:flex;gap:0.75rem;justify-content:center">
            <button class="btn btn-outline" onclick="navigator.clipboard.writeText('${qrData.scannable_url}');PP.UI.toast('Link Copied','Pocket destination link copied to clipboard','success')">
              <i data-lucide="copy"></i> Copy Link
            </button>
            <button class="btn btn-primary" onclick="(() => {
              const link = document.createElement('a');
              link.href = '${qrData.qr_code_url}';
              link.download = 'pocketpay_pocket_${pocket.id}.png';
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
              PP.UI.toast('QR Downloaded', 'Pocket QR image saved', 'success');
            })()">
              <i data-lucide="download"></i> Save QR
            </button>
          </div>
        `;
        PP.refreshIcons();
      }
    } catch (err) {
      wrap.innerHTML = `<p style="color:var(--danger)">Failed to load QR code: ${err.message}</p>`;
    }
  },

  pocketActions(pocket) {
    const modal = PP.UI.modal({
      title: pocket.name,
      subtitle: 'Pocket Actions & Management',
      icon: pocket.icon || 'wallet',
      iconClass: 'bg-accent',
      size: 'sm'
    });

    const menu = PP.el('div', { style: 'display:flex;flex-direction:column;gap:0.6rem' });
    
    const items = [
      { label: 'Pocket QR Code', icon: 'qr-code', action: () => { modal.close(); PP.Modals.showPocketQR(pocket); } },
      { label: 'Deposit Money', icon: 'plus-circle', action: () => { modal.close(); PP.Modals.addIncomeForPocket(pocket.id); } },
      { label: 'Pay / Withdraw', icon: 'minus-circle', action: () => { modal.close(); PP.Modals.addExpenseForPocket(pocket.id); } },
      { label: 'Transfer to Another Pocket', icon: 'refresh-ccw', action: () => { modal.close(); PP.Modals.transfer({ fromPocketId: pocket.id }); } },
      { label: 'Edit Pocket Settings', icon: 'edit-3', action: () => { modal.close(); PP.Modals.editPocket(pocket); } },
      pocket.archived
        ? { label: 'Restore Pocket', icon: 'archive-restore', action: () => { modal.close(); PP.Modals.restorePocket(pocket); } }
        : { label: 'Archive Pocket', icon: 'archive', action: () => { modal.close(); PP.Modals.archivePocket(pocket); } },
      { label: 'Delete Pocket', icon: 'trash-2', danger: true, action: () => { modal.close(); PP.Modals.deletePocket(pocket); } }
    ];

    items.forEach(item => {
      const btn = PP.el('button', {
        class: `btn ${item.danger ? 'btn-danger' : 'btn-ghost'}`,
        style: 'justify-content:flex-start;width:100%;padding:0.75rem 1rem;font-weight:600',
        onclick: item.action
      }, [
        PP.el('i', { 'data-lucide': item.icon, style: 'margin-right:0.65rem' }),
        item.label
      ]);
      menu.appendChild(btn);
    });

    modal.body.appendChild(menu);
    PP.refreshIcons();
  },

  async saveDistributionRule(rule = null) {
    const editing = !!rule;
    const pockets = PP.state.pockets?.length ? PP.state.pockets : await PP.PocketsAPI.list({ per_page: 200 }).then(r => r.data.items).catch(() => []);
    let name = rule?.name || ''; let desc = rule?.description || ''; let ruleType = rule?.rule_type || 'percentage';
    let allocations = rule?.allocations ? rule.allocations.map(a => ({ ...a })) : [];
    const modal = PP.UI.modal({ title: editing ? 'Edit Rule' : 'Save Distribution Rule', subtitle: editing ? 'Update your allocation rule' : 'Create a reusable rule for quick income splits', icon: 'bookmark', iconClass: 'bg-accent', size: 'lg' });
    const renderBody = () => {
      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
      body.appendChild(PP.el('div', { class: 'form-row' }, [
        PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Rule Name *']),
          (() => { const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. Monthly Salary Split', value: name }); inp.oninput = () => name = inp.value; return inp; })(),
        ]),
        PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Allocation Type']),
          (() => {
            const s = PP.el('select', { class: 'form-select' });
            [['percentage', 'Percentage Split'], ['fixed', 'Fixed Amounts']].forEach(o => { const op = PP.el('option', { value: o[0] }, [o[1]]); if (ruleType === o[0]) op.selected = true; s.appendChild(op); });
            s.onchange = () => { ruleType = s.value; allocations = []; renderBody(); };
            return s;
          })(),
        ]),
      ]));
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Description (optional)']),
        (() => { const t = PP.el('textarea', { class: 'form-textarea', rows: 1 }); t.value = desc; t.oninput = () => desc = t.value; return t; })(),
      ]));
      let total = ruleType === 'percentage' ? allocations.reduce((s, a) => s + (a.percentage || 0), 0) : 0;
      body.appendChild(PP.el('div', { style: 'display:flex;justify-content:space-between;align-items:center;margin-bottom:.25rem' }, [
        PP.el('span', { class: 'form-label' }, ['Pocket Allocations']),
        ruleType === 'percentage' && PP.el('span', { class: 'font-semibold mono', style: `color:${Math.abs(total - 100) < .01 ? 'var(--success)' : 'var(--warning)'}` }, [`${total.toFixed(0)}% / 100%`]),
      ]));
      const list = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.4rem;max-height:320px;overflow:auto;padding:.25rem' });
      pockets.filter(p => !p.archived).forEach(p => {
        const curr = allocations.find(a => a.pocket_id == p.id);
        const r = PP.el('div', { style: 'display:grid;grid-template-columns:1fr 110px;gap:.5rem;align-items:center' }, [
          PP.el('div', { style: 'display:flex;align-items:center;gap:.5rem' }, [
            PP.el('div', { style: `width:30px;height:30px;border-radius:8px;background:${p.color};color:white;display:flex;align-items:center;justify-content:center;flex-shrink:0` }, [PP.el('i', { 'data-lucide': p.icon, style: 'width:14px;height:14px' })]),
            PP.el('span', { style: 'font-weight:500' }, [p.name]),
          ]),
        ]);
        const inp = PP.el('input', { class: 'form-input', type: 'number', min: '0', step: ruleType === 'percentage' ? '1' : '0.01', value: curr ? (ruleType === 'percentage' ? curr.percentage : curr.amount) : '', style: 'padding:.5rem;font-size:.85rem;text-align:right' });
        inp.oninput = () => {
          const v = parseFloat(inp.value);
          if (!v || v <= 0) allocations = allocations.filter(a => a.pocket_id != p.id);
          else { let rec = allocations.find(a => a.pocket_id == p.id); if (!rec) { rec = { pocket_id: p.id, pocket_name: p.name }; allocations.push(rec); } if (ruleType === 'percentage') rec.percentage = v; else rec.amount = v; }
          renderBody();
        };
        r.appendChild(inp); list.appendChild(r);
      });
      body.appendChild(list);
      modal.body.innerHTML = ''; modal.body.appendChild(body);
      modal.footer.innerHTML = ''; modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
      const saveBtn = PP.el('button', { class: 'btn btn-primary', onclick: async () => {
        if (!name.trim()) return PP.UI.toast('Name required', 'Enter a rule name', 'warning');
        if (!allocations.length) return PP.UI.toast('No allocations', 'Pick at least one pocket', 'warning');
        if (ruleType === 'percentage') { const t = allocations.reduce((s, a) => s + (a.percentage || 0), 0); if (Math.abs(t - 100) > .01) return PP.UI.toast('Must sum to 100%', `Current: ${t.toFixed(0)}%`, 'warning'); }
        try {
          saveBtn.disabled = true; saveBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Saving…'; PP.refreshIcons();
          const payload = { name: name.trim(), rule_type: ruleType, description: desc.trim() || null, allocations };
          const res = editing ? await PP.WalletAPI.updateRule(rule.id, payload) : await PP.WalletAPI.createRule(payload);
          PP.UI.toast('Rule saved', res.message || 'Rule has been stored', 'success'); modal.close(); PP.emit('rules:changed'); PP.refreshCurrentView();
        } catch (e) { PP.UI.toast('Save failed', e.message, 'error'); }
        finally { saveBtn.disabled = false; saveBtn.innerHTML = ['Save Rule']; }
      }}, ['Save Rule']);
      modal.footer.appendChild(saveBtn);
      PP.refreshIcons();
    };
    renderBody();
  },

  verifyEmail() {
    return PP.UI.prompt('Verify Email', 'Enter 6-digit OTP sent to your email').then(async otp => {
      if (!otp) return false;
      try { const res = await PP.Auth.verifyEmail(otp); PP.UI.toast('Email verified', res.message, 'success'); PP.state.user.email_verified = true; PP.refreshUserChrome(); return true; }
      catch (e) { PP.UI.toast('Verification failed', e.message, 'error'); return false; }
    });
  },

  verifyPhone() {
    if (!PP.state.user?.phone) {
      return PP.UI.prompt('Add Phone Number', 'Enter your phone number with country code').then(async phone => {
        if (!phone) return false;
        try {
          await PP.Auth.updateProfile({ phone });
          PP.state.user.phone = phone;
          PP.refreshUserChrome();
        } catch (e) { PP.UI.toast('Error', e.message, 'error'); return false; }
        return PP.Modals.verifyPhone();
      });
    }
    return PP.UI.prompt('Verify Phone', 'Enter 6-digit OTP sent to your phone').then(async otp => {
      if (!otp) return false;
      try {
        const res = await PP.Auth.verifyPhone(otp);
        PP.UI.toast('Phone verified', res.message, 'success');
        PP.state.user.phone_verified = true;
        PP.refreshUserChrome();
        return true;
      } catch (e) { PP.UI.toast('Verification failed', e.message, 'error'); return false; }
    });
  },

  changePin() {
    let step = 1; let oldPin = ''; let pin1 = ''; let pin2 = '';
    const modal = PP.UI.modal({ title: 'Change Transaction PIN', subtitle: 'Enter your current PIN and then a new 4-digit PIN', icon: 'lock', iconClass: 'bg-warning', size: 'sm' });
    const renderBody = () => {
      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem;align-items:center;padding:1rem 0' });
      body.appendChild(PP.el('div', { class: 'stepper', style: 'justify-content:center' },
        ['Current','New PIN','Confirm'].map((label, i) => {
          const n = i + 1;
          const s = PP.el('div', { class: `step ${step === n ? 'active' : step > n ? 'done' : ''}` }, [
            PP.el('div', { class: 'step-circle' }, [step > n ? PP.el('i', { 'data-lucide': 'check', style: 'width:14px;height:14px' }) : String(n)]),
            PP.el('div', { class: 'step-label' }, [label]),
          ]);
          if (n < 3) s.appendChild(PP.el('div', { class: 'step-line' }));
          return s;
        })
      ));
      const title = step === 1 ? 'Enter current PIN' : (step === 2 ? 'Create new 4-digit PIN' : 'Confirm new PIN');
      body.appendChild(PP.el('div', { class: 'form-label', style: 'font-weight:600;font-size:.9rem' }, [title]));
      const dots = PP.el('div', { class: 'pin-dots', style: 'display:flex;gap:.75rem;margin:.5rem 0 1rem' });
      const target = step === 1 ? 4 : (step === 2 ? 4 : 4);
      const enteredCur = step === 1 ? oldPin : (step === 2 ? pin1 : pin2);
      for (let i = 0; i < target; i++) dots.appendChild(PP.el('div', { class: 'pin-dot' + (enteredCur[i] ? ' filled' : ''), style: `width:14px;height:14px;border-radius:50%;border:2px solid ${enteredCur[i] ? 'var(--accent)' : 'var(--border-strong)'};background:${enteredCur[i] ? 'var(--accent)' : 'transparent'};transition:all .15s ease` }));
      body.appendChild(dots);
      const pad = PP.el('div', { class: 'pin-pad', style: 'display:grid;grid-template-columns:repeat(3,60px);gap:.5rem' });
      const set = (d) => {
        if (step === 1 && oldPin.length < 4) { oldPin += d; if (oldPin.length === 4) { setTimeout(() => { step = 2; renderBody(); }, 180); } }
        else if (step === 2 && pin1.length < 4) { pin1 += d; if (pin1.length === 4) { setTimeout(() => { step = 3; renderBody(); }, 180); } }
        else if (step === 3 && pin2.length < 4) { pin2 += d; if (pin2.length === 4) { setTimeout(async () => {
          if (pin1 !== pin2) { PP.UI.toast('PIN mismatch', 'PINs do not match, please try again', 'error'); pin1 = ''; pin2 = ''; step = 2; renderBody(); return; }
          try {
            const subBtn = modal.footer.querySelector('.btn-warning');
            if (subBtn) { subBtn.disabled = true; subBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i>…'; PP.refreshIcons(); }
            await PP.Auth.changePin(oldPin, pin1);
            PP.UI.toast('PIN changed', 'Your transaction PIN has been updated', 'success');
            modal.close();
            PP.state.user = (await PP.Auth.me()).data.user;
            PP.refreshUserChrome();
          } catch (e) { PP.UI.toast('Change PIN failed', e.message, 'error'); pin1 = ''; pin2 = ''; oldPin = ''; step = 1; renderBody(); }
          finally { const subBtn = modal.footer.querySelector('.btn-warning'); if (subBtn) { subBtn.disabled = false; subBtn.innerHTML = ['Change PIN']; } }
        }, 220); } }
        renderBody();
      };
      [1,2,3,4,5,6,7,8,9].forEach(d => pad.appendChild(PP.el('button', { class: 'btn btn-ghost', style: 'width:60px;height:60px;font-size:1.25rem;font-weight:700', onclick: () => set(String(d)) }, [String(d)])));
      pad.appendChild(PP.el('button', { class: 'btn btn-outline', style: 'width:60px;height:60px;font-weight:600', onclick: () => {
        if (step === 1 && oldPin.length > 0) oldPin = oldPin.slice(0, -1);
        else if (step === 2 && pin1.length > 0) pin1 = pin1.slice(0, -1);
        else if (step === 3 && pin2.length > 0) pin2 = pin2.slice(0, -1);
        renderBody();
      } }, [PP.el('i', { 'data-lucide': 'delete', style: 'width:18px;height:18px' })]));
      pad.appendChild(PP.el('button', { class: 'btn btn-ghost', style: 'width:60px;height:60px;font-size:1.25rem;font-weight:700', onclick: () => set('0') }, ['0']));
      pad.appendChild(PP.el('button', { class: 'btn btn-outline', style: 'width:60px;height:60px;font-weight:600;color:var(--danger)', onclick: () => modal.close() }, [PP.el('i', { 'data-lucide': 'x', style: 'width:18px;height:18px' })]));
      body.appendChild(pad);
      modal.body.innerHTML = ''; modal.body.appendChild(body);
      modal.footer.innerHTML = '';
      if (step > 1) modal.footer.appendChild(PP.el('button', { class: 'btn btn-outline', onclick: () => { if (step === 3) pin2 = ''; else if (step === 2) pin1 = ''; step--; renderBody(); } }, ['Back']));
      modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
      const go = PP.el('button', { class: 'btn btn-warning', onclick: async () => {
        if (step === 1 && oldPin.length === 4) { step = 2; renderBody(); }
        else if (step === 2 && pin1.length === 4) { step = 3; renderBody(); }
        else if (step === 3 && pin2.length === 4) {
          if (pin1 !== pin2) { PP.UI.toast('PIN mismatch', 'PINs do not match', 'error'); pin1 = ''; pin2 = ''; step = 2; renderBody(); return; }
          try {
            go.disabled = true; go.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i>…'; PP.refreshIcons();
            await PP.Auth.changePin(oldPin, pin1);
            PP.UI.toast('PIN changed', 'PIN updated successfully', 'success'); modal.close();
            PP.state.user = (await PP.Auth.me()).data.user; PP.refreshUserChrome();
          } catch (e) { PP.UI.toast('Change PIN failed', e.message, 'error'); pin1 = ''; pin2 = ''; oldPin = ''; step = 1; renderBody(); }
          finally { go.disabled = false; go.innerHTML = ['Change PIN']; }
        } else PP.UI.toast('Enter PIN', 'Please enter a full 4-digit PIN', 'warning');
      } }, ['Change PIN']);
      modal.footer.appendChild(go);
      PP.refreshIcons();
    };
    renderBody();
  },

  changePassword() {
    const modal = PP.UI.modal({ title: 'Change Password', subtitle: 'Update your account password', icon: 'key-round', iconClass: 'bg-info', size: 'md' });
    const body = PP.el('form', { class: 'auth-form', style: 'display:flex;flex-direction:column;gap:1rem', onsubmit: async (e) => {
      e.preventDefault();
      const fd = new FormData(body);
      const old = fd.get('old_password') || '';
      const np = fd.get('new_password') || '';
      const cp = fd.get('confirm_password') || '';
      if (!old || !np || np.length < 8) return PP.UI.toast('Invalid password', 'New password must be at least 8 characters', 'warning');
      if (np !== cp) return PP.UI.toast('Mismatch', 'New passwords do not match', 'warning');
      const sub = modal.footer.querySelector('.btn-primary');
      try {
        sub.disabled = true; sub.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Updating…'; PP.refreshIcons();
        await PP.Auth.updateProfile({ old_password: old, password: np });
        PP.UI.toast('Password changed', 'Your password has been updated', 'success');
        modal.close();
      } catch (e) { PP.UI.toast('Change failed', e.message, 'error'); }
      finally { sub.disabled = false; sub.innerHTML = ['Update Password']; }
    } });
    body.innerHTML = `
      <div class="form-group"><label class="form-label">Current Password</label><input class="form-input" name="old_password" type="password" placeholder="••••••••" required /></div>
      <div class="form-group"><label class="form-label">New Password (min 8 chars)</label><input class="form-input" name="new_password" type="password" minlength="8" placeholder="••••••••" required /></div>
      <div class="form-group"><label class="form-label">Confirm New Password</label><input class="form-input" name="confirm_password" type="password" minlength="8" placeholder="••••••••" required /></div>`;
    modal.body.innerHTML = ''; modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', type: 'button', onclick: () => modal.close() }, ['Cancel']));
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-primary', type: 'submit', form: body.getAttribute('class')?.includes('auth-form') ? null : null }, ['Update Password']));
    const sb = modal.footer.querySelector('.btn-primary'); sb.onclick = () => body.requestSubmit();
    PP.refreshIcons();
  },

  pocketActions(pocket) {
    if (!pocket) return;
    const modal = PP.UI.modal({ title: pocket.name, subtitle: `Balance: ${PP.fmt(pocket.current_balance)}`, icon: pocket.icon || 'wallet', iconClass: 'bg-accent', size: 'sm' });
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.5rem' });
    const makeBtn = (label, icon, cls, fn, danger = false) => PP.el('button', { class: `btn ${cls}`, style: 'justify-content:flex-start;gap:.75rem;padding:.85rem 1rem', onclick: async () => {
      try { await fn(); modal.close(); } catch {}
    } }, [PP.el('i', { 'data-lucide': icon, style: 'width:16px;height:16px' }), label]);
    body.appendChild(makeBtn('Edit Pocket', 'pencil', 'btn-outline', () => PP.Modals.createPocket(pocket)));
    body.appendChild(makeBtn('Deposit Money', 'arrow-down-left', 'btn-outline', () => PP.Modals.addIncomeForPocket(pocket.id)));
    body.appendChild(makeBtn('Pay / Expense', 'arrow-up-right', 'btn-outline', () => PP.Modals.addExpenseForPocket(pocket.id)));
    body.appendChild(makeBtn('Transfer to Another Pocket', 'refresh-ccw', 'btn-outline', () => PP.Modals.transfer({ fromPocketId: pocket.id })));
    if (!pocket.archived) body.appendChild(makeBtn('Archive Pocket', 'archive', 'btn-outline btn-warning', () => PP.Modals.archivePocket(pocket)));
    else body.appendChild(makeBtn('Restore Pocket', 'archive-restore', 'btn-outline btn-success', () => PP.Modals.restorePocket(pocket)));
    body.appendChild(makeBtn('Delete Pocket', 'trash-2', 'btn-outline btn-danger', () => PP.Modals.deletePocket(pocket), true));
    modal.body.innerHTML = ''; modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Close']));
    PP.refreshIcons();
  },

  addIncomeForPocket(pocketId) {
    return PP.Modals.addIncome({ singlePocketId: pocketId, strategy: 'single' });
  },

  addExpenseForPocket(pocketId) {
    return PP.Modals.addExpense(pocketId);
  },

  createBudget(existing = null) {
    const editing = !!existing;
    const pockets = PP.state.pockets?.length ? PP.state.pockets : [];
    let name = existing?.name || '';
    let limit = existing?.limit_amount || 0;
    let category = existing?.category || '';
    let pocket_id = existing?.pocket_id || '';
    let period = existing?.period || 'monthly';
    const modal = PP.UI.modal({ title: editing ? 'Edit Budget' : 'Create Budget', subtitle: editing ? 'Update your budget' : 'Set a spending limit to stay on track', icon: 'target', iconClass: 'bg-info', size: 'md' });
    const renderBody = () => {
      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
      body.appendChild(PP.el('div', { class: 'form-row' }, [
        PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Budget Name *']),
          (() => { const i = PP.el('input', { class: 'form-input', placeholder: 'e.g. Grocery Budget', value: name }); i.oninput = () => name = i.value; return i; })(),
        ]),
        PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Period']),
          (() => {
            const s = PP.el('select', { class: 'form-select' });
            [['weekly','Weekly'],['monthly','Monthly'],['quarterly','Quarterly'],['yearly','Yearly']].forEach(o => {
              const op = PP.el('option', { value: o[0] }, [o[1]]); if (period === o[0]) op.selected = true; s.appendChild(op);
            });
            s.onchange = () => period = s.value; return s;
          })(),
        ]),
      ]));
      body.appendChild(PP.el('div', { class: 'form-row' }, [
        PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Limit Amount *']),
          (() => { const i = PP.el('input', { class: 'form-input', type: 'number', min: '1', step: '1', placeholder: '0', value: limit || '' }); i.oninput = () => limit = parseFloat(i.value) || 0; return i; })(),
        ]),
        PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Apply to Pocket (optional)']),
          (() => {
            const s = PP.el('select', { class: 'form-select' });
            s.appendChild(PP.el('option', { value: '' }, ['— All pockets —']));
            pockets.filter(p => !p.archived).forEach(p => { const op = PP.el('option', { value: p.id }, [`${p.name} (${PP.fmt(p.current_balance)})`]); if (pocket_id == p.id) op.selected = true; s.appendChild(op); });
            s.onchange = () => pocket_id = s.value ? parseInt(s.value) : ''; return s;
          })(),
        ]),
      ]));
      const cats = PP.state.categories?.length ? PP.state.categories : ['Food & Dining','Shopping','Transportation','Entertainment','Bills & Utilities','Healthcare','Education','Travel','Other'];
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Category (optional, leave blank for all)']),
        (() => {
          const s = PP.el('select', { class: 'form-select' });
          s.appendChild(PP.el('option', { value: '' }, ['— All categories —']));
          cats.forEach(c => { const op = PP.el('option', { value: c }, [c]); if (category === c) op.selected = true; s.appendChild(op); });
          s.onchange = () => category = s.value; return s;
        })(),
      ]));
      modal.body.innerHTML = ''; modal.body.appendChild(body);
      modal.footer.innerHTML = '';
      modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
      const save = PP.el('button', { class: 'btn btn-primary', onclick: async () => {
        if (!name.trim()) return PP.UI.toast('Name required', 'Please enter a budget name', 'warning');
        if (!(limit > 0)) return PP.UI.toast('Invalid limit', 'Please enter a valid limit amount', 'warning');
        try {
          save.disabled = true; save.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Saving…'; PP.refreshIcons();
          let startDate, endDate;
          if (editing && existing?.start_date && existing?.end_date) {
            startDate = existing.start_date;
            endDate = existing.end_date;
          } else {
            const today = new Date();
            const end = new Date(today);
            if (period === 'weekly') end.setDate(today.getDate() + 7);
            else if (period === 'quarterly') end.setMonth(today.getMonth() + 3);
            else if (period === 'yearly') end.setFullYear(today.getFullYear() + 1);
            else end.setMonth(today.getMonth() + 1);
            startDate = today.toISOString().split('T')[0];
            endDate = end.toISOString().split('T')[0];
          }
          const payload = {
            name: name.trim(), limit_amount: Number(limit), period,
            category: category || null, pocket_id: pocket_id || null,
            start_date: startDate, end_date: endDate, is_active: true, repeat: true,
          };
          if (editing) await PP.AnalyticsAPI.updateBudget(existing.id, payload);
          else await PP.AnalyticsAPI.createBudget(payload);
          PP.UI.toast('Budget saved', editing ? 'Budget has been updated' : 'Budget has been created', 'success');
          modal.close(); PP.refreshCurrentView();
        } catch (e) { PP.UI.toast('Save failed', e.message, 'error'); }
        finally { save.disabled = false; save.innerHTML = [editing ? 'Update Budget' : 'Create Budget']; }
      }}, [editing ? 'Update Budget' : 'Create Budget']);
      modal.footer.appendChild(save);
      PP.refreshIcons();
    };
    renderBody();
  },

  transactionDetail(tx) {
    if (!tx) return;
    const modal = PP.UI.modal({ title: 'Transaction Details', subtitle: `Transaction #${tx.transaction_id || tx.id}`, icon: 'receipt', iconClass: 'bg-accent', size: 'md' });
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.75rem' });
    const isExp = tx.type === 'expense' || tx.amount < 0;
    const color = isExp ? 'var(--danger)' : (tx.type === 'income' || tx.type === 'topup' ? 'var(--success)' : 'var(--accent)');
    body.appendChild(PP.el('div', { class: 'glass-card', style: `padding:1.5rem;text-align:center;border:1px solid ${color}33` }, [
      PP.el('div', { style: `font-size:.8rem;text-transform:uppercase;letter-spacing:.1em;font-weight:700;color:${color};margin-bottom:.5rem` }, [tx.type || 'Transaction']),
      PP.el('div', { style: `font-family:var(--font-display);font-size:2.25rem;font-weight:900;color:${color}` }, [
        `${isExp ? '-' : '+'}${PP.fmt(Math.abs(tx.amount || 0))}`,
      ]),
      tx.status && PP.el('div', { class: `chip ${tx.status === 'completed' ? 'success' : 'warning'}`, style: 'margin-top:.5rem' }, [tx.status.toUpperCase()]),
    ]));
    const row = (k, v, copy = false) => PP.el('div', { class: 'setting-row', style: 'display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:.65rem 0;border-bottom:1px solid var(--border)' }, [
      PP.el('span', { class: 'text-muted', style: 'font-size:.85rem;font-weight:500' }, [k]),
      PP.el('div', { style: 'display:flex;align-items:center;gap:.4rem' }, [
        PP.el('span', { style: 'font-weight:600;font-size:.9rem' }, [v || '—']),
        copy && PP.el('button', { class: 'btn-icon-sm btn btn-ghost', style: 'padding:0;width:28px;height:28px', onclick: () => { navigator.clipboard?.writeText(v); PP.UI.toast('Copied', k + ' copied', 'success'); } }, [PP.el('i', { 'data-lucide': 'copy', style: 'width:13px;height:13px' })]),
      ]),
    ]);
    body.appendChild(row('Date & Time', PP.formatDateTime(tx.created_at || tx.date)));
    body.appendChild(row('Category', tx.category || '—'));
    if (tx.merchant) body.appendChild(row('Merchant', tx.merchant));
    if (tx.from_pocket_name || tx.from_pocket_id) body.appendChild(row('From', tx.from_pocket_name || `Pocket #${tx.from_pocket_id}`));
    if (tx.to_pocket_name || tx.to_pocket_id) body.appendChild(row('To', tx.to_pocket_name || `Pocket #${tx.to_pocket_id}`));
    if (tx.payment_method) body.appendChild(row('Method', tx.payment_method));
    if (tx.description || tx.notes) body.appendChild(row('Notes', tx.description || tx.notes));
    body.appendChild(row('Transaction ID', tx.transaction_id || tx.id, true));
    modal.body.innerHTML = ''; modal.body.appendChild(body);
    modal.footer.innerHTML = '';

    // Edit button
    const editBtn = PP.el('button', {
      class: 'btn btn-outline',
      onclick: () => {
        modal.close();
        PP.Modals.editTransaction(tx);
      }
    }, [PP.el('i', { 'data-lucide': 'edit-3', style: 'width:15px;height:15px' }), 'Edit']);
    modal.footer.appendChild(editBtn);

    // Delete button
    const delBtn = PP.el('button', {
      class: 'btn btn-outline text-danger',
      onclick: async () => {
        const ok = await PP.UI.confirm(
          'Delete Transaction',
          `Are you sure you want to delete transaction #${tx.transaction_id || tx.id}? Pocket balances will be automatically adjusted.`
        );
        if (!ok) return;
        try {
          delBtn.disabled = true;
          delBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i>…';
          PP.refreshIcons();
          await PP.TxAPI.delete(tx.id);
          PP.UI.toast('Deleted', 'Transaction has been deleted and balances adjusted', 'success');
          modal.close();
          PP.refreshCurrentView();
        } catch (e) {
          PP.UI.toast('Delete failed', e.message, 'error');
        } finally {
          delBtn.disabled = false;
          delBtn.innerHTML = [PP.el('i', { 'data-lucide': 'trash-2', style: 'width:15px;height:15px' }), 'Delete'];
        }
      }
    }, [PP.el('i', { 'data-lucide': 'trash-2', style: 'width:15px;height:15px' }), 'Delete']);
    modal.footer.appendChild(delBtn);

    if (tx.status === 'completed' && (tx.type === 'expense' || tx.type === 'transfer')) {
      const refBtn = PP.el('button', { class: 'btn btn-outline', onclick: async () => {
        try {
          const pin = await PP.UI.pinPrompt({ title: 'Confirm Refund', subtitle: 'Enter transaction PIN to proceed' });
          if (!pin) return;
          refBtn.disabled = true; refBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i>…'; PP.refreshIcons();
          await PP.TxAPI.refund(tx.id, pin);
          PP.UI.toast('Refunded', 'Transaction has been refunded', 'success');
          modal.close(); PP.refreshCurrentView();
        } catch (e) { PP.UI.toast('Refund failed', e.message, 'error'); }
        finally { refBtn.disabled = false; refBtn.innerHTML = [PP.el('i', { 'data-lucide': 'undo-2', style: 'width:16px;height:16px' }), 'Refund']; }
      }}, [PP.el('i', { 'data-lucide': 'undo-2', style: 'width:16px;height:16px' }), 'Refund']);
      modal.footer.appendChild(refBtn);
    }
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Close']));
    PP.refreshIcons();
  },

  editTransaction(tx) {
    if (!tx) return;
    const modal = PP.UI.modal({
      title: 'Edit Transaction',
      subtitle: `Transaction #${tx.transaction_id || tx.id}`,
      icon: 'edit-3',
      iconClass: 'bg-accent',
      size: 'md'
    });
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
    const categories = [
      'Food & Dining', 'Groceries', 'Shopping', 'Bills & Utilities', 'Entertainment',
      'Travel & Transport', 'Health & Fitness', 'Education', 'Investments', 'Personal Care',
      'Gifts & Donations', 'Business', 'Salary', 'Freelance', 'General'
    ];
    
    body.innerHTML = `
      <div class="form-group">
        <label class="form-label">Category</label>
        <select class="form-select" id="editTxCategory">
          ${categories.map(c => `<option value="${c}" ${c === tx.category ? 'selected' : ''}>${c}</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Merchant / Payee</label>
        <input class="form-input" id="editTxMerchant" type="text" value="${tx.merchant || ''}" placeholder="e.g. Swiggy, Amazon" />
      </div>
      <div class="form-group">
        <label class="form-label">Description / Note</label>
        <textarea class="form-textarea" id="editTxDesc" rows="2" placeholder="Add details...">${tx.description || ''}</textarea>
      </div>
    `;
    modal.body.innerHTML = '';
    modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    
    const saveBtn = PP.el('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        const cat = PP.$('#editTxCategory', modal.body)?.value;
        const merchant = PP.$('#editTxMerchant', modal.body)?.value?.trim();
        const desc = PP.$('#editTxDesc', modal.body)?.value?.trim();
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Saving…';
        PP.refreshIcons();
        try {
          await PP.TxAPI.update(tx.id, {
            category: cat,
            merchant: merchant || null,
            description: desc || null
          });
          PP.UI.toast('Updated', 'Transaction updated successfully', 'success');
          modal.close();
          PP.refreshCurrentView();
        } catch (e) {
          PP.UI.toast('Update Failed', e.message, 'error');
        } finally {
          saveBtn.disabled = false;
          saveBtn.innerHTML = 'Save Changes';
        }
      }
    }, ['Save Changes']);
    
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
    modal.footer.appendChild(saveBtn);
    PP.refreshIcons();
  },

  reorderPockets() {
    const pockets = (PP.state.pockets || []).filter(p => !p.archived).slice().sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0));
    if (!pockets.length) return PP.UI.toast('Nothing to sort', 'Create some pockets first', 'info');
    const modal = PP.UI.modal({ title: 'Reorder Pockets', subtitle: 'Drag and drop to reorder', icon: 'arrow-up-down', iconClass: 'bg-accent', size: 'md' });
    let order = pockets.map(p => p.id);
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.5rem;max-height:50vh;overflow:auto;padding:.25rem' });
    const render = () => {
      body.innerHTML = '';
      order.forEach((pid, idx) => {
        const p = pockets.find(pp => pp.id === pid) || {};
        const row = PP.el('div', { class: 'glass-card', draggable: 'true', style: `padding:.75rem 1rem;display:flex;align-items:center;gap:.75rem;cursor:grab;border-left:4px solid ${p.color || 'var(--accent)'}` }, [
          PP.el('i', { 'data-lucide': 'grip-vertical', style: 'color:var(--text-dim);cursor:grab' }),
          PP.el('div', { style: `width:32px;height:32px;border-radius:8px;background:${p.color || '#6366f1'};color:white;display:flex;align-items:center;justify-content:center;flex-shrink:0` }, [PP.el('i', { 'data-lucide': p.icon || 'wallet', style: 'width:14px;height:14px' })]),
          PP.el('span', { style: 'font-weight:600;flex:1' }, [p.name || `Pocket ${pid}`]),
          PP.el('span', { class: 'text-dim', style: 'font-family:var(--font-mono);font-size:.8rem' }, [`#${idx + 1}`]),
        ]);
        row.addEventListener('dragstart', (e) => { row.style.opacity = '.5'; e.dataTransfer.setData('text/plain', String(pid)); e.dataTransfer.effectAllowed = 'move'; });
        row.addEventListener('dragend', () => { row.style.opacity = '1'; });
        row.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; row.style.background = 'var(--hover-bg)'; });
        row.addEventListener('dragleave', () => { row.style.background = ''; });
        row.addEventListener('drop', (e) => {
          e.preventDefault(); row.style.background = '';
          const draggedId = parseInt(e.dataTransfer.getData('text/plain'));
          if (isNaN(draggedId) || draggedId === pid) return;
          const from = order.indexOf(draggedId); const to = order.indexOf(pid);
          if (from < 0 || to < 0) return;
          order.splice(from, 1); order.splice(to, 0, draggedId);
          render();
        });
        body.appendChild(row);
      });
      PP.refreshIcons();
    };
    render();
    modal.body.innerHTML = ''; modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
    const saveBtn = PP.el('button', { class: 'btn btn-primary', onclick: async () => {
      try {
        saveBtn.disabled = true; saveBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Saving…'; PP.refreshIcons();
        await PP.PocketsAPI.reorder(order);
        PP.UI.toast('Saved', 'Pocket order updated', 'success');
        modal.close(); PP.refreshCurrentView();
      } catch (e) { PP.UI.toast('Save failed', e.message, 'error'); }
      finally { saveBtn.disabled = false; saveBtn.innerHTML = ['Save Order']; }
    }}, ['Save Order']);
    modal.footer.appendChild(saveBtn);
    PP.refreshIcons();
  },

  linkBankAccount() {
    let bankName = 'HDFC Bank';
    let accountHolder = PP.state.user?.full_name || '';
    let accountNumber = '';
    let ifscCode = '';

    const modal = PP.UI.modal({
      title: 'Connect Bank Account',
      subtitle: 'Safe Sandbox Mode: Connect an account to auto-categorize deposits',
      icon: 'building-2',
      iconClass: 'bg-info',
      size: 'md'
    });

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });

    body.appendChild(PP.el('div', {
      class: 'glass-card',
      style: 'padding:.85rem 1rem;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);border-radius:var(--radius-md);display:flex;align-items:flex-start;gap:.75rem'
    }, [
      PP.el('i', { 'data-lucide': 'shield-check', style: 'width:20px;height:20px;color:var(--success);flex-shrink:0;margin-top:2px' }),
      PP.el('div', { style: 'font-size:.8rem;color:var(--text-muted);line-height:1.4' }, [
        PP.el('strong', { style: 'color:var(--success);display:block;margin-bottom:2px' }, ['Bank-Grade Privacy & Security']),
        'PocketPay will never ask for or store your real ATM PIN, debit card PIN, or net-banking password. All connections are securely tokenized.'
      ])
    ]));

    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Select Bank *']),
      (() => {
        const sel = PP.el('select', { class: 'form-select' });
        ['HDFC Bank', 'State Bank of India (SBI)', 'ICICI Bank', 'Axis Bank', 'Kotak Mahindra Bank', 'Punjab National Bank'].forEach(b => {
          const opt = PP.el('option', { value: b }, [b]);
          sel.appendChild(opt);
        });
        sel.onchange = () => bankName = sel.value;
        return sel;
      })(),
    ]));

    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Account Holder Name *']),
      (() => {
        const inp = PP.el('input', { class: 'form-input', value: accountHolder, placeholder: 'e.g. Arjun Sharma' });
        inp.oninput = () => accountHolder = inp.value;
        return inp;
      })(),
    ]));

    body.appendChild(PP.el('div', { class: 'form-row' }, [
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Account Number / ID *']),
        (() => {
          const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. 501004928192', maxlength: '18' });
          inp.oninput = () => accountNumber = inp.value;
          return inp;
        })(),
      ]),
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['IFSC Code (optional)']),
        (() => {
          const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. HDFC0001234', maxlength: '11' });
          inp.oninput = () => ifscCode = inp.value.toUpperCase();
          return inp;
        })(),
      ]),
    ]));

    modal.body.innerHTML = '';
    modal.body.appendChild(body);

    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
    const linkBtn = PP.el('button', { class: 'btn btn-primary', onclick: async () => {
      if (!accountHolder.trim()) return PP.UI.toast('Name Required', 'Enter account holder name', 'warning');
      if (!accountNumber.trim() || accountNumber.trim().length < 4) return PP.UI.toast('Account Number Required', 'Enter a valid account number', 'warning');

      try {
        linkBtn.disabled = true; linkBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Connecting…';
        PP.refreshIcons();
        const res = await PP.Auth.linkBankAccount({
          bank_name: bankName,
          account_holder: accountHolder.trim(),
          account_number: accountNumber.trim(),
          ifsc_code: ifscCode.trim()
        });
        modal.close();
        PP.UI.showSuccess({
          title: 'Bank Account Linked',
          subtitle: `${bankName} account (${res?.data?.bank?.account_mask || '••••'}) connected successfully in Sandbox Mode.`,
          meta: { 'Bank': bankName, 'Account Holder': accountHolder, 'Mode': 'Sandbox / Dev' }
        });
        if (PP.state.user) {
          PP.state.user.linked_banks = res?.data?.linked_banks || [];
        }
        PP.refreshCurrentView();
      } catch (e) {
        PP.UI.toast('Connection Failed', e.message, 'error');
      } finally {
        linkBtn.disabled = false;
        linkBtn.innerHTML = ['Connect Bank Account'];
      }
    }}, ['Connect Bank Account']);
    modal.footer.appendChild(linkBtn);
    PP.refreshIcons();
  },

  addMoneyToPocket(pocket) {
    const modal = PP.UI.modal({
      title: `Add Money to ${pocket.name}`,
      subtitle: `Allocate funds from your available balance to this pocket`,
      icon: 'plus-circle',
      iconClass: 'bg-success',
      size: 'sm'
    });
    let amount = 0;
    let desc = '';
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.25rem' });
    
    // Show current balances
    const balWrap = PP.el('div', { class: 'glass-card', style: 'padding:14px 18px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:14px;display:flex;justify-content:space-between;align-items:center' }, [
      PP.el('div', {}, [
        PP.el('div', { style: 'font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em' }, ['Available Balance']),
        PP.el('div', { style: 'font-size:1.15rem;font-weight:700;color:var(--success)' }, [PP.fmt(PP.state.user?.wallet_balance || 0)])
      ]),
      PP.el('div', { style: 'text-align:right' }, [
        PP.el('div', { style: 'font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em' }, [`${pocket.name} Balance`]),
        PP.el('div', { style: 'font-size:1.15rem;font-weight:700;color:var(--text)' }, [PP.fmt(pocket.current_balance || 0)])
      ])
    ]);
    body.appendChild(balWrap);

    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Amount to Allocate (₹) *']),
      (() => {
        const inp = PP.el('input', { class: 'form-input', type: 'number', min: '1', step: '0.01', placeholder: 'e.g. 2000', autofocus: true });
        inp.oninput = () => amount = parseFloat(inp.value) || 0;
        return inp;
      })()
    ]));

    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Note (optional)']),
      (() => {
        const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. Extra savings' });
        inp.oninput = () => desc = inp.value.trim();
        return inp;
      })()
    ]));

    modal.body.innerHTML = '';
    modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
    
    const saveBtn = PP.el('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        if (!(amount > 0)) return PP.UI.toast('Invalid Amount', 'Please enter a positive amount', 'warning');
        if (amount > (PP.state.user?.wallet_balance || 0)) {
          return PP.UI.toast('Insufficient Balance', `You only have ${PP.fmt(PP.state.user?.wallet_balance || 0)} available.`, 'warning');
        }
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Allocating…';
        PP.refreshIcons();
        try {
          const res = await PP.PocketsAPI.addMoney(pocket.id, amount, desc);
          PP.UI.toast('Funds Allocated', res.message || `₹${amount.toLocaleString('en-IN')} added to ${pocket.name}`, 'success');
          modal.close();
          if (PP.state.user) PP.state.user.wallet_balance = res?.data?.wallet_balance ?? PP.state.user.wallet_balance;
          PP.emit('pockets:changed');
          PP.refreshCurrentView();
        } catch (e) {
          PP.UI.toast('Allocation Failed', e.message, 'error');
        } finally {
          saveBtn.disabled = false;
          saveBtn.innerHTML = 'Add to Pocket';
        }
      }
    }, ['Add to Pocket']);
    modal.footer.appendChild(saveBtn);
    PP.refreshIcons();
  },

  withdrawFromPocket(pocket) {
    const modal = PP.UI.modal({
      title: `Withdraw from ${pocket.name}`,
      subtitle: `Move funds from ${pocket.name} back to your available balance`,
      icon: 'arrow-down-left',
      iconClass: 'bg-warning',
      size: 'sm'
    });
    let amount = 0;
    let desc = '';
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.25rem' });
    
    const balWrap = PP.el('div', { class: 'glass-card', style: 'padding:14px 18px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:14px;display:flex;justify-content:space-between;align-items:center' }, [
      PP.el('div', {}, [
        PP.el('div', { style: 'font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em' }, [`${pocket.name} Balance`]),
        PP.el('div', { style: 'font-size:1.15rem;font-weight:700;color:var(--warning)' }, [PP.fmt(pocket.current_balance || 0)])
      ]),
      PP.el('div', { style: 'text-align:right' }, [
        PP.el('div', { style: 'font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em' }, ['Available Balance']),
        PP.el('div', { style: 'font-size:1.15rem;font-weight:700;color:var(--text)' }, [PP.fmt(PP.state.user?.wallet_balance || 0)])
      ])
    ]);
    body.appendChild(balWrap);

    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Amount to Withdraw (₹) *']),
      (() => {
        const inp = PP.el('input', { class: 'form-input', type: 'number', min: '1', max: pocket.current_balance, step: '0.01', placeholder: `Max ${pocket.current_balance}`, autofocus: true });
        inp.oninput = () => amount = parseFloat(inp.value) || 0;
        return inp;
      })()
    ]));

    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Note (optional)']),
      (() => {
        const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. Freeing up funds' });
        inp.oninput = () => desc = inp.value.trim();
        return inp;
      })()
    ]));

    modal.body.innerHTML = '';
    modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
    
    const saveBtn = PP.el('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        if (!(amount > 0)) return PP.UI.toast('Invalid Amount', 'Please enter a positive amount', 'warning');
        if (amount > pocket.current_balance) {
          return PP.UI.toast('Exceeds Pocket Balance', `This pocket only has ${PP.fmt(pocket.current_balance)}.`, 'warning');
        }
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Withdrawing…';
        PP.refreshIcons();
        try {
          const res = await PP.PocketsAPI.withdrawMoney(pocket.id, amount, desc);
          PP.UI.toast('Funds Withdrawn', res.message || `₹${amount.toLocaleString('en-IN')} returned to available balance`, 'success');
          modal.close();
          if (PP.state.user) PP.state.user.wallet_balance = res?.data?.wallet_balance ?? PP.state.user.wallet_balance;
          PP.emit('pockets:changed');
          PP.refreshCurrentView();
        } catch (e) {
          PP.UI.toast('Withdrawal Failed', e.message, 'error');
        } finally {
          saveBtn.disabled = false;
          saveBtn.innerHTML = 'Withdraw to Available';
        }
      }
    }, ['Withdraw to Available']);
    modal.footer.appendChild(saveBtn);
    PP.refreshIcons();
  },

  pocketActions(pocket) {
    const modal = PP.UI.modal({
      title: pocket.name,
      subtitle: `Balance: ${PP.fmt(pocket.current_balance)}`,
      icon: pocket.icon || 'wallet',
      iconClass: 'bg-accent',
      size: 'sm'
    });
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.6rem' });
    const items = [
      { label: 'Add Money / Allocate', sub: 'Move funds from available balance to this pocket', icon: 'plus-circle', color: 'var(--success)', fn: () => { modal.close(); PP.Modals.addMoneyToPocket(pocket); } },
      { label: 'Withdraw to Available', sub: 'Move money back into unallocated balance', icon: 'arrow-down-left', color: 'var(--warning)', fn: () => { modal.close(); PP.Modals.withdrawFromPocket(pocket); } },
      { label: 'Transfer to Another Pocket', sub: 'Move funds directly between pockets', icon: 'refresh-ccw', color: 'var(--accent)', fn: () => { modal.close(); PP.Modals.transfer({ fromPocketId: pocket.id }); } },
      { label: 'Edit Pocket Details', sub: 'Change name, budget, icon, or color', icon: 'pencil', color: 'var(--text-muted)', fn: () => { modal.close(); PP.Modals.createPocket(pocket); } },
      { label: 'Delete Pocket', sub: 'Remove pocket (returns funds if remaining)', icon: 'trash-2', color: 'var(--danger)', fn: () => { modal.close(); PP.Modals.deletePocket(pocket); } },
    ];
    items.forEach(it => {
      body.appendChild(PP.el('button', {
        class: 'btn btn-outline',
        style: 'justify-content:flex-start;padding:.8rem 1rem;gap:.9rem;text-align:left;width:100%',
        onclick: it.fn
      }, [
        PP.el('div', { style: `width:34px;height:34px;border-radius:10px;background:rgba(255,255,255,.06);display:flex;align-items:center;justify-content:center;color:${it.color};flex-shrink:0` }, [
          PP.el('i', { 'data-lucide': it.icon, style: 'width:17px;height:17px' })
        ]),
        PP.el('div', { style: 'flex:1;min-width:0' }, [
          PP.el('div', { style: 'font-weight:600;font-size:.88rem;color:var(--text)' }, [it.label]),
          PP.el('div', { style: 'font-size:.72rem;color:var(--text-muted);margin-top:2px' }, [it.sub])
        ]),
        PP.el('i', { 'data-lucide': 'chevron-right', style: 'width:15px;height:15px;color:var(--text-dim)' })
      ]));
    });
    modal.body.innerHTML = '';
    modal.body.appendChild(body);
    PP.refreshIcons();
  },

  deleteAccountModal() {
    const modal = PP.UI.modal({
      title: 'Delete Account',
      subtitle: 'Permanently close and deactivate your PocketPay account',
      icon: 'alert-triangle',
      iconClass: 'bg-danger',
      size: 'md'
    });
    
    const u = PP.state.user || {};
    const walletBal = u.wallet_balance || 0;
    const pocketBal = u.total_pocket_balance || 0;
    const totalRemaining = walletBal + pocketBal;
    const isEligible = totalRemaining === 0;

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.25rem' });

    body.appendChild(PP.el('div', { class: 'glass-card', style: 'padding:16px 20px;background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.2);border-radius:16px;' }, [
      PP.el('div', { style: 'display:flex;align-items:center;gap:10px;margin-bottom:8px' }, [
        PP.el('i', { 'data-lucide': 'shield-alert', style: 'color:var(--danger);width:22px;height:22px' }),
        PP.el('h4', { style: 'margin:0;color:#fff;font-size:0.95rem;font-weight:700' }, ['Account Deletion Requirements'])
      ]),
      PP.el('p', { style: 'margin:0;color:var(--text-muted);font-size:0.83rem;line-height:1.5' }, [
        'To ensure no funds are lost, PocketPay requires all pocket allocations and available balance to be exactly ₹0 before an account can be deleted.'
      ])
    ]));

    // Checklist
    const checklist = PP.el('div', { class: 'glass-card', style: 'padding:16px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.08);border-radius:14px;display:flex;flex-direction:column;gap:10px' }, [
      PP.el('div', { style: 'display:flex;justify-content:space-between;align-items:center;font-size:0.88rem' }, [
        PP.el('span', { style: 'color:var(--text-muted)' }, ['Available Balance:']),
        PP.el('span', { style: `font-weight:700;color:${walletBal === 0 ? 'var(--success)' : 'var(--danger)'}` }, [
          walletBal === 0 ? '✓ ₹0.00' : `✗ ${PP.fmt(walletBal)}`
        ])
      ]),
      PP.el('div', { style: 'display:flex;justify-content:space-between;align-items:center;font-size:0.88rem' }, [
        PP.el('span', { style: 'color:var(--text-muted)' }, ['Pocket Allocations:']),
        PP.el('span', { style: `font-weight:700;color:${pocketBal === 0 ? 'var(--success)' : 'var(--danger)'}` }, [
          pocketBal === 0 ? '✓ ₹0.00' : `✗ ${PP.fmt(pocketBal)}`
        ])
      ]),
      PP.el('div', { style: 'display:flex;justify-content:space-between;align-items:center;font-size:0.88rem' }, [
        PP.el('span', { style: 'color:var(--text-muted)' }, ['Pending Operations:']),
        PP.el('span', { style: 'font-weight:700;color:var(--success)' }, ['✓ None'])
      ])
    ]);
    body.appendChild(checklist);

    let password = '';
    if (!isEligible) {
      body.appendChild(PP.el('div', { style: 'padding:12px 16px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:12px;font-size:0.82rem;color:#f59e0b' }, [
        `⚠️ Your account cannot be deleted because you still have ${PP.fmt(totalRemaining)} in your account. Please withdraw or transfer all funds to reach ₹0.`
      ]));
    } else {
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Confirm Password to Delete Account *']),
        (() => {
          const inp = PP.el('input', { class: 'form-input', type: 'password', placeholder: 'Enter your password' });
          inp.oninput = () => password = inp.value;
          return inp;
        })()
      ]));
    }

    modal.body.innerHTML = '';
    modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));

    if (isEligible) {
      const delBtn = PP.el('button', {
        class: 'btn btn-danger',
        onclick: async () => {
          if (!password) return PP.UI.toast('Password Required', 'Please enter your password to confirm', 'warning');
          delBtn.disabled = true;
          delBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Deleting…';
          PP.refreshIcons();
          try {
            await PP.Auth.deleteAccount(password);
            modal.close();
            PP.UI.toast('Account Closed', 'Your account has been deleted permanently.', 'info');
            PP.state.user = null;
            setTimeout(() => { window.location.reload(); }, 600);
          } catch (e) {
            PP.UI.toast('Deletion Failed', e.message, 'error');
            delBtn.disabled = false;
            delBtn.innerHTML = 'Permanently Delete Account';
          }
        }
      }, ['Permanently Delete Account']);
      modal.footer.appendChild(delBtn);
    }

    PP.refreshIcons();
  },

  unifiedTransferHub() {
    const modal = PP.UI.modal({
      title: 'Transfers & Payments',
      subtitle: 'Choose your transfer or payment method',
      icon: 'send',
      iconClass: 'bg-accent',
      size: 'md'
    });
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.75rem' });
    const options = [
      { label: 'Scan & Pay QR', sub: 'Scan UPI, BharatQR, or PocketPay QR code', icon: 'qr-code', color: 'var(--accent)', fn: () => { modal.close(); PP.Modals.scanAndPay(); } },
      { label: 'Transfer to Bank Account', sub: 'Instant payout via IMPS / NEFT with UTR receipt', icon: 'landmark', color: 'var(--success)', fn: () => { modal.close(); PP.Modals.transferToBank(); } },
      { label: 'Net Banking Transfer', sub: 'Transfer to partner bank via Net Banking gateway', icon: 'building-2', color: 'var(--warning)', fn: () => { modal.close(); PP.Modals.netbankingTransfer(); } },
      { label: 'Transfer Between Pockets', sub: 'Reallocate funds instantly between your custom pockets', icon: 'refresh-ccw', color: 'var(--accent-2)', fn: () => { modal.close(); PP.Modals.transfer(); } },
    ];
    options.forEach(opt => {
      body.appendChild(PP.el('button', {
        class: 'btn btn-outline',
        style: 'justify-content:flex-start;padding:1rem 1.25rem;gap:1rem;text-align:left;width:100%',
        onclick: opt.fn
      }, [
        PP.el('div', { style: `width:42px;height:42px;border-radius:12px;background:rgba(255,255,255,.06);display:flex;align-items:center;justify-content:center;color:${opt.color};flex-shrink:0` }, [
          PP.el('i', { 'data-lucide': opt.icon, style: 'width:22px;height:22px' })
        ]),
        PP.el('div', { style: 'flex:1;min-width:0' }, [
          PP.el('div', { style: 'font-weight:700;font-size:.95rem;color:var(--text)' }, [opt.label]),
          PP.el('div', { style: 'font-size:.78rem;color:var(--text-muted);margin-top:2px' }, [opt.sub])
        ]),
        PP.el('i', { 'data-lucide': 'chevron-right', style: 'width:18px;height:18px;color:var(--text-dim)' })
      ]));
    });
    modal.body.innerHTML = '';
    modal.body.appendChild(body);
    PP.refreshIcons();
  },

  scanAndPay() {
    const modal = PP.UI.modal({
      title: 'Scan & Pay QR',
      subtitle: 'Pay via UPI QR, BharatQR, or PocketPay Wallet ID',
      icon: 'qr-code',
      iconClass: 'bg-accent',
      size: 'md'
    });

    let qrContent = '';
    let parsedRecipient = null;
    let amount = 0;
    let sourceType = 'wallet';
    let selectedPocketId = null;
    let notes = '';

    const pockets = (PP.state.pockets || []).filter(p => !p.archived);

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });

    // QR Input Area
    const qrSection = PP.el('div', { class: 'glass-card', style: 'padding:1.25rem;background:rgba(255,255,255,0.02);border:1px dashed rgba(255,255,255,0.15);border-radius:14px;text-align:center' });
    qrSection.innerHTML = `
      <div style="display:flex;justify-content:center;margin-bottom:0.75rem">
        <div style="width:48px;height:48px;border-radius:12px;background:rgba(99,102,241,0.12);color:var(--accent);display:flex;align-items:center;justify-content:center">
          <i data-lucide="scan" style="width:24px;height:24px"></i>
        </div>
      </div>
      <p style="margin:0 0 0.5rem;font-weight:600;font-size:0.92rem">Enter UPI ID or Paste QR Code string</p>
      <input type="text" id="qrInputBox" class="form-input" placeholder="e.g. merchant@upi, upi://pay?pa=... or wallet ID" style="text-align:center;font-family:monospace;font-size:0.88rem" />
      <div style="margin-top:0.75rem;display:flex;gap:0.5rem;justify-content:center">
        <button type="button" class="btn btn-sm btn-outline" id="sampleUpiBtn"><i data-lucide="sparkles"></i> Try Sample UPI</button>
      </div>
    `;
    body.appendChild(qrSection);

    // Payee details preview card
    const payeePreview = PP.el('div', { id: 'payeePreviewCard', class: 'glass-card', style: 'display:none;padding:1rem;background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.2);border-radius:14px' });
    body.appendChild(payeePreview);

    // Amount & Source group
    const formFields = PP.el('div', { id: 'qrFormFields', style: 'display:none;flex-direction:column;gap:1rem' });
    
    // Amount
    formFields.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Amount to Pay (₹) *']),
      (() => {
        const inp = PP.el('input', { class: 'form-input', type: 'number', min: '1', step: '0.01', placeholder: 'e.g. 500', id: 'qrAmountInput' });
        inp.oninput = () => amount = parseFloat(inp.value) || 0;
        return inp;
      })()
    ]));

    // Source Selector (Wallet vs Pocket)
    formFields.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Pay From']),
      (() => {
        const sel = PP.el('select', { class: 'form-select' });
        sel.appendChild(PP.el('option', { value: 'wallet' }, [`Available Balance (${PP.fmt(PP.state.user?.wallet_balance || 0)})`]));
        pockets.forEach(p => {
          sel.appendChild(PP.el('option', { value: `pocket:${p.id}` }, [`${p.name} Pocket (${PP.fmt(p.current_balance)})`]));
        });
        sel.onchange = () => {
          if (sel.value === 'wallet') {
            sourceType = 'wallet';
            selectedPocketId = null;
          } else {
            sourceType = 'pocket';
            selectedPocketId = parseInt(sel.value.split(':')[1]);
          }
        };
        return sel;
      })()
    ]));

    // Notes
    formFields.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Notes (optional)']),
      (() => {
        const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. Dinner with friends' });
        inp.oninput = () => notes = inp.value.trim();
        return inp;
      })()
    ]));

    body.appendChild(formFields);

    modal.body.innerHTML = '';
    modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));

    const payBtn = PP.el('button', {
      class: 'btn btn-primary',
      id: 'qrPayBtn',
      disabled: true,
      onclick: async () => {
        if (!parsedRecipient) return PP.UI.toast('Invalid QR', 'Please enter a valid QR code or UPI ID', 'warning');
        if (!(amount > 0)) return PP.UI.toast('Invalid Amount', 'Please enter a valid amount', 'warning');

        try {
          const pin = await PP.UI.pinPrompt({
            title: 'Confirm QR Payment',
            subtitle: `Pay ${PP.fmt(amount)} to ${parsedRecipient.recipient_name || 'Merchant'}`
          });
          if (!pin) return;

          payBtn.disabled = true;
          payBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Processing…';
          PP.refreshIcons();

          const res = await PP.PayoutsAPI.payQR({
            qr_string: qrContent,
            amount: amount,
            source_type: sourceType,
            pocket_id: selectedPocketId,
            pin: pin,
            notes: notes
          });

          modal.close();
          PP.UI.showSuccess({
            title: 'Payment Successful',
            subtitle: `${PP.fmt(amount)} sent to ${parsedRecipient.display_title || parsedRecipient.recipient_name}`,
            qr_code_url: res?.data?.qr_code_url || res?.data?.receipt_qr || res?.data?.transaction?.qr_code_url,
            meta: {
              'Payee': parsedRecipient.recipient_name,
              'Method': 'UPI / QR Code',
              'Reference': res?.data?.transaction?.upi_reference || 'TXN-SUCCESS'
            }
          });

          if (PP.state.user && res?.data?.wallet_balance != null) {
            PP.state.user.wallet_balance = res.data.wallet_balance;
          }
          PP.emit('pockets:changed');
          PP.refreshCurrentView();
        } catch (e) {
          PP.UI.toast('Payment Failed', e.message, 'error');
          payBtn.disabled = false;
          payBtn.innerHTML = 'Pay Now';
        }
      }
    }, ['Pay Now']);
    modal.footer.appendChild(payBtn);

    // Handler to parse QR
    const onQrUpdated = async (val) => {
      qrContent = val.trim();
      if (!qrContent) {
        payeePreview.style.display = 'none';
        formFields.style.display = 'none';
        payBtn.disabled = true;
        return;
      }

      // Automatically detect and verify Transaction Receipt QR scans
      if (qrContent.includes('/qr/tx/') || qrContent.startsWith('pocketpay://tx/') || /^(PPT|TX)[0-9A-Za-z]+/i.test(qrContent)) {
        try {
          const recRes = await PP.TxAPI.verifyReceipt(qrContent);
          if (recRes?.data?.receipt) {
            modal.close();
            PP.Modals.transactionReceiptModal(recRes.data.receipt);
            return;
          }
        } catch (recErr) {
          console.debug('[QR Scan] Not a transaction receipt:', recErr);
        }
      }

      try {
        const res = await PP.PayoutsAPI.parseQR(qrContent);
        parsedRecipient = res?.data?.qr_data;
        if (parsedRecipient && parsedRecipient.valid) {
          payeePreview.style.display = 'block';
          payeePreview.innerHTML = `
            <div style="display:flex;align-items:center;gap:0.75rem">
              <div style="width:38px;height:38px;border-radius:10px;background:rgba(16,185,129,0.15);color:#10b981;display:flex;align-items:center;justify-content:center">
                <i data-lucide="check-circle" style="width:20px;height:20px"></i>
              </div>
              <div>
                <div style="font-weight:700;font-size:0.95rem;color:#fff">${parsedRecipient.recipient_name || 'Merchant Payee'}</div>
                <div style="font-size:0.78rem;color:var(--text-muted);font-family:monospace">${parsedRecipient.display_title || ''}</div>
              </div>
            </div>
          `;
          formFields.style.display = 'flex';
          if (parsedRecipient.suggested_amount && parsedRecipient.suggested_amount > 0) {
            amount = parsedRecipient.suggested_amount;
            const amtInp = modal.body.querySelector('#qrAmountInput');
            if (amtInp) amtInp.value = amount;
          }
          payBtn.disabled = false;
          PP.refreshIcons();
        }
      } catch (e) {
        payeePreview.style.display = 'none';
        formFields.style.display = 'none';
        payBtn.disabled = true;
      }
    };

    setTimeout(() => {
      const inp = modal.body.querySelector('#qrInputBox');
      if (inp) {
        inp.addEventListener('input', (e) => onQrUpdated(e.target.value));
      }
      modal.body.querySelector('#sampleUpiBtn')?.addEventListener('click', () => {
        if (inp) {
          inp.value = 'coffee.shop@okaxis';
          onQrUpdated('coffee.shop@okaxis');
        }
      });
    }, 0);

    PP.refreshIcons();
  },

  transferToBank() {
    const modal = PP.UI.modal({
      title: 'Transfer to Bank Account',
      subtitle: 'Instant payout via IMPS / NEFT (Sandbox / Live Provider)',
      icon: 'landmark',
      iconClass: 'bg-success',
      size: 'md'
    });

    const user = PP.state.user || {};
    const linkedBanks = user.linked_banks || [];
    let selectedMode = 'IMPS';
    let accountHolder = user.full_name || '';
    let accountNumber = '';
    let ifscCode = 'SBIN0001234';
    let bankName = 'State Bank of India';
    let amount = 0;

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.15rem' });

    // Sandbox notice banner
    body.appendChild(PP.el('div', { class: 'glass-card', style: 'padding:12px 16px;background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:12px;font-size:0.82rem;color:var(--text-muted)' }, [
      PP.el('strong', { style: 'color:#818cf8;margin-right:6px' }, ['Sandbox Gateway:']),
      'Payout is processed through the server-side Payout Provider API with simulated UTR reconciliation.'
    ]));

    // Quick select saved bank or new
    if (linkedBanks.length > 0) {
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Select Destination Bank']),
        (() => {
          const sel = PP.el('select', { class: 'form-select' });
          sel.appendChild(PP.el('option', { value: 'custom' }, ['+ Enter New Beneficiary Details']));
          linkedBanks.forEach((bk, idx) => {
            sel.appendChild(PP.el('option', { value: idx }, [`${bk.bank_name} (${bk.account_mask || '••••'}) — ${bk.account_holder}`]));
          });
          sel.onchange = () => {
            if (sel.value === 'custom') {
              accountNumber = '';
              bankName = '';
            } else {
              const b = linkedBanks[parseInt(sel.value)];
              accountHolder = b.account_holder;
              accountNumber = '501004928192'; // standard sandbox account
              ifscCode = b.ifsc_code || 'SBIN0001234';
              bankName = b.bank_name;
              const accInp = modal.body.querySelector('#bankAccInput');
              const ifscInp = modal.body.querySelector('#bankIfscInput');
              const nameInp = modal.body.querySelector('#bankHolderInput');
              if (accInp) accInp.value = accountNumber;
              if (ifscInp) ifscInp.value = ifscCode;
              if (nameInp) nameInp.value = accountHolder;
            }
          };
          return sel;
        })()
      ]));
    }

    // Beneficiary form
    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Account Holder Name *']),
      (() => {
        const inp = PP.el('input', { class: 'form-input', value: accountHolder, id: 'bankHolderInput', placeholder: 'e.g. Arjun Sharma' });
        inp.oninput = () => accountHolder = inp.value.trim();
        return inp;
      })()
    ]));

    body.appendChild(PP.el('div', { class: 'form-row' }, [
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Account Number *']),
        (() => {
          const inp = PP.el('input', { class: 'form-input', value: accountNumber, id: 'bankAccInput', placeholder: '9 to 18 digits', maxlength: '18' });
          inp.oninput = () => accountNumber = inp.value.trim();
          return inp;
        })()
      ]),
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['IFSC Code *']),
        (() => {
          const inp = PP.el('input', { class: 'form-input', value: ifscCode, id: 'bankIfscInput', placeholder: 'e.g. SBIN0001234', maxlength: '11' });
          inp.oninput = () => ifscCode = inp.value.trim().toUpperCase();
          return inp;
        })()
      ])
    ]));

    body.appendChild(PP.el('div', { class: 'form-row' }, [
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Transfer Mode']),
        (() => {
          const sel = PP.el('select', { class: 'form-select' });
          [['IMPS', 'IMPS (Instant 24x7)'], ['NEFT', 'NEFT (Standard)'], ['RTGS', 'RTGS (High Value)']].forEach(m => {
            sel.appendChild(PP.el('option', { value: m[0] }, [m[1]]));
          });
          sel.onchange = () => selectedMode = sel.value;
          return sel;
        })()
      ]),
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, [`Amount (Available: ${PP.fmt(user.wallet_balance || 0)}) *`]),
        (() => {
          const inp = PP.el('input', { class: 'form-input', type: 'number', min: '10', step: '0.01', placeholder: 'Min ₹10' });
          inp.oninput = () => amount = parseFloat(inp.value) || 0;
          return inp;
        })()
      ])
    ]));

    modal.body.innerHTML = '';
    modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));

    const sendBtn = PP.el('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        if (!accountHolder) return PP.UI.toast('Name Required', 'Enter account holder name', 'warning');
        if (!accountNumber || accountNumber.length < 9) return PP.UI.toast('Account Number Required', 'Enter a valid 9-18 digit account number', 'warning');
        if (!ifscCode || ifscCode.length < 11) return PP.UI.toast('IFSC Required', 'Enter a valid 11-character IFSC code', 'warning');
        if (!(amount >= 10)) return PP.UI.toast('Minimum Amount', 'Transfer amount must be at least ₹10.00', 'warning');
        if (amount > (user.wallet_balance || 0)) return PP.UI.toast('Insufficient Balance', `You only have ${PP.fmt(user.wallet_balance || 0)} available.`, 'warning');

        try {
          const pin = await PP.UI.pinPrompt({
            title: 'Authorize Bank Transfer',
            subtitle: `Transfer ${PP.fmt(amount)} to ${accountHolder} (${ifscCode})`
          });
          if (!pin) return;

          sendBtn.disabled = true;
          sendBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Contacting Gateway…';
          PP.refreshIcons();

          const res = await PP.PayoutsAPI.transferToBank({
            account_holder: accountHolder,
            account_number: accountNumber,
            ifsc_code: ifscCode,
            bank_name: bankName,
            amount: amount,
            mode: selectedMode,
            pin: pin,
            idempotency_key: `payout_ui_${Date.now()}`
          });

          modal.close();
          const p = res?.data?.payout || {};
          PP.UI.showSuccess({
            title: 'Transfer Successful',
            subtitle: `${PP.fmt(amount)} transferred via ${selectedMode} to ${p.account_holder || accountHolder}`,
            qr_code_url: res?.data?.qr_code_url || res?.data?.receipt_qr || res?.data?.transaction?.qr_code_url,
            meta: {
              'Bank': p.bank_name || bankName,
              'Account': p.account_mask || '••••',
              'UTR Reference': p.utr || 'PROCESSED',
              'Status': 'Completed (Sandbox Gateway)'
            }
          });

          if (PP.state.user && res?.data?.wallet_balance != null) {
            PP.state.user.wallet_balance = res.data.wallet_balance;
          }
          PP.emit('pockets:changed');
          PP.refreshCurrentView();
        } catch (e) {
          PP.UI.toast('Transfer Failed', e.message, 'error');
          sendBtn.disabled = false;
          sendBtn.innerHTML = 'Send Transfer';
        }
      }
    }, ['Send Transfer']);
    modal.footer.appendChild(sendBtn);

    PP.refreshIcons();
  },

  netbankingTransfer() {
    const modal = PP.UI.modal({
      title: 'Net Banking Transfer',
      subtitle: 'Transfer funds securely through Partner Bank Net Banking',
      icon: 'building-2',
      iconClass: 'bg-warning',
      size: 'md'
    });

    const user = PP.state.user || {};
    let selectedBank = 'SBIN';
    let accountHolder = user.full_name || '';
    let accountNumber = '501004928192';
    let amount = 0;

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.15rem' });

    // Bank Grid
    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Select Partner Bank']),
      (() => {
        const sel = PP.el('select', { class: 'form-select' });
        [
          ['SBIN', 'State Bank of India (SBI)'],
          ['HDFC', 'HDFC Bank'],
          ['ICIC', 'ICICI Bank'],
          ['UTIB', 'Axis Bank'],
          ['KKBK', 'Kotak Mahindra Bank'],
          ['PUNB', 'Punjab National Bank'],
          ['BARB', 'Bank of Baroda'],
          ['CNRB', 'Canara Bank'],
        ].forEach(b => {
          sel.appendChild(PP.el('option', { value: b[0] }, [b[1]]));
        });
        sel.onchange = () => selectedBank = sel.value;
        return sel;
      })()
    ]));

    body.appendChild(PP.el('div', { class: 'form-row' }, [
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Beneficiary Name *']),
        (() => {
          const inp = PP.el('input', { class: 'form-input', value: accountHolder, placeholder: 'e.g. Ramesh Kumar' });
          inp.oninput = () => accountHolder = inp.value.trim();
          return inp;
        })()
      ]),
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Beneficiary Account Number *']),
        (() => {
          const inp = PP.el('input', { class: 'form-input', value: accountNumber, placeholder: '9 to 18 digits' });
          inp.oninput = () => accountNumber = inp.value.trim();
          return inp;
        })()
      ])
    ]));

    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, [`Amount to Transfer (Available: ${PP.fmt(user.wallet_balance || 0)}) *`]),
      (() => {
        const inp = PP.el('input', { class: 'form-input', type: 'number', min: '10', step: '0.01', placeholder: 'Min ₹10' });
        inp.oninput = () => amount = parseFloat(inp.value) || 0;
        return inp;
      })()
    ]));

    modal.body.innerHTML = '';
    modal.body.appendChild(body);
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));

    const payBtn = PP.el('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        if (!accountHolder) return PP.UI.toast('Name Required', 'Enter beneficiary name', 'warning');
        if (!accountNumber || accountNumber.length < 9) return PP.UI.toast('Account Number Required', 'Enter a valid account number', 'warning');
        if (!(amount >= 10)) return PP.UI.toast('Minimum Amount', 'Transfer amount must be at least ₹10.00', 'warning');
        if (amount > (user.wallet_balance || 0)) return PP.UI.toast('Insufficient Balance', `You only have ${PP.fmt(user.wallet_balance || 0)} available.`, 'warning');

        try {
          const pin = await PP.UI.pinPrompt({
            title: 'Authorize Net Banking Transfer',
            subtitle: `Transfer ${PP.fmt(amount)} via ${selectedBank} Net Banking`
          });
          if (!pin) return;

          payBtn.disabled = true;
          payBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Authenticating with Bank…';
          PP.refreshIcons();

          const res = await PP.PayoutsAPI.netbankingTransfer({
            bank_code: selectedBank,
            account_holder: accountHolder,
            account_number: accountNumber,
            amount: amount,
            pin: pin,
            idempotency_key: `netbank_${Date.now()}`
          });

          modal.close();
          const p = res?.data?.payout || {};
          PP.UI.showSuccess({
            title: 'Net Banking Transfer Complete',
            subtitle: `${PP.fmt(amount)} transferred via Net Banking to ${p.account_holder || accountHolder}`,
            qr_code_url: res?.data?.qr_code_url || res?.data?.receipt_qr || res?.data?.transaction?.qr_code_url,
            meta: {
              'Bank Gateway': p.bank_name || selectedBank,
              'UTR Number': p.utr || 'NETBANK-SUCCESS',
              'Mode': 'Net Banking (Sandbox)'
            }
          });

          if (PP.state.user && res?.data?.wallet_balance != null) {
            PP.state.user.wallet_balance = res.data.wallet_balance;
          }
          PP.emit('pockets:changed');
          PP.refreshCurrentView();
        } catch (e) {
          PP.UI.toast('Transfer Failed', e.message, 'error');
          payBtn.disabled = false;
          payBtn.innerHTML = 'Proceed to Transfer';
        }
      }
    }, ['Proceed to Transfer']);
    modal.footer.appendChild(payBtn);

    PP.refreshIcons();
  },

  openQuickAdd() {
    const modal = PP.UI.modal({
      title: 'Quick Actions',
      subtitle: 'What would you like to do?',
      icon: 'plus-circle',
      iconClass: 'bg-accent',
      size: 'sm'
    });
    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:.75rem' });
    const actions = [
      { label: 'Scan & Pay QR', sub: 'Scan UPI, BharatQR, or Wallet QR', icon: 'qr-code', cls: 'btn-outline', iconColor: 'var(--accent)', fn: () => { modal.close(); PP.Modals.scanAndPay(); } },
      { label: 'Transfer to Bank / Net Banking', sub: 'Payout to bank account via IMPS/NEFT', icon: 'landmark', cls: 'btn-outline', iconColor: 'var(--success)', fn: () => { modal.close(); PP.Modals.unifiedTransferHub(); } },
      { label: 'Transfer Between Pockets', sub: 'Move money from one pocket to another', icon: 'refresh-ccw', cls: 'btn-outline', iconColor: 'var(--accent)', fn: () => { modal.close(); PP.Modals.transfer(); } },
      { label: 'Add Income / Deposit', sub: 'Split incoming money across pockets', icon: 'arrow-down-left', cls: 'btn-outline', iconColor: 'var(--success)', fn: () => { modal.close(); PP.Modals.addIncome(); } },
      { label: 'Make Payment / Expense', sub: 'Pay from a pocket with PIN security', icon: 'arrow-up-right', cls: 'btn-outline', iconColor: 'var(--danger)', fn: () => { modal.close(); PP.Modals.addExpense(); } },
      { label: 'Create New Pocket', sub: 'Set up a custom category or savings goal', icon: 'folder-plus', cls: 'btn-outline', iconColor: 'var(--accent-2)', fn: () => { modal.close(); PP.Modals.createPocket(); } },
    ];
    actions.forEach(a => {
      body.appendChild(PP.el('button', {
        class: `btn ${a.cls}`,
        style: 'justify-content:flex-start;padding:.85rem 1rem;gap:.9rem;text-align:left;width:100%',
        onclick: a.fn
      }, [
        PP.el('div', { style: `width:36px;height:36px;border-radius:10px;background:rgba(255,255,255,.07);display:flex;align-items:center;justify-content:center;color:${a.iconColor};flex-shrink:0` }, [
          PP.el('i', { 'data-lucide': a.icon, style: 'width:18px;height:18px' })
        ]),
        PP.el('div', { style: 'flex:1;min-width:0' }, [
          PP.el('div', { style: 'font-weight:600;font-size:.9rem;color:var(--text)' }, [a.label]),
          PP.el('div', { style: 'font-size:.75rem;color:var(--text-muted);margin-top:2px' }, [a.sub])
        ]),
        PP.el('i', { 'data-lucide': 'chevron-right', style: 'width:16px;height:16px;color:var(--text-dim)' })
      ]));
    });
    modal.body.innerHTML = '';
    modal.body.appendChild(body);
    PP.refreshIcons();
  },

  async setupTOTP() {
    const modal = PP.UI.modal({
      title: 'Enable Two-Factor Authentication',
      subtitle: 'Scan QR with Google Authenticator, Microsoft Authenticator, or 1Password',
      icon: 'shield-check',
      iconClass: 'bg-accent',
      size: 'md'
    });

    modal.body.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;padding:2rem">
        <i data-lucide="loader-2" style="width:32px;height:32px;animation:slowSpin 1s linear infinite;color:var(--accent)"></i>
      </div>
    `;
    PP.refreshIcons();

    try {
      const res = await PP.Auth.totpSetup();
      const setup = res?.data || {};
      let step = 1;

      const renderStep1 = () => {
        const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.25rem' });

        // QR Code Container
        body.appendChild(PP.el('div', {
          class: 'glass-card',
          style: 'display:flex;flex-direction:column;align-items:center;padding:1.25rem;background:#ffffff;border-radius:16px;margin:0 auto;max-width:240px'
        }, [
          PP.el('img', {
            src: setup.qr_code,
            alt: 'Authenticator 2FA QR Code',
            style: 'width:180px;height:180px;display:block;border-radius:8px'
          }),
          PP.el('div', { style: 'font-size:0.75rem;color:#0a0b14;font-weight:700;margin-top:6px;text-align:center' }, ['Scan in Authenticator App'])
        ]));

        // Manual Key Card
        body.appendChild(PP.el('div', {
          class: 'glass-card',
          style: 'padding:0.85rem 1rem;background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:12px;display:flex;align-items:center;justify-content:space-between;gap:0.75rem'
        }, [
          PP.el('div', {}, [
            PP.el('div', { style: 'font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-weight:600' }, ['Can’t scan? Enter key manually']),
            PP.el('div', { style: 'font-family:var(--font-mono);font-size:0.95rem;font-weight:700;color:var(--accent);letter-spacing:0.1em;margin-top:2px' }, [setup.manual_key || setup.secret])
          ]),
          PP.el('button', {
            type: 'button',
            class: 'btn btn-sm btn-outline',
            onclick: () => {
              navigator.clipboard?.writeText(setup.secret);
              PP.UI.toast('Copied', 'Setup key copied to clipboard', 'info');
            }
          }, [PP.el('i', { 'data-lucide': 'copy' }), 'Copy'])
        ]));

        // 6-digit Code Input
        const verifyGroup = PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Enter 6-Digit Code from Authenticator App *']),
          (() => {
            const inp = PP.el('input', {
              class: 'form-input',
              type: 'text',
              maxlength: '7',
              placeholder: '000 000',
              inputmode: 'numeric',
              autocomplete: 'one-time-code',
              id: 'totpSetupCodeInp',
              style: 'text-align:center;font-family:var(--font-mono);font-size:1.5rem;letter-spacing:0.25em;font-weight:700'
            });
            inp.oninput = () => {
              const val = inp.value.replace(/\s+/g, '').replace(/-/g, '');
              if (val.length === 6) {
                setTimeout(() => {
                  const btn = modal.footer.querySelector('#totpVerifyBtn');
                  if (btn && !btn.disabled) btn.click();
                }, 150);
              }
            };
            inp.onkeydown = (e) => {
              if (e.key === 'Enter') {
                const btn = modal.footer.querySelector('#totpVerifyBtn');
                if (btn && !btn.disabled) btn.click();
              }
            };
            setTimeout(() => inp.focus(), 100);
            return inp;
          })()
        ]);
        body.appendChild(verifyGroup);

        modal.body.innerHTML = '';
        modal.body.appendChild(body);

        modal.footer.innerHTML = '';
        modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
        
        const verifyBtn = PP.el('button', {
          class: 'btn btn-primary',
          id: 'totpVerifyBtn',
          onclick: async () => {
            const inp = modal.body.querySelector('#totpSetupCodeInp');
            const rawVal = inp ? inp.value : '';
            const code = rawVal.replace(/\s+/g, '').replace(/-/g, '').trim();
            if (!code || code.length < 6) {
              return PP.UI.toast('Code Required', 'Enter the 6-digit code shown in Google Authenticator or Microsoft Authenticator', 'warning');
            }

            verifyBtn.disabled = true;
            verifyBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Verifying…';
            PP.refreshIcons();

            try {
              const verifyRes = await PP.Auth.totpVerifySetup(code, setup.secret, setup.backup_codes);
              if (PP.state.user) {
                PP.state.user.totp_enabled = true;
              }
              step = 2;
              renderStep2(verifyRes?.data?.backup_codes || setup.backup_codes || []);
            } catch (err) {
              PP.UI.toast('Verification Failed', err.message || 'Invalid code. Check Authenticator app and device time.', 'error');
              verifyBtn.disabled = false;
              verifyBtn.innerHTML = 'Verify & Activate 2FA';
            }
          }
        }, ['Verify & Activate 2FA']);
        modal.footer.appendChild(verifyBtn);
        PP.refreshIcons();
      };

      const renderStep2 = (backupCodes) => {
        modal.header.querySelector('.modal-title').textContent = '2FA Enabled — Save Backup Codes';
        modal.header.querySelector('.modal-sub').textContent = 'Save these 8 single-use recovery codes in case you lose access to your authenticator app.';

        const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.25rem' });

        const banner = PP.el('div', {
          class: 'glass-card',
          style: 'padding:1rem;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);border-radius:12px;font-size:0.85rem;color:var(--text)'
        }, [
          PP.el('strong', { style: 'color:#10b981;display:block;margin-bottom:4px' }, ['✓ Two-Factor Authentication is Active']),
          'Each backup code can be used once to authorize payments or log in if you cannot access your authenticator.'
        ]);
        body.appendChild(banner);

        const codesGrid = PP.el('div', {
          style: 'display:grid;grid-template-columns:1fr 1fr;gap:0.65rem;background:rgba(0,0,0,0.3);padding:1rem;border-radius:12px;border:1px solid var(--border)'
        });
        backupCodes.forEach((bc, idx) => {
          codesGrid.appendChild(PP.el('div', {
            style: 'font-family:var(--font-mono);font-size:0.92rem;font-weight:700;letter-spacing:0.08em;color:var(--text);padding:6px 10px;background:rgba(255,255,255,0.04);border-radius:8px;text-align:center'
          }, [`${idx + 1}. ${bc}`]));
        });
        body.appendChild(codesGrid);

        const copyAllBtn = PP.el('button', {
          type: 'button',
          class: 'btn btn-outline',
          style: 'align-self:center;gap:0.5rem',
          onclick: () => {
            const text = backupCodes.map((c, i) => `${i + 1}. ${c}`).join('\n');
            navigator.clipboard?.writeText(text);
            PP.UI.toast('Copied', 'Backup recovery codes copied to clipboard', 'info');
          }
        }, [PP.el('i', { 'data-lucide': 'copy' }), 'Copy All Backup Codes']);
        body.appendChild(copyAllBtn);

        modal.body.innerHTML = '';
        modal.body.appendChild(body);

        modal.footer.innerHTML = '';
        modal.footer.appendChild(PP.el('button', {
          class: 'btn btn-primary',
          onclick: () => {
            modal.close();
            PP.UI.toast('2FA Ready', 'Your account is now secured with TOTP Two-Factor Authentication.', 'success');
            PP.refreshCurrentView();
          }
        }, ['Done']));

        PP.refreshIcons();
      };

      renderStep1();
    } catch (e) {
      PP.UI.toast('Setup Failed', e.message || 'Could not initiate TOTP setup', 'error');
      modal.close();
    }
  },

  async disableTOTP() {
    const modal = PP.UI.modal({
      title: 'Disable Two-Factor Authentication',
      subtitle: 'Enter your password to turn off Authenticator 2FA verification',
      icon: 'shield-alert',
      iconClass: 'bg-danger',
      size: 'sm'
    });

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Account Password *']),
      (() => {
        const inp = PP.el('input', {
          class: 'form-input',
          type: 'password',
          placeholder: 'Enter your account password',
          id: 'totpDisablePassword'
        });
        setTimeout(() => inp.focus(), 100);
        return inp;
      })()
    ]));

    modal.body.innerHTML = '';
    modal.body.appendChild(body);

    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));

    const disableBtn = PP.el('button', {
      class: 'btn btn-danger',
      onclick: async () => {
        const pass = modal.body.querySelector('#totpDisablePassword')?.value || '';
        if (!pass) return PP.UI.toast('Password Required', 'Enter your account password', 'warning');

        disableBtn.disabled = true;
        disableBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Disabling…';
        PP.refreshIcons();

        try {
          await PP.Auth.totpDisable({ password: pass });
          if (PP.state.user) {
            PP.state.user.totp_enabled = false;
          }
          modal.close();
          PP.UI.toast('2FA Disabled', 'Two-factor authentication has been turned off.', 'info');
          PP.refreshCurrentView();
        } catch (e) {
          PP.UI.toast('Failed to Disable', e.message || 'Incorrect password', 'error');
          disableBtn.disabled = false;
          disableBtn.innerHTML = 'Turn Off 2FA';
        }
      }
    }, ['Turn Off 2FA']);
    modal.footer.appendChild(disableBtn);
    PP.refreshIcons();
  },

  async viewBackupCodes() {
    const modal = PP.UI.modal({
      title: 'Regenerate Backup Recovery Codes',
      subtitle: 'Enter your password to generate a fresh set of 8 recovery codes',
      icon: 'key-round',
      iconClass: 'bg-accent',
      size: 'sm'
    });

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Account Password *']),
      (() => {
        const inp = PP.el('input', {
          class: 'form-input',
          type: 'password',
          placeholder: 'Enter your account password',
          id: 'regenCodesPassword'
        });
        setTimeout(() => inp.focus(), 100);
        return inp;
      })()
    ]));

    modal.body.innerHTML = '';
    modal.body.appendChild(body);

    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));

    const genBtn = PP.el('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        const pass = modal.body.querySelector('#regenCodesPassword')?.value || '';
        if (!pass) return PP.UI.toast('Password Required', 'Enter your account password', 'warning');

        genBtn.disabled = true;
        genBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Generating…';
        PP.refreshIcons();

        try {
          const res = await PP.Auth.totpRegenerateBackupCodes({ password: pass });
          const newCodes = res?.data?.backup_codes || [];
          
          modal.header.querySelector('.modal-title').textContent = 'Your New Backup Codes';
          modal.header.querySelector('.modal-sub').textContent = 'Previous backup codes have been invalidated.';

          const resultBody = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });
          const codesGrid = PP.el('div', {
            style: 'display:grid;grid-template-columns:1fr 1fr;gap:0.65rem;background:rgba(0,0,0,0.3);padding:1rem;border-radius:12px;border:1px solid var(--border)'
          });
          newCodes.forEach((bc, idx) => {
            codesGrid.appendChild(PP.el('div', {
              style: 'font-family:var(--font-mono);font-size:0.92rem;font-weight:700;letter-spacing:0.08em;color:var(--text);padding:6px 10px;background:rgba(255,255,255,0.04);border-radius:8px;text-align:center'
            }, [`${idx + 1}. ${bc}`]));
          });
          resultBody.appendChild(codesGrid);

          const copyBtn = PP.el('button', {
            type: 'button',
            class: 'btn btn-outline',
            style: 'align-self:center;gap:0.5rem',
            onclick: () => {
              navigator.clipboard?.writeText(newCodes.map((c, i) => `${i + 1}. ${c}`).join('\n'));
              PP.UI.toast('Copied', 'Codes copied to clipboard', 'info');
            }
          }, [PP.el('i', { 'data-lucide': 'copy' }), 'Copy All Codes']);
          resultBody.appendChild(copyBtn);

          modal.body.innerHTML = '';
          modal.body.appendChild(resultBody);

          modal.footer.innerHTML = '';
          modal.footer.appendChild(PP.el('button', { class: 'btn btn-primary', onclick: () => modal.close() }, ['Done']));
          PP.refreshIcons();
        } catch (e) {
          PP.UI.toast('Generation Failed', e.message || 'Incorrect password', 'error');
          genBtn.disabled = false;
          genBtn.innerHTML = 'Generate Codes';
        }
      }
    }, ['Generate Codes']);
    modal.footer.appendChild(genBtn);
    PP.refreshIcons();
  },

  showTransferReceipt(data = {}) {
    const t = data.transaction || {};
    const recipient = data.recipient || {};
    const amountVal = data.amount || t.amount || 0;
    
    // Resolve clean image URL: base64 Data-URI or dynamic PNG image generator endpoint
    const rawQr = data.receipt_qr || t.receipt_qr || t.qr_code_url;
    let qrUrl = null;
    if (rawQr && typeof rawQr === 'string' && rawQr.startsWith('data:image/')) {
      qrUrl = rawQr;
    } else if (t.transaction_id) {
      qrUrl = `/api/qr?content=${encodeURIComponent('https://pocketpay-1.onrender.com/qr/tx/' + t.transaction_id)}&size=250`;
    } else if (rawQr) {
      qrUrl = `/api/qr?content=${encodeURIComponent(rawQr)}&size=250`;
    }

    const senderSource = data.source_name || (t.from_pocket_id ? 'Funding Pocket' : 'PocketPay Wallet');
    const recipientDisplay = recipient.full_name || data.resolvedUser?.full_name || t.merchant || 'PocketPay Member';
    const recipientUpi = recipient.virtual_upi_id || data.resolvedUser?.virtual_upi_id || (t.extra_data?.peer_upi) || '—';
    const dateStr = t.created_at ? (PP.formatDate ? PP.formatDate(t.created_at, true) : new Date(t.created_at).toLocaleString()) : new Date().toLocaleString();

    const modal = PP.UI.modal({
      title: 'Payment Successful',
      subtitle: 'Transfer completed & recorded on PocketPay ledger',
      icon: 'check-circle-2',
      iconClass: 'bg-success',
      size: 'md'
    });

    const body = PP.el('div', { id: 'printableReceiptArea', style: 'display:flex;flex-direction:column;gap:1rem' });

    // Amount & Hero
    body.appendChild(PP.el('div', {
      class: 'glass-card',
      style: 'text-align:center;padding:1.25rem;background:linear-gradient(180deg, rgba(16,185,129,0.12), rgba(16,185,129,0.02));border:1px solid rgba(16,185,129,0.25);border-radius:16px'
    }, [
      PP.el('div', { style: 'font-size:0.8rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-weight:700' }, ['SENT TO RECIPIENT']),
      PP.el('div', {
        style: 'font-size:2.2rem;font-weight:800;font-family:var(--font-display);color:var(--success);margin-top:0.25rem'
      }, [`₹${Number(amountVal).toLocaleString('en-IN', {minimumFractionDigits:2})}`]),
      PP.el('div', { style: 'display:inline-flex;align-items:center;gap:0.35rem;margin-top:0.4rem;padding:0.25rem 0.75rem;border-radius:9999px;font-size:0.78rem;font-weight:700;background:rgba(16,185,129,0.15);color:#10b981' }, [
        PP.el('i', { 'data-lucide': 'check-circle-2', style: 'width:14px;height:14px' }),
        'TRANSFER COMPLETED'
      ])
    ]));

    // Transaction Verification QR Card
    const qrContainer = PP.el('div', {
      class: 'glass-card',
      style: 'display:flex;flex-direction:column;align-items:center;padding:1rem;background:#ffffff;border-radius:14px;margin:0 auto;max-width:210px;box-shadow:0 8px 24px rgba(0,0,0,0.35);text-align:center'
    });

    if (qrUrl) {
      qrContainer.innerHTML = `
        <img src="${qrUrl}" alt="Transaction Receipt QR" style="width:150px;height:150px;display:block;border-radius:8px;object-fit:contain" id="transferReceiptQrImg" onerror="this.src='/api/qr?content=${encodeURIComponent('https://pocketpay-1.onrender.com/qr/tx/' + (t.transaction_id || ''))}&size=250'" />
        <div style="font-size:0.72rem;font-weight:800;color:#0a0b14;margin-top:6px;letter-spacing:0.02em">
          Digital Verification QR
        </div>
        <div style="font-size:0.65rem;color:#475569;margin-top:2px">
          Scan with PocketPay to verify
        </div>
      `;
    } else {
      qrContainer.innerHTML = `
        <div style="padding:1rem 0.5rem;color:#475569;font-size:0.8rem">
          <i data-lucide="qr-code" style="width:32px;height:32px;margin:0 auto 0.5rem;color:#94a3b8;display:block"></i>
          <div>Receipt QR unavailable</div>
          <button type="button" class="btn btn-sm btn-outline" style="margin-top:0.5rem" id="retryQrBtn">
            <i data-lucide="refresh-cw"></i> Generate QR
          </button>
        </div>
      `;
      setTimeout(() => {
        PP.$('#retryQrBtn', qrContainer)?.addEventListener('click', async () => {
          try {
            const genRes = await PP.API.post('/api/qr/generate', { content: `https://pocketpay-1.onrender.com/qr/tx/${t.transaction_id}` });
            if (genRes?.data?.qr_code_url) {
              qrContainer.innerHTML = `
                <img src="${genRes.data.qr_code_url}" alt="Transaction Receipt QR" style="width:150px;height:150px;display:block;border-radius:8px" />
                <div style="font-size:0.72rem;font-weight:800;color:#0a0b14;margin-top:6px">Digital Verification QR</div>
              `;
            }
          } catch {
            PP.UI.toast('QR Error', 'Could not generate QR code at this time', 'warning');
          }
        });
      }, 50);
    }
    body.appendChild(qrContainer);

    // Detail Rows
    const rows = [
      { label: 'Transaction ID', value: t.transaction_id || '—', copyable: true },
      { label: 'Date & Time', value: dateStr },
      { label: 'Sender', value: `${PP.state.user?.full_name || 'You'} (${senderSource})` },
      { label: 'Recipient', value: `${recipientDisplay} (${recipientUpi})` },
      { label: 'Payment Method', value: 'PocketPay P2P Transfer' },
      data.note ? { label: 'Note', value: data.note } : null,
      data.wallet_balance != null ? { label: 'Updated Wallet Balance', value: `₹${Number(data.wallet_balance).toLocaleString('en-IN', {minimumFractionDigits:2})}` } : null
    ].filter(Boolean);

    const detailsWrap = PP.el('div', {
      class: 'glass-card',
      style: 'padding:0.75rem 1rem;border-radius:12px;display:flex;flex-direction:column;gap:0.6rem;background:rgba(255,255,255,0.02);border:1px solid var(--border)'
    });
    rows.forEach(r => {
      detailsWrap.appendChild(PP.el('div', {
        style: 'display:flex;justify-content:space-between;align-items:center;font-size:0.85rem;padding:0.25rem 0'
      }, [
        PP.el('div', { style: 'color:var(--text-muted)' }, [r.label]),
        PP.el('div', { style: 'font-weight:600;display:flex;align-items:center;gap:0.35rem;text-align:right' }, [
          PP.el('span', {}, [r.value]),
          r.copyable ? PP.el('button', {
            type: 'button',
            class: 'btn-icon',
            style: 'width:22px;height:22px;padding:2px',
            onclick: () => {
              navigator.clipboard?.writeText(r.value);
              PP.UI.toast('Copied', `${r.label} copied to clipboard`, 'info');
            }
          }, [PP.el('i', { 'data-lucide': 'copy', style: 'width:12px;height:12px' })]) : null
        ].filter(Boolean))
      ]));
    });
    body.appendChild(detailsWrap);

    modal.body.innerHTML = '';
    modal.body.appendChild(body);

    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', {
      class: 'btn btn-ghost',
      onclick: () => modal.close()
    }, ['Done']));

    if (qrUrl) {
      modal.footer.appendChild(PP.el('button', {
        class: 'btn btn-outline',
        onclick: () => {
          const a = document.createElement('a');
          a.href = qrUrl;
          a.download = `PocketPay_Receipt_${t.transaction_id || 'transfer'}.png`;
          a.click();
          PP.UI.toast('Saved', 'Transfer receipt downloaded', 'success');
        }
      }, [PP.el('i', { 'data-lucide': 'download' }), 'Save QR']));
    }

    modal.footer.appendChild(PP.el('button', {
      class: 'btn btn-primary',
      onclick: () => {
        window.print();
      }
    }, [PP.el('i', { 'data-lucide': 'printer' }), 'Print Receipt']));

    PP.refreshIcons();
  },

  transactionReceiptModal(r) {
    if (!r) return;
    const isIncome = ['income', 'topup', 'peer_receive'].includes(r.type);
    const isExpense = ['expense', 'peer_send', 'withdraw'].includes(r.type);
    
    const rawQr = r.receipt_qr || r.qr_code_url;
    let qrUrl = null;
    if (rawQr && typeof rawQr === 'string' && rawQr.startsWith('data:image/')) {
      qrUrl = rawQr;
    } else if (r.transaction_id) {
      qrUrl = `/api/qr?content=${encodeURIComponent('https://pocketpay-1.onrender.com/qr/tx/' + r.transaction_id)}&size=250`;
    } else if (rawQr) {
      qrUrl = `/api/qr?content=${encodeURIComponent(rawQr)}&size=250`;
    }

    const modal = PP.UI.modal({
      title: 'Verified Transaction Receipt',
      subtitle: `Official Reference: ${r.transaction_id || '—'}`,
      icon: 'shield-check',
      iconClass: 'bg-success',
      size: 'md'
    });

    const body = PP.el('div', { id: 'printableReceiptArea', style: 'display:flex;flex-direction:column;gap:1.15rem' });

    // Header & Verified badge
    body.appendChild(PP.el('div', {
      class: 'glass-card',
      style: 'text-align:center;padding:1.25rem;background:linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));border-radius:14px;border:1px solid var(--border)'
    }, [
      PP.el('div', { style: 'font-size:0.8rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-weight:700' }, [r.type?.toUpperCase() || 'PAYMENT']),
      PP.el('div', {
        style: `font-size:2rem;font-weight:800;font-family:var(--font-display);margin-top:0.25rem;color:${isIncome ? 'var(--success)' : (isExpense ? 'var(--danger)' : 'var(--text)')}`
      }, [`${isIncome ? '+' : (isExpense ? '-' : '')}${PP.fmt(r.amount)}`]),
      PP.el('div', { style: 'display:flex;justify-content:center;gap:0.5rem;margin-top:0.5rem' }, [
        PP.el('span', { class: `chip ${r.status === 'completed' ? 'success' : 'warning'}` }, [(r.status || 'COMPLETED').toUpperCase()]),
        PP.el('span', { class: 'chip success' }, [
          PP.el('i', { 'data-lucide': 'check-circle', style: 'width:12px;height:12px' }),
          'SERVER VERIFIED'
        ])
      ])
    ]));

    // Transfer Receipt QR Code
    if (qrUrl) {
      body.appendChild(PP.el('div', {
        class: 'glass-card',
        style: 'display:flex;flex-direction:column;align-items:center;padding:1rem;background:#ffffff;border-radius:14px;margin:0 auto;max-width:200px;box-shadow:0 4px 16px rgba(0,0,0,0.3)'
      }, [
        PP.el('img', {
          src: qrUrl,
          alt: 'Transfer Receipt QR',
          style: 'width:150px;height:150px;display:block;border-radius:8px;object-fit:contain',
          onerror: function() { this.src = `/api/qr?content=${encodeURIComponent('https://pocketpay-1.onrender.com/qr/tx/' + (r.transaction_id || ''))}&size=250`; }
        }),
        PP.el('div', {
          style: 'font-size:0.72rem;font-weight:700;color:#0a0b14;margin-top:6px;text-align:center'
        }, ['Official Receipt QR']),
      ]));
    }

    // Detail Rows
    const rows = [
      { label: 'Transaction ID', value: r.transaction_id, copyable: true },
      { label: 'Date & Time', value: r.date_formatted || r.created_at || 'Recent' },
      r.sender?.name ? { label: 'Sender', value: `${r.sender.name} (${r.sender.source || 'Wallet'})` } : null,
      r.recipient?.name ? { label: 'Recipient', value: `${r.recipient.name} (${r.recipient.destination || 'Wallet'})` } : null,
      r.merchant ? { label: 'Merchant / Payee', value: r.merchant } : null,
      r.category ? { label: 'Category', value: r.category } : null,
      r.payment_method ? { label: 'Payment Method', value: String(r.payment_method).toUpperCase() } : null,
      r.description ? { label: 'Description', value: r.description } : null,
    ].filter(Boolean);

    const detailsWrap = PP.el('div', {
      class: 'glass-card',
      style: 'padding:0.75rem 1rem;border-radius:12px;display:flex;flex-direction:column;gap:0.6rem;background:rgba(255,255,255,0.02);border:1px solid var(--border)'
    });
    rows.forEach(rw => {
      detailsWrap.appendChild(PP.el('div', {
        style: 'display:flex;justify-content:space-between;align-items:center;font-size:0.85rem;padding:0.25rem 0'
      }, [
        PP.el('div', { style: 'color:var(--text-muted)' }, [rw.label]),
        PP.el('div', { style: 'font-weight:600;display:flex;align-items:center;gap:0.35rem;text-align:right' }, [
          PP.el('span', {}, [rw.value]),
          rw.copyable ? PP.el('button', {
            type: 'button',
            class: 'btn-icon',
            style: 'width:22px;height:22px;padding:2px',
            onclick: () => {
              navigator.clipboard?.writeText(rw.value);
              PP.UI.toast('Copied', `${rw.label} copied to clipboard`, 'info');
            }
          }, [PP.el('i', { 'data-lucide': 'copy', style: 'width:12px;height:12px' })]) : null
        ].filter(Boolean))
      ]));
    });
    body.appendChild(detailsWrap);

    modal.body.innerHTML = '';
    modal.body.appendChild(body);

    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Close']));

    if (qrUrl) {
      modal.footer.appendChild(PP.el('button', {
        class: 'btn btn-outline',
        onclick: () => {
          const a = document.createElement('a');
          a.href = qrUrl;
          a.download = `PocketPay_Receipt_${r.transaction_id || 'transfer'}.png`;
          a.click();
          PP.UI.toast('Saved', 'Transfer receipt downloaded', 'success');
        }
      }, [PP.el('i', { 'data-lucide': 'download' }), 'Save QR']));
    }

    modal.footer.appendChild(PP.el('button', {
      class: 'btn btn-primary',
      onclick: () => window.print()
    }, [PP.el('i', { 'data-lucide': 'printer' }), 'Print Receipt']));

    PP.refreshIcons();
  },

  transactionDetail(t) {
    if (!t) return;
    return this.transactionReceiptModal(t);
  },

  // =========================================================================
  // PIN & SECURITY HELPERS
  // =========================================================================
  setPin(opts = {}) {
    return this.setupPin(opts);
  },

  async promptPin(opts = {}) {
    const auth = await PP.UI.pinPrompt({
      title: opts.title || 'Enter Transaction PIN',
      subtitle: opts.subtitle || (opts.amount ? `Authorizing ₹${Number(opts.amount).toLocaleString('en-IN', {minimumFractionDigits:2})}` : 'Enter your 4-digit PIN')
    });
    if (auth && typeof opts.onConfirm === 'function') {
      opts.onConfirm(auth);
    } else if (!auth && typeof opts.onCancel === 'function') {
      opts.onCancel();
    }
    return auth;
  },

  // =========================================================================
  // PEER-TO-PEER (P2P): SEND MONEY MODAL
  // =========================================================================
  async sendMoney(opts = {}) {
    const user = PP.state.user;
    if (!user) return;
    const pockets = (PP.state.pockets || []).filter(p => !p.archived && (p.current_balance || 0) > 0);

    const modal = PP.UI.modal({
      title: 'Send Money',
      subtitle: 'Transfer funds instantly to any PocketPay user',
      icon: 'send',
      iconClass: 'bg-accent',
      size: 'md'
    });

    let recipientInput = opts.recipient || '';
    let resolvedUser = null;
    let searching = false;
    let searchError = '';
    let amountVal = opts.amount ? Number(opts.amount) : 0;
    let selectedSource = 'wallet'; // 'wallet' or pocketId
    let noteVal = opts.note || '';
    let isSubmitting = false;

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.25rem' });

    // Status / verification container (updated dynamically without touching the input)
    const searchStatusEl = PP.el('div', { id: 'recipientSearchStatus' });

    const updateStatus = () => {
      searchStatusEl.innerHTML = '';
      if (searching) {
        searchStatusEl.appendChild(PP.el('div', {
          style: 'font-size:0.8rem;color:var(--accent);display:flex;align-items:center;gap:0.4rem;margin-top:0.4rem'
        }, [
          PP.el('i', { 'data-lucide': 'loader-2', style: 'width:14px;height:14px;animation:slowSpin 1s linear infinite' }),
          'Searching PocketPay network…'
        ]));
      } else if (resolvedUser) {
        searchStatusEl.appendChild(PP.el('div', {
          class: 'glass-card',
          style: 'display:flex;align-items:center;gap:0.75rem;padding:0.75rem 1rem;background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:12px;margin-top:0.5rem'
        }, [
          PP.el('div', {
            class: 'avatar gradient-avatar',
            style: 'width:38px;height:38px;font-size:1rem;flex-shrink:0'
          }, [resolvedUser.full_name?.charAt(0)?.toUpperCase() || 'U']),
          PP.el('div', { style: 'flex:1;min-width:0' }, [
            PP.el('div', { style: 'font-weight:700;font-size:0.95rem;color:var(--text)' }, [resolvedUser.full_name]),
            PP.el('div', { style: 'font-size:0.78rem;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis' }, [
              resolvedUser.virtual_upi_id || resolvedUser.masked_email
            ])
          ]),
          PP.el('span', { class: 'chip success' }, [
            PP.el('i', { 'data-lucide': 'check-circle-2', style: 'width:12px;height:12px' }),
            'Verified User'
          ])
        ]));
      } else if (searchError && recipientInput.trim().length >= 2) {
        searchStatusEl.appendChild(PP.el('div', {
          style: 'font-size:0.8rem;color:var(--danger);display:flex;align-items:center;gap:0.4rem;margin-top:0.4rem'
        }, [
          PP.el('i', { 'data-lucide': 'alert-circle', style: 'width:14px;height:14px' }),
          searchError
        ]));
      }
      PP.refreshIcons();
    };

    const doSearch = PP.debounce(async (val) => {
      const q = val?.trim();
      if (!q || q.length < 2) {
        resolvedUser = null;
        searchError = '';
        searching = false;
        updateStatus();
        return;
      }
      searching = true;
      searchError = '';
      updateStatus();
      try {
        const res = await PP.WalletAPI.searchUser(q);
        resolvedUser = res.data?.user || null;
        searchError = '';
      } catch (err) {
        resolvedUser = null;
        searchError = err.message || 'User not found';
      } finally {
        searching = false;
        updateStatus();
      }
    }, 350);

    // 1. Recipient Search Input (created once, never destroyed on typing/search)
    const recipientInp = PP.el('input', {
      class: 'form-input',
      id: 'sendMoneyRecipientInput',
      placeholder: 'e.g. arjun@pocketpay.app, +919876543210, user@pocketpay',
      value: recipientInput
    });
    recipientInp.oninput = (e) => {
      recipientInput = e.target.value;
      doSearch(recipientInput);
    };

    const searchGrp = PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Send To (Email, Phone, UPI ID, or Wallet ID) *']),
      recipientInp,
      searchStatusEl
    ]);
    body.appendChild(searchGrp);

    // 2. Amount Input & Quick Chips
    const amtInp = PP.el('input', {
      type: 'number',
      step: '0.01',
      min: '1',
      class: 'form-input',
      style: 'font-size:1.25rem;font-weight:700',
      placeholder: '0.00',
      value: amountVal || ''
    });
    amtInp.oninput = (e) => amountVal = parseFloat(e.target.value) || 0;

    const amtGrp = PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Amount to Send *']),
      amtInp,
      PP.el('div', { class: 'quick-chips', style: 'display:flex;gap:0.4rem;margin-top:0.5rem;flex-wrap:wrap' }, [
        ...[100, 250, 500, 1000, 2000, 5000].map(v => {
          const btn = PP.el('button', {
            type: 'button',
            class: 'chip',
            style: 'cursor:pointer;background:var(--surface-2);border:1px solid var(--border)',
            onclick: () => {
              amountVal = v;
              amtInp.value = v;
            }
          }, [`₹${v}`]);
          return btn;
        })
      ])
    ]);
    body.appendChild(amtGrp);

    // 3. Source Selection (Wallet or Pocket)
    const srcSel = PP.el('select', { class: 'form-select' });
    const walletOpt = PP.el('option', { value: 'wallet' }, [`💳 Available Balance (₹${(user.wallet_balance || 0).toLocaleString('en-IN', {minimumFractionDigits:2})})`]);
    if (selectedSource === 'wallet') walletOpt.selected = true;
    srcSel.appendChild(walletOpt);

    pockets.forEach(p => {
      const opt = PP.el('option', { value: p.id }, [`📁 ${p.name} (₹${(p.current_balance || 0).toLocaleString('en-IN', {minimumFractionDigits:2})})`]);
      if (String(selectedSource) === String(p.id)) opt.selected = true;
      srcSel.appendChild(opt);
    });

    srcSel.onchange = (e) => selectedSource = e.target.value;

    const srcGrp = PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Payment Source']),
      srcSel
    ]);
    body.appendChild(srcGrp);

    // 4. Note (optional)
    const noteInp = PP.el('input', {
      type: 'text',
      class: 'form-input',
      placeholder: 'e.g. Lunch split, Trip contribution, Birthday gift',
      maxlength: 100,
      value: noteVal
    });
    noteInp.oninput = (e) => noteVal = e.target.value;

    body.appendChild(PP.el('div', { class: 'form-group' }, [
      PP.el('label', { class: 'form-label' }, ['Note / Reference (optional)']),
      noteInp
    ]));

    modal.body.innerHTML = '';
    modal.body.appendChild(body);

    // Footer
    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', {
      class: 'btn btn-ghost',
      onclick: () => modal.close()
    }, ['Cancel']));

    const submitBtn = PP.el('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        if (isSubmitting) return;

        const targetIdent = recipientInput.trim();
        if (!targetIdent) {
          return PP.UI.toast('Recipient Required', 'Please enter a recipient email, phone, or UPI ID', 'warning');
        }
        if (!amountVal || amountVal <= 0) {
          return PP.UI.toast('Invalid Amount', 'Please enter an amount greater than ₹0 (minimum ₹1.00)', 'warning');
        }
        if (amountVal < 1.0) {
          return PP.UI.toast('Minimum Amount', 'Minimum transfer amount is ₹1.00', 'warning');
        }

        // Check balance before asking for PIN
        let available = user.wallet_balance || 0;
        if (selectedSource !== 'wallet') {
          const p = pockets.find(x => String(x.id) === String(selectedSource));
          available = p?.current_balance || 0;
        }
        if (available < amountVal) {
          return PP.UI.toast('Insufficient Balance', `You only have ₹${available.toLocaleString('en-IN', {minimumFractionDigits:2})} in selected source`, 'error');
        }

        // Check if user has transaction PIN configured
        const hasPin = Boolean(user.has_transaction_pin || user.has_pin || user.transaction_pin_hash);
        if (!hasPin) {
          PP.UI.toast('PIN Required', 'Please configure your 4-digit transaction PIN first', 'info');
          return PP.Modals.setupPin();
        }

        // Prompt PIN & optional TOTP via robust PP.UI.pinPrompt
        const auth = await PP.UI.pinPrompt({
          title: 'Confirm Payment',
          subtitle: `Authorizing ₹${amountVal.toLocaleString('en-IN', {minimumFractionDigits:2})} to ${resolvedUser?.full_name || targetIdent}`
        });
        if (!auth) return; // User cancelled or exited

        const pinStr = typeof auth === 'object' && auth !== null ? auth.pin : String(auth);
        const totpCode = typeof auth === 'object' && auth !== null ? auth.totp_code : null;

        isSubmitting = true;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Processing Transfer…';
        PP.refreshIcons();

        try {
          const res = await PP.WalletAPI.sendMoney({
            recipient: targetIdent,
            amount: amountVal,
            pocket_id: selectedSource === 'wallet' ? null : parseInt(selectedSource),
            note: noteVal,
            pin: pinStr,
            totp_code: totpCode
          });

          modal.close();
          if (PP.bootstrap) {
            try { await PP.bootstrap(true); } catch {}
          } else {
            PP.renderView?.();
          }

          // Render comprehensive Payment Successful Receipt Modal with scannable QR
          PP.Modals.showTransferReceipt({
            transaction: res.data?.transaction,
            recipient: res.data?.recipient,
            amount: amountVal,
            wallet_balance: res.data?.wallet_balance,
            pocket_balance: res.data?.pocket_balance,
            receipt_qr: res.data?.receipt_qr || res.data?.transaction?.qr_code_url,
            source_name: selectedSource === 'wallet' ? 'PocketPay Wallet' : (pockets.find(x => String(x.id) === String(selectedSource))?.name || 'Funding Pocket'),
            note: noteVal,
            resolvedUser: resolvedUser
          });
        } catch (err) {
          const msg = err.data?.message || err.data?.error || err.message || 'Payment could not be processed';
          PP.UI.toast('Transfer Failed', msg, 'error');
        } finally {
          isSubmitting = false;
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<i data-lucide="send"></i> Send Money';
          PP.refreshIcons();
        }
      }
    }, [PP.el('i', { 'data-lucide': 'send' }), 'Send Money']);
    modal.footer.appendChild(submitBtn);

    PP.refreshIcons();
    if (recipientInput) doSearch(recipientInput);
  },

  // =========================================================================
  // PEER-TO-PEER (P2P): REQUEST MONEY MODAL
  // =========================================================================
  async requestMoney(opts = {}) {
    const user = PP.state.user;
    if (!user) return;

    const modal = PP.UI.modal({
      title: 'Request Money',
      subtitle: 'Send a payment request to another PocketPay user',
      icon: 'hand-coins',
      iconClass: 'bg-info',
      size: 'md'
    });

    let recipientInput = opts.recipient || '';
    let resolvedUser = null;
    let searching = false;
    let searchError = '';
    let amountVal = opts.amount ? Number(opts.amount) : 0;
    let noteVal = opts.note || '';

    const doSearch = PP.debounce(async (val) => {
      const q = val?.trim();
      if (!q || q.length < 2) {
        resolvedUser = null;
        searchError = '';
        searching = false;
        render();
        return;
      }
      searching = true;
      searchError = '';
      render();
      try {
        const res = await PP.WalletAPI.searchUser(q);
        resolvedUser = res.data?.user || null;
        searchError = '';
      } catch (err) {
        resolvedUser = null;
        searchError = err.message || 'User not found';
      } finally {
        searching = false;
        render();
      }
    }, 350);

    const render = () => {
      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.25rem' });

      // 1. Recipient Search
      const searchGrp = PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Request From (Email, Phone, UPI ID, or Wallet ID) *']),
        (() => {
          const inp = PP.el('input', {
            class: 'form-input',
            placeholder: 'e.g. friend@pocketpay.app, +919876543210',
            value: recipientInput
          });
          inp.oninput = (e) => {
            recipientInput = e.target.value;
            doSearch(recipientInput);
          };
          return inp;
        })()
      ]);

      if (searching) {
        searchGrp.appendChild(PP.el('div', {
          style: 'font-size:0.8rem;color:var(--accent);display:flex;align-items:center;gap:0.4rem;margin-top:0.4rem'
        }, [
          PP.el('i', { 'data-lucide': 'loader-2', style: 'width:14px;height:14px;animation:slowSpin 1s linear infinite' }),
          'Searching PocketPay network…'
        ]));
      } else if (resolvedUser) {
        searchGrp.appendChild(PP.el('div', {
          class: 'glass-card',
          style: 'display:flex;align-items:center;gap:0.75rem;padding:0.75rem 1rem;background:rgba(14,165,233,0.08);border:1px solid rgba(14,165,233,0.25);border-radius:12px;margin-top:0.5rem'
        }, [
          PP.el('div', {
            class: 'avatar gradient-avatar',
            style: 'width:38px;height:38px;font-size:1rem;flex-shrink:0'
          }, [resolvedUser.full_name?.charAt(0)?.toUpperCase() || 'U']),
          PP.el('div', { style: 'flex:1;min-width:0' }, [
            PP.el('div', { style: 'font-weight:700;font-size:0.95rem;color:var(--text)' }, [resolvedUser.full_name]),
            PP.el('div', { style: 'font-size:0.78rem;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis' }, [
              resolvedUser.virtual_upi_id || resolvedUser.masked_email
            ])
          ]),
          PP.el('span', { class: 'chip info' }, ['Verified User'])
        ]));
      } else if (searchError && recipientInput.trim().length >= 2) {
        searchGrp.appendChild(PP.el('div', {
          style: 'font-size:0.8rem;color:var(--danger);display:flex;align-items:center;gap:0.4rem;margin-top:0.4rem'
        }, [
          PP.el('i', { 'data-lucide': 'alert-circle', style: 'width:14px;height:14px' }),
          searchError
        ]));
      }
      body.appendChild(searchGrp);

      // 2. Amount Input
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Amount to Request *']),
        (() => {
          const inp = PP.el('input', {
            type: 'number',
            step: '0.01',
            min: '1',
            class: 'form-input',
            style: 'font-size:1.25rem;font-weight:700',
            placeholder: '0.00',
            value: amountVal || ''
          });
          inp.oninput = (e) => amountVal = parseFloat(e.target.value) || 0;
          return inp;
        })()
      ]));

      // 3. Note
      body.appendChild(PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Purpose / Note *']),
        (() => {
          const inp = PP.el('input', {
            type: 'text',
            class: 'form-input',
            placeholder: 'e.g. Dinner bill split, Grocery share, Cab fare',
            maxlength: 100,
            value: noteVal
          });
          inp.oninput = (e) => noteVal = e.target.value;
          return inp;
        })()
      ]));

      modal.body.innerHTML = '';
      modal.body.appendChild(body);

      // Footer
      modal.footer.innerHTML = '';
      modal.footer.appendChild(PP.el('button', {
        class: 'btn btn-ghost',
        onclick: () => modal.close()
      }, ['Cancel']));

      const submitBtn = PP.el('button', {
        class: 'btn btn-primary',
        onclick: async () => {
          if (!recipientInput.trim()) {
            return PP.UI.toast('Recipient Required', 'Please enter user email, phone, or UPI ID', 'warning');
          }
          if (!amountVal || amountVal <= 0) {
            return PP.UI.toast('Invalid Amount', 'Please enter an amount greater than ₹0', 'warning');
          }
          if (!noteVal.trim()) {
            return PP.UI.toast('Note Required', 'Please specify a brief note for the request', 'warning');
          }

          submitBtn.disabled = true;
          submitBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Sending Request…';
          PP.refreshIcons();
          try {
            await PP.WalletAPI.requestMoney({
              recipient: recipientInput.trim(),
              amount: amountVal,
              note: noteVal.trim()
            });

            modal.close();
            PP.UI.toast('Request Sent', `Money request for ₹${amountVal.toLocaleString('en-IN', {minimumFractionDigits:2})} sent to ${resolvedUser?.full_name || recipientInput}`, 'success');
            await PP.loadState?.();
            PP.renderView?.();
          } catch (err) {
            PP.UI.toast('Request Failed', err.message || 'Could not send money request', 'error');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i data-lucide="hand-coins"></i> Send Request';
            PP.refreshIcons();
          }
        }
      }, [PP.el('i', { 'data-lucide': 'hand-coins' }), 'Send Request']);
      modal.footer.appendChild(submitBtn);

      PP.refreshIcons();
    };

    render();
    if (recipientInput) doSearch(recipientInput);
  },

  // =========================================================================
  // PEER-TO-PEER (P2P): MONEY REQUESTS MANAGER MODAL
  // =========================================================================
  async moneyRequests(defaultTab = 'incoming') {
    const user = PP.state.user;
    if (!user) return;

    const modal = PP.UI.modal({
      title: 'Money Requests',
      subtitle: 'Manage received and sent payment requests',
      icon: 'arrow-down-left',
      iconClass: 'bg-accent',
      size: 'lg'
    });

    let currentTab = defaultTab;
    let requests = [];
    let loading = true;

    const loadData = async () => {
      loading = true;
      render();
      try {
        const res = await PP.WalletAPI.listRequests({ type: currentTab });
        requests = res.data?.requests || [];
      } catch (err) {
        PP.UI.toast('Error', 'Failed to load money requests', 'error');
        requests = [];
      } finally {
        loading = false;
        render();
      }
    };

    const render = () => {
      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' });

      // Tab switcher
      const tabWrap = PP.el('div', {
        style: 'display:flex;gap:0.5rem;background:var(--surface-2);padding:4px;border-radius:12px;border:1px solid var(--border)'
      }, [
        PP.el('button', {
          class: `btn btn-sm ${currentTab === 'incoming' ? 'btn-primary' : 'btn-ghost'}`,
          style: 'flex:1;font-weight:600',
          onclick: () => { currentTab = 'incoming'; loadData(); }
        }, ['📥 Incoming Requests']),
        PP.el('button', {
          class: `btn btn-sm ${currentTab === 'outgoing' ? 'btn-primary' : 'btn-ghost'}`,
          style: 'flex:1;font-weight:600',
          onclick: () => { currentTab = 'outgoing'; loadData(); }
        }, ['📤 Sent Requests'])
      ]);
      body.appendChild(tabWrap);

      if (loading) {
        body.appendChild(PP.el('div', {
          style: 'padding:2.5rem;text-align:center;color:var(--text-muted)'
        }, [
          PP.el('i', { 'data-lucide': 'loader-2', style: 'width:28px;height:28px;animation:slowSpin 1s linear infinite;margin-bottom:0.5rem' }),
          PP.el('p', {}, ['Loading money requests…'])
        ]));
      } else if (!requests.length) {
        body.appendChild(PP.el('div', {
          class: 'empty-state',
          style: 'padding:2.5rem 1rem;text-align:center'
        }, [
          PP.el('div', {
            style: 'width:56px;height:56px;border-radius:16px;background:rgba(99,102,241,0.12);color:var(--accent);display:flex;align-items:center;justify-content:center;margin:0 auto 1rem'
          }, [PP.el('i', { 'data-lucide': currentTab === 'incoming' ? 'inbox' : 'send', style: 'width:28px;height:28px' })]),
          PP.el('h4', { style: 'font-weight:700;margin-bottom:0.35rem' }, [currentTab === 'incoming' ? 'No incoming requests' : 'No outgoing requests']),
          PP.el('p', { style: 'color:var(--text-muted);font-size:0.85rem;max-width:320px;margin:0 auto 1rem' }, [
            currentTab === 'incoming'
              ? 'When other PocketPay users request money from you, they will appear here.'
              : 'You have not sent any pending money requests yet.'
          ]),
          PP.el('button', {
            class: 'btn btn-primary btn-sm',
            onclick: () => { modal.close(); PP.Modals.requestMoney(); }
          }, [PP.el('i', { 'data-lucide': 'plus' }), 'Request Money'])
        ]));
      } else {
        const list = PP.el('div', { style: 'display:flex;flex-direction:column;gap:0.75rem;max-height:420px;overflow-y:auto;padding-right:4px' });

        requests.forEach(req => {
          const isPending = req.status === 'pending';
          const isIncoming = currentTab === 'incoming';
          const otherName = isIncoming ? req.requester_name : req.target_user_name;
          const otherUpi = isIncoming ? (req.requester_upi || req.requester_email) : (req.target_user_upi || req.target_user_email);

          const card = PP.el('div', {
            class: 'glass-card',
            style: `display:flex;flex-direction:column;gap:0.6rem;padding:1rem;border-radius:14px;border:1px solid ${isPending ? 'rgba(99,102,241,0.25)' : 'var(--border)'}`
          }, [
            PP.el('div', { style: 'display:flex;justify-content:space-between;align-items:flex-start;gap:0.75rem' }, [
              PP.el('div', { style: 'display:flex;align-items:center;gap:0.65rem' }, [
                PP.el('div', {
                  class: 'avatar gradient-avatar',
                  style: 'width:38px;height:38px;font-size:0.95rem;flex-shrink:0'
                }, [otherName?.charAt(0)?.toUpperCase() || 'U']),
                PP.el('div', {}, [
                  PP.el('div', { style: 'font-weight:700;font-size:0.95rem' }, [
                    isIncoming ? `Request from ${otherName}` : `Requested from ${otherName}`
                  ]),
                  PP.el('div', { style: 'font-size:0.75rem;color:var(--text-muted)' }, [otherUpi || 'PocketPay User'])
                ])
              ]),
              PP.el('div', { style: 'text-align:right' }, [
                PP.el('div', { style: 'font-size:1.15rem;font-weight:800;font-family:var(--font-display);color:var(--text)' }, [
                  `₹${(req.amount || 0).toLocaleString('en-IN', {minimumFractionDigits:2})}`
                ]),
                PP.el('span', {
                  class: `chip ${req.status === 'paid' ? 'success' : (req.status === 'declined' ? 'danger' : 'warning')}`,
                  style: 'margin-top:0.25rem;font-size:0.7rem'
                }, [req.status?.toUpperCase()])
              ])
            ]),
            req.note ? PP.el('div', {
              style: 'font-size:0.83rem;color:var(--text-muted);background:rgba(255,255,255,0.03);padding:0.4rem 0.65rem;border-radius:8px'
            }, [`💬 "${req.note}"`]) : null,
            PP.el('div', {
              style: 'display:flex;justify-content:space-between;align-items:center;font-size:0.75rem;color:var(--text-dim);margin-top:0.2rem'
            }, [
              PP.el('span', {}, [PP.formatDateTime ? PP.formatDateTime(req.created_at) : String(req.created_at || '')]),
              (isIncoming && isPending) ? PP.el('div', { style: 'display:flex;gap:0.4rem' }, [
                PP.el('button', {
                  class: 'btn btn-danger btn-sm',
                  style: 'padding:0.35rem 0.75rem;font-size:0.78rem',
                  onclick: async () => {
                    if (!confirm(`Decline request of ₹${req.amount} from ${otherName}?`)) return;
                    try {
                      await PP.WalletAPI.declineRequest(req.id);
                      PP.UI.toast('Declined', 'Money request declined', 'info');
                      loadData();
                    } catch (err) {
                      PP.UI.toast('Error', err.message || 'Could not decline request', 'error');
                    }
                  }
                }, ['Decline']),
                PP.el('button', {
                  class: 'btn btn-primary btn-sm',
                  style: 'padding:0.35rem 0.9rem;font-size:0.78rem',
                  onclick: () => {
                    PP.Modals.promptPin({
                      title: 'Pay Money Request',
                      subtitle: `Paying ₹${req.amount.toLocaleString('en-IN', {minimumFractionDigits:2})} to ${otherName}`,
                      amount: req.amount,
                      requireTotp: !!user.totp_enabled,
                      onConfirm: async (authPayload) => {
                        try {
                          await PP.WalletAPI.payRequest(req.id, authPayload.pin, { totp_code: authPayload.totp_code });
                          modal.close();
                          await PP.loadState?.();
                          PP.renderView?.();
                          PP.UI.showSuccess({
                            title: 'Request Paid Successfully!',
                            sub: `₹${req.amount.toLocaleString('en-IN', {minimumFractionDigits:2})} sent to ${otherName}`,
                            meta: [
                              { label: 'Paid To', value: otherName },
                              { label: 'Amount', value: `₹${req.amount.toLocaleString('en-IN', {minimumFractionDigits:2})}` },
                              { label: 'Note', value: req.note || 'Payment Request' }
                            ]
                          });
                        } catch (err) {
                          PP.UI.toast('Payment Failed', err.message || 'Could not pay request', 'error');
                        }
                      }
                    });
                  }
                }, [PP.el('i', { 'data-lucide': 'check' }), 'Pay Now'])
              ]) : null
            ].filter(Boolean))
          ].filter(Boolean));

          list.appendChild(card);
        });

        body.appendChild(list);
      }

      modal.body.innerHTML = '';
      modal.body.appendChild(body);

      modal.footer.innerHTML = '';
      modal.footer.appendChild(PP.el('button', {
        class: 'btn btn-ghost',
        onclick: () => modal.close()
      }, ['Close']));

      modal.footer.appendChild(PP.el('button', {
        class: 'btn btn-primary',
        onclick: () => { modal.close(); PP.Modals.requestMoney(); }
      }, [PP.el('i', { 'data-lucide': 'plus' }), 'New Request']));

      PP.refreshIcons();
    };

    loadData();
  },

  // =========================================================================
  // NOTIFICATIONS CENTER MODAL
  // =========================================================================
  async notifications() {
    const modal = PP.UI.modal({
      title: 'Notifications',
      subtitle: 'Activity, transactions, and security alerts',
      icon: 'bell',
      iconClass: 'bg-accent',
      size: 'md'
    });

    let notifs = [];
    let loading = true;

    const loadData = async () => {
      loading = true;
      render();
      try {
        const res = await PP.AnalyticsAPI.notifications({ limit: 40 });
        notifs = res.data?.items || [];
      } catch (err) {
        notifs = PP.state.notifications || [];
      } finally {
        loading = false;
        render();
      }
    };

    const render = () => {
      const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:0.75rem' });

      // Actions Header
      body.appendChild(PP.el('div', {
        style: 'display:flex;justify-content:space-between;align-items:center;margin-bottom:0.25rem'
      }, [
        PP.el('span', { style: 'font-size:0.8rem;color:var(--text-muted);font-weight:600' }, [
          `${notifs.filter(n => !n.is_read).length} unread alerts`
        ]),
        PP.el('button', {
          type: 'button',
          class: 'btn btn-ghost btn-sm',
          style: 'font-size:0.75rem;padding:0.2rem 0.5rem',
          onclick: async () => {
            try {
              await PP.AnalyticsAPI.readAll();
              notifs.forEach(n => n.is_read = true);
              const badge = PP.$('#notifBadge');
              if (badge) badge.classList.add('hidden');
              render();
              PP.UI.toast('Marked Read', 'All notifications marked as read', 'info');
            } catch (err) {
              PP.UI.toast('Error', 'Failed to mark all as read', 'error');
            }
          }
        }, ['Mark all as read'])
      ]));

      if (loading) {
        body.appendChild(PP.el('div', { style: 'padding:2rem;text-align:center;color:var(--text-muted)' }, [
          PP.el('i', { 'data-lucide': 'loader-2', style: 'width:24px;height:24px;animation:slowSpin 1s linear infinite' })
        ]));
      } else if (!notifs.length) {
        body.appendChild(PP.el('div', {
          class: 'empty-state',
          style: 'padding:2.5rem 1rem;text-align:center'
        }, [
          PP.el('div', {
            style: 'width:48px;height:48px;border-radius:14px;background:rgba(99,102,241,0.12);color:var(--accent);display:flex;align-items:center;justify-content:center;margin:0 auto 0.75rem'
          }, [PP.el('i', { 'data-lucide': 'bell-off', style: 'width:24px;height:24px' })]),
          PP.el('h4', { style: 'font-weight:700;margin-bottom:0.25rem' }, ['All caught up!']),
          PP.el('p', { style: 'color:var(--text-muted);font-size:0.85rem' }, ['No notifications or alerts right now.'])
        ]));
      } else {
        const list = PP.el('div', {
          style: 'display:flex;flex-direction:column;gap:0.5rem;max-height:420px;overflow-y:auto;padding-right:4px'
        });

        notifs.forEach(n => {
          const isUnread = !n.is_read;
          let iconName = 'info';
          let iconColor = 'var(--info)';
          if (n.type === 'success' || (n.title && n.title.includes('Success'))) { iconName = 'check-circle'; iconColor = 'var(--success)'; }
          else if (n.type === 'warning' || (n.title && n.title.includes('Alert')) || (n.title && n.title.includes('Budget'))) { iconName = 'alert-triangle'; iconColor = 'var(--warning)'; }
          else if (n.type === 'danger' || (n.title && n.title.includes('Failed'))) { iconName = 'alert-circle'; iconColor = 'var(--danger)'; }
          else if (n.title && (n.title.includes('Received') || n.title.includes('Sent'))) { iconName = 'arrow-left-right'; iconColor = 'var(--accent)'; }

          const item = PP.el('div', {
            class: 'glass-card',
            style: `display:flex;align-items:flex-start;gap:0.75rem;padding:0.75rem 1rem;border-radius:12px;cursor:pointer;transition:all .2s;${isUnread ? 'background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.25);' : 'background:rgba(255,255,255,0.02);border:1px solid var(--border);'}`,
            onclick: async () => {
              if (isUnread) {
                try {
                  await PP.AnalyticsAPI.markRead(n.id);
                  n.is_read = true;
                  render();
                } catch {}
              }
            }
          }, [
            PP.el('div', {
              style: `width:34px;height:34px;border-radius:10px;background:rgba(255,255,255,0.06);color:${iconColor};display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px`
            }, [PP.el('i', { 'data-lucide': iconName, style: 'width:18px;height:18px' })]),
            PP.el('div', { style: 'flex:1;min-width:0' }, [
              PP.el('div', { style: 'display:flex;justify-content:space-between;align-items:center;gap:0.5rem' }, [
                PP.el('h5', { style: `font-weight:700;font-size:0.88rem;color:${isUnread ? 'var(--text)' : 'var(--text-muted)'}` }, [n.title]),
                isUnread ? PP.el('span', { style: 'width:8px;height:8px;border-radius:50%;background:var(--accent);flex-shrink:0' }) : null
              ].filter(Boolean)),
              PP.el('p', { style: 'font-size:0.8rem;color:var(--text-muted);margin:0.2rem 0 0.35rem;line-height:1.35' }, [n.message]),
              PP.el('span', { style: 'font-size:0.72rem;color:var(--text-dim)' }, [
                PP.formatTimeAgo ? PP.formatTimeAgo(n.created_at) : String(n.created_at || '')
              ])
            ])
          ]);

          list.appendChild(item);
        });

        body.appendChild(list);
      }

      modal.body.innerHTML = '';
      modal.body.appendChild(body);

      modal.footer.innerHTML = '';
      modal.footer.appendChild(PP.el('button', {
        class: 'btn btn-ghost',
        onclick: () => modal.close()
      }, ['Close']));

      PP.refreshIcons();
    };

    loadData();
  },

  // =========================================================================
  // SAVINGS GOALS: CREATE & FUND MODALS (Phase 11)
  // =========================================================================
  async createGoal(existing = null) {
    const editing = !!existing;
    let nameVal = editing ? existing.name : '';
    let targetVal = editing ? existing.target_amount : '';
    let dateVal = editing ? (existing.target_date || '') : '';
    let categoryVal = editing ? (existing.category || 'General') : 'General';
    let colorVal = editing ? (existing.color || '#6366f1') : '#6366f1';

    const modal = PP.UI.modal({
      title: editing ? 'Edit Savings Goal' : 'Create Savings Goal',
      subtitle: 'Set a target and track your progress to financial milestones',
      icon: 'target',
      iconClass: 'bg-accent',
      size: 'md'
    });

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' }, [
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Goal Name *']),
        (() => {
          const inp = PP.el('input', { class: 'form-input', placeholder: 'e.g. New Laptop, Emergency Fund, Vacation', value: nameVal });
          inp.oninput = () => nameVal = inp.value;
          return inp;
        })()
      ]),
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Target Amount (₹) *']),
        (() => {
          const inp = PP.el('input', { type: 'number', class: 'form-input', placeholder: 'e.g. 50000', value: targetVal });
          inp.oninput = () => targetVal = inp.value;
          return inp;
        })()
      ]),
      PP.el('div', { class: 'form-row' }, [
        PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Category']),
          (() => {
            const sel = PP.el('select', { class: 'form-select' }, [
              PP.el('option', { value: 'General' }, ['General']),
              PP.el('option', { value: 'Tech & Gadgets' }, ['Tech & Gadgets']),
              PP.el('option', { value: 'Travel & Vacation' }, ['Travel & Vacation']),
              PP.el('option', { value: 'Vehicle & Auto' }, ['Vehicle & Auto']),
              PP.el('option', { value: 'Emergency Fund' }, ['Emergency Fund']),
              PP.el('option', { value: 'Education' }, ['Education']),
              PP.el('option', { value: 'Home & Real Estate' }, ['Home & Real Estate'])
            ]);
            sel.value = categoryVal;
            sel.onchange = () => categoryVal = sel.value;
            return sel;
          })()
        ]),
        PP.el('div', { class: 'form-group' }, [
          PP.el('label', { class: 'form-label' }, ['Target Date (Optional)']),
          (() => {
            const inp = PP.el('input', { type: 'date', class: 'form-input', value: dateVal });
            inp.oninput = () => dateVal = inp.value;
            return inp;
          })()
        ])
      ])
    ]);

    modal.body.innerHTML = '';
    modal.body.appendChild(body);

    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', {
      class: 'btn btn-ghost',
      onclick: () => modal.close()
    }, ['Cancel']));

    const submitBtn = PP.el('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        if (!nameVal.trim()) return PP.UI.toast('Validation Error', 'Please enter a goal name', 'warning');
        const amt = parseFloat(targetVal);
        if (!amt || amt <= 0) return PP.UI.toast('Validation Error', 'Target amount must be greater than ₹0', 'warning');

        try {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Saving...';
          const payload = {
            name: nameVal.trim(),
            target_amount: amt,
            category: categoryVal,
            target_date: dateVal || null,
            color: colorVal
          };

          if (editing) {
            await PP.GoalsAPI.update(existing.id, payload);
            PP.UI.toast('Goal Updated', `"${nameVal}" updated successfully`, 'success');
          } else {
            await PP.GoalsAPI.create(payload);
            PP.UI.toast('Goal Created', `"${nameVal}" created! Start saving now.`, 'success');
          }

          modal.close();
          await PP.loadState?.();
          PP.renderView?.();
        } catch (err) {
          PP.UI.toast('Error', err.message || 'Could not save goal', 'error');
          submitBtn.disabled = false;
          submitBtn.textContent = editing ? 'Update Goal' : 'Create Goal';
        }
      }
    }, [editing ? 'Update Goal' : 'Create Goal']);
    modal.footer.appendChild(submitBtn);
    PP.refreshIcons();
  },

  async depositGoal(goal) {
    let amountVal = '';
    let sourceVal = 'wallet';
    const pockets = PP.state.pockets || [];

    const modal = PP.UI.modal({
      title: `Add Money to "${goal.name}"`,
      subtitle: `Target: ₹${goal.target_amount.toLocaleString('en-IN')} | Saved: ₹${goal.current_amount.toLocaleString('en-IN')}`,
      icon: 'plus-circle',
      iconClass: 'bg-success',
      size: 'sm'
    });

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1rem' }, [
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Deposit Amount (₹) *']),
        (() => {
          const inp = PP.el('input', { type: 'number', class: 'form-input', placeholder: 'Enter amount to save', autofocus: true });
          inp.oninput = () => amountVal = inp.value;
          return inp;
        })()
      ]),
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Funding Source']),
        (() => {
          const sel = PP.el('select', { class: 'form-select' }, [
            PP.el('option', { value: 'wallet' }, [`Main Available Balance (₹${(PP.state.user?.wallet_balance || 0).toLocaleString('en-IN')})`]),
            ...pockets.map(p => PP.el('option', { value: String(p.id) }, [`Pocket: ${p.name} (₹${p.current_balance.toLocaleString('en-IN')})`]))
          ]);
          sel.onchange = () => sourceVal = sel.value;
          return sel;
        })()
      ])
    ]);

    modal.body.innerHTML = '';
    modal.body.appendChild(body);

    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));

    const submitBtn = PP.el('button', {
      class: 'btn btn-success',
      onclick: async () => {
        const amt = parseFloat(amountVal);
        if (!amt || amt <= 0) return PP.UI.toast('Validation Error', 'Please enter a valid amount to deposit', 'warning');

        try {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Depositing...';
          await PP.GoalsAPI.deposit(goal.id, amt, sourceVal);
          PP.UI.toast('Deposit Success', `₹${amt.toLocaleString('en-IN')} deposited to "${goal.name}"`, 'success');
          modal.close();
          await PP.loadState?.();
          PP.renderView?.();
        } catch (err) {
          PP.UI.toast('Deposit Failed', err.message || 'Could not complete deposit', 'error');
          submitBtn.disabled = false;
          submitBtn.textContent = 'Confirm Deposit';
        }
      }
    }, ['Confirm Deposit']);
    modal.footer.appendChild(submitBtn);
    PP.refreshIcons();
  },

  async editProfile() {
    const u = PP.state.user || {};
    let fullNameVal = u.full_name || '';

    const modal = PP.UI.modal({
      title: 'Edit Profile',
      subtitle: 'Update your personal details & profile info',
      icon: 'user',
      iconClass: 'bg-accent',
      size: 'sm'
    });

    const body = PP.el('div', { style: 'display:flex;flex-direction:column;gap:1.1rem' }, [
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Full Name *']),
        (() => {
          const inp = PP.el('input', { class: 'form-input', value: fullNameVal, placeholder: 'Your Name', maxlength: 100 });
          inp.oninput = () => fullNameVal = inp.value;
          return inp;
        })()
      ]),
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Email Address']),
        PP.el('div', { class: 'glass-card', style: 'padding:0.75rem 1rem;display:flex;align-items:center;justify-content:space-between;border-radius:var(--radius-md)' }, [
          PP.el('span', { style: 'font-size:0.9rem;font-weight:500' }, [u.email || '—']),
          PP.el('span', { class: 'chip ' + (u.email_verified ? 'success' : 'warning') }, [u.email_verified ? 'Verified' : 'Pending'])
        ])
      ]),
      PP.el('div', { class: 'form-group' }, [
        PP.el('label', { class: 'form-label' }, ['Virtual UPI ID']),
        PP.el('div', { class: 'glass-card', style: 'padding:0.75rem 1rem;display:flex;align-items:center;justify-content:space-between;border-radius:var(--radius-md)' }, [
          PP.el('span', { style: 'font-size:0.9rem;font-weight:600;color:var(--accent)' }, [u.virtual_upi_id || '—']),
          PP.el('button', {
            class: 'btn btn-ghost btn-sm',
            onclick: () => { navigator.clipboard?.writeText(u.virtual_upi_id || ''); PP.UI.toast('Copied', 'UPI ID copied to clipboard', 'success'); }
          }, [PP.el('i', { 'data-lucide': 'copy' })])
        ])
      ])
    ]);

    modal.body.innerHTML = '';
    modal.body.appendChild(body);

    modal.footer.innerHTML = '';
    modal.footer.appendChild(PP.el('button', { class: 'btn btn-ghost', onclick: () => modal.close() }, ['Cancel']));
    const saveBtn = PP.el('button', {
      class: 'btn btn-primary',
      onclick: async () => {
        if (!fullNameVal || fullNameVal.trim().length < 2) {
          return PP.UI.toast('Validation', 'Full name must be at least 2 characters', 'warning');
        }
        try {
          saveBtn.disabled = true;
          saveBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Saving…';
          PP.refreshIcons();
          await PP.Auth.updateProfile({ full_name: fullNameVal.trim() });
          if (PP.state.user) PP.state.user.full_name = fullNameVal.trim();
          PP.updateTopAvatar?.();
          PP.UI.toast('Profile Updated', 'Your profile details have been updated', 'success');
          modal.close();
          PP.refreshCurrentView?.();
        } catch (e) {
          PP.UI.toast('Update Failed', e.message || 'Could not update profile', 'error');
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save Changes';
        }
      }
    }, ['Save Changes']);
    modal.footer.appendChild(saveBtn);
    PP.refreshIcons();
  },

  // =========================================================================
  // TELEGRAM BOT INTEGRATION MODAL
  // =========================================================================
  async telegramIntegrationModal() {
    const modal = PP.UI.modal({
      title: 'Telegram Bot & Alerts',
      subtitle: 'Connect your PocketPay account with Telegram Bot for real-time notifications',
      icon: 'bot',
      iconClass: 'bg-info',
      size: 'md'
    });

    modal.body.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;padding:2.5rem 1rem">
        <i data-lucide="loader-2" style="width:32px;height:32px;animation:slowSpin 1s linear infinite;color:var(--accent)"></i>
      </div>
    `;
    PP.refreshIcons();

    let pollInterval = null;
    modal.onClose = () => {
      if (pollInterval) clearInterval(pollInterval);
    };

    const renderConnected = (status) => {
      if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
      modal.body.innerHTML = `
        <div class="tg-integration-box">
          <div class="tg-header">
            <div class="tg-brand">
              <div class="tg-icon-badge">
                <i data-lucide="send" style="width:22px;height:22px"></i>
              </div>
              <div>
                <h4 style="margin:0;font-size:1.05rem;font-weight:700">PocketPay Bot</h4>
                <p style="margin:0;font-size:0.82rem;color:var(--text-muted)">
                  ${status.telegram_username ? '@' + status.telegram_username : 'ID: ' + status.telegram_id}
                </p>
              </div>
            </div>
            <span class="tg-badge-connected">
              <i data-lucide="check-circle" style="width:14px;height:14px"></i> Connected
            </span>
          </div>

          <div style="background:var(--bg-card);border:1px solid var(--border);padding:1rem;border-radius:12px;display:flex;flex-direction:column;gap:0.75rem">
            <div style="display:flex;align-items:center;justify-content:space-between">
              <div>
                <b style="font-size:0.9rem">Transaction & Security Alerts</b>
                <p style="margin:0;font-size:0.78rem;color:var(--text-muted)">Instant Telegram alerts on payments, top-ups, and sign-ins</p>
              </div>
              <label class="checkbox-row" style="margin:0">
                <input type="checkbox" id="tgNotifToggle" ${status.notifications_enabled ? 'checked' : ''} />
              </label>
            </div>
          </div>

          <div style="display:flex;gap:0.6rem;flex-wrap:wrap">
            <a href="https://t.me/${status.telegram_username || 'PocketPayBot'}" target="_blank" class="btn btn-outline btn-sm" style="flex:1;display:flex;align-items:center;justify-content:center;gap:0.4rem;text-decoration:none">
              <i data-lucide="external-link" style="width:15px;height:15px"></i> Open Bot in Telegram
            </a>
            <button type="button" class="btn btn-outline btn-sm" id="tgDisconnectBtn" style="color:var(--danger);border-color:rgba(239,68,68,0.3)">
              <i data-lucide="log-out" style="width:15px;height:15px"></i> Disconnect
            </button>
          </div>
        </div>
      `;

      modal.footer.innerHTML = `
        <button type="button" class="btn btn-ghost" onclick="this.closest('.modal-overlay').close()">Close</button>
      `;

      PP.refreshIcons();

      const toggle = modal.body.querySelector('#tgNotifToggle');
      toggle?.addEventListener('change', async () => {
        try {
          const res = await PP.Auth.telegramToggleNotifications();
          PP.UI.toast('Updated', res.message || 'Notification preference saved', 'success');
        } catch (e) {
          PP.UI.toast('Error', e.message || 'Failed to update preference', 'error');
          toggle.checked = !toggle.checked;
        }
      });

      const disconnectBtn = modal.body.querySelector('#tgDisconnectBtn');
      disconnectBtn?.addEventListener('click', async () => {
        const confirmed = await PP.UI.confirm('Disconnect Telegram', 'Are you sure you want to unlink your Telegram account? You will stop receiving alerts.');
        if (!confirmed) return;
        try {
          disconnectBtn.disabled = true;
          await PP.Auth.telegramDisconnect();
          if (PP.state.user) {
            PP.state.user.telegram_linked = false;
            PP.state.user.telegram_username = null;
            PP.state.user.telegram_id = null;
          }
          PP.UI.toast('Disconnected', 'Telegram account has been unlinked', 'info');
          PP.refreshCurrentView?.();
          renderUnconnected();
        } catch (e) {
          disconnectBtn.disabled = false;
          PP.UI.toast('Error', e.message || 'Could not disconnect Telegram', 'error');
        }
      });
    };

    const renderUnconnected = async () => {
      modal.body.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:center;padding:2rem 1rem">
          <i data-lucide="loader-2" style="width:28px;height:28px;animation:slowSpin 1s linear infinite;color:var(--accent)"></i>
        </div>
      `;
      PP.refreshIcons();

      try {
        const res = await PP.Auth.telegramGenerateLinkToken();
        const data = res.data || {};
        const token = data.token || 'PKP000000';
        const directLink = data.direct_link || `https://t.me/${data.bot_username || 'PocketPayBot'}?start=link_${token}`;
        const botName = data.bot_username || 'PocketPayBot';

        modal.body.innerHTML = `
          <div style="display:flex;flex-direction:column;gap:1.25rem">
            <div style="text-align:center">
              <div class="tg-icon-badge" style="margin:0 auto 0.75rem">
                <i data-lucide="send" style="width:24px;height:24px"></i>
              </div>
              <h3 style="margin:0 0 0.35rem;font-size:1.15rem">Connect PocketPay Bot</h3>
              <p style="margin:0;font-size:0.85rem;color:var(--text-muted)">
                Receive real-time transaction notifications and access your pockets directly in Telegram.
              </p>
            </div>

            <div style="background:var(--bg-card);border:1px solid var(--border);padding:1rem;border-radius:12px;text-align:center">
              <div style="font-size:0.8rem;color:var(--text-dim);margin-bottom:0.5rem;text-transform:uppercase;letter-spacing:1px;font-weight:600">
                Single-Use Link Code (Valid 15 Mins)
              </div>
              <div class="tg-token-display" id="tgLinkCode">${token}</div>
              <div style="font-size:0.78rem;color:var(--text-dim);margin-top:0.4rem">
                Send <code>/link ${token}</code> in bot or tap button below
              </div>
            </div>

            <a href="${directLink}" target="_blank" class="btn btn-primary btn-lg btn-block" style="display:flex;align-items:center;justify-content:center;gap:0.5rem;text-decoration:none">
              <i data-lucide="send"></i> Open Telegram Bot & Link Instantly
            </a>

            <div style="background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.15);border-radius:10px;padding:0.75rem 1rem;font-size:0.82rem;color:var(--text-muted)">
              <b style="color:var(--text)">Instructions:</b><br/>
              1. Tap <b>Open Telegram Bot</b> above<br/>
              2. Tap <b>Start</b> in Telegram<br/>
              3. Your account will link automatically and this dialog will update!
            </div>
          </div>
        `;

        modal.footer.innerHTML = `
          <button type="button" class="btn btn-ghost" onclick="this.closest('.modal-overlay').close()">Cancel</button>
        `;

        PP.refreshIcons();

        // Start background polling to auto-detect when linked
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(async () => {
          try {
            const stRes = await PP.Auth.telegramStatus();
            if (stRes.data?.linked) {
              clearInterval(pollInterval);
              pollInterval = null;
              if (PP.state.user) {
                PP.state.user.telegram_linked = true;
                PP.state.user.telegram_username = stRes.data.telegram_username;
                PP.state.user.telegram_id = stRes.data.telegram_id;
              }
              PP.UI.toast('Telegram Connected!', 'Your account has been linked successfully.', 'success');
              PP.refreshCurrentView?.();
              renderConnected(stRes.data);
            }
          } catch {}
        }, 3000);

      } catch (e) {
        modal.body.innerHTML = `
          <div style="text-align:center;padding:1.5rem">
            <p style="color:var(--danger)">Failed to generate linking token: ${e.message}</p>
            <button type="button" class="btn btn-outline btn-sm" id="tgRetryBtn">Retry</button>
          </div>
        `;
        modal.body.querySelector('#tgRetryBtn')?.addEventListener('click', () => renderUnconnected());
      }
    };

    try {
      const statusRes = await PP.Auth.telegramStatus();
      if (statusRes.data?.linked) {
        renderConnected(statusRes.data);
      } else {
        await renderUnconnected();
      }
    } catch (err) {
      await renderUnconnected();
    }
  }
};



// Backward compatibility aliases
PP.Modals.setupPIN = PP.Modals.setupPin;
PP.Modals.changePIN = PP.Modals.changePin;
PP.Modals.saveRule = PP.Modals.saveDistributionRule;

PP.UI.genericModal = PP.UI.modal;



// ========== PocketPay: Context-Aware AI Assistant ==========
window.PP = window.PP || {};

PP.Assistant = {
  isOpen: false,
  messages: [],
  
  // Knowledge base and contextual prompts per route
  contextPrompts: {
    dashboard: [
      { text: 'What are Pockets?', query: 'Explain what pockets are and how they work' },
      { text: 'How to add income?', query: 'How do I add income and split it across pockets?' },
      { text: 'How to transfer money?', query: 'How do I transfer money between pockets?' },
      { text: 'How does PIN security work?', query: 'How does the 4-digit transaction PIN protect my account?' },
    ],
    pockets: [
      { text: 'How to create a pocket?', query: 'How do I create a new pocket?' },
      { text: 'How to transfer between pockets?', query: 'How do I transfer money between different pockets?' },
      { text: 'How do limits & budgets work?', query: 'How do monthly limits and budget amounts work on pockets?' },
      { text: 'Can I delete or archive a pocket?', query: 'How do I archive or delete a pocket?' },
    ],
    'pocket-detail': [
      { text: 'How to deposit here?', query: 'How do I deposit money directly into this pocket?' },
      { text: 'How to transfer from this pocket?', query: 'How do I transfer money from this pocket to another pocket?' },
      { text: 'How to spend from this pocket?', query: 'How do I make a payment or expense from this pocket?' },
      { text: 'How does budget gauge work?', query: 'Explain the budget usage gauge and spending tracker.' },
    ],
    transactions: [
      { text: 'How to export CSV?', query: 'How do I download and export my transaction history as CSV?' },
      { text: 'Can I edit or refund a transaction?', query: 'How do I edit notes or delete/refund a transaction?' },
      { text: 'How to filter transactions?', query: 'How can I filter transactions by type, pocket, or category?' },
    ],
    analytics: [
      { text: 'How is savings rate calculated?', query: 'How is my net savings and savings rate calculated?' },
      { text: 'What are category breakdowns?', query: 'How does category spending analytics work?' },
      { text: 'How do budget alerts work?', query: 'How do automatic budget threshold alerts work?' },
    ],
    budgets: [
      { text: 'How to create a budget?', query: 'How do I create a new budget limit?' },
      { text: 'What are alert thresholds?', query: 'What are the 75%, 90%, and 100% budget alert thresholds?' },
      { text: 'Can budgets repeat monthly?', query: 'How do recurring monthly and yearly budgets work?' },
    ],
    wallet: [
      { text: 'How to use Wallet QR / UPI?', query: 'How does my virtual UPI ID and QR code work?' },
      { text: 'How to top up wallet?', query: 'How do I top up my virtual wallet balance?' },
      { text: 'How to withdraw from wallet?', query: 'How do I withdraw money from my wallet?' },
      { text: 'How to save distribution rules?', query: 'What are saved income distribution rules?' },
    ],
    profile: [
      { text: 'How to change password?', query: 'How do I update my account password?' },
      { text: 'How to change transaction PIN?', query: 'How do I setup or change my 4-digit transaction PIN?' },
      { text: 'How to switch theme?', query: 'How do I switch between dark and light mode?' },
    ],
    settings: [
      { text: 'How to change transaction PIN?', query: 'How do I setup or change my 4-digit transaction PIN?' },
      { text: 'How to update profile info?', query: 'How do I update my name, email, or preferences?' },
    ],
    login: [
      { text: 'How does Email OTP work?', query: 'How does real email OTP verification work during registration?' },
      { text: 'What if OTP expires?', query: 'What should I do if my registration verification OTP expires?' },
      { text: 'How to reset password?', query: 'How do I recover my account if I forgot my password?' },
    ],
  },

  // Knowledge base responses
  knowledgeBase: [
    {
      keywords: ['pocket', 'what is', 'what are', 'organize', 'purpose'],
      title: 'Smart Pockets Overview',
      text: '<b>Pockets</b> are dedicated sub-accounts within PocketPay that let you organize your money for specific goals or expenses (e.g. Rent, Groceries, Savings, Entertainment). Each pocket tracks its own balance, income received, and spending with customizable colors and icons.',
      actions: [
        { label: 'View Pockets', icon: 'wallet-cards', fn: () => PP.navigate('pockets') },
        { label: 'Create New Pocket', icon: 'folder-plus', fn: () => PP.Modals.createPocket() },
      ]
    },
    {
      keywords: ['create pocket', 'new pocket', 'add pocket', 'make pocket'],
      title: 'Creating a Pocket',
      text: 'To create a pocket:<ol><li>Go to <b>Pockets</b> or click <b>New Pocket</b>.</li><li>Enter a pocket name (e.g. "Dining & Outings").</li><li>Pick your favorite color and icon.</li><li>(Optional) Set an initial balance, total budget, or monthly limit.</li><li>Click <b>Create Pocket</b>.</li></ol>',
      actions: [
        { label: 'Create Pocket Now', icon: 'folder-plus', fn: () => PP.Modals.createPocket() },
      ]
    },
    {
      keywords: ['transfer', 'between pocket', 'move money', 'pocket to pocket', 'from pocket'],
      title: 'Transferring Between Pockets',
      text: 'You can instantly transfer money between any two pockets:<ul><li>Click <b>Transfer</b> in the balance card, sidebar, or from any pocket\'s menu.</li><li>Select the <b>Source (From)</b> pocket and <b>Destination (To)</b> pocket.</li><li>Enter the amount and (optional) note.</li><li>Confirm with your <b>4-digit Transaction PIN</b>.</li></ul>The balances update atomically in real-time.',
      actions: [
        { label: 'Transfer Money Now', icon: 'refresh-ccw', fn: () => PP.Modals.transfer() },
      ]
    },
    {
      keywords: ['income', 'add money', 'deposit', 'salary', 'split', 'distribution', 'percentage'],
      title: 'Adding Income & Smart Splits',
      text: 'When money arrives (e.g. salary, freelance, gifts), click <b>Add Income</b>. You can allocate it in 4 ways:<ul><li><b>Single Pocket:</b> Deposit 100% directly into one pocket.</li><li><b>Percentage Split:</b> Distribute across multiple pockets using sliders (e.g. 50% Needs, 30% Wants, 20% Savings).</li><li><b>Fixed Amounts:</b> Specify exact rupee amounts per pocket.</li><li><b>Saved Rule:</b> Apply an automated distribution template.</li></ul>',
      actions: [
        { label: 'Add Income', icon: 'arrow-down-left', fn: () => PP.Modals.addIncome() },
      ]
    },
    {
      keywords: ['expense', 'payment', 'pay', 'spend', 'make payment'],
      title: 'Making Payments & Expenses',
      text: 'To record an expense:<ul><li>Click <b>Pay / Expense</b> in the top bar, sidebar, or quick actions.</li><li>Choose which pocket to pay from.</li><li>Enter the amount, category (e.g. Food, Utilities), and merchant.</li><li>Enter your <b>4-digit Transaction PIN</b> to verify.</li></ul>Your pocket balance and monthly budget tracker will update immediately.',
      actions: [
        { label: 'Make Payment', icon: 'arrow-up-right', fn: () => PP.Modals.addExpense() },
      ]
    },
    {
      keywords: ['pin', 'transaction pin', 'security', '4-digit', 'lockout'],
      title: 'Transaction PIN Security',
      text: 'Every financial movement (Expenses, Transfers, Wallet Withdrawals) is protected by your secure <b>4-digit Transaction PIN</b>.<ul><li>PINs are securely hashed and never stored in plain text.</li><li>After 5 incorrect attempts, PIN actions are automatically locked for 15 minutes to safeguard your account.</li><li>You can change your PIN anytime in <b>Settings</b>.</li></ul>',
      actions: [
        { label: 'Set / Change PIN', icon: 'shield-check', fn: () => PP.Modals.setupPin() },
      ]
    },
    {
      keywords: ['otp', 'email otp', 'verification', 'verify', 'register', 'resend'],
      title: 'Email OTP Verification',
      text: 'When registering for PocketPay:<ul><li>A secure 6-digit verification code is dispatched to your registered email address.</li><li>The code is valid for <b>5 minutes</b>.</li><li>Enter the code to verify your email and activate your account.</li><li>If the code expires, click <b>Resend Code</b> to receive a new one.</li></ul>',
      actions: []
    },
    {
      keywords: ['budget', 'limit', 'threshold', 'alert', '75', '90', '100'],
      title: 'Budgets & Spending Alerts',
      text: 'PocketPay monitors your spending dynamically:<ul><li>Create budgets tied to specific pockets or spending categories.</li><li>Set monthly limits and custom alert thresholds.</li><li>Receive automated alerts when your spending reaches <b>75%</b>, <b>90%</b>, or <b>100%</b> of your limit.</li></ul>',
      actions: [
        { label: 'View Budgets', icon: 'target', fn: () => PP.navigate('budgets') },
        { label: 'Create Budget', icon: 'plus-circle', fn: () => PP.Modals.createBudget() },
      ]
    },
    {
      keywords: ['history', 'transaction', 'csv', 'export', 'filter', 'refund', 'delete transaction', 'edit transaction'],
      title: 'Transaction History & Export',
      text: 'In the <b>Transactions</b> tab:<ul><li>Filter transactions by type (income, expense, transfer), pocket, category, or date.</li><li>Click any transaction to view details, edit merchant notes, or delete it (which automatically refunds the pocket balance).</li><li>Click <b>Export CSV</b> to download your complete ledger spreadsheet.</li></ul>',
      actions: [
        { label: 'View Transactions', icon: 'arrow-left-right', fn: () => PP.navigate('transactions') },
      ]
    },
    {
      keywords: ['wallet', 'top up', 'topup', 'withdraw', 'qr', 'upi', 'virtual upi'],
      title: 'Virtual Wallet & QR System',
      text: 'Your PocketPay account includes a virtual wallet and unique UPI ID (e.g. <code>username@pocketpay</code>):<ul><li><b>Top Up:</b> Add funds to your wallet using UPI, Card, or Netbanking.</li><li><b>Wallet QR:</b> Display or download your scannable payment QR code.</li><li><b>Withdraw:</b> Transfer funds out of your wallet securely with your PIN.</li></ul>',
      actions: [
        { label: 'Open My Wallet', icon: 'smartphone', fn: () => PP.navigate('wallet') },
      ]
    },
    {
      keywords: ['theme', 'dark mode', 'light mode', 'switch theme'],
      title: 'Theme & Customization',
      text: 'PocketPay supports both sleek Dark Mode and vibrant Light Mode. Click the <b>Moon / Sun</b> icon in the top navigation bar to toggle themes anytime.',
      actions: [
        { label: 'Toggle Theme', icon: 'sun', fn: () => {
          const cur = document.documentElement.getAttribute('data-theme') || 'dark';
          PP.setTheme(cur === 'dark' ? 'light' : 'dark');
        } },
      ]
    },
    {
      keywords: ['archive', 'delete pocket', 'restore', 'guardrail'],
      title: 'Archiving & Deleting Pockets',
      text: '<ul><li><b>Archive Pocket:</b> Hides a pocket from everyday views while preserving all historical transactions and records. You can restore it anytime.</li><li><b>Delete Pocket:</b> Safety guardrails prevent deleting pockets with an active balance. Simply transfer the remaining balance to ₹0 first, then click Delete.</li></ul>',
      actions: [
        { label: 'Manage Pockets', icon: 'wallet-cards', fn: () => PP.navigate('pockets') },
      ]
    },
  ],

  init() {
    this.renderWidget();
    this.attachEventListeners();
    this.updateContextPrompts();
    
    // Auto-update prompts when route changes
    PP.on('route:change', () => this.updateContextPrompts());
    PP.on('view:rendered', () => this.updateContextPrompts());
  },

  renderWidget() {
    // Remove any existing assistant widget
    const existing = document.getElementById('ppAssistantWidget');
    if (existing) existing.remove();

    const widget = PP.el('div', { id: 'ppAssistantWidget', class: 'assistant-widget' }, [
      // Floating launcher button
      PP.el('button', {
        id: 'assistantLauncher',
        class: 'assistant-launcher glow-pulse',
        'aria-label': 'PocketPay AI Assistant',
        title: 'Need help? Ask PocketPay Assistant',
        onclick: () => this.toggle(),
      }, [
        PP.el('div', { class: 'launcher-icon' }, [
          PP.el('i', { 'data-lucide': 'sparkles' }),
        ]),
        PP.el('span', { class: 'launcher-text hidden-xs' }, ['PocketPay Assistant']),
        PP.el('span', { class: 'launcher-badge' }, ['AI']),
      ]),

      // Chat Window
      PP.el('div', { id: 'assistantWindow', class: 'assistant-window glass-card' }, [
        // Header
        PP.el('div', { class: 'assistant-header' }, [
          PP.el('div', { class: 'assistant-brand' }, [
            PP.el('div', { class: 'assistant-avatar' }, [
              PP.el('i', { 'data-lucide': 'bot' }),
            ]),
            PP.el('div', {}, [
              PP.el('h4', {}, ['PocketPay Assistant']),
              PP.el('div', { class: 'assistant-status' }, [
                PP.el('span', { class: 'status-dot' }),
                PP.el('span', { id: 'assistantContextLabel' }, ['Context: Dashboard']),
              ]),
            ]),
          ]),
          PP.el('div', { class: 'assistant-header-actions' }, [
            PP.el('button', {
              class: 'btn-icon',
              title: 'Clear Chat',
              onclick: () => this.clearChat(),
            }, [PP.el('i', { 'data-lucide': 'rotate-ccw', style: 'width:15px;height:15px' })]),
            PP.el('button', {
              class: 'btn-icon',
              title: 'Close Assistant',
              onclick: () => this.close(),
            }, [PP.el('i', { 'data-lucide': 'x', style: 'width:18px;height:18px' })]),
          ]),
        ]),

        // Quick Context Chips
        PP.el('div', { class: 'assistant-chips-container' }, [
          PP.el('div', { class: 'assistant-chips-title' }, [
            PP.el('i', { 'data-lucide': 'lightbulb', style: 'width:12px;height:12px' }),
            'Suggested for this page:',
          ]),
          PP.el('div', { id: 'assistantChipsList', class: 'assistant-chips-list' }),
        ]),

        // Messages scroll area
        PP.el('div', { id: 'assistantMessages', class: 'assistant-messages' }),

        // Guardrail safety notice
        PP.el('div', { class: 'assistant-guardrail-notice' }, [
          PP.el('i', { 'data-lucide': 'shield-check', style: 'width:12px;height:12px' }),
          'Informational assistant. Credentials and financial actions are strictly protected.',
        ]),

        // Input Footer
        PP.el('form', {
          id: 'assistantForm',
          class: 'assistant-form',
          onsubmit: (e) => {
            e.preventDefault();
            this.handleUserSubmit();
          },
        }, [
          PP.el('input', {
            id: 'assistantInput',
            type: 'text',
            class: 'assistant-input',
            placeholder: 'Ask anything about PocketPay…',
            autocomplete: 'off',
          }),
          PP.el('button', {
            type: 'submit',
            class: 'assistant-send-btn',
            'aria-label': 'Send Message',
          }, [
            PP.el('i', { 'data-lucide': 'send', style: 'width:16px;height:16px' }),
          ]),
        ]),
      ]),
    ]);

    document.body.appendChild(widget);
    PP.refreshIcons();
  },

  attachEventListeners() {
    // Close when clicking outside on mobile
    document.addEventListener('click', (e) => {
      const widget = document.getElementById('ppAssistantWidget');
      if (this.isOpen && widget && !widget.contains(e.target)) {
        // Only auto-close on smaller screens
        if (window.innerWidth < 768) {
          this.close();
        }
      }
    });

    // Send initial greeting if empty
    if (this.messages.length === 0) {
      this.addAssistantMessage({
        text: '👋 Hi there! I\'m your <b>PocketPay Assistant</b>. I can help explain features, guide you through organizing pockets, adding income, making payments, and navigating the app.<br><br>What would you like to know?',
        title: 'Welcome to PocketPay!',
      });
    }
  },

  toggle() {
    if (this.isOpen) this.close();
    else this.open();
  },

  open() {
    this.isOpen = true;
    const win = document.getElementById('assistantWindow');
    const launcher = document.getElementById('assistantLauncher');
    if (win) win.classList.add('open');
    if (launcher) launcher.classList.add('active');
    this.updateContextPrompts();
    
    // Focus input after opening
    setTimeout(() => {
      const inp = document.getElementById('assistantInput');
      if (inp && window.innerWidth >= 768) inp.focus();
    }, 150);
  },

  close() {
    this.isOpen = false;
    const win = document.getElementById('assistantWindow');
    const launcher = document.getElementById('assistantLauncher');
    if (win) win.classList.remove('open');
    if (launcher) launcher.classList.remove('active');
  },

  updateContextPrompts() {
    const route = PP.state.currentRoute || 'dashboard';
    const chipsList = document.getElementById('assistantChipsList');
    const contextLabel = document.getElementById('assistantContextLabel');
    
    if (contextLabel) {
      const formatted = route.charAt(0).toUpperCase() + route.slice(1).replace('-', ' ');
      contextLabel.textContent = `Context: ${formatted}`;
    }

    if (!chipsList) return;
    chipsList.innerHTML = '';

    const prompts = this.contextPrompts[route] || this.contextPrompts.dashboard || [];
    prompts.forEach(p => {
      const chip = PP.el('button', {
        class: 'assistant-chip',
        onclick: () => this.askQuestion(p.query),
      }, [
        PP.el('i', { 'data-lucide': 'help-circle', style: 'width:12px;height:12px;opacity:.7' }),
        p.text,
      ]);
      chipsList.appendChild(chip);
    });

    PP.refreshIcons();
  },

  askQuestion(query) {
    const inp = document.getElementById('assistantInput');
    if (inp) inp.value = query;
    this.handleUserSubmit();
  },

  handleUserSubmit() {
    const inp = document.getElementById('assistantInput');
    if (!inp) return;
    const text = inp.value.trim();
    if (!text) return;
    inp.value = '';

    this.addUserMessage(text);
    this.processQuery(text);
  },

  addUserMessage(text) {
    this.messages.push({ sender: 'user', text });
    const container = document.getElementById('assistantMessages');
    if (!container) return;

    const msgEl = PP.el('div', { class: 'assistant-msg user-msg' }, [
      PP.el('div', { class: 'msg-bubble user-bubble' }, [text]),
    ]);
    container.appendChild(msgEl);
    this.scrollToBottom();
  },

  addAssistantMessage(data) {
    this.messages.push({ sender: 'assistant', ...data });
    const container = document.getElementById('assistantMessages');
    if (!container) return;

    const msgEl = PP.el('div', { class: 'assistant-msg bot-msg' });
    const bubble = PP.el('div', { class: 'msg-bubble bot-bubble' });

    if (data.title) {
      bubble.appendChild(PP.el('div', { class: 'msg-title' }, [
        PP.el('i', { 'data-lucide': 'sparkles', style: 'width:14px;height:14px;color:var(--accent)' }),
        data.title,
      ]));
    }

    const content = PP.el('div', { class: 'msg-content' });
    content.innerHTML = data.text;
    bubble.appendChild(content);

    // Action buttons
    if (data.actions && data.actions.length) {
      const actionsWrap = PP.el('div', { class: 'msg-actions' });
      data.actions.forEach(a => {
        const btn = PP.el('button', {
          class: 'btn btn-outline btn-sm assistant-action-btn',
          onclick: () => {
            if (window.innerWidth < 768) this.close();
            a.fn();
          },
        }, [
          a.icon && PP.el('i', { 'data-lucide': a.icon, style: 'width:14px;height:14px' }),
          a.label,
        ]);
        actionsWrap.appendChild(btn);
      });
      bubble.appendChild(actionsWrap);
    }

    msgEl.appendChild(bubble);
    container.appendChild(msgEl);
    PP.refreshIcons();
    this.scrollToBottom();
  },

  async processQuery(rawQuery) {
    const q = rawQuery.trim();
    if (!q) return;

    // Show typing indicator
    const container = document.getElementById('assistantMessages');
    const typingEl = PP.el('div', { class: 'assistant-msg assistant-typing', style: 'display:flex;align-items:center;gap:0.5rem;padding:0.75rem 1rem;color:var(--text-muted);font-size:0.85rem' }, [
      PP.el('i', { 'data-lucide': 'sparkles', class: 'spin', style: 'color:var(--accent);width:16px;height:16px' }),
      'Thinking...'
    ]);
    if (container) {
      container.appendChild(typingEl);
      PP.refreshIcons();
      this.scrollToBottom();
    }

    try {
      const res = await PP.API.post('/api/assistant/ask', {
        query: q,
        route: PP.state.currentRoute || 'dashboard',
        history: this.messages.slice(-6).map(m => ({ sender: m.sender, text: m.text }))
      });

      if (typingEl && typingEl.parentNode) typingEl.parentNode.removeChild(typingEl);

      const data = res.data || {};
      const actionMap = {
        transfer: () => PP.Modals.transfer?.(),
        send_money: () => PP.Modals.sendMoney?.(data.recipient ? { recipient: data.recipient, amount: data.amount } : {}),
        add_income: () => PP.Modals.addIncome?.(),
        create_pocket: () => PP.Modals.createPocket?.(),
        create_goal: () => PP.Modals.createGoal?.(),
        balance: () => PP.navigate('dashboard'),
        pockets: () => PP.navigate('pockets'),
        analytics: () => PP.navigate('analytics'),
        transactions: () => PP.navigate('transactions'),
        budgets: () => PP.navigate('budgets'),
        wallet: () => PP.navigate('wallet'),
        view_premium: () => PP.navigate('premium'),
        totp_setup: () => PP.Modals.setupTotp?.() || PP.navigate('wallet'),
        change_pin: () => PP.Modals.changePin?.() || PP.navigate('wallet'),
        settings: () => PP.navigate('wallet'),
      };

      const mappedActions = (data.actions || []).map(act => ({
        label: act.label,
        icon: act.icon || 'arrow-right',
        fn: actionMap[act.action] || (() => PP.navigate(act.action || 'dashboard'))
      }));

      this.addAssistantMessage({
        title: data.title,
        text: data.message || 'I am ready to help you manage PocketPay.',
        actions: mappedActions,
        suggestedPrompts: data.suggested_prompts || []
      });

    } catch (err) {
      if (typingEl && typingEl.parentNode) typingEl.parentNode.removeChild(typingEl);
      // Offline / client fallback
      this.addAssistantMessage({
        title: 'PocketPay Assistant',
        text: 'You can check your balance on the dashboard, create smart pockets, transfer funds with your 4-digit PIN, or set savings goals.',
        actions: [
          { label: 'Check Balance', icon: 'wallet', fn: () => PP.navigate('dashboard') },
          { label: 'Manage Pockets', icon: 'wallet-cards', fn: () => PP.navigate('pockets') }
        ]
      });
    }
  },

  clearChat() {
    this.messages = [];
    const container = document.getElementById('assistantMessages');
    if (container) container.innerHTML = '';
    this.addAssistantMessage({
      text: 'Chat history cleared. How can I help you today?',
    });
  },

  scrollToBottom() {
    const container = document.getElementById('assistantMessages');
    if (container) {
      setTimeout(() => {
        container.scrollTop = container.scrollHeight;
      }, 50);
    }
  },
};

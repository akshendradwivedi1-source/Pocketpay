// ========== API Wrapper Layer ==========
PP.API = {
  getBaseUrl() {
    if (window.POCKETPAY_API_BASE) {
      return window.POCKETPAY_API_BASE.replace(/\/+$/, '');
    }
    if (window.location && window.location.origin && !window.location.origin.startsWith('file:') && !window.location.origin.startsWith('capacitor:')) {
      return window.location.origin;
    }
    return '';
  },
  async request(url, opts = {}) {
    const baseUrl = this.getBaseUrl();
    const fullUrl = url.startsWith('http') ? url : (baseUrl + url);
    const res = await fetch(fullUrl, {
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', ...(opts.headers || {}) },
      credentials: 'include',
      ...opts,
      body: opts.body ? (typeof opts.body === 'string' ? opts.body : JSON.stringify(opts.body)) : undefined,
    });
    let data = null;
    const rawText = await res.text();
    if (rawText) {
      try {
        data = JSON.parse(rawText);
      } catch (parseErr) {
        data = { success: false, message: `Server error (${res.status}): ${rawText.slice(0, 100)}` };
      }
    }
    if (!res.ok || (data && data.success === false)) {
      const err = new Error(data?.message || data?.error || `HTTP ${res.status}`);
      err.status = res.status;
      err.code = data?.code;
      err.data = data || {};
      throw err;
    }
    return data || {};
  },
  get(u, qs) {
    const url = qs ? `${u}?${new URLSearchParams(qs).toString()}` : u;
    return this.request(url, { method: 'GET' });
  },
  post(u, body) { return this.request(u, { method: 'POST', body }); },
  put(u, body) { return this.request(u, { method: 'PUT', body }); },
  delete(u, body) { return this.request(u, { method: 'DELETE', body }); },
};

// ========== Auth ==========
PP.Auth = {
  async login(email, password, remember = false) {
    return PP.API.post('/auth/login', { email, password, remember });
  },
  async register(payload) {
    return PP.API.post('/auth/register', payload);
  },
  async verifyRegistrationOtp(email, otp) {
    return PP.API.post('/auth/verify-registration-otp', { email, otp });
  },
  async resendRegistrationOtp(email) {
    return PP.API.post('/auth/resend-registration-otp', { email });
  },
  async logout() {
    return PP.API.post('/auth/logout');
  },
  async me() {
    return PP.API.get('/auth/me');
  },
  async checkOtpStatus(email) {
    return PP.API.post('/auth/otp-status', { email });
  },
  async verifyEmail(otp) {
    return PP.API.post('/auth/verify-email', { otp });
  },
  async verifyPhone(otp) {
    return PP.API.post('/auth/verify-phone', { otp });
  },
  async sendPhoneOtp(phone) {
    return PP.API.post('/auth/send-phone-otp', { phone });
  },
  async setUpiId(upi_id, totp_code) {
    return PP.API.post('/auth/set-upi-id', { upi_id, totp_code });
  },
  async requestVerification(email) {
    return PP.API.post('/auth/request-verification', { email });
  },
  async linkBankAccount(bankData) {
    return PP.API.post('/auth/link-bank-account', bankData);
  },
  async getLinkedBanks() {
    return PP.API.get('/auth/linked-banks');
  },
  async syncBankBalance() {
    return PP.API.post('/auth/sync-bank-balance');
  },
  async unlinkBankAccount(bank_id) {
    return PP.API.post('/auth/unlink-bank-account', { bank_id });
  },
  async deleteAccount(password, confirm_text = 'DELETE', totp_code = null) {
    return PP.API.post('/auth/delete-account', { password, confirm_text, totp_code });
  },
  async resendOtp(type = 'email') {
    return PP.API.post('/auth/resend-otp', { type });
  },
  async setupPin(pin, confirm_pin) {
    return PP.API.post('/auth/setup-pin', { pin, confirm_pin });
  },
  async completeSecuritySetup(pin, confirm_pin) {
    return PP.API.post('/auth/complete-security-setup', { pin, confirm_pin });
  },
  async changePin(old_pin, new_pin) {
    return PP.API.post('/auth/change-pin', { old_pin, new_pin });
  },
  async verifyPin(pin) {
    return PP.API.post('/auth/verify-pin', { pin });
  },
  async totpStatus() {
    return PP.API.get('/auth/totp/status');
  },
  async totpSetup() {
    return PP.API.post('/auth/totp/setup');
  },
  async totpVerifySetup(code, secret, backup_codes) {
    return PP.API.post('/auth/totp/verify-setup', { code, secret, backup_codes });
  },
  async totpDisable(payload) {
    return PP.API.post('/auth/totp/disable', payload);
  },
  async totpRegenerateBackupCodes(payload) {
    return PP.API.post('/auth/totp/regenerate-backup-codes', payload);
  },
  async forgotPassword(email) {
    return PP.API.post('/auth/forgot-password', { email });
  },
  async resetPassword(email, otp, new_password) {
    return PP.API.post('/auth/reset-password', { email, otp, new_password });
  },
  async updateProfile(payload) {
    return PP.API.put('/auth/update-profile', payload);
  },
  async walletQr() {
    return PP.API.get('/auth/wallet-qr');
  },
  async telegramStatus() {
    return PP.API.get('/auth/telegram/status');
  },
  async telegramGenerateLinkToken() {
    return PP.API.post('/auth/telegram/generate-link-token');
  },
  async telegramToggleNotifications() {
    return PP.API.post('/auth/telegram/toggle-notifications');
  },
  async telegramDisconnect() {
    return PP.API.post('/auth/telegram/disconnect');
  },


  renderOtpVerification(userEmail) {
    const wrap = PP.$('#authFormWrapper');
    if (!wrap) return;
    wrap.innerHTML = '';

    // If no email was provided, ask the user to enter their email first
    if (!userEmail) {
      const emailForm = PP.el('form', {
        class: 'auth-form',
        onsubmit: async (e) => {
          e.preventDefault();
          const emailInp = PP.$('input[name="email"]', emailForm);
          const emailVal = emailInp?.value?.trim().toLowerCase();
          if (!emailVal) return PP.UI.toast('Email Required', 'Please enter your email address', 'warning');
          
          const btn = PP.$('.auth-submit', emailForm);
          btn.disabled = true; btn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Submitting Request…';
          PP.refreshIcons();
          try {
            await PP.Auth.requestVerification(emailVal);
            PP.UI.toast('Request Sent', `Verification request submitted for admin approval for ${emailVal}`, 'info');
            PP.Auth.renderOtpVerification(emailVal);
          } catch (err) {
            PP.UI.toast('Request Failed', err.message || 'Could not send verification request', 'error');
            btn.disabled = false;
            btn.innerHTML = 'Send Verification Request';
          }
        }
      });
      emailForm.innerHTML = `
        <div style="text-align:center;margin-bottom:1.5rem">
          <div style="width:52px;height:52px;border-radius:14px;background:rgba(99,102,241,0.15);color:var(--accent);display:flex;align-items:center;justify-content:center;margin:0 auto 1rem">
            <i data-lucide="mail" style="width:26px;height:26px"></i>
          </div>
          <h2 class="auth-title">Verify Your Email Address</h2>
          <p class="auth-subtitle">Enter your account email address to request your verification code.</p>
        </div>
        <div class="form-group">
          <label class="form-label">Email Address</label>
          <input class="form-input" name="email" type="email" placeholder="you@example.com" required autofocus />
        </div>
        <button type="submit" class="btn btn-primary btn-lg btn-block auth-submit" style="margin-top:0.75rem">
          Send Verification Request
        </button>
        <div style="margin-top:1.25rem;text-align:center">
          <button type="button" class="link-btn" id="backToSignInFromEmail" style="color:var(--text-dim);font-size:0.85rem">
            Back to Sign In
          </button>
        </div>
      `;
      wrap.appendChild(emailForm);
      PP.refreshIcons();
      PP.$('#backToSignInFromEmail')?.addEventListener('click', () => { PP.Auth.renderLoginForm(); });
      return;
    }

    const form = PP.el('form', {
      class: 'auth-form',
      onsubmit: async (e) => {
        e.preventDefault();
        const otpInp = PP.$('input[name="otp"]', form);
        const otp = otpInp?.value?.trim();
        if (!otp || otp.length !== 6) {
          return PP.UI.toast('Invalid Code', 'Please enter the 6-digit verification code', 'warning');
        }
        const btn = PP.$('.auth-submit', form);
        btn.disabled = true; btn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Verifying…';
        PP.refreshIcons();
        try {
          const res = await PP.Auth.verifyRegistrationOtp(userEmail, otp);
          PP.UI.toast('Verified!', 'Your email has been verified.', 'success');
          PP.state.user = res?.data?.user || null;
          if (window._otpPollTimer) clearInterval(window._otpPollTimer);
          setTimeout(() => { PP.bootstrap(true); }, 350);
        } catch (err) {
          PP.UI.toast('Verification Failed', err.message || 'Incorrect or expired code', 'error');
        } finally {
          btn.disabled = false;
          btn.innerHTML = 'Verify Email & Continue';
        }
      }
    });

    form.innerHTML = `
      <div style="text-align:center;margin-bottom:1.25rem">
        <div style="width:52px;height:52px;border-radius:14px;background:rgba(99,102,241,0.15);color:var(--accent);display:flex;align-items:center;justify-content:center;margin:0 auto 1rem">
          <i data-lucide="mail-check" style="width:26px;height:26px"></i>
        </div>
        <h2 class="auth-title">Email Verification</h2>
        <p class="auth-subtitle" style="margin-bottom:0.75rem">Verification code will be sent to <b style="color:var(--text)">${userEmail}</b></p>
        
        <div id="otpStatusBadge" style="background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);border-radius:10px;padding:8px 12px;font-size:0.78rem;color:#f59e0b;display:inline-flex;align-items:center;gap:6px;margin:0 auto">
          <i data-lucide="clock" style="width:14px;height:14px"></i>
          <span id="otpStatusText">Waiting for admin approval to send code…</span>
        </div>
      </div>

      <div class="form-group" style="text-align:center;margin-top:1rem">
        <label class="form-label" style="text-align:center;font-size:0.8rem">Enter 6-digit Code</label>
        <input class="form-input text-center mono" name="otp" type="text" maxlength="6" pattern="[0-9]{6}" placeholder="000000" style="font-size:1.6rem;letter-spacing:6px;font-weight:700" required autofocus />
      </div>

      <button type="submit" class="btn btn-primary btn-lg btn-block auth-submit" style="margin-top:0.75rem">
        Verify Email & Continue
      </button>

      <div style="margin-top:1.25rem;text-align:center;display:flex;flex-direction:column;gap:.75rem">
        <p style="font-size:0.85rem;color:var(--text-muted)">
          Didn't receive the email?
          <button type="button" class="link-btn" id="resendOtpBtn" style="font-weight:600">Resend Request</button>
        </p>
        <button type="button" class="link-btn" id="backToSignIn" style="color:var(--text-dim);font-size:0.8rem">
          Change Email / Sign In
        </button>
      </div>
    `;

    wrap.appendChild(form);
    PP.refreshIcons();

    // Poll approval status in background
    if (window._otpPollTimer) clearInterval(window._otpPollTimer);
    window._otpPollTimer = setInterval(async () => {
      try {
        const res = await PP.Auth.checkOtpStatus(userEmail);
        const data = res?.data || {};
        const badge = PP.$('#otpStatusBadge', form);
        const text = PP.$('#otpStatusText', form);
        if (badge && text) {
          if (data.approval_status === 'approved_sent' || data.has_active_otp) {
            badge.style.background = 'rgba(16,185,129,0.12)';
            badge.style.borderColor = 'rgba(16,185,129,0.3)';
            badge.style.color = '#10b981';
            text.textContent = '✓ Approved! Verification code sent to your email.';
            PP.refreshIcons();
          }
        }
      } catch {}
    }, 4000);

    PP.$('#resendOtpBtn')?.addEventListener('click', async () => {
      const resendBtn = PP.$('#resendOtpBtn');
      resendBtn.disabled = true;
      try {
        await PP.Auth.resendRegistrationOtp(userEmail);
        PP.UI.toast('Request Sent', `Admin has been notified to send your OTP`, 'info');
        let count = 30;
        resendBtn.textContent = `Resend in ${count}s`;
        const timer = setInterval(() => {
          count -= 1;
          if (count <= 0) {
            clearInterval(timer);
            resendBtn.disabled = false;
            resendBtn.textContent = 'Resend Request';
          } else {
            resendBtn.textContent = `Resend in ${count}s`;
          }
        }, 1000);
      } catch (err) {
        resendBtn.disabled = false;
        PP.UI.toast('Error', err.message || 'Failed to resend request', 'error');
      }
    });

    PP.$('#backToSignIn')?.addEventListener('click', () => {
      if (window._otpPollTimer) clearInterval(window._otpPollTimer);
      PP.Auth.renderLoginForm();
    });
  },

  attachPasswordToggles(container) {
    container.querySelectorAll('.pwd-toggle-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const wrap = btn.closest('.password-field-wrap');
        const input = wrap?.querySelector('input');
        if (!input) return;
        const isPwd = input.type === 'password';
        input.type = isPwd ? 'text' : 'password';
        btn.innerHTML = `<i data-lucide="${isPwd ? 'eye-off' : 'eye'}" style="width:18px;height:18px"></i>`;
        PP.refreshIcons();
      });
    });
  },

  showForgotPasswordModal(initialEmail = '') {
    const modal = PP.UI.modal({
      title: 'Reset Account Password',
      subtitle: 'Verify with 6-digit OTP and choose a new password',
      icon: 'key-round',
      iconClass: 'bg-accent',
      size: 'md'
    });

    modal.body.innerHTML = `
      <form id="forgotPasswordForm" style="display:flex;flex-direction:column;gap:1rem">
        <div id="fpStep1">
          <p style="font-size:0.88rem;color:var(--text-muted);margin-bottom:0.75rem">
            Enter the email address associated with your PocketPay account. We will send you a 6-digit verification code.
          </p>
          <div class="form-group">
            <label class="form-label">Email Address *</label>
            <input class="form-input" id="fpEmail" type="email" value="${initialEmail}" placeholder="you@example.com" required />
          </div>
          <button type="button" class="btn btn-primary btn-block" id="fpSendOtpBtn" style="margin-top:0.5rem">
            Send Reset OTP
          </button>
        </div>

        <div id="fpStep2" style="display:none;flex-direction:column;gap:1rem">
          <div style="background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.2);padding:10px 14px;border-radius:10px;font-size:0.85rem">
            <i data-lucide="mail" style="width:15px;height:15px;display:inline-block;vertical-align:middle;margin-right:4px;color:var(--accent)"></i>
            OTP dispatched! Please check your inbox for <b id="fpTargetEmail"></b>
          </div>

          <div class="form-group">
            <label class="form-label">6-digit Verification Code *</label>
            <input class="form-input text-center mono" id="fpOtp" type="text" maxlength="6" placeholder="000000" style="font-size:1.4rem;letter-spacing:4px;font-weight:700" required />
          </div>

          <div class="form-group">
            <label class="form-label">New Password (min 8 chars) *</label>
            <div class="password-field-wrap">
              <input class="form-input" id="fpNewPassword" type="password" minlength="8" placeholder="••••••••" required />
              <button type="button" class="pwd-toggle-btn" title="Toggle password visibility"><i data-lucide="eye" style="width:18px;height:18px"></i></button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Confirm New Password *</label>
            <div class="password-field-wrap">
              <input class="form-input" id="fpConfirmPassword" type="password" minlength="8" placeholder="••••••••" required />
              <button type="button" class="pwd-toggle-btn" title="Toggle password visibility"><i data-lucide="eye" style="width:18px;height:18px"></i></button>
            </div>
          </div>

          <button type="submit" class="btn btn-primary btn-block" id="fpSubmitBtn" style="margin-top:0.5rem">
            Save New Password & Continue
          </button>
        </div>
      </form>
    `;

    PP.refreshIcons();
    PP.Auth.attachPasswordToggles(modal.body);

    const step1 = modal.body.querySelector('#fpStep1');
    const step2 = modal.body.querySelector('#fpStep2');
    const emailInp = modal.body.querySelector('#fpEmail');
    const sendBtn = modal.body.querySelector('#fpSendOtpBtn');
    const form = modal.body.querySelector('#forgotPasswordForm');

    sendBtn.addEventListener('click', async () => {
      const email = emailInp.value.trim().toLowerCase();
      if (!email) return PP.UI.toast('Email Required', 'Please enter your email address', 'warning');
      sendBtn.disabled = true;
      sendBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Sending OTP…';
      PP.refreshIcons();
      try {
        await PP.Auth.forgotPassword(email);
        modal.body.querySelector('#fpTargetEmail').textContent = email;
        step1.style.display = 'none';
        step2.style.display = 'flex';
        PP.UI.toast('OTP Sent', `If an account exists, a reset code was sent to ${email}`, 'info');
        PP.refreshIcons();
      } catch (err) {
        PP.UI.toast('Request Failed', err.message || 'Failed to send reset code', 'error');
        sendBtn.disabled = false;
        sendBtn.innerHTML = 'Send Reset OTP';
      }
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = emailInp.value.trim().toLowerCase();
      const otp = modal.body.querySelector('#fpOtp').value.trim();
      const newPwd = modal.body.querySelector('#fpNewPassword').value;
      const confirmPwd = modal.body.querySelector('#fpConfirmPassword').value;

      if (!otp || otp.length !== 6) {
        return PP.UI.toast('Invalid OTP', 'Please enter the 6-digit verification code', 'warning');
      }
      if (!newPwd || newPwd.length < 8) {
        return PP.UI.toast('Weak Password', 'New password must be at least 8 characters', 'warning');
      }
      if (newPwd !== confirmPwd) {
        return PP.UI.toast('Password Mismatch', 'Passwords do not match. Please re-enter.', 'warning');
      }

      const submitBtn = modal.body.querySelector('#fpSubmitBtn');
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Resetting Password…';
      PP.refreshIcons();

      try {
        await PP.Auth.resetPassword(email, otp, newPwd);
        modal.close();
        PP.UI.toast('Password Reset', 'Password changed successfully. Please sign in.', 'success');
        PP.Auth.renderLoginForm();
      } catch (err) {
        PP.UI.toast('Reset Failed', err.message || 'Invalid or expired OTP', 'error');
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Save New Password & Continue';
      }
    });
  },

  renderLoginForm() {
    const wrap = PP.$('#authFormWrapper');
    if (!wrap) return;
    wrap.innerHTML = '';
    
    // Update active tab buttons if present
    const tabLogin = PP.$('#tabLogin');
    const tabReg = PP.$('#tabRegister');
    if (tabLogin) tabLogin.classList.add('active');
    if (tabReg) tabReg.classList.remove('active');

    const form = PP.el('form', {
      class: 'auth-form',
      onsubmit: async (e) => {
        e.preventDefault();
        const btn = PP.$('.auth-submit', form);
        btn.disabled = true; btn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Signing In…';
        PP.refreshIcons();
        try {
          const fd = new FormData(form);
          const payload = Object.fromEntries(fd.entries());
          const res = await PP.Auth.login(payload.email, payload.password, payload.remember === 'on');
          PP.UI.toast('Welcome back!', res.message || '', 'success');
          PP.state.user = res?.data?.user || null;
          
          if (res?.data?.needs_email_verification) {
            PP.UI.toast('Email Unverified', 'Please complete email verification', 'warning');
            PP.Auth.renderOtpVerification(payload.email);
          } else {
            setTimeout(() => { PP.bootstrap(true); }, 350);
          }
        } catch (err) {
          PP.UI.toast('Sign In Failed', err.message || 'Invalid email or password', 'error');
        } finally {
          btn.disabled = false;
          btn.innerHTML = 'Sign In';
        }
      },
    });

    form.innerHTML = `
      <h2 class="auth-title">Sign in to PocketPay</h2>
      <p class="auth-subtitle">Welcome back. Enter your credentials to access your pockets.</p>
      
      <div class="form-group">
        <label class="form-label">Email Address *</label>
        <input class="form-input" name="email" type="email" placeholder="you@example.com" required autofocus />
      </div>

      <div class="form-group">
        <label class="form-label">Password *</label>
        <div class="password-field-wrap">
          <input class="form-input" name="password" type="password" placeholder="••••••••" required minlength="8" />
          <button type="button" class="pwd-toggle-btn" title="Toggle password visibility"><i data-lucide="eye" style="width:18px;height:18px"></i></button>
        </div>
      </div>

      <label class="checkbox-row">
        <input type="checkbox" name="remember" />
        <span>Remember me for 30 days</span>
      </label>

      <div style="display:flex;justify-content:space-between;align-items:center;gap:.75rem;flex-wrap:wrap;margin:-.25rem 0 .75rem">
        <button type="button" class="link-btn forgot-btn" id="forgotBtn">Forgot password?</button>
      </div>

      <button type="submit" class="btn btn-primary btn-lg btn-block auth-submit">
        Sign In
      </button>

      <div class="auth-divider"><span>or</span></div>
      
      <div class="auth-switch">
        <p>New to PocketPay? <button type="button" class="link-btn" id="goRegister">Create an account</button></p>
      </div>
    `;

    wrap.appendChild(form);
    PP.refreshIcons();
    PP.Auth.attachPasswordToggles(form);

    PP.$('#goRegister')?.addEventListener('click', () => {
      PP.Auth.renderRegisterForm();
    });

    PP.$('#forgotBtn')?.addEventListener('click', () => {
      const emailVal = PP.$('input[name="email"]', form)?.value?.trim() || '';
      PP.Auth.showForgotPasswordModal(emailVal);
    });
  },

  renderRegisterForm() {
    const wrap = PP.$('#authFormWrapper');
    if (!wrap) return;
    wrap.innerHTML = '';

    // Update active tab buttons if present
    const tabLogin = PP.$('#tabLogin');
    const tabReg = PP.$('#tabRegister');
    if (tabReg) tabReg.classList.add('active');
    if (tabLogin) tabLogin.classList.remove('active');

    const form = PP.el('form', {
      class: 'auth-form',
      onsubmit: async (e) => {
        e.preventDefault();
        const btn = PP.$('.auth-submit', form);
        
        try {
          const fd = new FormData(form);
          const payload = Object.fromEntries(fd.entries());
          
          if (payload.password !== payload.password_confirm) {
            return PP.UI.toast('Password Mismatch', 'Passwords do not match. Please re-enter your password.', 'warning');
          }

          btn.disabled = true; btn.innerHTML = '<i data-lucide="loader-2" style="animation:slowSpin 1s linear infinite"></i> Creating Account…';
          PP.refreshIcons();
          const res = await PP.Auth.register(payload);
          PP.UI.toast('Account Created!', res.message || 'Verification request sent for admin approval.', 'success');
          // Transition directly to OTP verification step for user's entered email
          PP.Auth.renderOtpVerification(payload.email);
        } catch (err) {
          PP.UI.toast('Registration Failed', err.message || 'Something went wrong', 'error');
        } finally {
          btn.disabled = false;
          btn.innerHTML = 'Create Account';
        }
      },
    });

    form.innerHTML = `
      <h2 class="auth-title">Create your account</h2>
      <p class="auth-subtitle">Start organizing every rupee, across every pocket.</p>
      
      <div class="form-group">
        <label class="form-label">Full Name *</label>
        <input class="form-input" name="full_name" type="text" placeholder="Arjun Sharma" required minlength="2" autofocus />
      </div>

      <div class="form-group">
        <label class="form-label">Email Address *</label>
        <input class="form-input" name="email" type="email" placeholder="you@example.com" required />
      </div>

      <div class="form-group">
        <label class="form-label">Phone Number (optional)</label>
        <input class="form-input" name="phone" type="tel" placeholder="+91 98765 43210" />
      </div>

      <div class="form-group">
        <label class="form-label">Password *</label>
        <div class="password-field-wrap">
          <input class="form-input" name="password" type="password" placeholder="••••••••" required minlength="8" />
          <button type="button" class="pwd-toggle-btn" title="Toggle password visibility"><i data-lucide="eye" style="width:18px;height:18px"></i></button>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">Confirm Password *</label>
        <div class="password-field-wrap">
          <input class="form-input" name="password_confirm" type="password" placeholder="••••••••" required minlength="8" />
          <button type="button" class="pwd-toggle-btn" title="Toggle password visibility"><i data-lucide="eye" style="width:18px;height:18px"></i></button>
        </div>
      </div>

      <div class="form-group">
        <label class="form-info">
          <i data-lucide="shield-check" style="width:14px;height:14px;margin-right:4px"></i>
          Upon registration, an OTP request will be submitted for admin verification approval.
        </label>
      </div>

      <button type="submit" class="btn btn-primary btn-lg btn-block auth-submit">
        Create Account
      </button>

      <div class="auth-divider"><span>or</span></div>
      
      <div class="auth-switch">
        <p>Already have an account? <button type="button" class="link-btn" id="goLogin">Sign in</button></p>
      </div>
    `;

    wrap.appendChild(form);
    PP.refreshIcons();
    PP.Auth.attachPasswordToggles(form);

    PP.$('#goLogin')?.addEventListener('click', () => {
      PP.Auth.renderLoginForm();
    });
  },

  renderForm(mode = 'login') {
    if (mode === 'register') {
      this.renderRegisterForm();
    } else {
      this.renderLoginForm();
    }
  },
};


// ========== Misc / Summary ==========
PP.MiscAPI = {
  health() { return PP.API.get('/api/health'); },
  dashboard() { return PP.API.get('/api/summary/dashboard'); },
  icons() { return PP.API.get('/api/icon-options'); },
  colors() { return PP.API.get('/api/color-options'); },
  generateQR(content, size) { return PP.API.post('/api/qr/generate', { content, size }); },
};

// ========== Wallet ==========
PP.WalletAPI = {
  balance() { return PP.API.get('/api/wallet/balance'); },
  topup(amount, payment_method = 'upi', upi_reference) {
    return PP.API.post('/api/wallet/topup', { amount, payment_method, upi_reference });
  },
  withdraw(amount, description, pin, payment_method = 'bank') {
    return PP.API.post('/api/wallet/withdraw', { amount, description, pin, payment_method });
  },
  previewDistribution(total_amount, strategy, extras = {}) {
    return PP.API.post('/api/wallet/income/distribute/preview', { total_amount, strategy, ...extras });
  },
  executeDistribution(total_amount, strategy, extras = {}) {
    return PP.API.post('/api/wallet/income/execute', { total_amount, strategy, ...extras });
  },
  rules(params = {}) { return PP.API.get('/api/wallet/rules', params); },
  createRule(payload) { return PP.API.post('/api/wallet/rules', payload); },
  getRule(id) { return PP.API.get(`/api/wallet/rules/${id}`); },
  updateRule(id, payload) { return PP.API.put(`/api/wallet/rules/${id}`, payload); },
  deleteRule(id) { return PP.API.delete(`/api/wallet/rules/${id}`); },
  categories() { return PP.API.get('/api/wallet/categories'); },
  searchUser(q) { return PP.API.get('/api/wallet/search-user', { q }); },
  verifyWalletId(wallet_id) { return PP.API.get('/api/wallet/verify-id', { id: wallet_id }); },
  verifyId(id) { return PP.API.get('/api/wallet/verify-id', { id }); },
  verifyUpi(upi_id) { return PP.API.post('/api/wallet/verify-upi', { upi_id }); },
  sendMoney(payload) {
    const pin = payload.pin;
    const pinStr = typeof pin === 'object' && pin !== null ? pin.pin : String(pin || '');
    const totp = payload.totp_code || (typeof pin === 'object' && pin !== null ? pin.totp_code : null);
    return PP.API.post('/api/wallet/send-money', { ...payload, pin: pinStr, totp_code: totp });
  },
  requestMoney(payload) { return PP.API.post('/api/wallet/request-money', payload); },
  listRequests(params = {}) { return PP.API.get('/api/wallet/requests', params); },
  payRequest(req_id, pin, extras = {}) {
    const pinStr = typeof pin === 'object' && pin !== null ? pin.pin : String(pin || '');
    const totp = extras.totp_code || (typeof pin === 'object' && pin !== null ? pin.totp_code : null);
    return PP.API.post(`/api/wallet/requests/${req_id}/pay`, { pin: pinStr, totp_code: totp, ...extras });
  },
  declineRequest(req_id) { return PP.API.post(`/api/wallet/requests/${req_id}/decline`); },
};

// ========== Pockets ==========
PP.PocketsAPI = {
  list(params = {}) { return PP.API.get('/api/pockets', params); },
  get(id) { return PP.API.get(`/api/pockets/${id}`); },
  create(payload) { return PP.API.post('/api/pockets', payload); },
  update(id, payload) { return PP.API.put(`/api/pockets/${id}`, payload); },
  remove(id, emptyToWallet = false) { return PP.API.delete(`/api/pockets/${id}?empty_to_wallet=${emptyToWallet}`); },
  addMoney(id, amount, description) { return PP.API.post(`/api/pockets/${id}/add-money`, { amount, description }); },
  withdrawMoney(id, amount, description) { return PP.API.post(`/api/pockets/${id}/withdraw`, { amount, description }); },
  rename(id, name) { return PP.API.put(`/api/pockets/${id}/rename`, { name }); },
  setColor(id, color) { return PP.API.put(`/api/pockets/${id}/color`, { color }); },
  setIcon(id, icon, icon_type = 'lucide') { return PP.API.put(`/api/pockets/${id}/icon`, { icon, icon_type }); },
  archive(id) { return PP.API.post(`/api/pockets/${id}/archive`); },
  restore(id) { return PP.API.post(`/api/pockets/${id}/restore`); },
  reorder(order) { return PP.API.post('/api/pockets/reorder', { order }); },
  transfer(from_pocket_id, to_pocket_id, amount, description) {
    return PP.API.post('/api/pockets/transfer', { from_pocket_id, to_pocket_id, amount, description });
  },
  transactions(id, params = {}) { return PP.API.get(`/api/pockets/${id}/transactions`, params); },
  qr(id) { return PP.API.get(`/api/pockets/${id}/qr`); },
  lookup(ref) { return PP.API.get(`/api/pockets/lookup/${encodeURIComponent(ref)}`); },
  releaseGoal(id) { return PP.API.post(`/api/pockets/${id}/release-goal`, {}); },
};

// ========== Transactions ==========
PP.TxAPI = {
  list(params = {}) { return PP.API.get('/api/transactions', params); },
  get(id) { return PP.API.get(`/api/transactions/${id}`); },
  update(id, payload) { return PP.API.put(`/api/transactions/${id}`, payload); },
  delete(id) { return PP.API.delete(`/api/transactions/${id}`); },
  previewExpense(pocket_id, amount, extras = {}) {
    return PP.API.post('/api/transactions/expense/preview', { pocket_id, amount, ...extras });
  },
  executeExpense(pocket_id, amount, pin, extras = {}) {
    const pinStr = typeof pin === 'object' && pin !== null ? pin.pin : String(pin || '');
    const totp = extras.totp_code || (typeof pin === 'object' && pin !== null ? pin.totp_code : null);
    return PP.API.post('/api/transactions/expense/execute', { pocket_id, amount, pin: pinStr, totp_code: totp, ...extras });
  },
  transferPockets(from_pocket_id, to_pocket_id, amount, pin, description, extras = {}) {
    const pinStr = typeof pin === 'object' && pin !== null ? pin.pin : String(pin || '');
    const totp = extras.totp_code || (typeof pin === 'object' && pin !== null ? pin.totp_code : null);
    return PP.API.post('/api/transactions/transfer', { from_pocket_id, to_pocket_id, amount, pin: pinStr, totp_code: totp, description, ...extras });
  },
  timeline(months = 6) { return PP.API.get('/api/transactions/timeline', { months }); },
  refund(id, pin) {
    const pinStr = typeof pin === 'object' && pin !== null ? pin.pin : String(pin || '');
    const totp = typeof pin === 'object' && pin !== null ? pin.totp_code : null;
    return PP.API.post(`/api/transactions/${id}/refund`, { pin: pinStr, totp_code: totp });
  },
  search(q) { return PP.API.get('/api/transactions/search', { q }); },
  recurringSuggestions() { return PP.API.get('/api/transactions/recurring/suggestions'); },
  getReceipt(ref) { return PP.API.get(`/api/transactions/${encodeURIComponent(ref)}/receipt`); },
  verifyReceipt(content) { return PP.API.post('/api/transactions/verify-receipt', { content }); },
};

// ========== Analytics ==========
PP.AnalyticsAPI = {
  overview() { return PP.API.get('/api/analytics/overview'); },
  spendingByCategory(months = 1) { return PP.API.get('/api/analytics/spending-by-category', { months }); },
  spendingByPocket(months = 1) { return PP.API.get('/api/analytics/spending-by-pocket', { months }); },
  dailyTrend(days = 30) { return PP.API.get('/api/analytics/daily-trend', { days }); },
  budgetPerformance() { return PP.API.get('/api/analytics/budget-performance'); },
  insights() { return PP.API.get('/api/analytics/insights'); },
  notifications(params = {}) { return PP.API.get('/api/analytics/notifications', params); },
  markRead(id) { return PP.API.post(`/api/analytics/notifications/${id}/read`); },
  readAll() { return PP.API.post('/api/analytics/notifications/read-all'); },
  listBudgets() { return PP.API.get('/api/analytics/budgets'); },
  createBudget(payload) { return PP.API.post('/api/analytics/budgets', payload); },
  updateBudget(id, payload) { return PP.API.put(`/api/analytics/budgets/${id}`, payload); },
  deleteBudget(id) { return PP.API.delete(`/api/analytics/budgets/${id}`); },
};

// ========== Payouts & QR Transfers ==========
PP.PayoutsAPI = {
  banksList() { return PP.API.get('/api/payouts/banks-list'); },
  beneficiaries() { return PP.API.get('/api/payouts/beneficiaries'); },
  validateBeneficiary(payload) { return PP.API.post('/api/payouts/validate-beneficiary', payload); },
  parseQR(qr_string) { return PP.API.post('/api/payouts/parse-qr', { qr_string }); },
  payQR(payload) {
    const pin = payload.pin;
    const pinStr = typeof pin === 'object' && pin !== null ? pin.pin : String(pin || '');
    const totp = payload.totp_code || (typeof pin === 'object' && pin !== null ? pin.totp_code : null);
    return PP.API.post('/api/payouts/pay-qr', { ...payload, pin: pinStr, totp_code: totp });
  },
  transferToBank(payload) {
    const pin = payload.pin;
    const pinStr = typeof pin === 'object' && pin !== null ? pin.pin : String(pin || '');
    const totp = payload.totp_code || (typeof pin === 'object' && pin !== null ? pin.totp_code : null);
    return PP.API.post('/api/payouts/transfer-to-bank', { ...payload, pin: pinStr, totp_code: totp });
  },
  netbankingTransfer(payload) {
    const pin = payload.pin;
    const pinStr = typeof pin === 'object' && pin !== null ? pin.pin : String(pin || '');
    const totp = payload.totp_code || (typeof pin === 'object' && pin !== null ? pin.totp_code : null);
    return PP.API.post('/api/payouts/netbanking-transfer', { ...payload, pin: pinStr, totp_code: totp });
  },
  payoutStatus(payout_id) { return PP.API.get(`/api/payouts/${payout_id}`); },
};

// ========== Savings Goals (Phase 11) ==========
PP.GoalsAPI = {
  list() { return PP.API.get('/api/analytics/goals'); },
  create(payload) { return PP.API.post('/api/analytics/goals', payload); },
  update(id, payload) { return PP.API.put(`/api/analytics/goals/${id}`, payload); },
  deposit(id, amount, source = 'wallet') { return PP.API.post(`/api/analytics/goals/${id}/deposit`, { amount, source }); },
  withdraw(id, amount) { return PP.API.post(`/api/analytics/goals/${id}/withdraw`, { amount }); },
  release(id) { return PP.API.post(`/api/analytics/goals/${id}/release`, {}); },
  delete(id) { return PP.API.delete(`/api/analytics/goals/${id}`); },
};

// ========== Universal QR Resolver API ==========
PP.QRAPI = {
  resolve(content) {
    return PP.API.post('/qr/api/resolve', { content });
  },
  getUser(ref) {
    return PP.API.get(`/qr/api/user/${encodeURIComponent(ref)}`);
  },
  getPocket(ref) {
    return PP.API.get(`/qr/api/pocket/${encodeURIComponent(ref)}`);
  },
  getTransaction(ref) {
    return PP.API.get(`/qr/api/transaction/${encodeURIComponent(ref)}`);
  }
};

// ========== PocketPay Premium Suite API ==========
PP.PremiumAPI = {
  getStatus() { return PP.API.get('/api/premium/status'); },
  getPlans() { return PP.API.get('/api/premium/plans'); },
  createCheckoutOrder(plan_id = 'monthly') {
    return PP.API.post('/api/premium/create-checkout-order', { plan_id });
  },
  verifyPayment(payload) {
    return PP.API.post('/api/premium/verify-payment', payload);
  },
  cancel() {
    return PP.API.post('/api/premium/cancel', {});
  },
  // Rules
  getRules() { return PP.API.get('/api/premium/rules'); },
  createRule(payload) { return PP.API.post('/api/premium/rules', payload); },
  updateRule(id, payload) { return PP.API.put(`/api/premium/rules/${id}`, payload); },
  deleteRule(id) { return PP.API.delete(`/api/premium/rules/${id}`); },
  toggleRule(id, is_active) { return PP.API.post(`/api/premium/rules/${id}/toggle`, { is_active }); },
  getRuleHistory(rule_id) { return PP.API.get('/api/premium/rules/history', rule_id ? { rule_id } : undefined); },
  // Pocket Lock
  lockPocket(pocket_id, payload) { return PP.API.post(`/api/premium/pockets/${pocket_id}/lock`, payload); },
  unlockPocket(pocket_id) { return PP.API.post(`/api/premium/pockets/${pocket_id}/unlock`, {}); },
  // Forecasting
  getForecast(days = 30) { return PP.API.get('/api/premium/forecast', { days }); },
  // Subscriptions
  getDetectedSubscriptions() { return PP.API.get('/api/premium/subscriptions/detected'); },
  updateDetectedSub(id, payload) { return PP.API.post(`/api/premium/subscriptions/detected/${id}/update`, payload); },
  // Payment Approval
  getApprovalSettings() { return PP.API.get('/api/premium/approval-mode/settings'); },
  updateApprovalSettings(payload) { return PP.API.post('/api/premium/approval-mode/settings', payload); },
  // Simulator
  calculateSimulation(payload) { return PP.API.post('/api/premium/simulator/calculate', payload); },
  applySimulation(payload) { return PP.API.post('/api/premium/simulator/apply', payload); },
  // Routing
  previewRouting(payload) { return PP.API.post('/api/premium/routing/preview', payload); },
  // Concierge
  askConcierge(question) { return PP.API.post('/api/premium/concierge/ask', { question }); }
};



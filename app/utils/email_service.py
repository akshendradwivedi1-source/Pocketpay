import threading
import logging
import traceback
import re
import socket
import json
import requests
from datetime import datetime
from flask import current_app
from flask_mail import Message
from app.extensions import mail

logger = logging.getLogger('pocketpay.email')
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [PocketPay Email] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _extract_clean_email(raw_val):
    if not raw_val:
        return ''
    raw_str = str(raw_val).strip()
    match = re.search(r'[\w\.-]+@[\w\.-]+', raw_str)
    return match.group(0) if match else raw_str


def _mask_email(email):
    """Safely masks email for logging without exposing full private user addresses."""
    if not email or '@' not in email:
        return '***'
    parts = email.split('@', 1)
    name = parts[0]
    domain = parts[1]
    if len(name) <= 2:
        masked_name = name[0] + '*'
    else:
        masked_name = name[0] + '*' * (len(name) - 2) + name[-1]
    return f"{masked_name}@{domain}"


def get_admin_recipient_email(app):
    """
    Returns the configured administrator email address.
    Checks POCKETPAY_ADMIN_EMAIL first, then ADMIN_EMAIL, then MAIL_USERNAME, then MAIL_DEFAULT_SENDER.
    """
    raw_admin = (
        app.config.get('POCKETPAY_ADMIN_EMAIL') or
        app.config.get('ADMIN_EMAIL') or
        app.config.get('MAIL_USERNAME') or
        app.config.get('MAIL_DEFAULT_SENDER') or
        ''
    )
    clean_admin = _extract_clean_email(raw_admin)
    return clean_admin


def get_network_base_urls(app, request_obj=None):
    """
    Determines all reachable base URLs for local dev, LAN/Wi-Fi, and production.
    """
    configured = (app.config.get('APP_BASE_URL') or '').strip().rstrip('/')
    if configured:
        return {
            'primary': configured,
            'localhost': configured,
            'lan': configured,
            'has_lan': False
        }
    
    port = 5000
    if request_obj:
        try:
            req_port = request_obj.environ.get('SERVER_PORT')
            if req_port:
                port = int(req_port)
        except Exception:
            pass

    lan_ip = '127.0.0.1'
    try:
        hostname = socket.gethostname()
        lan_ip = socket.gethostbyname(hostname)
    except Exception:
        pass
        
    localhost_url = f"http://localhost:{port}"
    has_lan = bool(lan_ip and not lan_ip.startswith('127.'))
    lan_url = f"http://{lan_ip}:{port}" if has_lan else localhost_url
    
    primary = localhost_url
    if request_obj and request_obj.host_url:
        req_host = request_obj.host_url.rstrip('/')
        if req_host and '127.0.0.1' not in req_host and 'localhost' not in req_host:
            primary = req_host
        else:
            primary = localhost_url

    return {
        'primary': primary,
        'localhost': localhost_url,
        'lan': lan_url,
        'has_lan': has_lan,
        'lan_ip': lan_ip
    }


# ==============================================================================
#                 Transactional Email API Providers (HTTP REST)
# ==============================================================================

def _send_via_resend(app, sender_email, sender_name, recipients, subject, body, html):
    """Dispatches email via Resend HTTP REST API (https://resend.com)"""
    api_key = app.config.get('RESEND_API_KEY')
    if not api_key:
        return False, "RESEND_API_KEY not configured"
    
    # Resend default sandbox sender if custom domain isn't verified
    from_header = f"{sender_name} <{sender_email}>" if '@' in sender_email and not sender_email.endswith('@gmail.com') else f"PocketPay <onboarding@resend.dev>"
    if app.config.get('RESEND_FROM_EMAIL'):
        from_header = app.config.get('RESEND_FROM_EMAIL')

    payload = {
        "from": from_header,
        "to": recipients,
        "subject": subject,
        "text": body or "",
        "html": html or body or ""
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    resp = requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=15)
    if resp.status_code in (200, 201):
        return True, "Delivered via Resend API"
    return False, f"Resend API error {resp.status_code}: {resp.text}"


def _send_via_brevo(app, sender_email, sender_name, recipients, subject, body, html):
    """Dispatches email via Brevo / Sendinblue HTTP REST API (https://brevo.com)"""
    api_key = app.config.get('BREVO_API_KEY')
    if not api_key:
        return False, "BREVO_API_KEY not configured"

    payload = {
        "sender": {"name": sender_name, "email": sender_email or "noreply@pocketpay.app"},
        "to": [{"email": r} for r in recipients],
        "subject": subject,
        "textContent": body or "",
        "htmlContent": html or body or ""
    }
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    resp = requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=15)
    if resp.status_code in (200, 201):
        return True, "Delivered via Brevo API"
    return False, f"Brevo API error {resp.status_code}: {resp.text}"


def _send_via_sendgrid(app, sender_email, sender_name, recipients, subject, body, html):
    """Dispatches email via SendGrid HTTP REST API (https://sendgrid.com)"""
    api_key = app.config.get('SENDGRID_API_KEY')
    if not api_key:
        return False, "SENDGRID_API_KEY not configured"

    payload = {
        "personalizations": [{"to": [{"email": r} for r in recipients]}],
        "from": {"email": sender_email or "noreply@pocketpay.app", "name": sender_name},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": body or " "},
            {"type": "text/html", "value": html or body or " "}
        ]
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    resp = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers, timeout=15)
    if resp.status_code in (200, 202):
        return True, "Delivered via SendGrid API"
    return False, f"SendGrid API error {resp.status_code}: {resp.text}"


def _send_via_mailgun(app, sender_email, sender_name, recipients, subject, body, html):
    """Dispatches email via Mailgun HTTP REST API (https://mailgun.com)"""
    api_key = app.config.get('MAILGUN_API_KEY')
    domain = app.config.get('MAILGUN_DOMAIN')
    if not api_key or not domain:
        return False, "MAILGUN_API_KEY or MAILGUN_DOMAIN not configured"

    from_header = f"{sender_name} <{sender_email or 'noreply@' + domain}>"
    data = {
        "from": from_header,
        "to": recipients,
        "subject": subject,
        "text": body or "",
        "html": html or body or ""
    }
    resp = requests.post(
        f"https://api.mailgun.net/v3/{domain}/messages",
        auth=("api", api_key),
        data=data,
        timeout=15
    )
    if resp.status_code == 200:
        return True, "Delivered via Mailgun API"
    return False, f"Mailgun API error {resp.status_code}: {resp.text}"


def _send_via_smtp(app, msg):
    """Dispatches email via standard SMTP socket connection (Flask-Mail)"""
    server = app.config.get('MAIL_SERVER', 'unknown')
    port = app.config.get('MAIL_PORT', 'unknown')
    mail_user = app.config.get('MAIL_USERNAME', '')
    if not mail_user:
        return False, "MAIL_USERNAME not configured for SMTP"
    
    mail.send(msg)
    return True, f"Delivered via SMTP ({server}:{port})"


def _dispatch_async_email(app, sender_email, sender_name, recipient_list, subject, body, html):
    """
    Executes in background thread: auto-detects configured transactional provider
    or uses explicit EMAIL_PROVIDER setting with automatic fallback.
    """
    with app.app_context():
        masked_recipients = [_mask_email(r) for r in recipient_list]
        provider = (app.config.get('EMAIL_PROVIDER') or 'auto').lower()
        
        # 1. Resend API
        if provider == 'resend' or (provider == 'auto' and app.config.get('RESEND_API_KEY')):
            try:
                success, reason = _send_via_resend(app, sender_email, sender_name, recipient_list, subject, body, html)
                if success:
                    logger.info(f"✓ Email '{subject}' delivered to {masked_recipients} via Resend API")
                    return
                else:
                    logger.warning(f"Resend delivery failed ({reason}), attempting fallback...")
            except Exception as e:
                logger.warning(f"Resend dispatch exception: {type(e).__name__} - {str(e)}")

        # 2. Brevo (Sendinblue) API
        if provider in ('brevo', 'sendinblue') or (provider == 'auto' and app.config.get('BREVO_API_KEY')):
            try:
                success, reason = _send_via_brevo(app, sender_email, sender_name, recipient_list, subject, body, html)
                if success:
                    logger.info(f"✓ Email '{subject}' delivered to {masked_recipients} via Brevo API")
                    return
                else:
                    logger.warning(f"Brevo delivery failed ({reason}), attempting fallback...")
            except Exception as e:
                logger.warning(f"Brevo dispatch exception: {type(e).__name__} - {str(e)}")

        # 3. SendGrid API
        if provider == 'sendgrid' or (provider == 'auto' and app.config.get('SENDGRID_API_KEY')):
            try:
                success, reason = _send_via_sendgrid(app, sender_email, sender_name, recipient_list, subject, body, html)
                if success:
                    logger.info(f"✓ Email '{subject}' delivered to {masked_recipients} via SendGrid API")
                    return
                else:
                    logger.warning(f"SendGrid delivery failed ({reason}), attempting fallback...")
            except Exception as e:
                logger.warning(f"SendGrid dispatch exception: {type(e).__name__} - {str(e)}")

        # 4. Mailgun API
        if provider == 'mailgun' or (provider == 'auto' and app.config.get('MAILGUN_API_KEY') and app.config.get('MAILGUN_DOMAIN')):
            try:
                success, reason = _send_via_mailgun(app, sender_email, sender_name, recipient_list, subject, body, html)
                if success:
                    logger.info(f"✓ Email '{subject}' delivered to {masked_recipients} via Mailgun API")
                    return
                else:
                    logger.warning(f"Mailgun delivery failed ({reason}), attempting fallback...")
            except Exception as e:
                logger.warning(f"Mailgun dispatch exception: {type(e).__name__} - {str(e)}")

        # 5. SMTP Fallback (Local / Traditional)
        if provider in ('smtp', 'auto') and app.config.get('MAIL_USERNAME'):
            try:
                msg = Message(
                    subject=subject,
                    recipients=recipient_list,
                    sender=(sender_name, sender_email) if sender_email else (app.config.get('MAIL_DEFAULT_SENDER') or 'noreply@pocketpay.app'),
                    body=body,
                    html=html
                )
                success, reason = _send_via_smtp(app, msg)
                if success:
                    logger.info(f"✓ Email '{subject}' delivered to {masked_recipients} via SMTP")
                    return
                else:
                    logger.warning(f"SMTP delivery failed: {reason}")
            except Exception as e:
                logger.error(f"✗ SMTP delivery FAILED for {masked_recipients}: {type(e).__name__} - {str(e)}")

        # 6. Simulated Development / Local Fallback
        logger.info(f"ℹ [SIMULATED] Email '{subject}' dispatched to {masked_recipients} (No external email API key configured).")


def send_email_sync(subject, recipients, body=None, html=None):
    """
    Synchronously dispatches email and validates that the email provider (SMTP / HTTP API)
    has authoritatively accepted the message for delivery.
    Returns (True, reason) or (False, error_reason).
    """
    try:
        app = current_app._get_current_object()
        raw_sender = (app.config.get('MAIL_DEFAULT_SENDER') or app.config.get('MAIL_USERNAME') or 'noreply@pocketpay.app').strip()
        clean_sender_email = _extract_clean_email(raw_sender) or 'noreply@pocketpay.app'
        sender_name = 'PocketPay'

        recipient_list = recipients if isinstance(recipients, list) else [recipients]
        if app.config.get('TESTING') or app.config.get('MAIL_SUPPRESS_SEND'):
            return True, "Suppressed in test environment"

        provider = (app.config.get('EMAIL_PROVIDER') or 'auto').lower()

        # 1. Resend
        if provider == 'resend' or (provider == 'auto' and app.config.get('RESEND_API_KEY')):
            try:
                ok, reason = _send_via_resend(app, clean_sender_email, sender_name, recipient_list, subject, body, html)
                if ok:
                    return True, reason
            except Exception as e:
                logger.warning(f"Resend error: {e}")

        # 2. Brevo
        if provider in ('brevo', 'sendinblue') or (provider == 'auto' and app.config.get('BREVO_API_KEY')):
            try:
                ok, reason = _send_via_brevo(app, clean_sender_email, sender_name, recipient_list, subject, body, html)
                if ok:
                    return True, reason
            except Exception as e:
                logger.warning(f"Brevo error: {e}")

        # 3. SendGrid
        if provider == 'sendgrid' or (provider == 'auto' and app.config.get('SENDGRID_API_KEY')):
            try:
                ok, reason = _send_via_sendgrid(app, clean_sender_email, sender_name, recipient_list, subject, body, html)
                if ok:
                    return True, reason
            except Exception as e:
                logger.warning(f"SendGrid error: {e}")

        # 4. Mailgun
        if provider == 'mailgun' or (provider == 'auto' and app.config.get('MAILGUN_API_KEY') and app.config.get('MAILGUN_DOMAIN')):
            try:
                ok, reason = _send_via_mailgun(app, clean_sender_email, sender_name, recipient_list, subject, body, html)
                if ok:
                    return True, reason
            except Exception as e:
                logger.warning(f"Mailgun error: {e}")

        # 5. SMTP (Flask-Mail)
        if provider in ('smtp', 'auto') and app.config.get('MAIL_USERNAME'):
            try:
                msg = Message(
                    subject=subject,
                    recipients=recipient_list,
                    sender=(sender_name, clean_sender_email),
                    body=body,
                    html=html
                )
                ok, reason = _send_via_smtp(app, msg)
                if ok:
                    return True, reason
                return False, f"SMTP delivery failed: {reason}"
            except Exception as e:
                clean_err = str(e)
                logger.error(f"SMTP delivery error: {type(e).__name__} - {clean_err}")
                return False, f"Email delivery failed: {type(e).__name__}"

        return False, "No active email delivery provider configured"
    except Exception as e:
        logger.error(f"send_email_sync error: {type(e).__name__} - {str(e)}")
        return False, str(e)


def send_otp_email_sync(recipient_email, otp, user_name="User", purpose="verification"):
    """Synchronous OTP sender with provider acceptance confirmation."""
    return send_otp_email(recipient_email, otp, user_name=user_name, purpose=purpose, sync=True)


def send_email_async(subject, recipients, body=None, html=None):
    """
    Unified transactional asynchronous email dispatcher.
    Dispatches via HTTP transactional APIs (Resend, Brevo, SendGrid, Mailgun) or SMTP without blocking requests.
    """
    try:
        app = current_app._get_current_object()
        raw_sender = (app.config.get('MAIL_DEFAULT_SENDER') or app.config.get('MAIL_USERNAME') or 'noreply@pocketpay.app').strip()
        clean_sender_email = _extract_clean_email(raw_sender) or 'noreply@pocketpay.app'
        sender_name = 'PocketPay'

        recipient_list = recipients if isinstance(recipients, list) else [recipients]
        
        if app.config.get('TESTING') or app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"[TESTING] Email '{subject}' suppressed for test environment.")
            return True

        thr = threading.Thread(
            target=_dispatch_async_email,
            args=(app, clean_sender_email, sender_name, recipient_list, subject, body, html)
        )
        thr.daemon = True
        thr.start()
        return True
    except Exception as e:
        logger.error(f"Error preparing async email dispatch: {type(e).__name__} - {str(e)}")
        return False


def send_admin_otp_request_notification(user_email, user_name="User", approval_token="", request_obj=None):
    """
    Dispatches the OTP Verification Request notification to the administrator.
    Includes multi-environment accessible 'SEND OTP TO USER' action links for PC, Wi-Fi, and direct URL.
    DOES NOT contain the OTP itself.
    """
    try:
        app = current_app._get_current_object()
        admin_email = get_admin_recipient_email(app)
        if not admin_email:
            logger.error("Admin recipient email could not be determined. Please verify POCKETPAY_ADMIN_EMAIL or MAIL_USERNAME.")
            return False
            
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        urls = get_network_base_urls(app, request_obj)
        primary_approval_url = f"{urls['primary']}/auth/admin-approve-otp?token={approval_token}"
        local_approval_url = f"{urls['localhost']}/auth/admin-approve-otp?token={approval_token}"
        lan_approval_url = f"{urls['lan']}/auth/admin-approve-otp?token={approval_token}"
        
        subject = "PocketPay — OTP Verification Request"
        
        body = f"""PocketPay — OTP Verification Request

A user has requested email verification.
User email: {user_email}
User name: {user_name}
Status: OTP requested — waiting for admin approval.
Time: {now_str}

Click the link below to approve this request and dispatch the verification code to the user:
- Main Action: {primary_approval_url}
- On Local PC (Localhost): {local_approval_url}
- On Phone / Same Wi-Fi ({urls.get('lan_ip', 'LAN')}): {lan_approval_url}

Notice: The actual OTP verification code is NOT included in this notification. It will be generated and dispatched directly to {user_email} when you click 'SEND OTP TO USER'.
"""

        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 580px; margin: 0 auto; padding: 28px; background: #0a0b14; color: #e7e9f3; border-radius: 20px; border: 1px solid rgba(255,255,255,0.12); box-shadow: 0 10px 40px rgba(0,0,0,0.5);">
          
          <!-- Header -->
          <div style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 20px; margin-bottom: 24px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
              <span style="font-size: 22px;">🔔</span>
              <h2 style="margin: 0; color: #ffffff; font-size: 19px; font-weight: 800; letter-spacing: -0.3px;">PocketPay — OTP Verification Request</h2>
            </div>
            <p style="margin: 0; color: #9aa0b4; font-size: 13px;">A user has requested email verification. Admin approval required.</p>
          </div>
          
          <!-- Details Table -->
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 20px; margin-bottom: 26px;">
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
              <tr>
                <td style="padding: 9px 0; color: #9aa0b4; width: 140px; font-weight: 500;">User Email:</td>
                <td style="padding: 9px 0; color: #ffffff; font-weight: 700; font-family: monospace; font-size: 14.5px;">{user_email}</td>
              </tr>
              <tr>
                <td style="padding: 9px 0; color: #9aa0b4; font-weight: 500;">User Name:</td>
                <td style="padding: 9px 0; color: #ffffff; font-weight: 600;">{user_name}</td>
              </tr>
              <tr>
                <td style="padding: 9px 0; color: #9aa0b4; font-weight: 500;">Status:</td>
                <td style="padding: 9px 0; color: #f59e0b; font-weight: 700;">OTP requested — waiting for admin approval</td>
              </tr>
              <tr>
                <td style="padding: 9px 0; color: #9aa0b4; font-weight: 500;">Time:</td>
                <td style="padding: 9px 0; color: #cbd5e1; font-size: 13px;">{now_str}</td>
              </tr>
            </table>
          </div>
          
          <!-- Primary Action Button -->
          <div style="text-align: center; margin: 30px 0 20px;">
            <a href="{primary_approval_url}" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); color: #ffffff; text-decoration: none; font-weight: 800; font-size: 15.5px; padding: 16px 40px; border-radius: 12px; letter-spacing: 0.5px; box-shadow: 0 4px 22px rgba(99,102,241,0.5); border: 1px solid rgba(255,255,255,0.25);">
              SEND OTP TO USER
            </a>
            <p style="margin: 12px 0 0; color: #6c7289; font-size: 12px;">Single-use approval link expires in 2 hours.</p>
          </div>
          
          <!-- Alternative Access Links for Local / Phone Access -->
          <div style="background: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.12); border-radius: 12px; padding: 14px 16px; margin: 20px 0; font-size: 12px;">
            <p style="margin: 0 0 8px; color: #cbd5e1; font-weight: 600;">Device Connection Options:</p>
            <div style="display: flex; flex-direction: column; gap: 6px;">
              <div>
                <span style="color: #94a3b8;">💻 <b>On this PC:</b></span>
                <a href="{local_approval_url}" target="_blank" style="color: #818cf8; text-decoration: underline; margin-left: 4px;">{local_approval_url}</a>
              </div>
              {f'''<div>
                <span style="color: #94a3b8;">📱 <b>On Phone / Wi-Fi:</b></span>
                <a href="{lan_approval_url}" target="_blank" style="color: #818cf8; text-decoration: underline; margin-left: 4px;">{lan_approval_url}</a>
              </div>''' if urls.get('has_lan') else ''}
            </div>
          </div>
          
          <!-- Security Notice -->
          <div style="padding: 14px 18px; background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.25); border-radius: 10px; font-size: 12.5px; color: #9aa0b4; line-height: 1.5;">
            🔒 <b>Security Notice:</b> The OTP is <b>NOT</b> included in this notification. When you click <b>SEND OTP TO USER</b>, PocketPay will securely generate the OTP and deliver it directly to <b>{user_email}</b>.
          </div>
          
          <!-- Footer -->
          <div style="text-align: center; margin-top: 24px; color: #475569; font-size: 11.5px;">
            &copy; {datetime.utcnow().year} PocketPay Security System. Automated administrative notice.
          </div>
        </div>
        """
        logger.info(f"Dispatching admin OTP request notification to {_mask_email(admin_email)} for user {_mask_email(user_email)}...")
        return send_email_async(subject, admin_email, body=body, html=html)
    except Exception as e:
        logger.error(f"Failed to dispatch admin notification: {type(e).__name__} - {str(e)}")
        return False


def send_otp_email(recipient_email, otp, user_name="User", purpose="verification", sync=False):
    """
    Sends the real 6-digit OTP exclusively to the user's email address.
    If sync=True, waits for provider delivery confirmation and returns (success, reason).
    """
    try:
        logger.info(f"Preparing {purpose} OTP email for user {_mask_email(recipient_email)}...")
        app = current_app._get_current_object()
        subject = f"PocketPay: Your {purpose.capitalize()} Verification Code is {otp}"
        expiry_min = app.config.get('OTP_EXPIRY_MINUTES', 5)
        
        body = f"""Hello {user_name},

Your PocketPay {purpose} verification code is: {otp}

This code is valid for {expiry_min} minutes. Please do not share this code with anyone.

If you did not request this code, please ignore this email.

Best regards,
The PocketPay Team
"""
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 32px 24px; background: #0a0b14; color: #e7e9f3; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1);">
          <div style="text-align: center; margin-bottom: 28px;">
            <h1 style="color: #ffffff; font-size: 26px; font-weight: 900; letter-spacing: -0.5px; margin: 0;">Pocket<span style="color: #6366f1;">Pay</span></h1>
            <p style="color: #9aa0b4; font-size: 13px; margin-top: 4px;">Smart Pocket Management</p>
          </div>
          
          <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 24px;">
            <h2 style="font-size: 18px; font-weight: 700; color: #ffffff; margin-top: 0;">Hello {user_name},</h2>
            <p style="color: #9aa0b4; font-size: 14px; line-height: 1.6;">
              Please use the verification code below to complete your {purpose}.
            </p>
            
            <div style="text-align: center; margin: 28px 0;">
              <div style="display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #ffffff; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%); padding: 14px 28px; border-radius: 12px; box-shadow: 0 4px 20px rgba(99,102,241,0.4);">
                {otp}
              </div>
            </div>
            
            <p style="color: #9aa0b4; font-size: 13px; margin-bottom: 0;">
              ⏱ This code is valid for <b>{expiry_min} minutes</b>. Never share your verification code with anyone.
            </p>
          </div>
          
          <div style="text-align: center; margin-top: 24px; color: #6c7289; font-size: 12px;">
            &copy; {datetime.utcnow().year} PocketPay. All rights reserved.
          </div>
        </div>
        """
        if sync:
            return send_email_sync(subject, recipient_email, body=body, html=html)
        user_email_success = send_email_async(subject, recipient_email, body=body, html=html)
        return user_email_success
    except Exception as e:
        logger.error(f"Error in send_otp_email for {_mask_email(recipient_email)}: {type(e).__name__} - {str(e)}")
        if sync:
            return False, f"Email dispatch failed: {type(e).__name__}"
        return False


def send_welcome_email(recipient_email, user_name="User"):
    subject = "Welcome to PocketPay!"
    body = f"Hello {user_name},\n\nWelcome to PocketPay! Start organizing your money with smart custom pockets."
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; background: #0a0b14; color: #e7e9f3; border-radius: 16px;">
        <h1 style="color: #ffffff;">Welcome to PocketPay, {user_name}!</h1>
        <p style="color: #9aa0b4;">Your account is ready. Create unlimited pockets, set smart budgets, and track your financial journey.</p>
    </div>
    """
    return send_email_async(subject, recipient_email, body=body, html=html)


# =============================================================================
# OFFICIAL POCKETPAY SUPPORT CONTACTS & NOTIFICATION DISPATCH
# =============================================================================

SUPPORT_CONTACT_EMAILS = [
    'agarwal.anirudh2006@gmail.com',
    'akshendra.dwivedi1@gmail.com',
    'ankitlawaniya2005@gmail.com'
]

SUPPORT_HELPLINES = [
    '+91 85278 70864',
    '8010906123',
    '+91 92679 32341'
]


def send_support_ticket_notification(ticket):
    """
    Sends notification to the official PocketPay support team when a user opens a ticket.
    Recipients: agarwal.anirudh2006@gmail.com, akshendra.dwivedi1@gmail.com, ankitlawaniya2005@gmail.com
    """
    try:
        subject = f"POCKETPAY SUPPORT REQUEST [{ticket.ticket_number}] - {ticket.subject}"
        submitted_at = ticket.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if ticket.created_at else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        body = f"""POCKETPAY SUPPORT REQUEST

Ticket ID: {ticket.ticket_number}
User: {ticket.name}
Email: {ticket.email}
Category: {ticket.category}
Subject: {ticket.subject}
Transaction ID: {ticket.transaction_id or 'N/A'}
Description:
{ticket.description}

Submitted: {submitted_at}
"""
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; background: #0a0b14; color: #e7e9f3; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);">
          <div style="display: flex; align-items: center; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 16px;">
            <div style="font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">Pocket<span style="color: #6366f1;">Pay</span> <span style="font-size: 13px; font-weight: 600; padding: 3px 8px; border-radius: 6px; background: rgba(99,102,241,0.2); color: #818cf8; margin-left: 8px;">SUPPORT DESK</span></div>
          </div>
          
          <div style="background: rgba(255,255,255,0.04); border-radius: 12px; padding: 20px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 20px;">
            <div style="color: #6366f1; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px;">NEW SUPPORT TICKET</div>
            <h2 style="margin: 0 0 14px 0; color: #ffffff; font-size: 18px;">{ticket.subject}</h2>
            
            <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: #9aa0b4; margin-bottom: 16px;">
              <tr><td style="padding: 6px 0; width: 130px; font-weight: 600; color: #6c7289;">Ticket ID:</td><td style="padding: 6px 0; color: #818cf8; font-family: monospace; font-weight: 700;">{ticket.ticket_number}</td></tr>
              <tr><td style="padding: 6px 0; font-weight: 600; color: #6c7289;">User Name:</td><td style="padding: 6px 0; color: #ffffff;">{ticket.name}</td></tr>
              <tr><td style="padding: 6px 0; font-weight: 600; color: #6c7289;">Registered Email:</td><td style="padding: 6px 0; color: #ffffff;">{ticket.email}</td></tr>
              <tr><td style="padding: 6px 0; font-weight: 600; color: #6c7289;">Category:</td><td style="padding: 6px 0; color: #f59e0b;">{ticket.category}</td></tr>
              <tr><td style="padding: 6px 0; font-weight: 600; color: #6c7289;">Transaction ID:</td><td style="padding: 6px 0; color: #ffffff; font-family: monospace;">{ticket.transaction_id or 'N/A'}</td></tr>
              <tr><td style="padding: 6px 0; font-weight: 600; color: #6c7289;">Submitted At:</td><td style="padding: 6px 0; color: #9aa0b4;">{submitted_at}</td></tr>
            </table>
            
            <div style="background: rgba(0,0,0,0.3); border-radius: 8px; padding: 14px; border-left: 3px solid #6366f1;">
              <div style="font-size: 12px; font-weight: 700; color: #6c7289; margin-bottom: 6px; text-transform: uppercase;">User Description:</div>
              <p style="margin: 0; color: #e7e9f3; font-size: 14px; line-height: 1.6; white-space: pre-wrap;">{ticket.description}</p>
            </div>
          </div>
          
          <div style="text-align: center; color: #6c7289; font-size: 12px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px;">
            PocketPay Official Support System • Automated Desk Notification
          </div>
        </div>
        """
        for recipient in SUPPORT_CONTACT_EMAILS:
            send_email_async(subject, recipient, body=body, html=html)
        return True
    except Exception as e:
        logger.error(f"Failed to dispatch support ticket email: {e}")
        return False


def send_ticket_resolution_email(ticket, admin_response, admin_name="PocketPay Support"):
    """
    Sends official admin resolution email to the user when their support ticket is responded to.
    """
    try:
        subject = f"Resolution for Ticket [{ticket.ticket_number}]: {ticket.subject}"
        resolved_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        body = f"""Hello {ticket.name},

Your support request ({ticket.ticket_number}) has been reviewed and responded to by our support team.

Subject: {ticket.subject}
Status: {ticket.status}

Response:
{admin_response}

If you have further questions, you can reply to this email or submit a follow-up request in the PocketPay app.

PocketPay Support Team
Helpline: +91 85278 70864 | 8010906123 | +91 92679 32341
Emails: agarwal.anirudh2006@gmail.com, akshendra.dwivedi1@gmail.com, ankitlawaniya2005@gmail.com
"""
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; background: #0a0b14; color: #e7e9f3; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);">
          <div style="display: flex; align-items: center; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 16px;">
            <div style="font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">Pocket<span style="color: #6366f1;">Pay</span> <span style="font-size: 13px; font-weight: 600; padding: 3px 8px; border-radius: 6px; background: rgba(16,185,129,0.2); color: #10b981; margin-left: 8px;">OFFICIAL RESOLUTION</span></div>
          </div>
          
          <p style="font-size: 15px; color: #e7e9f3; margin-bottom: 16px;">Hello <b>{ticket.name}</b>,</p>
          <p style="font-size: 14px; color: #9aa0b4; line-height: 1.5; margin-bottom: 20px;">
            Your support ticket <b style="color:#818cf8; font-family:monospace;">{ticket.ticket_number}</b> regarding <i>"{ticket.subject}"</i> has been resolved.
          </p>
          
          <div style="background: rgba(16,185,129,0.06); border-radius: 12px; padding: 18px; border: 1px solid rgba(16,185,129,0.25); margin-bottom: 20px;">
            <div style="font-size: 12px; font-weight: 700; color: #10b981; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px;">Support Team Response:</div>
            <p style="margin: 0; color: #ffffff; font-size: 14px; line-height: 1.6; white-space: pre-wrap;">{admin_response}</p>
          </div>
          
          <div style="background: rgba(255,255,255,0.03); border-radius: 10px; padding: 14px; font-size: 13px; color: #9aa0b4; margin-bottom: 20px;">
            <div style="font-weight: 700; color: #ffffff; margin-bottom: 4px;">Need additional assistance?</div>
            📞 <b>Helplines:</b> +91 85278 70864 | 8010906123 | +91 92679 32341<br>
            📧 <b>Support Emails:</b> agarwal.anirudh2006@gmail.com, akshendra.dwivedi1@gmail.com, ankitlawaniya2005@gmail.com
          </div>
          
          <div style="background: rgba(239,68,68,0.08); border-radius: 8px; padding: 10px 14px; font-size: 12px; color: #fca5a5; border-left: 3px solid #ef4444;">
            🛡️ <b>Security Reminder:</b> PocketPay Support will never ask for your password, OTP, or transaction PIN.
          </div>
          
          <div style="text-align: center; color: #6c7289; font-size: 12px; margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px;">
            &copy; {datetime.utcnow().year} PocketPay Inc. All rights reserved.
          </div>
        </div>
        """
        return send_email_async(subject, ticket.email, body=body, html=html)
    except Exception as e:
        logger.error(f"Failed to dispatch resolution email to {ticket.email}: {e}")
        return False

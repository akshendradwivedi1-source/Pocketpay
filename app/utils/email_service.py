import threading
import logging
import traceback
import re
import socket
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


def get_admin_recipient_email(app):
    """
    Returns the configured administrator email address.
    Checks ADMIN_EMAIL first, then MAIL_USERNAME (the mailbox account), then MAIL_DEFAULT_SENDER.
    """
    raw_admin = (
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
        except:
            pass

    lan_ip = '127.0.0.1'
    try:
        hostname = socket.gethostname()
        lan_ip = socket.gethostbyname(hostname)
    except:
        pass
        
    localhost_url = f"http://localhost:{port}"
    has_lan = bool(lan_ip and not lan_ip.startswith('127.'))
    lan_url = f"http://{lan_ip}:{port}" if has_lan else localhost_url
    
    # If the user made the request via their LAN IP, prefer LAN URL as primary
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


def _send_async_email(app, msg):
    with app.app_context():
        recipients = msg.recipients if hasattr(msg, 'recipients') else 'recipient'
        try:
            server = app.config.get('MAIL_SERVER', 'unknown')
            port = app.config.get('MAIL_PORT', 'unknown')
            use_tls = app.config.get('MAIL_USE_TLS', False)
            logger.info(f"Connecting to SMTP server {server}:{port} (TLS={use_tls}) for recipient {recipients}...")
            
            mail.send(msg)
            
            logger.info(f"✓ SMTP delivery SUCCEEDED for recipient {recipients} via {server}:{port}")
        except Exception as e:
            logger.error(f"✗ SMTP delivery FAILED for {recipients}: {type(e).__name__} - {str(e)}")
            logger.debug(f"Full traceback: {traceback.format_exc()}")


def send_email_async(subject, recipients, body=None, html=None):
    try:
        app = current_app._get_current_object()
        raw_sender = (app.config.get('MAIL_DEFAULT_SENDER') or app.config.get('MAIL_USERNAME') or 'noreply@pocketpay.app').strip()
        
        # Format sender tuple ("PocketPay", email_address) for clean inbox display
        clean_sender_email = _extract_clean_email(raw_sender)
        sender = ('PocketPay', clean_sender_email) if clean_sender_email else raw_sender
            
        recipient_list = recipients if isinstance(recipients, list) else [recipients]
        
        msg = Message(
            subject=subject,
            recipients=recipient_list,
            sender=sender
        )
        if body:
            msg.body = body
        if html:
            msg.html = html
            
        if app.config.get('TESTING') or app.config.get('MAIL_SUPPRESS_SEND'):
            logger.info(f"[TESTING] Email '{subject}' suppressed for {recipient_list}.")
            return True
            
        mail_user = app.config.get('MAIL_USERNAME', '')
        if mail_user:
            logger.info(f"Spawning async background thread to dispatch email '{subject}' to {recipient_list}...")
            thr = threading.Thread(target=_send_async_email, args=(app, msg))
            thr.daemon = True
            thr.start()
        else:
            logger.warning(f"SMTP not configured (MAIL_USERNAME empty). Email dispatch skipped for {recipient_list}.")
        return True
    except Exception as e:
        logger.error(f"Error preparing async email for {recipients}: {type(e).__name__} - {str(e)}")
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
            logger.error("Admin recipient email could not be determined. Please verify MAIL_USERNAME or ADMIN_EMAIL in .env.")
            return False
            
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        urls = get_network_base_urls(app, request_obj)
        primary_approval_url = f"{urls['primary']}/auth/admin-approve-otp?token={approval_token}"
        local_approval_url = f"{urls['localhost']}/auth/admin-approve-otp?token={approval_token}"
        lan_approval_url = f"{urls['lan']}/auth/admin-approve-otp?token={approval_token}"
        
        subject = "PocketPay — OTP Verification Request"
        
        body = f"""PocketPay — OTP Verification Request

A user has requested email verification.
User email:
{user_email}

User name:
{user_name}

Status:
OTP requested — waiting for admin approval.

Time:
{now_str}

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
        logger.info(f"Dispatching admin OTP request notification to {admin_email} for user {user_email}...")
        return send_email_async(subject, admin_email, body=body, html=html)
    except Exception as e:
        logger.error(f"Failed to dispatch admin notification: {type(e).__name__} - {str(e)}")
        return False


def send_otp_email(recipient_email, otp, user_name="User", purpose="verification"):
    """
    Sends the real 6-digit OTP exclusively to the user's email address.
    """
    try:
        logger.info(f"Preparing {purpose} OTP email for user {recipient_email}...")
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
        # Send OTP directly to the user's entered email
        user_email_success = send_email_async(subject, recipient_email, body=body, html=html)
        if user_email_success:
            logger.info(f"OTP verification email successfully queued for recipient {recipient_email}")
        return user_email_success
    except Exception as e:
        logger.error(f"Error in send_otp_email for {recipient_email}: {type(e).__name__} - {str(e)}")
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

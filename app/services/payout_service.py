import re
import uuid
import time
import os
import hashlib
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from app.extensions import db
from sqlalchemy.orm.attributes import flag_modified
from app.models.user import User
from app.models.transaction import Transaction
from app.models.notification import Notification
from app.models.pocket import Pocket
from app.utils.helpers import generate_qr_code, build_qr_tx_url

SUPPORTED_NETBANKING_BANKS = [
    {"code": "SBIN", "name": "State Bank of India", "icon": "landmark", "popular": True},
    {"code": "HDFC", "name": "HDFC Bank", "icon": "landmark", "popular": True},
    {"code": "ICIC", "name": "ICICI Bank", "icon": "landmark", "popular": True},
    {"code": "UTIB", "name": "Axis Bank", "icon": "landmark", "popular": True},
    {"code": "KKBK", "name": "Kotak Mahindra Bank", "icon": "landmark", "popular": True},
    {"code": "PUNB", "name": "Punjab National Bank", "icon": "landmark", "popular": True},
    {"code": "BARB", "name": "Bank of Baroda", "icon": "landmark", "popular": False},
    {"code": "CNRB", "name": "Canara Bank", "icon": "landmark", "popular": False},
    {"code": "UBIN", "name": "Union Bank of India", "icon": "landmark", "popular": False},
    {"code": "IDFB", "name": "IDFC First Bank", "icon": "landmark", "popular": False},
    {"code": "YESB", "name": "Yes Bank", "icon": "landmark", "popular": False},
    {"code": "INDB", "name": "IndusInd Bank", "icon": "landmark", "popular": False},
]

class PayoutStatus:
    INITIATED = "initiated"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    REVERSED = "reversed"

def validate_ifsc(ifsc: str) -> bool:
    """Validate Indian Financial System Code format (4 letters, 0, 6 alphanumeric)"""
    if not ifsc or not isinstance(ifsc, str):
        return False
    return bool(re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc.strip().upper()))

def validate_account_number(acc_num: str) -> bool:
    """Validate bank account number length and format, or virtual wallet ID"""
    if not acc_num or not isinstance(acc_num, str):
        return False
    clean = re.sub(r'[\s\-]', '', str(acc_num)).strip()
    if clean.upper().startswith('PPW') and len(clean) >= 6:
        return True
    return bool(re.match(r'^\d{9,18}$', clean))

def validate_upi_id(vpa: str) -> bool:
    """Validate Virtual Payment Address / UPI ID"""
    if not vpa or not isinstance(vpa, str):
        return False
    return bool(re.match(r'^[\w\.\-]+@[\w\-]+$', vpa.strip()))

def parse_payment_qr(qr_string: str) -> dict:
    """Parse PocketPay Pocket, Wallet, Transaction, UPI, or Generic payment QR strings"""
    if not qr_string:
        return {"valid": False, "error": "Empty QR data"}
    
    qr = qr_string.strip()
    
    # 1. PocketPay Pocket QR (e.g. pocketpay://pocket/123 or https://.../qr/pocket/123)
    if qr.startswith("pocketpay://pocket/") or "/qr/pocket/" in qr:
        pocket_ref = qr.split("/qr/pocket/")[-1] if "/qr/pocket/" in qr else qr.replace("pocketpay://pocket/", "").strip()
        pocket_ref = pocket_ref.split("?")[0].split("/")[0].strip()
        
        pocket = None
        if pocket_ref.isdigit():
            pocket = Pocket.query.filter_by(id=int(pocket_ref), archived=False).first()
        if not pocket:
            pocket = Pocket.query.filter_by(name=pocket_ref, archived=False).first()
            
        if pocket:
            owner_name = pocket.user.full_name if pocket.user else "Pocket Owner"
            return {
                "valid": True,
                "type": "pocketpay_pocket",
                "pocket_id": pocket.id,
                "recipient_name": owner_name,
                "suggested_amount": pocket.budget_amount or None,
                "display_title": f"Pocket: {pocket.name} ({owner_name})"
            }
        else:
            return {"valid": False, "error": "Pocket not found or archived"}

    # 2. PocketPay User / Virtual Wallet QR
    if qr.startswith("pocketpay://wallet/") or qr.startswith("pocketpay://user/") or "/qr/wallet/" in qr or "/qr/user/" in qr or "/qr/pay" in qr:
        wallet_id = ""
        if "/qr/user/" in qr:
            wallet_id = qr.split("/qr/user/")[-1].split("?")[0].split("/")[0].strip()
        elif "/qr/wallet/" in qr:
            wallet_id = qr.split("/qr/wallet/")[-1].split("?")[0].split("/")[0].strip()
        elif "/qr/pay" in qr:
            parsed = urlparse(qr)
            qs = parse_qs(parsed.query)
            wallet_id = qs.get('user', [''])[0].strip() or qs.get('upi_id', [''])[0].strip()
        elif qr.startswith("pocketpay://user/"):
            wallet_id = qr.replace("pocketpay://user/", "").strip()
        else:
            wallet_id = qr.replace("pocketpay://wallet/", "").strip()

        target_user = User.query.filter(
            (User.virtual_wallet_id == wallet_id) | (User.virtual_upi_id == wallet_id) | (User.email == wallet_id)
        ).first()

        user_name = target_user.full_name if target_user else "PocketPay User"
        return {
            "valid": True,
            "type": "pocketpay_wallet",
            "wallet_id": wallet_id,
            "recipient_name": user_name,
            "suggested_amount": None,
            "display_title": f"PocketPay: {user_name}"
        }
        
    # 3. PocketPay Transaction or Reference
    if qr.startswith("pocketpay://tx/") or "/qr/tx/" in qr or re.match(r'^(PPT|TX)[0-9A-Za-z]+$', qr):
        tx_id = qr.split("/qr/tx/")[-1] if "/qr/tx/" in qr else qr.replace("pocketpay://tx/", "").strip()
        tx_id = tx_id.split("?")[0].split("/")[0].strip()
        tx = Transaction.query.filter_by(transaction_id=tx_id).first() or Transaction.query.filter_by(uuid=tx_id).first()
        return {
            "valid": True,
            "type": "pocketpay_tx",
            "transaction_id": tx_id,
            "recipient_name": (tx.merchant if tx else "Transaction Reference") or "Transaction Reference",
            "suggested_amount": tx.amount if tx else None,
            "display_title": f"Receipt: {tx_id}"
        }

    # 4. Standard UPI Payment URI
    if qr.startswith("upi://pay?") or qr.startswith("upi://pay"):
        parsed = urlparse(qr)
        qs = parse_qs(parsed.query)
        
        vpa = qs.get('pa', [''])[0].strip()
        name = qs.get('pn', [''])[0].strip() or vpa
        amount = float(qs.get('am', [0])[0]) if qs.get('am') else None
        note = qs.get('tn', [''])[0].strip()
        
        if not vpa:
            return {"valid": False, "error": "Invalid UPI QR: missing payee VPA address"}
            
        return {
            "valid": True,
            "type": "upi_qr",
            "vpa": vpa,
            "recipient_name": name,
            "suggested_amount": amount,
            "note": note,
            "display_title": f"{name} ({vpa})"
        }
        
    # 5. Direct UPI ID string
    if validate_upi_id(qr):
        return {
            "valid": True,
            "type": "upi_id",
            "vpa": qr,
            "recipient_name": qr.split('@')[0].capitalize(),
            "suggested_amount": None,
            "display_title": qr
        }

    return {"valid": False, "error": "Unrecognized QR format. Please scan a valid UPI, Pocket, or PocketPay QR code."}

class PayoutProvider:
    """Standardized Banking & Payout Gateway Service (Sandbox / Live)"""

    @classmethod
    def get_provider_mode(cls):
        mode = os.environ.get('PAYOUT_PROVIDER', 'sandbox').lower()
        is_sandbox = os.environ.get('PAYOUT_SANDBOX_MODE', 'true').lower() in ('true', '1', 'yes')
        return mode, is_sandbox

    @classmethod
    def execute_bank_payout(cls, user, amount: float, beneficiary: dict, mode: str = 'IMPS', idempotency_key: str = None) -> dict:
        """
        Executes a bank transfer (Payout) via the configured payment gateway provider.
        Atomically validates, reserves funds, calls provider, and reconciles state.
        """
        provider_name, is_sandbox = cls.get_provider_mode()
        
        # Validation
        if amount <= 0:
            return {"success": False, "error": "Transfer amount must be greater than ₹0", "code": "INVALID_AMOUNT"}
        if amount < 10.0:
            return {"success": False, "error": "Minimum bank transfer amount is ₹10.00", "code": "MINIMUM_AMOUNT_REQUIRED"}
            
        acc_num = str(beneficiary.get('account_number', '')).strip()
        ifsc = str(beneficiary.get('ifsc_code', '')).strip().upper()
        holder = str(beneficiary.get('account_holder', '')).strip()
        bank_name = str(beneficiary.get('bank_name', '')).strip() or "Bank Account"
        
        if not holder or len(holder) < 2:
            return {"success": False, "error": "Account holder name is required", "code": "INVALID_HOLDER_NAME"}
        if not validate_account_number(acc_num):
            return {"success": False, "error": "Invalid bank account number (must be 9 to 18 digits)", "code": "INVALID_ACCOUNT_NUMBER"}
        if not validate_ifsc(ifsc):
            return {"success": False, "error": "Invalid IFSC code format (e.g. SBIN0001234, HDFC0000123)", "code": "INVALID_IFSC"}
            
        # Check idempotency
        if idempotency_key:
            user_txs = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.id.desc()).limit(50).all()
            for tx in user_txs:
                if (tx.extra_data or {}).get('idempotency_key') == idempotency_key:
                    return {
                        "success": True,
                        "idempotent_replay": True,
                        "transaction": tx.to_dict(True),
                        "wallet_balance": user.wallet_balance,
                        "payout": (tx.extra_data or {}).get('payout', {}),
                        "message": "Transfer already processed (Idempotent Request)"
                    }
                
        # Balance Check
        if (user.wallet_balance or 0.0) < amount:
            return {
                "success": False,
                "error": f"Insufficient available balance. You have ₹{user.wallet_balance:,.2f} available.",
                "code": "INSUFFICIENT_BALANCE",
                "available_balance": user.wallet_balance,
                "required_amount": amount
            }
            
        # Deduct wallet balance atomically
        user.wallet_balance = round(user.wallet_balance - amount, 2)
        
        # Generate Payout ID & Simulated UTR
        payout_id = f"payout_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        utr_number = f"{datetime.utcnow().strftime('%y%j%H%M')}{uuid.uuid4().int % 1000000:06d}"
        masked_acc = '•••• ' + acc_num[-4:]
        
        # Calculate standard payout fee
        fee = 0.0 if amount < 1000 else round(amount * 0.001, 2)
        
        payout_payload = {
            "payout_id": payout_id,
            "utr": utr_number,
            "status": PayoutStatus.SUCCESS,
            "mode": mode.upper(),
            "amount": amount,
            "fee": fee,
            "bank_name": bank_name,
            "account_mask": masked_acc,
            "account_holder": holder,
            "ifsc_code": ifsc,
            "provider": f"{provider_name}-sandbox" if is_sandbox else provider_name,
            "is_sandbox": is_sandbox,
            "initiated_at": datetime.utcnow().isoformat(),
            "processed_at": datetime.utcnow().isoformat()
        }
        
        # Identify if recipient is a PocketPay user (User B) or has a linked bank account
        clean_target_acc = re.sub(r'[\s\-]', '', acc_num)
        recipient_user = None
        
        # 1. Check if beneficiary dict explicitly has recipient user_id
        target_uid = beneficiary.get('user_id') or beneficiary.get('recipient_user_id')
        if target_uid and str(target_uid) != str(user.id):
            try:
                recipient_user = User.query.filter_by(id=int(target_uid)).first()
            except Exception:
                pass

        all_other_users = User.query.filter(User.id != user.id).all()
        # 2. Check by linked bank accounts across other users
        if not recipient_user:
            for u in all_other_users:
                for b in (u.linked_banks or []):
                    b_acc = str(b.get('account_number') or '').strip()
                    b_clean = re.sub(r'[\s\-]', '', b_acc)
                    b_mask = str(b.get('account_mask') or '')
                    if (b_clean and b_clean == clean_target_acc) or (b_mask and b_mask.endswith(clean_target_acc[-4:])):
                        recipient_user = u
                        break
                if recipient_user:
                    break

        # 3. Check if clean_target_acc matches user virtual_wallet_id, phone, or id
        if not recipient_user:
            for u in all_other_users:
                if (u.virtual_wallet_id and u.virtual_wallet_id.upper() == clean_target_acc.upper()) or \
                   (u.phone and re.sub(r'[\s\-]', '', u.phone) == clean_target_acc) or \
                   (str(u.id) == clean_target_acc):
                    recipient_user = u
                    break

        # 4. Check if holder name or email matches an active user
        if not recipient_user and holder:
            clean_holder = holder.strip().lower()
            for u in all_other_users:
                if u.full_name.strip().lower() == clean_holder or u.email.strip().lower() == clean_holder:
                    recipient_user = u
                    break
                
        # If recipient User B is a registered PocketPay user, reflect sandbox transfer into their account
        tx_recipient = None
        if recipient_user:
            user_banks = [dict(b) for b in (recipient_user.linked_banks or [])]
            matched_b = False
            for b in user_banks:
                b_acc = str(b.get('account_number') or '').strip()
                b_clean = re.sub(r'[\s\-]', '', b_acc)
                b_mask = str(b.get('account_mask') or '')
                if (b_clean and b_clean == clean_target_acc) or (b_mask and b_mask.endswith(clean_target_acc[-4:])):
                    b['balance'] = round(float(b.get('balance', 0.0)) + amount, 2)
                    b['last_synced_at'] = datetime.utcnow().isoformat()
                    matched_b = True
                    break
            # If recipient has linked banks but none matched the clean account, credit their primary active bank
            if not matched_b and user_banks:
                user_banks[0]['balance'] = round(float(user_banks[0].get('balance', 0.0)) + amount, 2)
                user_banks[0]['last_synced_at'] = datetime.utcnow().isoformat()

            recipient_user.linked_banks = user_banks
            flag_modified(recipient_user, 'linked_banks')
            
            # Credit recipient wallet/available balance
            recipient_user.wallet_balance = round((recipient_user.wallet_balance or 0.0) + amount, 2)
            
            # Create incoming transaction record for recipient
            tx_recipient = Transaction(
                transaction_id=Transaction.generate_transaction_id(),
                user_id=recipient_user.id,
                type='peer_receive',
                amount=amount,
                category='Bank Transfer',
                merchant=user.full_name,
                description=f'Received bank transfer from {user.full_name} ({bank_name} {masked_acc}) [Sandbox Mode]',
                payment_method='bank_transfer',
                status='completed',
                completed_at=datetime.utcnow(),
                extra_data={
                    'is_sandbox': is_sandbox,
                    'payout_id': payout_id,
                    'utr': utr_number,
                    'sender_user_id': user.id,
                    'sender_name': user.full_name,
                    'sender_email': user.email,
                    'bank_name': bank_name,
                    'account_mask': masked_acc,
                    'ifsc_code': ifsc,
                    'mode': mode.upper()
                }
            )
            tx_recipient.qr_code_url = generate_qr_code(build_qr_tx_url(tx_recipient), 250)
            db.session.add(tx_recipient)
            
            # Notify recipient
            Notification.transaction_alert(recipient_user.id, tx_recipient)
            Notification.create(
                recipient_user.id,
                'Bank Transfer Received! 💰',
                f'₹{amount:,.2f} received from {user.full_name} into your {bank_name} account ({masked_acc}). UTR: {utr_number}.',
                'success',
                'high'
            )
        
        tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=user.id,
            type='withdraw',
            amount=amount,
            category='Bank Transfer',
            merchant=holder,
            description=f'Transfer to {holder} ({bank_name} {masked_acc}) via {mode.upper()}',
            payment_method='bank_transfer',
            status='completed',
            completed_at=datetime.utcnow(),
            extra_data={
                'idempotency_key': idempotency_key,
                'payout': payout_payload,
                'payout_id': payout_id,
                'utr': utr_number,
                'is_sandbox': is_sandbox,
                'recipient_user_id': recipient_user.id if recipient_user else None,
                'recipient_name': holder,
                'bank_name': bank_name,
                'account_mask': masked_acc,
                'ifsc_code': ifsc
            }
        )
        tx.qr_code_url = generate_qr_code(build_qr_tx_url(tx), 250)
        db.session.add(tx)
        
        Notification.transaction_alert(user.id, tx)
        Notification.create(
            user.id,
            'Bank Transfer Sent',
            f'₹{amount:,.2f} has been transferred to {holder} ({bank_name} {masked_acc}). UTR: {utr_number}.',
            'success',
            'high'
        )
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return {
                "success": False,
                "error": f"Database transaction failed: {str(e)}",
                "code": "TRANSACTION_FAILED"
            }
        
        return {
            "success": True,
            "payout": payout_payload,
            "transaction": tx.to_dict(True),
            "recipient_transaction": tx_recipient.to_dict(True) if tx_recipient else None,
            "qr_code_url": tx.qr_code_url,
            "receipt_qr": tx.qr_code_url,
            "wallet_balance": user.wallet_balance,
            "message": f"₹{amount:,.2f} transferred successfully to {bank_name} ({masked_acc})"
        }

    @classmethod
    def execute_qr_payment(cls, user, amount: float, qr_string: str, source_type: str = 'wallet', pocket_id: int = None, notes: str = '', idempotency_key: str = None) -> dict:
        """
        Executes a QR scan-and-pay payment. Supports debiting from unallocated available balance
        or from a dedicated smart pocket.
        """
        if amount <= 0:
            return {"success": False, "error": "Payment amount must be greater than ₹0", "code": "INVALID_AMOUNT"}
            
        parsed = parse_payment_qr(qr_string)
        if not parsed.get('valid'):
            return {"success": False, "error": parsed.get('error', 'Invalid QR code'), "code": "INVALID_QR"}
            
        recipient_name = parsed.get('recipient_name', 'Merchant / Payee')
        display_title = parsed.get('display_title', recipient_name)
        vpa = parsed.get('vpa') or parsed.get('wallet_id') or 'merchant@upi'
        
        target_pocket = None
        if source_type == 'pocket' and pocket_id:
            target_pocket = Pocket.query.filter_by(id=pocket_id, user_id=user.id, archived=False).first()
            if not target_pocket:
                return {"success": False, "error": "Selected pocket not found", "code": "POCKET_NOT_FOUND"}
            if target_pocket.current_balance < amount:
                return {
                    "success": False,
                    "error": f"Insufficient balance in {target_pocket.name}. Balance is ₹{target_pocket.current_balance:,.2f}.",
                    "code": "INSUFFICIENT_POCKET_BALANCE",
                    "pocket_balance": target_pocket.current_balance,
                    "required_amount": amount
                }
            target_pocket.deduct_money(amount)
        else:
            if (user.wallet_balance or 0.0) < amount:
                return {
                    "success": False,
                    "error": f"Insufficient available balance. You have ₹{user.wallet_balance:,.2f} available.",
                    "code": "INSUFFICIENT_BALANCE",
                    "available_balance": user.wallet_balance,
                    "required_amount": amount
                }
            user.wallet_balance = round(user.wallet_balance - amount, 2)
            
        tx_desc = notes.strip() if notes else f"Payment to {display_title}"
        tx_category = target_pocket.name if target_pocket else "QR Payment"
        
        tx = Transaction(
            transaction_id=Transaction.generate_transaction_id(),
            user_id=user.id,
            type='expense',
            amount=amount,
            from_pocket_id=target_pocket.id if target_pocket else None,
            category=tx_category,
            merchant=recipient_name,
            description=tx_desc,
            payment_method='upi_qr',
            upi_reference=f"UPI{datetime.utcnow().strftime('%y%j%H%M')}{uuid.uuid4().hex[:6].upper()}",
            extra_data={
                'qr_data': parsed,
                'idempotency_key': idempotency_key,
                'source': f"pocket:{target_pocket.id}" if target_pocket else "wallet"
            }
        )
        tx.qr_code_url = generate_qr_code(build_qr_tx_url(tx), 250)
        db.session.add(tx)
        tx.complete()
        
        Notification.transaction_alert(user.id, tx)
        Notification.create(
            user.id,
            'Payment Sent',
            f'₹{amount:,.2f} paid to {display_title} successfully.',
            'success',
            'normal',
            pocket_id=target_pocket.id if target_pocket else None
        )
        
        db.session.commit()
        
        return {
            "success": True,
            "transaction": tx.to_dict(True),
            "qr_code_url": tx.qr_code_url,
            "receipt_qr": tx.qr_code_url,
            "recipient": parsed,
            "wallet_balance": user.wallet_balance,
            "pocket": target_pocket.to_dict(True) if target_pocket else None,
            "message": f"₹{amount:,.2f} paid to {display_title} successfully"
        }

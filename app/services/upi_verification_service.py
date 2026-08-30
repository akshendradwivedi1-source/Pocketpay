"""
PocketPay - UPI ID (VPA) Verification Service
Provides format validation, real provider integration hooks, and a fully isolated
Mock/Development verification service for testing without banking provider credentials.
"""

import re
import os
import requests
from datetime import datetime
from app.models.user import User


class UPIVerificationService:
    """
    Modular UPI/VPA Verification Service.
    Supports pluggable real payment aggregators (Setu, Razorpay, Decentro, Cashfree)
    and falls back to a transparent Mock/Development verification service.
    """

    UPI_REGEX = re.compile(r'^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z0-9.\-_]{2,64}$')

    @classmethod
    def validate_format(cls, vpa: str) -> tuple[bool, str]:
        """Validates UPI ID syntax according to NPCI / UPI standards."""
        if not vpa or not isinstance(vpa, str):
            return False, "UPI ID cannot be empty"
        clean = vpa.strip()
        if len(clean) < 5 or len(clean) > 256:
            return False, "UPI ID length must be between 5 and 256 characters"
        if not cls.UPI_REGEX.match(clean):
            return False, "Invalid UPI ID format. Expected format: username@bank"
        return True, ""

    @classmethod
    def verify_vpa(cls, vpa_string: str) -> dict:
        """
        Verifies a UPI ID and retrieves the registered payee name and account status.
        Never stores or asks for UPI PIN, bank passwords, or OTPs.
        """
        valid_format, err_msg = cls.validate_format(vpa_string)
        if not valid_format:
            return {
                "valid": False,
                "vpa": vpa_string,
                "error": err_msg,
                "verification_status": "FAILED",
                "recipient_name": None,
                "is_mock": False,
                "provider": "format_validator"
            }

        clean_vpa = vpa_string.strip()

        # 1. Internal PocketPay Virtual UPI check (@pocketpay)
        if clean_vpa.lower().endswith('@pocketpay'):
            internal_user = User.query.filter(
                (User.virtual_upi_id == clean_vpa.lower()) |
                (User.email == clean_vpa.lower().replace('@pocketpay', ''))
            ).first()
            if internal_user:
                if not internal_user.is_active:
                    return {
                        "valid": False,
                        "vpa": clean_vpa,
                        "error": "PocketPay recipient account is inactive or suspended",
                        "verification_status": "INACTIVE",
                        "recipient_name": internal_user.full_name,
                        "is_mock": False,
                        "provider": "pocketpay_internal"
                    }
                return {
                    "valid": True,
                    "vpa": clean_vpa,
                    "recipient_name": internal_user.full_name,
                    "user_id": internal_user.id,
                    "wallet_id": internal_user.virtual_wallet_id,
                    "verification_status": "VERIFIED",
                    "verified_at": datetime.utcnow().isoformat(),
                    "is_mock": False,
                    "provider": "pocketpay_internal",
                    "account_type": "POCKETPAY_WALLET"
                }

        # 2. Check for configured real UPI verification provider
        provider_name = os.environ.get('UPI_VERIFICATION_PROVIDER', '').strip().lower()
        api_key = os.environ.get('UPI_VERIFICATION_API_KEY', '').strip()

        if provider_name == 'setu' and api_key:
            return cls._verify_with_setu(clean_vpa, api_key)
        elif provider_name == 'razorpay' and api_key:
            return cls._verify_with_razorpay(clean_vpa, api_key)
        elif provider_name == 'cashfree' and api_key:
            return cls._verify_with_cashfree(clean_vpa, api_key)

        # 3. Transparent Mock / Development Verification Service
        return cls._verify_mock_development(clean_vpa)

    @classmethod
    def _verify_mock_development(cls, vpa: str) -> dict:
        """
        Isolated Mock/Development service for local testing and demo environments.
        Explicitly marked as mock so users and developers know real banking verification
        requires live provider credentials.
        """
        lower = vpa.lower()

        # Simulated negative test cases
        blocked_keywords = ['invalid', 'blocked', 'closed', 'fraud', 'unknown', 'reject', 'fail', 'inactive']
        handle, _, bank = lower.partition('@')

        if any(bad in handle for bad in blocked_keywords) or bank in ('invalid', 'fake', 'blocked'):
            return {
                "valid": False,
                "vpa": vpa,
                "error": f"UPI ID '{vpa}' could not be verified by banking switch (Simulated Sandbox).",
                "verification_status": "FAILED",
                "recipient_name": None,
                "is_mock": True,
                "provider": "mock_development_service",
                "simulated": True
            }

        # Generate a realistic mock payee name from the username handle
        formatted_handle = re.sub(r'[._\-]', ' ', handle).strip().title()
        if not formatted_handle:
            formatted_handle = "Merchant Payee"

        # Special known test fixtures
        known_payees = {
            'coffee.shop': 'Coffee & Bistro Lounge',
            'starbucks': 'Starbucks India Retail',
            'swiggy': 'Swiggy Food Delivery',
            'zomato': 'Zomato Payments Ltd',
            'amazon': 'Amazon Pay India',
            'flipkart': 'Flipkart Internet Pvt Ltd',
            'uber': 'Uber Rides India',
            'ola': 'ANI Technologies Pvt Ltd',
            'merchant': 'Demo Merchant Enterprise',
            'arjun.sharma': 'Arjun Sharma',
            'alice.smith': 'Alice Smith',
            'bob.jones': 'Bob Jones'
        }

        payee_name = known_payees.get(handle.lower(), formatted_handle)

        return {
            "valid": True,
            "vpa": vpa,
            "recipient_name": payee_name,
            "verification_status": "VERIFIED",
            "verified_at": datetime.utcnow().isoformat(),
            "is_mock": True,
            "provider": "mock_development_service",
            "simulated": True,
            "account_type": "SAVINGS",
            "message": "UPI ID verified successfully (Simulated Sandbox)"
        }

    @classmethod
    def _verify_with_setu(cls, vpa: str, api_key: str) -> dict:
        """Integration template for Setu UPI DeepLink / VPA Auth API."""
        try:
            url = os.environ.get('SETU_VPA_ENDPOINT', 'https://api.setu.co/api/v1/verify/vpa')
            resp = requests.post(
                url,
                json={"vpa": vpa},
                headers={"X-Setu-Client-ID": api_key, "Content-Type": "application/json"},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "valid": data.get("valid", True),
                    "vpa": vpa,
                    "recipient_name": data.get("customerName") or data.get("name"),
                    "verification_status": "VERIFIED" if data.get("valid") else "FAILED",
                    "is_mock": False,
                    "provider": "setu"
                }
            return {
                "valid": False,
                "vpa": vpa,
                "error": "Setu verification failed",
                "is_mock": False,
                "provider": "setu"
            }
        except Exception as e:
            return {
                "valid": False,
                "vpa": vpa,
                "error": f"Provider network error: {str(e)}",
                "is_mock": False,
                "provider": "setu"
            }

    @classmethod
    def _verify_with_razorpay(cls, vpa: str, api_key: str) -> dict:
        """Integration template for Razorpay VPA Validation API."""
        try:
            api_secret = os.environ.get('UPI_VERIFICATION_SECRET', '')
            url = 'https://api.razorpay.com/v1/payments/validate/vpa'
            resp = requests.post(
                url,
                json={"vpa": vpa},
                auth=(api_key, api_secret),
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "valid": data.get("success", True),
                    "vpa": vpa,
                    "recipient_name": data.get("customer_name"),
                    "verification_status": "VERIFIED" if data.get("success") else "FAILED",
                    "is_mock": False,
                    "provider": "razorpay"
                }
            return {"valid": False, "vpa": vpa, "error": "Razorpay VPA lookup failed", "is_mock": False, "provider": "razorpay"}
        except Exception as e:
            return {"valid": False, "vpa": vpa, "error": str(e), "is_mock": False, "provider": "razorpay"}

    @classmethod
    def _verify_with_cashfree(cls, vpa: str, app_id: str) -> dict:
        """Integration template for Cashfree VPA Verification API."""
        try:
            secret = os.environ.get('UPI_VERIFICATION_SECRET', '')
            url = 'https://payout-api.cashfree.com/payout/v1/validation/upiDetails'
            resp = requests.get(
                url,
                params={"vpa": vpa},
                headers={"X-Client-Id": app_id, "X-Client-Secret": secret},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "valid": data.get("status") == "SUCCESS",
                    "vpa": vpa,
                    "recipient_name": data.get("data", {}).get("nameAtBank"),
                    "verification_status": "VERIFIED" if data.get("status") == "SUCCESS" else "FAILED",
                    "is_mock": False,
                    "provider": "cashfree"
                }
            return {"valid": False, "vpa": vpa, "error": "Cashfree VPA lookup failed", "is_mock": False, "provider": "cashfree"}
        except Exception as e:
            return {"valid": False, "vpa": vpa, "error": str(e), "is_mock": False, "provider": "cashfree"}

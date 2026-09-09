import requests
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:5000"

def test_live_server():
    session = requests.Session()
    print("Testing live PocketPay server on", BASE_URL)
    
    # 1. Test index page
    res = session.get(f"{BASE_URL}/")
    assert res.status_code == 200, f"Failed to load index: {res.status_code}"
    print(" [x] Index page loaded successfully")
    
    import random
    uid = random.randint(10000, 99999)
    test_email = f"buyer_{uid}@example.com"
    test_phone = f"98{random.randint(10000000, 99999999)}"
    
    # 2. Register fresh Standard User
    reg_res = session.post(f"{BASE_URL}/auth/register", json={
        "email": test_email,
        "password": "SecurePass@123",
        "full_name": f"Tester {uid}",
        "phone": test_phone
    })
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
    print(f" [x] Registered new standard user: {test_email}")
    
    # Login as this standard user
    login_res = session.post(f"{BASE_URL}/auth/login", json={
        "email": test_email,
        "password": "SecurePass@123"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    user_data = login_res.json().get("data", {}).get("user", {})
    assert user_data.get("is_premium") is False
    print(f" [x] Logged in as Standard user: {test_email} (is_premium: False)")
    
    # 3. Verify Access Control: Standard user CANNOT access Premium APIs (403 Forbidden)
    forbidden_rules = session.get(f"{BASE_URL}/api/premium/rules")
    assert forbidden_rules.status_code == 403, f"Expected 403, got {forbidden_rules.status_code}"
    forbidden_forecast = session.get(f"{BASE_URL}/api/premium/forecast")
    assert forbidden_forecast.status_code == 403, f"Expected 403, got {forbidden_forecast.status_code}"
    print(" [x] Access Control verified: Standard user rejected with 403 Forbidden on Premium APIs")
    
    # 4. Test Subscription Plans endpoint
    plans_res = session.get(f"{BASE_URL}/api/premium/plans")
    assert plans_res.status_code == 200, f"Plans failed: {plans_res.text}"
    plans_data = plans_res.json().get("data", {}).get("plans", {})
    assert "monthly" in plans_data and "yearly" in plans_data
    print(f" [x] Plans loaded: Monthly (INR{plans_data['monthly']['amount']}), Annual (INR{plans_data['yearly']['amount']})")
    
    # 5. Test Create Order endpoint (Fix for 'Order creation failed')
    order_res = session.post(f"{BASE_URL}/api/premium/create-checkout-order", json={
        "plan_id": "monthly"
    })
    assert order_res.status_code in (200, 201), f"Order creation failed: {order_res.text}"
    order_json = order_res.json().get("data", {})
    order_id = order_json.get("order_id")
    assert order_id is not None
    print(f" [x] Order created successfully: {order_id} (amount: INR{order_json.get('amount')}, sandbox: {order_json.get('sandbox')})")
    
    # 6. Verify payment (sandbox activation)
    import uuid
    payment_id = f"pay_live_test_{uuid.uuid4().hex[:16]}"
    verify_res = session.post(f"{BASE_URL}/api/premium/verify-payment", json={
        "order_id": order_id,
        "payment_id": payment_id,
        "signature": f"sig_sandbox_{order_id}",
        "plan_id": "monthly"
    })
    assert verify_res.status_code == 200, f"Verify failed: {verify_res.text}"
    print(" [x] Subscription verified and activated on backend!")
    
    # 7. Test Subscription Status
    status_res = session.get(f"{BASE_URL}/api/premium/status")
    assert status_res.status_code == 200
    sub_status = status_res.json().get("data", {})
    assert sub_status.get("is_premium") is True
    print(f" [x] User is now verified PREMIUM! (Plan: {sub_status.get('current_plan')})")
    
    # 8. Duplicate Payment Attempt Prevention
    dup_res = session.post(f"{BASE_URL}/api/premium/create-checkout-order", json={
        "plan_id": "monthly"
    })
    assert dup_res.status_code == 400
    print(" [x] Duplicate subscription creation prevented correctly!")
    
    # Create a pocket for the user first
    pocket_res = session.post(f"{BASE_URL}/api/pockets", json={
        "name": f"Emergency Fund {uid}",
        "category": "Emergency",
        "funding_source": "fund_later"
    })
    assert pocket_res.status_code in (200, 201), f"Pocket create failed: {pocket_res.text}"
    target_pocket_id = pocket_res.json().get("data", {}).get("pocket", {}).get("id")
    assert target_pocket_id is not None
    print(f" [x] Created target pocket #{target_pocket_id} for automation")

    # 9. Test Premium Feature 1: Rules Engine (Create, List, Toggle, Delete)
    rule_create = session.post(f"{BASE_URL}/api/premium/rules", json={
        "name": "Live Emergency Fund Rule",
        "trigger_type": "INCOME_RECEIVED",
        "target_pocket_id": target_pocket_id,
        "action_type": "ALLOCATE_PERCENT",
        "action_value": 25.0,
        "percentage": 25.0
    })
    if rule_create.status_code != 201:
        print("Rule creation failed with:", rule_create.status_code, rule_create.text)
    assert rule_create.status_code == 201
    created_rule = rule_create.json().get("data", {}).get("rule", {})
    rule_id = created_rule.get("id")
    print(f" [x] Rules Engine: Rule #{rule_id} created successfully")
    
    rules_res = session.get(f"{BASE_URL}/api/premium/rules")
    assert rules_res.status_code == 200
    print(" [x] Rules Engine: Listed rules successfully")
    
    # 10. Test Premium Feature 2: Forecast
    forecast_res = session.get(f"{BASE_URL}/api/premium/forecast?days=30")
    assert forecast_res.status_code == 200
    f_data = forecast_res.json().get("data", {})
    print(f" [x] Forecast loaded: Current INR{f_data.get('current_balance')}, Projected INR{f_data.get('projected_balance')}")
    
    # 11. Test Premium Feature 3: Simulator
    sim_res = session.post(f"{BASE_URL}/api/premium/simulator/calculate", json={
        "income": 50000,
        "expenses": {"rent": 15000, "food": 8000, "travel": 5000},
        "savings_target": 12000
    })
    assert sim_res.status_code == 200
    sim_data = sim_res.json().get("data", {})
    print(f" [x] Simulator calculated: Proposed savings INR{sim_data.get('proposed_allocations', {}).get('savings', 0)}")
    
    # 12. Test Premium Feature 4: Concierge
    concierge_res = session.post(f"{BASE_URL}/api/premium/concierge/ask", json={
        "question": "Can I afford INR8,000 this month?"
    })
    assert concierge_res.status_code == 200
    c_data = concierge_res.json().get("data", {})
    print(f" [x] Concierge response received: {c_data.get('answer')[:70]}...")
    
    # 13. Test Premium Feature 5: Subscriptions Detector
    detector_res = session.get(f"{BASE_URL}/api/premium/subscriptions/detected")
    assert detector_res.status_code == 200
    print(" [x] Subscription Detector API accessible")

    # 14. Test Premium Feature 6: Payment Approval Settings
    approval_res = session.post(f"{BASE_URL}/api/premium/approval-mode/settings", json={
        "require_payment_approval": True,
        "payment_approval_threshold": 5000.0
    })
    assert approval_res.status_code == 200
    print(" [x] Payment Approval Threshold configured (INR5000)")

    # 15. Test Premium Feature 7: Multi-Pocket Payment Routing
    routing_res = session.post(f"{BASE_URL}/api/premium/routing/preview", json={
        "amount": 3500.0
    })
    assert routing_res.status_code == 200
    print(" [x] Payment Routing Preview calculated successfully")

    # 16. Test Cancel Subscription
    cancel_res = session.post(f"{BASE_URL}/api/premium/cancel", json={})
    assert cancel_res.status_code == 200
    print(" [x] Subscription cancellation processed cleanly")

    print("\n==========================================================")
    print("ALL 16 LIVE HTTP INTEGRATION CHECKS PASSED WITH 100% SUCCESS!")
    print("==========================================================")

if __name__ == "__main__":
    test_live_server()

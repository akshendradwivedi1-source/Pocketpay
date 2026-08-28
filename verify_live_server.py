import requests
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:5000"

def test_live_server():
    session = requests.Session()
    
    print("=" * 70)
    print("PocketPay Live Fintech Server Verification Suite")
    print("=" * 70)
    
    # 1. Health check
    res = session.get(f"{BASE_URL}/api/health")
    assert res.status_code == 200, f"Health check failed: {res.status_code}"
    print("[PASS] 1. Health Check (200 OK):", res.json())
    
    # 2. Main SPA Interface
    res = session.get(f"{BASE_URL}/")
    assert res.status_code == 200, f"Root page failed: {res.status_code}"
    assert "PocketPay" in res.text, "PocketPay brand not found in HTML"
    print("[PASS] 2. Web SPA Main Interface Loaded (200 OK)")
    
    # 3. Login with User Account (Akshendra)
    login_payload = {
        "email": "akshendra.dwivedi1@gmail.com",
        "password": "Admin@PocketPay2026"
    }
    res = session.post(f"{BASE_URL}/auth/login", json=login_payload)
    assert res.status_code == 200, f"Login failed: {res.status_code} - {res.text}"
    user_data = res.json()["data"]["user"]
    print(f"[PASS] 3. Authentication Succeeded: Logged in as {user_data['full_name']} ({user_data['email']})")
    
    # 4. Wallet Balance & Pockets
    res = session.get(f"{BASE_URL}/api/wallet/balance")
    assert res.status_code == 200, f"Wallet balance failed: {res.status_code}"
    bal = res.json()["data"]
    print(f"[PASS] 4. Wallet Balance: Total = Rs.{bal.get('total_balance', 0):,.2f}, Available = Rs.{bal.get('wallet_balance', 0):,.2f}, In Pockets = Rs.{bal.get('pocket_balance', 0):,.2f}")
    
    # 5. Pockets List
    res = session.get(f"{BASE_URL}/api/pockets")
    assert res.status_code == 200, f"Pockets list failed: {res.status_code}"
    pockets = res.json()["data"]["items"]
    print(f"[PASS] 5. Smart Pockets Count: {len(pockets)} active pockets retrieved")
    
    # 6. Savings Goals (Phase 11)
    res = session.get(f"{BASE_URL}/api/analytics/goals")
    assert res.status_code == 200, f"Goals failed: {res.status_code}"
    goals_data = res.json()["data"]
    print(f"[PASS] 6. Savings Goals Center: {goals_data.get('total_count', 0)} active goals retrieved")
    
    # 7. Conversational AI Assistant (Phases 16, 17, 18)
    res = session.post(f"{BASE_URL}/api/assistant/ask", json={
        "query": "What's my balance and which pocket has the most money?",
        "route": "dashboard"
    })
    assert res.status_code == 200, f"Assistant ask failed: {res.status_code}"
    ai_resp = res.json()["data"]
    print(f"[PASS] 7. AI Assistant NLP Processed: Title='{ai_resp.get('title')}' Actions={len(ai_resp.get('actions', []))}")
    
    # 8. Transactions List & Filter
    res = session.get(f"{BASE_URL}/api/transactions?type=expense")
    assert res.status_code == 200, f"Transactions failed: {res.status_code}"
    tx_count = len(res.json()["data"]["items"])
    print(f"[PASS] 8. Transactions Ledger: {tx_count} expense transactions loaded")
    
    # 9. Analytics Overview
    res = session.get(f"{BASE_URL}/api/analytics/overview")
    assert res.status_code == 200, f"Analytics failed: {res.status_code}"
    analytics = res.json()["data"]
    print(f"[PASS] 9. Financial Analytics: Monthly Income = Rs.{analytics.get('monthly', {}).get('income', 0):,.2f}, Spent = Rs.{analytics.get('monthly', {}).get('expense', 0):,.2f}, Savings Rate = {analytics.get('monthly', {}).get('savings_rate', 0)}%")
    
    # 10. P2P Self-Search Guard
    res = session.get(f"{BASE_URL}/api/wallet/search-user?q=akshendra.dwivedi1@gmail.com")
    assert res.status_code == 400, "Self-search validation check failed"
    print("[PASS] 10. P2P Self-Search Guard Working (cannot transfer to own account)")
    
    # 11. P2P Money Requests
    res = session.get(f"{BASE_URL}/api/wallet/requests")
    assert res.status_code == 200, f"Money requests failed: {res.status_code}"
    reqs = res.json()["data"]["requests"]
    print(f"[PASS] 11. Money Requests Manager: {len(reqs)} peer requests retrieved")
    
    # 12. Security TOTP Status
    res = session.get(f"{BASE_URL}/auth/totp/status")
    assert res.status_code == 200, f"TOTP status failed: {res.status_code}"
    print(f"[PASS] 12. Security 2FA Status: Enabled = {res.json()['data']['totp_enabled']}")
    
    # 13. Admin Dashboard Access (Akshendra is Admin -> 200 OK)
    admin_session = requests.Session()
    admin_login_res = admin_session.post(f"{BASE_URL}/admin/login", data={
        "email": "akshendra.dwivedi1@gmail.com",
        "password": "Admin@PocketPay2026"
    }, allow_redirects=False)
    assert admin_login_res.status_code in [200, 302], f"Admin login failed: {admin_login_res.status_code}"
    
    res = admin_session.get(f"{BASE_URL}/admin/dashboard")
    assert res.status_code == 200, f"Admin dashboard failed: {res.status_code}"
    print("[PASS] 13. Admin Dashboard Access (Akshendra authenticated as Admin, 200 OK)")

    # 14. Admin Live Database Stats API
    res = admin_session.get(f"{BASE_URL}/admin/api/stats")
    assert res.status_code == 200, f"Admin stats failed: {res.status_code}"
    stats = res.json()["data"]
    print(f"[PASS] 14. Admin Real-Time Database Metrics: Users={stats['total_users']}, Pockets={stats['total_pockets']}, Balance=Rs.{stats['total_platform_funds']:,.2f}")

    # 15. Admin User Directory API
    res = admin_session.get(f"{BASE_URL}/admin/api/users")
    assert res.status_code == 200
    print(f"[PASS] 15. Admin User Directory API ({res.json()['data']['total_items']} registered users)")

    # 16. Admin Smart Pockets API
    res = admin_session.get(f"{BASE_URL}/admin/api/pockets")
    assert res.status_code == 200
    print(f"[PASS] 16. Admin Smart Pockets API ({res.json()['data']['total_items']} active pockets)")

    # 17. Admin Analytics Charts API
    res = admin_session.get(f"{BASE_URL}/admin/api/analytics/charts")
    assert res.status_code == 200
    print("[PASS] 17. Admin Real Analytics Charts API (7-day live volume & category breakdown)")

    # 18. User App Access with Admin Account
    res = admin_session.get(f"{BASE_URL}/api/wallet/balance")
    assert res.status_code == 200, f"Admin accessing user app failed: {res.status_code}"
    admin_bal = res.json()["data"]["wallet_balance"]
    print(f"[PASS] 18. Dual Admin Access: Admin can use PocketPay User App (Balance: Rs.{admin_bal:,.2f})")

    # 19. Admin Logout
    res = admin_session.get(f"{BASE_URL}/admin/logout", allow_redirects=False)
    assert res.status_code == 302, f"Admin logout failed: {res.status_code}"
    print("[PASS] 19. Admin Logout Successful (302 Redirect to /admin/login)")
    
    print("=" * 70)
    print("ALL 19 LIVE FINTECH & ADMIN VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    test_live_server()

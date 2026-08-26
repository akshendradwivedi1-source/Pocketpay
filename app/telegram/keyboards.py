from typing import List, Optional
from app.models.pocket import Pocket


def main_menu_keyboard(is_logged_in: bool = False) -> dict:
    """Returns the main Telegram inline keyboard based on login state"""
    if not is_logged_in:
        return {
            "inline_keyboard": [
                [
                    {"text": "🔐 Login", "callback_data": "auth_login"},
                    {"text": "📝 Create Account", "callback_data": "auth_register"}
                ],
                [
                    {"text": "ℹ️ Help & Guide", "callback_data": "help"}
                ]
            ]
        }

    return {
        "inline_keyboard": [
            [
                {"text": "💰 Balance", "callback_data": "menu_balance"},
                {"text": "🗂️ My Pockets", "callback_data": "menu_pockets"}
            ],
            [
                {"text": "➕ Create Pocket", "callback_data": "menu_create_pocket"},
                {"text": "💸 Transfer", "callback_data": "menu_transfer"}
            ],
            [
                {"text": "📜 Transactions", "callback_data": "menu_transactions"},
                {"text": "🏦 Bank Account", "callback_data": "menu_bank"}
            ],
            [
                {"text": "⚙️ Account", "callback_data": "menu_account"},
                {"text": "🚪 Logout", "callback_data": "menu_logout"}
            ]
        ]
    }


def pockets_keyboard(pockets: List[Pocket]) -> dict:
    """Generates dynamic inline keyboard listing all user pockets"""
    buttons = []
    for p in pockets:
        buttons.append([
            {"text": f"📁 {p.name} — ₹{p.current_balance:,.2f}", "callback_data": f"pocket_view_{p.id}"}
        ])

    buttons.append([
        {"text": "➕ Create Pocket", "callback_data": "menu_create_pocket"},
        {"text": "🔙 Main Menu", "callback_data": "menu_main"}
    ])

    return {"inline_keyboard": buttons}


def pocket_detail_keyboard(pocket_id: int) -> dict:
    """Buttons for viewing a specific pocket"""
    return {
        "inline_keyboard": [
            [
                {"text": "💸 Add Money to Pocket", "callback_data": f"transfer_to_pocket_{pocket_id}"},
                {"text": "🔄 Transfer Out", "callback_data": f"transfer_from_pocket_{pocket_id}"}
            ],
            [
                {"text": "🗂️ All Pockets", "callback_data": "menu_pockets"},
                {"text": "🔙 Main Menu", "callback_data": "menu_main"}
            ]
        ]
    }


def transfer_source_keyboard(pockets: List[Pocket], wallet_balance: float) -> dict:
    """Select source of funds for transfer"""
    buttons = [
        [{"text": f"💳 Available Balance (₹{wallet_balance:,.2f})", "callback_data": "tx_src_wallet"}]
    ]
    for p in pockets:
        if p.current_balance > 0:
            buttons.append([
                {"text": f"📁 {p.name} (₹{p.current_balance:,.2f})", "callback_data": f"tx_src_pocket_{p.id}"}
            ])
    buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_action"}])
    return {"inline_keyboard": buttons}


def transfer_dest_keyboard(pockets: List[Pocket], exclude_pocket_id: Optional[int] = None, allow_wallet: bool = True) -> dict:
    """Select destination of funds for transfer"""
    buttons = []
    if allow_wallet:
        buttons.append([{"text": "💳 Available Balance", "callback_data": "tx_dst_wallet"}])
    for p in pockets:
        if p.id != exclude_pocket_id:
            buttons.append([
                {"text": f"📁 {p.name} (₹{p.current_balance:,.2f})", "callback_data": f"tx_dst_pocket_{p.id}"}
            ])
    buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_action"}])
    return {"inline_keyboard": buttons}


def confirm_keyboard(confirm_data: str, cancel_data: str = "cancel_action", confirm_label: str = "✅ Confirm", cancel_label: str = "❌ Cancel") -> dict:
    """Universal confirmation inline keyboard"""
    return {
        "inline_keyboard": [
            [
                {"text": confirm_label, "callback_data": confirm_data},
                {"text": cancel_label, "callback_data": cancel_data}
            ]
        ]
    }


def account_menu_keyboard() -> dict:
    """Account & Settings submenu keyboard"""
    return {
        "inline_keyboard": [
            [
                {"text": "👤 Profile Details", "callback_data": "acc_profile"},
                {"text": "🔒 Security & PIN", "callback_data": "acc_security"}
            ],
            [
                {"text": "🗑️ Delete Account", "callback_data": "acc_delete_init"}
            ],
            [
                {"text": "🚪 Logout", "callback_data": "menu_logout"},
                {"text": "🔙 Main Menu", "callback_data": "menu_main"}
            ]
        ]
    }


def back_to_menu_keyboard() -> dict:
    """Simple Back button"""
    return {
        "inline_keyboard": [
            [{"text": "🔙 Main Menu", "callback_data": "menu_main"}]
        ]
    }


def cancel_keyboard() -> dict:
    """Simple Cancel button"""
    return {
        "inline_keyboard": [
            [{"text": "❌ Cancel Action", "callback_data": "cancel_action"}]
        ]
    }

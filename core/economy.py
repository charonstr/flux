from core.database import applyledger, syncwallet, walletbalance


INITIAL_GRANT_GOLD = 1000

TX_INITIAL_GRANT = "initial_grant"
TX_REWARD = "reward"
TX_PURCHASE = "purchase"
TX_ADJUSTMENT = "adjustment"


def initialize_user_economy(user_id: int, reference_id: str | None = None) -> bool:
    ref = reference_id or f"signup:{int(user_id)}:initial_grant"
    return applyledger(int(user_id), INITIAL_GRANT_GOLD, TX_INITIAL_GRANT, "signup bonus", ref)


def get_balance(user_id: int) -> int:
    # Keep wallet aligned with immutable ledger before every balance read.
    return syncwallet(int(user_id))


def add_gold(user_id: int, amount: int, description: str, reference_id: str | None = None, tx_type: str = TX_REWARD) -> bool:
    value = int(amount)
    if value <= 0:
        raise ValueError("amount must be positive")
    return applyledger(int(user_id), value, tx_type, description, reference_id)


def spend_gold(user_id: int, amount: int, description: str, reference_id: str | None = None, tx_type: str = TX_PURCHASE) -> bool:
    value = int(amount)
    if value <= 0:
        raise ValueError("amount must be positive")
    if walletbalance(int(user_id)) < value:
        return False
    return applyledger(int(user_id), -value, tx_type, description, reference_id)


def adjust_gold(user_id: int, amount: int, description: str, reference_id: str | None = None) -> bool:
    value = int(amount)
    if value == 0:
        return False
    return applyledger(int(user_id), value, TX_ADJUSTMENT, description, reference_id)


def reconcile_wallet(user_id: int) -> int:
    return syncwallet(int(user_id))

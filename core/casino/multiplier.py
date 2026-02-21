import random
import secrets
import time
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from threading import Lock
from typing import Callable


MIN_BET = 10
MAX_BET = 10000
PICK_COUNT = 5
HISTORY_LIMIT = 10
REVEAL_INTERVAL_MS = 350
RNG = random.SystemRandom()

# Assumptions from product prompt:
# - 0.4x -> 30 weight
# - 2.5x -> 0.3 weight (typo fix for duplicate 2.3 line)
MULTIPLIER_WEIGHTS: list[tuple[str, float]] = [
    ("0.1", 95),
    ("0.2", 85),
    ("0.3", 40),
    ("0.4", 30),
    ("0.5", 20),
    ("1", 10),
    ("1.5", 5),
    ("2", 1),
    ("2.3", 0.5),
    ("2.5", 0.3),
    ("3", 0.1),
    ("3.5", 0.05),
    ("4", 0.01),
    ("5", 0.005),
    ("6", 0.001),
    ("7", 0.0005),
    ("8", 0.0001),
    ("9", 0.00005),
    ("10", 0.00001),
    ("30", 0.000005),
    ("50", 0.0000001),
]

ALLOWED_MULTIPLIERS = {x[0] for x in MULTIPLIER_WEIGHTS}


def _fmt_decimal(val: Decimal) -> str:
    norm = val.normalize()
    text = format(norm, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _compute_payout_int(bet_amount: int, total_multiplier: Decimal) -> int:
    amount = (Decimal(int(bet_amount)) * total_multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(amount)


def _weighted_pick() -> Decimal:
    total = float(sum(w for _, w in MULTIPLIER_WEIGHTS))
    target = RNG.random() * total
    upto = 0.0
    for value, weight in MULTIPLIER_WEIGHTS:
        upto += float(weight)
        if target <= upto:
            return Decimal(value)
    return Decimal(MULTIPLIER_WEIGHTS[-1][0])


@dataclass
class MultiplierRound:
    round_id: str
    user_id: int
    bet_amount: int
    picks: list[str] = field(default_factory=list)
    total_multiplier: str = "0"
    payout_amount: int = 0
    created_at: float = field(default_factory=time.time)
    status: str = "created"  # created/debited/revealed/credited/finished/failed
    error: str = ""
    idempotency_key: str = ""

    def to_dict(self) -> dict:
        return {
            "round_id": self.round_id,
            "user_id": int(self.user_id),
            "bet_amount": int(self.bet_amount),
            "picks": self.picks[:],
            "total_multiplier": self.total_multiplier,
            "payout_amount": int(self.payout_amount),
            "created_at": float(self.created_at),
            "status": self.status,
            "error": self.error,
        }


class MultiplierManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._current: dict[int, MultiplierRound] = {}
        self._history: dict[int, list[MultiplierRound]] = {}
        self._in_progress: set[int] = set()
        self._idem: dict[int, dict[str, dict]] = {}

    def constants(self) -> dict:
        return {
            "min_bet": MIN_BET,
            "max_bet": MAX_BET,
            "pick_count": PICK_COUNT,
            "reveal_interval_ms": REVEAL_INTERVAL_MS,
            "weights": [{"multiplier": m, "weight": w} for m, w in MULTIPLIER_WEIGHTS],
        }

    def state(self, user_id: int) -> dict:
        uid = int(user_id)
        with self._lock:
            cur = self._current.get(uid)
            return {
                "in_progress": uid in self._in_progress,
                "current_round": cur.to_dict() if cur else None,
            }

    def history(self, user_id: int, limit: int = HISTORY_LIMIT) -> list[dict]:
        uid = int(user_id)
        with self._lock:
            rows = self._history.get(uid, [])
            return [r.to_dict() for r in rows[: max(1, int(limit))]]

    def play(
        self,
        user_id: int,
        bet_amount: int,
        idempotency_key: str,
        settle_round: Callable[[int, str, int, int], tuple[bool, str]],
    ) -> tuple[bool, dict]:
        uid = int(user_id)
        idem = str(idempotency_key or "").strip()
        bet = int(bet_amount or 0)
        if not idem:
            return False, {"error": "missing_idempotency"}
        if bet < MIN_BET:
            return False, {"error": "min_bet"}
        if bet > MAX_BET:
            return False, {"error": "max_bet"}

        with self._lock:
            cache = self._idem.setdefault(uid, {})
            if idem in cache:
                cached = cache[idem]
                out = dict(cached.get("data") or {})
                out["idempotent_replay"] = True
                return bool(cached.get("ok")), out
            if uid in self._in_progress:
                cur = self._current.get(uid)
                return False, {
                    "error": "round_in_progress",
                    "state": {"in_progress": True, "current_round": cur.to_dict() if cur else None},
                }
            self._in_progress.add(uid)

        rnd = MultiplierRound(
            round_id=secrets.token_hex(10),
            user_id=uid,
            bet_amount=bet,
            status="created",
            idempotency_key=idem,
        )

        outcome_ok = False
        outcome_data: dict = {}
        try:
            picks = [_weighted_pick() for _ in range(PICK_COUNT)]
            total_multiplier = sum(picks, Decimal("0"))
            payout_amount = _compute_payout_int(bet, total_multiplier)
            rnd.picks = [_fmt_decimal(p) for p in picks]
            rnd.total_multiplier = _fmt_decimal(total_multiplier)
            rnd.payout_amount = int(payout_amount)
            rnd.status = "revealed"

            ok, err = settle_round(uid, rnd.round_id, bet, payout_amount)
            if not ok:
                rnd.status = "failed"
                rnd.error = str(err or "settlement_failed")
                outcome_ok = False
                outcome_data = {"error": rnd.error, "state": rnd.to_dict()}
                return outcome_ok, outcome_data

            rnd.status = "finished"
            outcome_ok = True
            outcome_data = {"state": rnd.to_dict()}
            return outcome_ok, outcome_data
        finally:
            with self._lock:
                self._in_progress.discard(uid)
                self._current[uid] = rnd
                items = self._history.setdefault(uid, [])
                items.insert(0, rnd)
                del items[HISTORY_LIMIT:]
                if rnd.status in {"finished", "failed"}:
                    self._idem.setdefault(uid, {})[idem] = {"ok": outcome_ok, "data": dict(outcome_data)}


MANAGER = MultiplierManager()

import secrets
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any
import random


ROULETTE_VARIANT = "EU"
BETTING_TIMER_SECONDS = 20
RESULT_DISPLAY_SECONDS = 5
MIN_BET = 10
MAX_BET = 10000
MAX_TOTAL_BET_PER_ROUND = 20000
CHIPS = [10, 50, 100, 500, 1000, 5000]
RNG = random.SystemRandom()

EU_WHEEL = [
    "0", "32", "15", "19", "4", "21", "2", "25", "17", "34", "6", "27", "13", "36", "11", "30", "8", "23", "10", "5",
    "24", "16", "33", "1", "20", "14", "31", "9", "22", "18", "29", "7", "28", "12", "35", "3", "26",
]
US_WHEEL = [
    "0", "28", "9", "26", "30", "11", "7", "20", "32", "17", "5", "22", "34", "15", "3", "24", "36", "13", "1", "00",
    "27", "10", "25", "29", "12", "8", "19", "31", "18", "6", "21", "33", "16", "4", "23", "35", "14", "2",
]
RED_NUMBERS = {"1", "3", "5", "7", "9", "12", "14", "16", "18", "19", "21", "23", "25", "27", "30", "32", "34", "36"}


def wheel_pockets() -> list[str]:
    return EU_WHEEL[:] if ROULETTE_VARIANT == "EU" else US_WHEEL[:]


def color_of(pocket: str) -> str:
    if pocket in {"0", "00"}:
        return "green"
    return "red" if pocket in RED_NUMBERS else "black"


def _normalize_num(n: Any) -> str:
    s = str(n).strip()
    if s == "00" and ROULETTE_VARIANT == "US":
        return s
    if s.isdigit() and 0 <= int(s) <= 36:
        return str(int(s))
    return ""


def _is_valid_straight(selection: list[str]) -> bool:
    return len(selection) == 1 and _normalize_num(selection[0]) in set(wheel_pockets())


def _is_valid_split(selection: list[str]) -> bool:
    if len(selection) != 2:
        return False
    a = _normalize_num(selection[0])
    b = _normalize_num(selection[1])
    if not a or not b or a in {"0", "00"} or b in {"0", "00"}:
        return False
    x = int(a)
    y = int(b)
    if abs(x - y) == 3:
        return True
    if abs(x - y) == 1:
        lo = min(x, y)
        return lo % 3 != 0
    return False


def _is_valid_street(selection: list[str]) -> bool:
    if len(selection) != 3:
        return False
    vals = sorted(int(_normalize_num(s) or -1) for s in selection)
    if vals[0] < 1:
        return False
    return vals[1] == vals[0] + 1 and vals[2] == vals[1] + 1 and vals[0] % 3 == 1


def _is_valid_corner(selection: list[str]) -> bool:
    if len(selection) != 4:
        return False
    vals = sorted(int(_normalize_num(s) or -1) for s in selection)
    if vals[0] < 1:
        return False
    candidates = [vals[0], vals[0] + 1, vals[0] + 3, vals[0] + 4]
    return vals == candidates and vals[0] % 3 in {1, 2}


def _is_valid_sixline(selection: list[str]) -> bool:
    if len(selection) != 6:
        return False
    vals = sorted(int(_normalize_num(s) or -1) for s in selection)
    if vals[0] < 1:
        return False
    first = vals[0]
    needed = [first, first + 1, first + 2, first + 3, first + 4, first + 5]
    return vals == needed and first % 3 == 1


def _selection_key(bet_type: str, selection: list[str]) -> str:
    if bet_type in {"red", "black", "odd", "even", "low", "high", "dozen1", "dozen2", "dozen3", "col1", "col2", "col3"}:
        return bet_type
    return f"{bet_type}:{','.join(sorted(selection))}"


def _validate_bet(bet_type: str, selection: list[str], amount: int) -> tuple[bool, str]:
    if amount < MIN_BET:
        return False, "min_bet"
    if amount > MAX_BET:
        return False, "max_bet"
    if bet_type == "straight" and _is_valid_straight(selection):
        return True, ""
    if bet_type == "split" and _is_valid_split(selection):
        return True, ""
    if bet_type == "street" and _is_valid_street(selection):
        return True, ""
    if bet_type == "corner" and _is_valid_corner(selection):
        return True, ""
    if bet_type == "sixline" and _is_valid_sixline(selection):
        return True, ""
    if bet_type in {"red", "black", "odd", "even", "low", "high", "dozen1", "dozen2", "dozen3", "col1", "col2", "col3"}:
        return True, ""
    return False, "invalid_selection"


def _wins(bet_type: str, selection: list[str], pocket: str) -> bool:
    if bet_type == "straight":
        return pocket in selection
    if bet_type in {"split", "street", "corner", "sixline"}:
        return pocket in selection
    if pocket in {"0", "00"}:
        return False
    n = int(pocket)
    if bet_type == "red":
        return color_of(pocket) == "red"
    if bet_type == "black":
        return color_of(pocket) == "black"
    if bet_type == "odd":
        return n % 2 == 1
    if bet_type == "even":
        return n % 2 == 0
    if bet_type == "low":
        return 1 <= n <= 18
    if bet_type == "high":
        return 19 <= n <= 36
    if bet_type == "dozen1":
        return 1 <= n <= 12
    if bet_type == "dozen2":
        return 13 <= n <= 24
    if bet_type == "dozen3":
        return 25 <= n <= 36
    if bet_type == "col1":
        return n % 3 == 1
    if bet_type == "col2":
        return n % 3 == 2
    if bet_type == "col3":
        return n % 3 == 0
    return False


def _ratio(bet_type: str) -> int:
    return {
        "straight": 35,
        "split": 17,
        "street": 11,
        "corner": 8,
        "sixline": 5,
        "red": 1,
        "black": 1,
        "odd": 1,
        "even": 1,
        "low": 1,
        "high": 1,
        "dozen1": 2,
        "dozen2": 2,
        "dozen3": 2,
        "col1": 2,
        "col2": 2,
        "col3": 2,
    }[bet_type]


@dataclass
class Bet:
    bet_id: str
    bet_type: str
    selection: list[str]
    amount: int


@dataclass
class RouletteRound:
    round_id: str
    state: str = "betting_open"
    betting_open_until: float = 0.0
    result_pocket: str = ""
    bets: list[Bet] = field(default_factory=list)
    idempotency: set[str] = field(default_factory=set)
    stake_locked: bool = False
    settled: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def total_bet(self) -> int:
        return sum(b.amount for b in self.bets)

    def to_dict(self) -> dict:
        return {
            "round_id": self.round_id,
            "state": self.state,
            "betting_open_until": self.betting_open_until,
            "result_pocket": self.result_pocket,
            "result_color": color_of(self.result_pocket) if self.result_pocket else "",
            "bets": [{"bet_id": b.bet_id, "bet_type": b.bet_type, "selection": b.selection, "amount": b.amount} for b in self.bets],
            "total_bet": self.total_bet(),
            "stake_locked": bool(self.stake_locked),
            "settled": bool(self.settled),
            "remaining_seconds": max(0, int(self.betting_open_until - time.time())) if self.state == "betting_open" else 0,
        }


class RouletteManager:
    def __init__(self) -> None:
        self._rounds: dict[int, RouletteRound] = {}
        self._lock = Lock()

    def _current(self, user_id: int) -> RouletteRound:
        uid = int(user_id)
        rnd = self._rounds.get(uid)
        now = time.time()
        if rnd is None or rnd.state in {"finished"}:
            rnd = RouletteRound(round_id=secrets.token_hex(10), betting_open_until=now + BETTING_TIMER_SECONDS)
            self._rounds[uid] = rnd
        elif rnd.state == "betting_open" and now >= rnd.betting_open_until:
            rnd.state = "betting_locked"
        return rnd

    def get_state(self, user_id: int) -> dict:
        with self._lock:
            return self._current(user_id).to_dict()

    def start_round(self, user_id: int) -> dict:
        with self._lock:
            rnd = RouletteRound(round_id=secrets.token_hex(10), betting_open_until=time.time() + BETTING_TIMER_SECONDS)
            self._rounds[int(user_id)] = rnd
            return rnd.to_dict()

    def place_bet(self, user_id: int, bet_type: str, selection: list[str], amount: int, idempotency_key: str) -> tuple[bool, dict]:
        with self._lock:
            rnd = self._current(user_id)
            if rnd.state != "betting_open":
                return False, {"error": "betting_closed", "state": rnd.to_dict()}
            if idempotency_key and idempotency_key in rnd.idempotency:
                return True, {"state": rnd.to_dict()}
            ok, err = _validate_bet(bet_type, selection, int(amount))
            if not ok:
                return False, {"error": err, "state": rnd.to_dict()}
            total = rnd.total_bet() + int(amount)
            if total > MAX_TOTAL_BET_PER_ROUND:
                return False, {"error": "max_total_bet", "state": rnd.to_dict()}

            key = _selection_key(bet_type, selection)
            same_spot = sum(b.amount for b in rnd.bets if _selection_key(b.bet_type, b.selection) == key)
            if same_spot + int(amount) > MAX_BET:
                return False, {"error": "max_bet", "state": rnd.to_dict()}

            rnd.bets.append(Bet(bet_id=secrets.token_hex(8), bet_type=bet_type, selection=[str(s) for s in selection], amount=int(amount)))
            if idempotency_key:
                rnd.idempotency.add(idempotency_key)
            rnd.updated_at = time.time()
            return True, {"state": rnd.to_dict()}

    def undo(self, user_id: int) -> tuple[bool, dict]:
        with self._lock:
            rnd = self._current(user_id)
            if rnd.state != "betting_open":
                return False, {"error": "betting_closed", "state": rnd.to_dict()}
            if rnd.bets:
                rnd.bets.pop()
            rnd.updated_at = time.time()
            return True, {"state": rnd.to_dict()}

    def clear(self, user_id: int) -> tuple[bool, dict]:
        with self._lock:
            rnd = self._current(user_id)
            if rnd.state != "betting_open":
                return False, {"error": "betting_closed", "state": rnd.to_dict()}
            rnd.bets = []
            rnd.updated_at = time.time()
            return True, {"state": rnd.to_dict()}

    def lock_bets(self, user_id: int, idempotency_key: str) -> tuple[bool, dict]:
        with self._lock:
            rnd = self._current(user_id)
            if rnd.state not in {"betting_open", "betting_locked"}:
                return False, {"error": "invalid_state", "state": rnd.to_dict()}
            if idempotency_key and idempotency_key in rnd.idempotency:
                return True, {"state": rnd.to_dict()}
            if not rnd.bets:
                return False, {"error": "no_bets", "state": rnd.to_dict()}
            rnd.state = "betting_locked"
            if idempotency_key:
                rnd.idempotency.add(idempotency_key)
            rnd.updated_at = time.time()
            return True, {"state": rnd.to_dict()}

    def spin(self, user_id: int, idempotency_key: str) -> tuple[bool, dict]:
        with self._lock:
            rnd = self._current(user_id)
            if rnd.state == "betting_open" and time.time() >= rnd.betting_open_until:
                rnd.state = "betting_locked"
            if rnd.state != "betting_locked":
                return False, {"error": "invalid_state", "state": rnd.to_dict()}
            if not rnd.bets:
                return False, {"error": "no_bets", "state": rnd.to_dict()}
            if idempotency_key and idempotency_key in rnd.idempotency and rnd.result_pocket:
                return True, {"state": rnd.to_dict()}
            rnd.state = "spinning"
            rnd.result_pocket = RNG.choice(wheel_pockets())
            rnd.state = "result_revealed"
            if idempotency_key:
                rnd.idempotency.add(idempotency_key)
            rnd.updated_at = time.time()
            return True, {"state": rnd.to_dict()}

    def settle(self, user_id: int) -> tuple[bool, dict]:
        with self._lock:
            rnd = self._current(user_id)
            if rnd.state not in {"result_revealed", "settling"}:
                return False, {"error": "invalid_state", "state": rnd.to_dict()}
            if not rnd.result_pocket:
                return False, {"error": "no_result", "state": rnd.to_dict()}
            if rnd.settled:
                total_stake = rnd.total_bet()
                return True, {"state": rnd.to_dict(), "total_stake": total_stake, "total_payout": 0, "net_delta": 0}
            rnd.state = "settling"
            total_stake = rnd.total_bet()
            total_payout = 0
            for bet in rnd.bets:
                if _wins(bet.bet_type, bet.selection, rnd.result_pocket):
                    total_payout += bet.amount * (_ratio(bet.bet_type) + 1)
            net_delta = total_payout - total_stake
            rnd.state = "finished"
            rnd.settled = True
            rnd.updated_at = time.time()
            return True, {"state": rnd.to_dict(), "total_stake": total_stake, "total_payout": total_payout, "net_delta": net_delta}

    def constants(self) -> dict:
        return {
            "variant": ROULETTE_VARIANT,
            "wheel": wheel_pockets(),
            "colors": {str(n): color_of(str(n)) for n in wheel_pockets()},
            "chips": CHIPS,
            "min_bet": MIN_BET,
            "max_bet": MAX_BET,
            "max_total_bet_per_round": MAX_TOTAL_BET_PER_ROUND,
            "betting_timer_seconds": BETTING_TIMER_SECONDS,
            "result_display_seconds": RESULT_DISPLAY_SECONDS,
        }

    def mark_stake_locked(self, user_id: int) -> dict:
        with self._lock:
            rnd = self._current(user_id)
            rnd.stake_locked = True
            rnd.updated_at = time.time()
            return rnd.to_dict()


MANAGER = RouletteManager()

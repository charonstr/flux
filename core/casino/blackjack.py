import random
import secrets
from threading import Lock


RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["H", "D", "C", "S"]
RNG = random.SystemRandom()


def _card_value(rank: str) -> int:
    if rank in {"J", "Q", "K"}:
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_total_details(cards: list[dict]) -> tuple[int, bool]:
    total = 0
    aces = 0
    for card in cards:
        rank = card["rank"]
        if rank == "A":
            aces += 1
        total += _card_value(rank)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    soft = aces > 0
    return total, soft


def is_blackjack(cards: list[dict]) -> bool:
    if len(cards) != 2:
        return False
    total, _ = hand_total_details(cards)
    return total == 21


class BlackjackGame:
    def __init__(self, soft17_stand: bool = True) -> None:
        self.soft17_stand = soft17_stand
        self.deck: list[dict] = []
        self.player_hand: list[dict] = []
        self.dealer_hand: list[dict] = []
        self.phase = "idle"
        self.result = ""
        self.message = "ready"
        self.dealer_hole_hidden = True
        self.current_bet = 0
        self.round_id = ""
        self.settled = False

    def _new_deck(self) -> list[dict]:
        cards = [{"rank": r, "suit": s, "code": f"{r}{s}"} for s in SUITS for r in RANKS]
        RNG.shuffle(cards)
        return cards

    def _draw(self) -> dict | None:
        if not self.deck:
            return None
        return self.deck.pop()

    def _public_dealer_hand(self) -> list[dict]:
        out = []
        for idx, card in enumerate(self.dealer_hand):
            if idx == 1 and self.dealer_hole_hidden:
                out.append({"hidden": True})
            else:
                out.append(card)
        return out

    def _dealer_visible_total(self) -> str:
        if not self.dealer_hand:
            return "?"
        if self.dealer_hole_hidden:
            total, _ = hand_total_details([self.dealer_hand[0]])
            return f"{total} + ?"
        total, _ = hand_total_details(self.dealer_hand)
        return str(total)

    def _state(self) -> dict:
        player_total, _ = hand_total_details(self.player_hand)
        dealer_total, _ = hand_total_details(self.dealer_hand) if self.dealer_hand else (0, False)
        return {
            "deck_count": len(self.deck),
            "player_hand": self.player_hand,
            "dealer_hand": self._public_dealer_hand(),
            "phase": self.phase,
            "result": self.result,
            "message": self.message,
            "player_total": player_total,
            "dealer_total": dealer_total,
            "dealer_visible_total": self._dealer_visible_total(),
            "bet": int(self.current_bet),
            "round_id": self.round_id,
            "settled": bool(self.settled),
        }

    def start_round(self, bet: int) -> tuple[bool, dict]:
        value = int(bet or 0)
        if value <= 0:
            return False, {"error": "invalid_bet", "state": self._state()}
        self.current_bet = value
        self.deck = self._new_deck()
        self.player_hand = []
        self.dealer_hand = []
        self.phase = "dealing"
        self.result = ""
        self.message = "dealing cards"
        self.dealer_hole_hidden = True
        self.round_id = secrets.token_hex(8)
        self.settled = False

        c1 = self._draw()
        c2 = self._draw()
        c3 = self._draw()
        c4 = self._draw()
        if not c1 or not c2 or not c3 or not c4:
            self.phase = "finished"
            self.result = "push"
            self.message = "deck exhausted"
            return False, {"error": "deck_exhausted", "state": self._state()}
        self.player_hand.append(c1)
        self.dealer_hand.append(c2)
        self.player_hand.append(c3)
        self.dealer_hand.append(c4)

        player_bj = is_blackjack(self.player_hand)
        dealer_bj = is_blackjack(self.dealer_hand)
        if player_bj and dealer_bj:
            self.dealer_hole_hidden = False
            self.phase = "finished"
            self.result = "push"
            self.message = "both blackjack"
            return True, self._state()
        if player_bj:
            self.dealer_hole_hidden = False
            self.phase = "finished"
            self.result = "blackjack"
            self.message = "player blackjack"
            return True, self._state()
        if dealer_bj:
            self.dealer_hole_hidden = False
            self.phase = "finished"
            self.result = "lose"
            self.message = "dealer blackjack"
            return True, self._state()

        self.phase = "player_turn"
        self.message = "player turn"
        return True, self._state()

    def get_state(self) -> dict:
        return self._state()

    def hit(self) -> tuple[bool, dict]:
        if self.phase != "player_turn":
            return False, {"error": "invalid_state", "state": self._state()}
        card = self._draw()
        if not card:
            self.phase = "finished"
            self.result = "push"
            self.message = "deck exhausted"
            return False, {"error": "deck_exhausted", "state": self._state()}
        self.player_hand.append(card)
        total, _ = hand_total_details(self.player_hand)
        if total > 21:
            self.dealer_hole_hidden = False
            self.phase = "finished"
            self.result = "lose"
            self.message = "player bust"
        elif total == 21:
            return self.stand()
        else:
            self.message = "player turn"
        return True, self._state()

    def stand(self) -> tuple[bool, dict]:
        if self.phase != "player_turn":
            return False, {"error": "invalid_state", "state": self._state()}

        self.phase = "dealer_turn"
        self.dealer_hole_hidden = False
        self.message = "dealer turn"

        while True:
            dealer_total, dealer_soft = hand_total_details(self.dealer_hand)
            if dealer_total < 17:
                card = self._draw()
                if not card:
                    self.phase = "finished"
                    self.result = "push"
                    self.message = "deck exhausted"
                    return True, self._state()
                self.dealer_hand.append(card)
                continue
            if dealer_total == 17 and dealer_soft and not self.soft17_stand:
                card = self._draw()
                if not card:
                    self.phase = "finished"
                    self.result = "push"
                    self.message = "deck exhausted"
                    return True, self._state()
                self.dealer_hand.append(card)
                continue
            break

        player_total, _ = hand_total_details(self.player_hand)
        dealer_total, _ = hand_total_details(self.dealer_hand)

        self.phase = "finished"
        if dealer_total > 21:
            self.result = "win"
            self.message = "dealer bust"
        elif player_total > dealer_total:
            self.result = "win"
            self.message = "player wins"
        elif player_total < dealer_total:
            self.result = "lose"
            self.message = "dealer wins"
        else:
            self.result = "push"
            self.message = "push"
        return True, self._state()

    def mark_settled(self) -> dict:
        self.settled = True
        return self._state()


class BlackjackManager:
    def __init__(self) -> None:
        self._games: dict[int, BlackjackGame] = {}
        self._lock = Lock()

    def _get(self, user_id: int) -> BlackjackGame:
        uid = int(user_id)
        with self._lock:
            game = self._games.get(uid)
            if game is None:
                game = BlackjackGame(soft17_stand=True)
                self._games[uid] = game
            return game

    def start_round(self, user_id: int, bet: int) -> tuple[bool, dict]:
        return self._get(user_id).start_round(bet)

    def get_state(self, user_id: int) -> dict:
        return self._get(user_id).get_state()

    def hit(self, user_id: int) -> tuple[bool, dict]:
        return self._get(user_id).hit()

    def stand(self, user_id: int) -> tuple[bool, dict]:
        return self._get(user_id).stand()

    def mark_settled(self, user_id: int) -> dict:
        return self._get(user_id).mark_settled()


MANAGER = BlackjackManager()

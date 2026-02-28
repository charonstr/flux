import random
import secrets
import time
from threading import Lock

CASE_HISTORY_LIMIT = 10
RNG = random.SystemRandom()

CASES = {
    "afet": {
        "id": "afet",
        "name": "Felaket Kasasi",
        "price": 1000,
        "items": [
            {"id": "nova_sand_dune", "name": "Nova | Sand Dune", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 250.0, "multiplier": 0.10, "img": "/assets/casino/case/afet/nova_sand_dune.png"},
            {"id": "p250_boreal_forest", "name": "P250 | Boreal Forest", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 200.0, "multiplier": 0.15, "img": "/assets/casino/case/afet/p250_boreal_forest.png"},
            {"id": "ump45_urban_ddpat", "name": "UMP-45 | Urban DDPAT", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 150.0, "multiplier": 0.20, "img": "/assets/casino/case/afet/ump45_urban_ddpat.png"},
            {"id": "m249_contrast_spray", "name": "M249 | Contrast Spray", "rarity": "Industrial Grade", "color": "#5e98d9", "weight": 120.0, "multiplier": 0.35, "img": "/assets/casino/case/afet/m249_contrast_spray.png"},
            {"id": "g3sg1_desert_storm", "name": "G3SG1 | Desert Storm", "rarity": "Industrial Grade", "color": "#5e98d9", "weight": 100.0, "multiplier": 0.45, "img": "/assets/casino/case/afet/g3sg1_desert_storm.png"},
            {"id": "p90_module", "name": "P90 | Module", "rarity": "Mil-Spec Grade", "color": "#4b69ff", "weight": 80.0, "multiplier": 0.80, "img": "/assets/casino/case/afet/p90_module.png"},
            {"id": "awp_atheris", "name": "AWP | Atheris", "rarity": "Restricted", "color": "#8847ff", "weight": 35.0, "multiplier": 3.0, "img": "/assets/casino/case/afet/awp_atheris.png"},
            {"id": "glock18_water_elemental", "name": "Glock-18 | Water Elemental", "rarity": "Classified", "color": "#d32ce6", "weight": 12.0, "multiplier": 6.0, "img": "/assets/casino/case/afet/glock18_water_elemental.png"},
            {"id": "usp_s_cortex", "name": "USP-S | Cortex", "rarity": "Classified", "color": "#d32ce6", "weight": 8.0, "multiplier": 8.5, "img": "/assets/casino/case/afet/usp_s_cortex.png"},
            {"id": "ak47_redline", "name": "AK-47 | Redline", "rarity": "Classified", "color": "#d32ce6", "weight": 6.0, "multiplier": 12.0, "img": "/assets/casino/case/afet/ak47_redline.png"},
            {"id": "m4a1_s_printstream", "name": "M4A1-S | Printstream", "rarity": "Covert", "color": "#eb4b4b", "weight": 2.5, "multiplier": 30.0, "img": "/assets/casino/case/afet/m4a1_s_printstream.png"},
            {"id": "awp_dragon_lore", "name": "AWP | Dragon Lore", "rarity": "Covert", "color": "#eb4b4b", "weight": 0.8, "multiplier": 80.0, "img": "/assets/casino/case/afet/awp_dragon_lore.png"},
            {"id": "m4a4_howl", "name": "M4A4 | Howl", "rarity": "Contraband", "color": "#e4ae39", "weight": 0.4, "multiplier": 150.0, "img": "/assets/casino/case/afet/m4a4_howl.png"},
            {"id": "karambit_doppler", "name": "Karambit | Doppler", "rarity": "Rare Special Item", "color": "#ffd700", "weight": 0.25, "multiplier": 200.0, "img": "/assets/casino/case/afet/karambit_doppler.png"},
            {"id": "sport_gloves_pandoras_box", "name": "Sport Gloves | Pandora's Box", "rarity": "Rare Special Item", "color": "#ffd700", "weight": 0.05, "multiplier": 500.0, "img": "/assets/casino/case/afet/sport_gloves_pandoras_box.png"},
        ],
    },
    "kristal": {
        "id": "kristal",
        "name": "Kristal Kasasi",
        "price": 250,
        "items": [
            {"id": "pp_bizon_forest_leaves", "name": "PP-Bizon | Forest Leaves", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 300.0, "multiplier": 0.10, "img": "/assets/casino/case/kristal/pp_bizon_forest_leaves.png"},
            {"id": "five_seven_forest_night", "name": "Five-SeveN | Forest Night", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 250.0, "multiplier": 0.20, "img": "/assets/casino/case/kristal/five_seven_forest_night.png"},
            {"id": "mac10_calf_skin", "name": "MAC-10 | Calf Skin", "rarity": "Industrial Grade", "color": "#5e98d9", "weight": 200.0, "multiplier": 0.40, "img": "/assets/casino/case/kristal/mac10_calf_skin.png"},
            {"id": "sawed_off_origami", "name": "Sawed-Off | Origami", "rarity": "Mil-Spec Grade", "color": "#4b69ff", "weight": 120.0, "multiplier": 0.80, "img": "/assets/casino/case/kristal/sawed_off_origami.png"},
            {"id": "p2000_ivory", "name": "P2000 | Ivory", "rarity": "Mil-Spec Grade", "color": "#4b69ff", "weight": 90.0, "multiplier": 1.10, "img": "/assets/casino/case/kristal/p2000_ivory.png"},
            {"id": "p250_visions", "name": "P250 | Visions", "rarity": "Restricted", "color": "#8847ff", "weight": 40.0, "multiplier": 3.0, "img": "/assets/casino/case/kristal/p250_visions.png"},
            {"id": "mp9_food_chain", "name": "MP9 | Food Chain", "rarity": "Classified", "color": "#d32ce6", "weight": 15.0, "multiplier": 6.0, "img": "/assets/casino/case/kristal/mp9_food_chain.png"},
            {"id": "famas_mecha_industries", "name": "FAMAS | Mecha Industries", "rarity": "Classified", "color": "#d32ce6", "weight": 10.0, "multiplier": 10.0, "img": "/assets/casino/case/kristal/famas_mecha_industries.png"},
            {"id": "mp7_bloodsport", "name": "MP7 | Bloodsport", "rarity": "Covert", "color": "#eb4b4b", "weight": 2.5, "multiplier": 18.0, "img": "/assets/casino/case/kristal/mp7_bloodsport.png"},
            {"id": "five_seven_angry_mob", "name": "Five-SeveN | Angry Mob", "rarity": "Covert", "color": "#eb4b4b", "weight": 2.0, "multiplier": 22.0, "img": "/assets/casino/case/kristal/five_seven_angry_mob.png"},
            {"id": "galil_chatterbox", "name": "Galil AR | Chatterbox", "rarity": "Covert", "color": "#eb4b4b", "weight": 1.5, "multiplier": 28.0, "img": "/assets/casino/case/kristal/galil_chatterbox.png"},
            {"id": "mac10_neon_rider", "name": "MAC-10 | Neon Rider", "rarity": "Covert", "color": "#eb4b4b", "weight": 1.2, "multiplier": 35.0, "img": "/assets/casino/case/kristal/mac10_neon_rider.png"},
            {"id": "usp_s_neo_noir", "name": "USP-S | Neo-Noir", "rarity": "Covert", "color": "#eb4b4b", "weight": 1.0, "multiplier": 45.0, "img": "/assets/casino/case/kristal/usp_s_neo_noir.png"},
            {"id": "deagle_printstream", "name": "Desert Eagle | Printstream", "rarity": "Covert", "color": "#eb4b4b", "weight": 0.8, "multiplier": 60.0, "img": "/assets/casino/case/kristal/deagle_printstream.png"},
            {"id": "m4a1_s_hyper_beast", "name": "M4A1-S | Hyper Beast", "rarity": "Covert", "color": "#eb4b4b", "weight": 0.5, "multiplier": 90.0, "img": "/assets/casino/case/kristal/m4a1_s_hyper_beast.png"},
            {"id": "ak47_neon_rider", "name": "AK-47 | Neon Rider", "rarity": "Covert", "color": "#eb4b4b", "weight": 0.3, "multiplier": 150.0, "img": "/assets/casino/case/kristal/ak47_neon_rider.png"},
            {"id": "awp_fade", "name": "AWP | Fade", "rarity": "Covert", "color": "#eb4b4b", "weight": 0.1, "multiplier": 300.0, "img": "/assets/casino/case/kristal/awp_fade.png"},
            {"id": "ak47_gold_arabesque", "name": "AK-47 | Gold Arabesque", "rarity": "Covert", "color": "#eb4b4b", "weight": 0.02, "multiplier": 800.0, "img": "/assets/casino/case/kristal/ak47_gold_arabesque.png"},
        ],
    },
}


class CaseManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._history: dict[int, dict[str, list]] = {}
        self._idem: dict[int, dict[str, dict]] = {}

    def list_cases(self) -> list[dict]:
        return [{"id": c["id"], "name": c["name"], "price": int(c["price"])} for c in CASES.values()]

    def constants(self, case_id: str) -> dict:
        case = CASES.get(str(case_id or "").strip().lower())
        if not case:
            return {}
        return {
            "case": {"id": case["id"], "name": case["name"], "price": int(case["price"])},
            "items": case["items"],
        }

    def _pick_item(self, case: dict) -> dict:
        items = case.get("items", [])
        total = sum(float(i["weight"]) for i in items)
        target = RNG.random() * total
        upto = 0.0
        for item in items:
            upto += float(item["weight"])
            if target <= upto:
                return item
        return items[0]

    def open_case(self, user_id: int, case_id: str, idempotency_key: str, settle_round) -> tuple[bool, dict]:
        uid = int(user_id)
        key = str(case_id or "").strip().lower()
        idem = str(idempotency_key or "").strip()
        case = CASES.get(key)
        if not idem:
            return False, {"error": "missing_idempotency"}
        if not case:
            return False, {"error": "invalid_case"}

        cache_key = f"{key}:{idem}"
        with self._lock:
            cache = self._idem.setdefault(uid, {})
            if cache_key in cache:
                cached = cache[cache_key]
                out = dict(cached.get("data") or {})
                out["idempotent_replay"] = True
                return bool(cached.get("ok")), out

        winning_item = self._pick_item(case)
        rid = secrets.token_hex(10)
        case_price = int(case["price"])
        multiplier = float(winning_item.get("multiplier", 1.0))
        payout = max(0, int(round(case_price * multiplier)))

        sequence = [self._pick_item(case) for _ in range(45)]
        sequence[35] = winning_item

        ok, err = settle_round(uid, rid, case_price, payout)

        if not ok:
            outcome_ok = False
            outcome_data = {"error": err}
        else:
            outcome_ok = True
            round_data = {
                "round_id": rid,
                "case_id": key,
                "item": winning_item,
                "multiplier": multiplier,
                "sequence": sequence,
                "payout": payout,
                "created_at": time.time(),
            }
            outcome_data = {"state": round_data}

        with self._lock:
            if outcome_ok:
                by_case = self._history.setdefault(uid, {})
                case_rows = by_case.setdefault(key, [])
                case_rows.insert(0, round_data)
                del case_rows[CASE_HISTORY_LIMIT:]
            self._idem.setdefault(uid, {})[cache_key] = {"ok": outcome_ok, "data": dict(outcome_data)}

        return outcome_ok, outcome_data

    def history(self, user_id: int, case_id: str) -> list[dict]:
        uid = int(user_id)
        key = str(case_id or "").strip().lower()
        with self._lock:
            return list(self._history.get(uid, {}).get(key, []))

    def top_wins(self, user_id: int, case_id: str, limit: int = 3) -> list[dict]:
        uid = int(user_id)
        key = str(case_id or "").strip().lower()
        cap = max(1, int(limit))
        with self._lock:
            rows = list(self._history.get(uid, {}).get(key, []))
        rows.sort(key=lambda r: int(r.get("payout", 0) or 0), reverse=True)
        return rows[:cap]


MANAGER = CaseManager()

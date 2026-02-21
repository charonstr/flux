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
            {"id": "ump45_urban_ddpat", "name": "UMP-45 | Urban DDPAT", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 80.0, "multiplier": 0.50, "img": "/assets/casino/case/afet/ump45_urban_ddpat.png"},
            {"id": "p250_boreal_forest", "name": "P250 | Boreal Forest", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 70.0, "multiplier": 0.40, "img": "/assets/casino/case/afet/p250_boreal_forest.png"},
            {"id": "nova_sand_dune", "name": "Nova | Sand Dune", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 60.0, "multiplier": 0.1, "img": "/assets/casino/case/afet/nova_sand_dune.png"},
            {"id": "g3sg1_desert_storm", "name": "G3SG1 | Desert Storm", "rarity": "Industrial Grade", "color": "#5e98d9", "weight": 50.0, "multiplier": 0.20, "img": "/assets/casino/case/afet/g3sg1_desert_storm.png"},
            {"id": "m249_contrast_spray", "name": "M249 | Contrast Spray", "rarity": "Industrial Grade", "color": "#5e98d9", "weight": 40.0, "multiplier": 0.30, "img": "/assets/casino/case/afet/m249_contrast_spray.png"},
            {"id": "glock18_water_elemental", "name": "Glock-18 | Water Elemental", "rarity": "Mil-Spec", "color": "#4b69ff", "weight": 30, "multiplier": 0.5, "img": "/assets/casino/case/afet/glock18_water_elemental.png"},
            {"id": "p90_module", "name": "P90 | Module", "rarity": "Mil-Spec", "color": "#4b69ff", "weight": 50.0, "multiplier": 0.25, "img": "/assets/casino/case/afet/p90_module.png"},
            {"id": "usp_s_cortex", "name": "USP-S | Cortex", "rarity": "Restricted", "color": "#8847ff", "weight": 50.0, "multiplier": 1.5, "img": "/assets/casino/case/afet/usp_s_cortex.png"},
            {"id": "awp_atheris", "name": "AWP | Atheris", "rarity": "Restricted", "color": "#8847ff", "weight": 9, "multiplier": 2, "img": "/assets/casino/case/afet/awp_atheris.png"},
            {"id": "ak47_redline", "name": "AK-47 | Redline", "rarity": "Classified", "color": "#d32ce6", "weight": 8, "multiplier": 2.5, "img": "/assets/casino/case/afet/ak47_redline.png"},
            {"id": "m4a1_s_printstream", "name": "M4A1-S | Printstream", "rarity": "Classified", "color": "#d32ce6", "weight": 5, "multiplier": 3, "img": "/assets/casino/case/afet/m4a1_s_printstream.png"},
            {"id": "m4a4_howl", "name": "M4A4 | Howl", "rarity": "Covert", "color": "#eb4b4b", "weight": 3, "multiplier": 4, "img": "/assets/casino/case/afet/m4a4_howl.png"},
            {"id": "awp_dragon_lore", "name": "AWP | Dragon Lore", "rarity": "Covert", "color": "#eb4b4b", "weight": 2, "multiplier": 5, "img": "/assets/casino/case/afet/awp_dragon_lore.png"},
            {"id": "karambit_doppler", "name": "Karambit | Doppler", "rarity": "Rare Special Item", "color": "#ffd700", "weight": 1, "multiplier": 10, "img": "/assets/casino/case/afet/karambit_doppler.png"},
            {"id": "sport_gloves_pandoras_box", "name": "Sport Gloves | Pandora's Box", "rarity": "Rare Special Item", "color": "#ffd700", "weight": 0.01, "multiplier": 50.0, "img": "/assets/casino/case/afet/sport_gloves_pandoras_box.png"},
        ],
    }
    ,
    "kristal": {
        "id": "kristal",
        "name": "Kristal Kasasi",
        "price": 250,
        "items": [
            {"id": "mac10_calf_skin", "name": "MAC-10 | Calf Skin", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 80.0, "multiplier": 0.20, "img": "/assets/casino/case/kristal/mac10_calf_skin.png"},
            {"id": "p2000_ivory", "name": "P2000 | Ivory", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 80.0, "multiplier": 0.50, "img": "/assets/casino/case/kristal/p2000_ivory.png"},
            {"id": "sawed_off_origami", "name": "Sawed-Off | Origami", "rarity": "Consumer Grade", "color": "#b0c3d9", "weight": 80.0, "multiplier": 0.50, "img": "/assets/casino/case/kristal/sawed_off_origami.png"},
            {"id": "pp_bizon_forest_leaves", "name": "PP-Bizon | Forest Leaves", "rarity": "Industrial Grade", "color": "#5e98d9", "weight": 80.0, "multiplier": 0.40, "img": "/assets/casino/case/kristal/pp_bizon_forest_leaves.png"},
            {"id": "five_seven_forest_night", "name": "Five-SeveN | Forest Night", "rarity": "Industrial Grade", "color": "#5e98d9", "weight": 80.0, "multiplier": 0.30, "img": "/assets/casino/case/kristal/five_seven_forest_night.png"},
            {"id": "ak47_gold_arabesque", "name": "AK-47 | Gold Arabesque", "rarity": "Rare Special Item", "color": "#ffd700", "weight": 0.01, "multiplier": 20.0, "img": "/assets/casino/case/kristal/ak47_gold_arabesque.png"},
            {"id": "awp_fade", "name": "AWP | Fade", "rarity": "Covert", "color": "#eb4b4b", "weight": 0.10, "multiplier": 10.0, "img": "/assets/casino/case/kristal/awp_fade.png"},
            {"id": "ak47_neon_rider", "name": "AK-47 | Neon Rider", "rarity": "Classified", "color": "#d32ce6", "weight": 10.0, "multiplier": 2.0, "img": "/assets/casino/case/kristal/ak47_neon_rider.png"},
            {"id": "m4a1_s_hyper_beast", "name": "M4A1-S | Hyper Beast", "rarity": "Classified", "color": "#d32ce6", "weight": 10.0, "multiplier": 2.0, "img": "/assets/casino/case/kristal/m4a1_s_hyper_beast.png"},
            {"id": "deagle_printstream", "name": "Desert Eagle | Printstream", "rarity": "Classified", "color": "#d32ce6", "weight": 10.0, "multiplier": 2.0, "img": "/assets/casino/case/kristal/deagle_printstream.png"},
            {"id": "usp_s_neo_noir", "name": "USP-S | Neo-Noir", "rarity": "Restricted", "color": "#8847ff", "weight": 23.333333, "multiplier": 1.5, "img": "/assets/casino/case/kristal/usp_s_neo_noir.png"},
            {"id": "mp7_bloodsport", "name": "MP7 | Bloodsport", "rarity": "Restricted", "color": "#8847ff", "weight": 23.333333, "multiplier": 2, "img": "/assets/casino/case/kristal/mp7_bloodsport.png"},
            {"id": "five_seven_angry_mob", "name": "Five-SeveN | Angry Mob", "rarity": "Restricted", "color": "#8847ff", "weight": 23.333333, "multiplier": 2.5, "img": "/assets/casino/case/kristal/five_seven_angry_mob.png"},
            {"id": "mp9_food_chain", "name": "MP9 | Food Chain", "rarity": "Mil-Spec", "color": "#4b69ff", "weight": 1.0, "multiplier": 3, "img": "/assets/casino/case/kristal/mp9_food_chain.png"},
            {"id": "galil_chatterbox", "name": "Galil AR | Chatterbox", "rarity": "Mil-Spec", "color": "#4b69ff", "weight": 1.0, "multiplier": 3, "img": "/assets/casino/case/kristal/galil_chatterbox.png"},
            {"id": "mac10_neon_rider", "name": "MAC-10 | Neon Rider", "rarity": "Mil-Spec", "color": "#4b69ff", "weight": 1.0, "multiplier": 3, "img": "/assets/casino/case/kristal/mac10_neon_rider.png"},
            {"id": "famas_mecha_industries", "name": "FAMAS | Mecha Industries", "rarity": "Mil-Spec", "color": "#4b69ff", "weight": 1.0, "multiplier": 4, "img": "/assets/casino/case/kristal/famas_mecha_industries.png"},
            {"id": "p250_visions", "name": "P250 | Visions", "rarity": "Mil-Spec", "color": "#4b69ff", "weight": 1.0, "multiplier": 4, "img": "/assets/casino/case/kristal/p250_visions.png"},
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


MANAGER = CaseManager()

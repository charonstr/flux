import copy
import json
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint

bp = Blueprint("abysslegacy_backend", __name__)
_registered = False

ROOT = Path(__file__).resolve().parents[1]

# dependency bindings set by register_abysslegacy_backend
app = None
request = None
redirect = None
render_template = None
url_for = None
connect = None
applyledger = None
initialize_user_economy = None
spend_gold = None
userlanguage = None
currentaccount = None
texts = None
navcontext = None
viewfile = None
accountbyid = None


ABYSS_LEGACY_RANK_ORDER = [
    "bronz3",
    "bronz2",
    "bronz1",
    "gumus3",
    "gumus2",
    "gumus1",
    "altin3",
    "altin2",
    "altin1",
    "platin3",
    "platin2",
    "platin1",
    "elmas3",
    "elmas2",
    "elmas1",
    "obsidyen",
]
ABYSS_LEGACY_DEFAULT_RANK = "bronz3"
ABYSS_LEGACY_MAX_RP_WIN = 30
ABYSS_LEGACY_MAX_RP_LOSS = -30
ABYSS_LEGACY_MATCH_TIMEOUT_SEC = 300
ABYSS_LEGACY_BOT_FALLBACK_SEC = 6
ABYSS_LEGACY_BOT_COUNT = 30
ABYSS_LEGACY_BOT_DAILY_MATCH_CAP = 12
ABYSS_LEGACY_BOT_TICK_SEC = 60
ABYSS_LEGACY_HUMAN_BOT_REPEAT_COOLDOWN_SEC = 1800
ABYSS_GLOBAL_REWARDS = [10000, 5000, 1500]
ABYSS_RANK_REWARDS = [2000, 1000]
ABYSS_LEGACY_RANK_LABELS = {
    "bronz3": "Bronz 3",
    "bronz2": "Bronz 2",
    "bronz1": "Bronz 1",
    "gumus3": "Gümüş 3",
    "gumus2": "Gümüş 2",
    "gumus1": "Gümüş 1",
    "altin3": "Altın 3",
    "altin2": "Altın 2",
    "altin1": "Altın 1",
    "platin3": "Platin 3",
    "platin2": "Platin 2",
    "platin1": "Platin 1",
    "elmas3": "Elmas 3",
    "elmas2": "Elmas 2",
    "elmas1": "Elmas 1",
    "obsidyen": "Obsidyen",
}
ABYSS_BOT_STYLES = ["aggressive", "defensive", "balanced", "counter"]
ABYSS_BOT_SYNERGIES = ["Vanguard", "Mystic", "Assassin", "Guardian", "Arcane", "Ranger", "Titan", "Warden"]
ABYSS_BOT_COMMANDERS = ["Kael", "Nyra", "Orion", "Selene", "Draven", "Ilya", "Vex", "Astra"]
ABYSS_BOT_SEED = [
    ("ArdaK", "bronz3"), ("MertA", "bronz3"), ("EgeCan", "bronz2"), ("KeremT", "bronz2"), ("BoraY", "bronz1"), ("DenizR", "bronz1"),
    ("Runa Vale", "gumus3"), ("Selim Voss", "gumus3"), ("Onur Kade", "gumus2"), ("Tuna Riven", "gumus2"), ("Ilker Nox", "gumus1"), ("Mina Hart", "gumus1"),
    ("Arel Dawn", "altin3"), ("Ceren Flux", "altin3"), ("Yalcin Edge", "altin2"), ("Sera Quinn", "altin2"), ("Vera North", "altin1"), ("Kaiden Frost", "altin1"),
    ("Riven Prime", "platin3"), ("Helia Vorn", "platin3"), ("Darian Kyre", "platin2"), ("Liora Zenith", "platin2"), ("Nyxor Vale", "platin1"),
    ("Astra Novus", "elmas3"), ("Velkan Prime", "elmas3"), ("Cyra Helix", "elmas2"), ("Orion Null", "elmas1"),
    ("Eidolon Rex", "obsidyen"), ("Nova Imperium", "obsidyen"), ("Zenith Ark", "obsidyen"),
]
ABYSS_CARDS_JSON = ROOT / "data" / "abyss_legacy_cards.json"
ABYSS_RARITY_COST = {"common": 1, "rare": 3, "legendary": 4, "eternal": 5}
ABYSS_GENERATIONS = {"fire", "sniper", "tank"}


def _ensure_abyss_legacy_rank_table() -> None:
    with connect("accounts") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS abyss_legacy_rank (
                user_id INTEGER PRIMARY KEY,
                rank_code TEXT NOT NULL DEFAULT 'bronz3',
                rp INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cols = [r[1] for r in db.execute("PRAGMA table_info(abyss_legacy_rank)").fetchall()]
        if "rp" not in cols:
            db.execute("ALTER TABLE abyss_legacy_rank ADD COLUMN rp INTEGER NOT NULL DEFAULT 0")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS abyss_legacy_profile (
                user_id INTEGER PRIMARY KEY,
                total_matches INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                total_xp INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS abyss_legacy_match_queue (
                user_id INTEGER PRIMARY KEY,
                rank_code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'idle',
                match_id INTEGER,
                started_at TEXT NOT NULL DEFAULT '',
                expires_at TEXT NOT NULL DEFAULT '',
                matched_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS abyss_legacy_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_a INTEGER NOT NULL,
                player_b INTEGER,
                is_bot INTEGER NOT NULL DEFAULT 0,
                bot_user_id INTEGER,
                bot_name TEXT NOT NULL DEFAULT '',
                rank_a TEXT NOT NULL,
                rank_b TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        mcols = [r[1] for r in db.execute("PRAGMA table_info(abyss_legacy_matches)").fetchall()]
        if "bot_user_id" not in mcols:
            db.execute("ALTER TABLE abyss_legacy_matches ADD COLUMN bot_user_id INTEGER")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS abyss_legacy_bot_profiles (
                bot_user_id INTEGER PRIMARY KEY,
                bot_name TEXT NOT NULL,
                style TEXT NOT NULL DEFAULT 'balanced',
                favorite_synergy TEXT NOT NULL DEFAULT 'Vanguard',
                commander_pref TEXT NOT NULL DEFAULT 'Kael',
                decision_ms INTEGER NOT NULL DEFAULT 1200,
                error_rate REAL NOT NULL DEFAULT 0.07,
                matches_today INTEGER NOT NULL DEFAULT 0,
                last_day TEXT NOT NULL DEFAULT '',
                last10_json TEXT NOT NULL DEFAULT '[]',
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS abyss_legacy_bot_runtime (
                k TEXT PRIMARY KEY,
                v TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS abyss_legacy_human_bot_recent (
                human_user_id INTEGER NOT NULL,
                bot_user_id INTEGER NOT NULL,
                matched_at TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (human_user_id, bot_user_id)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS abyss_legacy_arena_state (
                match_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL DEFAULT '{}',
                phase TEXT NOT NULL DEFAULT 'prep',
                phase_ends_at TEXT NOT NULL DEFAULT '',
                winner_user_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS abyss_legacy_leaderboard_rewards (
                reward_date TEXT NOT NULL,
                reward_type TEXT NOT NULL,
                rank_code TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (reward_date, reward_type, rank_code, position, user_id)
            )
            """
        )


def _normalize_abyss_legacy_rank(rank_code: str) -> str:
    code = str(rank_code or "").strip().lower()
    return code if code in ABYSS_LEGACY_RANK_LABELS else ABYSS_LEGACY_DEFAULT_RANK


def _abyss_legacy_rank_progression() -> list[dict]:
    out = []
    for idx in range(len(ABYSS_LEGACY_RANK_ORDER) - 1):
        from_code = ABYSS_LEGACY_RANK_ORDER[idx]
        to_code = ABYSS_LEGACY_RANK_ORDER[idx + 1]
        out.append(
            {
                "from_code": from_code,
                "to_code": to_code,
                "from_label": ABYSS_LEGACY_RANK_LABELS[from_code],
                "to_label": ABYSS_LEGACY_RANK_LABELS[to_code],
                "required_rp": (idx + 1) * 200,
            }
        )
    return out


def _abyss_legacy_next_level_xp(level_num: int) -> int:
    lvl = max(1, int(level_num))
    return 100 * (2 ** (lvl - 1))


def _abyss_legacy_level_from_total_xp(total_xp: int) -> tuple[int, int, int]:
    xp = max(0, int(total_xp))
    level_num = 1
    while True:
        need = _abyss_legacy_next_level_xp(level_num)
        if xp < need:
            return level_num, xp, need
        xp -= need
        level_num += 1


def _abyss_rank_thresholds() -> list[int]:
    thresholds = [0]
    total = 0
    for i in range(len(ABYSS_LEGACY_RANK_ORDER) - 1):
        total += (i + 1) * 200
        thresholds.append(total)
    return thresholds


def _abyss_rank_from_rp(rp: int) -> str:
    value = max(0, int(rp))
    thresholds = _abyss_rank_thresholds()
    idx = 0
    for i, need in enumerate(thresholds):
        if value >= need:
            idx = i
    idx = min(idx, len(ABYSS_LEGACY_RANK_ORDER) - 1)
    return ABYSS_LEGACY_RANK_ORDER[idx]


def _bot_user_id(index: int) -> int:
    return 900000 + int(index) + 1


def _seed_bots_if_needed(db) -> None:
    row = db.execute("SELECT COUNT(*) FROM abyss_legacy_bot_profiles").fetchone()
    if int(row[0] or 0) >= ABYSS_LEGACY_BOT_COUNT:
        return
    for idx, (name, rank_code) in enumerate(ABYSS_BOT_SEED[:ABYSS_LEGACY_BOT_COUNT]):
        bot_uid = _bot_user_id(idx)
        style = random.choice(ABYSS_BOT_STYLES)
        synergy = random.choice(ABYSS_BOT_SYNERGIES)
        commander = random.choice(ABYSS_BOT_COMMANDERS)
        decision_ms = random.randint(850, 1900)
        error_rate = round(random.uniform(0.03, 0.14), 3)
        db.execute(
            """
            INSERT OR IGNORE INTO abyss_legacy_bot_profiles
            (bot_user_id, bot_name, style, favorite_synergy, commander_pref, decision_ms, error_rate, last_day, last10_json, wins, losses)
            VALUES (?, ?, ?, ?, ?, ?, ?, '', '[]', 0, 0)
            """,
            (bot_uid, name, style, synergy, commander, decision_ms, error_rate),
        )
        db.execute(
            """
            INSERT OR IGNORE INTO abyss_legacy_rank (user_id, rank_code, rp, created_at, updated_at)
            VALUES (?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (bot_uid, _normalize_abyss_legacy_rank(rank_code)),
        )
        db.execute(
            """
            INSERT OR IGNORE INTO abyss_legacy_profile (user_id, total_matches, wins, losses, total_xp)
            VALUES (?, 0, 0, 0, 0)
            """,
            (bot_uid,),
        )
    # Guarantee exact bot count by trimming extras if seed shrinks.
    extras = db.execute(
        "SELECT bot_user_id FROM abyss_legacy_bot_profiles ORDER BY bot_user_id ASC"
    ).fetchall()
    if len(extras) > ABYSS_LEGACY_BOT_COUNT:
        for rowx in extras[ABYSS_LEGACY_BOT_COUNT:]:
            bid = int(rowx[0])
            db.execute("DELETE FROM abyss_legacy_bot_profiles WHERE bot_user_id = ?", (bid,))
            db.execute("DELETE FROM abyss_legacy_rank WHERE user_id = ?", (bid,))
            db.execute("DELETE FROM abyss_legacy_profile WHERE user_id = ?", (bid,))


def _append_last10(last10_json: str, won: bool) -> str:
    try:
        arr = json.loads(last10_json or "[]")
        if not isinstance(arr, list):
            arr = []
    except Exception:
        arr = []
    arr.append(1 if won else 0)
    arr = arr[-10:]
    return json.dumps(arr, ensure_ascii=True)


def _abyss_legacy_now() -> datetime:
    return datetime.now(timezone.utc)


def _abyss_legacy_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _abyss_legacy_parse_iso(raw: str | None) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _abyss_legacy_match_compatible(rank_a: str, rank_b: str) -> bool:
    a = _normalize_abyss_legacy_rank(rank_a)
    b = _normalize_abyss_legacy_rank(rank_b)
    if a == b:
        return True

    def _major(code: str) -> str:
        return "".join(ch for ch in code if not ch.isdigit())

    am = _major(a)
    bm = _major(b)
    if am == bm:
        return True

    majors = ["bronze", "silver", "gold", "platinum", "diamond", "obsidian"]
    if am in majors and bm in majors:
        ai = majors.index(am)
        bi = majors.index(bm)
        if abs(ai - bi) == 1:
            # Bridge rule: only rank 1 can cross to adjacent major rank.
            return a.endswith("1") or b.endswith("1")

    # Conservative fallback.
    ra = ABYSS_LEGACY_RANK_ORDER.index(a)
    rb = ABYSS_LEGACY_RANK_ORDER.index(b)
    return abs(ra - rb) <= 1


def _abyss_legacy_bot_name_for_rank(rank_code: str) -> str:
    rc = _normalize_abyss_legacy_rank(rank_code)
    if rc.startswith("bronze"):
        pool = ["ArdaK", "MertQ", "KaanR", "BoraX", "EfeN", "DenizT"]
    elif rc.startswith("silver"):
        pool = ["Kerem Vale", "Orin Kade", "Selim Vox", "Alper Rune", "Doran Pike"]
    elif rc.startswith("gold"):
        pool = ["Varden Hale", "Riven Sol", "Kael Draven", "Marek Thorn", "Eldrin Vox"]
    elif rc.startswith("platinum"):
        pool = ["Auron Crest", "Nox Ardent", "Zareth Flux", "Kairo Voss", "Velkan Prime"]
    elif rc.startswith("diamond"):
        pool = ["Ithar Zenith", "Draven Luxor", "Astra Veyl", "Caelum Reign", "Velkan Prime"]
    else:
        pool = ["Obsidian Warden", "Nyx Sovereign", "Aether Monarch", "Void Regent", "Velkan Prime"]
    return random.choice(pool)


def _abyss_legacy_cleanup_queue(db) -> None:
    now_iso = _abyss_legacy_iso(_abyss_legacy_now())
    db.execute(
        """
        DELETE FROM abyss_legacy_match_queue
        WHERE status = 'searching' AND expires_at <= ?
        """,
        (now_iso,),
    )


def _adapt_bot_style(db, bot_uid: int) -> None:
    row = db.execute(
        """
        SELECT style, favorite_synergy, commander_pref, decision_ms, error_rate, last10_json
        FROM abyss_legacy_bot_profiles
        WHERE bot_user_id = ?
        """,
        (int(bot_uid),),
    ).fetchone()
    if not row:
        return
    style, favorite_synergy, commander_pref, decision_ms, error_rate, last10_json = row
    try:
        recent = json.loads(last10_json or "[]")
        recent = [int(x) for x in recent][-10:]
    except Exception:
        recent = []
    if len(recent) < 5:
        return
    win_rate = sum(recent) / max(1, len(recent))
    new_style = str(style or "balanced")
    new_synergy = str(favorite_synergy or "Vanguard")
    new_commander = str(commander_pref or "Kael")
    ms = int(decision_ms or 1200)
    err = float(error_rate or 0.07)
    if win_rate <= 0.3:
        new_style = random.choice(["defensive", "counter", "balanced"])
        new_synergy = random.choice(ABYSS_BOT_SYNERGIES)
        new_commander = random.choice(ABYSS_BOT_COMMANDERS)
        ms = min(2200, ms + random.randint(30, 120))
        err = min(0.22, err + random.uniform(0.005, 0.02))
    elif win_rate >= 0.7:
        new_style = "aggressive"
        ms = max(650, ms - random.randint(40, 130))
        err = max(0.015, err - random.uniform(0.004, 0.015))
    db.execute(
        """
        UPDATE abyss_legacy_bot_profiles
        SET style = ?, favorite_synergy = ?, commander_pref = ?, decision_ms = ?, error_rate = ?, updated_at = CURRENT_TIMESTAMP
        WHERE bot_user_id = ?
        """,
        (new_style, new_synergy, new_commander, int(ms), float(err), int(bot_uid)),
    )


def _simulate_round_decision(style: str, rank_idx: int, profile_row: tuple | None, opponent_style: str) -> float:
    # Features requested by design: synergy count, stars, average HP, skill power, tower risk.
    base = 50.0 + (rank_idx * 2.1)
    active_synergy_count = random.uniform(1.0, 5.0)
    avg_star = random.uniform(1.0, 3.0)
    avg_hp = random.uniform(40.0, 100.0)
    skill_power = random.uniform(25.0, 95.0)
    tower_risk_if_loss = random.uniform(8.0, 38.0)
    style_bonus = {"aggressive": 7.5, "defensive": 2.5, "balanced": 4.0, "counter": 5.0}.get(str(style), 3.0)
    if str(style) == "counter" and str(opponent_style) == "aggressive":
        style_bonus += 4.5
    if tower_risk_if_loss >= 26.0:
        # Defensive pivot when risk is high.
        style_bonus -= 1.5
        avg_hp += 6.0
    score = (
        base
        + (active_synergy_count * 4.8)
        + (avg_star * 8.5)
        + (avg_hp * 0.35)
        + (skill_power * 0.55)
        + style_bonus
    )
    if profile_row:
        decision_ms = int(profile_row[5] or 1200)
        error_rate = float(profile_row[6] or 0.07)
        human_like_noise = random.uniform(-6.0, 6.0) - (error_rate * 20.0) - (decision_ms / 2500.0)
        score += human_like_noise
    return score


def _rp_delta_from_context(won: bool, own_rank_idx: int, opp_rank_idx: int, duration_sec: int) -> int:
    diff = opp_rank_idx - own_rank_idx
    duration_penalty = min(0.45, max(0.0, (float(duration_sec) - 120.0) / 480.0))
    base = 16.0
    if won:
        base += max(-5.0, min(8.0, diff * 2.2))
        base *= (1.0 - duration_penalty)
        return int(max(6.0, min(float(ABYSS_LEGACY_MAX_RP_WIN), base)))
    # Loss logic: long game reduces loss, stronger opponent reduces loss.
    loss_base = 16.0 - (duration_penalty * 6.0) - max(-4.0, min(8.0, diff * 1.5))
    return -int(max(4.0, min(float(abs(ABYSS_LEGACY_MAX_RP_LOSS)), loss_base)))


def _apply_match_result(db, user_id: int, won: bool, delta_rp: int, xp_gain: int) -> None:
    uid = int(user_id)
    r = db.execute("SELECT rp FROM abyss_legacy_rank WHERE user_id = ?", (uid,)).fetchone()
    cur_rp = max(0, int(r[0] if r else 0))
    new_rp = max(0, cur_rp + int(delta_rp))
    new_rank = _abyss_rank_from_rp(new_rp)
    db.execute(
        """
        UPDATE abyss_legacy_rank
        SET rp = ?, rank_code = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (int(new_rp), str(new_rank), uid),
    )
    p = db.execute("SELECT total_matches, wins, losses, total_xp FROM abyss_legacy_profile WHERE user_id = ?", (uid,)).fetchone()
    tm = int(p[0] if p else 0) + 1
    w = int(p[1] if p else 0) + (1 if won else 0)
    l = int(p[2] if p else 0) + (0 if won else 1)
    tx = max(0, int(p[3] if p else 0) + int(xp_gain))
    db.execute(
        """
        INSERT INTO abyss_legacy_profile (user_id, total_matches, wins, losses, total_xp, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            total_matches = excluded.total_matches,
            wins = excluded.wins,
            losses = excluded.losses,
            total_xp = excluded.total_xp,
            updated_at = CURRENT_TIMESTAMP
        """,
        (uid, tm, w, l, tx),
    )


def _simulate_bot_vs_bot_once(db, bot_a_row: tuple, bot_b_row: tuple) -> None:
    a_id, a_name, a_style, *_ = bot_a_row
    b_id, b_name, b_style, *_ = bot_b_row
    a_rank_row = db.execute("SELECT rank_code, rp FROM abyss_legacy_rank WHERE user_id = ?", (int(a_id),)).fetchone()
    b_rank_row = db.execute("SELECT rank_code, rp FROM abyss_legacy_rank WHERE user_id = ?", (int(b_id),)).fetchone()
    if not a_rank_row or not b_rank_row:
        return
    a_rank_code = str(a_rank_row[0] or ABYSS_LEGACY_DEFAULT_RANK)
    b_rank_code = str(b_rank_row[0] or ABYSS_LEGACY_DEFAULT_RANK)
    a_idx = ABYSS_LEGACY_RANK_ORDER.index(_normalize_abyss_legacy_rank(a_rank_code))
    b_idx = ABYSS_LEGACY_RANK_ORDER.index(_normalize_abyss_legacy_rank(b_rank_code))
    duration_sec = random.randint(90, 480)
    a_score = _simulate_round_decision(a_style, a_idx, bot_a_row, b_style)
    b_score = _simulate_round_decision(b_style, b_idx, bot_b_row, a_style)
    a_win = a_score >= b_score
    a_delta = _rp_delta_from_context(a_win, a_idx, b_idx, duration_sec)
    b_delta = _rp_delta_from_context(not a_win, b_idx, a_idx, duration_sec)
    _apply_match_result(db, int(a_id), a_win, a_delta, 60 if a_win else 32)
    _apply_match_result(db, int(b_id), not a_win, b_delta, 60 if not a_win else 32)
    db.execute(
        """
        INSERT INTO abyss_legacy_matches (player_a, player_b, is_bot, bot_user_id, bot_name, rank_a, rank_b, status)
        VALUES (?, ?, 1, ?, ?, ?, ?, 'simulated')
        """,
        (int(a_id), int(b_id), int(b_id), f"{a_name} vs {b_name}", a_rank_code, b_rank_code),
    )
    for bid, won in ((int(a_id), a_win), (int(b_id), not a_win)):
        row = db.execute("SELECT last10_json, wins, losses, matches_today, last_day FROM abyss_legacy_bot_profiles WHERE bot_user_id = ?", (bid,)).fetchone()
        if not row:
            continue
        last10_json, wins, losses, matches_today, last_day = row
        today = datetime.now(timezone.utc).date().isoformat()
        mt = int(matches_today or 0)
        if str(last_day or "") != today:
            mt = 0
        mt += 1
        njson = _append_last10(str(last10_json or "[]"), bool(won))
        db.execute(
            """
            UPDATE abyss_legacy_bot_profiles
            SET last10_json = ?, wins = wins + ?, losses = losses + ?, matches_today = ?, last_day = ?, updated_at = CURRENT_TIMESTAMP
            WHERE bot_user_id = ?
            """,
            (njson, 1 if won else 0, 0 if won else 1, mt, today, bid),
        )
        _adapt_bot_style(db, bid)


def _select_bot_for_human(db, human_user_id: int, human_rank_code: str) -> tuple | None:
    now = _abyss_legacy_now()
    cutoff = _abyss_legacy_iso(now - timedelta(seconds=ABYSS_LEGACY_HUMAN_BOT_REPEAT_COOLDOWN_SEC))
    bots = db.execute(
        """
        SELECT b.bot_user_id, b.bot_name, b.style, b.favorite_synergy, b.commander_pref, b.decision_ms, b.error_rate, b.matches_today, b.last_day, b.last10_json, r.rank_code
        FROM abyss_legacy_bot_profiles b
        JOIN abyss_legacy_rank r ON r.user_id = b.bot_user_id
        ORDER BY RANDOM()
        """
    ).fetchall()
    fallback = None
    for row in bots:
        bot_uid = int(row[0])
        bot_rank = str(row[10] or "")
        if not _abyss_legacy_match_compatible(human_rank_code, bot_rank):
            continue
        rec = db.execute(
            "SELECT matched_at FROM abyss_legacy_human_bot_recent WHERE human_user_id = ? AND bot_user_id = ?",
            (int(human_user_id), bot_uid),
        ).fetchone()
        if rec and str(rec[0] or "") > cutoff:
            if fallback is None:
                fallback = row
            continue
        return row
    return fallback


def _bot_tick_if_due() -> None:
    _ensure_abyss_legacy_rank_table()
    with connect("accounts") as db:
        _seed_bots_if_needed(db)
        now = _abyss_legacy_now()
        last = db.execute("SELECT v FROM abyss_legacy_bot_runtime WHERE k = 'last_tick'").fetchone()
        last_dt = _abyss_legacy_parse_iso(last[0] if last else "")
        if last_dt and (now - last_dt).total_seconds() < ABYSS_LEGACY_BOT_TICK_SEC:
            return
        bots = db.execute(
            """
            SELECT bot_user_id, bot_name, style, favorite_synergy, commander_pref, decision_ms, error_rate, matches_today, last_day, last10_json
            FROM abyss_legacy_bot_profiles
            ORDER BY RANDOM()
            """
        ).fetchall()
        if len(bots) < 2:
            db.execute(
                "INSERT OR REPLACE INTO abyss_legacy_bot_runtime (k, v) VALUES ('last_tick', ?)",
                (_abyss_legacy_iso(now),),
            )
            return
        today = now.date().isoformat()
        eligible = []
        for b in bots:
            mt = int(b[7] or 0)
            last_day = str(b[8] or "")
            if last_day != today:
                mt = 0
                db.execute("UPDATE abyss_legacy_bot_profiles SET matches_today = 0, last_day = ? WHERE bot_user_id = ?", (today, int(b[0])))
            if mt < ABYSS_LEGACY_BOT_DAILY_MATCH_CAP:
                eligible.append(b)
        random.shuffle(eligible)
        matches_to_run = min(max(2, len(eligible) // 4), 6)
        i = 0
        ran = 0
        while i + 1 < len(eligible) and ran < matches_to_run:
            a = eligible[i]
            b = eligible[i + 1]
            _simulate_bot_vs_bot_once(db, a, b)
            i += 2
            ran += 1
        db.execute(
            "INSERT OR REPLACE INTO abyss_legacy_bot_runtime (k, v) VALUES ('last_tick', ?)",
            (_abyss_legacy_iso(now),),
        )


def _load_abyss_cards() -> list[dict]:
    try:
        raw = json.loads(ABYSS_CARDS_JSON.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            cards = []
            for c in raw:
                if not isinstance(c, dict):
                    continue
                rarity = str(c.get("rarity", "common")).strip().lower()
                if rarity not in ABYSS_RARITY_COST:
                    continue
                generation = str(c.get("generation", "")).strip().lower()
                if generation not in ABYSS_GENERATIONS:
                    continue
                skills = c.get("skills") if isinstance(c.get("skills"), list) else []
                if len(skills) < 3:
                    continue
                cards.append(c)
            if cards:
                return cards
    except Exception:
        pass
    return []


def _rarity_weights_for_turn(turn_no: int) -> dict:
    t = max(1, int(turn_no))
    if t <= 2:
        return {"common": 0.60, "rare": 0.40, "legendary": 0.0, "eternal": 0.0}
    if t <= 4:
        return {"common": 0.50, "rare": 0.40, "legendary": 0.10, "eternal": 0.0}
    return {"common": 0.45, "rare": 0.35, "legendary": 0.15, "eternal": 0.05}


def _max_board_slots(turn_no: int) -> int:
    t = max(1, int(turn_no))
    if t >= 7:
        return 5
    if t >= 4:
        return 4
    if t >= 3:
        return 3
    return 2


def _enforce_board_slot_cap(side_state: dict, turn_no: int) -> None:
    board = side_state.get("board") if isinstance(side_state.get("board"), list) else _empty_board()
    while len(board) < 5:
        board.append(None)
    side_state["board"] = board[:5]


def _build_shop(turn_no: int, cards: list[dict], n: int = 5) -> list[dict]:
    by_r = {"common": [], "rare": [], "legendary": [], "eternal": []}
    for c in cards:
        by_r[str(c.get("rarity"))].append(c)
    w = _rarity_weights_for_turn(turn_no)
    rarities = list(w.keys())
    probs = [w[r] for r in rarities]
    shop = []
    for _ in range(int(n)):
        chosen = random.choices(rarities, weights=probs, k=1)[0]
        pool = by_r.get(chosen) or by_r.get("common") or cards
        card = random.choice(pool)
        shop.append(
            {
                "id": str(card["id"]),
                "name": str(card["name"]),
                "rarity": str(card["rarity"]),
                "cost": int(ABYSS_RARITY_COST[str(card["rarity"])]),
                "image": str(card["image"]),
                "generation": str(card["generation"]),
                "hp": int(card["hp"]),
                "atk": int(card["atk"]),
                "def": int(card["def"]),
                "skills": card["skills"][:3],
            }
        )
    return shop


def _new_card_instance(shop_card: dict) -> dict:
    return {
        "inst_id": f"ci_{random.randint(100000, 999999)}_{int(time.time() * 1000)}",
        "id": shop_card["id"],
        "name": shop_card["name"],
        "rarity": shop_card["rarity"],
        "cost": int(shop_card["cost"]),
        "image": shop_card["image"],
        "generation": shop_card["generation"],
        "base_hp": int(shop_card["hp"]),
        "base_atk": int(shop_card["atk"]),
        "base_def": int(shop_card["def"]),
        "hp": int(shop_card["hp"]),
        "atk": int(shop_card["atk"]),
        "def": int(shop_card["def"]),
        "skills": shop_card["skills"],
        "chosen_skill": None,
        "target_index": None,
        "star_level": 1,
    }


def _empty_board() -> list:
    return [None, None, None, None, None]


def _auto_place_random_if_empty(side_state: dict, cards: list[dict], turn_no: int) -> None:
    board = side_state.get("board") if isinstance(side_state.get("board"), list) else _empty_board()
    placed = sum(1 for c in board if c)
    if placed > 0:
        return
    gold = int(side_state.get("gold", 0))
    affordable = [c for c in _build_shop(turn_no, cards, n=8) if int(c["cost"]) <= gold]
    if not affordable:
        return
    pick = random.choice(affordable)
    board[0] = _new_card_instance(pick)
    side_state["gold"] = max(0, gold - int(pick["cost"]))
    side_state["board"] = board


def _leftmost_alive(board: list) -> int | None:
    for i, c in enumerate(board):
        if c and int(c.get("hp", 0)) > 0:
            return i
    return None


def _all_dead(board: list) -> bool:
    return _leftmost_alive(board) is None


def _card_power_value(card: dict) -> float:
    return float(card.get("atk", 0)) * 1.5 + float(card.get("def", 0)) * 1.1 + float(card.get("hp", 0))


def _apply_star_stats(card: dict) -> None:
    star = max(1, int(card.get("star_level", 1)))
    mult = 1.0 + (0.5 * float(star - 1))
    card["hp"] = int(round(float(card.get("base_hp", card.get("hp", 0))) * mult))
    card["atk"] = int(round(float(card.get("base_atk", card.get("atk", 0))) * mult))
    card["def"] = int(round(float(card.get("base_def", card.get("def", 0))) * mult))


def _generation_buff_state(board: list) -> dict:
    counts = {"fire": 0, "sniper": 0, "tank": 0}
    for c in board:
        if c and int(c.get("hp", 0)) > 0:
            g = str(c.get("generation", "")).lower()
            if g in counts:
                counts[g] += 1
    return {"fire": counts["fire"] >= 2, "sniper": counts["sniper"] >= 2, "tank": counts["tank"] >= 2}


def _bot_choose_skill_index(card: dict, opp_board: list, style: str) -> int:
    skills = card.get("skills", [])[:3]
    if not skills:
        return 0
    hp = float(card.get("hp", 0))
    base_hp = float(card.get("base_hp", max(1.0, hp)))
    hp_ratio = hp / max(1.0, base_hp)
    candidates = []
    for idx, s in enumerate(skills):
        st = str(s.get("type", "damage"))
        mul = float(s.get("multiplier", 1.0))
        sc = 0.0
        if st == "damage":
            target_i = _leftmost_alive(opp_board)
            target_def = float(opp_board[target_i].get("def", 0)) if target_i is not None and opp_board[target_i] else 0.0
            sc = (float(card.get("atk", 0)) * mul) * (100.0 / (100.0 + target_def))
            sc *= 1.20 if style in ("aggressive", "counter") else 1.0
        elif st == "defense":
            base = float(s.get("def_bonus", 0)) + float(card.get("def", 0)) * 0.25
            # Defense is favored only when unit is low HP or explicitly defensive.
            risk_boost = 1.45 if hp_ratio <= 0.45 else (1.1 if hp_ratio <= 0.70 else 0.8)
            style_boost = 1.25 if style == "defensive" else 1.0
            sc = base * risk_boost * style_boost
        else:
            sc = float(s.get("atk_bonus", 0)) * 1.2 + float(s.get("shield", 0)) * (1.1 if hp_ratio <= 0.6 else 0.7)
            if style == "aggressive":
                sc *= 1.15
        # Keep bot human-like: small randomness prevents same move spam.
        sc += random.uniform(-2.0, 2.0)
        # Prevent repetitive defensive loops.
        if st == "defense":
            def_streak = int(card.get("defense_streak", 0))
            if def_streak >= 1:
                sc *= 0.55
            if def_streak >= 2:
                sc *= 0.35
        candidates.append((sc, idx))
    candidates.sort(reverse=True)
    if len(candidates) == 1:
        return int(candidates[0][1])
    # 75% best, 25% second-best to diversify.
    if random.random() < 0.75:
        return int(candidates[0][1])
    return int(candidates[1][1])


def _bot_choose_target_index(opp_board: list, style: str) -> int | None:
    alive = []
    for i, c in enumerate(opp_board):
        if c and int(c.get("hp", 0)) > 0:
            alive.append((i, c))
    if not alive:
        return None
    if style == "aggressive":
        # Finisher behavior: focus the weakest target.
        alive.sort(key=lambda x: (int(x[1].get("hp", 0)), int(x[1].get("def", 0)), x[0]))
        return int(alive[0][0])
    if style == "defensive":
        # Remove biggest threat first by ATK.
        alive.sort(key=lambda x: (-int(x[1].get("atk", 0)), x[0]))
        return int(alive[0][0])
    # Balanced defaults to leftmost alive.
    return int(alive[0][0])


def _simulate_battle_rounds(state: dict, bot_profiles: dict) -> dict:
    a_board = copy.deepcopy(state["a"]["board"])
    b_board = copy.deepcopy(state["b"]["board"])
    a_tower = int(state["a"].get("tower_hp", 0))
    b_tower = int(state["b"].get("tower_hp", 0))
    logs = []
    events = []
    elapsed = 0.0
    starter = random.choice(["a", "b"])
    turn_side = starter
    while elapsed < 30.0 and (not _all_dead(a_board)) and (not _all_dead(b_board)):
        interval = 1.5 if elapsed >= 20.0 else 3.0
        attacker_board = a_board if turn_side == "a" else b_board
        defender_board = b_board if turn_side == "a" else a_board
        ai = _leftmost_alive(attacker_board)
        if ai is None:
            turn_side = "b" if turn_side == "a" else "a"
            elapsed += interval
            continue
        attacker = attacker_board[ai]
        chosen_idx = attacker.get("chosen_skill")
        attacker_style = "balanced"
        if state.get(f"{turn_side}_is_bot", False):
            bp = bot_profiles.get(turn_side)
            attacker_style = str(bp.get("style", "balanced")) if bp else "balanced"
            # Bot re-evaluates each action instead of locking one skill forever.
            chosen_idx = _bot_choose_skill_index(attacker, defender_board, attacker_style)
            attacker["chosen_skill"] = int(chosen_idx)
        elif chosen_idx is None:
            chosen_idx = random.randint(0, 2)
            attacker["chosen_skill"] = int(chosen_idx)
        skill = attacker["skills"][int(chosen_idx) % 3]
        stype = str(skill.get("type", "damage"))
        target_i = attacker.get("target_index")
        if state.get(f"{turn_side}_is_bot", False):
            bot_target = _bot_choose_target_index(defender_board, attacker_style)
            if bot_target is not None:
                target_i = bot_target
        if target_i is None or target_i < 0 or target_i > 4 or not defender_board[target_i] or int(defender_board[target_i].get("hp", 0)) <= 0:
            target_i = _leftmost_alive(defender_board)
        if stype == "damage" and target_i is not None:
            atk_buffs = _generation_buff_state(attacker_board)
            def_buffs = _generation_buff_state(defender_board)
            target = defender_board[target_i]
            base_damage = float(attacker.get("atk", 0)) * float(skill.get("multiplier", 1.0))
            effective_def = float(target.get("def", 0)) + (15.0 if def_buffs.get("tank") else 0.0)
            mitigated = base_damage * (100.0 / (100.0 + effective_def))
            trait_mod = float(skill.get("trait_modifier", 1.0))
            counter_mod = float(skill.get("counter_modifier", 1.0))
            gen_mod = 1.02 if atk_buffs.get("fire") else 1.0
            if atk_buffs.get("sniper") and str(target.get("generation", "")).lower() == "sniper":
                gen_mod *= 1.05
            final = max(1, int(round(mitigated * trait_mod * counter_mod * gen_mod)))
            shield = int(target.get("temp_shield", 0))
            if shield > 0:
                absorbed = min(shield, final)
                target["temp_shield"] = shield - absorbed
                final -= absorbed
            if final > 0:
                target["hp"] = int(target.get("hp", 0)) - final
            line = f"{attacker['name']} -> {target['name']} {final} dmg"
            logs.append(line)
            events.append(
                {
                    "t": round(elapsed, 2),
                    "line": line,
                    "a_board": copy.deepcopy(a_board),
                    "b_board": copy.deepcopy(b_board),
                }
            )
            if int(target.get("hp", 0)) <= 0:
                target["hp"] = int(target.get("hp", 0))
        elif stype == "defense":
            attacker["def"] = int(attacker.get("def", 0)) + int(skill.get("def_bonus", 0))
            line = f"{attacker['name']} def +{int(skill.get('def_bonus', 0))}"
            logs.append(line)
            events.append(
                {
                    "t": round(elapsed, 2),
                    "line": line,
                    "a_board": copy.deepcopy(a_board),
                    "b_board": copy.deepcopy(b_board),
                }
            )
        else:
            attacker["atk"] = int(attacker.get("atk", 0)) + int(skill.get("atk_bonus", 0))
            attacker["temp_shield"] = int(attacker.get("temp_shield", 0)) + int(skill.get("shield", 0))
            line = f"{attacker['name']} utility"
            logs.append(line)
            events.append(
                {
                    "t": round(elapsed, 2),
                    "line": line,
                    "a_board": copy.deepcopy(a_board),
                    "b_board": copy.deepcopy(b_board),
                }
            )
        turn_side = "b" if turn_side == "a" else "a"
        elapsed += interval

    a_hp = sum(int(c.get("hp", 0)) for c in a_board if c and int(c.get("hp", 0)) > 0)
    b_hp = sum(int(c.get("hp", 0)) for c in b_board if c and int(c.get("hp", 0)) > 0)
    if a_hp > b_hp:
        winner = "a"
    elif b_hp > a_hp:
        winner = "b"
    else:
        if a_tower > b_tower:
            winner = "a"
        elif b_tower > a_tower:
            winner = "b"
        else:
            seed = (int(state.get("turn", 1)) * 997) + int(state.get("match_id", 0))
            winner = "a" if (seed % 2 == 0) else "b"
    alive_count = sum(1 for c in (a_board if winner == "a" else b_board) if c and int(c.get("hp", 0)) > 0)
    loser = "b" if winner == "a" else "a"
    if loser == "a":
        a_tower = max(0, a_tower - int(alive_count))
    else:
        b_tower = max(0, b_tower - int(alive_count))
    return {
        "winner": winner,
        "alive_damage": int(alive_count),
        "logs": logs[:120],
        "events": events[:120],
        "elapsed_sec": int(min(30, round(elapsed))),
        "a_board": a_board,
        "b_board": b_board,
        "a_tower_hp": int(a_tower),
        "b_tower_hp": int(b_tower),
    }


def _match_row(db, match_id: int):
    return db.execute(
        """
        SELECT id, player_a, player_b, is_bot, bot_user_id, bot_name, rank_a, rank_b, status, created_at
        FROM abyss_legacy_matches
        WHERE id = ?
        """,
        (int(match_id),),
    ).fetchone()


def _arena_default_state(match_row, cards: list[dict]) -> dict:
    _, player_a, player_b, is_bot, bot_user_id, bot_name, rank_a, rank_b, status, _ = match_row
    return {
        "match_id": int(match_row[0]),
        "turn": 1,
        "phase": "prep",
        "a_user_id": int(player_a),
        "b_user_id": int(bot_user_id if int(is_bot or 0) == 1 and int(bot_user_id or 0) > 0 else (player_b or 0)),
        "a_is_bot": False,
        "b_is_bot": bool(int(is_bot or 0) == 1 or (int(player_b or 0) >= 900001)),
        "a_rank_code": str(rank_a or ABYSS_LEGACY_DEFAULT_RANK),
        "b_rank_code": str(rank_b or ABYSS_LEGACY_DEFAULT_RANK),
        "a": {"gold": 2, "tower_hp": 10, "board": _empty_board(), "shop": _build_shop(1, cards), "last_result": None, "win_streak": 0, "loss_streak": 0},
        "b": {"gold": 2, "tower_hp": 10, "board": _empty_board(), "shop": _build_shop(1, cards), "last_result": None, "win_streak": 0, "loss_streak": 0},
        "battle_result": None,
        "match_end": None,
        "winner_user_id": None,
        "bot_name": str(bot_name or ""),
    }


def _save_arena_state(db, match_id: int, state: dict, phase: str, phase_ends_at: str, winner_user_id: int | None = None) -> None:
    db.execute(
        """
        INSERT INTO abyss_legacy_arena_state (match_id, state_json, phase, phase_ends_at, winner_user_id, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(match_id) DO UPDATE SET
            state_json = excluded.state_json,
            phase = excluded.phase,
            phase_ends_at = excluded.phase_ends_at,
            winner_user_id = excluded.winner_user_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (int(match_id), json.dumps(state, ensure_ascii=True), str(phase), str(phase_ends_at), winner_user_id),
    )


def _arena_load_or_create(db, match_id: int, cards: list[dict]):
    row = db.execute(
        "SELECT state_json, phase, phase_ends_at, winner_user_id FROM abyss_legacy_arena_state WHERE match_id = ?",
        (int(match_id),),
    ).fetchone()
    if row:
        try:
            st = json.loads(str(row[0] or "{}"))
            if not isinstance(st, dict):
                st = {}
        except Exception:
            st = {}
        return st, str(row[1] or "prep"), str(row[2] or ""), row[3]
    mr = _match_row(db, match_id)
    if not mr:
        return None, None, None, None
    st = _arena_default_state(mr, cards)
    phase_end = _abyss_legacy_iso(_abyss_legacy_now() + timedelta(seconds=20))
    _save_arena_state(db, match_id, st, "prep", phase_end, None)
    return st, "prep", phase_end, None


def _arena_side_for_user(state: dict, user_id: int) -> str | None:
    uid = int(user_id)
    if int(state.get("a_user_id", 0)) == uid:
        return "a"
    if int(state.get("b_user_id", 0)) == uid:
        return "b"
    return None


def _bot_prepare_side(side_state: dict, opp_state: dict, cards: list[dict], turn_no: int, style: str) -> None:
    max_slots = _max_board_slots(turn_no)
    board = side_state.get("board") if isinstance(side_state.get("board"), list) else _empty_board()
    opp_board = opp_state.get("board") if isinstance(opp_state.get("board"), list) else _empty_board()
    shop = side_state.get("shop") if isinstance(side_state.get("shop"), list) else []
    gold = int(side_state.get("gold", 0))
    own_strength = sum(_card_power_value(c) for c in board if c and int(c.get("hp", 0)) > 0)
    opp_strength = sum(_card_power_value(c) for c in opp_board if c and int(c.get("hp", 0)) > 0)
    own_gen_counts = {"fire": 0, "sniper": 0, "tank": 0}
    for c in board:
        if c and int(c.get("hp", 0)) > 0:
            g = str(c.get("generation", "")).lower()
            if g in own_gen_counts:
                own_gen_counts[g] += 1

    def _buy_score(card: dict) -> float:
        gen = str(card.get("generation", "")).lower()
        rarity = str(card.get("rarity", "common")).lower()
        score = _card_power_value(card) + (int(card.get("cost", 0)) * 1.2)
        # Prioritize completing generation buffs.
        if gen in own_gen_counts:
            if own_gen_counts[gen] == 1:
                score += 55.0
            elif own_gen_counts[gen] >= 2:
                score += 20.0
        if style == "aggressive":
            score += float(card.get("atk", 0)) * 1.2
        elif style == "defensive":
            score += float(card.get("def", 0)) * 1.0 + float(card.get("hp", 0)) * 0.35
        # Under pressure, value high rarity spikes more.
        if opp_strength > own_strength * 1.25:
            score += {"common": 0.0, "rare": 8.0, "legendary": 22.0, "eternal": 36.0}.get(rarity, 0.0)
        return score

    while gold >= 1:
        placed = sum(1 for c in board if c)
        if placed >= max_slots:
            break
        affordable = [c for c in shop if int(c.get("cost", 0)) <= gold]
        if not affordable:
            break
        # Save-gold behavior: when behind, avoid low-impact spending and wait for spike/combo.
        critical_tower = int(side_state.get("tower_hp", 0)) <= 1
        if (not critical_tower) and opp_strength > own_strength * 1.30 and turn_no >= 3:
            desired_bank = min(8, 4 + (turn_no // 2))
            if gold < desired_bank:
                valuable = [c for c in affordable if str(c.get("rarity", "")).lower() in ("legendary", "eternal")]
                combo = [c for c in affordable if own_gen_counts.get(str(c.get("generation", "")).lower(), 0) >= 1]
                if not valuable and not combo:
                    break
        affordable.sort(key=lambda x: (-_buy_score(x), int(x.get("cost", 0))))
        pick = affordable[0]
        target = next((i for i in range(5) if not board[i]), None)
        if target is None:
            break
        inst = _new_card_instance(pick)
        inst["chosen_skill"] = _bot_choose_skill_index(inst, [], style)
        board[target] = inst
        gold -= int(pick["cost"])
        g = str(inst.get("generation", "")).lower()
        if g in own_gen_counts:
            own_gen_counts[g] += 1
        own_strength += _card_power_value(inst)
    temp_state = {"board": board, "gold": gold}
    # If bot saved too hard and ended empty, force a minimum playable board only on early game.
    if turn_no <= 2:
        _auto_place_random_if_empty(temp_state, cards, turn_no)
    board = temp_state["board"]
    gold = int(temp_state["gold"])
    side_state["board"] = board
    side_state["gold"] = max(0, gold)


def _battle_interval(elapsed_sec: float) -> float:
    return 0.5 if float(elapsed_sec) >= 20.0 else 1.0


def _battle_alive_hp(board: list) -> int:
    return sum(int(c.get("hp", 0)) for c in board if c and int(c.get("hp", 0)) > 0)


def _load_battle_bot_profiles(db, state: dict) -> dict:
    bot_profiles = {}
    for side_key in ("a", "b"):
        if state.get(f"{side_key}_is_bot", False):
            bp = db.execute(
                "SELECT style FROM abyss_legacy_bot_profiles WHERE bot_user_id = ?",
                (int(state.get(f"{side_key}_user_id", 0)),),
            ).fetchone()
            bot_profiles[side_key] = {"style": str(bp[0] if bp else "balanced")}
    return bot_profiles


def _battle_apply_single_action(state: dict, bot_profiles: dict) -> None:
    rt = state.get("battle_runtime") if isinstance(state.get("battle_runtime"), dict) else {}
    turn_side = str(rt.get("turn_side", "a"))
    elapsed = float(rt.get("elapsed", 0.0))
    attacker_board = state[turn_side]["board"]
    defender_side = "b" if turn_side == "a" else "a"
    defender_board = state[defender_side]["board"]
    alive_attackers = [i for i, c in enumerate(attacker_board) if c and int(c.get("hp", 0)) > 0]
    if not alive_attackers:
        rt["turn_side"] = defender_side
        rt["elapsed"] = elapsed + _battle_interval(elapsed)
        state["battle_runtime"] = rt
        return
    logs = state.get("battle_result", {}).get("logs")
    if not isinstance(logs, list):
        logs = []
    for ai in alive_attackers:
        if _all_dead(defender_board):
            break
        attacker = attacker_board[ai]
        if not attacker or int(attacker.get("hp", 0)) <= 0:
            continue
        chosen_idx = attacker.get("chosen_skill")
        attacker_style = "balanced"
        if state.get(f"{turn_side}_is_bot", False):
            bp = bot_profiles.get(turn_side)
            attacker_style = str(bp.get("style", "balanced")) if bp else "balanced"
            chosen_idx = _bot_choose_skill_index(attacker, defender_board, attacker_style)
            attacker["chosen_skill"] = int(chosen_idx)
        elif chosen_idx is None:
            chosen_idx = random.randint(0, 2)
            attacker["chosen_skill"] = int(chosen_idx)

        skill = attacker["skills"][int(chosen_idx) % 3]
        stype = str(skill.get("type", "damage"))
        # Prevent getting stuck on utility/defense loops:
        # after 2 non-damage casts, force a damage skill if available.
        non_damage_streak = int(attacker.get("non_damage_streak", 0))
        if stype != "damage" and non_damage_streak >= 2:
            for i, s in enumerate(attacker.get("skills", [])[:3]):
                if str(s.get("type", "damage")) == "damage":
                    chosen_idx = i
                    attacker["chosen_skill"] = int(i)
                    skill = s
                    stype = "damage"
                    break
        target_i = attacker.get("target_index")
        if state.get(f"{turn_side}_is_bot", False):
            bot_target = _bot_choose_target_index(defender_board, attacker_style)
            if bot_target is not None:
                target_i = bot_target
        if target_i is None or target_i < 0 or target_i > 4 or not defender_board[target_i] or int(defender_board[target_i].get("hp", 0)) <= 0:
            target_i = _leftmost_alive(defender_board)

        if stype == "damage" and target_i is not None:
            target = defender_board[target_i]
            base_damage = float(attacker.get("atk", 0)) * float(skill.get("multiplier", 1.0))
            mitigated = base_damage * (100.0 / (100.0 + float(target.get("def", 0))))
            trait_mod = float(skill.get("trait_modifier", 1.0))
            counter_mod = float(skill.get("counter_modifier", 1.0))
            final = max(1, int(round(mitigated * trait_mod * counter_mod)))
            shield = int(target.get("temp_shield", 0))
            if shield > 0:
                absorbed = min(shield, final)
                target["temp_shield"] = shield - absorbed
                final -= absorbed
            if final > 0:
                target["hp"] = int(target.get("hp", 0)) - final
            logs.append(f"{attacker['name']} -> {target['name']} {final} dmg")
            attacker["last_skill_type"] = "damage"
            attacker["defense_streak"] = 0
            attacker["non_damage_streak"] = 0
            if int(target.get("hp", 0)) <= 0:
                defender_board[target_i] = None
        elif stype == "defense":
            attacker["def"] = int(attacker.get("def", 0)) + int(skill.get("def_bonus", 0))
            logs.append(f"{attacker['name']} def +{int(skill.get('def_bonus', 0))}")
            attacker["last_skill_type"] = "defense"
            attacker["defense_streak"] = int(attacker.get("defense_streak", 0)) + 1
            attacker["non_damage_streak"] = int(attacker.get("non_damage_streak", 0)) + 1
        else:
            attacker["atk"] = int(attacker.get("atk", 0)) + int(skill.get("atk_bonus", 0))
            attacker["temp_shield"] = int(attacker.get("temp_shield", 0)) + int(skill.get("shield", 0))
            logs.append(f"{attacker['name']} utility")
            attacker["last_skill_type"] = "utility"
            attacker["defense_streak"] = 0
            attacker["non_damage_streak"] = int(attacker.get("non_damage_streak", 0)) + 1

    if len(logs) > 120:
        logs = logs[-120:]
    state["battle_result"] = state.get("battle_result") or {}
    state["battle_result"]["logs"] = logs
    state["battle_result"]["elapsed_sec"] = int(min(30, elapsed + _battle_interval(elapsed)))

    rt["turn_side"] = defender_side
    rt["elapsed"] = elapsed + _battle_interval(elapsed)
    state["battle_runtime"] = rt


def _battle_resolve_round_outcome(state: dict) -> dict:
    a_board = state["a"]["board"]
    b_board = state["b"]["board"]
    a_hp = _battle_alive_hp(a_board)
    b_hp = _battle_alive_hp(b_board)
    if a_hp > b_hp:
        winner = "a"
    elif b_hp > a_hp:
        winner = "b"
    else:
        a_t = int(state["a"].get("tower_hp", 0))
        b_t = int(state["b"].get("tower_hp", 0))
        if a_t > b_t:
            winner = "a"
        elif b_t > a_t:
            winner = "b"
        else:
            seed = (int(state.get("turn", 1)) * 997) + int(state.get("match_id", 0))
            winner = "a" if (seed % 2 == 0) else "b"
    alive_count = sum(1 for c in (a_board if winner == "a" else b_board) if c and int(c.get("hp", 0)) > 0)
    loser = "b" if winner == "a" else "a"
    state[loser]["tower_hp"] = max(0, int(state[loser].get("tower_hp", 0)) - int(alive_count))
    return {"winner": winner, "alive_damage": int(alive_count)}


def _streak_bonus(streak: int) -> int:
    s = int(streak)
    if s == 2:
        return 2
    if s == 4:
        return 3
    return 0


def _update_round_streaks(state: dict, winner_side: str, loser_side: str) -> None:
    w = state[winner_side]
    l = state[loser_side]
    w["win_streak"] = int(w.get("win_streak", 0)) + 1
    w["loss_streak"] = 0
    l["loss_streak"] = int(l.get("loss_streak", 0)) + 1
    l["win_streak"] = 0


def _reset_side_for_new_round(side_state: dict) -> None:
    board = side_state.get("board") if isinstance(side_state.get("board"), list) else _empty_board()
    for c in board:
        if not c:
            continue
        _apply_star_stats(c)
        c["temp_shield"] = 0
        c["defense_streak"] = 0
        c["non_damage_streak"] = 0


def _arena_tick(db, state: dict, phase: str, phase_ends_at: str) -> tuple[dict, str, str, int | None]:
    now = _abyss_legacy_now()
    end_dt = _abyss_legacy_parse_iso(phase_ends_at) or now
    winner_user_id = None
    cards = _load_abyss_cards()
    if phase == "prep":
        if now < end_dt:
            return state, phase, phase_ends_at, None
        for side_key in ("a", "b"):
            _enforce_board_slot_cap(state[side_key], int(state.get("turn", 1)))
        for side_key in ("a", "b"):
            side = state[side_key]
            for c in side["board"]:
                if c and c.get("chosen_skill") is None:
                    c["chosen_skill"] = random.randint(0, 2)
        # Bot prep actions.
        for side_key, bot_flag in (("a", state.get("a_is_bot", False)), ("b", state.get("b_is_bot", False))):
            if bot_flag:
                bp = db.execute(
                    "SELECT style FROM abyss_legacy_bot_profiles WHERE bot_user_id = ?",
                    (int(state.get(f"{side_key}_user_id", 0)),),
                ).fetchone()
                style = str(bp[0] if bp else "balanced")
                opp_key = "b" if side_key == "a" else "a"
                _bot_prepare_side(state[side_key], state[opp_key], cards, int(state.get("turn", 1)), style)

        a_count = sum(1 for c in state["a"]["board"] if c and int(c.get("hp", 0)) > 0)
        b_count = sum(1 for c in state["b"]["board"] if c and int(c.get("hp", 0)) > 0)
        if (a_count == 0 and b_count > 0) or (b_count == 0 and a_count > 0):
            winner_side = "a" if a_count > 0 else "b"
            loser_side = "b" if winner_side == "a" else "a"
            alive_damage = sum(1 for c in state[winner_side]["board"] if c and int(c.get("hp", 0)) > 0)
            state[loser_side]["tower_hp"] = max(0, int(state[loser_side].get("tower_hp", 0)) - int(alive_damage))
            state["battle_result"] = {
                "winner": winner_side,
                "alive_damage": int(alive_damage),
                "logs": ["Kart koymayan taraf otomatik maglup oldu."],
                "elapsed_sec": 0,
            }
            state[winner_side]["last_result"] = "win"
            state[loser_side]["last_result"] = "loss"
            _update_round_streaks(state, winner_side, loser_side)
            if int(state[loser_side]["tower_hp"]) <= 0:
                winner_user_id = int(state.get(f"{winner_side}_user_id", 0))
                phase = "finished"
                phase_ends_at = ""
                a_uid = int(state.get("a_user_id", 0))
                b_uid = int(state.get("b_user_id", 0))
                a_idx = ABYSS_LEGACY_RANK_ORDER.index(_normalize_abyss_legacy_rank(str(state.get("a_rank_code", ABYSS_LEGACY_DEFAULT_RANK))))
                b_idx = ABYSS_LEGACY_RANK_ORDER.index(_normalize_abyss_legacy_rank(str(state.get("b_rank_code", ABYSS_LEGACY_DEFAULT_RANK))))
                dur = 30
                a_win = (winner_side == "a")
                a_delta = _rp_delta_from_context(a_win, a_idx, b_idx, dur)
                b_delta = _rp_delta_from_context((winner_side == "b"), b_idx, a_idx, dur)
                _apply_match_result(db, a_uid, a_win, a_delta, 120 if a_win else 70)
                _apply_match_result(db, b_uid, (winner_side == "b"), b_delta, 120 if winner_side == "b" else 70)
                state["match_end"] = {
                    "winner_side": winner_side,
                    "a_rp_delta": int(a_delta),
                    "b_rp_delta": int(b_delta),
                }
                return state, phase, phase_ends_at, winner_user_id
            state["turn"] = int(state.get("turn", 1)) + 1
            for side_key in ("a", "b"):
                side = state[side_key]
                gain = 1
                if side_key == winner_side:
                    gain += _streak_bonus(int(side.get("win_streak", 0)))
                else:
                    gain += _streak_bonus(int(side.get("loss_streak", 0)))
                side["gold"] = int(side.get("gold", 0)) + gain
                side["shop"] = _build_shop(int(state["turn"]), cards)
                board = side.get("board") if isinstance(side.get("board"), list) else _empty_board()
                while len(board) < 5:
                    board.append(None)
                side["board"] = board[:5]
                _reset_side_for_new_round(side)
            phase = "prep"
            phase_ends_at = _abyss_legacy_iso(now + timedelta(seconds=15))
            return state, phase, phase_ends_at, None

        state["battle_result"] = {
            "winner": None,
            "alive_damage": 0,
            "logs": [],
            "elapsed_sec": 0,
        }
        state["match_end"] = None
        state["battle_runtime"] = {"elapsed": 0.0, "turn_side": random.choice(["a", "b"])}
        phase = "battle"
        phase_ends_at = _abyss_legacy_iso(now + timedelta(seconds=30))
        return state, phase, phase_ends_at, None

    if phase == "battle":
        bot_profiles = _load_battle_bot_profiles(db, state)
        total = 30.0
        if now < end_dt:
            remaining = max(0.0, (end_dt - now).total_seconds())
            target_elapsed = max(0.0, min(total, total - remaining))
        else:
            target_elapsed = total

        rt = state.get("battle_runtime") if isinstance(state.get("battle_runtime"), dict) else {"elapsed": 0.0, "turn_side": random.choice(["a", "b"])}
        state["battle_runtime"] = rt
        while float(rt.get("elapsed", 0.0)) < target_elapsed and not _all_dead(state["a"]["board"]) and not _all_dead(state["b"]["board"]):
            _battle_apply_single_action(state, bot_profiles)
            rt = state.get("battle_runtime") if isinstance(state.get("battle_runtime"), dict) else rt

        elapsed_now = min(total, float(state.get("battle_runtime", {}).get("elapsed", 0.0)))
        state["battle_result"] = state.get("battle_result") or {}
        state["battle_result"]["elapsed_sec"] = int(elapsed_now)

        round_over = _all_dead(state["a"]["board"]) or _all_dead(state["b"]["board"]) or elapsed_now >= total - 1e-6
        if not round_over:
            return state, phase, phase_ends_at, None

        summary = _battle_resolve_round_outcome(state)
        state["battle_result"]["winner"] = summary["winner"]
        state["battle_result"]["alive_damage"] = int(summary["alive_damage"])
        winner_side = summary["winner"]
        loser_side = "b" if winner_side == "a" else "a"
        state[winner_side]["last_result"] = "win"
        state[loser_side]["last_result"] = "loss"
        _update_round_streaks(state, winner_side, loser_side)
        state.pop("battle_runtime", None)
        if int(state[loser_side]["tower_hp"]) <= 0:
            winner_user_id = int(state.get(f"{winner_side}_user_id", 0))
            phase = "finished"
            phase_ends_at = ""
            # RP/XP settle
            a_uid = int(state.get("a_user_id", 0))
            b_uid = int(state.get("b_user_id", 0))
            a_idx = ABYSS_LEGACY_RANK_ORDER.index(_normalize_abyss_legacy_rank(str(state.get("a_rank_code", ABYSS_LEGACY_DEFAULT_RANK))))
            b_idx = ABYSS_LEGACY_RANK_ORDER.index(_normalize_abyss_legacy_rank(str(state.get("b_rank_code", ABYSS_LEGACY_DEFAULT_RANK))))
            dur = max(30, int(elapsed_now))
            a_win = (winner_side == "a")
            a_delta = _rp_delta_from_context(a_win, a_idx, b_idx, dur)
            b_delta = _rp_delta_from_context((winner_side == "b"), b_idx, a_idx, dur)
            _apply_match_result(db, a_uid, a_win, a_delta, 120 if a_win else 70)
            _apply_match_result(db, b_uid, (winner_side == "b"), b_delta, 120 if winner_side == "b" else 70)
            state["match_end"] = {
                "winner_side": winner_side,
                "a_rp_delta": int(a_delta),
                "b_rp_delta": int(b_delta),
            }
            return state, phase, phase_ends_at, winner_user_id
        state["turn"] = int(state.get("turn", 1)) + 1
        for side_key in ("a", "b"):
            side = state[side_key]
            gain = 1
            if side_key == winner_side:
                gain += _streak_bonus(int(side.get("win_streak", 0)))
            else:
                gain += _streak_bonus(int(side.get("loss_streak", 0)))
            side["gold"] = int(side.get("gold", 0)) + gain
            side["shop"] = _build_shop(int(state["turn"]), cards)
            board = side.get("board") if isinstance(side.get("board"), list) else _empty_board()
            while len(board) < 5:
                board.append(None)
            side["board"] = board[:5]
            _reset_side_for_new_round(side)
            _enforce_board_slot_cap(side, int(state["turn"]))
        phase = "prep"
        prep_sec = 15
        phase_ends_at = _abyss_legacy_iso(now + timedelta(seconds=prep_sec))
        return state, phase, phase_ends_at, None

    return state, phase, phase_ends_at, winner_user_id


def _abyss_legacy_queue_state(user_id: int) -> dict:
    _ensure_abyss_legacy_rank_table()
    uid = int(user_id)
    now = _abyss_legacy_now()
    with connect("accounts") as db:
        _abyss_legacy_cleanup_queue(db)
        row = db.execute(
            """
            SELECT q.status, q.rank_code, q.match_id, q.started_at, q.expires_at, q.matched_at
            FROM abyss_legacy_match_queue q
            WHERE q.user_id = ?
            """,
            (uid,),
        ).fetchone()
        if not row:
            return {"state": "idle"}

        status, rank_code, match_id, started_at, expires_at, matched_at = row
        status = str(status or "idle")
        if status == "searching":
            start_dt = _abyss_legacy_parse_iso(started_at) or now
            exp_dt = _abyss_legacy_parse_iso(expires_at) or (start_dt + timedelta(seconds=ABYSS_LEGACY_MATCH_TIMEOUT_SEC))
            elapsed = max(0, int((now - start_dt).total_seconds()))
            remaining = max(0, int((exp_dt - now).total_seconds()))
            return {
                "state": "searching",
                "rank_code": str(rank_code or ""),
                "elapsed_sec": elapsed,
                "remaining_sec": remaining,
                "bot_fallback_sec": ABYSS_LEGACY_BOT_FALLBACK_SEC,
            }

        if status == "matched" and match_id:
            m = db.execute(
                """
                SELECT id, player_a, player_b, is_bot, bot_user_id, bot_name, rank_a, rank_b, created_at
                FROM abyss_legacy_matches
                WHERE id = ?
                """,
                (int(match_id),),
            ).fetchone()
            if not m:
                return {"state": "idle"}
            _, player_a, player_b, is_bot, bot_user_id, bot_name, rank_a, rank_b, created_at = m
            if int(is_bot or 0) == 1:
                return {
                    "state": "matched",
                    "match_id": int(match_id),
                    "is_bot": True,
                    "bot_user_id": int(bot_user_id or 0),
                    "opponent_name": str(bot_name or "Abyss Bot"),
                    "opponent_rank": ABYSS_LEGACY_RANK_LABELS.get(str(rank_b or ""), str(rank_b or "")),
                    "created_at": str(created_at or ""),
                }
            opp_id = int(player_b if int(player_a) == uid else player_a)
            acc = accountbyid(opp_id)
            opp_name = acc[1] if acc else f"Oyuncu {opp_id}"
            opp_rank_code = str(rank_b if int(player_a) == uid else rank_a)
            return {
                "state": "matched",
                "match_id": int(match_id),
                "is_bot": False,
                "opponent_id": opp_id,
                "opponent_name": opp_name,
                "opponent_rank": ABYSS_LEGACY_RANK_LABELS.get(opp_rank_code, opp_rank_code),
                "created_at": str(created_at or ""),
            }

        if status in {"timeout", "cancelled"}:
            return {"state": status}
        return {"state": "idle"}


def abyss_legacy_rank_state(user_id: int) -> dict:
    _ensure_abyss_legacy_rank_table()
    with connect("accounts") as db:
        db.execute(
            "INSERT OR IGNORE INTO abyss_legacy_rank (user_id, rank_code, rp) VALUES (?, ?, 0)",
            (int(user_id), ABYSS_LEGACY_DEFAULT_RANK),
        )
        row = db.execute(
            "SELECT rank_code, rp FROM abyss_legacy_rank WHERE user_id = ?",
            (int(user_id),),
        ).fetchone()
        rank_code = _normalize_abyss_legacy_rank(row[0] if row else ABYSS_LEGACY_DEFAULT_RANK)
        rp = max(0, int(row[1] if row else 0))
        if not row or str(row[0]).strip().lower() != rank_code or int(row[1] if row else 0) != rp:
            db.execute(
                "UPDATE abyss_legacy_rank SET rank_code = ?, rp = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (rank_code, int(rp), int(user_id)),
            )
    rank_index = ABYSS_LEGACY_RANK_ORDER.index(rank_code)
    return {
        "abyss_rank_code": rank_code,
        "abyss_rank_label": ABYSS_LEGACY_RANK_LABELS[rank_code],
        "abyss_rp": rp,
        "abyss_rank_index": rank_index,
        "abyss_rank_total": len(ABYSS_LEGACY_RANK_ORDER),
        "abyss_rank_is_max": rank_code == "obsidyen",
        "abyss_rank_list": ABYSS_LEGACY_RANK_ORDER,
        "abyss_rank_labels": ABYSS_LEGACY_RANK_LABELS,
        "abyss_rank_progression": _abyss_legacy_rank_progression(),
        "abyss_max_rp_win": ABYSS_LEGACY_MAX_RP_WIN,
        "abyss_max_rp_loss": ABYSS_LEGACY_MAX_RP_LOSS,
    }


def abyss_legacy_profile_state(user_id: int, rank_code: str, rank_label: str) -> dict:
    _ensure_abyss_legacy_rank_table()
    uid = int(user_id)
    with connect("accounts") as db:
        db.execute(
            """
            INSERT OR IGNORE INTO abyss_legacy_profile (user_id, total_matches, wins, losses, total_xp)
            VALUES (?, 0, 0, 0, 0)
            """,
            (uid,),
        )
        row = db.execute(
            """
            SELECT total_matches, wins, losses, total_xp
            FROM abyss_legacy_profile
            WHERE user_id = ?
            """,
            (uid,),
        ).fetchone()
        total_matches = max(0, int(row[0] if row else 0))
        wins = max(0, int(row[1] if row else 0))
        losses = max(0, int(row[2] if row else 0))
        total_xp = max(0, int(row[3] if row else 0))

        rank_rows = db.execute(
            """
            SELECT r.user_id, r.rank_code, r.rp, COALESCE(p.total_xp, 0) AS total_xp
            FROM abyss_legacy_rank r
            LEFT JOIN abyss_legacy_profile p ON p.user_id = r.user_id
            """
        ).fetchall()

    level_num, current_level_xp, next_level_xp = _abyss_legacy_level_from_total_xp(total_xp)
    xp_progress_percent = int((current_level_xp / max(1, next_level_xp)) * 100)
    win_rate = (float(wins) / float(total_matches) * 100.0) if total_matches > 0 else 0.0

    sorted_global = sorted(
        rank_rows,
        key=lambda r: (-int(r[2] or 0), -int(r[3] or 0), int(r[0])),
    )
    global_position = 1
    for i, r in enumerate(sorted_global, start=1):
        if int(r[0]) == uid:
            global_position = i
            break

    same_rank = [r for r in sorted_global if str(r[1] or "") == str(rank_code)]
    rank_group_position = 1
    for i, r in enumerate(same_rank, start=1):
        if int(r[0]) == uid:
            rank_group_position = i
            break

    return {
        "abyss_total_matches": total_matches,
        "abyss_wins": wins,
        "abyss_losses": losses,
        "abyss_win_rate": round(win_rate, 2),
        "abyss_level_num": level_num,
        "abyss_total_xp": total_xp,
        "abyss_current_level_xp": current_level_xp,
        "abyss_next_level_xp": next_level_xp,
        "abyss_xp_progress_percent": xp_progress_percent,
        "abyss_global_position": global_position,
        "abyss_global_rank_label": rank_label,
        "abyss_rank_group_position": rank_group_position,
    }


def _abyss_name_for_user(db, user_id: int) -> str:
    uid = int(user_id)
    if uid >= 900001:
        b = db.execute("SELECT bot_name FROM abyss_legacy_bot_profiles WHERE bot_user_id = ?", (uid,)).fetchone()
        if b and b[0]:
            return str(b[0])
    acc = accountbyid(uid)
    if acc and acc[1]:
        return str(acc[1])
    return f"Oyuncu {uid}"


def _abyss_build_leaderboard_rows(db) -> list[dict]:
    rows = db.execute(
        """
        SELECT r.user_id, r.rank_code, r.rp, COALESCE(p.total_xp, 0) AS total_xp
        FROM abyss_legacy_rank r
        LEFT JOIN abyss_legacy_profile p ON p.user_id = r.user_id
        """
    ).fetchall()
    ordered = sorted(rows, key=lambda r: (-int(r[2] or 0), -int(r[3] or 0), int(r[0])))
    out = []
    for i, r in enumerate(ordered, start=1):
        uid = int(r[0])
        code = _normalize_abyss_legacy_rank(str(r[1] or ABYSS_LEGACY_DEFAULT_RANK))
        out.append(
            {
                "position": i,
                "user_id": uid,
                "username": _abyss_name_for_user(db, uid),
                "rank_code": code,
                "rank_label": ABYSS_LEGACY_RANK_LABELS.get(code, code),
                "rp": int(r[2] or 0),
                "is_bot": uid >= 900001,
            }
        )
    return out


def _abyss_distribute_leaderboard_rewards(db, ordered: list[dict]) -> None:
    today = _abyss_legacy_now().date().isoformat()
    # Global rewards: economy money.
    for idx, amount in enumerate(ABYSS_GLOBAL_REWARDS, start=1):
        if idx > len(ordered):
            break
        row = ordered[idx - 1]
        uid = int(row["user_id"])
        exists = db.execute(
            """
            SELECT 1 FROM abyss_legacy_leaderboard_rewards
            WHERE reward_date = ? AND reward_type = 'global_money' AND rank_code = '' AND position = ? AND user_id = ?
            """,
            (today, idx, uid),
        ).fetchone()
        if exists:
            continue
        initialize_user_economy(uid)
        applyledger(uid, int(amount), "abyss_global_rank_reward", f"Abyss global rank #{idx} reward", f"abyss:global:{today}:{idx}:{uid}")
        db.execute(
            """
            INSERT OR IGNORE INTO abyss_legacy_leaderboard_rewards
            (reward_date, reward_type, rank_code, position, user_id, amount)
            VALUES (?, 'global_money', '', ?, ?, ?)
            """,
            (today, idx, uid, int(amount)),
        )

    # Rank-group rewards: economy gold rewards for top 2 in each rank.
    by_rank: dict[str, list[dict]] = {}
    for r in ordered:
        by_rank.setdefault(str(r["rank_code"]), []).append(r)
    for rank_code, members in by_rank.items():
        for idx, amount in enumerate(ABYSS_RANK_REWARDS, start=1):
            if idx > len(members):
                break
            row = members[idx - 1]
            uid = int(row["user_id"])
            exists = db.execute(
                """
                SELECT 1 FROM abyss_legacy_leaderboard_rewards
                WHERE reward_date = ? AND reward_type = 'rank_gold' AND rank_code = ? AND position = ? AND user_id = ?
                """,
                (today, rank_code, idx, uid),
            ).fetchone()
            if exists:
                continue
            initialize_user_economy(uid)
            applyledger(uid, int(amount), "abyss_rank_group_reward", f"Abyss {rank_code} rank #{idx} reward", f"abyss:rank:{today}:{rank_code}:{idx}:{uid}")
            db.execute(
                """
                INSERT OR IGNORE INTO abyss_legacy_leaderboard_rewards
                (reward_date, reward_type, rank_code, position, user_id, amount)
                VALUES (?, 'rank_gold', ?, ?, ?, ?)
                """,
                (today, rank_code, idx, uid, int(amount)),
            )


def _abyss_next_reward_at() -> datetime:
    now = _abyss_legacy_now()
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt


def _abyss_leaderboard_payload(user_id: int) -> dict:
    _ensure_abyss_legacy_rank_table()
    uid = int(user_id)
    with connect("accounts") as db:
        ordered = _abyss_build_leaderboard_rows(db)
        _abyss_distribute_leaderboard_rewards(db, ordered)
        rank_row = db.execute("SELECT rank_code FROM abyss_legacy_rank WHERE user_id = ?", (uid,)).fetchone()
        my_rank = _normalize_abyss_legacy_rank(str(rank_row[0] if rank_row else ABYSS_LEGACY_DEFAULT_RANK))
        rank_rows = [r for r in ordered if str(r["rank_code"]) == my_rank]
    nxt = _abyss_next_reward_at()
    now = _abyss_legacy_now()
    countdown_sec = max(0, int((nxt - now).total_seconds()))
    return {
        "global_rank_label": ABYSS_LEGACY_RANK_LABELS.get(my_rank, my_rank),
        "global_rewards": [
            {"position": 1, "reward_money": 10000},
            {"position": 2, "reward_money": 5000},
            {"position": 3, "reward_money": 1500},
        ],
        "rank_rewards": [
            {"position": 1, "reward_gold": 2000},
            {"position": 2, "reward_gold": 1000},
        ],
        "global_rows": ordered[:100],
        "rank_rows": rank_rows[:100],
        "reward_next_at": _abyss_legacy_iso(nxt),
        "reward_countdown_sec": countdown_sec,
    }



@bp.route("/abyss-legacy")
def abysslegacy():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    _bot_tick_if_due()
    content = texts(current)
    ctx = navcontext(content, current)
    ctx.update(abyss_legacy_rank_state(account[0]))
    ctx.update(abyss_legacy_profile_state(account[0], ctx["abyss_rank_code"], ctx["abyss_rank_label"]))
    ctx["arena_match_id"] = int(request.args.get("match_id", "0") or 0)
    return render_template(viewfile("abysslegacy.html"), **ctx)


@bp.route("/abyss-legacy/arena/<int:match_id>")
def abysslegacyarena(match_id: int):
    return redirect(url_for("abysslegacy", match_id=match_id))


@bp.route("/api/abyss-legacy/leaderboard")
def abysslegacyleaderboard():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    _bot_tick_if_due()
    payload = _abyss_leaderboard_payload(int(me[0]))
    return {"ok": True, **payload}


@bp.route("/api/abyss-legacy/matchmaking/start", methods=["POST"])
def abysslegacymatchstart():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    uid = int(me[0])
    _bot_tick_if_due()
    rank_state = abyss_legacy_rank_state(uid)
    rank_code = str(rank_state["abyss_rank_code"])
    now = _abyss_legacy_now()
    start_iso = _abyss_legacy_iso(now)
    expires_iso = _abyss_legacy_iso(now + timedelta(seconds=ABYSS_LEGACY_MATCH_TIMEOUT_SEC))

    with connect("accounts") as db:
        _abyss_legacy_cleanup_queue(db)
        db.execute(
            """
            INSERT INTO abyss_legacy_match_queue (user_id, rank_code, status, match_id, started_at, expires_at, matched_at, updated_at)
            VALUES (?, ?, 'searching', NULL, ?, ?, '', CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                rank_code = excluded.rank_code,
                status = 'searching',
                match_id = NULL,
                started_at = excluded.started_at,
                expires_at = excluded.expires_at,
                matched_at = '',
                updated_at = CURRENT_TIMESTAMP
            """,
            (uid, rank_code, start_iso, expires_iso),
        )

        opp = db.execute(
            """
            SELECT user_id, rank_code
            FROM abyss_legacy_match_queue
            WHERE status = 'searching'
              AND user_id != ?
            ORDER BY started_at ASC
            """,
            (uid,),
        ).fetchall()

        target = None
        for opp_uid, opp_rank in opp:
            if _abyss_legacy_match_compatible(rank_code, str(opp_rank or "")):
                target = (int(opp_uid), str(opp_rank or ""))
                break

        if target:
            opp_uid, opp_rank_code = target
            db.execute(
                """
                INSERT INTO abyss_legacy_matches (player_a, player_b, is_bot, bot_user_id, bot_name, rank_a, rank_b, status)
                VALUES (?, ?, 0, NULL, '', ?, ?, 'ready')
                """,
                (uid, opp_uid, rank_code, opp_rank_code),
            )
            match_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
            match_iso = _abyss_legacy_iso(now)
            db.execute(
                """
                UPDATE abyss_legacy_match_queue
                SET status = 'matched', match_id = ?, matched_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id IN (?, ?)
                """,
                (match_id, match_iso, uid, opp_uid),
            )

    state = _abyss_legacy_queue_state(uid)
    return {"ok": True, **state}


@bp.route("/api/abyss-legacy/matchmaking/cancel", methods=["POST"])
def abysslegacymatchcancel():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    uid = int(me[0])
    with connect("accounts") as db:
        db.execute(
            """
            UPDATE abyss_legacy_match_queue
            SET status = 'cancelled', match_id = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND status = 'searching'
            """,
            (uid,),
        )
    return {"ok": True, **_abyss_legacy_queue_state(uid)}


@bp.route("/api/abyss-legacy/matchmaking/status")
def abysslegacymatchstatus():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    uid = int(me[0])
    _bot_tick_if_due()
    rank_state = abyss_legacy_rank_state(uid)
    rank_code = str(rank_state["abyss_rank_code"])
    now = _abyss_legacy_now()

    with connect("accounts") as db:
        _abyss_legacy_cleanup_queue(db)
        row = db.execute(
            """
            SELECT status, started_at
            FROM abyss_legacy_match_queue
            WHERE user_id = ?
            """,
            (uid,),
        ).fetchone()
        if row and str(row[0] or "") == "searching":
            started_dt = _abyss_legacy_parse_iso(row[1]) or now
            elapsed = max(0, int((now - started_dt).total_seconds()))
            if elapsed >= ABYSS_LEGACY_BOT_FALLBACK_SEC:
                bot = _select_bot_for_human(db, uid, rank_code)
                if bot:
                    bot_uid = int(bot[0])
                    bot_name = str(bot[1] or _abyss_legacy_bot_name_for_rank(rank_code))
                    bot_rank = str(bot[10] or rank_code)
                else:
                    bot_uid = 0
                    bot_name = _abyss_legacy_bot_name_for_rank(rank_code)
                    bot_rank = rank_code
                db.execute(
                    """
                    INSERT INTO abyss_legacy_matches (player_a, player_b, is_bot, bot_user_id, bot_name, rank_a, rank_b, status)
                    VALUES (?, NULL, 1, ?, ?, ?, ?, 'ready')
                    """,
                    (uid, bot_uid if bot_uid > 0 else None, bot_name, rank_code, bot_rank),
                )
                match_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
                db.execute(
                    """
                    UPDATE abyss_legacy_match_queue
                    SET status = 'matched', match_id = ?, matched_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND status = 'searching'
                    """,
                    (match_id, _abyss_legacy_iso(now), uid),
                )
                if bot_uid > 0:
                    db.execute(
                        """
                        INSERT INTO abyss_legacy_human_bot_recent (human_user_id, bot_user_id, matched_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(human_user_id, bot_user_id) DO UPDATE SET matched_at = excluded.matched_at
                        """,
                        (uid, bot_uid, _abyss_legacy_iso(now)),
                    )

    return {"ok": True, **_abyss_legacy_queue_state(uid)}


def _arena_view_for_side(state: dict, side: str, phase: str, phase_ends_at: str, winner_user_id):
    you = state[side]
    opp_side = "b" if side == "a" else "a"
    opp = state[opp_side]
    end = state.get("match_end") if isinstance(state.get("match_end"), dict) else None
    end_view = None
    if end:
        my_delta = int(end.get("a_rp_delta", 0)) if side == "a" else int(end.get("b_rp_delta", 0))
        end_view = {
            "winner_side": str(end.get("winner_side", "")),
            "rp_delta": my_delta,
        }
    return {
        "ok": True,
        "match_id": int(state.get("match_id", 0)),
        "turn": int(state.get("turn", 1)),
        "phase": str(phase),
        "phase_ends_at": str(phase_ends_at or ""),
        "winner_user_id": winner_user_id,
        "you": you,
        "opponent": {
            "gold": int(opp.get("gold", 0)),
            "tower_hp": int(opp.get("tower_hp", 0)),
            "board": opp.get("board", _empty_board()),
            "last_result": opp.get("last_result"),
        },
        "battle_result": state.get("battle_result"),
        "match_end": end_view,
        "max_slots": _max_board_slots(int(state.get("turn", 1))),
    }


@bp.route("/api/abyss-legacy/arena/start", methods=["POST"])
def abysslegacyarenastart():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = request.get_json(silent=True) or {}
    match_id = int(payload.get("match_id", 0) or 0)
    if match_id <= 0:
        return {"ok": False, "error": "missing_match_id"}, 400
    _bot_tick_if_due()
    cards = _load_abyss_cards()
    if not cards:
        return {"ok": False, "error": "cards_not_loaded"}, 500
    with connect("accounts") as db:
        state, phase, phase_ends_at, winner = _arena_load_or_create(db, match_id, cards)
        if not state:
            return {"ok": False, "error": "match_not_found"}, 404
        side = _arena_side_for_user(state, int(me[0]))
        if not side:
            return {"ok": False, "error": "forbidden"}, 403
        state, phase, phase_ends_at, winner = _arena_tick(db, state, phase, phase_ends_at)
        _save_arena_state(db, match_id, state, phase, phase_ends_at, winner)
    return _arena_view_for_side(state, side, phase, phase_ends_at, winner)


@bp.route("/api/abyss-legacy/arena/state")
def abysslegacyarenastate():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    match_id = int(request.args.get("match_id", "0") or 0)
    if match_id <= 0:
        return {"ok": False, "error": "missing_match_id"}, 400
    _bot_tick_if_due()
    cards = _load_abyss_cards()
    with connect("accounts") as db:
        state, phase, phase_ends_at, winner = _arena_load_or_create(db, match_id, cards)
        if not state:
            return {"ok": False, "error": "match_not_found"}, 404
        side = _arena_side_for_user(state, int(me[0]))
        if not side:
            return {"ok": False, "error": "forbidden"}, 403
        state, phase, phase_ends_at, winner = _arena_tick(db, state, phase, phase_ends_at)
        _save_arena_state(db, match_id, state, phase, phase_ends_at, winner)
    return _arena_view_for_side(state, side, phase, phase_ends_at, winner)


@bp.route("/api/abyss-legacy/arena/buy", methods=["POST"])
def abysslegacyarenabuy():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = request.get_json(silent=True) or {}
    match_id = int(payload.get("match_id", 0) or 0)
    shop_index = int(payload.get("shop_index", -1))
    board_index = int(payload.get("board_index", -1))
    if match_id <= 0 or shop_index < 0 or board_index < 0 or board_index > 4:
        return {"ok": False, "error": "invalid_payload"}, 400
    cards = _load_abyss_cards()
    with connect("accounts") as db:
        state, phase, phase_ends_at, winner = _arena_load_or_create(db, match_id, cards)
        if not state:
            return {"ok": False, "error": "match_not_found"}, 404
        side = _arena_side_for_user(state, int(me[0]))
        if not side:
            return {"ok": False, "error": "forbidden"}, 403
        state, phase, phase_ends_at, winner = _arena_tick(db, state, phase, phase_ends_at)
        if phase not in ("prep", "battle"):
            return {"ok": False, "error": "phase_locked", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        you = state[side]
        board = you["board"]
        shop = you["shop"]
        max_slots = _max_board_slots(int(state.get("turn", 1)))
        placed = sum(1 for c in board if c and int(c.get("hp", 0)) > 0)
        if placed >= max_slots:
            return {"ok": False, "error": "slot_cap_reached", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        if board[board_index] and int(board[board_index].get("hp", 0)) > 0:
            return {"ok": False, "error": "target_slot_occupied", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        if shop_index >= len(shop):
            return {"ok": False, "error": "shop_index_invalid", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        pick = shop[shop_index]
        cost = int(pick.get("cost", 0))
        if int(you.get("gold", 0)) < cost:
            return {"ok": False, "error": "insufficient_gold", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        you["gold"] = int(you.get("gold", 0)) - cost
        board[board_index] = _new_card_instance(pick)
        shop.pop(shop_index)
        _save_arena_state(db, match_id, state, phase, phase_ends_at, winner)
    return _arena_view_for_side(state, side, phase, phase_ends_at, winner)


@bp.route("/api/abyss-legacy/arena/sell", methods=["POST"])
def abysslegacyarenasell():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = request.get_json(silent=True) or {}
    match_id = int(payload.get("match_id", 0) or 0)
    board_index = int(payload.get("board_index", -1))
    if match_id <= 0 or board_index < 0 or board_index > 4:
        return {"ok": False, "error": "invalid_payload"}, 400
    cards = _load_abyss_cards()
    with connect("accounts") as db:
        state, phase, phase_ends_at, winner = _arena_load_or_create(db, match_id, cards)
        if not state:
            return {"ok": False, "error": "match_not_found"}, 404
        side = _arena_side_for_user(state, int(me[0]))
        if not side:
            return {"ok": False, "error": "forbidden"}, 403
        state, phase, phase_ends_at, winner = _arena_tick(db, state, phase, phase_ends_at)
        if phase not in ("prep", "battle"):
            return {"ok": False, "error": "phase_locked", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        you = state[side]
        board = you["board"]
        card = board[board_index]
        if not card:
            return {"ok": False, "error": "card_not_found", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        refund = int(int(card.get("cost", 0)) * 0.5)
        you["gold"] = int(you.get("gold", 0)) + refund
        board[board_index] = None
        _save_arena_state(db, match_id, state, phase, phase_ends_at, winner)
    return _arena_view_for_side(state, side, phase, phase_ends_at, winner)


@bp.route("/api/abyss-legacy/arena/merge", methods=["POST"])
def abysslegacyarenamerge():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = request.get_json(silent=True) or {}
    match_id = int(payload.get("match_id", 0) or 0)
    from_index = int(payload.get("from_index", -1))
    to_index = int(payload.get("to_index", -1))
    if match_id <= 0 or from_index < 0 or from_index > 4 or to_index < 0 or to_index > 4 or from_index == to_index:
        return {"ok": False, "error": "invalid_payload"}, 400
    cards = _load_abyss_cards()
    with connect("accounts") as db:
        state, phase, phase_ends_at, winner = _arena_load_or_create(db, match_id, cards)
        if not state:
            return {"ok": False, "error": "match_not_found"}, 404
        side = _arena_side_for_user(state, int(me[0]))
        if not side:
            return {"ok": False, "error": "forbidden"}, 403
        state, phase, phase_ends_at, winner = _arena_tick(db, state, phase, phase_ends_at)
        if phase != "prep":
            return {"ok": False, "error": "phase_locked", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        board = state[side]["board"]
        src = board[from_index]
        dst = board[to_index]
        if not src or not dst:
            return {"ok": False, "error": "card_not_found", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        if str(src.get("id", "")) != str(dst.get("id", "")):
            return {"ok": False, "error": "merge_id_mismatch", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        dst["star_level"] = min(5, int(dst.get("star_level", 1)) + 1)
        _apply_star_stats(dst)
        board[from_index] = None
        _save_arena_state(db, match_id, state, phase, phase_ends_at, winner)
    return _arena_view_for_side(state, side, phase, phase_ends_at, winner)


@bp.route("/api/abyss-legacy/arena/skill", methods=["POST"])
def abysslegacyarenaskill():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = request.get_json(silent=True) or {}
    match_id = int(payload.get("match_id", 0) or 0)
    board_index = int(payload.get("board_index", -1))
    skill_index = int(payload.get("skill_index", -1))
    if match_id <= 0 or board_index < 0 or board_index > 4 or skill_index < 0 or skill_index > 2:
        return {"ok": False, "error": "invalid_payload"}, 400
    cards = _load_abyss_cards()
    with connect("accounts") as db:
        state, phase, phase_ends_at, winner = _arena_load_or_create(db, match_id, cards)
        if not state:
            return {"ok": False, "error": "match_not_found"}, 404
        side = _arena_side_for_user(state, int(me[0]))
        if not side:
            return {"ok": False, "error": "forbidden"}, 403
        state, phase, phase_ends_at, winner = _arena_tick(db, state, phase, phase_ends_at)
        if phase != "prep":
            return {"ok": False, "error": "phase_locked", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        card = state[side]["board"][board_index]
        if not card:
            return {"ok": False, "error": "card_not_found", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        card["chosen_skill"] = int(skill_index)
        _save_arena_state(db, match_id, state, phase, phase_ends_at, winner)
    return _arena_view_for_side(state, side, phase, phase_ends_at, winner)


@bp.route("/api/abyss-legacy/arena/target", methods=["POST"])
def abysslegacyarenatarget():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = request.get_json(silent=True) or {}
    match_id = int(payload.get("match_id", 0) or 0)
    board_index = int(payload.get("board_index", -1))
    target_index = int(payload.get("target_index", -1))
    if match_id <= 0 or board_index < 0 or board_index > 4:
        return {"ok": False, "error": "invalid_payload"}, 400
    cards = _load_abyss_cards()
    with connect("accounts") as db:
        state, phase, phase_ends_at, winner = _arena_load_or_create(db, match_id, cards)
        if not state:
            return {"ok": False, "error": "match_not_found"}, 404
        side = _arena_side_for_user(state, int(me[0]))
        if not side:
            return {"ok": False, "error": "forbidden"}, 403
        state, phase, phase_ends_at, winner = _arena_tick(db, state, phase, phase_ends_at)
        if phase != "prep":
            return {"ok": False, "error": "phase_locked", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        card = state[side]["board"][board_index]
        if not card:
            return {"ok": False, "error": "card_not_found", **_arena_view_for_side(state, side, phase, phase_ends_at, winner)}, 400
        if target_index < 0 or target_index > 4:
            card["target_index"] = None
        else:
            card["target_index"] = int(target_index)
        _save_arena_state(db, match_id, state, phase, phase_ends_at, winner)
    return _arena_view_for_side(state, side, phase, phase_ends_at, winner)


@bp.route("/api/abyss-legacy/bots/<int:bot_user_id>/profile")
def abysslegacybotprofile(bot_user_id: int):
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    _bot_tick_if_due()
    with connect("accounts") as db:
        row = db.execute(
            """
            SELECT b.bot_user_id, b.bot_name, b.style, b.favorite_synergy, b.commander_pref,
                   b.decision_ms, b.error_rate, b.wins, b.losses, b.last10_json,
                   r.rank_code, r.rp, p.total_matches, p.total_xp
            FROM abyss_legacy_bot_profiles b
            JOIN abyss_legacy_rank r ON r.user_id = b.bot_user_id
            LEFT JOIN abyss_legacy_profile p ON p.user_id = b.bot_user_id
            WHERE b.bot_user_id = ?
            """,
            (int(bot_user_id),),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "bot_not_found"}, 404
    wins = int(row[7] or 0)
    losses = int(row[8] or 0)
    total_matches = int(row[12] or (wins + losses))
    win_rate = (float(wins) / float(total_matches) * 100.0) if total_matches > 0 else 0.0
    return {
        "ok": True,
        "bot_user_id": int(row[0]),
        "bot_name": str(row[1]),
        "style": str(row[2]),
        "favorite_synergy": str(row[3]),
        "commander_preference": str(row[4]),
        "decision_ms": int(row[5] or 1200),
        "error_rate": float(row[6] or 0.07),
        "wins": wins,
        "losses": losses,
        "total_matches": total_matches,
        "win_rate": round(win_rate, 2),
        "rank_code": str(row[10]),
        "rank_label": ABYSS_LEGACY_RANK_LABELS.get(str(row[10]), str(row[10])),
        "rp": int(row[11] or 0),
        "total_xp": int(row[13] or 0),
        "last10": json.loads(str(row[9] or "[]")),
    }



def register_abysslegacy_backend(
    app_obj,
    request_obj,
    redirect_obj,
    render_template_obj,
    url_for_obj,
    connect_obj,
    applyledger_obj,
    initialize_user_economy_obj,
    spend_gold_obj,
    userlanguage_obj,
    currentaccount_obj,
    texts_obj,
    navcontext_obj,
    viewfile_obj,
    accountbyid_obj,
    root_path=None,
):
    global _registered, app, request, redirect, render_template, url_for, connect, applyledger, initialize_user_economy, spend_gold, userlanguage, currentaccount, texts, navcontext, viewfile, accountbyid, ROOT
    app = app_obj
    request = request_obj
    redirect = redirect_obj
    render_template = render_template_obj
    url_for = url_for_obj
    connect = connect_obj
    applyledger = applyledger_obj
    initialize_user_economy = initialize_user_economy_obj
    spend_gold = spend_gold_obj
    userlanguage = userlanguage_obj
    currentaccount = currentaccount_obj
    texts = texts_obj
    navcontext = navcontext_obj
    viewfile = viewfile_obj
    accountbyid = accountbyid_obj
    if root_path is not None:
        ROOT = Path(root_path)
    if not _registered:
        app.register_blueprint(bp)
        _registered = True



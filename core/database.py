import secrets
import sqlite3
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT = Path(__file__).resolve().parent.parent
DBROOT = ROOT / "database"


def _turkey_tz():
    try:
        return ZoneInfo("Europe/Istanbul")
    except ZoneInfoNotFoundError:
        # Fallback for environments without tzdata package
        return timezone(timedelta(hours=3))


TURKEY_TZ = _turkey_tz()


def path(name: str) -> Path:
    DBROOT.mkdir(parents=True, exist_ok=True)
    target = DBROOT / f"{name}.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def connect(name: str) -> sqlite3.Connection:
    db = sqlite3.connect(path(name), timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout = 20000")
    return db


def hascolumn(db: sqlite3.Connection, table: str, col: str) -> bool:
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == col for row in rows)


def pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def setup() -> None:
    with connect("visitors") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS visitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                language TEXT NOT NULL,
                useragent TEXT NOT NULL,
                ip TEXT NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    with connect("accounts") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                passwordhash TEXT NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        if not hascolumn(db, "accounts", "avatar"):
            db.execute("ALTER TABLE accounts ADD COLUMN avatar TEXT DEFAULT ''")
        if not hascolumn(db, "accounts", "usernamechangedat"):
            db.execute("ALTER TABLE accounts ADD COLUMN usernamechangedat TEXT DEFAULT ''")
        if not hascolumn(db, "accounts", "lastseen"):
            db.execute("ALTER TABLE accounts ADD COLUMN lastseen TEXT DEFAULT ''")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS wallets (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                type TEXT NOT NULL,
                description TEXT NOT NULL,
                reference_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_idempotent
            ON ledger(user_id, type, reference_id)
            WHERE reference_id IS NOT NULL AND reference_id <> ''
            """
        )
        db.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_ledger_no_update
            BEFORE UPDATE ON ledger
            BEGIN
                SELECT RAISE(ABORT, 'ledger is immutable');
            END;
            """
        )
        db.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_ledger_no_delete
            BEFORE DELETE ON ledger
            BEGIN
                SELECT RAISE(ABORT, 'ledger is immutable');
            END;
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_level (
                user_id INTEGER PRIMARY KEY,
                level INTEGER NOT NULL DEFAULT 1,
                xp INTEGER NOT NULL DEFAULT 0,
                total_xp INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS xp_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                reference_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_xp_idempotent
            ON xp_ledger(user_id, reference_id)
            WHERE reference_id IS NOT NULL AND reference_id <> ''
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS casino_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_name TEXT NOT NULL DEFAULT '',
                delta_amount INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    with connect("casino/rewards") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_daily_rewards (
                user_id INTEGER NOT NULL,
                week_start_date TEXT NOT NULL,
                rewards_day1 INTEGER NOT NULL,
                rewards_day2 INTEGER NOT NULL,
                rewards_day3 INTEGER NOT NULL,
                rewards_day4 INTEGER NOT NULL,
                rewards_day5 INTEGER NOT NULL,
                rewards_day6 INTEGER NOT NULL,
                rewards_day7 INTEGER NOT NULL,
                bonus_day7 INTEGER NOT NULL,
                claimed_days INTEGER NOT NULL DEFAULT 0,
                last_claim_date TEXT NOT NULL DEFAULT '',
                streak_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, week_start_date)
            )
            """
        )

    with connect("social") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS friendships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usera INTEGER NOT NULL,
                userb INTEGER NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(usera, userb)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender INTEGER NOT NULL,
                receiver INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                createdat TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(sender, receiver)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                blocker INTEGER NOT NULL,
                blocked INTEGER NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(blocker, blocked)
            )
            """
        )

    with connect("dm") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usera INTEGER NOT NULL,
                userb INTEGER NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(usera, userb)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversationid INTEGER NOT NULL,
                sender INTEGER NOT NULL,
                kind TEXT NOT NULL,
                refid INTEGER NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        if not hascolumn(db, "entries", "readat"):
            db.execute("ALTER TABLE entries ADD COLUMN readat TEXT DEFAULT ''")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender INTEGER NOT NULL,
                receiver INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                createdat TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(sender, receiver)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usera INTEGER NOT NULL,
                userb INTEGER NOT NULL,
                allowed INTEGER NOT NULL DEFAULT 1,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(usera, userb)
            )
            """
        )

    with connect("dmtext") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                body TEXT NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    with connect("dmimage") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    with connect("dmvideo") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    with connect("dmaudio") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    with connect("dmfile") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    with connect("servers") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ownerid INTEGER NOT NULL,
                name TEXT NOT NULL,
                avatar TEXT NOT NULL DEFAULT '',
                visibility TEXT NOT NULL DEFAULT 'public',
                joinmode TEXT NOT NULL DEFAULT 'open',
                joincode TEXT NOT NULL DEFAULT '',
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serverid INTEGER NOT NULL,
                userid INTEGER NOT NULL,
                roleid INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                createdat TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(serverid, userid)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS joins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serverid INTEGER NOT NULL,
                sender INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serverid INTEGER NOT NULL,
                name TEXT NOT NULL,
                perms TEXT NOT NULL DEFAULT '{}',
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serverid INTEGER NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'text',
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serverid INTEGER NOT NULL,
                categoryid INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'text',
                contentmode TEXT NOT NULL DEFAULT 'all',
                visibleperms TEXT NOT NULL DEFAULT '',
                writeperms TEXT NOT NULL DEFAULT '',
                shareperms TEXT NOT NULL DEFAULT '',
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serverid INTEGER NOT NULL,
                channelid INTEGER NOT NULL,
                sender INTEGER NOT NULL,
                kind TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                path TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS voicepresence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serverid INTEGER NOT NULL,
                channelid INTEGER NOT NULL,
                userid INTEGER NOT NULL,
                lastseen TEXT NOT NULL,
                UNIQUE(serverid, channelid, userid)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS voicesignals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serverid INTEGER NOT NULL,
                channelid INTEGER NOT NULL,
                sender INTEGER NOT NULL,
                target INTEGER NOT NULL,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                createdat TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        if not hascolumn(db, "servers", "visibleperms"):
            db.execute("ALTER TABLE servers ADD COLUMN visibleperms TEXT NOT NULL DEFAULT ''")
        if not hascolumn(db, "servers", "writeperms"):
            db.execute("ALTER TABLE servers ADD COLUMN writeperms TEXT NOT NULL DEFAULT ''")
        if not hascolumn(db, "servers", "shareperms"):
            db.execute("ALTER TABLE servers ADD COLUMN shareperms TEXT NOT NULL DEFAULT ''")

def savevisitor(token: str, language: str, useragent: str, ip: str) -> None:
    with connect("visitors") as db:
        db.execute(
            """
            INSERT INTO visitors (token, language, useragent, ip)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                language=excluded.language,
                useragent=excluded.useragent,
                ip=excluded.ip
            """,
            (token, language, useragent, ip),
        )


def visitorlanguage(token: str) -> str | None:
    if not token:
        return None
    with connect("visitors") as db:
        row = db.execute("SELECT language FROM visitors WHERE token = ?", (str(token),)).fetchone()
    return str(row[0]) if row and row[0] else None


def createaccount(username: str, passwordhash: str) -> bool:
    try:
        with connect("accounts") as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO accounts (username, passwordhash) VALUES (?, ?)", (username, passwordhash))
            user_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
            _applyledger(db, user_id, 1000, "initial_grant", "signup bonus", f"signup:{user_id}:initial_grant")
            db.execute("COMMIT")
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception:
        return False


def _ensurewallet(db: sqlite3.Connection, user_id: int) -> None:
    db.execute("INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)", (int(user_id),))


def _applyledger(
    db: sqlite3.Connection,
    user_id: int,
    amount: int,
    tx_type: str,
    description: str,
    reference_id: str | None = None,
) -> bool:
    if int(amount) == 0:
        raise ValueError("amount cannot be zero")
    _ensurewallet(db, user_id)
    try:
        db.execute(
            "INSERT INTO ledger (user_id, amount, type, description, reference_id) VALUES (?, ?, ?, ?, ?)",
            (int(user_id), int(amount), str(tx_type), str(description), reference_id),
        )
    except sqlite3.IntegrityError:
        return False
    db.execute(
        "UPDATE wallets SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
        (int(amount), int(user_id)),
    )
    return True


def applyledger(user_id: int, amount: int, tx_type: str, description: str, reference_id: str | None = None) -> bool:
    with connect("accounts") as db:
        db.execute("BEGIN IMMEDIATE")
        applied = _applyledger(db, user_id, amount, tx_type, description, reference_id)
        if applied:
            db.execute("COMMIT")
            return True
        db.execute("ROLLBACK")
        return False


def walletbalance(user_id: int) -> int:
    with connect("accounts") as db:
        _ensurewallet(db, user_id)
        row = db.execute("SELECT balance FROM wallets WHERE user_id = ?", (int(user_id),)).fetchone()
    return int(row[0]) if row else 0


def syncwallet(user_id: int) -> int:
    with connect("accounts") as db:
        db.execute("BEGIN IMMEDIATE")
        _ensurewallet(db, user_id)
        row = db.execute("SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE user_id = ?", (int(user_id),)).fetchone()
        balance = int(row[0]) if row else 0
        db.execute(
            "UPDATE wallets SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (balance, int(user_id)),
        )
        db.execute("COMMIT")
    return balance


def ensurelevel(user_id: int) -> None:
    with connect("accounts") as db:
        db.execute("INSERT OR IGNORE INTO user_level (user_id, level, xp, total_xp) VALUES (?, 1, 0, 0)", (int(user_id),))


def levelstate(user_id: int):
    with connect("accounts") as db:
        db.execute("INSERT OR IGNORE INTO user_level (user_id, level, xp, total_xp) VALUES (?, 1, 0, 0)", (int(user_id),))
        return db.execute(
            "SELECT level, xp, total_xp, updated_at FROM user_level WHERE user_id = ?",
            (int(user_id),),
        ).fetchone()


def applyxp(
    user_id: int,
    amount: int,
    reason: str,
    reference_id: str | None = None,
    max_level: int = 100,
    base_xp: int = 100,
    step_xp: int = 50,
) -> tuple[bool, int, int, int]:
    value = int(amount)
    if value <= 0:
        raise ValueError("amount must be positive")
    with connect("accounts") as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO user_level (user_id, level, xp, total_xp) VALUES (?, 1, 0, 0)", (int(user_id),))
        try:
            db.execute(
                "INSERT INTO xp_ledger (user_id, amount, reason, reference_id) VALUES (?, ?, ?, ?)",
                (int(user_id), value, str(reason), reference_id),
            )
        except sqlite3.IntegrityError:
            row = db.execute("SELECT level, xp, total_xp FROM user_level WHERE user_id = ?", (int(user_id),)).fetchone()
            db.execute("ROLLBACK")
            return False, int(row[0]), int(row[1]), int(row[2])

        row = db.execute("SELECT level, xp, total_xp FROM user_level WHERE user_id = ?", (int(user_id),)).fetchone()
        level = int(row[0]) if row else 1
        xp = int(row[1]) if row else 0
        total_xp = int(row[2]) if row else 0
        xp += value
        total_xp += value

        while level < int(max_level):
            required = int(base_xp) + (int(level) - 1) * int(step_xp)
            if xp < required:
                break
            xp -= required
            level += 1

        db.execute(
            "UPDATE user_level SET level = ?, xp = ?, total_xp = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (level, xp, total_xp, int(user_id)),
        )
        db.execute("COMMIT")
        return True, level, xp, total_xp


def casinosummary(user_id: int):
    with connect("accounts") as db:
        row = db.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN delta_amount > 0 THEN delta_amount ELSE 0 END), 0) AS total_win_amount,
                COALESCE(SUM(CASE WHEN delta_amount < 0 THEN -delta_amount ELSE 0 END), 0) AS total_lose_amount
            FROM casino_games
            WHERE user_id = ?
            """,
            (int(user_id),),
        ).fetchone()
    wins = int(row[0]) if row else 0
    loses = int(row[1]) if row else 0
    ratio = round((wins / loses), 2) if loses > 0 else (float(wins) if wins > 0 else 0.0)
    return wins, loses, ratio


def casinoleaderboard(period: str, limit: int = 5):
    where = ""
    if period == "daily":
        where = "AND created_at >= datetime('now', '-1 day')"
    elif period == "weekly":
        where = "AND created_at >= datetime('now', '-7 day')"
    elif period == "monthly":
        where = "AND created_at >= datetime('now', '-30 day')"
    with connect("accounts") as db:
        rows = db.execute(
            f"""
            SELECT a.username, COALESCE(SUM(CASE WHEN g.delta_amount > 0 THEN g.delta_amount ELSE 0 END), 0) AS total_win
            FROM casino_games g
            JOIN accounts a ON a.id = g.user_id
            WHERE 1=1 {where}
            GROUP BY g.user_id, a.username
            HAVING total_win > 0
            ORDER BY total_win DESC, a.username ASC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [{"username": r[0], "amount": int(r[1])} for r in rows]


def casinorichest(limit: int = 5):
    with connect("accounts") as db:
        rows = db.execute(
            """
            SELECT a.username, w.balance
            FROM wallets w
            JOIN accounts a ON a.id = w.user_id
            WHERE EXISTS (SELECT 1 FROM casino_games g WHERE g.user_id = w.user_id)
            ORDER BY w.balance DESC, a.username ASC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [{"username": r[0], "balance": int(r[1])} for r in rows]


def casinolastgames(user_id: int, limit: int = 10):
    with connect("accounts") as db:
        rows = db.execute(
            """
            SELECT game_name, delta_amount, created_at
            FROM casino_games
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(user_id), int(limit)),
        ).fetchall()
    return [{"game_name": r[0], "delta_amount": int(r[1]), "created_at": r[2]} for r in rows]


def recordcasinogame(user_id: int, game_name: str, delta_amount: int) -> None:
    with connect("accounts") as db:
        db.execute(
            "INSERT INTO casino_games (user_id, game_name, delta_amount) VALUES (?, ?, ?)",
            (int(user_id), str(game_name), int(delta_amount)),
        )


def _turkey_now() -> datetime:
    return datetime.now(TURKEY_TZ)


def _week_start(day: datetime) -> datetime:
    return (day - timedelta(days=day.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def _week_rewards(user_id: int, week_start_text: str) -> tuple[list[int], int]:
    seed = f"{int(user_id)}:{week_start_text}"
    rng = Random(seed)
    rewards = [rng.randint(100, 2000) for _ in range(7)]
    bonus = rng.randint(1000, 3000)
    return rewards, bonus


def _ensure_reward_row(db: sqlite3.Connection, user_id: int, week_start_text: str):
    row = db.execute(
        """
        SELECT rewards_day1, rewards_day2, rewards_day3, rewards_day4, rewards_day5, rewards_day6, rewards_day7,
               bonus_day7, claimed_days, last_claim_date, streak_count
        FROM casino.user_daily_rewards
        WHERE user_id = ? AND week_start_date = ?
        """,
        (int(user_id), week_start_text),
    ).fetchone()
    if row:
        return row
    rewards, bonus = _week_rewards(user_id, week_start_text)
    db.execute(
        """
        INSERT INTO casino.user_daily_rewards (
            user_id, week_start_date, rewards_day1, rewards_day2, rewards_day3, rewards_day4, rewards_day5, rewards_day6, rewards_day7, bonus_day7
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (int(user_id), week_start_text, rewards[0], rewards[1], rewards[2], rewards[3], rewards[4], rewards[5], rewards[6], bonus),
    )
    return (rewards[0], rewards[1], rewards[2], rewards[3], rewards[4], rewards[5], rewards[6], bonus, 0, "", 0)


def dailyrewardstate(user_id: int):
    now = _turkey_now()
    today_text = now.date().isoformat()
    start = _week_start(now)
    week_start_text = start.date().isoformat()
    day_index = (now.date() - start.date()).days + 1
    with connect("accounts") as db:
        db.execute("ATTACH DATABASE ? AS casino", (str(path("casino/rewards")),))
        row = _ensure_reward_row(db, int(user_id), week_start_text)
        rewards = [int(row[0]), int(row[1]), int(row[2]), int(row[3]), int(row[4]), int(row[5]), int(row[6])]
        bonus = int(row[7])
        claimed_days = int(row[8])
        last_claim_date = row[9] or ""
        streak_count = int(row[10] or 0)
        days = []
        for i, amount in enumerate(rewards, start=1):
            bit = 1 << (i - 1)
            claimed = bool(claimed_days & bit)
            state = "future"
            if claimed:
                state = "claimed"
            elif i == day_index:
                state = "today"
            days.append({"day": i, "amount": amount, "claimed": claimed, "state": state})
    can_claim = 1 <= day_index <= 7 and not bool(claimed_days & (1 << (day_index - 1))) and last_claim_date != today_text
    return {
        "week_start_date": week_start_text,
        "today_index": day_index,
        "days": days,
        "bonus_day7": bonus,
        "claimed_days": claimed_days,
        "last_claim_date": last_claim_date,
        "streak_count": streak_count,
        "can_claim_today": bool(can_claim),
    }


def claimdailyreward(user_id: int):
    now = _turkey_now()
    today_text = now.date().isoformat()
    start = _week_start(now)
    week_start_text = start.date().isoformat()
    day_index = (now.date() - start.date()).days + 1
    if day_index < 1 or day_index > 7:
        return {"ok": False, "error": "invalid_day"}
    with connect("accounts") as db:
        db.execute("ATTACH DATABASE ? AS casino", (str(path("casino/rewards")),))
        db.execute("BEGIN IMMEDIATE")
        row = _ensure_reward_row(db, int(user_id), week_start_text)
        rewards = [int(row[0]), int(row[1]), int(row[2]), int(row[3]), int(row[4]), int(row[5]), int(row[6])]
        bonus = int(row[7])
        claimed_days = int(row[8])
        last_claim_date = row[9] or ""
        streak_count = int(row[10] or 0)
        bit = 1 << (day_index - 1)
        if claimed_days & bit or last_claim_date == today_text:
            db.execute("ROLLBACK")
            return {"ok": False, "error": "already_claimed"}

        amount = rewards[day_index - 1]
        prev = today_text
        if last_claim_date:
            try:
                prev = (datetime.fromisoformat(today_text) - timedelta(days=1)).date().isoformat()
            except Exception:
                prev = ""
        if last_claim_date == prev:
            streak_count = min(7, streak_count + 1)
        else:
            streak_count = 1
        if day_index == 7 and streak_count >= 7:
            amount += bonus

        ref = f"daily_reward:{week_start_text}:day{day_index}"
        applied = _applyledger(db, int(user_id), int(amount), "daily_reward", "daily reward claim", ref)
        if not applied:
            db.execute("ROLLBACK")
            return {"ok": False, "error": "idempotent"}

        claimed_days |= bit
        db.execute(
            """
            UPDATE casino.user_daily_rewards
            SET claimed_days = ?, last_claim_date = ?, streak_count = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND week_start_date = ?
            """,
            (claimed_days, today_text, streak_count, int(user_id), week_start_text),
        )
        db.execute("COMMIT")
    state = dailyrewardstate(int(user_id))
    return {"ok": True, "claimed_amount": int(amount), "state": state}


def accountbyname(username: str):
    with connect("accounts") as db:
        return db.execute(
            "SELECT id, username, passwordhash, avatar, usernamechangedat, lastseen FROM accounts WHERE username = ?",
            (username,),
        ).fetchone()


def accountbyid(accountid: int):
    with connect("accounts") as db:
        return db.execute(
            "SELECT id, username, passwordhash, avatar, usernamechangedat, lastseen FROM accounts WHERE id = ?",
            (accountid,),
        ).fetchone()


def accountsbasic(ids: list[int]):
    if not ids:
        return []
    marks = ",".join(["?"] * len(ids))
    with connect("accounts") as db:
        rows = db.execute(f"SELECT id, username, avatar, lastseen FROM accounts WHERE id IN ({marks})", tuple(ids)).fetchall()
    byid = {r[0]: r for r in rows}
    return [byid[i] for i in ids if i in byid]


def allaccounts(exclude: int, limit: int = 20):
    with connect("accounts") as db:
        return db.execute(
            "SELECT id, username, avatar, lastseen FROM accounts WHERE id != ? ORDER BY id DESC LIMIT ?",
            (exclude, limit),
        ).fetchall()


def updateusername(accountid: int, username: str, changedat: str) -> bool:
    try:
        with connect("accounts") as db:
            db.execute("UPDATE accounts SET username = ?, usernamechangedat = ? WHERE id = ?", (username, changedat, accountid))
        return True
    except sqlite3.IntegrityError:
        return False


def updateavatar(accountid: int, avatar: str) -> None:
    with connect("accounts") as db:
        db.execute("UPDATE accounts SET avatar = ? WHERE id = ?", (avatar, accountid))


def updatepassword(accountid: int, passwordhash: str) -> None:
    with connect("accounts") as db:
        db.execute("UPDATE accounts SET passwordhash = ? WHERE id = ?", (passwordhash, accountid))


def heartbeat(accountid: int, when: str) -> None:
    try:
        with connect("accounts") as db:
            db.execute("UPDATE accounts SET lastseen = ? WHERE id = ?", (when, accountid))
    except sqlite3.OperationalError:
        # Presence update is best-effort; do not fail request flow on transient locks.
        return


def arefriends(a: int, b: int) -> bool:
    x, y = pair(a, b)
    with connect("social") as db:
        row = db.execute("SELECT 1 FROM friendships WHERE usera = ? AND userb = ?", (x, y)).fetchone()
    return bool(row)


def isblocked(a: int, b: int) -> bool:
    with connect("social") as db:
        row = db.execute("SELECT 1 FROM blocks WHERE blocker = ? AND blocked = ?", (a, b)).fetchone()
    return bool(row)


def blockedids(blocker: int):
    with connect("social") as db:
        rows = db.execute("SELECT blocked FROM blocks WHERE blocker = ? ORDER BY id DESC", (blocker,)).fetchall()
    return [r[0] for r in rows]


def unblockuser(blocker: int, blocked: int) -> None:
    with connect("social") as db:
        db.execute("DELETE FROM blocks WHERE blocker = ? AND blocked = ?", (blocker, blocked))


def requeststatus(a: int, b: int) -> str:
    with connect("social") as db:
        row = db.execute("SELECT status FROM requests WHERE sender = ? AND receiver = ?", (a, b)).fetchone()
    return row[0] if row else ""


def sendrequest(sender: int, receiver: int) -> None:
    with connect("social") as db:
        db.execute(
            "INSERT OR REPLACE INTO requests (id, sender, receiver, status) VALUES ((SELECT id FROM requests WHERE sender = ? AND receiver = ?), ?, ?, 'pending')",
            (sender, receiver, sender, receiver),
        )


def pendingreceived(receiver: int):
    with connect("social") as db:
        return db.execute("SELECT id, sender FROM requests WHERE receiver = ? AND status = 'pending' ORDER BY id DESC", (receiver,)).fetchall()


def pendingsent(sender: int):
    with connect("social") as db:
        rows = db.execute("SELECT receiver FROM requests WHERE sender = ? AND status = 'pending'", (sender,)).fetchall()
    return {r[0] for r in rows}


def acceptrequest(requestid: int, receiver: int) -> None:
    with connect("social") as db:
        row = db.execute("SELECT sender, receiver FROM requests WHERE id = ? AND receiver = ? AND status = 'pending'", (requestid, receiver)).fetchone()
        if not row:
            return
        sender = row[0]
        x, y = pair(sender, receiver)
        db.execute("INSERT OR IGNORE INTO friendships (usera, userb) VALUES (?, ?)", (x, y))
        db.execute("UPDATE requests SET status = 'accepted' WHERE id = ?", (requestid,))


def rejectrequest(requestid: int, receiver: int) -> None:
    with connect("social") as db:
        db.execute("UPDATE requests SET status = 'rejected' WHERE id = ? AND receiver = ? AND status = 'pending'", (requestid, receiver))


def removefriend(a: int, b: int) -> None:
    x, y = pair(a, b)
    with connect("social") as db:
        db.execute("DELETE FROM friendships WHERE usera = ? AND userb = ?", (x, y))


def blockuser(blocker: int, blocked: int) -> None:
    x, y = pair(blocker, blocked)
    with connect("social") as db:
        db.execute("INSERT OR IGNORE INTO blocks (blocker, blocked) VALUES (?, ?)", (blocker, blocked))
        db.execute("DELETE FROM friendships WHERE usera = ? AND userb = ?", (x, y))
        db.execute("DELETE FROM requests WHERE (sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?)", (blocker, blocked, blocked, blocker))


def friendids(user: int):
    with connect("social") as db:
        rows = db.execute(
            "SELECT CASE WHEN usera = ? THEN userb ELSE usera END AS fid FROM friendships WHERE usera = ? OR userb = ? ORDER BY id DESC",
            (user, user, user),
        ).fetchall()
    return [r[0] for r in rows]


def friendcount(user: int) -> int:
    with connect("social") as db:
        row = db.execute("SELECT COUNT(*) FROM friendships WHERE usera = ? OR userb = ?", (user, user)).fetchone()
    return row[0]


def conversation(a: int, b: int) -> int:
    x, y = pair(a, b)
    with connect("dm") as db:
        row = db.execute("SELECT id FROM conversations WHERE usera = ? AND userb = ?", (x, y)).fetchone()
        if row:
            return row[0]
        db.execute("INSERT INTO conversations (usera, userb) VALUES (?, ?)", (x, y))
        row2 = db.execute("SELECT id FROM conversations WHERE usera = ? AND userb = ?", (x, y)).fetchone()
    return row2[0]


def dmpeers(user: int):
    with connect("dm") as db:
        rows = db.execute(
            "SELECT CASE WHEN usera = ? THEN userb ELSE usera END AS peer FROM conversations WHERE usera = ? OR userb = ? ORDER BY id DESC",
            (user, user, user),
        ).fetchall()
    return [r[0] for r in rows]


def markread(convid: int, reader: int, when: str) -> None:
    with connect("dm") as db:
        db.execute(
            "UPDATE entries SET readat = ? WHERE conversationid = ? AND sender != ? AND (readat = '' OR readat IS NULL)",
            (when, convid, reader),
        )


def unreadcount(convid: int, reader: int) -> int:
    with connect("dm") as db:
        row = db.execute(
            "SELECT COUNT(*) FROM entries WHERE conversationid = ? AND sender != ? AND (readat = '' OR readat IS NULL)",
            (convid, reader),
        ).fetchone()
    return row[0]


def addtext(convid: int, sender: int, body: str) -> None:
    with connect("dmtext") as db:
        db.execute("INSERT INTO items (body) VALUES (?)", (body,))
        ref = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    with connect("dm") as db:
        db.execute("INSERT INTO entries (conversationid, sender, kind, refid, readat) VALUES (?, ?, 'text', ?, '')", (convid, sender, ref))


def addfile(convid: int, sender: int, kind: str, relpath: str, size: int) -> None:
    dbname = {"image": "dmimage", "video": "dmvideo", "audio": "dmaudio", "file": "dmfile"}[kind]
    with connect(dbname) as db:
        db.execute("INSERT INTO items (path, size) VALUES (?, ?)", (relpath, size))
        ref = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    with connect("dm") as db:
        db.execute("INSERT INTO entries (conversationid, sender, kind, refid, readat) VALUES (?, ?, ?, ?, '')", (convid, sender, kind, ref))


def latestentryid(convid: int) -> int:
    with connect("dm") as db:
        row = db.execute("SELECT COALESCE(MAX(id), 0) FROM entries WHERE conversationid = ?", (convid,)).fetchone()
    return row[0]


def dmhistory(convid: int):
    with connect("dm") as db:
        entries = db.execute(
            "SELECT id, sender, kind, refid, createdat, readat FROM entries WHERE conversationid = ? ORDER BY id ASC",
            (convid,),
        ).fetchall()

    out = []
    for eid, sender, kind, refid, createdat, readat in entries:
        if kind == "text":
            with connect("dmtext") as db:
                row = db.execute("SELECT body FROM items WHERE id = ?", (refid,)).fetchone()
            out.append({"id": eid, "sender": sender, "kind": kind, "body": row[0] if row else "", "createdat": createdat, "read": bool(readat)})
        else:
            dbname = {"image": "dmimage", "video": "dmvideo", "audio": "dmaudio", "file": "dmfile"}[kind]
            with connect(dbname) as db:
                row = db.execute("SELECT path, size FROM items WHERE id = ?", (refid,)).fetchone()
            out.append({"id": eid, "sender": sender, "kind": kind, "path": row[0] if row else "", "size": row[1] if row else 0, "createdat": createdat, "read": bool(readat)})
    return out


def dmpermission(a: int, b: int) -> bool:
    x, y = pair(a, b)
    with connect("dm") as db:
        row = db.execute("SELECT allowed FROM permissions WHERE usera = ? AND userb = ?", (x, y)).fetchone()
    return bool(row and row[0] == 1)


def setdmpermission(a: int, b: int, allowed: int = 1) -> None:
    x, y = pair(a, b)
    with connect("dm") as db:
        db.execute(
            "INSERT OR REPLACE INTO permissions (id, usera, userb, allowed) VALUES ((SELECT id FROM permissions WHERE usera = ? AND userb = ?), ?, ?, ?)",
            (x, y, x, y, allowed),
        )


def senddmrequest(sender: int, receiver: int) -> None:
    with connect("dm") as db:
        db.execute(
            "INSERT OR REPLACE INTO requests (id, sender, receiver, status) VALUES ((SELECT id FROM requests WHERE sender = ? AND receiver = ?), ?, ?, 'pending')",
            (sender, receiver, sender, receiver),
        )


def pendingdmreceived(receiver: int):
    with connect("dm") as db:
        return db.execute("SELECT id, sender FROM requests WHERE receiver = ? AND status = 'pending' ORDER BY id DESC", (receiver,)).fetchall()


def acceptdmrequest(reqid: int, receiver: int) -> None:
    with connect("dm") as db:
        row = db.execute("SELECT sender FROM requests WHERE id = ? AND receiver = ? AND status = 'pending'", (reqid, receiver)).fetchone()
        if not row:
            return
        sender = int(row[0])
        setdmpermission(sender, receiver, 1)
        db.execute("UPDATE requests SET status = 'accepted' WHERE id = ?", (reqid,))


def rejectdmrequest(reqid: int, receiver: int) -> None:
    with connect("dm") as db:
        db.execute("UPDATE requests SET status = 'rejected' WHERE id = ? AND receiver = ? AND status = 'pending'", (reqid, receiver))


_JOINCODE_ALPHABET = string.ascii_lowercase + string.digits


def _normalize_joincode(value: str) -> str:
    cleaned = "".join(ch for ch in (value or "").strip().lower() if ch.isalnum() or ch in ("-", "_"))
    return cleaned[:32]


def _random_joincode(length: int = 8) -> str:
    return "".join(secrets.choice(_JOINCODE_ALPHABET) for _ in range(length))


def _generate_unique_joincode(db: sqlite3.Connection, preferred: str = "", exclude_serverid: int = 0) -> str:
    base = _normalize_joincode(preferred)
    for _ in range(64):
        if base:
            candidate = base
            base = f"{base}-{_random_joincode(4)}" if len(base) <= 27 else f"{base[:27]}-{_random_joincode(4)}"
        else:
            candidate = _random_joincode(8)
        row = db.execute(
            "SELECT 1 FROM servers WHERE lower(joincode) = ? AND id != ? LIMIT 1",
            (candidate.lower(), int(exclude_serverid or 0)),
        ).fetchone()
        if not row:
            return candidate
    return _random_joincode(12)


def servercreate(ownerid: int, name: str, avatar: str, visibility: str, joinmode: str, joincode: str) -> int:
    with connect("servers") as db:
        code = _generate_unique_joincode(db, preferred=joincode)
        db.execute(
            "INSERT INTO servers (ownerid, name, avatar, visibility, joinmode, joincode) VALUES (?, ?, ?, ?, ?, ?)",
            (ownerid, name, avatar, visibility, joinmode, code),
        )
        sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT OR IGNORE INTO members (serverid, userid, roleid, status) VALUES (?, ?, 0, 'active')", (sid, ownerid))
    return sid


def serverbyid(serverid: int):
    with connect("servers") as db:
        row = db.execute(
            "SELECT id, ownerid, name, avatar, visibility, joinmode, joincode, visibleperms, writeperms, shareperms FROM servers WHERE id = ?",
            (serverid,),
        ).fetchone()
        if not row:
            return None
        if not (row[6] or "").strip():
            new_code = _generate_unique_joincode(db, exclude_serverid=serverid)
            db.execute("UPDATE servers SET joincode = ? WHERE id = ?", (new_code, serverid))
            row = db.execute(
                "SELECT id, ownerid, name, avatar, visibility, joinmode, joincode, visibleperms, writeperms, shareperms FROM servers WHERE id = ?",
                (serverid,),
            ).fetchone()
        return row


def serverlist(userid: int):
    with connect("servers") as db:
        mine = db.execute(
            "SELECT s.id, s.name, s.avatar, s.visibility FROM servers s JOIN members m ON m.serverid = s.id WHERE m.userid = ? AND m.status = 'active' ORDER BY s.id DESC",
            (userid,),
        ).fetchall()
        publics = db.execute(
            "SELECT id, name, avatar, visibility FROM servers WHERE visibility = 'public' ORDER BY id DESC LIMIT 50"
        ).fetchall()
    return mine, publics


def serverismember(serverid: int, userid: int) -> bool:
    with connect("servers") as db:
        row = db.execute("SELECT 1 FROM members WHERE serverid = ? AND userid = ? AND status = 'active'", (serverid, userid)).fetchone()
    return bool(row)


def serverjoinrequest(serverid: int, userid: int) -> None:
    with connect("servers") as db:
        db.execute(
            "INSERT INTO joins (serverid, sender, status) VALUES (?, ?, 'pending')",
            (serverid, userid),
        )


def serverjoin(serverid: int, userid: int) -> None:
    with connect("servers") as db:
        db.execute("INSERT OR REPLACE INTO members (id, serverid, userid, roleid, status) VALUES ((SELECT id FROM members WHERE serverid = ? AND userid = ?), ?, ?, 0, 'active')", (serverid, userid, serverid, userid))


def serverpending(serverid: int):
    with connect("servers") as db:
        return db.execute("SELECT id, sender FROM joins WHERE serverid = ? AND status = 'pending' ORDER BY id DESC", (serverid,)).fetchall()


def serveraccept(joinid: int, ownerid: int) -> None:
    with connect("servers") as db:
        row = db.execute(
            "SELECT j.serverid, j.sender FROM joins j JOIN servers s ON s.id = j.serverid WHERE j.id = ? AND s.ownerid = ? AND j.status = 'pending'",
            (joinid, ownerid),
        ).fetchone()
        if not row:
            return
        db.execute("UPDATE joins SET status = 'accepted' WHERE id = ?", (joinid,))
        db.execute("INSERT OR IGNORE INTO members (serverid, userid, roleid, status) VALUES (?, ?, 0, 'active')", (row[0], row[1]))


def serverreject(joinid: int, ownerid: int) -> None:
    with connect("servers") as db:
        db.execute(
            "UPDATE joins SET status = 'rejected' WHERE id = ? AND status = 'pending' AND serverid IN (SELECT id FROM servers WHERE ownerid = ?)",
            (joinid, ownerid),
        )


def serverroles(serverid: int):
    with connect("servers") as db:
        return db.execute("SELECT id, name, perms FROM roles WHERE serverid = ? ORDER BY id ASC", (serverid,)).fetchall()


def servercreaterole(serverid: int, name: str, perms: str) -> int:
    with connect("servers") as db:
        db.execute("INSERT INTO roles (serverid, name, perms) VALUES (?, ?, ?)", (serverid, name, perms))
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def serverupdaterole(roleid: int, serverid: int, name: str, perms: str) -> None:
    with connect("servers") as db:
        db.execute("UPDATE roles SET name = ?, perms = ? WHERE id = ? AND serverid = ?", (name, perms, roleid, serverid))


def servermembers(serverid: int):
    with connect("servers") as db:
        return db.execute("SELECT userid, roleid, status FROM members WHERE serverid = ? ORDER BY id ASC", (serverid,)).fetchall()


def serverassignrole(serverid: int, userid: int, roleid: int) -> None:
    with connect("servers") as db:
        db.execute("UPDATE members SET roleid = ? WHERE serverid = ? AND userid = ?", (roleid, serverid, userid))


def servermemberrole(serverid: int, userid: int) -> int:
    with connect("servers") as db:
        row = db.execute("SELECT roleid FROM members WHERE serverid = ? AND userid = ? AND status = 'active'", (serverid, userid)).fetchone()
    return int(row[0]) if row else -1


def servercategories(serverid: int):
    with connect("servers") as db:
        return db.execute("SELECT id, name, kind FROM categories WHERE serverid = ? ORDER BY id ASC", (serverid,)).fetchall()


def servercreatecategory(serverid: int, name: str, kind: str) -> int:
    with connect("servers") as db:
        db.execute("INSERT INTO categories (serverid, name, kind) VALUES (?, ?, ?)", (serverid, name, kind))
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def serverupdatecategory(serverid: int, categoryid: int, name: str, kind: str) -> None:
    with connect("servers") as db:
        db.execute("UPDATE categories SET name = ?, kind = ? WHERE id = ? AND serverid = ?", (name, kind, categoryid, serverid))


def serverchannels(serverid: int):
    with connect("servers") as db:
        return db.execute(
            "SELECT id, categoryid, name, kind, contentmode, visibleperms, writeperms, shareperms FROM channels WHERE serverid = ? ORDER BY id ASC",
            (serverid,),
        ).fetchall()


def servercreatechannel(serverid: int, categoryid: int, name: str, kind: str, contentmode: str, visibleperms: str, writeperms: str, shareperms: str) -> int:
    with connect("servers") as db:
        db.execute(
            "INSERT INTO channels (serverid, categoryid, name, kind, contentmode, visibleperms, writeperms, shareperms) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (serverid, categoryid, name, kind, contentmode, visibleperms, writeperms, shareperms),
        )
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def serverupdatechannel(serverid: int, channelid: int, categoryid: int, name: str, kind: str, contentmode: str, visibleperms: str, writeperms: str, shareperms: str) -> None:
    with connect("servers") as db:
        db.execute(
            "UPDATE channels SET categoryid = ?, name = ?, kind = ?, contentmode = ?, visibleperms = ?, writeperms = ?, shareperms = ? WHERE id = ? AND serverid = ?",
            (categoryid, name, kind, contentmode, visibleperms, writeperms, shareperms, channelid, serverid),
        )


def serverchannel(serverid: int, channelid: int):
    with connect("servers") as db:
        return db.execute(
            "SELECT id, categoryid, name, kind, contentmode, visibleperms, writeperms, shareperms FROM channels WHERE id = ? AND serverid = ?",
            (channelid, serverid),
        ).fetchone()


def serverentries(serverid: int, channelid: int, limit: int = 200):
    with connect("servers") as db:
        return db.execute(
            "SELECT id, sender, kind, body, path, size, createdat FROM entries WHERE serverid = ? AND channelid = ? ORDER BY id DESC LIMIT ?",
            (serverid, channelid, limit),
        ).fetchall()[::-1]


def addserverentry(serverid: int, channelid: int, sender: int, kind: str, body: str, path: str, size: int) -> None:
    with connect("servers") as db:
        db.execute(
            "INSERT INTO entries (serverid, channelid, sender, kind, body, path, size) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (serverid, channelid, sender, kind, body, path, size),
        )


def voiceping(serverid: int, channelid: int, userid: int, when: str) -> None:
    with connect("servers") as db:
        db.execute(
            "INSERT OR REPLACE INTO voicepresence (id, serverid, channelid, userid, lastseen) VALUES ((SELECT id FROM voicepresence WHERE serverid = ? AND channelid = ? AND userid = ?), ?, ?, ?, ?)",
            (serverid, channelid, userid, serverid, channelid, userid, when),
        )


def voiceparticipants(serverid: int, channelid: int):
    with connect("servers") as db:
        return db.execute(
            "SELECT userid, lastseen FROM voicepresence WHERE serverid = ? AND channelid = ? ORDER BY id ASC",
            (serverid, channelid),
        ).fetchall()


def voicecleanup(serverid: int, channelid: int, threshold: str) -> None:
    with connect("servers") as db:
        db.execute(
            "DELETE FROM voicepresence WHERE serverid = ? AND channelid = ? AND lastseen < ?",
            (serverid, channelid, threshold),
        )


def sendvoicesignal(serverid: int, channelid: int, sender: int, target: int, kind: str, payload: str) -> None:
    with connect("servers") as db:
        db.execute(
            "INSERT INTO voicesignals (serverid, channelid, sender, target, kind, payload) VALUES (?, ?, ?, ?, ?, ?)",
            (serverid, channelid, sender, target, kind, payload),
        )


def getvoicesignals(serverid: int, channelid: int, userid: int, afterid: int):
    with connect("servers") as db:
        return db.execute(
            "SELECT id, sender, target, kind, payload FROM voicesignals WHERE serverid = ? AND channelid = ? AND id > ? AND (target = ? OR target = 0) ORDER BY id ASC",
            (serverid, channelid, afterid, userid),
        ).fetchall()



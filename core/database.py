import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DBROOT = ROOT / "database"


def path(name: str) -> Path:
    DBROOT.mkdir(parents=True, exist_ok=True)
    return DBROOT / f"{name}.db"


def connect(name: str) -> sqlite3.Connection:
    return sqlite3.connect(path(name))


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

    with connect("content") as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL
            )
            """
        )
        count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        if count == 0:
            db.execute("INSERT INTO messages (text) VALUES (?)", ("Hosgeldin",))


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


def createaccount(username: str, passwordhash: str) -> bool:
    try:
        with connect("accounts") as db:
            db.execute(
                "INSERT INTO accounts (username, passwordhash) VALUES (?, ?)",
                (username, passwordhash),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def accountbyname(username: str):
    with connect("accounts") as db:
        return db.execute(
            "SELECT id, username, passwordhash FROM accounts WHERE username = ?",
            (username,),
        ).fetchone()


def accountbyid(accountid: int):
    with connect("accounts") as db:
        return db.execute(
            "SELECT id, username FROM accounts WHERE id = ?",
            (accountid,),
        ).fetchone()

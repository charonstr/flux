import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DBROOT = ROOT / "database"


def path(name: str) -> Path:
    DBROOT.mkdir(parents=True, exist_ok=True)
    return DBROOT / f"{name}.db"


def connect(name: str) -> sqlite3.Connection:
    return sqlite3.connect(path(name))


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


def createaccount(username: str, passwordhash: str) -> bool:
    try:
        with connect("accounts") as db:
            db.execute("INSERT INTO accounts (username, passwordhash) VALUES (?, ?)", (username, passwordhash))
        return True
    except sqlite3.IntegrityError:
        return False


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
    with connect("accounts") as db:
        db.execute("UPDATE accounts SET lastseen = ? WHERE id = ?", (when, accountid))


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


def servercreate(ownerid: int, name: str, avatar: str, visibility: str, joinmode: str, joincode: str) -> int:
    with connect("servers") as db:
        db.execute(
            "INSERT INTO servers (ownerid, name, avatar, visibility, joinmode, joincode) VALUES (?, ?, ?, ?, ?, ?)",
            (ownerid, name, avatar, visibility, joinmode, joincode),
        )
        sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT OR IGNORE INTO members (serverid, userid, roleid, status) VALUES (?, ?, 0, 'active')", (sid, ownerid))
    return sid


def serverbyid(serverid: int):
    with connect("servers") as db:
        return db.execute(
            "SELECT id, ownerid, name, avatar, visibility, joinmode, joincode, visibleperms, writeperms, shareperms FROM servers WHERE id = ?",
            (serverid,),
        ).fetchone()


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

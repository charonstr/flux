import copy
import json
import random
import shutil
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, Response, abort, redirect, render_template, request, send_from_directory, session, url_for
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from core.config import load
from core.casino.blackjack import MANAGER as BLACKJACK
from core.casino.multiplier import MANAGER as MULTIPLIER
from core.casino.roulette import MANAGER as ROULETTE
from core.casino.cs2case import MANAGER as CS2CASE
from core.database import (
    acceptdmrequest,
    acceptrequest,
    accountbyid,
    accountbyname,
    accountsbasic,
    addfile,
    addtext,
    allaccounts,
    arefriends,
    blockedids,
    blockuser,
    conversation,
    createaccount,
    connect,
    dmhistory,
    dmpermission,
    dmpeers,
    friendcount,
    friendids,
    heartbeat,
    isblocked,
    latestentryid,
    markread,
    pendingdmreceived,
    pendingreceived,
    pendingsent,
    rejectrequest,
    rejectdmrequest,
    removefriend,
    requeststatus,
    savevisitor,
    senddmrequest,
    sendvoicesignal,
    sendrequest,
    serveraccept,
    serverbyid,
    servercategories,
    serverchannel,
    serverchannels,
    servercreate,
    servercreatecategory,
    servercreatechannel,
    servercreaterole,
    serverentries,
    serverismember,
    serverjoin,
    serverjoinrequest,
    serverlist,
    servermemberrole,
    servermembers,
    serverpending,
    serverroles,
    serverupdatecategory,
    serverupdatechannel,
    serverupdaterole,
    serverassignrole,
    addserverentry,
    applyledger,
    casinosummary,
    casinoleaderboard,
    casinorichest,
    casinolastgames,
    recordcasinogame,
    claimdailyreward,
    claimcasinoachievement,
    setdmpermission,
    voicecleanup,
    voiceparticipants,
    voiceping,
    getvoicesignals,
    getcasinoaction,
    savecasinoaction,
    setup,
    dailyrewardstate,
    casinoachievementstate,
    unblockuser,
    unreadcount,
    updateavatar,
    updatepassword,
    updateusername,
)
from core.economy import get_balance, initialize_user_economy, spend_gold
from core.fearofabyss_backend import register_fearofabyss_backend
from core.abysslegacy_backend import register_abysslegacy_backend
from core.leveling import add_xp, get_level
from core.texts import language, texts


ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
DMROOT = MEDIA / "dm"
LITERALS_INDEX = ROOT / "data" / "literals_index.json"

IMAGE_MAX = 200 * 1024 * 1024
VIDEO_MAX = 300 * 1024 * 1024
FILE_MAX = 500 * 1024 * 1024
ACTIVE_WINDOW = timedelta(seconds=40)
VOICE_WINDOW = timedelta(seconds=35)
SERVER_IMAGE_MAX = 200 * 1024 * 1024
SERVER_VIDEO_MAX = 300 * 1024 * 1024
SERVER_AUDIO_MAX = 200 * 1024 * 1024
SERVER_FILE_MAX = 500 * 1024 * 1024


def _turkey_tz():
    try:
        return ZoneInfo("Europe/Istanbul")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=3))


TURKEY_TZ = _turkey_tz()

app = Flask(__name__)
app.template_folder = str(ROOT)
app.secret_key = "changeme"
app.permanent_session_lifetime = timedelta(days=30)


def _compute_asset_version() -> str:
    """Return a stable cache-busting token based on critical asset mtimes."""
    candidates = [
        ROOT / "pc" / "js" / "app.js",
        ROOT / "mobile" / "js" / "app.js",
        ROOT / "pc" / "css" / "style.css",
        ROOT / "mobile" / "css" / "style.css",
        ROOT / "pc" / "fearofabyss.html",
        ROOT / "mobile" / "fearofabyss.html",
    ]
    latest = 0
    for p in candidates:
        try:
            latest = max(latest, int(p.stat().st_mtime))
        except OSError:
            continue
    return str(latest or int(time.time()))


ASSET_VERSION = _compute_asset_version()


@app.context_processor
def inject_asset_version():
    return {"asset_v": ASSET_VERSION}


EVENT_LOCK = Lock()
EVENT_VERSIONS: dict[int, int] = defaultdict(int)


def emit(*userids: int) -> None:
    with EVENT_LOCK:
        for uid in userids:
            if uid:
                EVENT_VERSIONS[int(uid)] += 1


def emit_server(serverid: int) -> None:
    members = servermembers(serverid)
    if members:
        uids = [m[0] for m in members]
        emit(*uids)


def eventversion(userid: int) -> int:
    with EVENT_LOCK:
        return int(EVENT_VERSIONS.get(int(userid), 0))


def nowiso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mobileagent(agent: str) -> bool:
    text = (agent or "").lower()
    keys = ["mobile", "android", "iphone", "ipad"]
    return any(key in text for key in keys)


def mobileview() -> bool:
    return mobileagent(request.headers.get("User-Agent", ""))


def viewfile(name: str) -> str:
    return f"mobile/{name}" if mobileview() else f"pc/{name}"


def visitor() -> str:
    token = session.get("token")
    if token:
        return token
    token = str(uuid4())
    session["token"] = token
    return token


def userlanguage() -> str | None:
    current = session.get("language")
    if not current:
        return None
    return language(current)


def currentaccount():
    accountid = session.get("accountid")
    if not accountid:
        return None
    acc = accountbyid(int(accountid))
    if acc:
        heartbeat(acc[0], nowiso())
    return acc


def avatarurl(account) -> str:
    if not account or not account[3]:
        return "/pc/avatar.svg" if not mobileview() else "/mobile/avatar.svg"
    return f"/media/{account[3]}"


def statuslabel(user) -> str:
    last = user[3] if len(user) > 3 else ""
    if not last:
        return "offline"
    try:
        dt = datetime.fromisoformat(last)
    except Exception:
        return "offline"
    if datetime.now(timezone.utc) - dt <= ACTIVE_WINDOW:
        return "active"
    return dt.astimezone(TURKEY_TZ).strftime("%Y-%m-%d %H:%M")


def canchange(account) -> bool:
    last = account[4] if account else ""
    if not last:
        return True
    lastdt = datetime.fromisoformat(last)
    return datetime.now(timezone.utc) - lastdt >= timedelta(days=7)


def savechoice(code: str) -> None:
    lang = language(code)
    session["language"] = lang
    savevisitor(token=visitor(), language=lang, useragent=request.headers.get("User-Agent", "unknown"), ip=request.remote_addr or "unknown")


def smallavatar(raw: str) -> str:
    return f"/media/{raw}" if raw else ("/mobile/avatar.svg" if mobileview() else "/pc/avatar.svg")


def socialcards(accountid: int):
    sent = pendingsent(accountid)
    pending = []
    for rid, sid in pendingreceived(accountid):
        user = accountbyid(sid)
        if user:
            pending.append({"requestid": rid, "id": user[0], "username": user[1], "avatar": smallavatar(user[3])})

    suggestions = []
    for uid, uname, uava, _ in allaccounts(accountid, 18):
        if isblocked(accountid, uid) or isblocked(uid, accountid):
            continue
        status = "none"
        if arefriends(accountid, uid):
            status = "friend"
        elif uid in sent:
            status = "sent"
        elif requeststatus(uid, accountid) == "pending":
            status = "incoming"
        suggestions.append({"id": uid, "username": uname, "avatar": smallavatar(uava), "status": status})
        if len(suggestions) >= 8:
            break

    return suggestions, pending


def navcontext(content: dict, current: str):
    account = currentaccount()
    ctx = {
        "t": content,
        "current": current,
        "username": account[1] if account else None,
        "avatar": avatarurl(account),
        "friendcount": 0,
    }
    if account:
        ctx["friendcount"] = friendcount(account[0])
    return ctx


def literallookup(content: dict) -> dict[str, str]:
    if not LITERALS_INDEX.exists():
        return {}
    try:
        raw = json.loads(LITERALS_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, str] = {}
    for key, source in raw.items():
        source_text = str(source or "").strip()
        if not source_text:
            continue
        target = str(content.get(str(key), source_text))
        out[source_text] = target
    return out


def saveavatar(file, crop: bool) -> str:
    MEDIA.mkdir(parents=True, exist_ok=True)
    ext = Path(secure_filename(file.filename)).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("invalid")
    name = f"{uuid4().hex}{ext}"
    out = MEDIA / name
    file.save(out)
    if crop:
        with Image.open(out) as img:
            size = min(img.width, img.height)
            left = (img.width - size) // 2
            top = (img.height - size) // 2
            cropped = img.crop((left, top, left + size, top + size)).resize((256, 256))
            cropped.save(out)
    return name


def savemedium(file, kind: str) -> tuple[str, int]:
    ext = Path(secure_filename(file.filename)).suffix.lower()
    allow = {
        "image": {".jpg", ".jpeg", ".png", ".webp", ".gif"},
        "video": {".mp4", ".webm", ".mov", ".mkv"},
        "audio": {".mp3", ".wav", ".m4a", ".ogg", ".webm"},
        "file": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    }[kind]
    if ext not in allow:
        raise ValueError("invalid")

    sub = {"image": "images", "video": "videos", "audio": "audios", "file": "files"}[kind]
    folder = DMROOT / sub
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4().hex}{ext}"
    out = folder / name
    file.save(out)
    size = out.stat().st_size

    if kind == "image" and size > IMAGE_MAX:
        out.unlink(missing_ok=True)
        raise ValueError("imglimit")
    if kind == "video" and size > VIDEO_MAX:
        out.unlink(missing_ok=True)
        raise ValueError("vidlimit")
    if kind == "file" and size > FILE_MAX:
        out.unlink(missing_ok=True)
        raise ValueError("filelimit")

    rel = str(Path("dm") / sub / name).replace("\\", "/")
    return rel, size


def dmpanel(meid: int):
    ids = dmpeers(meid)
    for fid in friendids(meid):
        if fid not in ids:
            ids.append(fid)
    peers = []
    for row in accountsbasic(ids):
        convo = conversation(meid, row[0])
        peers.append(
            {
                "id": row[0],
                "username": row[1],
                "avatar": smallavatar(row[2]),
                "status": statuslabel((row[0], row[1], row[2], row[3])),
                "unread": unreadcount(convo, meid),
            }
        )
    return peers


def parseids(items) -> str:
    vals = []
    for v in items:
        if str(v).isdigit():
            vals.append(str(int(v)))
    return ",".join(sorted(set(vals), key=lambda x: int(x)))


def hasserverperm(server, userid: int, key: str) -> bool:
    if not server:
        return False
    if int(server[1]) == int(userid):
        return True
    roleid = servermemberrole(int(server[0]), int(userid))
    if roleid < 0:
        return False
    for rid, _, perms in serverroles(int(server[0])):
        if int(rid) == int(roleid):
            try:
                data = json.loads(perms or "{}")
            except Exception:
                data = {}
            return bool(data.get(key))
    return False


def roleinlist(roleid: int, text: str) -> bool:
    if not text:
        return True
    allowed = {p for p in text.split(",") if p}
    return str(roleid) in allowed


def canchannel(server, channel, userid: int, mode: str) -> bool:
    if int(server[1]) == int(userid):
        return True
    if not serverismember(int(server[0]), int(userid)):
        return False
    roleid = servermemberrole(int(server[0]), int(userid))
    svis, swri, ssha = server[7], server[8], server[9]
    cvis, cwri, csha = channel[5], channel[6], channel[7]
    if mode == "view":
        return roleinlist(roleid, svis) and roleinlist(roleid, cvis)
    if mode == "write":
        return roleinlist(roleid, svis) and roleinlist(roleid, cvis) and roleinlist(roleid, swri) and roleinlist(roleid, cwri)
    if mode == "share":
        return roleinlist(roleid, svis) and roleinlist(roleid, cvis) and roleinlist(roleid, ssha) and roleinlist(roleid, csha)
    return False


def saveservermedia(serverid: int, channelid: int, file) -> tuple[str, int, str]:
    ext = Path(secure_filename(file.filename)).suffix.lower()
    imageext = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    videoext = {".mp4", ".webm", ".mov", ".mkv"}
    audioext = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}
    kind = "file"
    if ext in imageext:
        kind = "image"
    elif ext in videoext:
        kind = "video"
    elif ext in audioext:
        kind = "audio"
    folder = MEDIA / "servers" / str(serverid) / str(channelid)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4().hex}{ext}"
    out = folder / name
    file.save(out)
    size = out.stat().st_size
    if kind == "image" and size > SERVER_IMAGE_MAX:
        out.unlink(missing_ok=True)
        raise ValueError("imglimit")
    if kind == "video" and size > SERVER_VIDEO_MAX:
        out.unlink(missing_ok=True)
        raise ValueError("vidlimit")
    if kind == "audio" and size > SERVER_AUDIO_MAX:
        out.unlink(missing_ok=True)
        raise ValueError("audlimit")
    if kind == "file" and size > SERVER_FILE_MAX:
        out.unlink(missing_ok=True)
        raise ValueError("filelimit")
    return str(Path("servers") / str(serverid) / str(channelid) / name).replace("\\", "/"), size, kind


def candom(meid: int, peer: int) -> bool:
    if arefriends(meid, peer):
        return True
    if dmpermission(meid, peer):
        return True
    ids = dmpeers(meid)
    return peer in ids


register_fearofabyss_backend(
    app,
    request=request,
    redirect=redirect,
    render_template=render_template,
    url_for=url_for,
    connect=connect,
    applyledger=applyledger,
    initialize_user_economy=initialize_user_economy,
    get_balance=get_balance,
    spend_gold=spend_gold,
    userlanguage=userlanguage,
    currentaccount=currentaccount,
    texts=texts,
    navcontext=navcontext,
    viewfile=viewfile,
)

register_abysslegacy_backend(
    app_obj=app,
    request_obj=request,
    redirect_obj=redirect,
    render_template_obj=render_template,
    url_for_obj=url_for,
    connect_obj=connect,
    applyledger_obj=applyledger,
    initialize_user_economy_obj=initialize_user_economy,
    spend_gold_obj=spend_gold,
    userlanguage_obj=userlanguage,
    currentaccount_obj=currentaccount,
    texts_obj=texts,
    navcontext_obj=navcontext,
    viewfile_obj=viewfile,
    accountbyid_obj=accountbyid,
    root_path=ROOT,
)

@app.route("/api/nav")
def apinav():
    me = currentaccount()
    if not me:
        return {"ok": False}
    mine, _ = serverlist(me[0])
    servers = [{"id": s[0], "name": s[1], "avatar": smallavatar(s[2])} for s in mine]
    return {"ok": True, "servers": servers, "avatar": avatarurl(me)}


@app.route("/api/i18n/literals")
def i18nliterals():
    current = userlanguage() or "en"
    content = texts(current)
    return {"ok": True, "lang": current, "map": literallookup(content)}


@app.route("/home")
def home():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
        
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
        
    content = texts(current)
    ctx = navcontext(content, current)
    
    s, p = socialcards(account[0])
    ctx["suggestions"] = s
    ctx["pending"] = p
    dmp = []
    for rid, sid in pendingdmreceived(account[0]):
        u = accountbyid(sid)
        if u:
            dmp.append({"requestid": rid, "id": sid, "username": u[1], "avatar": smallavatar(u[3])})
    ctx["dmpending"] = dmp
    
    return render_template(viewfile("home.html"), **ctx)


@app.route("/")
def root():
    return redirect(url_for("home"))


@app.route("/casino")
def casinohome():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    initialize_user_economy(account[0])
    return render_template(
        viewfile("casino/home.html"),
        **navcontext(content, current),
    )


@app.route("/api/casino/profile")
def apicasinoprofile():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    lvl = get_level(me[0])
    wins, loses, ratio = casinosummary(me[0])
    daily = casinoleaderboard("daily", 5)
    weekly = casinoleaderboard("weekly", 5)
    monthly = casinoleaderboard("monthly", 5)
    richest = casinorichest(5)
    games = casinolastgames(me[0], 10)
    return {
        "ok": True,
        "total_win_amount": wins,
        "total_lose_amount": loses,
        "win_lose_ratio": ratio,
        "daily_top5": daily,
        "weekly_top5": weekly,
        "monthly_top5": monthly,
        "richest_top5": richest,
        "last10_games": games,
        "profile_summary": {
            "total_win_amount": wins,
            "total_lose_amount": loses,
            "win_lose_ratio": ratio,
        },
        "leaderboards": {
            "daily_top5": daily,
            "weekly_top5": weekly,
            "monthly_top5": monthly,
        },
        "level": {
            "level": lvl["level"],
            "xp": lvl["xp"],
            "next_level_xp": lvl["next_level_xp"],
        },
        "profile": {
            "username": me[1],
            "avatar": avatarurl(me),
            "balance": get_balance(me[0]),
        },
    }


@app.route("/casino/blackjack")
def casinoblackjack():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    initialize_user_economy(account[0])
    return render_template(viewfile("casino/blackjack.html"), **navcontext(content, current))


@app.route("/casino/roulette")
def casinoroulette():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    initialize_user_economy(account[0])
    return render_template(viewfile("casino/roulette.html"), **navcontext(content, current))


@app.route("/casino/case")
def casinocasehome():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    initialize_user_economy(account[0])
    return render_template(viewfile("casino/case_home.html"), **navcontext(content, current))


@app.route("/casino/achievements")
def casinoachievements():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    initialize_user_economy(account[0])
    return render_template(viewfile("casino/achievements.html"), **navcontext(content, current))


@app.route("/api/casino/achievements/state")
def apicasinoachievementstate():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    return {"ok": True, **casinoachievementstate(me[0])}


@app.route("/api/casino/achievements/claim", methods=["POST"])
def apicasinoachievementclaim():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    payload = request.get_json(silent=True) or {}
    achievement_key = str(payload.get("achievement_key") or request.form.get("achievement_key") or "").strip().lower()
    if not achievement_key:
        return {"ok": False, "error": "achievement_key_required"}, 400
    result = claimcasinoachievement(me[0], achievement_key)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "claim_failed"), **result.get("state", {})}, 400
    return {"ok": True, "claimed_amount": int(result.get("claimed_amount", 0)), **result.get("state", {})}


@app.route("/casino/case/<caseid>")
def casinocaseopen(caseid: str):
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    if caseid not in {"afet", "kristal"}:
        return redirect(url_for("casinocasehome"))
    content = texts(current)
    initialize_user_economy(account[0])
    return render_template(viewfile("casino/case_open.html"), caseid=caseid, **navcontext(content, current))


def caseconstants(userid: int, caseid: str) -> dict:
    base = CS2CASE.constants(caseid)
    base["cases"] = CS2CASE.list_cases()
    base["balance"] = int(get_balance(userid))
    return base


@app.route("/api/casino/case/state")
def casinocasestate():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    caseid = str(request.args.get("case", "afet") or "afet").strip().lower()
    if caseid not in {"afet", "kristal"}:
        return {"ok": False, "error": "invalid_case"}, 400
    return {
        "ok": True,
        "constants": caseconstants(me[0], caseid),
        "balance": int(get_balance(me[0])),
        "history": CS2CASE.history(me[0], caseid),
        "top_wins": CS2CASE.top_wins(me[0], caseid),
    }


@app.route("/api/casino/case/open", methods=["POST"])
def casinocaseopenapi():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    payload = request.get_json(silent=True) or {}
    caseid = str(payload.get("case", "afet") or "afet").strip().lower()
    if caseid not in {"afet", "kristal"}:
        return {"ok": False, "error": "invalid_case"}, 400
    idem = str(payload.get("idempotency_key", "")).strip()
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400

    def settle_cs2(uid, rid, bet, payout):
        bet_ref = f"cs2case:{rid}:bet"
        payout_ref = f"cs2case:{rid}:payout"
        try:
            with connect("casino/player") as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)", (uid,))
                row = db.execute("SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE user_id = ?", (uid,)).fetchone()
                balance = int(row[0]) if row else 0
                db.execute("UPDATE wallets SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (balance, uid))
                if balance < bet:
                    db.execute("ROLLBACK")
                    return False, "insufficient_balance"
                db.execute("INSERT INTO ledger (user_id, amount, type, description, reference_id) VALUES (?, ?, ?, ?, ?)", (uid, -bet, "cs2case_bet", "cs2 case bet", bet_ref))
                db.execute("INSERT INTO ledger (user_id, amount, type, description, reference_id) VALUES (?, ?, ?, ?, ?)", (uid, payout, "cs2case_payout", "cs2 case payout", payout_ref))
                db.execute("UPDATE wallets SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (payout - bet, uid))
                db.execute("COMMIT")
            return True, ""
        except Exception:
            return False, "settlement_failed"

    ok, data = CS2CASE.open_case(me[0], caseid, idem, settle_cs2)
    if ok and not bool(data.get("idempotent_replay")):
        state = data.get("state", {})
        price = int(CS2CASE.constants(caseid).get("case", {}).get("price", 0))
        payout = int(state.get("payout", 0))
        recordcasinogame(me[0], f"case:{caseid}", payout - price)
        # XP SISTEMI
        xp_amount = max(5, price // 50) + max(0, payout // 100)
        add_xp(me[0], xp_amount, "casino_case", f"case:{caseid}:{idem}")

    code = 200 if ok else 400
    return {
        "ok": ok,
        **data,
        "constants": caseconstants(me[0], caseid),
        "balance": int(get_balance(me[0])),
        "history": CS2CASE.history(me[0], caseid),
        "top_wins": CS2CASE.top_wins(me[0], caseid),
    }, code


@app.route("/casino/cs2case")
def legacycs2page():
    return redirect(url_for("casinocaseopen", caseid="afet"))


def rouletteconstants(userid: int) -> dict:
    balance = int(get_balance(userid))
    base = ROULETTE.constants()
    base["balance"] = balance
    return base


def _jsonpayload() -> dict:
    return request.get_json(silent=True) or {}


def _idem_from(payload: dict, fallback_prefix: str = "") -> str:
    val = str(payload.get("idempotency_key", "") or request.form.get("idempotency_key", "")).strip()
    if val:
        return val
    return f"{fallback_prefix}:{int(time.time() * 1000)}:{uuid4().hex[:8]}" if fallback_prefix else ""


def _casino_action_replay(userid: int, game: str, action: str, idem: str):
    if not idem:
        return None
    replay = getcasinoaction(userid, game, action, idem)
    if not replay:
        return None
    body = dict(replay.get("response") or {})
    body["idempotent_replay"] = True
    return body, int(replay.get("status_code", 200))


def _casino_action_store(userid: int, game: str, action: str, idem: str, status_code: int, body: dict) -> None:
    if not idem:
        return
    payload = dict(body or {})
    savecasinoaction(userid, game, action, idem, int(status_code), payload)


@app.route("/api/casino/roulette/state")
def roulettestate():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    return {"ok": True, "state": ROULETTE.get_state(me[0]), "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}


def _multiplier_settle_atomic(user_id: int, round_id: str, bet_amount: int, payout_amount: int) -> tuple[bool, str]:
    uid = int(user_id)
    bet = int(bet_amount or 0)
    payout = int(payout_amount or 0)
    rid = str(round_id or "").strip()
    if uid <= 0 or not rid or bet <= 0 or payout < 0:
        return False, "invalid_settlement"

    bet_ref = f"multiplier:{rid}:bet"
    payout_ref = f"multiplier:{rid}:payout"
    try:
        with connect("casino/player") as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)", (uid,))
            # Sync wallet from immutable ledger to avoid stale cached balances.
            row = db.execute("SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE user_id = ?", (uid,)).fetchone()
            balance = int(row[0]) if row else 0
            db.execute(
                "UPDATE wallets SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (balance, uid),
            )
            if balance < bet:
                db.execute("ROLLBACK")
                return False, "insufficient_balance"
            db.execute(
                "INSERT INTO ledger (user_id, amount, type, description, reference_id) VALUES (?, ?, ?, ?, ?)",
                (uid, -bet, "multiplier_bet", "multiplier bet", bet_ref),
            )
            db.execute(
                "INSERT INTO ledger (user_id, amount, type, description, reference_id) VALUES (?, ?, ?, ?, ?)",
                (uid, payout, "multiplier_payout", "multiplier payout", payout_ref),
            )
            db.execute(
                "UPDATE wallets SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (payout - bet, uid),
            )
            db.execute("COMMIT")
        return True, ""
    except sqlite3.IntegrityError:
        # Idempotent replay safety: if both ledger rows exist, treat as success.
        with connect("casino/player") as db:
            b = db.execute(
                "SELECT 1 FROM ledger WHERE user_id = ? AND type = ? AND reference_id = ?",
                (uid, "multiplier_bet", bet_ref),
            ).fetchone()
            p = db.execute(
                "SELECT 1 FROM ledger WHERE user_id = ? AND type = ? AND reference_id = ?",
                (uid, "multiplier_payout", payout_ref),
            ).fetchone()
        if b and p:
            return True, ""
        return False, "settlement_integrity_error"
    except Exception:
        return False, "settlement_failed"


@app.route("/api/casino/roulette/start", methods=["POST"])
def roulettestart():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = _jsonpayload()
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    replay = _casino_action_replay(me[0], "roulette", "start", idem)
    if replay:
        return replay
    initialize_user_economy(me[0])
    prev = ROULETTE.get_state(me[0])
    prev_total_bet = int(prev.get("total_bet", 0) or 0)
    prev_round_id = str(prev.get("round_id", "") or "")
    prev_state = str(prev.get("state", "") or "")
    if prev_total_bet > 0 and prev_round_id and prev_state in {"betting_open", "betting_locked"}:
        applyledger(me[0], prev_total_bet, "roulette_refund", "roulette round cancelled refund", f"roulette:{prev_round_id}:cancel_refund")
    response = {"ok": True, "state": ROULETTE.start_round(me[0]), "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}
    _casino_action_store(me[0], "roulette", "start", idem, 200, response)
    return response


@app.route("/casino/multiplier")
def casinomultiplier():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    initialize_user_economy(account[0])
    return render_template(viewfile("casino/multiplier.html"), **navcontext(content, current))


def multiplierconstants(userid: int) -> dict:
    base = MULTIPLIER.constants()
    limits = blackjacklimits(userid)
    base["min_bet"] = int(limits.get("min_bet", base.get("min_bet", 100)))
    base["max_bet"] = int(limits.get("max_bet", base.get("max_bet", 0)))
    base["level_cap"] = int(limits.get("level_cap", 0))
    base["level"] = int(limits.get("level", 1))
    base["balance"] = int(limits.get("balance", get_balance(userid)))
    return base


@app.route("/casino/multiplier/state")
def multiplierstate():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    return {
        "ok": True,
        "state": MULTIPLIER.state(me[0]),
        "constants": multiplierconstants(me[0]),
        "balance": int(get_balance(me[0])),
    }


@app.route("/casino/multiplier/play", methods=["POST"])
def multiplierplay():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    payload = _jsonpayload()
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    try:
        bet_amount = int(payload.get("bet_amount", 0) or 0)
    except Exception:
        bet_amount = 0
    limits = multiplierconstants(me[0])
    min_bet = int(limits.get("min_bet", 100))
    max_bet = int(limits.get("max_bet", 0))
    if bet_amount < min_bet:
        return {"ok": False, "error": "invalid_bet_min", "constants": limits, "balance": int(get_balance(me[0]))}, 400
    if bet_amount > max_bet:
        return {"ok": False, "error": "invalid_bet_max", "constants": limits, "balance": int(get_balance(me[0]))}, 400

    ok, data = MULTIPLIER.play(me[0], bet_amount, idem, _multiplier_settle_atomic)
    if ok and not bool(data.get("idempotent_replay")):
        state = data.get("state", {})
        bet = int(state.get("bet_amount", 0) or 0)
        payout = int(state.get("payout_amount", 0) or 0)
        recordcasinogame(me[0], "multiplier", payout - bet)
        # XP SISTEMI
        xp_amount = max(5, bet // 50) + max(0, payout // 100)
        add_xp(me[0], xp_amount, "casino_multiplier", f"multiplier:{idem}")

    code = 200 if ok else 400
    return {"ok": ok, **data, "constants": multiplierconstants(me[0]), "balance": int(get_balance(me[0]))}, code


@app.route("/casino/multiplier/history")
def multiplierhistory():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    return {"ok": True, "rows": MULTIPLIER.history(me[0], 10), "balance": int(get_balance(me[0]))}


@app.route("/api/casino/roulette/place", methods=["POST"])
def rouletteplace():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = _jsonpayload()
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    bet_type = str(payload.get("bet_type", "")).strip()
    selection = payload.get("selection", [])
    if not isinstance(selection, list):
        selection = []
    try:
        amount = int(payload.get("amount", 0) or 0)
    except Exception:
        amount = 0
    if amount > 0 and int(get_balance(me[0])) < amount:
        return {"ok": False, "error": "insufficient_balance", "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}, 400
    before = ROULETTE.get_state(me[0])
    before_total = int(before.get("total_bet", 0) or 0)
    ok, data = ROULETTE.place_bet(me[0], bet_type, selection, amount, idem)
    if ok:
        state = data.get("state", {})
        round_id = str(state.get("round_id", "") or "")
        after_total = int(state.get("total_bet", 0) or 0)
        delta = max(0, after_total - before_total)
        if delta > 0 and round_id:
            debit_ref = f"roulette:{round_id}:place:{idem}"
            if not applyledger(me[0], -delta, "roulette_bet", "roulette bet placed", debit_ref):
                ROULETTE.undo(me[0])
                rollback_state = ROULETTE.get_state(me[0])
                return {"ok": False, "error": "bet_debit_failed", "state": rollback_state, "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}, 400
    code = 200 if ok else 400
    return {"ok": ok, **data, "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}, code


@app.route("/api/casino/roulette/undo", methods=["POST"])
def rouletteundo():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = _jsonpayload()
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    replay = _casino_action_replay(me[0], "roulette", "undo", idem)
    if replay:
        return replay
    before = ROULETTE.get_state(me[0])
    before_total = int(before.get("total_bet", 0) or 0)
    round_id = str(before.get("round_id", "") or "")
    ok, data = ROULETTE.undo(me[0])
    if ok:
        after_total = int((data.get("state") or {}).get("total_bet", 0) or 0)
        refund = max(0, before_total - after_total)
        if refund > 0 and round_id:
            applyledger(me[0], refund, "roulette_refund", "roulette undo refund", f"roulette:{round_id}:undo:{idem}")
    code = 200 if ok else 400
    response = {"ok": ok, **data, "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}
    _casino_action_store(me[0], "roulette", "undo", idem, code, response)
    return response, code


@app.route("/api/casino/roulette/clear", methods=["POST"])
def rouletteclear():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = _jsonpayload()
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    replay = _casino_action_replay(me[0], "roulette", "clear", idem)
    if replay:
        return replay
    before = ROULETTE.get_state(me[0])
    refund = int(before.get("total_bet", 0) or 0)
    round_id = str(before.get("round_id", "") or "")
    ok, data = ROULETTE.clear(me[0])
    if ok and refund > 0 and round_id:
        applyledger(me[0], refund, "roulette_refund", "roulette clear refund", f"roulette:{round_id}:clear:{idem}")
    code = 200 if ok else 400
    response = {"ok": ok, **data, "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}
    _casino_action_store(me[0], "roulette", "clear", idem, code, response)
    return response, code


@app.route("/api/casino/roulette/lock", methods=["POST"])
def roulettelock():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = _jsonpayload()
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    ok, data = ROULETTE.lock_bets(me[0], idem)
    if not ok:
        return {"ok": False, **data, "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}, 400
    state = data.get("state", {})
    total_bet = int(state.get("total_bet", 0) or 0)
    if total_bet <= 0:
        return {"ok": False, "error": "no_bets", "state": state, "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}, 400
    return {"ok": True, "state": state, "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}


@app.route("/api/casino/roulette/spin", methods=["POST"])
def roulettespin():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = _jsonpayload()
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    ok, data = ROULETTE.spin(me[0], idem)
    code = 200 if ok else 400
    return {"ok": ok, **data, "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}, code


@app.route("/api/casino/roulette/settle", methods=["POST"])
def roulettesettle():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    payload = _jsonpayload()
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    replay = _casino_action_replay(me[0], "roulette", "settle", idem)
    if replay:
        return replay
    ok, data = ROULETTE.settle(me[0])
    if not ok:
        response = {"ok": False, **data, "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}
        _casino_action_store(me[0], "roulette", "settle", idem, 400, response)
        return response, 400
    state = data.get("state", {})
    round_id = str(state.get("round_id", "") or "")
    total_payout = int(data.get("total_payout", 0) or 0)
    total_stake = int(data.get("total_stake", 0) or 0)
    net_delta = int(data.get("net_delta", 0) or 0)
    
    if total_payout > 0:
        applyledger(me[0], total_payout, "roulette_payout", "roulette payout", f"roulette:{round_id}:payout")
    recordcasinogame(me[0], "roulette", net_delta if total_stake > 0 else 0)
    
    # XP SISTEMI
    if total_stake > 0:
        xp_amount = max(5, total_stake // 50) + max(0, total_payout // 100)
        add_xp(me[0], xp_amount, "casino_roulette", f"roulette:{round_id}")
        
    state["settled"] = True
    response = {"ok": True, **data, "state": state, "constants": rouletteconstants(me[0]), "balance": int(get_balance(me[0]))}
    _casino_action_store(me[0], "roulette", "settle", idem, 200, response)
    return response


def blackjacklimits(userid: int) -> dict:
    level = int(get_level(userid).get("level", 1))
    balance = int(get_balance(userid))
    min_bet = 100
    level_cap = 500 + max(0, level - 1) * 100
    max_bet = min(level_cap, balance) if balance >= min_bet else 0
    return {
        "min_bet": min_bet,
        "max_bet": int(max_bet),
        "level_cap": int(level_cap),
        "balance": balance,
        "level": level,
    }


def blackjacksettle(userid: int, state: dict) -> dict:
    if not state:
        return {}
    if str(state.get("phase", "")) != "finished":
        return state
    if bool(state.get("settled")):
        return state
    round_id = str(state.get("round_id", "") or "")
    bet = int(state.get("bet", 0) or 0)
    result = str(state.get("result", "") or "")
    if not round_id or bet <= 0:
        return state

    payout = 0
    net_delta = 0
    if result == "push":
        payout = bet
        net_delta = 0
    elif result == "win":
        payout = bet * 2
        net_delta = bet
    elif result == "blackjack":
        payout = (bet * 5) // 2
        net_delta = payout - bet
    else:
        payout = 0
        net_delta = -bet

    if payout > 0:
        applyledger(userid, payout, "blackjack_payout", f"blackjack {result}", f"blackjack:{round_id}:payout")
    recordcasinogame(userid, "blackjack", net_delta)
    
    # XP SISTEMI
    xp_amount = max(5, bet // 50) + max(0, payout // 100)
    add_xp(userid, xp_amount, "casino_blackjack", f"blackjack:{round_id}:xp")
    
    return BLACKJACK.mark_settled(userid)


@app.route("/api/casino/blackjack/state")
def blackjackstate():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    state = blackjacksettle(me[0], BLACKJACK.get_state(me[0]))
    return {"ok": True, "state": state, "limits": blackjacklimits(me[0])}


@app.route("/api/casino/blackjack/new", methods=["POST"])
def blackjacknew():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    payload = request.get_json(silent=True) or {}
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    replay = _casino_action_replay(me[0], "blackjack", "new", idem)
    if replay:
        return replay
    current = BLACKJACK.get_state(me[0]) or {}
    phase = str(current.get("phase", "idle") or "idle")
    if phase in {"player_turn", "dealer_turn"}:
        return {"ok": False, "error": "round_in_progress", "limits": blackjacklimits(me[0]), "state": current}, 409
    bet_raw = payload.get("bet", request.form.get("bet", "0"))
    try:
        bet = int(bet_raw or 0)
    except Exception:
        bet = 0
    limits = blackjacklimits(me[0])
    if bet < limits["min_bet"]:
        response = {"ok": False, "error": "invalid_bet_min", "limits": limits}
        _casino_action_store(me[0], "blackjack", "new", idem, 400, response)
        return response, 400
    if bet > limits["max_bet"]:
        response = {"ok": False, "error": "invalid_bet_max", "limits": limits}
        _casino_action_store(me[0], "blackjack", "new", idem, 400, response)
        return response, 400
    if not applyledger(me[0], -bet, "blackjack_bet", "blackjack bet", f"blackjack:bet:{idem}"):
        response = {"ok": False, "error": "bet_failed", "limits": blackjacklimits(me[0])}
        _casino_action_store(me[0], "blackjack", "new", idem, 400, response)
        return response, 400
    ok, state = BLACKJACK.start_round(me[0], bet)
    if not ok:
        applyledger(me[0], bet, "blackjack_refund", "blackjack refund", f"blackjack:refund:{idem}")
        response = {"ok": False, **state, "limits": limits}
        _casino_action_store(me[0], "blackjack", "new", idem, 400, response)
        return response, 400
    state = blackjacksettle(me[0], state)
    response = {"ok": True, "state": state, "limits": blackjacklimits(me[0])}
    _casino_action_store(me[0], "blackjack", "new", idem, 200, response)
    return response


@app.route("/api/casino/blackjack/hit", methods=["POST"])
def blackjackhit():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    payload = request.get_json(silent=True) or {}
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    replay = _casino_action_replay(me[0], "blackjack", "hit", idem)
    if replay:
        return replay
    ok, payload = BLACKJACK.hit(me[0])
    if not ok:
        response = {"ok": False, **payload, "limits": blackjacklimits(me[0])}
        _casino_action_store(me[0], "blackjack", "hit", idem, 400, response)
        return response, 400
    payload = blackjacksettle(me[0], payload)
    response = {"ok": True, "state": payload, "limits": blackjacklimits(me[0])}
    _casino_action_store(me[0], "blackjack", "hit", idem, 200, response)
    return response


@app.route("/api/casino/blackjack/stand", methods=["POST"])
def blackjackstand():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    payload = request.get_json(silent=True) or {}
    idem = _idem_from(payload)
    if not idem:
        return {"ok": False, "error": "missing_idempotency"}, 400
    replay = _casino_action_replay(me[0], "blackjack", "stand", idem)
    if replay:
        return replay
    ok, payload = BLACKJACK.stand(me[0])
    if not ok:
        response = {"ok": False, **payload, "limits": blackjacklimits(me[0])}
        _casino_action_store(me[0], "blackjack", "stand", idem, 400, response)
        return response, 400
    payload = blackjacksettle(me[0], payload)
    response = {"ok": True, "state": payload, "limits": blackjacklimits(me[0])}
    _casino_action_store(me[0], "blackjack", "stand", idem, 200, response)
    return response


@app.route("/level")
def levelinfo():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    data = get_level(me[0])
    return {"ok": True, "level": data["level"], "xp": data["xp"], "next_level_xp": data["next_level_xp"]}


@app.route("/level/xp", methods=["POST"])
def leveladdxp():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    internal_key = request.headers.get("X-Internal-Key", "")
    if not internal_key or internal_key != app.secret_key:
        return {"ok": False, "error": "forbidden"}, 403
    payload = request.get_json(silent=True) or {}
    amount = int(payload.get("amount", 0) or 0)
    reason = str(payload.get("reason", "") or "").strip()
    reference_id = str(payload.get("reference_id", "") or "").strip()
    idempotency_key = str(payload.get("idempotency_key", "") or "").strip()
    if amount <= 0 or not reason:
        return {"ok": False, "error": "invalid_payload"}, 400
    ref = reference_id or idempotency_key or None
    result = add_xp(me[0], amount, reason, ref)
    return {
        "ok": True,
        "applied": result["applied"],
        "level": result["level"],
        "xp": result["xp"],
        "next_level_xp": result["next_level_xp"],
    }


@app.route("/rewards/daily")
def rewardsdaily():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    return {"ok": True, **dailyrewardstate(me[0])}


@app.route("/rewards/daily/claim", methods=["POST"])
def rewardsdailyclaim():
    me = currentaccount()
    if not me:
        return {"ok": False, "error": "unauthorized"}, 401
    initialize_user_economy(me[0])
    result = claimdailyreward(me[0])
    if not result.get("ok"):
        return result, 400
    return {
        "ok": True,
        "claimed_amount": result["claimed_amount"],
        "balance": get_balance(me[0]),
        **result["state"],
    }


@app.route("/choose", methods=["GET", "POST"])
def choose():
    if request.method == "POST":
        savechoice(request.form.get("language", "en"))
        if not currentaccount():
            return redirect(url_for("login"))
        return redirect(url_for("home"))
    current = userlanguage() or "en"
    return render_template(viewfile("language.html"), t=texts(current), current=current)


@app.route("/set/<code>")
def setlanguage(code: str):
    savechoice(code)
    if not currentaccount():
        return redirect(url_for("login"))
    return redirect(url_for("home"))


@app.route("/register", methods=["GET", "POST"])
def register():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    content = texts(current)
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3:
            error = content.get("erroruser", "Username must be at least 3 characters")
        elif len(password) < 6:
            error = content.get("errorpass", "Password must be at least 6 characters")
        else:
            created = createaccount(username, generate_password_hash(password))
            if not created:
                error = content.get("errorexists", "This username already exists")
            else:
                session["accountid"] = accountbyname(username)[0]
                return redirect(url_for("home"))
    return render_template(viewfile("register.html"), error=error, **navcontext(content, current))


@app.route("/login", methods=["GET", "POST"])
def login():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    content = texts(current)
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "1"
        account = accountbyname(username)
        if not account or not check_password_hash(account[2], password):
            error = content.get("errorlogin", "Username or password is incorrect")
        else:
            session["accountid"] = account[0]
            session.permanent = remember
            heartbeat(account[0], nowiso())
            return redirect(url_for("home"))
    return render_template(viewfile("login.html"), error=error, **navcontext(content, current))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))

    content = texts(current)
    error = ""
    success = ""
    if request.method == "POST":
        newname = request.form.get("username", "").strip()
        crop = request.form.get("crop", "0") == "1"
        file = request.files.get("avatar")
        if newname and newname != account[1]:
            if not canchange(account):
                error = content.get("errorrenamewait", "You can change username once every 7 days")
            elif len(newname) < 3:
                error = content.get("erroruser", "Username must be at least 3 characters")
            elif not updateusername(account[0], newname, nowiso()):
                error = content.get("errorexists", "This username already exists")
        if not error and file and file.filename:
            try:
                updateavatar(account[0], saveavatar(file, crop))
            except Exception:
                error = content.get("erroravatar", "Avatar upload failed")
        if not error:
            success = content.get("saved", "Saved")
    return render_template(viewfile("profile.html"), error=error, success=success, canchangeusername=canchange(account), **navcontext(content, current))


@app.route("/friends")
def friends():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    rows = accountsbasic(friendids(account[0]))
    items = [{"id": r[0], "username": r[1], "avatar": smallavatar(r[2])} for r in rows]
    preq = pendingreceived(account[0])
    sender_ids = [sid for _, sid in preq]
    sender_rows = accountsbasic(sender_ids) if sender_ids else []
    sender_map = {int(r[0]): r for r in sender_rows}
    pending = []
    for rid, sid in preq:
        row = sender_map.get(int(sid))
        if row:
            pending.append({"requestid": rid, "id": row[0], "username": row[1], "avatar": smallavatar(row[2])})
    return render_template(viewfile("friends.html"), friends=items, pending=pending, **navcontext(content, current))


@app.route("/friendships")
def friendships():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    rows = accountsbasic(blockedids(account[0]))
    items = [{"id": r[0], "username": r[1], "avatar": smallavatar(r[2])} for r in rows]
    return render_template(viewfile("friendships.html"), blocked=items, **navcontext(content, current))


@app.route("/settings")
def settingspage():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    return render_template(viewfile("settings.html"), **navcontext(content, current))


@app.route("/sitesettings")
def sitesettings():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    return render_template(viewfile("sitesettings.html"), **navcontext(content, current))


@app.route("/privacy")
def privacy():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    return render_template(viewfile("privacy.html"), **navcontext(content, current))


@app.route("/changepassword", methods=["GET", "POST"])
def changepassword():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    error = ""
    success = ""
    if request.method == "POST":
        old = request.form.get("oldpassword", "")
        new = request.form.get("newpassword", "")
        confirm = request.form.get("confirmpassword", "")
        if not check_password_hash(account[2], old):
            error = content.get("errorold", "Old password is incorrect")
        elif len(new) < 6:
            error = content.get("errorpass", "Password must be at least 6 characters")
        elif new != confirm:
            error = content.get("errormatch", "Passwords do not match")
        else:
            updatepassword(account[0], generate_password_hash(new))
            success = content.get("saved", "Saved")
    return render_template(viewfile("changepassword.html"), error=error, success=success, **navcontext(content, current))


@app.route("/dm")
def dmhome():
    dmerror = request.args.get("error", "")
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    account = currentaccount()
    if not account:
        return redirect(url_for("login"))
    content = texts(current)
    peers = dmpanel(account[0])
    if dmerror:
        dmerror = content.get(dmerror, dmerror)
    return render_template(viewfile("dm.html"), peers=peers, messages=[], peer=None, error=dmerror, lastid=0, **navcontext(content, current))


@app.route("/dm/<int:peer>", methods=["GET", "POST"])
def dmchat(peer: int):
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    if me[0] == peer or not candom(me[0], peer):
        return redirect(url_for("dmhome", error="errorfriendonly"))

    content = texts(current)
    err = ""
    convid = conversation(me[0], peer)

    if request.method == "POST":
        text = request.form.get("text", "").strip()
        upload = request.files.get("file")
        voice = request.files.get("voice")
        try:
            if text:
                addtext(convid, me[0], text)
                emit(me[0], peer)
            if upload and upload.filename:
                ext = Path(secure_filename(upload.filename)).suffix.lower()
                imageext = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
                videoext = {".mp4", ".webm", ".mov", ".mkv"}
                fileext = {".zip", ".rar", ".7z", ".tar", ".gz"}
                if ext in imageext:
                    rel, size = savemedium(upload, "image")
                    addfile(convid, me[0], "image", rel, size)
                    emit(me[0], peer)
                elif ext in videoext:
                    rel, size = savemedium(upload, "video")
                    addfile(convid, me[0], "video", rel, size)
                    emit(me[0], peer)
                elif ext in fileext:
                    rel, size = savemedium(upload, "file")
                    addfile(convid, me[0], "file", rel, size)
                    emit(me[0], peer)
                else:
                    raise ValueError("invalid")
            if voice and voice.filename:
                rel, size = savemedium(voice, "audio")
                addfile(convid, me[0], "audio", rel, size)
                emit(me[0], peer)
        except ValueError as ex:
            if str(ex) == "imglimit":
                err = content.get("errorimglimit", "Image cannot be larger than 200MB")
            elif str(ex) == "vidlimit":
                err = content.get("errorvidlimit", "Video cannot be larger than 300MB")
            elif str(ex) == "filelimit":
                err = content.get("errorfilelimit", "Archive cannot be larger than 500MB")
            else:
                err = content.get("errorupload", "Upload failed")

    markread(convid, me[0], nowiso())
    history = dmhistory(convid)
    p = accountbyid(peer)
    pstatus = "offline"
    if p:
        pstatus = statuslabel((p[0], p[1], p[3], p[5]))
    peerobj = {"id": p[0], "username": p[1], "avatar": smallavatar(p[3]), "status": pstatus} if p else None
    peers = dmpanel(me[0])
    return render_template(
        viewfile("dm.html"),
        peers=peers,
        peer=peerobj,
        messages=history,
        myid=me[0],
        error=err,
        convid=convid,
        lastid=latestentryid(convid),
        **navcontext(content, current),
    )


@app.route("/dm/stream/<int:peer>")
def dmstream(peer: int):
    me = currentaccount()
    if not me or me[0] == peer or not candom(me[0], peer):
        return Response("", status=403)

    convid = conversation(me[0], peer)
    last = int(request.args.get("last", "0"))
    if last <= 0:
        last = latestentryid(convid)

    def gen():
        nonlocal last
        idle = 0
        while idle < 55:
            current = latestentryid(convid)
            if current > last:
                last = current
                markread(convid, me[0], nowiso())
                payload = json.dumps({"type": "update", "last": last})
                yield f"data: {payload}\n\n"
                idle = 0
            else:
                idle += 1
                yield "data: {\"type\":\"ping\"}\n\n"
            time.sleep(1)

    return Response(gen(), mimetype="text/event-stream")


@app.route("/presence/ping", methods=["POST"])
def presenceping():
    me = currentaccount()
    if me:
        heartbeat(me[0], nowiso())
    return {"ok": True}


@app.route("/events/stream")
def eventstream():
    me = currentaccount()
    if not me:
        return Response("", status=401)
    uid = int(me[0])
    last = int(request.args.get("last", "0"))
    current = eventversion(uid)
    if last <= 0:
        last = current

    def gen():
        nonlocal last
        idle = 0
        while idle < 55:
            cur = eventversion(uid)
            if cur > last:
                last = cur
                payload = json.dumps({"type": "refresh", "version": cur})
                yield f"data: {payload}\n\n"
                idle = 0
            else:
                idle += 1
                yield "data: {\"type\":\"ping\"}\n\n"
            time.sleep(1)

    return Response(gen(), mimetype="text/event-stream")


@app.route("/social/request/<int:target>", methods=["POST"])
def socialrequest(target: int):
    me = currentaccount()
    if me and me[0] != target and not isblocked(me[0], target) and not isblocked(target, me[0]) and not arefriends(me[0], target):
        sendrequest(me[0], target)
        emit(me[0], target)
    return redirect(url_for("home"))


@app.route("/social/revoke/<int:target>", methods=["POST"])
def socialrevoke(target: int):
    me = currentaccount()
    if me:
        from core.database import connect
        with connect("social") as db:
            db.execute("DELETE FROM friend_requests WHERE senderid = ? AND receiverid = ?", (me[0], target))
        emit(me[0], target)
    return redirect(url_for("home"))


@app.route("/social/accept/<int:reqid>", methods=["POST"])
def socialaccept(reqid: int):
    me = currentaccount()
    if me:
        row = pendingreceived(me[0])
        sender = 0
        for rid, sid in row:
            if int(rid) == int(reqid):
                sender = int(sid)
                break
        acceptrequest(reqid, me[0])
        emit(me[0], sender)
    return redirect(url_for("home"))


@app.route("/social/reject/<int:reqid>", methods=["POST"])
def socialreject(reqid: int):
    me = currentaccount()
    if me:
        row = pendingreceived(me[0])
        sender = 0
        for rid, sid in row:
            if int(rid) == int(reqid):
                sender = int(sid)
                break
        rejectrequest(reqid, me[0])
        emit(me[0], sender)
    return redirect(url_for("home"))


@app.route("/social/remove/<int:target>", methods=["POST"])
def socialremove(target: int):
    me = currentaccount()
    if me and me[0] != target:
        removefriend(me[0], target)
        emit(me[0], target)
    return redirect(url_for("home"))


@app.route("/social/block/<int:target>", methods=["POST"])
def socialblock(target: int):
    me = currentaccount()
    if me and me[0] != target:
        blockuser(me[0], target)
        emit(me[0], target)
    return redirect(url_for("home"))


@app.route("/social/unblock/<int:target>", methods=["POST"])
def socialunblock(target: int):
    me = currentaccount()
    if me and me[0] != target:
        unblockuser(me[0], target)
        emit(me[0], target)
    return redirect(url_for("friendships"))


@app.route("/dm/request/accept/<int:reqid>", methods=["POST"])
def dmrequestaccept(reqid: int):
    me = currentaccount()
    if me:
        sender = 0
        for rid, sid in pendingdmreceived(me[0]):
            if int(rid) == int(reqid):
                sender = int(sid)
                break
        acceptdmrequest(reqid, me[0])
        emit(me[0], sender)
    return redirect(url_for("home"))


@app.route("/dm/request/reject/<int:reqid>", methods=["POST"])
def dmrequestreject(reqid: int):
    me = currentaccount()
    if me:
        sender = 0
        for rid, sid in pendingdmreceived(me[0]):
            if int(rid) == int(reqid):
                sender = int(sid)
                break
        rejectdmrequest(reqid, me[0])
        emit(me[0], sender)
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.pop("accountid", None)
    session.permanent = False
    return redirect(url_for("login"))


@app.route("/media/<path:filename>")
def media(filename: str):
    resp = send_from_directory(MEDIA, filename)
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/assets/<path:filename>")
def projectassets(filename: str):
    resp = send_from_directory(ROOT / "assets", filename)
    resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return resp


@app.route("/<zone>/<path:filename>")
def assets(zone: str, filename: str):
    if zone not in {"pc", "mobile"}:
        abort(404)
    resp = send_from_directory(ROOT / zone, filename)
    ext = Path(filename).suffix.lower()
    if ext in {".js", ".css"}:
        resp.headers["Cache-Control"] = "public, max-age=3600"
    elif ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".woff", ".woff2", ".ttf"}:
        resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    else:
        resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


def run() -> None:
    setup()
    settings = load()
    app.secret_key = settings["secret"]
    app.run(host=settings["host"], port=settings["port"], debug=settings["debug"], threaded=True)


@app.route("/dm/start", methods=["POST"])
def dmstart():
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))

    peerid = request.form.get("peerid", "").strip()
    username = request.form.get("username", "").strip()

    target = None
    if peerid.isdigit():
        target = int(peerid)
    elif username:
        user = accountbyname(username)
        if user:
            target = int(user[0])

    if not target or target == me[0]:
        return redirect(url_for("dmhome", error="errorusernotfound"))
    if not candom(me[0], target):
        senddmrequest(me[0], target)
        emit(me[0], target)
        return redirect(url_for("dmhome", error="dmsentrequest"))
    return redirect(url_for("dmchat", peer=target))


@app.route("/servers", methods=["GET", "POST"])
def servers():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    content = texts(current)
    error = ""
    if request.method == "POST":
        mode = request.form.get("mode", "create")
        if mode == "create":
            name = request.form.get("name", "").strip()
            visibility = request.form.get("visibility", "public")
            joinmode = request.form.get("joinmode", "open")
            code = request.form.get("joincode", "").strip()
            if len(name) < 2:
                error = content.get("errorservername", "Server name is too short")
            else:
                avatar = ""
                file = request.files.get("avatar")
                if file and file.filename:
                    try:
                        avatar = saveavatar(file, True)
                    except Exception:
                        avatar = ""
                sid = servercreate(me[0], name, avatar, visibility, joinmode, code)
                emit(me[0])
                return redirect(url_for("serverdetail", serverid=sid))
        if mode == "join":
            code = request.form.get("joincode", "").strip()
            sid = request.form.get("serverid", "").strip()
            target = None
            if sid.isdigit():
                target = serverbyid(int(sid))
            elif code:
                from core.database import connect

                with connect("servers") as db:
                    target = db.execute(
                        "SELECT id, ownerid, name, avatar, visibility, joinmode, joincode, visibleperms, writeperms, shareperms FROM servers WHERE lower(joincode) = lower(?)",
                        (code,),
                    ).fetchone()
            if not target:
                error = content.get("errorservernotfound", "Server not found")
            else:
                if target[5] == "approval":
                    serverjoinrequest(target[0], me[0])
                    emit_server(target[0])
                else:
                    serverjoin(target[0], me[0])
                    emit_server(target[0])
                return redirect(url_for("serverdetail", serverid=target[0]))
    mine, publics = serverlist(me[0])
    return render_template(viewfile("servers.html"), mine=mine, publics=publics, error=error, **navcontext(content, current))


# --- DAVET LİNKİ (URL) İLE SUNUCUYA KATILMA ROTASI ---
@app.route("/join/<code>", methods=["GET", "POST"])
def join_by_code(code: str):
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    content = texts(current)

    from core.database import connect
    with connect("servers") as db:
        target = db.execute(
            "SELECT id, name, avatar, joinmode FROM servers WHERE lower(joincode) = lower(?)",
            (code,),
        ).fetchone()

    if not target:
        return redirect(url_for("servers"))

    if request.method == "POST":
        action = request.form.get("action", "").strip().lower()
        if action != "join":
            return redirect(url_for("servers"))
        if not serverismember(target[0], me[0]):
            if target[3] == "approval":
                serverjoinrequest(target[0], me[0])
                emit_server(target[0])
            else:
                serverjoin(target[0], me[0])
                emit_server(target[0])
        return redirect(url_for("serverdetail", serverid=target[0]))

    return render_template(
        viewfile("joinconfirm.html"),
        invitecode=code,
        server={"id": target[0], "name": target[1], "avatar": smallavatar(target[2]), "joinmode": target[3]},
        **navcontext(content, current),
    )


@app.route("/servers/<int:serverid>")
def serverdetail(serverid: int):
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    content = texts(current)
    server = serverbyid(serverid)
    if not server:
        return redirect(url_for("servers"))
    if not serverismember(serverid, me[0]) and server[4] != "public":
        return redirect(url_for("servers"))
    pending = []
    roles = serverroles(serverid)
    categories = servercategories(serverid)
    channels = serverchannels(serverid)
    members = []
    for uid, roleid, status in servermembers(serverid):
        acc = accountbyid(uid)
        if acc:
            members.append({"id": uid, "username": acc[1], "avatar": smallavatar(acc[3]), "roleid": roleid, "status": status})
    if server[1] == me[0]:
        pending = []
        for j in serverpending(serverid):
            u = accountbyid(j[1])
            if u:
                pending.append({"joinid": j[0], "id": u[0], "username": u[1], "avatar": smallavatar(u[3])})
    return render_template(
        viewfile("serverdetail.html"),
        server=server,
        pending=pending,
        roles=roles,
        categories=categories,
        channels=channels,
        members=members,
        canmanageroles=hasserverperm(server, me[0], "manageroles"),
        canmanagechannels=hasserverperm(server, me[0], "managechannels"),
        myid=me[0],
        **navcontext(content, current),
    )


@app.route("/servers/accept/<int:joinid>", methods=["POST"])
def serverjoinaccept(joinid: int):
    me = currentaccount()
    if me:
        serveraccept(joinid, me[0])
        emit(me[0])
    return redirect(url_for("servers"))


@app.route("/servers/reject/<int:joinid>", methods=["POST"])
def serverjoinreject(joinid: int):
    me = currentaccount()
    if me:
        from core.database import serverreject

        serverreject(joinid, me[0])
        emit(me[0])
    return redirect(url_for("servers"))


@app.route("/servers/<int:serverid>/leave", methods=["POST"])
def serverleave(serverid: int):
    me = currentaccount()
    if me:
        from core.database import connect
        with connect("servers") as db:
            owner = db.execute("SELECT ownerid FROM servers WHERE id = ?", (serverid,)).fetchone()
            if owner and owner[0] != me[0]:
                db.execute("DELETE FROM members WHERE serverid = ? AND userid = ?", (serverid, me[0]))
        emit(me[0])
        emit_server(serverid)
    return redirect(url_for("servers"))


@app.route("/servers/<int:serverid>/avatar", methods=["POST"])
def serveravatarupdate(serverid: int):
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    server = serverbyid(serverid)
    if not server or int(server[1]) != int(me[0]):
        return redirect(url_for("serverdetail", serverid=serverid))
    file = request.files.get("avatar")
    if file and file.filename:
        try:
            avatar = saveavatar(file, True)
            with connect("servers") as db:
                db.execute("UPDATE servers SET avatar = ? WHERE id = ? AND ownerid = ?", (avatar, serverid, me[0]))
            emit(me[0])
            emit_server(serverid)
        except Exception:
            pass
    return redirect(url_for("serverdetail", serverid=serverid))


@app.route("/servers/<int:serverid>/delete", methods=["POST"])
def serverdelete(serverid: int):
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    server = serverbyid(serverid)
    if not server or int(server[1]) != int(me[0]):
        return redirect(url_for("serverdetail", serverid=serverid))

    avatar_path = str(server[3] or "").strip()
    with connect("servers") as db:
        db.execute("DELETE FROM voicesignals WHERE serverid = ?", (serverid,))
        db.execute("DELETE FROM voicepresence WHERE serverid = ?", (serverid,))
        db.execute("DELETE FROM entries WHERE serverid = ?", (serverid,))
        db.execute("DELETE FROM channels WHERE serverid = ?", (serverid,))
        db.execute("DELETE FROM categories WHERE serverid = ?", (serverid,))
        db.execute("DELETE FROM roles WHERE serverid = ?", (serverid,))
        db.execute("DELETE FROM joins WHERE serverid = ?", (serverid,))
        db.execute("DELETE FROM members WHERE serverid = ?", (serverid,))
        db.execute("DELETE FROM servers WHERE id = ? AND ownerid = ?", (serverid, me[0]))

    # Remove server media folder if present.
    shutil.rmtree(MEDIA / "servers" / str(serverid), ignore_errors=True)
    if avatar_path:
        try:
            avatar_file = MEDIA / avatar_path
            if avatar_file.is_file():
                avatar_file.unlink()
        except Exception:
            pass

    emit(me[0])
    return redirect(url_for("servers"))


@app.route("/servers/<int:serverid>/channels/<int:channelid>/delete", methods=["POST"])
def deletechannel(serverid: int, channelid: int):
    me = currentaccount()
    if me:
        server = serverbyid(serverid)
        if hasserverperm(server, me[0], "managechannels"):
            from core.database import connect
            with connect("servers") as db:
                db.execute("DELETE FROM channels WHERE id = ? AND serverid = ?", (channelid, serverid))
            emit_server(serverid)
    return redirect(url_for("serverdetail", serverid=serverid))


@app.route("/servers/<int:serverid>/categories/<int:categoryid>/delete", methods=["POST"])
def deletecategory(serverid: int, categoryid: int):
    me = currentaccount()
    if me:
        server = serverbyid(serverid)
        if hasserverperm(server, me[0], "managechannels"):
            from core.database import connect
            with connect("servers") as db:
                db.execute("DELETE FROM categories WHERE id = ? AND serverid = ?", (categoryid, serverid))
                db.execute("UPDATE channels SET categoryid = 0 WHERE categoryid = ? AND serverid = ?", (categoryid, serverid))
            emit_server(serverid)
    return redirect(url_for("serverdetail", serverid=serverid))


@app.route("/servers/<int:serverid>/roles/create", methods=["POST"])
def createrole(serverid: int):
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    server = serverbyid(serverid)
    if not hasserverperm(server, me[0], "manageroles"):
        return redirect(url_for("serverdetail", serverid=serverid))
    name = request.form.get("name", "").strip()
    if not name:
        return redirect(url_for("serverdetail", serverid=serverid))
    perms = {
        "invitelink": request.form.get("perm_invitelink") == "1",
        "managechannels": request.form.get("perm_managechannels") == "1",
        "deleteothers": request.form.get("perm_deleteothers") == "1",
        "kick": request.form.get("perm_kick") == "1",
        "ban": request.form.get("perm_ban") == "1",
        "timeout": request.form.get("perm_timeout") == "1",
        "voiceban": request.form.get("perm_voiceban") == "1",
        "voicetimeout": request.form.get("perm_voicetimeout") == "1",
        "unkick": request.form.get("perm_unkick") == "1",
        "unban": request.form.get("perm_unban") == "1",
        "untimeout": request.form.get("perm_untimeout") == "1",
        "manageroles": request.form.get("perm_manageroles") == "1",
    }
    servercreaterole(serverid, name, json.dumps(perms))
    emit_server(serverid)
    return redirect(url_for("serverdetail", serverid=serverid))


@app.route("/servers/<int:serverid>/roles/<int:roleid>/edit", methods=["POST"])
def editrole(serverid: int, roleid: int):
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    server = serverbyid(serverid)
    if not hasserverperm(server, me[0], "manageroles"):
        return redirect(url_for("serverdetail", serverid=serverid))
    name = request.form.get("name", "").strip()
    perms = {
        "invitelink": request.form.get("perm_invitelink") == "1",
        "managechannels": request.form.get("perm_managechannels") == "1",
        "deleteothers": request.form.get("perm_deleteothers") == "1",
        "kick": request.form.get("perm_kick") == "1",
        "ban": request.form.get("perm_ban") == "1",
        "timeout": request.form.get("perm_timeout") == "1",
        "voiceban": request.form.get("perm_voiceban") == "1",
        "voicetimeout": request.form.get("perm_voicetimeout") == "1",
        "unkick": request.form.get("perm_unkick") == "1",
        "unban": request.form.get("perm_unban") == "1",
        "untimeout": request.form.get("perm_untimeout") == "1",
        "manageroles": request.form.get("perm_manageroles") == "1",
    }
    serverupdaterole(roleid, serverid, name, json.dumps(perms))
    emit_server(serverid)
    return redirect(url_for("serverdetail", serverid=serverid))


@app.route("/servers/<int:serverid>/members/<int:userid>/role", methods=["POST"])
def memberrole(serverid: int, userid: int):
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    server = serverbyid(serverid)
    if not hasserverperm(server, me[0], "manageroles"):
        return redirect(url_for("serverdetail", serverid=serverid))
    roleid = int(request.form.get("roleid", "0"))
    serverassignrole(serverid, userid, roleid)
    emit_server(serverid)
    return redirect(url_for("serverdetail", serverid=serverid))


@app.route("/servers/<int:serverid>/categories/create", methods=["POST"])
def createcategory(serverid: int):
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    server = serverbyid(serverid)
    if not hasserverperm(server, me[0], "managechannels"):
        return redirect(url_for("serverdetail", serverid=serverid))
    name = request.form.get("name", "").strip()
    kind = request.form.get("kind", "text")
    if name:
        servercreatecategory(serverid, name, kind)
        emit_server(serverid)
    return redirect(url_for("serverdetail", serverid=serverid))


@app.route("/servers/<int:serverid>/categories/<int:categoryid>/edit", methods=["POST"])
def editcategory(serverid: int, categoryid: int):
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    server = serverbyid(serverid)
    if not hasserverperm(server, me[0], "managechannels"):
        return redirect(url_for("serverdetail", serverid=serverid))
    serverupdatecategory(serverid, categoryid, request.form.get("name", "").strip(), request.form.get("kind", "text"))
    emit_server(serverid)
    return redirect(url_for("serverdetail", serverid=serverid))


@app.route("/servers/<int:serverid>/channels/create", methods=["POST"])
def createchannel(serverid: int):
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    server = serverbyid(serverid)
    if not hasserverperm(server, me[0], "managechannels"):
        return redirect(url_for("serverdetail", serverid=serverid))
    name = request.form.get("name", "").strip()
    if not name:
        return redirect(url_for("serverdetail", serverid=serverid))
    servercreatechannel(
        serverid=serverid,
        categoryid=int(request.form.get("categoryid", "0")),
        name=name,
        kind=request.form.get("kind", "text"),
        contentmode=request.form.get("contentmode", "all"),
        visibleperms=parseids(request.form.getlist("visibleperms")),
        writeperms=parseids(request.form.getlist("writeperms")),
        shareperms=parseids(request.form.getlist("shareperms")),
    )
    emit_server(serverid)
    return redirect(url_for("serverdetail", serverid=serverid))


@app.route("/servers/<int:serverid>/channels/<int:channelid>/edit", methods=["POST"])
def editchannel(serverid: int, channelid: int):
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    server = serverbyid(serverid)
    if not hasserverperm(server, me[0], "managechannels"):
        return redirect(url_for("serverdetail", serverid=serverid))
    serverupdatechannel(
        serverid=serverid,
        channelid=channelid,
        categoryid=int(request.form.get("categoryid", "0")),
        name=request.form.get("name", "").strip(),
        kind=request.form.get("kind", "text"),
        contentmode=request.form.get("contentmode", "all"),
        visibleperms=parseids(request.form.getlist("visibleperms")),
        writeperms=parseids(request.form.getlist("writeperms")),
        shareperms=parseids(request.form.getlist("shareperms")),
    )
    emit_server(serverid)
    return redirect(url_for("serverdetail", serverid=serverid))


@app.route("/servers/<int:serverid>/channels/<int:channelid>", methods=["GET", "POST"])
def channelview(serverid: int, channelid: int):
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    content = texts(current)
    server = serverbyid(serverid)
    if not server:
        return redirect(url_for("servers"))
    channel = serverchannel(serverid, channelid)
    if not channel:
        return redirect(url_for("serverdetail", serverid=serverid))
    if not canchannel(server, channel, me[0], "view"):
        return redirect(url_for("serverdetail", serverid=serverid))
    
    roles = serverroles(serverid)
    
    error = ""
    if request.method == "POST":
        if not canchannel(server, channel, me[0], "write"):
            error = content.get("errornoperm", "No permission")
        else:
            text = request.form.get("text", "").strip()
            upload = request.files.get("file")
            cm = channel[4]
            if text:
                if cm != "all":
                    error = content.get("errorcontentmode", "This channel has content restriction")
                else:
                    addserverentry(serverid, channelid, me[0], "text", text, "", 0)
                    emit_server(serverid)
            if not error and upload and upload.filename:
                if not canchannel(server, channel, me[0], "share"):
                    error = content.get("errornopermshare", "No file sharing permission")
                else:
                    try:
                        rel, size, kind = saveservermedia(serverid, channelid, upload)
                        if cm in {"image", "video", "audio"} and cm != kind:
                            raise ValueError("contentmode")
                        addserverentry(serverid, channelid, me[0], kind, "", rel, size)
                        emit_server(serverid)
                    except ValueError as ex:
                        if str(ex) == "contentmode":
                            error = content.get("errorcontentmode", "This channel has content restriction")
                        elif str(ex) == "imglimit":
                            error = content.get("errorimglimit", "Image cannot be larger than 200MB")
                        elif str(ex) == "vidlimit":
                            error = content.get("errorvidlimit", "Video cannot be larger than 300MB")
                        elif str(ex) == "audlimit":
                            error = content.get("erroraudlimit", "Audio cannot be larger than 200MB")
                        elif str(ex) == "filelimit":
                            error = content.get("errorfilelimit", "File cannot be larger than 500MB")
                        else:
                            error = content.get("errorupload", "Upload failed")
    entries = serverentries(serverid, channelid, 300)
    cats = servercategories(serverid)
    chans = [c for c in serverchannels(serverid) if canchannel(server, c, me[0], "view")]
    users = {}
    for e in entries:
        if e[1] not in users:
            a = accountbyid(e[1])
            users[e[1]] = a[1] if a else "user"
            
    return render_template(
        viewfile("channel.html"),
        server=server,
        channel=channel,
        entries=entries,
        users=users,
        categories=cats,
        channels=chans,
        roles=roles,
        error=error,
        myid=me[0],
        canwrite=canchannel(server, channel, me[0], "write"),
        canshare=canchannel(server, channel, me[0], "share"),
        canmanagechannels=hasserverperm(server, me[0], "managechannels"),
        canmanageroles=hasserverperm(server, me[0], "manageroles"),
        **navcontext(content, current),
    )


@app.route("/servers/<int:serverid>/voice/<int:channelid>")
def voicechannel(serverid: int, channelid: int):
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    me = currentaccount()
    if not me:
        return redirect(url_for("login"))
    content = texts(current)
    server = serverbyid(serverid)
    if not server:
        return redirect(url_for("servers"))
    channel = serverchannel(serverid, channelid)
    if not channel or channel[3] != "voice":
        return redirect(url_for("serverdetail", serverid=serverid))
    if not canchannel(server, channel, me[0], "view"):
        return redirect(url_for("serverdetail", serverid=serverid))

    roles = serverroles(serverid)
    cats = servercategories(serverid)
    chans = [c for c in serverchannels(serverid) if canchannel(server, c, me[0], "view")]

    voiceping(serverid, channelid, me[0], nowiso())
    cutoff = (datetime.now(timezone.utc) - VOICE_WINDOW).isoformat()
    voicecleanup(serverid, channelid, cutoff)
    users = []
    for uid, _ in voiceparticipants(serverid, channelid):
        a = accountbyid(uid)
        if a:
            users.append({"id": uid, "username": a[1], "avatar": smallavatar(a[3])})
            
    return render_template(
        viewfile("voice.html"), 
        server=server, 
        channel=channel, 
        users=users,
        categories=cats,
        channels=chans,
        roles=roles,
        myid=me[0],
        canmanagechannels=hasserverperm(server, me[0], "managechannels"),
        canmanageroles=hasserverperm(server, me[0], "manageroles"),
        **navcontext(content, current)
    )


@app.route("/voice/ping/<int:serverid>/<int:channelid>", methods=["POST"])
def voicepingroute(serverid: int, channelid: int):
    me = currentaccount()
    if not me:
        return {"ok": False}, 401
    server = serverbyid(serverid)
    channel = serverchannel(serverid, channelid)
    if not server or not channel or channel[3] != "voice" or not canchannel(server, channel, me[0], "view"):
        return {"ok": False}, 403
    voiceping(serverid, channelid, me[0], nowiso())
    cutoff = (datetime.now(timezone.utc) - VOICE_WINDOW).isoformat()
    voicecleanup(serverid, channelid, cutoff)
    rows = []
    for uid, _ in voiceparticipants(serverid, channelid):
        a = accountbyid(uid)
        if a:
            rows.append({"id": uid, "username": a[1], "avatar": smallavatar(a[3])})
    return {"ok": True, "users": rows}


@app.route("/voice/signal/<int:serverid>/<int:channelid>", methods=["POST"])
def voicesignal(serverid: int, channelid: int):
    me = currentaccount()
    if not me:
        return {"ok": False}, 401
    server = serverbyid(serverid)
    channel = serverchannel(serverid, channelid)
    if not server or not channel or channel[3] != "voice" or not canchannel(server, channel, me[0], "view"):
        return {"ok": False}, 403
    target = int(request.form.get("target", "0") or "0")
    kind = request.form.get("kind", "")
    payload = request.form.get("payload", "")
    if kind not in {"offer", "answer", "candidate", "hello"}:
        return {"ok": False}, 400
    sendvoicesignal(serverid, channelid, me[0], target, kind, payload)
    return {"ok": True}


@app.route("/voice/stream/<int:serverid>/<int:channelid>")
def voicestream(serverid: int, channelid: int):
    me = currentaccount()
    if not me:
        return Response("", status=401)
    server = serverbyid(serverid)
    channel = serverchannel(serverid, channelid)
    if not server or not channel or channel[3] != "voice" or not canchannel(server, channel, me[0], "view"):
        return Response("", status=403)
    last = int(request.args.get("last", "0"))

    def gen():
        nonlocal last
        idle = 0
        while idle < 55:
            rows = getvoicesignals(serverid, channelid, me[0], last)
            if rows:
                for sid, sender, target, kind, payload in rows:
                    last = sid
                    msg = json.dumps({"id": sid, "sender": sender, "target": target, "kind": kind, "payload": payload})
                    yield f"data: {msg}\n\n"
                idle = 0
            else:
                idle += 1
                yield "data: {\"kind\":\"ping\"}\n\n"
            time.sleep(1)

    return Response(gen(), mimetype="text/event-stream")

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from flask import Flask, Response, abort, redirect, render_template, request, send_from_directory, session, url_for
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from core.config import load
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
    setdmpermission,
    voicecleanup,
    voiceparticipants,
    voiceping,
    getvoicesignals,
    setup,
    unblockuser,
    unreadcount,
    updateavatar,
    updatepassword,
    updateusername,
)
from core.texts import language, texts


ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
DMROOT = MEDIA / "dm"

IMAGE_MAX = 200 * 1024 * 1024
VIDEO_MAX = 300 * 1024 * 1024
FILE_MAX = 500 * 1024 * 1024
ACTIVE_WINDOW = timedelta(seconds=40)
VOICE_WINDOW = timedelta(seconds=35)
SERVER_IMAGE_MAX = 200 * 1024 * 1024
SERVER_VIDEO_MAX = 300 * 1024 * 1024
SERVER_AUDIO_MAX = 200 * 1024 * 1024
SERVER_FILE_MAX = 500 * 1024 * 1024

app = Flask(__name__)
app.template_folder = str(ROOT)
app.secret_key = "changeme"
app.permanent_session_lifetime = timedelta(days=30)


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
    return dt.strftime("%Y-%m-%d %H:%M")


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


@app.route("/")
def home():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))
    content = texts(current)
    ctx = navcontext(content, current)
    if currentaccount():
        s, p = socialcards(currentaccount()[0])
        ctx["suggestions"] = s
        ctx["pending"] = p
        dmp = []
        for rid, sid in pendingdmreceived(currentaccount()[0]):
            u = accountbyid(sid)
            if u:
                dmp.append({"requestid": rid, "id": sid, "username": u[1], "avatar": smallavatar(u[3])})
        ctx["dmpending"] = dmp
    else:
        ctx["suggestions"] = []
        ctx["pending"] = []
        ctx["dmpending"] = []
    return render_template(viewfile("index.html"), **ctx)


@app.route("/choose", methods=["GET", "POST"])
def choose():
    if request.method == "POST":
        savechoice(request.form.get("language", "en"))
        return redirect(url_for("home"))
    return render_template(viewfile("language.html"))


@app.route("/set/<code>")
def setlanguage(code: str):
    savechoice(code)
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
    return render_template(viewfile("friends.html"), friends=items, **navcontext(content, current))


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
            if upload and upload.filename:
                ext = Path(secure_filename(upload.filename)).suffix.lower()
                imageext = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
                videoext = {".mp4", ".webm", ".mov", ".mkv"}
                fileext = {".zip", ".rar", ".7z", ".tar", ".gz"}
                if ext in imageext:
                    rel, size = savemedium(upload, "image")
                    addfile(convid, me[0], "image", rel, size)
                elif ext in videoext:
                    rel, size = savemedium(upload, "video")
                    addfile(convid, me[0], "video", rel, size)
                elif ext in fileext:
                    rel, size = savemedium(upload, "file")
                    addfile(convid, me[0], "file", rel, size)
                else:
                    raise ValueError("invalid")
            if voice and voice.filename:
                rel, size = savemedium(voice, "audio")
                addfile(convid, me[0], "audio", rel, size)
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
    # Failsafe: if client starts with 0, start from current tail to avoid
    # update-refresh loops on existing conversations.
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


@app.route("/social/request/<int:target>", methods=["POST"])
def socialrequest(target: int):
    me = currentaccount()
    if me and me[0] != target and not isblocked(me[0], target) and not isblocked(target, me[0]) and not arefriends(me[0], target):
        sendrequest(me[0], target)
    return redirect(url_for("home"))


@app.route("/social/accept/<int:reqid>", methods=["POST"])
def socialaccept(reqid: int):
    me = currentaccount()
    if me:
        acceptrequest(reqid, me[0])
    return redirect(url_for("home"))


@app.route("/social/reject/<int:reqid>", methods=["POST"])
def socialreject(reqid: int):
    me = currentaccount()
    if me:
        rejectrequest(reqid, me[0])
    return redirect(url_for("home"))


@app.route("/social/remove/<int:target>", methods=["POST"])
def socialremove(target: int):
    me = currentaccount()
    if me and me[0] != target:
        removefriend(me[0], target)
    return redirect(url_for("home"))


@app.route("/social/block/<int:target>", methods=["POST"])
def socialblock(target: int):
    me = currentaccount()
    if me and me[0] != target:
        blockuser(me[0], target)
    return redirect(url_for("home"))


@app.route("/social/unblock/<int:target>", methods=["POST"])
def socialunblock(target: int):
    me = currentaccount()
    if me and me[0] != target:
        unblockuser(me[0], target)
    return redirect(url_for("friendships"))


@app.route("/dm/request/accept/<int:reqid>", methods=["POST"])
def dmrequestaccept(reqid: int):
    me = currentaccount()
    if me:
        acceptdmrequest(reqid, me[0])
    return redirect(url_for("home"))


@app.route("/dm/request/reject/<int:reqid>", methods=["POST"])
def dmrequestreject(reqid: int):
    me = currentaccount()
    if me:
        rejectdmrequest(reqid, me[0])
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.pop("accountid", None)
    session.permanent = False
    return redirect(url_for("login"))


@app.route("/media/<path:filename>")
def media(filename: str):
    return send_from_directory(MEDIA, filename)


@app.route("/<zone>/<filename>")
def assets(zone: str, filename: str):
    if zone not in {"pc", "mobile"}:
        abort(404)
    return send_from_directory(ROOT / zone, filename)


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
                        "SELECT id, ownerid, name, avatar, visibility, joinmode, joincode, visibleperms, writeperms, shareperms FROM servers WHERE joincode = ?",
                        (code,),
                    ).fetchone()
            if not target:
                error = content.get("errorservernotfound", "Server not found")
            else:
                if target[5] == "approval":
                    serverjoinrequest(target[0], me[0])
                else:
                    serverjoin(target[0], me[0])
                return redirect(url_for("serverdetail", serverid=target[0]))
    mine, publics = serverlist(me[0])
    return render_template(viewfile("servers.html"), mine=mine, publics=publics, error=error, **navcontext(content, current))


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
        **navcontext(content, current),
    )


@app.route("/servers/accept/<int:joinid>", methods=["POST"])
def serverjoinaccept(joinid: int):
    me = currentaccount()
    if me:
        serveraccept(joinid, me[0])
    return redirect(url_for("servers"))


@app.route("/servers/reject/<int:joinid>", methods=["POST"])
def serverjoinreject(joinid: int):
    me = currentaccount()
    if me:
        from core.database import serverreject

        serverreject(joinid, me[0])
    return redirect(url_for("servers"))


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
            if not error and upload and upload.filename:
                if not canchannel(server, channel, me[0], "share"):
                    error = content.get("errornopermshare", "No file sharing permission")
                else:
                    try:
                        rel, size, kind = saveservermedia(serverid, channelid, upload)
                        if cm in {"image", "video", "audio"} and cm != kind:
                            raise ValueError("contentmode")
                        addserverentry(serverid, channelid, me[0], kind, "", rel, size)
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
        error=error,
        canwrite=canchannel(server, channel, me[0], "write"),
        canshare=canchannel(server, channel, me[0], "share"),
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

    voiceping(serverid, channelid, me[0], nowiso())
    cutoff = (datetime.now(timezone.utc) - VOICE_WINDOW).isoformat()
    voicecleanup(serverid, channelid, cutoff)
    users = []
    for uid, _ in voiceparticipants(serverid, channelid):
        a = accountbyid(uid)
        if a:
            users.append({"id": uid, "username": a[1], "avatar": smallavatar(a[3])})
    return render_template(viewfile("voice.html"), server=server, channel=channel, users=users, **navcontext(content, current))


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





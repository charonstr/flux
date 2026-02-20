from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from core.config import load
from core.database import accountbyid, accountbyname, createaccount, savevisitor, setup
from core.texts import language, texts


ROOT = Path(__file__).resolve().parent.parent


app = Flask(__name__)
app.template_folder = str(ROOT)
app.secret_key = "changeme"


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
    return accountbyid(int(accountid))


def savechoice(code: str) -> None:
    lang = language(code)
    session["language"] = lang
    savevisitor(
        token=visitor(),
        language=lang,
        useragent=request.headers.get("User-Agent", "unknown"),
        ip=request.remote_addr or "unknown",
    )


@app.route("/")
def home():
    current = userlanguage()
    if not current:
        return redirect(url_for("choose"))

    content = texts(current)
    account = currentaccount()
    username = account[1] if account else None

    return render_template(
        viewfile("index.html"),
        t=content,
        current=current,
        username=username,
    )


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
                account = accountbyname(username)
                session["accountid"] = account[0]
                return redirect(url_for("home"))

    return render_template(viewfile("register.html"), t=content, current=current, error=error)


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
        account = accountbyname(username)

        if not account or not check_password_hash(account[2], password):
            error = content.get("errorlogin", "Username or password is incorrect")
        else:
            session["accountid"] = account[0]
            return redirect(url_for("home"))

    return render_template(viewfile("login.html"), t=content, current=current, error=error)


@app.route("/logout")
def logout():
    session.pop("accountid", None)
    return redirect(url_for("home"))


@app.route("/<zone>/<filename>")
def assets(zone: str, filename: str):
    if zone not in {"pc", "mobile"}:
        abort(404)
    return send_from_directory(ROOT / zone, filename)


def run() -> None:
    setup()
    settings = load()
    app.secret_key = settings["secret"]
    app.run(host=settings["host"], port=settings["port"], debug=settings["debug"])

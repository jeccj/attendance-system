"""简易课堂签到系统：Flask + SQLite，运行 python app.py 即可启动。"""

import csv
import io
import os
import re
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from getpass import getpass
from pathlib import Path

from flask import (
    Flask, Response, abort, flash, g, redirect, render_template,
    request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
CHINA_TZ = timezone(timedelta(hours=8))


def get_db():
    """每个请求使用一个数据库连接，请求结束后自动关闭。"""
    if "db" not in g:
        from flask import current_app
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def teacher_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("teacher_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def session_is_open(item):
    return not item["is_closed"] and item["ends_at"] > int(time.time())


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(BASE_DIR / "instance" / "attendance.db"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    # 密钥在首次启动时生成并保存，重启服务后登录凭据仍有效。
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    if not app.config.get("SECRET_KEY"):
        secret_file = BASE_DIR / "instance" / "secret.key"
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(secret_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(secrets.token_hex(32))
        app.config["SECRET_KEY"] = secret_file.read_text(encoding="utf-8").strip()
        if not app.config["SECRET_KEY"]:
            raise RuntimeError("instance/secret.key 为空，请删除该文件后重新启动。")

    app.teardown_appcontext(close_db)
    app.jinja_env.globals.update(
        csrf_token=csrf_token,
        session_is_open=session_is_open,
    )

    @app.template_filter("localtime")
    def localtime(value, fmt="%m-%d %H:%M"):
        return datetime.fromtimestamp(value, CHINA_TZ).strftime(fmt)

    @app.before_request
    def verify_csrf():
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            supplied = request.form.get("csrf_token", "")
            if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
                abort(400, description="页面已失效，请刷新页面后重新提交。")

    @app.after_request
    def add_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    with app.app_context():
        db = get_db()
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
        # 仅首次建库创建账号；密码更改后不会被重启覆盖。
        if not db.execute("SELECT id FROM teachers LIMIT 1").fetchone():
            db.execute(
                "INSERT INTO teachers (username, password_hash) VALUES (?, ?)",
                ("admin", generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin123"))),
            )
        db.commit()

    @app.route("/", methods=["GET", "POST"])
    def checkin():
        values = {"code": request.args.get("code", ""), "student_id": "", "name": ""}
        if request.method == "GET":
            return render_template("checkin.html", values=values)

        values = {key: request.form.get(key, "").strip() for key in values}
        error = None
        status = 400
        if not re.fullmatch(r"[0-9]{6}", values["code"]):
            error = "请输入老师提供的 6 位签到码。"
        elif not re.fullmatch(r"[0-9]{4,24}", values["student_id"]):
            error = "学号应为 4～24 位数字。"
        elif not 1 <= len(values["name"]) <= 30 or any(ord(c) < 32 for c in values["name"]):
            error = "请填写姓名，长度不超过 30 个字。"
        if error:
            flash(error, "error")
            return render_template("checkin.html", values=values), status

        db = get_db()
        # 写事务锁使「检查有效期 + 插入」成为一个整体，避免结束签到时并发写入。
        db.execute("BEGIN IMMEDIATE")
        try:
            item = db.execute("SELECT * FROM sessions WHERE code = ?", (values["code"],)).fetchone()
            if item is None:
                error = "签到码不存在，请确认后再试。"
                status = 404
            elif not session_is_open(item):
                error = "这次签到已结束，请联系老师。"
                status = 410
            else:
                try:
                    result = db.execute(
                        "INSERT INTO attendance (session_id, student_id, name, checked_at) VALUES (?, ?, ?, ?)",
                        (item["id"], values["student_id"], values["name"], int(time.time())),
                    )
                    db.commit()
                except sqlite3.IntegrityError:
                    error = "该学号已完成本次签到，无需重复提交。"
                    status = 409
                else:
                    session["receipt_id"] = result.lastrowid
                    return redirect(url_for("success"))
        finally:
            if db.in_transaction:
                db.rollback()
        flash(error, "error")
        return render_template("checkin.html", values=values), status

    @app.get("/success")
    def success():
        receipt_id = session.get("receipt_id")
        if not receipt_id:
            return redirect(url_for("checkin"))
        receipt = get_db().execute(
            """SELECT a.*, s.course_name, s.title FROM attendance a
               JOIN sessions s ON s.id = a.session_id WHERE a.id = ?""",
            (receipt_id,),
        ).fetchone()
        if not receipt:
            return redirect(url_for("checkin"))
        return render_template("success.html", receipt=receipt)

    @app.route("/teacher/login", methods=["GET", "POST"])
    def login():
        if session.get("teacher_id"):
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            teacher = get_db().execute(
                "SELECT * FROM teachers WHERE username = ?",
                (request.form.get("username", "").strip(),),
            ).fetchone()
            if teacher and check_password_hash(teacher["password_hash"], request.form.get("password", "")):
                session.clear()
                session["teacher_id"] = teacher["id"]
                session.permanent = True
                return redirect(url_for("dashboard"))
            flash("账号或密码不正确。", "error")
            return render_template("login.html"), 401
        return render_template("login.html")

    @app.post("/teacher/logout")
    @teacher_required
    def logout():
        session.clear()
        return redirect(url_for("checkin"))

    @app.get("/teacher")
    @teacher_required
    def dashboard():
        items = get_db().execute(
            """SELECT s.*, COUNT(a.id) AS attendance_count FROM sessions s
               LEFT JOIN attendance a ON a.session_id = s.id
               WHERE s.teacher_id = ? GROUP BY s.id ORDER BY s.id DESC""",
            (session["teacher_id"],),
        ).fetchall()
        stats = {
            "total": len(items),
            "active": sum(session_is_open(item) for item in items),
            "records": sum(item["attendance_count"] for item in items),
        }
        return render_template("dashboard.html", items=items, stats=stats)

    @app.post("/teacher/create")
    @teacher_required
    def create_session():
        course = request.form.get("course_name", "").strip()
        title = request.form.get("title", "").strip()
        duration = request.form.get("duration", "")
        if not 1 <= len(course) <= 50 or not 1 <= len(title) <= 80:
            flash("请填写课程名称和签到主题，并检查文字长度。", "error")
            return redirect(url_for("dashboard"))
        if duration not in {"5", "10", "15", "30", "60"}:
            flash("请选择有效的签到时长。", "error")
            return redirect(url_for("dashboard"))
        now = int(time.time())
        db = get_db()
        for _ in range(20):
            code = f"{secrets.randbelow(1_000_000):06d}"
            try:
                result = db.execute(
                    """INSERT INTO sessions
                       (teacher_id, course_name, title, code, created_at, ends_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session["teacher_id"], course, title, code, now, now + int(duration) * 60),
                )
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
            else:
                flash("签到已发起，将签到码告诉同学即可。", "success")
                return redirect(url_for("session_detail", session_id=result.lastrowid))
        abort(503, description="暂时无法生成签到码，请稍后重试。")

    def owned_session(session_id):
        item = get_db().execute(
            "SELECT * FROM sessions WHERE id = ? AND teacher_id = ?",
            (session_id, session["teacher_id"]),
        ).fetchone()
        if not item:
            abort(404, description="没有找到这次签到。")
        return item

    @app.get("/teacher/sessions/<int:session_id>")
    @teacher_required
    def session_detail(session_id):
        item = owned_session(session_id)
        records = get_db().execute(
            "SELECT * FROM attendance WHERE session_id = ? ORDER BY checked_at, id",
            (session_id,),
        ).fetchall()
        return render_template("detail.html", item=item, records=records)

    @app.post("/teacher/sessions/<int:session_id>/close")
    @teacher_required
    def close_session(session_id):
        owned_session(session_id)
        db = get_db()
        db.execute("UPDATE sessions SET is_closed = 1 WHERE id = ?", (session_id,))
        db.commit()
        flash("本次签到已结束。", "success")
        return redirect(url_for("session_detail", session_id=session_id))

    @app.get("/teacher/sessions/<int:session_id>/export")
    @teacher_required
    def export_csv(session_id):
        item = owned_session(session_id)
        rows = get_db().execute(
            "SELECT * FROM attendance WHERE session_id = ? ORDER BY checked_at, id",
            (session_id,),
        ).fetchall()
        output = io.StringIO(newline="")
        output.write("\ufeff")  # Excel 直接打开时正确识别中文。
        writer = csv.writer(output)
        writer.writerow(["序号", "学号", "姓名", "课程", "签到主题", "签到时间（北京时间）"])

        def safe_cell(value):
            value = str(value)
            return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else value

        for index, row in enumerate(rows, 1):
            writer.writerow([safe_cell(value) for value in [
                index, row["student_id"], row["name"], item["course_name"], item["title"],
                localtime(row["checked_at"], "%Y-%m-%d %H:%M:%S"),
            ]])
        return Response(
            output.getvalue(), content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="attendance-{session_id}.csv"'},
        )

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    @app.errorhandler(503)
    def show_error(error):
        descriptions = {404: "没有找到这个页面。", 413: "提交内容过大，请检查后重试。"}
        message = descriptions.get(error.code, "操作未完成，请刷新页面后重试。")
        if error.code in (400, 503):
            message = error.description
        return render_template("error.html", message=message), error.code

    return app


if __name__ == "__main__":
    app = create_app()
    if len(sys.argv) > 1 and sys.argv[1] == "set-password":
        password = getpass("输入新的教师密码（至少 8 位）：")
        confirm = getpass("再次输入：")
        if len(password) < 8 or password != confirm:
            raise SystemExit("密码长度不足，或两次密码不一致。")
        with app.app_context():
            db = get_db()
            db.execute(
                "UPDATE teachers SET password_hash = ? WHERE username = ?",
                (generate_password_hash(password), "admin"),
            )
            db.commit()
        print("教师密码已更新。")
    else:
        # 课堂实验默认只在本机运行；局域网演示可设置 HOST=0.0.0.0。
        app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=False)

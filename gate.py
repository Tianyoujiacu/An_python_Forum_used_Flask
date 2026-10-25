"""前厅闸门（访问控制）。

集成只需两行（放进 app.py 末尾附近即可）：

    from gate import bp as gate_bp, gate_before_request
    app.register_blueprint(gate_bp)
    app.before_request(gate_before_request)

配置全在环境变量（PA：Web → Environment Variables）：

    GATE_ENABLED          默认 1。设成 0 就是逃生开关，整站立刻恢复原样
    GATE_PASSWORD_HASH    推荐。pbkdf2/argon2 哈希，用 `python3 gate_password.py 你的口令` 生成
    GATE_PASSWORD         图省事可用明文（每次启动现算哈希），但会留在 PA 变量里
    GATE_MAX_ATTEMPTS     默认 5
    GATE_WINDOW_SECONDS   默认 300，滑窗内超过上限就 429

未解锁时（且演示模式关着）：任意页面返回一张极简 404 页（状态码 404 + noindex），
桌面按 Ctrl+Alt+C、手机长按页面上的“404”两秒，都只打开一个口令框；
口令对了才写 session（浏览器会话，关标签页即失效）。
唯一多放行的公开路径是 /robots.txt（见 PUBLIC_PATHS）：那页写着“全站禁止收录”，
它自己反而必须随时取到，未解锁时也不能变 404。
"""
import os
import time
from datetime import datetime, timedelta


def utcnow():
    """与 app.py 同一口径：naive UTC。"""
    return datetime.utcnow()

from flask import (Blueprint, jsonify, make_response, render_template,
                   request, session)
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint("gate", __name__)

OK_KEY = "gate_ok"                       # session 里唯一的凭据
ATTEMPT_PATHS = ("/enter", "/favicon.ico")   # 闸门自身/图标放行
# 未解锁时也要能取到的公开路径：只有 robots.txt。
# 它返回 404 的话，爬虫会当成“没有指令”=允许抓全站，正好把“禁止收录”反着做掉了。
PUBLIC_PATHS = ("/robots.txt", "/healthz")   # 机器人指令 + 运维自检（只回 "ok"，不含站点信息）
EXEMPT_ENDPOINTS = {"gate.enter", "gate.open", "static"}

_attempts = {}                           # ip -> [时间戳]  单 worker 够用

# ============================================================================
#  ① 想直接改代码：就改下面这一行的字符串，别的都不用动
#  ② 更推荐：别管这行，去 PA 的 Web → Environment Variables 里设
#       GATE_PASSWORD_HASH=<python3 gate_password.py 你的口令 的输出>
#     env 存在时优先级高于这一行，这一行就完全不生效
#  ⚠ 不改这行的话，线上入口令就是下面这个示例值 —— 等于公开，务必改掉
# ============================================================================
_DEMO_PASSWORD = "class-demo-2026"       # ← 只有这一行需要你改


def gate_enabled():
    return os.environ.get("GATE_ENABLED", "1").strip() != "0"


def is_unlocked():
    return bool(session.get(OK_KEY))


def expected_hash():
    h = os.environ.get("GATE_PASSWORD_HASH", "").strip()
    if h:
        return h
    p = os.environ.get("GATE_PASSWORD", "").strip()
    if p:
        return generate_password_hash(p)
    if _DEMO_PASSWORD:
        # 兜底用代码里的示例口令。这等于把入口令写在源码里，所以每次校验都嚷一声。
        current_log("⚠ 正在使用 gate.py 第 44 行的示例口令，请改掉，"
                    "或在 PA 变量里设 GATE_PASSWORD_HASH")
        return generate_password_hash(_DEMO_PASSWORD)
    return None


def _plain_404(status=404):
    resp = make_response(render_template("gate/404.html"), status)
    resp.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    resp.headers["Cache-Control"] = "no-store"
    return resp


def gate_before_request():
    if not gate_enabled():
        return None
    if request.path.startswith(ATTEMPT_PATHS + PUBLIC_PATHS) or request.endpoint in EXEMPT_ENDPOINTS:
        return None
    if is_unlocked():
        return None
    return _plain_404()


def _db():
    from app import db
    return db


def client_bucket():
    """PA 前面有好几层代理，客户端能自己塞 X-Forwarded-For；取最右一项才是代理补的真实 IP。"""
    xff = request.headers.get("X-Forwarded-For") or ""
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    return "ip:" + (parts[-1] if parts else (request.remote_addr or "?"))[:70]


def _count(bucket, window, limit):
    """落库计数：多进程/重启都不会失效。**任何异常都倾向放行判断失败=拒绝**，不能因为库忙就放开闸门。"""
    db = _db()
    since = utcnow() - timedelta(seconds=window)
    try:
        n = db.session.execute(text(
            "SELECT count(*) FROM gate_attempt WHERE bucket = :b AND at > :s AND ok = 0"),
            {"b": bucket, "s": since}).scalar() or 0
    except Exception:
        current_log("闸门限流表不可用，按拒绝处理：" + str(__import__('sys').exc_info()[1]))
        return None
    return n


def _record(bucket, ok=False):
    from app import GateAttempt
    db = _db()
    db.session.add(GateAttempt(bucket=bucket, ok=ok))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def _prune():
    db = _db()
    try:
        db.session.execute(text("DELETE FROM gate_attempt WHERE at < :c"),
                           {"c": utcnow() - timedelta(hours=6)})
        db.session.commit()
    except Exception:
        db.session.rollback()


def _gate_audit(action, detail, table="gate", row_id="-"):
    """app.py 里才有审计写入器（也要绕开循环 import），所以这里延迟取。"""
    try:
        import app as _app
        _app.audit_event(action, detail, table, row_id)
    except Exception:
        current_log("审计写入失败（不影响闸门）")

@bp.route("/enter", methods=["GET", "POST"])
def enter():
    """GET 只为手机用户（长按“404”）准备同一张页面；POST 才是校验。"""
    if request.method == "GET":
        return _plain_404(200)

    # 免 CSRF 的写接口必须自己挡跨站。两道 together：
    #   1) 只收 JSON —— 跨站 <form> 提交不了 application/json（要预检），也拿不到我们的
    #      X-Requested-With（自定义头同样要预检）；
    #   2) Origin/Referer 存在时必须同源。
    if not request.is_json and not request.headers.get("X-Requested-With"):
        return jsonify(ok=False, msg="非法请求形式。"), 400
    origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
    if origin:
        from urllib.parse import urlsplit
        netloc = urlsplit(origin).netloc
        if netloc and netloc != request.host:
            return jsonify(ok=False, msg="非法请求来源。"), 403

    if not gate_enabled():
        return jsonify(ok=True)                     # 关了闸门就别拦人
    window = float(os.environ.get("GATE_WINDOW_SECONDS", "300"))
    limit = int(os.environ.get("GATE_MAX_ATTEMPTS", "5"))
    # 全局阈值只是保 CPU（scrypt 很贵），故意放得很宽：
    # 定太紧会变成“任何人刷满全局就能把闸门对所有同学锁死”的 DoS 杠杆。
    glimit = int(os.environ.get("GATE_GLOBAL_MAX", "300"))
    # ip 桶取代理补在 XFF 最右的一段，客户端自己塞的那几段不可信。
    buckets = [client_bucket(), "global"]
    limits = [limit, glimit]
    cookie = request.cookies.get("session")
    if cookie:                                     # 只有真带 cookie 的会话才再叠一层，避免共享空桶
        buckets.append("sess:" + cookie[:24])
        limits.append(limit)
    _prune()
    for b, lim in zip(buckets, limits):
        n = _count(b, window, lim)
        if n is None or n >= lim:
            if request.cookies.get("session"):
                session.permanent = False
                session.pop(OK_KEY, None)
            resp = jsonify(ok=False, msg="尝试次数过多，稍后再试。")
            resp.status_code = 429
            resp.headers["Retry-After"] = str(int(window))
            return resp

    payload = request.get_json(silent=True) or request.form
    guess = (payload.get("pass") or "")[:256]
    want = expected_hash()
    if want is None:
        # 配置缺失绝不默认放行：日志里留一条，页面上只当口令错误
        current_log("GATE 已开启但未配置 GATE_PASSWORD_HASH / GATE_PASSWORD，拒绝解锁")
        return jsonify(ok=False, msg="口令不正确。"), 403
    ok = bool(guess) and check_password_hash(want, guess)
    for b in buckets:
        _record(b, ok=ok)
    # 口令对不对都进审计：有人试著闯门，老师得看得见。
    # 量不会失控 —— 上面每个来源（IP / 会话 / 全站）都已经限流过了。
    _gate_audit("gate", ("前厅口令正确，已解锁 → " + url_for_next()) if ok
           else "前厅口令错误（未提供口令）" if not guess else "前厅口令错误",
           "gate", "-")
    if ok:
        session.permanent = False                   # 关标签页即失效
        session[OK_KEY] = True
        return jsonify(ok=True, next=url_for_next())
    return jsonify(ok=False, msg="口令不正确。"), 403


def url_for_next():
    nxt = (request.args.get("to") or request.form.get("to") or "/")
    # 只允许站内相对路径，防开放重定向
    if not nxt.startswith("/") or nxt.startswith("//"):
        return "/"
    return nxt


@bp.post("/enter/lock")
def lock_again():
    # 同上：不收跨站表单能发到这里的形态，避免被人远端“上一把锁”
    if not request.is_json and not request.headers.get("X-Requested-With"):
        return jsonify(ok=False, msg="非法请求形式。"), 400
    session.pop(OK_KEY, None)
    return _plain_404(200)


def current_log(msg):
    try:
        import flask
        flask.current_app.logger.warning(msg)
    except Exception:
        pass


def register(app):
    """可选的一行集成（等价于上面两行）。"""
    app.register_blueprint(bp)
    app.before_request(gate_before_request)
    return app
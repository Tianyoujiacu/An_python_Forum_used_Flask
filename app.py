"""班级论坛 —— 加固 / 优化版（P0 + P1 + P2 + 找回密码）

部署（PythonAnywhere，免费套餐可用）：
    WSGI 配置文件里写：  from app import app as application
    Bash console 里跑：  flask --app app init-db        # 建表 + 建管理员
                         flask --app app ensure-schema  # 老库增量补列/补索引
                         flask --app app doctor         # 数据体检
本地开发：               flask --app app run

必须设置的环境变量 —— PythonAnywhere 网页上没有填环境变量的地方，只能写在 WSGI 文件里
（Web 标签页 -> WSGI configuration file 那个链接，指向 /var/www/<用户名>_pythonanywhere_com_wsgi.py），
在 from app import ... 之前逐行加：os.environ.setdefault("SECRET_KEY", "...")
（把值换成你自己的、不要提交进 git；改完点一次 Reload 才生效）：
    SECRET_KEY       必填。缺失时本次启动会用随机值，重启即全员掉线（绝不再用源码里的固定值）
    ADMIN_EMAIL / ADMIN_PASSWORD
                     init-db 建管理员用；不设置则管理员密码随机生成并打印一次
    SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / MAIL_FROM
                     可选。不设置则“找回密码”只走管理员手动重置，不发信
    MAIL_DEBUG       设为 1 时把重置/验证链接同时打到日志（只在调试时用，会把令牌泄露到日志里)

 操作审计（audit_log 表，后台“操作审计”页可见）不需要额外配置，可选：
     AUDIT_IP              full（默认，存完整 IP）/ masked（只存网段，1.2.3.*）/ none（不存 IP）
                           —— 存学生 IP 属于个人信息，班里能不能存你自己定；改完要 Reload。
     AUDIT_RETENTION_DAYS  保留天数，默认 30 天；超过这个天数的条目会被自动删除。
    记录范围：所有对象级增删改（发帖/回答/点赞/采纳/投票/冻结/删帖/改密…）+ 登录成功失败
    + 前厅解锁 + 自动注销。读操作、纯计数列同步、闸门尝试表都不记（否则真事件会被噪声埋掉）。
    自动过期有两条路，装一条就够：
      ① 定时任务（PA 控制台 Scheduled Tasks）每天跑 `flask --app app prune-audit`；
      ② 什么都不配也行：有人访问时顺手清（每个进程最多 6 小时一次，先探一条再删，
         且爬虫抓 robots.txt 不算访问）。
    后台页面底部还能“删得更狠”（比保留期更短，最少留 7 天；填比保留期长的数字没有意义，
    会被按保留期执行）。删除这个动作本身也会被记下来 —— 谁清的日志永远查得到。

 登录状态（自动注销）：默认就开，可选覆盖，改完要 Reload
     SESSION_IDLE_MINUTES  多久没操作就踢下线，默认 30 分钟
     SESSION_MAX_HOURS     一次登录最多用多久（一直在点也要重登），默认 12 小时
     勾了“记住我”的两项一起放宽到 REMEMBER_COOKIE_DURATION（当前 7 天）——
     否则界面上写的“7 天”是假的；到点必重登，不给无限续命。

 不被搜索引擎收录：三层，无需配置
     X-Robots-Tag 响应头（每个响应都带：页面、错误页、静态文件、闸门那张伪 404）
     + 模板里的 <meta name=robots> + /robots.txt 的 Disallow: /。
     没有 sitemap.xml。这三层只管“不进搜索结果”，管不住“谁拿到链接谁能看”——
     后者见下一节的门面内容。想让已经被收进去的历史页面掉下去，设 ROBOTS_DISALLOW=0
     放爬虫回访读一次 noindex（见 robots_txt_body），清完改回 1。

 没开通的人看到什么（门面内容）：默认开启，后台“备份与导出”第一张卡片可切换
     没登录的人、以及注册了但管理员还没点“开通”的账号 —— 被转发过链接的同学/家长、所有
     爬虫、以及知道入口口令但没账号的人 —— 在内容页上只看到 demo.py 里写死的那套页面。
     它看起来就是个正常论坛：页面、响应头、导航里都不出现“示例/演示/未开通”这类身份标识
     （留标识就等于没有门面），真实帖子、成员、公告、未读条数一个字节都不发出去。
     发言入口照常给，等人真的发出去时才提示一句“这个账号还没有开通”。记这一句：
         未登录 / 未开通的账号 → 门面内容（他们的发帖与回复会被挡下，提示“账号还没有开通”）
         已登录且被开通        → 真实站点
         管理员                → 真实站点（不会被自己锁在门外，否则连开通按钮都点不到）
         关掉这一层            → 回到老行为：凭前厅口令即可免注册浏览真实内容
     口令不再等于“能看真实内容”：它是全班共享的，凭它就能看完全站等于没有登录墙。
     两个人的状态各有去处：
       · 站点级开关在 site_flag 表（不放环境变量：要在后台点一下就立刻生效，并留下“谁改的”审计）
       · 谁被开通在 user.is_trusted 列（默认 0 = 不信任；后台“用户管理”逐个开通，或一键
         “全部开通”。那一页上的“未开通/已开通”徽章是给管理员看的，访客那边没有这种字样）
     所以升级后必须跑一次 flask --app app ensure-schema —— 补上这两样之后全员是“未开通”，
     记得去用户管理点一次“全部开通”，否则全班都会以为自己打不开论坛。
     初始状态想反过来（不要门面）就设 DEMO_MODE=0；管理员在后台点过一次之后以库里那行为准。
     另外 /healthz 只回一个 ok，用来判断“服务活着吗、有没有被误挡”，不含任何站点信息。
"""

import io
import json
import os
import re
import sys
import sqlite3
import zipfile
import secrets
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from types import SimpleNamespace
from urllib.parse import urljoin, urlsplit

import bleach
import demo                                      # 演示数据（未登录访客看到的假站点）
import html as html_mod
import mistune
from pygments import highlight as pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound
from flask import (Flask, abort, current_app, flash, g, has_request_context, make_response,
                   redirect, render_template, request, send_file, session, url_for)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import (LoginManager, UserMixin, current_user,
                         login_required, login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFError, CSRFProtect
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import Engine, event, text, update
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import (BooleanField, PasswordField, SelectField, StringField,
                     SubmitField, TextAreaField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length, Optional,
                                Regexp, ValidationError)


def utcnow():
    """入库统一用“无时区的 UTC”：老数据就是这个口径，不迁移也不会串。
    混用 aware/naive 做减法会 TypeError，所以全站只存 naive UTC。"""
    return datetime.utcnow()


try:                                  # 系统带 tz 数据库时优先用它
    from zoneinfo import ZoneInfo
    CHINA_TZ = ZoneInfo("Asia/Shanghai")
except Exception:                     # 没有 tzdata 时退回固定 +8（中国大陆无夏令时）
    CHINA_TZ = timezone(timedelta(hours=8))


def cn_now():
    """只给“现在”用（比如页脚年份），返回带北京时区的对象。"""
    return datetime.now(CHINA_TZ)


def cn_time(dt, fmt="%Y-%m-%d %H:%M"):
    """展示层专用：把库里 naive UTC 转成北京时间再格式化。
    绝不在写入时换算——那样一旦改时区或跨年就会把历史数据搅乱。"""
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CHINA_TZ).strftime(fmt)


# ---------------------------------------------------------------- 应用与配置

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

_secret_from_env = os.environ.get("SECRET_KEY")
if _secret_from_env:
    app.config["SECRET_KEY"] = _secret_from_env
else:
    # 以前这里是硬编码 'AClassForumForStudents20140430'：
    # 源码一旦外泄，任何人都能伪造任意用户（含管理员）的 session cookie。
    app.config["SECRET_KEY"] = secrets.token_urlsafe(48)
    app.logger.warning(
        "未检测到环境变量 SECRET_KEY，本次启动使用随机密钥。"
        "进程重启后所有人的登录状态会失效，请在 PythonAnywhere 的 Web 页设置 SECRET_KEY。")

# --- 会话与_cookie_安全 ---
# 本地开发/回归测试用 http://127.0.0.1 跑，带 Secure 的 cookie 浏览器和
# urllib 都不会回传，登录会直接失败 —— 所以给本地留一个开关，线上默认严格。
_DEV_HTTP = os.environ.get("DEV_HTTP", "0") == "1"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = not _DEV_HTTP     # 线上：PA 全站 HTTPS，必须开
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"       # 顺带挡掉一部分跨站 POST
app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
app.config["REMEMBER_COOKIE_HTTPONLY"] = True
# 实测：不显式设这两项时，remember_token 是【一年有效】且【不带 Secure】——
# 明文 http 请求会把它发出去，等于给会话劫持留了一年窗口。
app.config["REMEMBER_COOKIE_SECURE"] = not _DEV_HTTP
app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=7)

# --- 自动注销：会话有效期 ---
# 为什么不能只靠 cookie 的过期时间：Max-Age 是浏览器自觉，抄一份 cookie 一直发就能
# 用到天荒地老。真正的判定写在 enforce_session_expiry() 里，每个请求都比对
# 签名 cookie 内记的“最后活动时间”和“本次登录的诞生时间”（这两个值改不了，
# 改它需要 SECRET_KEY）。
def _env_int(name, default):
    try:
        return int((os.environ.get(name) or "").strip() or default)
    except (TypeError, ValueError):
        return default


SESSION_KEY_LAST = "_la"        # 最后一次活动（epoch 秒）
SESSION_KEY_BORN = "_sb"        # 本次登录的诞生时间（epoch 秒）
SESSION_KEY_REM = "_rm"         # 登录时勾了“记住我”


def session_idle_seconds():
    """无操作多久算过期。下限 1 分钟：设 0 等于每次刷新都踢自己，多半是手滑。"""
    return max(60, min(86400, _env_int("SESSION_IDLE_MINUTES", 30) * 60))


def session_max_age_seconds():
    """就算一直在点，一次登录最长能用多久。防止“忘了退出的教室电脑”挂一整天。"""
    return max(600, min(30 * 86400, _env_int("SESSION_MAX_HOURS", 12) * 3600))


def remember_window_seconds():
    """勾了“记住我”的空闲/绝对时限都用 REMEMBER_COOKIE_DURATION 这个值。
    两处故意取同一个数：只要那个 cookie 还活着，用户就该被认出来；它一到期，
    会话也必死。否则“记住我 7 天”会变成“记住我 12 小时”，是个骗人的勾选框。"""
    d = app.config["REMEMBER_COOKIE_DURATION"]
    return max(600, int(d.total_seconds() if isinstance(d, timedelta) else d))


def human_window(seconds):
    s = int(seconds)
    if s < 3600:
        return "%d 分钟" % round(s / 60.0)
    if s < 86400:
        return "%.1f 小时" % (s / 3600.0) if s % 3600 else "%d 小时" % (s // 3600)
    return "%d 天" % round(s / 86400.0)


# 只对 permanent session 生效。全站没人显式设 session.permanent=True（前厅闸门反而是
# 显式设 False 的），所以这项实际不起作用；写在这里是为了“哪天真开了 permanent，
# 浏览器端的寿命和服务端判定说的是同一句话”，不要一个 2 小时一个 30 分钟。
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(seconds=session_idle_seconds())

# --- 浏览器端响应头：防点击劫持 / MIME 嗅探 / referer 泄露 / 强制 https / 禁收录 ---
# 站内搜索“别被搜索引擎收录”这件事由这里统一兜底：after_request 对【每一个】响应都跑，
# 包括静态文件、错误页、闸门那张伪 404 —— 少一层（比如哪天加了个 JSON 接口）也不会漏。
ROBOTS_TAG = "noindex, nofollow, noarchive, nosnippet, noimageindex"


def robots_txt_body():
    """/robots.txt 的内容。两种模式，由 ROBOTS_DISALLOW 决定（改完要 Reload）：

    1（默认）  Disallow: /  —— 求所有爬虫连抓都别抓，省 crawl 配额，也不给不守 noindex
              的采集站喂正文。
    0          只写 Allow: /，不拦抓取 —— “已经被收进索引、需要它掉出去”时的过渡模式。
              这里有个反直觉但很关键的点：**noindex 必须让爬虫抓到页面才读得到**，
              而 Disallow 恰恰阻止了抓取；被 Disallow 挡住的已收录 URL，Google 会保留成
              “已收录但被 robots.txt 屏蔽”的仅有标题的结果，反而掉不下去。
              所以历史页面没清干净时：设 ROBOTS_DISALLOW=0 放它来抓（每个响应都带
              noindex，见 set_security_headers），等索引清空后再改回 1。
              不想等就同时用 Search Console 的“移除”功能（临时 6 个月）。
    """
    if os.environ.get("ROBOTS_DISALLOW", "1").strip() != "0":
        return ("# 本站是班级内部站点，全部内容禁止搜索引擎收录。\n"
                "# 另有 X-Robots-Tag: noindex 与 <meta name=robots> 两层兜底。\n"
                "User-agent: *\nDisallow: /\n")
    return ("# 过渡模式（ROBOTS_DISALLOW=0）：允许抓取，好让爬虫读到每个响应里的\n"
            "# X-Robots-Tag: noindex，把已经收进去的历史页面清出去。清完请改回 1。\n"
            "User-agent: *\nAllow: /\n")


@app.after_request
def set_security_headers(response):
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    # 这里不给 setdefault：闸门页自己设过一次，值必须全站完全一致，
    # 否则“有的页面 noindex、有的没设”这种缝隙正是被爬虫捡走的地方。
    response.headers["X-Robots-Tag"] = ROBOTS_TAG
    return response

# --- 请求体上限：16MB 对一个纯文本论坛太大，256KB 足够发帖用 ---
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024
# Flask-WTF 把校验用的 token 存在 session 的这个键下
CSRF_SESSION_KEY = "csrf_token"

# --- 数据库 ---
# 默认放在项目目录下的 forum.db（和原来一致）；换目录/换库时用环境变量覆盖
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URI", "sqlite:///" + os.path.join(basedir, "forum.db"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# 老代码里的 SQLALCHEMY_POOL_SIZE / MAX_OVERFLOW / POOL_RECYCLE 在
# Flask-SQLAlchemy 3.x 中被完全忽略（实测 app.config['SQLALCHEMY_ENGINE_OPTIONS'] == {}），
# 统一挪到这里；SQLite 上调连接池意义有限，这里只要“连接存活管理”。
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
    "connect_args": {"check_same_thread": False, "timeout": 15},
}

# --- 出站请求走代理时的真实访客 IP：不开 ProxyFix 的话
#     get_remote_address() 可能永远拿到 PythonAnywhere 自己的 IP，
#     于是 200/minute 由全站访客共享，直接把所有人限死。---
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# --- 邮件（不配置就是不发货，代码里会降级）---
app.config.update(
    SMTP_HOST=os.environ.get("SMTP_HOST", ""),
    SMTP_PORT=int(os.environ.get("SMTP_PORT", "465") or 465),
    SMTP_USER=os.environ.get("SMTP_USER", ""),
    SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD", ""),
    MAIL_FROM=os.environ.get("MAIL_FROM", os.environ.get("SMTP_USER", "")),
    MAIL_DEBUG=os.environ.get("MAIL_DEBUG", "") == "1",
    SITE_NAME=os.environ.get("SITE_NAME", "班级论坛"),
    # 免费套餐的出网白名单只放 HTTP(S)，25/465/587 端口的 SMTP 连不出去。
    # 要用真邮件：申请把 SMTP 服务商加白名单，或升级到 Developer 套餐。
)

_LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]", "testserver")
# 允许的 Host 白名单，多个用逗号分隔（例如：zhanganning.pythonanywhere.com,www.example.com）
_ALLOWED_HOSTS = [h.strip().lower() for h in os.environ.get("ALLOWED_HOSTS", "").split(",")
                  if h.strip()]
_HOST_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*(?::\d{1,5})?$")


def _reject_host():
    """Host 头不可解析或不在白名单里：给自家 400 页，而不是 Werkzeug 那页
    “Bad request version” 裸文本（顺带把线上实测 400 的那种丑页也统一掉）。"""
    from werkzeug.exceptions import BadRequest
    return _http_error_page(BadRequest(), "400", 400)


@app.before_request
def enforce_https():
    """线上用 http:// 打开时，浏览器不会保存带 Secure 的 cookie（表现就是提交表单后
    密码被清空 + CSRF 失败），而且登录请求里的账密是明文过网的。
    PythonAnywhere 不会自动帮你 302 到 https，所以这里跳。
    request.is_secure 会因为 ProxyFix 读到 X-Forwarded-Proto，判断是准的。
    本地开发是 http://127.0.0.1:5000，按主机名豁免；万一要关掉：FORCE_HTTPS=0。"""
    if os.environ.get("FORCE_HTTPS", "1") == "0":
        return
    host = (request.host or "").lower()
    if host.split(":")[0] in _LOCAL_HOSTS:
        return
    # Location 里只能出现“我们自己认的 Host”。现在 PA 前置代理会替我们挡掉伪造
    # Host（实测返回 404），但那是别人的实现细节，不能当成自己的防线：
    # 以后换域名/换反代或用 IPs 直连时，这行就会把用户送到 https://evil.com。
    if not _HOST_RE.match(host):
        return _reject_host()
    if _ALLOWED_HOSTS and host not in _ALLOWED_HOSTS:
        return redirect("https://" + _ALLOWED_HOSTS[0] + request.path, 302)
    if request.is_secure:
        return
    return redirect("https://" + host + request.full_path.rstrip("?"), 302)


# 前厅闸门：必须在 CSRFProtect 之前注册。before_request 按注册顺序执行，
# 顺序为 https 跳转 → 闸门 → CSRF → 限流 → last_seen。
# 这样未解锁时连 POST 也是那张 404，而不是暴露“这里有个表单被 CSRF 拦了”。
from gate import bp as gate_bp, gate_before_request       # noqa: E402

def serve_facade_to_untrusted():
    """没开通的人 —— 未登录的（被转发过链接的同学、家长、爬虫）以及注册了但管理员
    还没点“开通”的账号 —— 看到的那套门面内容（demo.py）。

    做成两件事：真实内容必须有账号且被开通（前厅口令是全班共享的，凭口令就能看完全站
    等于没有登录墙）；同时门面看起来就是个正常论坛 —— 页面上不自称“示例/演示”，
    否则一转出去就破功。注册在闸门之前，不然外人只会拿到伪 404。

        未登录 / 未开通的账号   → 门面内容（后台那张卡片可以整体关掉这一层）
        开通了的账号、管理员     → 真实站点，这一层完全不参与
    只接管 FACADE_PAGES 里的内容页；名单外的路由（发帖表单、改密码、后台）行为一律不动。
    """
    if visitor_trusted() or not demo_mode_on():
        return None
    if request.method != "GET":
        if request.endpoint in FACADE_WRITE_OPEN:
            return None                 # 进门/出门/改自己密码/找回密码不能一起挡死
        flash("这个账号还没有开通，暂时不能发言。开通请找班主任。", "warning")
        return redirect(url_for("index"))
    if request.endpoint not in FACADE_PAGES:
        return None
    return _demo_response(request.path)


app.register_blueprint(gate_bp)
app.before_request(serve_facade_to_untrusted)
app.before_request(gate_before_request)

# --- CSRF：以前只靠 Flask-WTF 的表单自带 token，
#     所有不使用 form 对象的 POST（点赞、删帖、冻结用户、投票）完全裸奔。---
csrf = CSRFProtect(app)
csrf.exempt(gate_bp)          # /enter 是唯一免 CSRF 的写接口：跨站调用在 gate.py 里按 Origin 拒

# --- 限流：memory 存储；免费套餐只有 1 个 worker，够用但不持久 ---
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per minute"],
    storage_uri="memory://",
)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"

db = SQLAlchemy(app)

# ---------------------------------------------------------------- 内容清洗
# ───────────────────────────────────────────────────────── @提及 / 通知
# 提名的判定一律以“数据库里真实存在的用户名”为准：写 @xxx 而没这个人就不算提及，
# 也不变链接，避免把不存在的账号做成“看起来能用”的假链接。
MENTION_RE = re.compile(r"(?<![\w.@\-])@([\w.\-]{2,20})")
# 检测提及时先剥掉代码区：围栏里的 def f(x): @param、行内 `@decorator` 都不是在叫人
_MD_FENCE_RE = re.compile(r"(```.*?```|~~~.*?~~~)", re.S)
_MD_INLINE_RE = re.compile(r"`[^`\n]*`")
# 链接里的 @ 不是“叫人”：裸 URL 与 markdown 链接的目标都要剥掉，
# 否则 http://e.com/@xy 会既不发链接、又凭空给人发一条通知（口径必须与渲染一致）。
_BARE_URL_RE = re.compile(r'(?:https?|ftp|mailto)://[^\s<>\)"]+', re.I)
_MD_LINK_TARGET_RE = re.compile(r"(\]\()([^)]*)(\))")     # [文字](目标) → 只留括号壳
_MENTION_TAIL = ".,;:!?)（。」"

_mention_cache = {"map": {}, "at": 0.0}


def mention_map(ttl=60.0):
    """小写用户名 → 真实用户名。带 TTL 缓存：每条正文都要问“这人存在吗”，
    逐条查库在免费套餐单 worker 上是白送的开销；改名/注册后最多 60 秒生效。"""
    now = time.monotonic()
    if _mention_cache["map"] and now - _mention_cache["at"] < ttl:
        return _mention_cache["map"]
    try:
        if "user" not in existing_tables():
            return _mention_cache["map"]
        rows = db.session.execute(text("SELECT username FROM user")).all()
    except Exception:                       # CLI / 无库 / 无应用上下文：沿用旧值
        return _mention_cache["map"]
    out = {(r[0] or "").lower(): r[0] for r in rows if r[0]}
    if out:
        _mention_cache["map"] = out
        _mention_cache["at"] = now
    return out


def mention_cache_clear():
    """注册/改名后调用，免得新账号 60 秒内 @ 不出来。"""
    _mention_cache["at"] = 0.0


def strip_code_for_mentions(raw):
    """把“不会被渲染成提及”的区域换成等长空白：代码（围栏/行内）与链接目标。
    等长替换保证字符偏移和原文一致，便于将来对齐。"""
    out = _MD_FENCE_RE.sub(lambda m: " " * len(m.group(1)), raw or "")
    out = _MD_INLINE_RE.sub(lambda m: " " * len(m.group(0)), out)
    out = _MD_LINK_TARGET_RE.sub(lambda m: m.group(1) + " " * len(m.group(2)) + m.group(3), out)
    return _BARE_URL_RE.sub(lambda m: " " * len(m.group(0)), out)


def mentioned_usernames(raw):
    """从原文解析出真实存在的用户名，按出现顺序去重。"""
    known = mention_map()
    seen, out = set(), []
    for m in MENTION_RE.finditer(strip_code_for_mentions(raw)):
        name = m.group(1).rstrip(_MENTION_TAIL)
        real = known.get(name.lower())
        if real and real.lower() not in seen:
            seen.add(real.lower())
            out.append(real)
    return out


def _linkify_mentions(html_text):
    """渲染阶段把 @name 变成 /u/name 链接；<pre>/<code> 段整段跳过。"""
    known = mention_map()
    if not known:
        return html_text

    def one(m):
        name = m.group(1).rstrip(_MENTION_TAIL)
        real = known.get(name.lower())
        if not real:
            return m.group(0)
        safe = html_mod.escape(real, quote=True)
        return '<a href="/u/%s" class="mention post-ref">@%s</a>' % (safe, safe)

    return _text_pass(html_text, lambda seg: MENTION_RE.sub(one, seg))


def excerpt_of(text, n=90):
    """通知里带的一小段摘要：压掉换行/markdown 记号，纯文本。"""
    t = re.sub(r"[`*_>#\[\]]+", " ", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n]


def notify(user_id, kind, dedup, actor=None, excerpt="", post_id=None,
           comment_id=None, announcement_id=None, commit=True, exclude=None):
    """写一条通知，重复调用同一 dedup 只落一条。
    不给“自己叫自己”发通知；收件人已冻结就跳过。
    exclude：没有 actor 对象时要排除的收件人（公告发布者就是这种情况）。"""
    if not user_id or user_id == exclude \
            or (actor is not None and getattr(actor, "id", None) == user_id):
        return False
    try:
        from sqlalchemy import select as _sel
        dup = db.session.execute(
            _sel(Notification.id).where(Notification.user_id == user_id,
                                        Notification.dedup == dedup)).first()
        if dup:
            return False
        who = db.session.get(User, user_id)
        if who is None or not who.is_active:
            return False
        db.session.add(Notification(
            user_id=user_id, kind=kind[:12], dedup=dedup[:90],
            actor_id=getattr(actor, "id", None),
            actor_name=(getattr(actor, "username", "") or "")[:150],
            excerpt=excerpt[:200], post_id=post_id, comment_id=comment_id,
            announcement_id=announcement_id))
        if commit:
            db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        app.logger.exception("通知写入失败：%s %s", kind, dedup)
        return False


def notify_mentions(raw_text, actor, post_id, comment_id=None):
    """@提及 → 通知。dedup 里带上被叫的人，同一帖里 @两次只发一条。"""
    n = 0
    ex = excerpt_of(raw_text)
    for name in mentioned_usernames(raw_text):
        target = User.query.filter(db.func.lower(User.username) == name.lower()).first()
        if target is None:
            continue
        dedup = "mention:%s:%s:%s" % (post_id, comment_id or "-", target.id)
        if notify(target.id, "mention", dedup, actor=actor, excerpt=ex,
                  post_id=post_id, comment_id=comment_id):
            n += 1
    return n


def watch_post(post_id, user_id):
    """订阅某帖（幂等）。"""
    if not post_id or not user_id:
        return
    try:
        from sqlalchemy import select as _sel
        if db.session.execute(_sel(PostWatch.id).where(
                PostWatch.post_id == post_id, PostWatch.user_id == user_id)).first():
            return
        db.session.add(PostWatch(post_id=post_id, user_id=user_id))
    except Exception:
        db.session.rollback()
        app.logger.exception("订阅写入失败")


def notify_new_comment(post, comment, actor):
    """新回答 → 楼主 + 订阅者（排除说话人自己）。"""
    ex = excerpt_of(comment.body)
    ids = {post.user_id} | {w.user_id for w in post.watches}
    n = 0
    for uid in ids:
        if notify(uid, "reply", "reply:%s:%s" % (post.id, comment.id), actor=actor,
                  excerpt=ex, post_id=post.id, comment_id=comment.id):
            n += 1
    return n


# 原来每次调用 bleach.clean 都会重建一遍 sanitizer；这里做成模块级对象，
# 顺便收紧规则：不允许 <p>/<br>（正文按纯文本渲染，避免与 whitespace-pre-wrap 叠成双换行），
# <a> 只留 href，协议锁死 http/https/mailto，并给外链加 rel="ugc nofollow"。
Cleaner = bleach.Cleaner(
    # 放开结构性标签 + class（class 不会带来执行风险；href/协议继续受限）
    tags=["b", "i", "u", "em", "strong", "a", "p", "br", "pre", "code", "div", "span",
          "blockquote", "h1", "h2", "h3", "h4", "ul", "ol", "li", "hr", "del",
          "img", "table", "thead", "tbody", "tr", "th", "td"],
    attributes={"a": ["href", "title", "rel"], "img": ["src", "alt", "title", "loading", "referrerpolicy"], "*": ["class"]},
    protocols=["http", "https", "mailto"],
    strip=True,
)

MD = mistune.create_markdown(escape=True, hard_wrap=True,
                          plugins=["table", "strikethrough", "url"])   # 单个换行即 <br>
PYG_FMT = HtmlFormatter(style="monokai", cssclass="hl", linenos="inline")
FENCE_RE = re.compile(r'<pre><code(?: class="language-([\w+#.\-]{1,24})")?>(.*?)</code></pre>',
                      re.S)
BARE_FENCE_RE = re.compile(r'<pre><code>(.*?)</code></pre>', re.S)


def _hl(code_escaped, lang):
    """服务端高亮：不引入前端 hljs（CSP 只允许同源脚本，且手机端少一次 JS 开销）。"""
    src = html_mod.unescape(code_escaped).rstrip("\n")
    name = (lang or "").strip().lower()
    lexer = None
    if name:
        try:
            lexer = get_lexer_by_name(name)
        except ClassNotFound:
            lexer = None
    if lexer is None:
        lexer = TextLexer()
    return pyg_highlight(src, lexer, PYG_FMT).rstrip("\n")


# ---- 正文后处理：互链 / 外链 rel / 图片属性 ----
# 定序：先清洗（bleach）→ 再互链 → 再装饰。互链只在“代码区之外”的文本里做，
# 因为代码里的 #123 通常是注释，不该变成站内链接。
CODE_BLOCK_RE = re.compile(r"(<pre[^>]*>.*?</pre>|<code[^>]*>.*?</code>)", re.S)
REF_RE = re.compile(r"(?<![\w/#])#(\d{1,6})\b")
A_OPEN_RE = re.compile(r"(<a\b[^>]*>)", re.I)
IMG_RE = re.compile(r"<img\b([^>]*)>", re.I)
HREF_VAL_RE = re.compile(r"href\s*=\s*([^\s>]+)", re.I)
QUOTE_CHARS = "\"'"


def _linkify_plain(text):
    return REF_RE.sub(lambda m: '<a href="/post/%s" class="post-ref">#%s'
                      '</a>' % (m.group(1), m.group(1)), text)


TAG_SPLIT_RE = re.compile(r"(<[^>]*>)")
# 整段不许动的区域：代码块，以及已经成形的链接（里面还有属性与链接文字）
SKIP_ZONE_RE = re.compile(r"(<a\b[^>]*>.*?</a>|<pre[^>]*>.*?</pre>|<code[^>]*>.*?</code>)", re.S)


def _text_pass(html_text, fn):
    """只在【标签之间的文本】上执行替换：既跳过 <pre>/<code>，也绝不碰标签内部的属性值。

    为什么必须这样：_finish 里替换发生在 bleach 之后，往属性值里插 `<a ...>`
    会把那条标签的引号撑破（用户写 [x](http://e.com/@x) 且恰好有个用户叫 x 时，
    就是一次 HTML 结构注入）。到这一步用户手写的 < 已被 bleach 转义成 &lt;，
    所以“看起来像标签”的片段只可能是我们自己生成的标签。"""
    out = []
    for i, zone in enumerate(SKIP_ZONE_RE.split(html_text)):
        if i % 2:                     # <a>/<pre>/<code> 整段原样：里面塞 <a> 会造成嵌套锚点
            out.append(zone)
            continue
        out.append("".join(
            piece if (len(piece) > 2 and piece[0] == "<" and piece[-1] == ">")
            else fn(piece)
            for piece in TAG_SPLIT_RE.split(zone)))   # 标签内部（属性值）也不碰
    return "".join(out)


def _linkify_refs(html_text):
    return _text_pass(html_text, _linkify_plain)


def _is_external(tag):
    m = HREF_VAL_RE.search(tag)
    if not m:
        return False
    val = m.group(1).strip(QUOTE_CHARS).lower()
    return val.startswith("http://") or val.startswith("https://") or val.startswith("mailto:")


def _decorate_links(cleaned):
    """只给站外链接加 ugc/nofollow；站内互链不需要，加了还会影响样式匹配。"""
    def rep(m):
        tag = m.group(1)
        if _is_external(tag) and "nofollow" not in tag.lower():
            tag = tag[:-1] + ' rel="ugc nofollow">'
        return tag
    return A_OPEN_RE.sub(rep, cleaned)


def _decorate_imgs(cleaned):
    """图片懒加载 + 不发 referer（避免点开后被第三方站点串身份）。"""
    def rep(m):
        attrs = m.group(1)
        low = attrs.lower()
        if "loading" not in low:
            attrs += ' loading="lazy"'
        if "referrerpolicy" not in low:
            attrs += ' referrerpolicy="no-referrer"'
        return "<img" + attrs + ">"
    return IMG_RE.sub(rep, cleaned)


def _finish(html_text):
    """统一出口：清洗 → 互链（代码区除外）→ 外链 rel → 图片属性。"""
    cleaned = Cleaner.clean(html_text or "")
    cleaned = _linkify_refs(cleaned)
    cleaned = _linkify_mentions(cleaned)   # @人名 → /u/人名（代码区跳过）
    cleaned = _decorate_links(cleaned)
    cleaned = _decorate_imgs(cleaned)
    return cleaned


HL_MAX_CHARS = 20000          # 超长代码块不再 tokenize：别让高亮变成免费档的 CPU 放大器
HL_MAX_LINES = 400


def _hl_guarded(code_escaped, lang):
    src = html_mod.unescape(code_escaped or "")
    if len(src) > HL_MAX_CHARS or src.count("\n") > HL_MAX_LINES:
        # 这里必须自己转义：内容之后还会被当 HTML 走一遍，不能因为“降级”就把
        # 用户写的标签当文本直出（>2 万字符的代码块是最好用的探针）
        return "<pre><code>" + html_mod.escape(src) + "</code></pre>"
    return _hl(code_escaped, lang)


def render_body(raw, language=None):
    """正文/评论渲染管线：markdown → 围栏逐个高亮 → #id 互链 → 清洗加 rel。"""
    out = MD(raw or "")
    out = FENCE_RE.sub(lambda m: _hl_guarded(m.group(2), m.group(1)), out)
    out = BARE_FENCE_RE.sub(lambda m: _hl_guarded(m.group(1), language), out)
    return _finish(out)


def clean_html(raw):
    """纯文本路径（不做 markdown），仍走同一套清洗。"""
    return _finish(raw or "")


# ---------------------------------------------------------------- 模型

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    # 账号有没有被管理员“开通”。默认 False：新注册的人、以及升级前就存在的老账号，
    # 都先只看到门面内容（demo.py），老师在“用户管理”里逐个打开才算信任。
    # 管理员自己不看这一列（见 visitor_trusted），否则一上线就把自已锁在门外。
    # 老库靠 ensure_schema 的 ALTER 补这列（默认 0），所以升级后记得跑一次
    # flask --app app ensure-schema，再进后台按名单开通。
    is_trusted = db.Column(db.Boolean, default=False, nullable=False)
    email_verified = db.Column(db.Boolean, default=True, nullable=False)
    failed_logins = db.Column(db.Integer, default=0, nullable=False)
    session_version = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime)
    last_seen = db.Column(db.DateTime, default=utcnow)
    created_at = db.Column(db.DateTime, default=utcnow)
    posts = db.relationship("Post", backref="author", lazy=True)
    comments = db.relationship("Comment", backref="author", lazy=True)
    likes = db.relationship("Like", backref="user", lazy=True,
                            cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        # 密码一变，已发出的会话 cookie 全部作废（含攻击者手里的）
        self.session_version = (self.session_version or 0) + 1

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > utcnow())

    def register_failure(self):
        """连续失败 5 次锁 10 分钟，配合 /login 的限流把撞库成本抬起来。"""
        self.failed_logins = (self.failed_logins or 0) + 1
        if self.failed_logins >= 5:
            self.locked_until = utcnow() + timedelta(minutes=10)
            self.failed_logins = 0

    def register_success(self):
        self.failed_logins = 0
        self.locked_until = None

    def initial(self):
        return (self.username or "?").strip()[:1].upper()


post_tag = db.Table("post_tag",
    db.Column("post_id", db.ForeignKey("post.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True))


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    slug = db.Column(db.String(40), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    posts = db.relationship("Post", secondary=post_tag, back_populates="tags")


TAG_RE = re.compile(r"^[\w.+#\-]{1,28}$")


def slugify(name):
    """保留中文等非 ASCII：否则 #递归 这类标签会被清成空 slug。"""
    keep = re.sub("[^0-9a-z" + chr(0x4e00) + "-" + chr(0x9fff) + ".+#_-]+", "-",
                 name.strip().lower(), flags=re.UNICODE)
    return keep.strip("-")[:40]


def parse_tags(raw):
    """逗号/空格分隔，最多 3 个；非法项静默丢掉，绝不拼进 SQL。"""
    out = []
    for piece in re.split(r"[,，;；\s]+", raw or ""):
        name = piece.strip().lstrip("#")[:28]
        if not name or not TAG_RE.match(name):
            continue
        if name.lower() not in [o[0].lower() for o in out]:
            out.append((name, slugify(name)))
        if len(out) >= 3:
            break
    return out


def attach_tags(post, raw):
    tags = []
    for name, slug in parse_tags(raw):
        t = Tag.query.filter(db.func.lower(Tag.slug) == slug).first()
        if t is None:
            t = Tag(name=name, slug=slug)
            db.session.add(t)
            db.session.flush()
        tags.append(t)
    post.tags = tags


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    # 冗余计数列：原来首页每张卡片都访问 post.comments / post.likes 触发 len()，
    # 实测“10 条帖子 = 23 条 SQL”。改成读计数列后一次查询搞定。
    comments_count = db.Column(db.Integer, default=0, nullable=False)
    likes_count = db.Column(db.Integer, default=0, nullable=False)
    language = db.Column(db.String(24))                   # python / c / godoc …
    is_solved = db.Column(db.Boolean, default=False, nullable=False)
    accepted_comment_id = db.Column(db.Integer)           # 采纳的回答（不建 FK，避免老库级联麻烦）
    solved_at = db.Column(db.DateTime)
    comments = db.relationship("Comment", backref="post", lazy=True,
                               cascade="all, delete-orphan")
    tags = db.relationship("Tag", secondary=post_tag, back_populates="posts", lazy="selectin")
    likes = db.relationship("Like", backref="post", lazy=True,
                            cascade="all, delete-orphan")
    # 删帖时订阅一起走：否则 orphan 的 watch 会让通知指向不存在的帖子
    watches = db.relationship("PostWatch", backref="post", lazy=True,
                              cascade="all, delete-orphan")

    def sanitize_content(self):
        """content_html 由 content + language 派生，随时可用 backfill-render 重算。"""
        self.content_html = render_body(self.content, self.language)


class GateAttempt(db.Model):
    """闸门的口令尝试记录。必须落库：PA 会有多个 worker 进程，内存计数会被打散。"""
    id = db.Column(db.Integer, primary_key=True)
    bucket = db.Column(db.String(80), nullable=False, index=True)   # ip:<x> / sess:<x> / global
    at = db.Column(db.DateTime, default=utcnow, nullable=False)
    ok = db.Column(db.Boolean, default=False, nullable=False)


class AuditLog(db.Model):
    """操作审计：谁、从哪个 IP、什么时候、改了哪一行。

    两条设计上的取舍，别改回去：
    1. user_id 不建外键、actor 存“当时的用户名快照”。
       删用户/改用户名时，审计记录必须留着且仍然说得出是谁 —— 建了外键，
       级联删除会把痕迹一起抹掉，等于谁都能销毁自己的记录。
    2. 表里不存字段的新值（更新只存“改了哪些列名”），密码哈希一类
       永远不进这张表：它比 forum.db 本身更怕被翻出来看。
    """
    # rowid 在 SQLite 里会被复用（INTEGER PRIMARY KEY 不带 AUTOINCREMENT）：
    # 清理过旧记录之后，同一个 id 可能代表另一条事件 → 别把 audit id 当长期引用，
    # 要认条目就用 (at, actor, action, table, row_id)。
    id = db.Column(db.Integer, primary_key=True)
    at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    user_id = db.Column(db.Integer)                        # 可为空：匿名或系统操作
    actor = db.Column(db.String(150), nullable=False, default="", index=True)
    actor_admin = db.Column(db.Boolean, default=False, nullable=False)
    ip = db.Column(db.String(64), nullable=False, default="", index=True)
    action = db.Column(db.String(12), nullable=False)      # create/update/delete/login/…
    table = db.Column(db.String(40), nullable=False, default="", index=True)
    row_id = db.Column(db.String(24), nullable=False, default="")
    detail = db.Column(db.String(280), nullable=False, default="")
    endpoint = db.Column(db.String(60), nullable=False, default="")
    __table_args__ = (db.Index("ix_audit_table_row", "table", "row_id"),)


class CommentLike(db.Model):
    """回答（评论）的点赞；与帖子点赞分表，避免共用的唯一约束互相干扰。"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    comment_id = db.Column(db.Integer,
                           db.ForeignKey("comment.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "comment_id", name="unique_comment_like"),)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(24))
    likes_count = db.Column(db.Integer, default=0, nullable=False)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer,
                        db.ForeignKey("post.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    likes = db.relationship("CommentLike", backref="comment", lazy=True,
                            cascade="all, delete-orphan")

    def sanitize_body(self):
        self.body_html = render_body(self.body, self.language)


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer,
                        db.ForeignKey("post.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="unique_like"),)


class VoteItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    options = db.relationship("VoteOption", backref="vote_item", lazy=True,
                              cascade="all, delete-orphan")
    records = db.relationship("VoteRecord", backref="vote_item", lazy=True,
                              cascade="all, delete-orphan")

    @property
    def total_votes(self):
        """进度条的分母必须和分子同源。
        原来分母是 records|length（还顺手把全部投票记录加载进内存），
        分子是 option.vote_count，两套数据一旦漂移就能画出 200% 的进度条。"""
        return sum(o.vote_count or 0 for o in self.options)

    def percent(self, option):
        total = self.total_votes
        if not total:
            return 0.0
        return round((option.vote_count or 0) * 100.0 / total, 1)


class VoteOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    option_text = db.Column(db.String(200), nullable=False)
    vote_count = db.Column(db.Integer, default=0, nullable=False)
    vote_item_id = db.Column(db.Integer,
                             db.ForeignKey("vote_item.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    # 投票记录引用的是“选项”。不声明这段关系，SQLAlchemy 就会先删选项再删记录，
    # 在老库（表上没有 ON DELETE CASCADE）里立刻 FOREIGN KEY constraint failed。
    records = db.relationship("VoteRecord", back_populates="option", lazy=True,
                              cascade="all, delete-orphan")


class VoteRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    vote_item_id = db.Column(db.Integer,
                             db.ForeignKey("vote_item.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    vote_option_id = db.Column(db.Integer,
                               db.ForeignKey("vote_option.id", ondelete="CASCADE"),
                               nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    option = db.relationship("VoteOption", back_populates="records")
    __table_args__ = (db.UniqueConstraint("user_id", "vote_item_id",
                                          name="unique_user_vote"),)


class Notification(db.Model):
    """站内通知：@我、我关注的帖子有新回答、我的回答被采纳、新公告。
    免费档发不出邮件，站内信是唯一可用的提醒通道。"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    kind = db.Column(db.String(12), nullable=False)          # mention/reply/accept/announce
    dedup = db.Column(db.String(90), nullable=False)         # 幂等键，见 notify()
    actor_id = db.Column(db.Integer)          # 不建外键：删号不该顺手抹掉通知痕迹
    actor_name = db.Column(db.String(150), nullable=False, default="")
    post_id = db.Column(db.Integer)
    comment_id = db.Column(db.Integer)
    announcement_id = db.Column(db.Integer)
    excerpt = db.Column(db.String(200), nullable=False, default="")
    at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    read_at = db.Column(db.DateTime, index=True)             # 空 = 未读
    __table_args__ = (db.UniqueConstraint("user_id", "dedup", name="unique_notification"),)


class PostWatch(db.Model):
    """“这帖有新动静叫我一声”。楼主与每个回答者自动订阅，也可手动关注/取关。"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    post_id = db.Column(db.Integer,
                        db.ForeignKey("post.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    at = db.Column(db.DateTime, default=utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="unique_post_watch"),)


class Announcement(db.Model):
    """组织内公告：可置顶、可过期、可下架；正文走同一套渲染管线（支持 markdown/代码块）。"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    body_html = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    edited_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    pinned = db.Column(db.Boolean, default=False, nullable=False)
    expires_at = db.Column(db.DateTime)         # 空 = 不过期；过期后不再走横幅
    user = db.relationship("User", backref="announcements", lazy=True)

    def live(self, now=None):
        now = now or utcnow()
        return bool(self.is_active) and (self.expires_at is None or self.expires_at > now)

    def sanitize_body(self):
        self.body_html = render_body(self.body, None)


class SiteFlag(db.Model):
    """站点级开关，一行一个键。现在只有 demo_mode（未登录访客看虚拟数据还是看真实内容）。

    为什么不放环境变量：这类东西要在后台点一下就立刻生效（环境变量得 Reload），
    而且必须留下“谁在什么时候改的”——改真实数据/虚拟数据是会被人问的。
    value 用文本不用布尔：以后想加“只对某些年段开放”这种第三种状态不用改表。
    key 是主键 → 老库里不存在这张表，靠 flask --app app ensure-schema 建。"""
    key = db.Column(db.String(40), primary_key=True)
    value = db.Column(db.String(40), nullable=False, default="")
    updated_by = db.Column(db.Integer)             # 不建外键：删号不能把“谁改的”一起删掉
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


@login_manager.user_loader
def load_user(user_id):
    try:
        user = db.session.get(User, int(user_id))
    except Exception:
        # 老库缺列（升级后没跑 flask --app app ensure-schema）时，这一句就会抛：
        # 整个站点会连带 500。退回“未登录”—— 对门面模式来说正好等于最安全的状态，
        # 而不是把一个班全锁在错误页外面。日志里留一行指明是列的问题。
        db.session.rollback()
        app.logger.warning("读用户 %s 失败：多半是 user 表缺列，跑一次 flask --app app ensure-schema",
                           user_id)
        return None
    # 被冻结的用户立刻变成匿名访客，不需要等 cookie 过期
    if user is not None and not user.is_active:
        return None
    return user


def existing_tables():
    try:
        return set(db.inspect(db.engine).get_table_names())
    except Exception:
        return set()


def sync_post_counts(post_id):
    """重算单帖的评论/点赞计数列，写操作之后调用。"""
    if post_id is None:
        return
    tables = existing_tables()
    if "post" not in tables:
        return
    # 老库里 comment / like 可能还没建：缺哪张子表就把哪项写成 0，而不是整体跳过
    post_columns = {row[1] for row in
                    db.session.execute(text("PRAGMA table_info(post)"))}
    sets, params = [], {"p": post_id}
    for column, source in (("comments_count", "comment"), ("likes_count", "like")):
        if column not in post_columns:
            continue
        if source in tables:
            sets.append('%s = (SELECT count(*) FROM "%s" WHERE post_id = :p)' % (column, source))
        else:
            sets.append("%s = 0" % column)
    if not sets:
        return
    db.session.execute(text("UPDATE post SET %s WHERE id = :p" % ", ".join(sets)), params)


def sync_comment_likes(comment_id):
    """回答点赞计数列（和帖子计数列同一套路，避免详情页 N+1）。"""
    if comment_id is None:
        return
    tables = existing_tables()
    if "comment" not in tables or "comment_like" not in tables:
        return
    db.session.execute(text(
        "UPDATE comment SET likes_count = "
        "(SELECT count(*) FROM comment_like WHERE comment_id = :p) WHERE id = :p"),
        {"p": comment_id})


def order_answers(post):
    """采纳优先 → 点赞数 → 时间。"""
    accepted = post.accepted_comment_id
    return sorted(post.comments,
                  key=lambda c: (0 if c.id == accepted else 1,
                                 -(c.likes_count or 0), c.timestamp))



# ---------------------------------------------------------------- 操作审计
# 挂在 Session 的 flush 上，而不是在每个路由里手写一遍：
# 这个应用有 20 多个写入口（点赞/采纳/投票/冻结/删除…），漏一个就等于那份操作没人知道。
# 事件收集在 after_flush，落库在 after_commit —— 事务真成功了才留下记录，
# 回滚掉的（比如删帖子撞到外键）不会在审计里留下“已删除”的假象。

AUDIT_SKIP_TABLES = {
    "audit_log",        # 自己的写入当然不能再记一次
    "site_flag",        # 开关只有一行，逐条记“value 变了”不如 /admin/display_mode 那条人话
    "gate_attempt",     # 口令尝试本来就逐条落库，再记一遍会把真事件淹掉
    "post_tag",         # 打标签是帖子的属性，跟着 post 那条记就够了
}
# 只有这些列发生变化时不记：纯属系统记账，不是“有人改了数据”
AUDIT_QUIET_COLUMNS = {
    "user": {"last_seen"},
    "post": {"comments_count", "likes_count", "content_html"},
    "comment": {"likes_count", "body_html"},
    "vote_option": {"vote_count"},
}
# 注：这里没有“哪些列可以记值”的白名单 —— 规则更简单：任何列的值都不记。
# 更新条目只写“改了哪几个列名”，新建/删除只写标题或用户名（本来就是列表页可见的短字段）。
def _audit_ip_mode():
    """每次读环境变量（而不是 import 时定值）：改了 PA 变量点 Reload 就生效，
    测试里也能按场景切。"""
    return (os.environ.get("AUDIT_IP", "full") or "full").strip().lower()


def _audit_now():
    """审计时间：站点整体是 naive UTC 口径（见 utcnow），显示时再过 cn_time()。"""
    return utcnow()


def _mask_ip(ip):
    """AUDIT_IP=masked 时只留网段：IPv4 去掉最后一段，IPv6 留前 3 组。"""
    if ":" in ip:                                   # IPv6
        parts = ip.split(":")
        return ":".join(parts[:3]) + ":**" if len(parts) > 3 else ip
    parts = ip.split(".")
    return ".".join(parts[:3]) + ".*" if len(parts) == 4 else ip


def audit_ip():
    """真实访客 IP。PythonAnywhere 在前面好几层代理，客户端能自己塞
    X-Forwarded-For，所以取“最右一项”（只有代理补的那段可信），
    口径与 gate.client_bucket() 一致。"""
    mode = _audit_ip_mode()
    if mode == "none":
        return ""
    xff = request.headers.get("X-Forwarded-For") or ""
    ip = (xff.split(",")[-1].strip() if xff else (request.remote_addr or ""))[:64]
    return _mask_ip(ip) if mode == "masked" and ip else ip


def _audit_actor():
    """返回 (user_id, actor 文字, 当时是否管理员)。CLI/启动期没有请求上下文 → 记成系统。

    注意 current_user 在无请求上下文时可能是 None（flask_login 没解析出 Anon），
    直接取 .is_authenticated 会 AttributeError，所以全部走 getattr。"""
    try:
        user = current_user
        if user is not None and getattr(user, "is_authenticated", False):
            return (getattr(user, "id", None), (getattr(user, "username", "") or "?")[:150],
                    bool(getattr(user, "is_admin", False)))
        return (None, "匿名" if has_request_context() else "系统", False)
    except RuntimeError:                 # 无请求上下文：init-db / backfill / 命令行
        return (None, "系统", False)


def _audit_snippet(obj):
    """给记录配一句人话：只取“标题/用户名”这类本来就是公开或短字段的标识，
    正文(body/content)、邮箱、描述一律不进审计 —— 那是内容审查，不是操作审计。"""
    table = getattr(obj, "__tablename__", "")
    pk = str(getattr(obj, "id", "") or "")[:24]
    if table == "post":
        label = "《%s》" % (getattr(obj, "title", "") or "")[:60]
    elif table == "user":
        label = "@%s" % (getattr(obj, "username", "") or "")[:30]
    elif table == "vote_item":
        label = "投票《%s》" % (getattr(obj, "title", "") or "")[:40]
    elif table == "tag":
        label = "#%s" % (getattr(obj, "name", "") or "")[:30]
    else:                                   # comment / like / vote_option … 用 id 说话
        label = ""
    return table, pk, label


def _changed_columns(obj):
    """本次 flush 里该对象真正变了哪些“列”（只看列名，不碰值）。

    state.attrs 连关系（relationship）一起给，级联删除时会冒出一堆
    likes/comments 这种名字，读起来像“有人改了点赞关系”——所以按表上的列名过滤。
    tags 是唯一想保留的关系名（改标签确实是人为操作）。"""
    try:
        cols = set(obj.__table__.columns.keys())
    except Exception:
        return []
    out = []
    for attr in db.inspect(obj).attrs:
        key = getattr(attr, "key", None)
        if key not in cols and key != "tags":
            continue
        try:
            if attr.history.has_changes():
                out.append(key)
        except Exception:
            continue
    return out


# flask-sqlalchemy 的 db.session 是 ScopedSession：不能在 import 时调用 db.session()
# （没有应用上下文会 RuntimeError），要拿它背后 sessionmaker 的 Session 子类。
try:
    _AuditSession = db.session.session_factory.class_
except AttributeError:                            # 版本差异兜底：直接挂基类
    from sqlalchemy.orm import Session as _AuditSession


@event.listens_for(_AuditSession, "after_flush", propagate=True)
def _audit_collect(session, flush_context):
    """把这一批改动翻译成审计条目，先攒着（不能在这里写库：
    flush 进行中再 session.flush() 会 “Session is already flushing”，实测）。
    真落库在 after_commit —— 业务回滚时根本走不到那儿，不会留假记录。"""
    if session.info.get("audit_inside"):
        return
    buf = session.info.setdefault("audit_pending", [])

    def push(action, obj):
        table, row_id, label = _audit_snippet(obj)
        if table in AUDIT_SKIP_TABLES:
            return
        if action == "update":
            changed = _changed_columns(obj)
            quiet = AUDIT_QUIET_COLUMNS.get(table, set())
            if not changed or set(changed) <= quiet:
                return                    # 只有计数列自己动了，不是人为改动
            names = ",".join(sorted(c for c in changed if c not in quiet)[:8])
            detail = "%s#%s 改了 %d 列：%s" % (table, row_id or "?", len(names.split(",")), names)
        elif action == "create":
            detail = ("新建 " + label).strip() or "新建记录"
        else:
            detail = ("删除 " + label).strip() or "删除记录"
        uid, actor, is_admin = _audit_actor()
        buf.append({
            "at": _audit_now(), "user_id": uid, "actor": actor[:150], "actor_admin": is_admin,
            "ip": audit_ip() if has_request_context() else "", "action": action,
            "table": table[:40], "row_id": row_id or "-", "detail": detail[:280],
            "endpoint": (request.endpoint or "")[:60] if has_request_context() else "",
        })

    for obj in list(session.new):
        push("create", obj)
    for obj in list(session.deleted):
        push("delete", obj)
    for obj in list(session.dirty):
        push("update", obj)


_AUDIT_ERR_SHOWN = False


@event.listens_for(_AuditSession, "after_commit", propagate=True)
def _audit_emit(session):
    """业务事务已提交 → 用另一个 Session（另一条连接）把审计写进去。
    同一个 session 在 committed 状态下再发 SQL 会 InvalidRequestError，所以必须新开。"""
    pending = session.info.pop("audit_pending", None)
    if not pending:
        return
    if hasattr(session, "get_bind"):
        bind = session.get_bind()
    else:
        bind = None
    try:
        from sqlalchemy.orm import Session as SASession
        with SASession(bind) as writer:
            writer.add_all([AuditLog(**row) for row in pending])
            writer.commit()
    except Exception:
        # 审计写失败不能把用户操作带下水；但必须留在 error.log 里看得见。
        # 只详细打一次：没跑 ensure-schema 时每条写都会失败，刷屏会埋掉别的日志。
        global _AUDIT_ERR_SHOWN
        if not _AUDIT_ERR_SHOWN:
            _AUDIT_ERR_SHOWN = True
            app.logger.exception("审计写入失败（%d 条）——多半是还没跑 flask --app app ensure-schema", len(pending))
        else:
            app.logger.warning("审计仍在写入失败（已省略堆栈），共 %d 条", len(pending))


@event.listens_for(_AuditSession, "after_rollback", propagate=True)
def _audit_drop(session):
    """回滚了就把攒着的条目丢掉，别留给下一次 commit（会记成“删了但没删”）。"""
    session.info.pop("audit_pending", None)


def _audit_row(action, detail, table, row_id):
    uid, actor, is_admin = _audit_actor()
    return AuditLog(at=_audit_now(), user_id=uid, actor=actor[:150], actor_admin=is_admin,
                    ip=audit_ip() if has_request_context() else "", action=action[:12],
                    table=(table or "-")[:40], row_id=str(row_id or "-")[:24],
                    detail=(detail or "")[:280],
                    endpoint=(request.endpoint or "")[:60] if has_request_context() else "")


def audit_event(action, detail="", table="", row_id=""):
    """不属于“对象增删改”的事件级记录：登录成功/失败、退出、前厅解锁。
    这类必须立刻独立落库：登录失败之后往往再也没有别的写操作，等不到 commit。"""
    try:
        from sqlalchemy.orm import Session as SASession
        with SASession(db.engine) as writer:
            writer.add(_audit_row(action, detail, table, row_id))
            writer.commit()
    except Exception:
        app.logger.exception("审计事件落库失败：%s %s", action, detail[:60])


# ------------------------------------------------ 审计自动过期（默认 30 天）
def audit_retention_days():
    """保留几天的审计。AUDIT_RETENTION_DAYS 改完要 Reload 才生效（PA 没有热重载）。
    地板设 7 天，和后台手动清理同一条线：设成 0/1 天基本等于“边写边删”，
    真出事时第二天就没证据可查了，多半是手滑而不是有意。"""
    return max(7, min(3650, _env_int("AUDIT_RETENTION_DAYS", 30)))


def audit_expired_count(days=None):
    """已经过了保留期、还赖在表里的条数。走 at 上的索引，不扫全表。"""
    cut = utcnow() - timedelta(days=audit_retention_days() if days is None else days)
    try:
        return db.session.query(AuditLog.id).filter(AuditLog.at < cut).count()
    except Exception:
        db.session.rollback()
        return 0


def purge_expired_audit(source="auto"):
    """删掉超过保留期的审计条目，返回删掉的条数。
    只在真删了东西时才补一条审计（“谁把日志清了”必须永远查得到），
    否则定时任务每小时跑一次就会被这条记账自己刷满表。"""
    days = audit_retention_days()
    cut = utcnow() - timedelta(days=days)
    try:
        n = db.session.query(AuditLog).filter(
            AuditLog.at < cut).delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("审计自动过期清理失败（不影响正常访问）")
        return 0
    if n:
        audit_event("delete", "审计自动过期：删除早于 %s 的 %d 条（保留 %d 天，触发方：%s）"
                    % (cn_time(cut, "%Y-%m-%d %H:%M"), n, days, source), "audit_log", "-")
    return n or 0


_AUDIT_SWEEP = {"not_before": 0.0}        # 单 worker，进程内的墙钟节流就够


@app.before_request
def auto_expire_audit():
    """没配定时任务也不会让“30 天自动过期”变成一句空话：
    有人访问时路过清一次，每个进程最多 6 小时一次。
    先用一次走 at 索引的 COUNT 探一下（绝大多数时候返回 0），确实有东西才发 DELETE，
    所以常态开销是一次轻量读 —— 不给 SQLite 添无谓的写锁，这个库的写锁全站排队。
    静态资源和 robots.txt 不参与：爬虫来探路不该替我们做维护。"""
    if request.endpoint in ("static", "robots_txt"):
        return
    now = time.monotonic()
    if now < _AUDIT_SWEEP["not_before"]:
        return
    # 不查 _audit_table_ready()：那个缓存只在进程启动时算一次，冷启动顺序不对就会
    # 一直说“表没有”，把兜底清理永久关掉。audit_expired_count() 自己吃得下
    # “表不存在”这种异常（返回 0），所以直接探一次反而更可靠。
    _AUDIT_SWEEP["not_before"] = now + 6 * 3600
    try:
        if audit_expired_count():
            n = purge_expired_audit("请求路过")
            if n:
                app.logger.info("审计自动过期：本次请求清理 %d 条", n)
    except Exception:
        db.session.rollback()
        app.logger.exception("审计自动过期清理异常")


# ------------------------------------------------ 门面内容：没开通的人只看到这套
def visitor_trusted():
    """这次请求的人能不能看真实内容。
    管理员永远可以（否则一上线就把自已锁在门外，连“开通”按钮都点不到）；
    其他人必须是已登录且被开通过的账号。未登录 = 一律不看真实内容。"""
    try:
        u = current_user
        if u is None or not getattr(u, "is_authenticated", False):
            return False
        return bool(u.is_admin) or bool(u.is_trusted)
    except Exception:
        # 老库还没补列时读 is_trusted 会抛异常：宁可退回“只有管理员能看真实内容”，
        # 也绝不能抛 500 —— 那会让整站在忘记跑 ensure-schema 的那一刻直接挂掉。
        app.logger.warning("读 is_trusted 失败（多半是还没跑 flask --app app ensure-schema）")
        return False


# ------------------------------------------------ 未登录访客只看到演示数据
DEMO_KEY_NAME = "demo_mode"            # site_flag 表里唯一的键，改名要连老库一起想清楚


def demo_default_value():
    """没被管理员点过之后的初始值：演示数据。
    环境变量 DEMO_MODE=0 能把初始值改成“真实内容”（给不想用演示模式的部署，
    也让老的回归脚本继续按“匿名可读”跑）—— 但管理员在后台点过一次之后，
    库里那一行就是唯一事实，环境变量不再起作用。"""
    return "0" if os.environ.get("DEMO_MODE", "").strip() == "0" else "1"


def demo_flag_value():
    """site_flag 表里的 demo_mode；行不存在 = 从没改过 → 用 demo_default_value()。
    老库还没跑 ensure-schema 时会抛“没有这张表” → 按默认值走，不逐请求重查。"""
    if getattr(g, "_demo_val", None) is not None:      # 一次请求里可能查多次（含模板）
        return g._demo_val
    val = demo_default_value()
    if "site_flag" in existing_tables():
        try:
            row = db.session.get(SiteFlag, DEMO_KEY_NAME)
            val = row.value if (row is not None and row.value) else demo_default_value()
        except Exception:
            db.session.rollback()
            app.logger.exception("读 demo_mode 失败，按默认处理")
            val = demo_default_value()
    else:
        if getattr(g, "_demo_warn", None) is None:
            g._demo_warn = True
            app.logger.warning("没有 site_flag 表：在 Bash console 跑一次 "
                               "flask --app app ensure-schema，否则后台的开关保存不了")
    g._demo_val = val
    return val


def demo_mode_on():
    return demo_flag_value() != "0"


def set_demo_mode(value):
    """写开关（只有后台那条路由会调）。value 只收 "1"/"0"，别的都当 "1" 处理。
    返回 False 表示没写进去 —— 老库还没建 site_flag 表时就是这个情况，
    路由要据此给出“先跑 ensure-schema”的人话，而不是抛 500 堆栈。"""
    val = "0" if value in ("0", 0, False, "off", "false") else "1"
    if "site_flag" not in existing_tables():
        app.logger.warning("保存 demo_mode 被跳过：库里没有 site_flag 表（跑 ensure-schema）")
        return False
    try:
        row = db.session.get(SiteFlag, DEMO_KEY_NAME)
        if row is None:
            row = SiteFlag(key=DEMO_KEY_NAME, value=val)
            db.session.add(row)
        else:
            row.value = val
        # CLI/测试里也可能直接调，所以先确认有请求上下文再碰 current_user
        row.updated_by = (current_user.id if (has_request_context()
                                              and current_user.is_authenticated) else None)
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("保存 demo_mode 失败")
        return False
    g._demo_val = val          # 同一请求里后面还要读的话，别读回旧值
    return True


def gate_passed():
    """这次请求是不是已经过了前厅那道门：闸门被关掉（GATE_ENABLED=0）也算过了。
    延迟导入 —— gate.py 由 app.py 引进来，在模块顶层反向 import 会成环。"""
    import gate as _g
    return (not _g.gate_enabled()) or bool(session.get(_g.OK_KEY))


# 门面接管这些会把班级内容端出去的内容页（白名单，不是黑名单）。
# 名单外的路由一律保持原样：需要登录的自然弹登录，后台的照旧 403/404 ——
# 做门面不是顺手改掉别人语义的借口。
FACADE_PAGES = {"index", "post_detail", "tag_page", "search", "unanswered",
                 "votes_index", "announcements", "user_profile"}

# 没开通的人唯一允许发出的写请求：进门 / 出门 / 改自己密码 / 闸门自身 / 找回密码。
# 其余 POST 一律挡掉 —— 不然“不信任”只挡住了读，却能往真实论坛里发帖。
FACADE_WRITE_OPEN = {"login", "logout", "register", "request_password_reset",
                      "reset_password_with_token", "verify_email", "change_password",
                      "gate.enter", "gate.lock_again", "static", "favicon",
                      "robots_txt", "healthz"}


def _demo_ctx(extra=None):
    """演示页的统一上下文：标题带演示字样、强制 banner=None
    （inject_globals 会查出真公告，别让它进渲染）、告诉模板现在是演示态，
    以及“登录/注册链接点了有没有用”（闸门没解锁时它们会撞伪 404，别给死链）。"""
    # 模板里只用这两个标记决定文案（demo 只是个内部名字，不会出现在页面上）
    ctx = dict(title=None, demo=True, banner=None, unread=0, entry_open=gate_passed(),
               empty_text=None)
    if extra:
        ctx.update(extra)
    return ctx


def demo_user(name):
    """演示成员：只认 demo.py 里写死的那几个人，别的用户名一律不存在。"""
    meta = demo.USERS.get(name)
    if meta is None:
        return None
    return SimpleNamespace(username=name, initial=meta["initial"], joined=meta["since"],
                           post_count=meta["posts"], answer_count=meta["answers"])


def demo_tag_view(t):
    """演示标签：让标签胶囊点进去有页可看，不会撞一条“假链接指向真路由”。"""
    return SimpleNamespace(name=t, slug=t)


def demo_build(p):
    """把 demo.py 里的字典包成模板能直接用的样子（假 author / 假时间，绝不回查数据库）。"""
    answers = [SimpleNamespace(
        id=a["author"], author=demo_user(a["author"]) or SimpleNamespace(
            username=a["author"], initial=a["author"][:1], joined="", post_count=0,
            answer_count=0),
        created_text=a["at"], body_html=a["body_html"], likes_count=a["likes"],
        accepted=bool(a["accepted"])) for a in p["answers"]]
    snippet = re.sub(r"<[^>]+>", " ", p["body_html"])
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return SimpleNamespace(
        id=p["id"], title=p["title"], content=p["body_html"], body_html=p["body_html"],
        author=demo_user(p["author"]) or SimpleNamespace(username=p["author"],
                                                         initial=p["author"][:1],
                                                         joined="", post_count=0,
                                                         answer_count=0),
        snippet=snippet[:150], created_text=p["at"], timestamp=p["at"], language=p["lang"],
        tags=[demo_tag_view(t) for t in p["tags"]], comments=len(answers),
        comments_count=len(answers), likes_count=p["likes"],
        solved=bool(p["solved"]), is_solved=bool(p["solved"]),
        answers=answers, views=max(20, p["likes"] * 7))


# 投票条宽度沿用了站点已有的 pv-* 类（10% 一档，见 templates/demo/demo_votes.html）：
# 模板里不能拼 style="width:…"，本站 CSP 没开 style-src-attr。


def demo_vote_view(v):
    total = v["total"] or 1
    return SimpleNamespace(
        id=v["id"], title=v["title"], total=total,
        options=[SimpleNamespace(option_text=t, vote_count=c,
                                 pct=int(round(100.0 * c / total)))
         for t, c in v["options"]])


def _demo_response(path):
    """渲染演示页。未解锁的访客走不到这里（gate 先给伪 404），所以这里的“访客”
    是：知道入口口令但没登录的人，以及被转发过链接的人。"""
    tpl, ctx = demo.render(path)
    args = {"title": "最新帖子"}
    if tpl == "demo_post.html":
        args["post"] = demo_build(ctx["post"])
        args["title"] = ctx["post"]["title"]
    elif tpl == "demo_list.html":
        args["posts"] = [demo_build(p) for p in ctx["posts"]]
        args["list_heading"] = ctx["heading"]
        args["empty_text"] = ctx.get("empty_text")
        args["title"] = ctx["heading"]
    elif tpl == "demo_votes.html":
        args["votes"] = [demo_vote_view(v) for v in ctx["votes"]]
        args["title"] = "新功能投票"
    elif tpl == "demo_announce.html":
        args["anns"] = [SimpleNamespace(id=a["id"], title=a["title"], body_html=a["body_html"],
                                        author_name=a["author"], at=a["at"])
                        for a in ctx["anns"]]
        args["title"] = "公告"
    elif tpl == "demo_profile.html":
        args["person"] = demo_user(ctx["handle"])
        args["handle"] = ctx["handle"]
        args["title"] = "成员 · %s" % ctx["handle"]
        args["posts"] = [demo_build(p) for p in demo.POSTS
                         if p["author"] == (args["person"].username if args["person"] else "")]
    else:   # demo_home.html
        args["posts"] = [demo_build(p) for p in demo.POSTS]
        args["votes"] = [demo_vote_view(v) for v in demo.VOTES]
        args["ann"] = SimpleNamespace(**demo.ANNOUNCEMENT)
    resp = make_response(render_template("demo/" + tpl, **_demo_ctx(args)))
    # 刻意不发任何响应头：头是 curl -I 就能看到的，门面也就不成立了。
    # 要知道是哪一层在应答，看服务端日志这一行（只有运维能看到）。
    app.logger.info("门面内容：%s %s（未开通/未登录）", request.method, path)
    return resp


@app.route("/healthz")
def healthz():
    """运维自检：不查库、不需要登录，专门用来回答“服务活着吗、有没有误挡成 404”。
    刻意不含任何站点信息（名字、条数都不给）。"""
    return ("ok", 200, {"Content-Type": "text/plain; charset=utf-8",
                        "Cache-Control": "no-store"})


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    """外键级联默认在 SQLite 是关的，不打开的话 ondelete='CASCADE' 形同注释。
    只对有 cursor 的 DBAPI 连接生效（内存测试库等会跳过）。"""
    try:
        cursor = dbapi_connection.cursor()
    except Exception:
        return
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()
    except Exception:
        pass


# 老库（已经跑在线上的 forum.db）没有本次新增的列，ALTER TABLE 增量补齐，
# 免去推倒重建。ondelete=CASCADE 这类“表级”约束无法 ALTER，
# 所以旧库仍依赖 doctor + sync_post_counts 兜底。
_SCHEMA_COLUMNS = {
    "user": [
        ("session_version", "INTEGER DEFAULT 0"),
        ("email_verified", "BOOLEAN DEFAULT 1"),
        ("failed_logins", "INTEGER DEFAULT 0"),
        ("locked_until", "DATETIME"),
        # 老库补这列时全员默认 0（= 未开通，只看门面）：升级后记得去用户管理点
        # 一次“全部开通”，否则全班都会以为自己打不开论坛。管理员自己不受影响。
        ("is_trusted", "BOOLEAN DEFAULT 0"),
    ],
    "post": [
        ("comments_count", "INTEGER DEFAULT 0"),
        ("likes_count", "INTEGER DEFAULT 0"),
        ("language", "VARCHAR(24)"),
        ("is_solved", "BOOLEAN DEFAULT 0"),
        ("accepted_comment_id", "INTEGER"),
        ("solved_at", "DATETIME"),
    ],
    "comment": [
        ("language", "VARCHAR(24)"),
        ("likes_count", "INTEGER DEFAULT 0"),
    ],
    "vote_option": [("vote_count", "INTEGER DEFAULT 0")],
}

IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")   # 结构名白名单：DDL 不能接受外部值


_SCHEMA_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_comment_post_id ON comment (post_id)",
    "CREATE INDEX IF NOT EXISTS ix_like_post_id ON like (post_id)",
    "CREATE INDEX IF NOT EXISTS ix_vote_record_vote_item_id ON vote_record (vote_item_id)",
    "CREATE INDEX IF NOT EXISTS ix_vote_option_vote_item_id ON vote_option (vote_item_id)",
]


def ensure_schema():
    """返回补过的东西的列表，方便 CLI 打印。"""
    changed = []
    known_indexes = {row[0] for row in db.session.execute(
        text("SELECT name FROM sqlite_master WHERE type='index'"))}
    for table, columns in _SCHEMA_COLUMNS.items():
        if not IDENT_RE.match(table):
            continue
        existing = {row[1] for row in
                    db.session.execute(text("PRAGMA table_info(%s)" % table))}
        if not existing:
            continue                      # 表还不存在，create_all 会建全
        for name, ddl in columns:
            # 白名单通过 且 这列真不在表上才发 DDL。上一版把条件写反，
            # 变成对“已存在的列”重复 ALTER（duplicate column 直接崩），
            # 而真正缺的新列反而被跳过。
            if IDENT_RE.match(name) and name not in existing:
                db.session.execute(text("ALTER TABLE %s ADD COLUMN %s %s"
                                         % (table, name, ddl)))
                changed.append("%s.%s" % (table, name))
    for ddl in _SCHEMA_INDEXES:
        name = ddl.split("EXISTS ")[1].split(" ON")[0]
        if name in known_indexes:
            continue
        try:
            db.session.execute(text(ddl))
            changed.append(name)
        except Exception:
            pass                          # 对应的表还没建
    db.session.commit()
    return changed


# ---------------------------------------------------------------- 表单

USERNAME_RE = re.compile(r"^[\w.\-]{2,20}$", re.UNICODE)


def normalize_username(value):
    value = (value or "").strip()
    value = re.sub(r"\s+", " ", value)          # “bob  ” 和 “bob” 视为同名
    return value


def normalize_email(value):
    return (value or "").strip().lower()


class RegistrationForm(FlaskForm):
    username = StringField("用户名", validators=[
        DataRequired(), Length(min=2, max=20),
        Regexp(USERNAME_RE, message="用户名只能是中文、字母、数字、点、下划线或减号")])
    email = StringField("邮箱", validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField("密码", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField("确认密码",
                                     validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("注册")

    def validate(self, *args, **kwargs):
        # 先规范化再查重，避免 “Alice” / “bob  ” 这类大小写或空格变体绕开唯一约束
        self.username.data = normalize_username(self.username.data)
        self.email.data = normalize_email(self.email.data)
        return super().validate(*args, **kwargs)

    def validate_username(self, field):
        if field.data and User.query.filter(
            db.func.lower(User.username) == field.data.lower()).first():
            raise ValidationError("该用户名已被注册")

    def validate_email(self, field):
        if field.data and User.query.filter(db.func.lower(User.email) == field.data).first():
            raise ValidationError("该邮箱已被注册")


class LoginForm(FlaskForm):
    email = StringField("邮箱", validators=[DataRequired(), Email()])
    password = PasswordField("密码", validators=[DataRequired()])
    remember = BooleanField("记住我（7 天）")
    submit = SubmitField("登录")


LANGUAGES = [("", "不指定（普通文本）")] + [(k, k) for k in (
    "python", "java", "c", "cpp", "csharp", "go", "rust", "javascript", "typescript",
    "html", "css", "sql", "bash", "shell", "dockerfile", "json", "yaml", "markdown",
    "diff", "text")]


class LanguageFieldMixin:
    def clean_language(self, field):
        value = (field.data or "").strip().lower()
        field.data = value if value in dict(LANGUAGES[1:]) else None


class PostForm(FlaskForm):
    title = StringField("标题", validators=[DataRequired(), Length(min=2, max=200)])
    language = SelectField("代码语言", choices=LANGUAGES, default="")
    tags = StringField("标签", validators=[Optional(), Length(max=120)])
    content = TextAreaField("内容", validators=[DataRequired(), Length(max=50000)])
    submit = SubmitField("发布帖子")

    def validate_language(self, field):
        LanguageFieldMixin().clean_language(field)


class CommentForm(FlaskForm):
    body = TextAreaField("评论", validators=[DataRequired(), Length(max=8000)])
    language = SelectField("代码语言", choices=LANGUAGES, default="")
    submit = SubmitField("发表评论")

    def validate_language(self, field):
        LanguageFieldMixin().clean_language(field)


class UpdatePasswordForm(FlaskForm):
    old_password = PasswordField("当前密码", validators=[DataRequired()])
    new_password = PasswordField("新密码", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_new_password = PasswordField("确认新密码",
                                         validators=[DataRequired(), EqualTo("new_password")])
    submit = SubmitField("修改密码")


class PasswordResetRequestForm(FlaskForm):
    email = StringField("邮箱", validators=[DataRequired(), Email()])
    submit = SubmitField("发送重置链接")


class PasswordResetForm(FlaskForm):
    new_password = PasswordField("新密码", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_new_password = PasswordField("确认新密码",
                                         validators=[DataRequired(), EqualTo("new_password")])
    submit = SubmitField("设置新密码")


class AdminSetPasswordForm(FlaskForm):
    new_password = PasswordField("新密码", validators=[DataRequired(), Length(min=8, max=128)])
    submit = SubmitField("重置该用户密码")


class VoteCreateForm(FlaskForm):
    title = StringField("投票主题", validators=[DataRequired(), Length(min=2, max=200)])
    description = TextAreaField("投票说明", validators=[DataRequired(), Length(max=1000)])
    option1 = StringField("选项1", validators=[DataRequired(), Length(max=200)])
    option2 = StringField("选项2", validators=[DataRequired(), Length(max=200)])
    option3 = StringField("选项3（选填）", validators=[Optional(), Length(max=200)])
    option4 = StringField("选项4（选填）", validators=[Optional(), Length(max=200)])
    submit = SubmitField("发布投票")


# ---------------------------------------------------------------- 通用小工具

def safe_next(target):
    """只允许跳回本站相对路径。原实现 redirect(request.args['next']) 实测
    会把用户直接送到 https://evil.com，是标准钓鱼跳板。"""
    if not target:
        return None
    if "\r" in target or "\n" in target:        # 顺带堵住响应头注入
        return None
    if "\\" in target:
        # `/\evil.com` 在浏览器的 URL 解析里等同于 `//evil.com`（协议相对）→ 会跳出站。
        # Werkzeug 恰好会把它百分号编码，所以“碰巧”安全；但这种安全不能指望实现细节。
        return None
    try:
        parsed = urlsplit(urljoin(request.host_url, target))
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.netloc != urlsplit(request.host_url).netloc:
        return None
    if parsed.path in ("/login", "/logout"):    # 自我循环
        return None
    return target


def next_or_endpoint(endpoint="index", **kwargs):
    """表单 action 用：把 ?next= 一路带下去（原代码 action="" 把 next 丢了）。"""
    params = dict(request.args.items()) if request.args else {}
    params.update(kwargs)
    return url_for(endpoint, **params)


_token_serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="forum.one-time-token.v1")


def make_token(purpose, user):
    """把密码哈希尾巴一起签进去：改过密码之后旧的一次性链接自动失效。"""
    return _token_serializer.dumps({"p": purpose, "u": user.id,
                                    "k": user.password_hash[-12:]})


def read_token(raw, purpose, max_age_seconds=3600):
    """返回 None 表示令牌无效/过期/已被密码变更作废。"""
    try:
        data = _token_serializer.loads(raw, max_age=max_age_seconds)
    except SignatureExpired:
        app.logger.info("一次性令牌过期 purpose=%s", purpose)
        return None
    except BadSignature:
        app.logger.info("一次性令牌签名无效 purpose=%s", purpose)
        return None
    u = db.session.get(User, data.get("u", 0))
    if u is None or data.get("p") != purpose:
        return None
    if data.get("k") != u.password_hash[-12:]:
        return None                              # 密码已改过，旧链接作废
    return u


def absolute_url(endpoint, **kwargs):
    return request.url_root.rstrip("/") + url_for(endpoint, **kwargs)


def send_email(to, subject, body):
    """成功 True / 失败或未配置 False。调用方必须自己准备降级路径。
    注意：PythonAnywhere 免费套餐只能访问白名单主机的 HTTP(S)，
    25/465/587 端口的 SMTP 出不去 —— 要么申请加白，要么升级到 Developer 套餐，
    要么改用 HTTP API 的邮件服务。"""
    host = app.config["SMTP_HOST"]
    if not host:
        return False
    msg = EmailMessage()
    msg["Subject"] = "[%s] %s" % (app.config["SITE_NAME"], subject)
    msg["From"] = app.config["MAIL_FROM"]
    msg["To"] = to
    msg.set_content(body)
    port = app.config["SMTP_PORT"]
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        with server:
            if app.config["SMTP_USER"]:
                server.login(app.config["SMTP_USER"], app.config["SMTP_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception as exc:                       # noqa: BLE001 - 发信失败不能变成 500
        app.logger.error("邮件发送失败 host=%s err=%s", host, exc)
        return False


def deliver_link(user, subject, body):
    """邮件正文里已带好链接。有 SMTP 就发，发不出去（或没配）时：
    MAIL_DEBUG=1 才把正文写进日志，否则调用方只会回一句通用提示。"""
    if send_email(user.email, subject, body):
        return True
    if app.config["MAIL_DEBUG"]:
        app.logger.warning("MAIL_DEBUG：邮件未发出，内容如下\n%s", body)
    return False




@app.template_filter("cn_time")
def _cn_time_filter(dt, fmt="%Y-%m-%d %H:%M"):
    return cn_time(dt, fmt)


def _asset_v():
    """静态资源的缓存版本号 = 最新 css/js 文件的 mtime。
    原来手写死 ?v=2026a：改了 app.js 却忘了升版本，浏览器会继续用旧缓存
    （这次的确认框/复制按钮修复就都会被旧脚本吃掉）。启动时算一次，不逐请求扫盘。"""
    try:
        return int(max(os.path.getmtime(os.path.join(dp, f))
                       for dp, _d, fs in os.walk(os.path.join(basedir, "static"))
                       for f in fs if f.endswith((".css", ".js"))))
    except Exception:
        return 0


_ASSET_V = _asset_v()          # 换文件后要 Reload 才会变，这与 PA 的部署节奏一致


def _nav_unread():
    """导航栏小铃铛的数字。匿名/闸门页不查库。
    没开通的账号也一样不给：未读条数本身就是“班里有人在聊”的信号。"""
    try:
        if not visitor_trusted() and demo_mode_on():
            return 0
        if not current_user.is_authenticated:
            return 0
        uid = current_user.id
        hit = g.get("_unread")
        if hit is None:
            hit = g._unread = unread_count(uid)
        return hit
    except Exception:
        return 0


def _nav_banner():
    """首页公告横幅。不要求登录：/announcements 列表本身也是对所有来访者开放的，
    真正的门槛是前厅闸门，不是这一层。
    但门面模式开着时，没开通的人连公告标题都不该看到 —— 公告里最容易写班里的事。"""
    try:
        if not visitor_trusted() and demo_mode_on():
            return None
        hit = g.get("_banner", "?")
        if hit == "?":
            hit = g._banner = banner_announcement()
        return hit
    except Exception:
        return None


@app.context_processor
def inject_globals():
    """模板全局。未读数与横幅都只在“这次请求真用到”时查一次库（挂在 g 上）。"""
    return {
        "asset_v": _ASSET_V,
        "unread": _nav_unread(),
        "banner": _nav_banner(),
        "mail_enabled": bool(app.config["SMTP_HOST"]),
        "site_name": app.config["SITE_NAME"],
        "current_year": cn_now().year,
        # 登录页要把“多久会自动注销”用人话写在框下面，而不是让人被踢了才猜
        "session_idle": human_window(session_idle_seconds()),
        "session_max": human_window(session_max_age_seconds()),
        "session_remember": human_window(remember_window_seconds()),
    }


# ---------------------------------------------------------------- 路由

def _using_remember_cookie():
    """这个会话算不算“记住了我”。两个来源都要认，漏一个就会把勾了“记住我”的同学按
    普通 30 分钟规则踢掉，而且还会连他们的 remember_token 一起删（那是真注销）：
      ① login() 里我们自己打的标记；
      ② Flask-Login 拿 remember cookie 把人自动登录回来时写的 _fresh=False
         —— 这条路径不经过我们的 login()，而正常 login_user() 写的是 _fresh=True。"""
    return session.get(SESSION_KEY_REM) == "1" or session.get("_fresh") is False


def _force_logout(reason):
    """会话到期 / 凭据失效 → 真·注销：清 session + 删“记住我”cookie + 留下一条审计。

    顺序有讲究：先 session.clear() 再 logout_user()。Flask-Login 是靠
    session["_remember"] == "clear" 这个标记在响应阶段发“删除 cookie”头的，
    反过来写会被 clear 把标记一起抹掉 —— 结果是页面上写着“已退出”，
    浏览器里的 remember_token 还活着，下一个请求它自己就把人登录回来了。

    session.clear() 是全部清掉，所以前厅闸门的解锁状态也一起没了：注销就是回到
    “门外”，不做半套。副作用是按 next= 跳回来时会先撞那张伪 404，口令得重输一次
    —— 这与“密码被管理员重置后强制下线”那条既有路径的行为完全一致。"""
    uid = getattr(current_user, "id", None)
    # 审计必须排在 logout 之前：actor 取的是“当时是谁”，logout 之后就只剩“匿名”了
    audit_event("logout", "自动注销：%s" % reason, "user", str(uid) if uid else "-")
    session.clear()
    logout_user()
    flash("登录状态已失效（%s），请重新登录。" % reason, "warning")
    nxt = safe_next(request.path) if request.method == "GET" else None
    return redirect(url_for("login", next=nxt) if nxt else url_for("login"))


@app.before_request
def enforce_session_expiry():
    """自动注销。两个独立上限，谁先到算谁：
      空闲上限  —— 连续没操作多久（默认 30 分钟）；教室电脑上忘了登出就靠它。
      绝对上限  —— 一次登录最多用多久（默认 12 小时），一直在点也照样重登。
    勾了“记住我”的两项一起放宽到 REMEMBER_COOKIE_DURATION（当前 7 天）：
    那个 cookie 一到期人就得出门重登，这样界面上写的“7 天”是真话。
    静态资源不参与（没必要让每张图都去比对一次，也不能让它在人写帖中途把人踢走）。"""
    if request.endpoint == "static" or not current_user.is_authenticated:
        return
    now = int(time.time())
    last = session.get(SESSION_KEY_LAST)
    born = session.get(SESSION_KEY_BORN)
    if last is None or born is None:
        # 走到这里只有两种情况：① 这条 cookie 是本策略上线之前签发的；② 刚被
        # remember cookie 自动登录回来（Flask-Login 会把 _user_id 写进一个空 session）。
        # 都不能当场把人踢走，先把基准值补上，下一次请求起按新规则算。
        # 顺手把 sv 补成当前值：不补的话 touch_last_seen 会拿 None 和 0 比，
        # 于是每次“凭记住我自动登录”都被误判成“密码已变更”而当场掉线。
        # 残余风险要说清楚：改密码对“只剩记住我 cookie”的设备要到本周期结束才生效；
        # 要立刻生效就在后台把人冻结 —— load_user() 对 is_active=False 直接返回 None，
        # remember cookie 也救不回来。
        session[SESSION_KEY_LAST] = session[SESSION_KEY_BORN] = now
        session.setdefault("sv", current_user.session_version or 0)
        # 只有 _fresh is False 才说明这次是拿 remember cookie 换回来的登录态；
        # 光“缺基准值”不足以给人升级到 7 天窗口（否则老 cookie 白捡一段有效期）。
        if session.get("_fresh") is False:
            session[SESSION_KEY_REM] = "1"
        return
    if _using_remember_cookie():
        idle_limit = age_limit = remember_window_seconds()
    else:
        idle_limit = session_idle_seconds()
        age_limit = session_max_age_seconds()
    if now - int(last) > idle_limit:
        return _force_logout("空闲超过 %s" % human_window(idle_limit))
    if now - int(born) > age_limit:
        return _force_logout("本次登录已超过 %s" % human_window(age_limit))
    if now - int(last) >= 60:        # 滑动续期，一分钟内不重复签 cookie
        session[SESSION_KEY_LAST] = now


@app.before_request
def touch_last_seen():
    """原实现每个请求都 UPDATE user + commit（实测 2 次 GET / = 8 条 SQL 里
    2 条是写）。SQLite 是库级写锁，免费套餐只有 1 个 worker，等于访客浏览页面
    时在排队写盘。这里改成 5 分钟内最多写一次。"""
    try:
        if not current_user.is_authenticated:
            return
        if session.get("sv") != (current_user.session_version or 0):
            # 密码被改过（本人改或被管理员重置）→ 这条 cookie 不再有效。
            # 走 _force_logout 而不是 logout_user()+session.clear()：后者会把
            # Flask-Login 用来发“删除 cookie”头的标记一并 clear 掉，勾了“记住我”的
            # 设备清不干净 —— 改密的“立刻下线”就只剩一半。
            return _force_logout("账号密码已变更")
        seen = current_user.last_seen
    except Exception:
        # 读 current_user 会查库：数据库本身不可读时（disk I/O error 等）
        # 不能让它把每个页面都变成 500
        db.session.rollback()
        return
    if seen and (utcnow() - seen) < timedelta(minutes=5):
        return
    try:
        current_user.last_seen = utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("更新 last_seen 失败")


@app.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    q, lang = _lang_filter(Post.query)
    posts = q.order_by(Post.timestamp.desc()).paginate(page=page, per_page=10, error_out=True)
    return render_template("index.html", posts=posts, lang=lang,
                           heading=("语言 · %s" % lang) if lang else "最新帖子",
                           pager_args=({"lang": lang} if lang else {}),
                           pager_endpoint="index")


def _lang_filter(q):
    """列表按语言筛选；非法值直接忽略，不拼进 SQL。"""
    lang = (request.args.get("lang") or "").strip().lower()
    if lang and lang in dict(LANGUAGES[1:]):
        return q.filter(Post.language == lang), lang
    return q, None


@app.route("/tag/<slug>")
def tag_page(slug):
    slug = (slug or "").strip().lower()[:40]
    t = Tag.query.filter(db.func.lower(Tag.slug) == slug).first()
    if t is None:
        abort(404)
    page = request.args.get("page", 1, type=int)
    posts = (Post.query.filter(Post.tags.contains(t)).order_by(Post.timestamp.desc())
             .paginate(page=page, per_page=10, error_out=True))
    return render_template("index.html", posts=posts, lang=None,
                           heading="标签 · %s" % t.name, tag=t.name,
                           pager_endpoint="tag_page", pager_args={"slug": t.slug})


ESCAPE_CHAR = chr(92)          # LIKE 的转义符（反斜杠）
LIKE_ESCAPE = {"\\": "\\\\", "%": "\\%", "_": "\\_"}


def like_arg(term):
    return "".join(LIKE_ESCAPE.get(ch, ch) for ch in term.lower())


@app.route("/search")
@limiter.limit("30 per minute")
def search():
    term = (request.args.get("q") or "").strip()[:60]
    page = request.args.get("page", 1, type=int)
    if not term:
        return redirect(url_for("index"))
    pat = "%" + like_arg(term) + "%"
    q = (Post.query.filter(db.or_(
            db.func.lower(Post.title).like(pat, escape=ESCAPE_CHAR),
            db.func.lower(Post.content).like(pat, escape=ESCAPE_CHAR),
            Post.tags.any(db.func.lower(Tag.name).like(pat, escape=ESCAPE_CHAR))))
         .order_by(Post.timestamp.desc()))
    posts = q.paginate(page=page, per_page=10, error_out=True)
    return render_template("index.html", posts=posts, lang=None,
                           heading="搜索：%s" % term, q=term,
                           pager_endpoint="search", pager_args={"q": term})


@app.route("/unanswered")
def unanswered():
    """还没人回答的帖子。用一次聚合查出目标 id，再走 ORM 分页，避免 N+1。"""
    page = request.args.get("page", 1, type=int)
    rows = list(db.session.execute(text(
        "SELECT p.id FROM post p LEFT JOIN comment c ON c.post_id = p.id "
        "WHERE coalesce(p.is_solved, 0) = 0 "
        "GROUP BY p.id HAVING count(c.id) = 0 ORDER BY max(p.timestamp) DESC")).scalars().all())
    if rows:
        q = Post.query.filter(Post.id.in_(rows))
    else:
        q = Post.query.filter(db.literal(1) == 0)      # 空集，但仍然走同一套分页/模板
    posts = q.order_by(Post.timestamp.desc()).paginate(page=page, per_page=10, error_out=True)
    return render_template("index.html", posts=posts, lang=None, heading="还没人回答",
                           unanswered=True, pager_endpoint="unanswered")


@app.route("/register", methods=["GET", "POST"])
# 只限 POST：否则输错几次密码的人连登录页都打不开
@limiter.limit("5 per 5 minutes", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data,
                    # 没配 SMTP 就不设验证门槛，否则没人能注册进来
                    email_verified=not app.config["SMTP_HOST"])
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
        except Exception:                        
            db.session.rollback()
            app.logger.exception("注册写入失败")
            flash("注册失败：用户名或邮箱已被占用，请换一个。", "danger")
            return render_template("register.html", title="注册", form=form)
        if app.config["SMTP_HOST"]:
            link = absolute_url("verify_email", token=make_token("verify-email", user))
            delivered = deliver_link(
                user, "请验证邮箱",
                "你好 %s，\n\n点下面的链接验证邮箱（1 小时内有效）：\n%s\n\n"
                "不是本人操作请忽略本邮件。" % (user.username, link))
            flash("注册成功，验证邮件已发送，请查收后再登录。" if delivered
                  else "注册成功。验证邮件发送失败，请直接联系管理员。", "success")
        else:
            mention_cache_clear()              # 新账号要能立刻被 @，不等缓存过期
        # 默认不信任：注册完先别让他以为站点空了，说清楚下一步找谁
        flash("注册成功！管理员开通之后才能看到班级内容，开通请找班主任。", "success")
        return redirect(url_for("login"))
    return render_template("register.html", title="注册", form=form)


@app.route("/verify-email/<token>")
@limiter.limit("30 per hour")
def verify_email(token):
    user = read_token(token, "verify-email")
    if user is None:
        flash("验证链接无效或已过期，请重新获取。", "warning")
        return redirect(url_for("login"))
    if not user.email_verified:
        user.email_verified = True
        db.session.commit()
        flash("邮箱验证完成，欢迎加入。", "success")
    else:
        flash("该邮箱此前已验证过。", "info")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per 10 minutes", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(safe_next(request.args.get("next")) or url_for("index"))
    form = LoginForm()
    # 登录是 POST 表单，?next= 会在提交时丢掉，所以模板里用隐藏字段带回来
    next_url = safe_next(request.args.get("next") or request.form.get("next"))
    if form.validate_on_submit():
        email = normalize_email(form.email.data)
        user = User.query.filter(db.func.lower(User.email) == email).first()
        # 用户不存在和密码错误给同一句提示，避免把邮箱库“枚举”出来
        if user is None or not user.check_password(form.password.data):
            if user is not None:
                user.register_failure()
            db.session.commit()
            audit_event("login", "登录失败：邮箱或密码不对（尝试账号 %s）" % email[:60],
                        "user", str(user.id) if user is not None else "-")
            flash("无效的邮箱或密码", "danger")
            return render_template("login.html", title="登录", form=form, next_url=next_url)
        if user.is_locked:
            audit_event("login", "被锁定账号尝试登录 @%s" % user.username[:30], "user", str(user.id))
            flash("失败次数过多，请 10 分钟后再试，或联系管理员重置密码。", "warning")
            return render_template("login.html", title="登录", form=form, next_url=next_url)
        if not user.is_active:
            audit_event("login", "已冻结账号尝试登录 @%s" % user.username[:30], "user", str(user.id))
            flash("您的账号已被冻结，请联系管理员。", "warning")
            return render_template("login.html", title="登录", form=form, next_url=next_url)
        user.register_success()
        db.session.commit()
        login_user(user, remember=bool(form.remember.data))
        audit_event("login", "登录成功" + ("（勾选了记住我）" if form.remember.data else ""),
                    "user", str(user.id))
        session["sv"] = user.session_version or 0
        # 自动注销的两个基准值：本次登录的诞生时间与最后活动时间（epoch 秒）。
        # 存在签名 cookie 里而不是库里：省掉每个请求一次写盘（SQLite 是库级写锁）。
        _now = int(time.time())
        session[SESSION_KEY_BORN] = _now
        session[SESSION_KEY_LAST] = _now
        session[SESSION_KEY_REM] = "1" if form.remember.data else "0"
        if user.email_verified is False and app.config["SMTP_HOST"]:
            flash("登录成功，但邮箱还没验证，部分功能会受限。", "warning")
        return redirect(next_url or url_for("index"))
    return render_template("login.html", title="登录", form=form, next_url=next_url)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    audit_event("logout", "退出登录")
    logout_user()
    flash("已退出登录。", "info")
    return redirect(url_for("index"))


@app.route("/post/new", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per hour")
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        recent = Post.query.filter(
            Post.user_id == current_user.id,
            Post.timestamp > utcnow() - timedelta(minutes=5)).count()
        if recent >= 5:
            flash("发帖太快了，请几分钟后再试。", "warning")
            return render_template("create_post.html", title="新建帖子", form=form,
                                   legend="新建帖子")
        post = Post(title=form.title.data.strip(), content=form.content.data,
                    language=form.language.data,
                    author=current_user._get_current_object())
        post.sanitize_content()
        attach_tags(post, form.tags.data)
        db.session.add(post)
        db.session.commit()
        watch_post(post.id, current_user.id)      # 自己发的帖默认关注
        m = notify_mentions(post.title + "\n" + post.content, current_user._get_current_object(),
                            post.id)
        db.session.commit()
        if m:
            flash("已通知 %d 位被 @ 的成员。" % m, "info")
        flash("帖子发布成功！", "success")
        return redirect(url_for("post_detail", post_id=post.id))
    return render_template("create_post.html", title="新建帖子", form=form, legend="新建帖子")


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def post_detail(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        abort(404)
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("请先登录以发表评论。", "warning")
            return redirect(url_for("login", next=url_for("post_detail", post_id=post.id)))
        recent = Comment.query.filter(
            Comment.user_id == current_user.id,
            Comment.timestamp > utcnow() - timedelta(minutes=5)).count()
        if recent >= 8:
            flash("评论过于频繁，请稍后再试。", "warning")
            return redirect(url_for("post_detail", post_id=post.id))
        comment = Comment(body=form.body.data, language=form.language.data,
                          author=current_user._get_current_object(), post=post)
        comment.sanitize_body()
        db.session.add(comment)
        db.session.commit()
        sync_post_counts(post.id)
        watch_post(post.id, current_user.id)      # 说过话的人自动关注这帖
        db.session.commit()
        notify_new_comment(post, comment, current_user._get_current_object())
        notify_mentions(comment.body, current_user._get_current_object(), post.id, comment.id)
        db.session.commit()
        flash("评论发表成功！", "success")
        return redirect(url_for("post_detail", post_id=post.id))
    is_liked = bool(current_user.is_authenticated and Like.query.filter_by(
        user_id=current_user.id, post_id=post.id).first())
    watching = False
    if current_user.is_authenticated:
        from sqlalchemy import select as _sel
        watching = bool(db.session.execute(_sel(PostWatch.id).where(
            PostWatch.post_id == post.id,
            PostWatch.user_id == current_user.id)).first())
    return render_template("post_detail.html", title=post.title, post=post,
                           form=form, is_liked=is_liked, watching=watching,
                           answers=order_answers(post))


@app.route("/post/<int:post_id>/like", methods=["POST"])
@login_required
@limiter.limit("60 per minute")
def like_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        abort(404)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if like:
        db.session.delete(like)
        msg, cat = "已取消点赞", "info"
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post.id))
        msg, cat = "点赞成功", "success"
    try:
        db.session.commit()
    except Exception:
        # 并发双击会撞 unique_like 约束，原来这里直接 500
        db.session.rollback()
        flash("操作太快了，刷新后重试。", "warning")
        return redirect(url_for("post_detail", post_id=post.id))
    sync_post_counts(post.id)
    db.session.commit()
    flash(msg, cat)
    return redirect(url_for("post_detail", post_id=post.id))


@app.post("/post/<int:post_id>/accept/<int:comment_id>")
@login_required
@limiter.limit("60 per hour", methods=["POST"])   # 采纳是特权动作，别被脚本刷
def accept_answer(post_id, comment_id):
    """采纳 / 取消采纳某个回答。只有楼主或管理员能操作（帖子作者本人也合理，
    因为「哪个回答解决了我这个问题」由他判断）。"""
    post = db.session.get(Post, post_id)
    if post is None:
        abort(404)
    comment = db.session.get(Comment, comment_id)
    if comment is None or comment.post_id != post.id:
        abort(404)                      # 跨帖采纳直接 404，不给枚举线索
    if current_user.id != post.user_id and not current_user.is_admin:
        abort(403)
    if post.accepted_comment_id == comment_id:
        post.accepted_comment_id = None
        post.is_solved = False
        post.solved_at = None
        flash("已取消采纳。", "info")
    else:
        post.accepted_comment_id = comment_id
        post.is_solved = True
        post.solved_at = utcnow()
        notify(comment.user_id, "accept", "accept:%s:%s" % (post.id, comment.id),
               actor=current_user._get_current_object(),
               excerpt="《%s》采纳了你的回答" % (post.title or "")[:60],
               post_id=post.id, comment_id=comment.id, commit=False)
        flash("已采纳 #%d 作为该问题的回答。" % comment_id, "success")
    db.session.commit()
    return redirect(url_for("post_detail", post_id=post.id))


@app.post("/comment/<int:comment_id>/like")
@login_required
@limiter.limit("60 per minute")
def like_comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        abort(404)
    mine = CommentLike.query.filter_by(user_id=current_user.id, comment_id=comment.id).first()
    if mine:
        db.session.delete(mine)
        msg = "已取消对该回答的点赞。"
    else:
        db.session.add(CommentLike(user_id=current_user.id, comment_id=comment.id))
        msg = "已点赞该回答。"
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("操作太快了，刷新后重试。", "warning")
        return redirect(url_for("post_detail", post_id=comment.post_id))
    sync_comment_likes(comment.id)
    db.session.commit()
    flash(msg, "success")
    return redirect(url_for("post_detail", post_id=comment.post_id) + "#c-%d" % comment.id)

@app.route("/account/password", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per 10 minutes", methods=["POST"])   # 防拿着别人会话验旧密码
def change_password():
    form = UpdatePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash("当前密码错误", "danger")
            return render_template("change_password.html", title="修改密码", form=form)
        current_user.set_password(form.new_password.data)
        # 改密后其它设备必须重新登录，也顺带作废所有未用完的一次性链接
        db.session.commit()
        logout_user()
        flash("密码修改成功，请用新密码重新登录。", "success")
        return redirect(url_for("login"))
    return render_template("change_password.html", title="修改密码", form=form)


def admin_required(view):
    """原来 is_admin 的判断在 7 个路由里各抄了一遍。"""
    from functools import wraps

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.path))
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------- 找回密码
# 免费套餐发不出邮件时，管理员手动重置是保底通道（/admin/users 页面里）。

@app.route("/password-reset", methods=["GET", "POST"])
@limiter.limit("5 per 10 minutes", methods=["POST"])
def request_password_reset():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter(db.func.lower(User.email)
                                 == normalize_email(form.email.data)).first()
        if user is not None:
            link = absolute_url("reset_password_with_token",
                                token=make_token("reset-password", user))
            sent = deliver_link(
                user, "重置密码",
                "你好 %s，\n\n有人请求重置你在「%s」的密码。"
                "如果不是你本人操作，请忽略本邮件。\n"
                "重置链接 1 小时内有效：\n%s" % (user.username, app.config["SITE_NAME"], link))
            app.logger.info("密码重置请求：user_id=%s 发信=%s", user.id, sent)
        # 无论邮箱是否存在，回复都一样，避免用来枚举注册用户
        flash("如果该邮箱已注册，重置链接已发送。若长时间未收到"
              "（免费套餐可能无法发信），请直接联系管理员重置。", "info")
        return redirect(url_for("login"))
    return render_template("reset_request.html", title="找回密码", form=form)


@app.route("/password-reset/<token>", methods=["GET", "POST"])
@limiter.limit("20 per hour")
def reset_password_with_token(token):
    user = read_token(token, "reset-password")
    if user is None:
        flash("重置链接无效或已过期，请重新申请。", "warning")
        return redirect(url_for("request_password_reset"))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        user.register_success()
        user.email_verified = True          # 能收mail=拥有该邮箱
        db.session.commit()
        flash("新密码已设置，请登录。", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html", title="设置新密码", form=form)


# ---------------------------------------------------------------- 管理后台

@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    page = request.args.get("page", 1, type=int)
    users = (User.query.order_by(User.created_at.desc())
             .paginate(page=page, per_page=25, error_out=True))
    return render_template("admin_users.html", title="用户管理", users=users)


AUDIT_ACTIONS = ("login", "logout", "register", "create", "update", "delete",
                 "gate", "export")   # export = 备份导出，也算“数据离开过站点”
AUDIT_EMPTY = "(无)"


_AUDIT_TABLE_OK = None


def _audit_table_ready():
    """audit_log 在不在。缓存结果：这是结构问题，跑一次命令就会 Reload。"""
    global _AUDIT_TABLE_OK
    if _AUDIT_TABLE_OK is None:
        _AUDIT_TABLE_OK = "audit_log" in existing_tables()
    return _AUDIT_TABLE_OK


def _empty_page():
    """给模板用的是 .items/.total/.has_prev… 都齐的对象（结构缺失时不走数据库）。"""
    from flask_sqlalchemy.pagination import Pagination
    return Pagination(query=None, page=1, per_page=50, max_per_page=200,
                      error_out=False, count=0, items=[])


@app.route("/admin/audit")
@login_required
@admin_required
def admin_audit():
    """操作审计：默认看最近 7 天，可按人/表/IP/关键字筛。只读页面。"""
    retention = audit_retention_days()
    # 下拉里的最大跨度就是保留期：更早的已经被自动过期删掉了，
    # 给个 365 的选项只会让人以为“下面还有，是我没翻到”。
    day_choices = sorted({d for d in (1, 3, 7, 14, 30, 60, 90, 180, 365) if d < retention})
    day_choices.append(retention)
    try:
        days = max(1, min(retention, int(request.args.get("days", 7))))
    except (TypeError, ValueError):
        days = min(7, retention)
    actor = (request.args.get("actor") or "").strip()[:150]
    ip = (request.args.get("ip") or "").strip()[:64]
    kw = (request.args.get("q") or "").strip()[:60]
    action = (request.args.get("action") or "").strip()[:12]
    table = (request.args.get("table") or "").strip()[:40]

    since = utcnow() - timedelta(days=days)
    q = AuditLog.query.filter(AuditLog.at >= since)
    if actor:
        q = q.filter(AuditLog.actor == actor)
    if ip:
        # 支持只填一半（10.1. 或 masked 后的 1.2.3.*）
        q = q.filter(AuditLog.ip.like(ip + "%"))
    if action in AUDIT_ACTIONS:
        q = q.filter(AuditLog.action == action)
    if table and re.match(r"^[a-z_][a-z0-9_]{0,39}$", table):
        q = q.filter(AuditLog.table == table)
    if kw:
        pat = "%" + like_arg(kw) + "%"          # 复用搜索那套 %/_/\ 转义
        q = q.filter(db.or_(AuditLog.detail.like(pat, escape=ESCAPE_CHAR),
                            AuditLog.actor.like(pat, escape=ESCAPE_CHAR),
                            AuditLog.row_id.like(pat, escape=ESCAPE_CHAR),
                            AuditLog.endpoint.like(pat, escape=ESCAPE_CHAR)))
    if not _audit_table_ready():
        # 忘记先跑 ensure-schema 是必然会踩的坑：给一句人话，而不是 500 堆栈
        flash("审计表还没建：在 Bash console 里跑 flask --app app ensure-schema（只建缺失的表/列，不动数据），然后重开这个页面。",
              "warning")
        return render_template("admin_audit.html", title="操作审计", rows=_empty_page(),
                               days=7, actor="", ip="", kw="", action="", table="",
                               stats={}, total=0, oldest=None, actions=AUDIT_ACTIONS,
                               tables=[], retention=retention, total_all=0,
                               day_choices=day_choices, expired=0)
    page = request.args.get("page", 1, type=int)
    rows = (q.order_by(AuditLog.at.desc(), AuditLog.id.desc())
            .paginate(page=page, per_page=50, error_out=False))

    # 顶部速览：总量 + 各动作条数。一次 GROUP BY，不逐条数。
    # 用 ORM 而不是 text()：裸 SQL 取 DATETIME 回来的是字符串（实测把 cn_time 打崩），
    # 交给表达式语言才会经过列类型转换。
    stats = dict(db.session.query(AuditLog.action, db.func.count())
                 .filter(AuditLog.at >= since).group_by(AuditLog.action).all())
    # “总量”说的是表里现存的全部条目，不是当前筛选窗口里的：两者混在一起标过两次人
    total_all = db.session.query(db.func.count(AuditLog.id)).scalar() or 0
    oldest = db.session.query(db.func.min(AuditLog.at)).scalar()
    return render_template("admin_audit.html", title="操作审计", rows=rows, days=days,
                           actor=actor, ip=ip, kw=kw, action=action, table=table,
                           stats=stats, total=sum(stats.values()), total_all=total_all,
                           oldest=oldest, actions=AUDIT_ACTIONS,
                           retention=retention, expired=audit_expired_count(),
                           day_choices=day_choices,
                           tables=[r[0] for r in db.session.query(AuditLog.table)
                                   .distinct().order_by(AuditLog.table).all()])


@app.route("/admin/audit/prune", methods=["POST"])
@login_required
@admin_required
@limiter.limit("6 per hour", methods=["POST"])
def admin_audit_prune():
    """手动清理旧审计记录 —— 免费套餐 500MB 配额 + SQLite，想删得更狠时用。
    上限锁在保留期：填 90 天而本站自动过期是 30 天，只会让人以为“90 天的东西还留着”，
    实际早删干净了；报出来的数字必须是真的发生过的删除。
    下限仍是 7 天，防手滑把“刚才那批”一起删掉。"""
    retention = audit_retention_days()
    try:
        want = int(request.form.get("keep_days", retention))
    except (TypeError, ValueError):
        want = retention
    keep = max(7, min(retention, want))
    cut = utcnow() - timedelta(days=keep)
    try:
        n = db.session.query(AuditLog).filter(AuditLog.at < cut).delete(
            synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("手动清理审计记录失败")
        flash("清理失败：数据库这会儿在写锁上排队，稍后再点一次。", "danger")
        return redirect(url_for("admin_audit"))
    if n:
        detail = ("清理审计记录：删除早于 %s 的 %d 条（保留 %d 天，本条本身在保留期内）"
                  % (cn_time(cut, "%Y-%m-%d %H:%M"), n, keep))
        if want > retention:
            detail += "；填的 %d 天超出本站保留期，按 %d 天执行" % (want, retention)
        audit_event("delete", detail[:280], "audit_log", "-")
    flash("已删除 %d 条早于 %s 的审计记录（本站保留期 %d 天，手动清理不得少于 7 天）"
          % (n or 0, cn_time(cut), retention), "success" if n else "info")
    return redirect(url_for("admin_audit"))


@app.route("/admin/user/<int:user_id>/trust", methods=["POST"])
@login_required
@limiter.limit("120 per hour", methods=["POST"])
@admin_required
def admin_user_trust(user_id):
    """开通/收回某个账号看到的真实内容。收回不等于冻结：他还能登录，只是回到门面。"""
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    want = (request.form.get("on") or "").strip() == "1"
    if bool(user.is_trusted) == want:
        flash("用户 %s 的状态本来就是这样，没做改动。" % user.username, "info")
        return redirect(url_for("admin_users"))
    user.is_trusted = want
    db.session.commit()
    audit_event("update", "账号%s @%s（%s看到%s）"
                % ("开通" if want else "收回", user.username[:30], user.username[:30],
                   "真实内容" if want else "门面内容"),
                "user", str(user.id))
    flash("已%s @%s：TA 现在看到%s。"
          % ("开通" if want else "收回", user.username,
             "真实内容" if want else "门面内容（未登录时看到的那一套）"), "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/trust_all", methods=["POST"])
@login_required
@limiter.limit("6 per hour", methods=["POST"])
@admin_required
def admin_users_trust_all():
    """一键开通所有在册成员 —— 加“默认不信任”这列时，老同学会被一起挡在门外，
    所以升级后的第一步就是按名单点一遍，或者用这个按钮全部放开再逐个收回。"""
    if request.form.get("confirm") != "1":
        flash("这个操作会一次改所有人的可见范围，请在弹窗里确认。", "warning")
        return redirect(url_for("admin_users"))
    n = (User.query.filter(User.is_trusted.isnot(True), User.is_admin.isnot(True))
         .update({"is_trusted": True}, synchronize_session=False))
    db.session.commit()
    audit_event("update", "一键开通全部成员的真实内容（新增 %d 人）" % (n or 0), "user", "-")
    flash("已开通 %s 个账号。之后新注册的仍是“未开通”，需要你再点一下。" % (n or 0),
          "success" if n else "info")
    return redirect(url_for("admin_users"))


@app.route("/admin/user/<int:user_id>/toggle_status", methods=["POST"])
@login_required
@limiter.limit("60 per hour", methods=["POST"])
@admin_required
def toggle_user_status(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash("不能冻结自己", "danger")
        return redirect(url_for("admin_users"))
    user.is_active = not user.is_active
    db.session.commit()
    flash("用户 %s 已%s" % (user.username, "激活" if user.is_active else "冻结"), "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/user/<int:user_id>/set_password", methods=["POST"])
@login_required
@limiter.limit("30 per hour", methods=["POST"])
@admin_required
def admin_set_password(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    form = AdminSetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        user.register_success()
        db.session.commit()
        # 让所有已签出的一次性链接立刻作废
        flash("已重置用户 %s 的密码，请把新密码转交给 TA。" % user.username, "success")
    else:
        flash("新密码不符合要求（至少 8 位）", "danger")
    return redirect(url_for("admin_users"))


def _delete_or_flash(obj, label):
    """删带子记录的行时，万一老库结构不配合（没有级联子句），
    回滚 + 说人话，而不是把 IntegrityError 抛成 500。"""
    try:
        db.session.delete(obj)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        app.logger.exception("删除%s失败", label)
        flash("%s下还有关联数据，数据库拒绝了删除，已记录日志。" % label, "danger")
        return False


@app.route("/admin/post/<int:post_id>/delete", methods=["POST"])
@login_required
@limiter.limit("60 per hour", methods=["POST"])
@admin_required
def delete_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        abort(404)
    if not _delete_or_flash(post, "帖子"):
        return redirect(request.referrer or url_for("index"))
    flash("帖子已删除", "success")
    return redirect(url_for("index"))


@app.route("/admin/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
@limiter.limit("120 per hour", methods=["POST"])
@admin_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        abort(404)
    post_id = comment.post_id
    if not _delete_or_flash(comment, "评论"):
        return redirect(url_for("post_detail", post_id=post_id))
    sync_post_counts(post_id)
    db.session.commit()
    flash("评论已删除", "success")
    return redirect(url_for("post_detail", post_id=post_id))


# ---------------------------------------------------------------- 投票

@app.route("/votes")
def votes_index():
    page = request.args.get("page", 1, type=int)
    active_votes = (VoteItem.query.filter_by(is_active=True)
                    .order_by(VoteItem.created_at.desc())
                    .paginate(page=page, per_page=10, error_out=True))
    voted_ids = set()
    if current_user.is_authenticated:
        voted_ids = {r.vote_item_id for r in
                     VoteRecord.query.filter_by(user_id=current_user.id).all()}
    return render_template("votes_index.html", title="新功能投票", votes=active_votes,
                           user_voted_ids=voted_ids)


@app.route("/admin/vote/create", methods=["GET", "POST"])
@login_required
@limiter.limit("20 per hour", methods=["POST"])
@admin_required
def create_vote():
    form = VoteCreateForm()
    if form.validate_on_submit():
        new_vote = VoteItem(title=form.title.data.strip(),
                            description=form.description.data,
                            user_id=current_user.id)
        db.session.add(new_vote)
        db.session.flush()
        # 原实现是 form.option3.data.strip()：字段为 None 时会抛 AttributeError；
        # 现在只有 1-2 个非空选项时直接拒绝，而不是建出一个没法投的投票
        texts = [form.option1.data, form.option2.data,
                 (form.option3.data or "").strip(), (form.option4.data or "").strip()]
        texts = [t for t in texts if t]
        if len(texts) < 2 or len(set(texts)) != len(texts):
            db.session.rollback()
            flash("至少需要 2 个互不相同的选项。", "danger")
            return render_template("create_vote.html", title="创建投票", form=form)
        for text_ in texts:
            db.session.add(VoteOption(option_text=text_[:200], vote_item_id=new_vote.id))
        db.session.commit()
        flash("投票发布成功！", "success")
        return redirect(url_for("votes_index"))
    return render_template("create_vote.html", title="创建投票", form=form)


@app.route("/vote/<int:vote_item_id>/submit/<int:option_id>", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def submit_vote(vote_item_id, option_id):
    """P0 修复：
    1) 必须校验 option_id 真的属于 vote_item_id —— 原实现用
       VoteOption.query.get_or_404(option_id) 直接加票，实测
       POST /vote/1/submit/2 能把票灌到另一个投票的选项上，
       而且不消耗自己的投票名额，可以无限刷。
    2) 计数与记录写在同一条语句里（条件 UPDATE + rowcount 判定），
       避免“两个请求同时读到 None 然后都插入撞唯一键”的竞态。
    """
    vote_item = db.session.get(VoteItem, vote_item_id)
    if vote_item is None:
        abort(404)
    if not vote_item.is_active:
        flash("该投票已结束，无法提交新的投票", "warning")
        return redirect(url_for("votes_index"))
    result = db.session.execute(
        update(VoteOption)
        .where(VoteOption.id == option_id,
               VoteOption.vote_item_id == vote_item_id)
        .values(vote_count=VoteOption.vote_count + 1))
    if result.rowcount != 1:
        db.session.rollback()
        abort(404)
    db.session.add(VoteRecord(user_id=current_user.id, vote_item_id=vote_item_id,
                              vote_option_id=option_id))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("你已经在该投票中投过票了。", "warning")
        return redirect(url_for("votes_index"))
    flash("投票提交成功，感谢你的反馈！", "success")
    return redirect(url_for("votes_index"))


@app.route("/admin/vote/<int:vote_item_id>/finish", methods=["POST"])
@login_required
@limiter.limit("60 per hour", methods=["POST"])
@admin_required
def finish_vote(vote_item_id):
    vote_item = db.session.get(VoteItem, vote_item_id)
    if vote_item is None:
        abort(404)
    vote_item.is_active = False
    db.session.commit()
    flash("该投票已成功结束", "success")
    return redirect(url_for("votes_index"))


@app.route("/admin/vote/<int:vote_item_id>/delete", methods=["POST"])
@login_required
@limiter.limit("60 per hour", methods=["POST"])
@admin_required
def delete_vote(vote_item_id):
    vote_item = db.session.get(VoteItem, vote_item_id)
    if vote_item is None:
        abort(404)
    if not _delete_or_flash(vote_item, "投票"):
        return redirect(url_for("votes_index"))
    flash("该投票已删除", "success")
    return redirect(url_for("votes_index"))



# ─────────────────────────────────────────────────────────── 公告
def live_announcements(limit=3):
    """当前有效（未下架、未过期）的公告，置顶优先。"""
    if "announcement" not in existing_tables():
        return []
    now = utcnow()
    return (Announcement.query.filter(Announcement.is_active.is_(True))
            .filter(db.or_(Announcement.expires_at.is_(None),
                           Announcement.expires_at > now))
            .order_by(Announcement.pinned.desc(), Announcement.at.desc())
            .limit(limit).all())


def banner_announcement():
    """首页顶部那条横幅：**只给置顶公告**。
    原来写成“最新一条有效公告”，与后台勾选框上写的“置顶（进首页横幅）”不一致，
    结果是任何人发一条普通公告就会把横幅劫走。不置顶的公告仍然：出现在 /announcements
    列表里、并且照常给全员发站内通知，所以不会漏消息。"""
    for a in live_announcements(20):
        if a.pinned:
            return a
    return None


@app.route("/announcements")
def announcements():
    """公告列表：只列有效条目（下架/过期的不展示，但仍在后台可见）。"""
    page = request.args.get("page", 1, type=int)
    now = utcnow()
    rows = (Announcement.query.filter(Announcement.is_active.is_(True))
            .filter(db.or_(Announcement.expires_at.is_(None), Announcement.expires_at > now))
            .order_by(Announcement.pinned.desc(), Announcement.at.desc())
            .paginate(page=page, per_page=15, error_out=False))
    return render_template("announcements.html", title="公告", rows=rows)


class AnnouncementForm(FlaskForm):
    title = StringField("标题", validators=[DataRequired(), Length(2, 200)])
    body = TextAreaField("正文", validators=[DataRequired(), Length(1, 30000)])
    pinned = BooleanField("置顶（首页横幅展示）")
    days = StringField("有效天数（留空=长期）", validators=[Optional(), Length(0, 6)])
    submit = SubmitField("发布")


@app.route("/admin/announcements", methods=["GET", "POST"])
@login_required
@admin_required
@limiter.limit("20 per hour", methods=["POST"])
def admin_announcements():
    """发公告；编辑/下架/删除各自单独 POST，方便审计逐条追责。"""
    form = AnnouncementForm()
    if form.validate_on_submit():
        expires = None
        raw_days = (form.days.data or "").strip()
        if raw_days:
            try:
                d = int(raw_days)
                if 0 < d <= 3650:
                    expires = utcnow() + timedelta(days=d)
            except ValueError:
                pass
        a = Announcement(title=form.title.data.strip()[:200], body=form.body.data,
                         pinned=bool(form.pinned.data), expires_at=expires,
                         user_id=current_user.id)
        a.sanitize_body()
        db.session.add(a)
        db.session.commit()
        n = notify_announcement(a)
        flash("公告已发布，%d 人收到站内通知。" % n, "success")
        return redirect(url_for("announcements"))
    allrows = Announcement.query.order_by(Announcement.at.desc()).limit(200).all()
    return render_template("admin_announcements.html", title="公告管理", form=form,
                           allrows=allrows, now=utcnow())


def notify_announcement(a):
    """新公告给所有未冻结账号发一条站内通知（除发布者本人）。"""
    n = 0
    for u in User.query.filter(User.is_active.is_(True)).all():
        # actor 得显式排除发布者：这里没有 actor 对象，用 exclude 表达“自己不通知自己”
        if notify(u.id, "announce", "announce:%s:%s" % (a.id, u.id),
                  actor=None, excerpt=a.title[:200], announcement_id=a.id,
                  exclude=a.user_id):
            n += 1
    return n


@app.post("/admin/announcement/<int:aid>/toggle")
@login_required
@admin_required
@limiter.limit("60 per hour", methods=["POST"])
def admin_announcement_toggle(aid):
    a = db.session.get(Announcement, aid)
    if a is None:
        abort(404)
    a.is_active = not a.is_active
    a.edited_at = utcnow()
    db.session.commit()
    flash("公告已%s。" % ("重新上架，会再给全员发一次通知" if a.is_active else "下架（历史保留，不是删除）"),
          "success")
    if a.is_active:
        notify_announcement(a)
    return redirect(url_for("admin_announcements"))


@app.post("/admin/announcement/<int:aid>/pin")
@login_required
@admin_required
@limiter.limit("60 per hour", methods=["POST"])
def admin_announcement_pin(aid):
    a = db.session.get(Announcement, aid)
    if a is None:
        abort(404)
    a.pinned = not a.pinned
    a.edited_at = utcnow()
    db.session.commit()
    flash("置顶状态已切换。", "success")
    return redirect(url_for("admin_announcements"))


@app.post("/admin/announcement/<int:aid>/delete")
@login_required
@admin_required
@limiter.limit("20 per hour", methods=["POST"])
def admin_announcement_delete(aid):
    a = db.session.get(Announcement, aid)
    if a is None:
        abort(404)
    db.session.delete(a)
    db.session.commit()
    flash("公告已删除（这条删除动作本身在操作审计里）。", "success")
    return redirect(url_for("admin_announcements"))


# ───────────────────────────────────────────────────────── 通知中心
NOTIF_LABEL = {"mention": "有人 @ 了你", "reply": "帖子有新回答",
               "accept": "你的回答被采纳", "announce": "新公告"}


def unread_count(uid):
    if not uid or "notification" not in existing_tables():
        return 0
    return Notification.query.filter(Notification.user_id == uid,
                                     Notification.read_at.is_(None)).count()


@app.route("/notifications")
@login_required
def notifications():
    """我的站内信。?only=unread 只看未读。"""
    page = request.args.get("page", 1, type=int)
    q = Notification.query.filter_by(user_id=current_user.id)
    only = (request.args.get("only") or "").strip()
    if only == "unread":
        q = q.filter(Notification.read_at.is_(None))
    rows = q.order_by(Notification.read_at.isnot(None), Notification.at.desc(),
                      Notification.id.desc()).paginate(page=page, per_page=30,
                                                       error_out=False)
    return render_template("notifications.html", title="通知", rows=rows, only=only,
                           unread=unread_count(current_user.id), label=NOTIF_LABEL)


@app.post("/notifications/<int:nid>/read")
@login_required
@limiter.limit("120 per hour", methods=["POST"])
def notification_read(nid):
    """标已读/未读。只认自己的行：别人的 id 一律 404，不给枚举线索。"""
    n = db.session.get(Notification, nid)
    if n is None or n.user_id != current_user.id:
        abort(404)
    n.read_at = None if request.form.get("unset") else utcnow()
    db.session.commit()
    return redirect(request.referrer or url_for("notifications"))


@app.post("/notifications/read-all")
@login_required
@limiter.limit("20 per hour", methods=["POST"])
def notification_read_all():
    n = Notification.query.filter(Notification.user_id == current_user.id,
                                 Notification.read_at.is_(None)).update(
        {"read_at": utcnow()}, synchronize_session=False)
    db.session.commit()
    flash("已标记 %d 条为已读。" % n, "success" if n else "info")
    return redirect(url_for("notifications"))


@app.post("/post/<int:post_id>/watch")
@login_required
@limiter.limit("60 per hour", methods=["POST"])
def watch_toggle(post_id):
    """关注/取消关注一帖（有新回答就叫我）。"""
    post = db.session.get(Post, post_id)
    if post is None:
        abort(404)
    from sqlalchemy import select as _sel
    hit = db.session.execute(_sel(PostWatch).where(PostWatch.post_id == post_id,
                                                   PostWatch.user_id == current_user.id)).scalar()
    if hit:
        db.session.delete(hit)
        msg = "已取消关注该帖。"
    else:
        db.session.add(PostWatch(post_id=post_id, user_id=current_user.id))
        msg = "已关注：这个帖有新回答会通知你。"
    db.session.commit()
    flash(msg, "info")
    return redirect(url_for("post_detail", post_id=post_id))


# ───────────────────────────────────────────────────── 个人主页
@app.route("/u/<username>")
@login_required
def user_profile(username):
    """某人发过什么。只给用户名/注册时间/帖子与回答数——不给邮箱、不给 IP。"""
    u = User.query.filter(db.func.lower(User.username) == (username or "").lower()).first()
    if u is None or not u.is_active:
        abort(404)
    page = request.args.get("page", 1, type=int)
    posts = (Post.query.filter_by(user_id=u.id).order_by(Post.timestamp.desc())
             .paginate(page=page, per_page=15, error_out=False))
    return render_template("user_profile.html", title="成员 · %s" % u.username,
                           person=u, posts=posts,
                           answering=Comment.query.filter_by(user_id=u.id).count())


# ───────────────────────────────────────────────────────── 备份导出
BACKUP_BYTES_LIMIT = 64 * 1024 * 1024      # 快照超过这个体积就别塞进内存，用 CLI
EXPORT_TABLES = ("user", "post", "comment", "like", "comment_like", "tag", "post_tag",
                 "vote_item", "vote_option", "vote_record", "announcement",
                 "notification", "post_watch", "audit_log", "gate_attempt")
# 公开导出（给别人看/自己存档）保留的内容；完整备份才会带这些
PUBLIC_TABLES = ("post", "comment", "like", "comment_like", "tag", "post_tag",
                 "vote_item", "vote_option", "vote_record", "announcement")
USER_PUBLIC_COLS = ("username", "created_at")          # 公开档里的人只到用户名


def _db_path():
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    return uri[9:] if uri.startswith("sqlite:///") else None


def _snapshot(dst_path):
    """用 SQLite 的 backup API 出一份一致性快照。

    绝不能用 shutil.copy：正在写入时直接复制文件，拿到的是撕裂的库
    （journal 模式下页面与 -wal 不同步），那种“备份”恢复时才发现问题就晚了。"""
    src_file = _db_path()
    if not src_file or not os.path.exists(src_file):
        return None
    src = sqlite3.connect(src_file, timeout=15)
    dst = sqlite3.connect(dst_path)
    try:
        with dst:
            src.backup(dst)
        return os.path.getsize(dst_path)
    finally:
        dst.close()
        src.close()


def _snapshot_rows(path, tables):
    out = {}
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in tables:
            if t not in have or not IDENT_RE.match(t):
                continue
            out[t] = [dict(r) for r in con.execute("SELECT * FROM %s" % _q(t))]
        return out
    finally:
        con.close()


def _q(name):
    return '"' + name.replace('"', "") + '"'


def build_json(private=False):
    """把库导成一份 JSON。private=False 时是“内容档”：
    不含 password_hash / email / 审计 / 闸门尝试。"""
    tmp = os.path.join(basedir, "backups", ".snap-export.db")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    size = _snapshot(tmp)
    if size is None:
        return None, None
    try:
        tables = EXPORT_TABLES if private else (PUBLIC_TABLES + ("user",))
        data = _snapshot_rows(tmp, tables)
        if not private:
            for r in data.get("user", []):
                for k in list(r):
                    if k not in USER_PUBLIC_COLS:
                        r.pop(k, None)
        payload = {"_meta": {"site": app.config["SITE_NAME"],
                             "exported_at": utcnow().isoformat() + "Z",
                             "private": bool(private),
                             "tables": sorted(data)},
                   "data": data}
        body = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
        return io.BytesIO(body), "forum-%s%s.json" % (
            utcnow().strftime("%Y%m%d-%H%M%S"), "-private" if private else "")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


MD_HEAD = ("---\ntitle: {title}\nauthor: {author}\nposted: {posted}\n"
           "language: {lang}\nsolved: {solved}\ntags: {tags}\nid: {pid}\n---\n\n")


def build_md_zip():
    """帖子/回答/公告导出成 Markdown 打包 —— 脱离本站也永远能读，最适合留档。"""
    tmp = os.path.join(basedir, "backups", ".snap-export.db")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    if _snapshot(tmp) is None:
        return None
    buf = io.BytesIO()
    try:
        data = _snapshot_rows(tmp, ("user", "post", "comment", "tag", "post_tag",
                                    "announcement"))
        users = {u["id"]: u.get("username") or "?" for u in data.get("user", [])}
        tagnames = {t["id"]: t.get("name") for t in data.get("tag", [])}
        tags_of = {}
        for link in data.get("post_tag", []):
            tags_of.setdefault(link.get("post_id"), []).append(
                tagnames.get(link.get("tag_id"), ""))
        by_post = {}
        for cm in sorted(data.get("comment", []), key=lambda c: c.get("id") or 0):
            by_post.setdefault(cm.get("post_id"), []).append(cm)
        z = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)
        posts = sorted(data.get("post", []), key=lambda p: p.get("id") or 0)
        used = set()
        for p in posts:
            slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", str(p.get("title") or ""))
            slug = (slug.strip("-")[:40] or "post").strip("-") or "post"
            name = "%05d-%s.md" % (p.get("id") or 0, slug)
            n = 2
            while name in used:                        # 同一 id 前缀仍可能撞名，加序号别互相覆盖
                name = "%05d-%s-%d.md" % (p.get("id") or 0, slug, n); n += 1
            used.add(name)
            body = [MD_HEAD.format(title=p.get("title") or "", author=users.get(p.get("user_id"), "?"),
                                   posted=str(p.get("timestamp"))[:19], lang=p.get("language") or "",
                                   solved="yes" if p.get("is_solved") else "no",
                                   tags=", ".join(t for t in tags_of.get(p.get("id"), []) if t),
                                   pid=p.get("id")),
                    (p.get("content") or "").rstrip(), ""]
            cms = by_post.get(p.get("id"), [])
            if cms:
                body += ["", "## 回答（%d）" % len(cms), ""]
                for cm in cms:
                    mark = " ✅已采纳" if p.get("accepted_comment_id") == cm.get("id") else ""
                    body += ["- **%s**%s · %s" % (users.get(cm.get("user_id"), "?"), mark,
                                                  str(cm.get("timestamp"))[:19]), "",
                             (cm.get("body") or "").replace("\n", "\n  ").rstrip(), ""]
            z.writestr("posts/" + name, "\n".join(body))
        anns = sorted(data.get("announcement", []), key=lambda a: a.get("id") or 0)
        for a in anns:
            z.writestr("announcements/%05d.md" % (a.get("id") or 0),
                       "# %s\n\n> %s · %s\n\n%s\n" % (
                           a.get("title") or "", users.get(a.get("user_id"), "?"),
                           str(a.get("at"))[:19], (a.get("body") or "").rstrip()))
        index = ["# %s 存档" % app.config["SITE_NAME"], "",
                 "导出时间：%s UTC | 帖子 %d 篇 | 回答 %d 条 | 公告 %d 条"
                 % (utcnow().strftime("%Y-%m-%d %H:%M"), len(posts),
                    len(data.get("comment", [])), len(anns)), ""]
        for p in posts:
            index.append("- [(%s)](posts/%05d-%s.md)" % (
                str(p.get("timestamp"))[:10], p.get("id") or 0,
                re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", str(p.get("title") or "")).strip("-")[:40] or "post"))
        z.writestr("README.md", "\n".join(index) + "\n")
        z.writestr("manifest.json", json.dumps(
            {"exported_at": utcnow().isoformat() + "Z", "counts": {
                "posts": len(posts), "comments": len(data.get("comment", [])),
                "announcements": len(anns)}}, ensure_ascii=False, indent=1).encode("utf-8"))
        z.close()
        buf.seek(0)
        return buf
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


@app.route("/admin/backup")
@login_required
@admin_required
def admin_backup():
    """备份页：能看到每种导出【具体含不含有哪些东西】，不玩文字游戏。"""
    path = _db_path()
    size = os.path.getsize(path) if path and os.path.exists(path) else 0
    with app.app_context():
        counts = {}
        for t, model in (("帖子", Post), ("回答", Comment), ("成员", User),
                         ("公告", Announcement), ("通知", Notification),
                         ("审计", AuditLog)):
            try:
                counts[t] = model.query.count()
            except Exception:
                counts[t] = 0
    return render_template("admin_backup.html", title="备份与导出", size=size,
                           counts=counts, limit=BACKUP_BYTES_LIMIT,
                           path=path, backup_dir=os.path.join(basedir, "backups"),
                           # 开关当前状态：模板要靠它决定哪个按钮是“反悔”、哪个是“危险”
                           demo_on=demo_mode_on())


def _big_db_guard():
    path = _db_path()
    size = os.path.getsize(path) if path and os.path.exists(path) else 0
    if size > BACKUP_BYTES_LIMIT:
        flash("数据库已有 %.1f MB，超过在线下载上限（%.0f MB）。"
              "用命令行备份：flask --app app backup" % (size / 1048576.0,
                                                        BACKUP_BYTES_LIMIT / 1048576.0),
              "danger")
        return False
    return True


@app.post("/admin/display_mode")
@login_required
@admin_required
@limiter.limit("20 per hour", methods=["POST"])
def admin_display_mode():
    """切换“未登录访客看到什么”。“真实数据”是刻意往外走的一步，所以确认框与审计都留全。"""
    want = (request.form.get("mode") or "").strip()
    if want not in ("0", "1"):
        flash("没收到要切换成哪种状态。", "danger")
        return redirect(url_for("admin_backup"))
    import demo as _demo   # 演示内容的条数写进审计，将来有人问“当时展示的是啥”有据可查
    before = "真实内容" if demo_flag_value() == "0" else "门面内容"
    after = "真实内容" if want == "0" else "门面内容"
    if not set_demo_mode(want):
        flash("保存失败：库里还没有 site_flag 表。在 Bash console 跑一次 "
              "flask --app app ensure-schema（只建缺失的表，不动数据），再回来点一次。", "danger")
        return redirect(url_for("admin_backup"))
    # 状态切换必须留下“谁、什么时候、从哪儿改的”
    audit_event("update", "对外展示切换：%s → %s（未登录访客看到的%s；演示内容是 %d 篇示例帖）"
                % (before, after, after, len(_demo.POSTS)), "site_flag", DEMO_KEY_NAME)
    flash("未登录访客现在看到%s。你自己登录着，所以现在仍看到真实站点——"
          "要看访客视角请另开一个未登录的浏览器窗口。" % after, "success")
    return redirect(url_for("admin_backup"))


@app.post("/admin/backup/db")
@login_required
@admin_required
@limiter.limit("6 per hour", methods=["POST"])
def admin_backup_db():
    """整库快照下载（含哈希与审计）——只有这个能真正还原站点。"""
    if not _big_db_guard():
        return redirect(url_for("admin_backup"))
    tmp = os.path.join(basedir, "backups", ".dl.db")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    try:
        if _snapshot(tmp) is None:
            flash("找不到数据库文件，检查 DATABASE_URI。", "danger")
            return redirect(url_for("admin_backup"))
        data = io.BytesIO(open(tmp, "rb").read())
        name = "forum-%s.db" % utcnow().strftime("%Y%m%d-%H%M%S")
        audit_event("export", "下载整库快照备份（含口令哈希与审计）", "backup", "-")
        return send_file(data, mimetype="application/octet-stream", as_attachment=True,
                         download_name=name)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


@app.post("/admin/backup/json")
@login_required
@admin_required
@limiter.limit("10 per hour", methods=["POST"])
def admin_backup_json():
    private = request.form.get("private") == "1"
    if not _big_db_guard():
        return redirect(url_for("admin_backup"))
    bio, name = build_json(private=private)
    if bio is None:
        flash("数据库文件不存在，无法导出。", "danger")
        return redirect(url_for("admin_backup"))
    audit_event("export", "导出 JSON：%s" % ("完整档（含哈希/邮箱/审计）" if private else "内容档（无敏感字段）"),
                "backup", "-")
    return send_file(bio, mimetype="application/json", as_attachment=True, download_name=name)


@app.post("/admin/backup/md")
@login_required
@admin_required
@limiter.limit("10 per hour", methods=["POST"])
def admin_backup_md():
    buf = build_md_zip()
    if buf is None:
        flash("导出失败：数据库快照不可用。", "danger")
        return redirect(url_for("admin_backup"))
    audit_event("export", "导出 Markdown 存档包（帖子/回答/公告）", "backup", "-")
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name="forum-archive-%s.zip" % utcnow().strftime("%Y%m%d-%H%M%S"))



# ---------------------------------------------------------------- 错误页
# 沿用你原来的写法：render_template('errors/xxx.html'), 状态码。
# 之前的问题是这些模板文件在仓库里根本不存在，所以任何 404 都会“处理异常时再抛异常”，
# 429（限流命中）也一样 —— 把文件补上就好，不用改机制。

@app.errorhandler(404)
def not_found(error):
    return render_template("errors/404.html"), 404


@app.errorhandler(403)
def forbidden(error):
    return render_template("errors/403.html"), 403


@app.errorhandler(429)
def ratelimit_handler(error):
    return render_template("errors/429.html"), 429


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("errors/500.html"), 500


@app.errorhandler(CSRFError)
def csrf_failed(error):
    """把“校验没过”变成一句话能看懂的页面 + 一行能定位问题的日志。
    只记录 token 前 6 位：完整 token 等同于登录凭据，不能进日志。"""
    form_token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or ""
    session_token = session.get(CSRF_SESSION_KEY) or ""
    app.logger.warning(
        "CSRF 失败 reason=%s | scheme=%s host=%s | 浏览器带回 session cookie=%s | "
        "新会话=%s | 表单token=%s... session里token=%s... | referer=%s | ua=%s",
        error.description, request.scheme, request.host,
        "session" in request.cookies, not session_token,
        form_token[:6], session_token[:6],
        request.headers.get("Referer"), request.headers.get("User-Agent", "")[:60])
    return _http_error_page(error, "400", 400, reason=error.description)


@app.errorhandler(400)
def bad_request(error):
    reason = getattr(error, "description", "") or ""
    return _http_error_page(error, "400", 400, reason=reason)


def _http_error_page(error, name, code, reason=""):
    try:
        return render_template("errors/%s.html" % name, reason=reason), code
    except Exception:
        app.logger.exception("错误页 templates/errors/%s.html 渲染失败", name)
        return "请求无效（%s）" % code, code


# ---------------------------------------------------------------- 内容安全策略
# Tailwind 已本地编译、行为脚本已自建，所以这里可以不开 'unsafe-inline'：
# 只放行自站 + Font Awesome 的 cdnjs（样式/字体）。style-src-attr 是给
# 进度条 style="width:…" 和卡片 style="--i:…" 这类属性用的。
_CSP = ("default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com; "
        # 模板里已无内联 style，所以不再放开 style-src-attr；
        # 一旦哪天手滑加回 style=\"...\"，浏览器会直接报违规而不是静默生效。
        "style-src 'self' https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com data:; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'; "
        "require-trusted-types-for 'script'")
_LOCAL_BUILT_CSS = os.path.join(basedir, "static", "css", "tailwind.css")


@app.route("/robots.txt")
def robots_txt():
    """禁收录的第三层（前两层：X-Robots-Tag 每个响应都带、模板里 <meta name=robots>）。

    这条路必须在前厅闸门【之前】放行（见 gate.PUBLIC_PATHS）：未解锁时若这里返回
    404，主流爬虫的解读是“没拿到指令 = 允许抓”，反而把拦截效果反过来了。
    Disallow 本身只是“请求你别来”，不守规矩的爬虫照抓 —— 真正让它进不了索引的是
    noindex 那个头，所以那两层才是主力。
    """
    return robots_txt_body(), 200, {"Content-Type": "text/plain; charset=utf-8",
                                    # 这个头就是给爬虫看的，缓存一小时足够；模式切换要
                                    # 立刻生效，所以不给更长的时间
                                    "Cache-Control": "public, max-age=3600"}


@app.route("/favicon.ico")
def favicon():
    # 浏览器每次都会要它；没有的话日志和控制台一直刷 404
    from flask import send_from_directory
    d = os.path.join(app.static_folder or "", "img")
    path = os.path.join(d, "favicon.svg")
    if os.path.exists(path):
        return send_from_directory(d, "favicon.svg", mimetype="image/svg+xml")
    return ("", 204, {"Content-Type": "image/png"})


@app.after_request
def set_csp(response):
    """只在自建 CSS 确实存在时才发 CSP —— 半部署（只传了模板没传 static/）
    本来就会白屏，再加一条 CSP 只会让它更难回滚。"""
    if not os.path.exists(_LOCAL_BUILT_CSS):
        return response
    if not response.mimetype.startswith("text/html"):
        return response
    header = ("Content-Security-Policy-Report-Only"
              if os.environ.get("CSP_REPORT_ONLY") == "1" else "Content-Security-Policy")
    response.headers.setdefault(header, _CSP)
    return response


# ---------------------------------------------------------------- 命令行

def _bootstrap_admin(email=None, password=None):
    if User.query.filter(db.func.lower(User.email) == (email or "admin@admin.com")).first():
        return None
    email = email or "admin@admin.com"
    taken = User.query.filter(db.func.lower(User.username) == "admin").first()
    admin = User(username="admin" if taken is None else "site-admin",
                 email=email, is_admin=True, email_verified=True)
    generated = None
    if not password:
        password = generated = secrets.token_urlsafe(12)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    if generated:
        click_echo("已创建管理员 %s / 随机密码（只显示这一次）：%s" % (email, generated))
    else:
        click_echo("已创建管理员 %s" % email)
    return admin


def click_echo(msg):
    print(msg)


@app.cli.command("init-db")
def init_db_command():
    """建表 + 增量补列 + 建管理员。PA 上跑一次即可（WSGI 导入不会执行这段）。"""
    db.create_all()
    changed = ensure_schema()
    _bootstrap_admin(os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD"))
    sync_all_counts()
    print("init-db 完成；补充的列/索引：%s" % (", ".join(changed) or "无"))


@app.cli.command("ensure-schema")
def ensure_schema_command():
    """老库升级：建缺失的好表（新功能的关联表）+ 加缺失的列/索引，不动已有数据。"""
    db.create_all()                      # 先补表，否则老库上删帖会因为缺 comment_like 报 500
    changed = ensure_schema()
    print("补充：%s" % (", ".join(changed) or "无（结构已是最新）"))


@app.cli.command("backup")
def backup_command():
    """整库快照备份到 backups/，只留最近 7 份。定时任务里跑这条就没人需要手工操心。"""
    d = os.path.join(basedir, "backups")
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "forum-%s.db" % utcnow().strftime("%Y%m%d-%H%M%S"))
    size = _snapshot(dst)
    if size is None:
        print("备份失败：找不到数据库文件（检查 DATABASE_URI）")
        return
    try:
        # 备份里有口令哈希与全量审计（含 IP），权限收紧到只有账号本人可读
        os.chmod(dst, 0o600)
        os.chmod(d, 0o700)
    except OSError:
        pass
    print("已备份 %s（%.2f MB，权限 600）" % (dst, size / 1048576.0))
    # 校验快照真能打开且表齐 —— 备份最怕的是“文件在、内容废”
    con = sqlite3.connect(dst)
    try:
        n = con.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        ok = con.execute("PRAGMA integrity_check").fetchone()[0]
        print("  表 %d 张，integrity_check=%s" % (n, ok))
    finally:
        con.close()
    keep = 7
    olds = sorted(f for f in os.listdir(d) if f.startswith("forum-") and f.endswith(".db"))
    for f in olds[:-keep]:
        os.remove(os.path.join(d, f))
        print("  清理旧备份：%s" % f)


@app.cli.command("prune-audit")
def prune_audit_command():
    """审计自动过期：删掉超过保留期（AUDIT_RETENTION_DAYS，默认 30 天）的条目。
    在 PA 控制台 Scheduled Tasks 里加一条每天跑（时间点随便，命令本身可重复执行）：
        /home/<用户名>/.venv/bin/flask --app app prune-audit
    不配也没关系：有人访问时会顺手清（auto_expire_audit，每进程最多 6 小时一次）。
    删掉的条数会作为一条 delete 审计留下，所以“日志被清过”永远查得到。"""
    days = audit_retention_days()
    n = purge_expired_audit("定时任务")
    print("审计保留期 %d 天：本次删除 %d 条早于 %s 的记录"
          % (days, n, cn_time(utcnow() - timedelta(days=days), "%Y-%m-%d %H:%M")))
    print("  剩余 %d 条。注意 SQLite 删完不会把空间还给操作系统，"
          "forum.db 文件不变小是预期的（空页会被后续写入复用）。" % AuditLog.query.count())


@app.cli.command("sync-counts")
def sync_counts_command():
    """重算所有帖子的评论/点赞计数列（计数列与真值不一致时手动纠正）。"""
    sync_all_counts()
    print("已重算计数列")


def sync_all_counts():
    tables = existing_tables()
    if "post" not in tables:
        return
    for post_id in [r[0] for r in db.session.execute(text("SELECT id FROM post"))]:
        sync_post_counts(post_id)
    db.session.commit()
    if "vote_record" not in tables or "vote_item" not in tables:
        return
    for vote_id in [r[0] for r in db.session.execute(text("SELECT id FROM vote_item"))]:
        db.session.execute(text(
            "UPDATE vote_option SET vote_count = "
            "(SELECT count(*) FROM vote_record WHERE vote_record.vote_option_id = vote_option.id) "
            "WHERE vote_item_id = :v"), {"v": vote_id})
    db.session.commit()


@app.cli.command("gen-pygments-css")
def gen_pygments_css_command():
    """换高亮主题（PYG_STYLE=…）后重新生成 static/css/pygments.css。"""
    from pygments.formatters import HtmlFormatter as _HF
    path = os.path.join(basedir, "static", "css", "pygments.css")
    old = open(path).read() if os.path.exists(path) else ""
    cut = old.find(".post-body .hl {")            # 前面那段是容器/行号样式，保留
    keep = old[:cut] if cut > 0 else ""
    style = os.environ.get("PYG_STYLE", "monokai")
    css = _HF(style=style, cssclass="hl").get_style_defs(".post-body .hl")
    # 主题自带背景放中间，容器底色覆盖放最后，保证跟随站点主题
    tail = ("\n/* 末尾覆盖：代码块容器底色跟随站点主题 */\n"
            ".post-body .hl { background:#12151a; border:1px solid #262d38; }\n"
            ".post-body .hl pre { background:transparent; color:#e7e9ee; }\n")
    with open(path, "w") as fh:
        fh.write(keep + css + tail)
    print("已生成 %s（style=%s）" % (path, style))


@app.cli.command("backfill-render")
def backfill_render_command():
    """用当前渲染管线重算所有历史正文/评论的 *_html。
    上线代码块渲染后跑一次即可；content 原文不动，所以可反复执行。"""
    n = 0
    for post in Post.query.yield_per(100):
        post.content_html = render_body(post.content, post.language)
        n += 1
    for c in Comment.query.yield_per(100):
        c.body_html = render_body(c.body, c.language)
        n += 1
    db.session.commit()
    print("已重算 %d 条正文/评论" % n)


# ---------------------------------------------------------------- 运行状态
_BOOT_AT = time.time()           # 进程启动时刻：改完环境变量要不要 Reload，看这个就知道

# 配额提醒线：PA 免费套餐的硬盘配额是 500MB，留点余量提前吆喝
DISK_WARN_BYTES = 320 * 1024 * 1024


def health_snapshot():
    """跑一遍所有自检，返回 (要处理的问题, 状态行)。

    只读，不改任何东西；面板和命令行 `flask --app app doctor` 调的是同一个函数 ——
    两处各写一遍检查结果，早晚会互相说不清是哪个坏了。
    状态行是 (标签, 值, 是否异常) —— 异常的那几个在面板上标黄，但没到“要处理”的程度。
    """
    problems, notes = [], []
    tables = existing_tables()

    # —— 部署：这些出事时页面往往是好的，坏在下次重启或别人换设备登录那一刻
    if not os.environ.get("SECRET_KEY"):
        problems.append("环境变量 SECRET_KEY 未设置（正在用随机值，重启会全员掉线）")
    notes.append(("SECRET_KEY", "来自环境变量" if os.environ.get("SECRET_KEY") else "随机值（危险）",
                  not os.environ.get("SECRET_KEY")))
    notes.append(("本进程启动于", cn_time(datetime.fromtimestamp(_BOOT_AT, timezone.utc),
                                      "%m-%d %H:%M") + "（北京时间）", False))
    if not os.environ.get("ALLOWED_HOSTS"):
        problems.append("提示：ALLOWED_HOSTS 未设置 —— 换域名或被 IP 直连时，"
                        "https 跳转那道校验会跟着 Host 走（设成你的域名，逗号分隔多个）")
    notes.append(("前厅闸门", "开着（口令用哈希配置）" if (gate_enabled_now() and gate_has_hash())
                  else ("开着，但口令是明文环境变量" if gate_enabled_now() else "已关（GATE_ENABLED=0）"),
                  gate_enabled_now() and not gate_has_hash()))
    notes.append(("对外展示", "%s；未开通账号 %d 个" % ("门面内容" if demo_mode_on() else "真实内容",
                  count_untrusted_users()), demo_mode_on() is False))
    notes.append(("审计保留期", "%d 天（自动过期）" % audit_retention_days(), False))
    notes.append(("自动注销", "空闲 %s / 单次登录 %s" % (human_window(session_idle_seconds()),
                  human_window(session_max_age_seconds())), False))
    notes.append(("存 IP 方式", {"full": "完整", "masked": "只留网段", "none": "不存"}.get(
        _audit_ip_mode(), _audit_ip_mode()), False))
    notes.append(("找回密码", "已配置 SMTP" if app.config["SMTP_HOST"] else "未配 SMTP（只能管理员手动重置）",
                  not app.config["SMTP_HOST"]))

    # —— 错误页与模板：上传被截断是这里最容易中招的一种
    for name in ("400", "403", "404", "429", "500"):
        if not os.path.exists(os.path.join(basedir, "templates", "errors", name + ".html")):
            problems.append("缺少模板 templates/errors/%s.html" % name)
    bad_tpl = compile_templates()
    problems.extend(bad_tpl)
    notes.append(("模板", "全部可编译" if not bad_tpl else "%d 个编译失败" % len(bad_tpl), bool(bad_tpl)))

    # —— 库与磁盘：免费套餐的 500MB 是硬墙，撑爆是“悄悄发生”的
    path = _db_path()
    size = os.path.getsize(path) if path and os.path.exists(path) else 0
    over = size > DISK_WARN_BYTES
    notes.append(("数据库", "%.1f MB%s" % (size / 1048576.0, "（接近配额）" if over else ""), over))
    if over:
        problems.append("数据库已 %.1f MB，接近免费套餐 500MB 配额：先把审计留短几天"
                        "（AUDIT_RETENTION_DAYS），并用命令行备份而不是在线下载" % (size / 1048576.0))
    free = _disk_free(path)
    if free is not None:
        notes.append(("所在磁盘剩余", "%.0f MB" % (free / 1048576.0), free < DISK_WARN_BYTES))
    if path and not os.path.exists(path):
        problems.append("数据库文件不在预期位置：%s（检查 DATABASE_URI）" % path)
    backup_note, backup_problem = _backup_status()
    notes.append(("最近备份", backup_note, backup_note.startswith(("没有", "读不到"))))
    if backup_problem:
        problems.append(backup_problem)

    # —— 结构：缺表缺列的表现是“某个功能点了没反应”，不是报错
    if "site_flag" not in tables:
        problems.append("没有 site_flag 表：跑一次 flask --app app ensure-schema，"
                        "否则后台的“对外展示”开关保存不了（默认仍是门面内容）")
    if "user" in tables and "is_trusted" not in {r[1] for r in
            db.session.execute(text("PRAGMA table_info(user)"))}:
        problems.append("user 表缺 is_trusted 列：跑 flask --app app ensure-schema，"
                        "否则“开通/收回”没法用（现在所有人都会看到门面内容）")

    # —— 数据一致性：这些会慢慢腐蚀成“看着不对但说不出哪坏了”
    probes = [
        ("帖子", "SELECT count(*) FROM post WHERE user_id NOT IN (SELECT id FROM user)",
         {"post", "user"}),
        ("评论", "SELECT count(*) FROM comment WHERE post_id NOT IN (SELECT id FROM post)",
         {"comment", "post", "user"}),
        ("点赞", 'SELECT count(*) FROM "like" WHERE post_id NOT IN (SELECT id FROM post)',
         {"like", "post", "user"}),
        ("标签关联孤儿",
         "SELECT count(*) FROM post_tag WHERE post_id NOT IN (SELECT id FROM post) "
         "OR tag_id NOT IN (SELECT id FROM tag)",
         {"post_tag", "post", "tag"}),
        ("计数列漂移",
         "SELECT count(*) FROM post WHERE comments_count <> "
         "(SELECT count(*) FROM comment WHERE comment.post_id = post.id) "
         'OR likes_count <> (SELECT count(*) FROM "like" WHERE "like".post_id = post.id)',
         {"post", "comment", "like"}),
    ]
    for label, sql, needs in probes:
        if not needs <= tables:
            continue                          # 老库还没这张表，跳过而不是崩
        count = db.session.execute(text(sql)).scalar()
        if count:
            hint = "（跑 flask sync-counts 修复）" if label == "计数列漂移" else ""
            problems.append("%s：%s 条%s" % (label, count, hint))

    # —— 自动过期与自动注销有没有真的在跑
    if _audit_table_ready():
        left = audit_expired_count()
        if left:
            problems.append("审计过期未清理：%d 条已超过保留期 %d 天"
                            "（定时任务 prune-audit 没跑，且 6 小时内没人访问）"
                            % (left, audit_retention_days()))
        notes.append(("审计条目", "%s 条（最早 %s）" % (
            db.session.query(db.func.count(AuditLog.id)).scalar(),
            cn_time(db.session.query(db.func.min(AuditLog.at)).scalar(), "%m-%d") or "—"), False))
    activity = recent_activity()
    notes.extend(activity)
    if not app.config["SMTP_HOST"]:
        problems.append("提示：未配置 SMTP，找回密码只能走管理员手动重置")
    return problems, [n for n in notes if n]


def gate_enabled_now():
    """闸开关状态（延迟导入：gate.py 是被 app.py 引进来的，顶层反向 import 会成环）。"""
    try:
        import gate as _g
        return _g.gate_enabled()
    except Exception:
        return False


def gate_has_hash():
    """口令是不是以哈希配的（明文 GATE_PASSWORD 会留在 PA 变量列表里，可读性=可泄露）。"""
    return bool((os.environ.get("GATE_PASSWORD_HASH") or "").strip())


def count_untrusted_users():
    if "user" not in existing_tables() or not demo_mode_on():
        return 0
    try:
        return User.query.filter(User.is_trusted.isnot(True),
                                 User.is_admin.isnot(True)).count()
    except Exception:
        db.session.rollback()
        return 0


def compile_templates():
    """逐个编译模板：上传被截断（少一行 {% endblock %}）是最难查的一类事故 ——
    浏览器里只会看到一个和代码毫无关系的 500，这里提前一行说清楚是哪个文件。"""
    bad = []
    tpl_root = os.path.join(basedir, "templates")
    for dirpath, _dirs, files in os.walk(tpl_root):
        for fn in sorted(files):
            if not fn.endswith(".html"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, tpl_root).replace(os.sep, "/")
            try:
                with open(full, encoding="utf-8") as fh:
                    app.jinja_env.parse(fh.read(), name=rel, filename=full)
            except Exception as exc:
                bad.append("模板编译失败 %s：%s" % (rel, str(exc).splitlines()[0][:120]))
    return bad


def _disk_free(any_path):
    try:
        import shutil
        return shutil.disk_usage(os.path.dirname(os.path.abspath(any_path or basedir))).free
    except Exception:
        return None


def _backup_status():
    """最近一次命令行备份是什么时候、多大、留了几份。在线下载的那份不入库，不算备份。"""
    d = os.path.join(basedir, "backups")
    try:
        names = sorted(f for f in os.listdir(d) if f.startswith("forum-") and f.endswith(".db"))
    except OSError:
        return ("没有备份目录", "还没有任何备份：在定时任务里加一条 flask --app app backup"
                "（磁盘写满前它也是唯一能还原整站的东西）")
    if not names:
        return ("没有", "还没有任何备份：定时任务里加一条 flask --app app backup")
    newest = os.path.join(d, names[-1])
    try:
        age_h = (time.time() - os.path.getmtime(newest)) / 3600.0
        size = os.path.getsize(newest) / 1048576.0
    except OSError:
        return ("读不到", "备份文件读不到时间/体积：%s" % newest)
    when = "%d 天前" % int(age_h // 24) if age_h >= 24 else "%.1f 小时前" % age_h
    note = "%s一份（%.1f MB，共 %d 份）" % (when, size, len(names))
    problem = ""
    if age_h > 72:
        problem = ("最近的备份是 %.0f 小时前：定时任务加一条 flask --app app backup" % age_h)
    return note, problem


def recent_activity():
    """最近 24 小时发生了什么 —— 登录失败与前厅错口令的次数是“有人在试”的唯一信号。"""
    out = []
    if not _audit_table_ready():
        return out
    since = utcnow() - timedelta(hours=24)
    try:
        by = dict(db.session.query(AuditLog.action, db.func.count())
                  .filter(AuditLog.at >= since).group_by(AuditLog.action).all())
        out.append(("近 24 小时", "登录失败 %d · 自动注销 %d · 改动 %d" % (
            by.get("login", 0), by.get("logout", 0),
            (by.get("create", 0) + by.get("update", 0) + by.get("delete", 0))), by.get("login", 0) >= 10))
        if "gate_attempt" in existing_tables():
            bad = db.session.execute(text(
                "SELECT count(*) FROM gate_attempt WHERE ok = 0 AND at >= :s"),
                {"s": since}).scalar() or 0
            out.append(("前厅错口令", "%d 次（近 24 小时）" % bad, bad >= 15))
    except Exception:
        db.session.rollback()
    return out


@app.cli.command("doctor")
def doctor_command():
    """数据体检 + 部署自检，全绿再上线。检查项与后台“运行状态”页是同一份
    （health_snapshot），这样命令行说“没问题”而页面上标红，是不会发生的事。"""
    with app.app_context():
        problems, notes = health_snapshot()
    print("自检结果：")
    for lbl, val, warn in notes:
        print("  %-12s %s%s" % (lbl, val, "   ← 注意" if warn else ""))
    for prob in problems:
        print("  - " + prob)
    if not problems:
        print("  全部通过")


# ---------------------------------------------------------------- 后台：运行状态面板
@app.route("/admin/health")
@login_required
@admin_required
def admin_health():
    """后台“运行状态”：和 `flask --app app doctor` 同一份检查，只是它有按钮。
    每次进页面现算（十几条查询 + 编译 32 个模板，几十毫秒量级）—— 面板上写
    “上次 reload 后”这种缓存值最容易骗人。"""
    problems, notes = health_snapshot()
    # 面板上真正会被点走的只有三处：这批账号、审计页、备份页
    now = utcnow()
    pending = []
    for u in (User.query.filter(User.is_trusted.isnot(True), User.is_admin.isnot(True))
              .order_by(User.created_at).limit(100).all()):
        waited = (now - (u.created_at or now)).days if u.created_at else 0
        pending.append({"username": u.username, "email": u.email, "waited": waited,
                        "at": cn_time(u.created_at, "%m-%d %H:%M")})
    return render_template("admin_health.html", title="运行状态", problems=problems,
                           notes=notes, pending=pending, now_bj=cn_time(now, "%Y-%m-%d %H:%M"),
                           now_utc=now.strftime("%Y-%m-%d %H:%M UTC"))




if __name__ == "__main__":
    # 本地调试与手工运维入口。线上由 WSGI 导入 app，这段不会执行。
    #
    # 真实踩过的坑：在 PA 控制台里敲 `python app.py ensure-schema`，
    # 这段代码不解析参数，直接去起开发服务器 → 打出 "Port 5000 is in use"，
    # 而 CLI 从未执行、库结构没动，看起来就像“跑了但没效果”。
    # 现在把子命令转发给 Flask CLI，两种写法都能用：
    #     flask --app app ensure-schema     （推荐）
    #     python app.py ensure-schema       （等价）
    _args = sys.argv[1:]
    if _args and _args[0] in {c.name for c in app.cli.commands.values()}:
        print("# 转发到 Flask CLI：python app.py %s" % " ".join(_args))
        # 必须把“现在这个 app”交给 ScriptInfo：不传的话 Flask 会按模块名重新 import，
        # 得到第二份 app/db 实例，命令跑在上面就会报
        # “The current Flask app is not registered with this 'SQLAlchemy' instance”。
        from flask.cli import ScriptInfo
        # Flask 3.1 的 ScriptInfo 没有 app= 形参；用 create_app 返回当前实例，
        # 避免 Flask 按模块名重新 import 出第二份 app/db。
        app.cli.main(args=_args, prog_name="python app.py",
                     obj=ScriptInfo(create_app=lambda: app))
        sys.exit(0)
    if _args:
        print("! 不认识参数 %r。要跑 init-db / ensure-schema / backup 这类命令，用："
              % _args[0])
        print("    flask --app app %s" % _args[0])
        sys.exit(2)
    with app.app_context():
        db.create_all()
        ensure_schema()
        _bootstrap_admin(os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD"))
    print("# 本地调试服务器（线上用不到这段）。要跑维护命令：flask --app app <命令>")
    app.run(debug=False)
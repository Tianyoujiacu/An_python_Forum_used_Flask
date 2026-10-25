"""未被信任的来访者（未登录的人 + 管理员还没开通的账号）看到的门面内容。

为什么要这一层：链接会被收藏、被转发，而 noindex/robots.txt 只管搜索引擎，管不住
“任何人打开链接都能读到本班内容”。所以内容页对**没开通的访问者**呈现本文件里的
一套帖子 —— 页面上不再自称“示例/演示”（那是你要的：门面要像个正常站点），
账号是否开通由管理员在“用户管理”里逐个设置，新注册的账号默认未开通。
    未登录                    → 本文件的内容
    已登录但管理员没开通       → 本文件的内容（界面与正式成员完全一样，连发帖按钮都在）
    管理员开通的账号 / 管理员  → 真实站点
    站点级开关关掉（后台）     → 上面全部失效，回到“凭前厅口令即可浏览真实内容”的老行为

规则：这里的内容必须永远与班级无关。
    ① 一行都不许从数据库读 —— 拼进真实 post/user，这一层就白做了；
    ② 全是写死的字符串，改门面就是改这个文件；帖子内容刻意选“无人身信息”的通用技术问题；
    ③ 别在这里放任何指向真实数据的链接或 id（下面的 id 用 9001+，与真实帖子不撞号段）。
"""

FLAG_KEY = "demo_mode"                    # site_flag 表里的键（app.py 的 SiteFlag）
VALUE_ON, VALUE_OFF = "1", "0"
SAFE_ID_MIN = 9000                        # 门面内容占用的 id 段，真实帖子不会长到这里

# 门面里出现的“成员”（都是网名样式的假名字，不含任何真实班级成员信息）
USERS = {
    "朱智祺": {"initial": "朱", "since": "2026-09-01", "posts": 12, "answers": 34},
    "王泽嘉": {"initial": "王", "since": "2026-09-03", "posts": 7, "answers": 21},
    "admin":   {"initial": "A", "since": "2026-09-05", "posts": 3, "answers": 40},
    "jason":   {"initial": "J", "since": "2025-09-01", "posts": 1, "answers": 88},
}

ANNOUNCEMENT = {"title": "test",
                "body": "test",
                "author": "admin", "at": "2026-10-12 09:20"}

# 门面帖子
POSTS = [
    {
        "id": 9001, "title": "pandas 分组统计之后，怎么把没有数据的周也显示成 0？",
        "author": "朱智祺", "at": "2026-10-14 20:15", "lang": "python",
        "tags": ["python", "pandas"], "likes": 4, "solved": True,
        "body_html": (
            "<p>我用 <code>groupby</code> 分组计数，结果没有数据的那几周直接从输出里消失了，"
            "但表格希望它们显示成 0。是哪里的问题？</p>"
            "<pre><code>df.groupby('week').size()</code></pre>"),
        "answers": [
            {"author": "admin", "at": "2026-10-14 20:41", "likes": 9, "accepted": True,
             "body_html": ("<p><code>size()</code> 只会返回出现过的组。要把空组补回来，"
                           "先准备一个完整索引，再 <code>reindex</code>：</p>"
                           "<pre><code>idx = pd.RangeIndex(1, 9)\n"
                           "df.groupby('week').size().reindex(idx, fill_value=0)</code></pre>")},
            {"author": "jason", "at": "2026-10-14 21:02", "likes": 2, "accepted": False,
             "body_html": "<p>顺便一句：周次如果是字符串，排序会按字典序乱掉（1 和 10 挨着），"
                          "转成 <code>int</code> 再排。</p>"},
        ],
    },
    {
        "id": 9002, "title": "这里的代码块要用什么符号包起来？",
        "author": "朱智祺", "at": "2026-10-13 16:40", "lang": "",
        "tags": ["求助"], "likes": 2, "solved": False,
        "body_html": "<p>第一次用，不太清楚格式。行内代码和整段代码分别是几个反引号？"
                     "@admin 知道的话说一下。</p>",
        "answers": [
            {"author": "admin", "at": "2026-10-13 17:05", "likes": 6, "accepted": False,
             "body_html": "<p>行内用单个反引号，整段用三个反引号，并在后面写语言名（比如 "
                          "<code>python</code>）就会自动上色。写 <code>@用户名</code> "
                          "对方会收到站内通知。</p>"},
        ],
    },
    {
        "id": 9004, "title": "建议：班委投票能不能加一个“只数人不记名”的开关",
        "author": "admin", "at": "2026-10-09 12:21", "lang": "",
        "tags": ["建议"], "likes": 7, "solved": True,
        "body_html": "<p>选活动方案的时候，实名投票大家就不太敢选真实想法了。</p>",
        "answers": [
            {"author": "朱智祺", "at": "2026-10-09 13:00", "likes": 15, "accepted": True,
             "body_html": "<p>可以做成投票的一个选项：开启后后台只统计票数，不保留“谁投了哪一项”。</p>"},
        ],
    },
]
_DEMO_KINDS = {"home": "demo_home.html", "post": "demo_post.html", "votes": "demo_votes.html",
               "profile": "demo_profile.html", "list": "demo_list.html",
               "announce": "demo_announce.html"}

VOTES={}
def post_by_id(pid):
    for p in POSTS:
        if p["id"] == pid:
            return p
    return None


def pick(path):
    """把访客真正想去的 URL 映射到一张演示页。

    只做“看起来能走通”的事：点帖子进详情、点标签看列表、@ 人看主页 ——
    其余一律回首页。全部返回的都是这里写死的假数据，不查库。"""
    parts = [x for x in (path or "").split("?")[0].split("/") if x]
    if not parts:
        return "home", {}
    head = parts[0].lower()
    if head == "post" and len(parts) > 1:
        try:
            p = post_by_id(int(parts[1]))
        except ValueError:
            p = None
        if p is not None:
            return "post", {"post": p}
        return "post", {"post": POSTS[0]}          # 不认识的 id 也给一条正常帖子，别露出 404 的差异
    if head == "tag" and len(parts) > 1:
        return "list", {"heading": "标签 · %s" % parts[1], "posts": POSTS[:2]}
    if head == "search":
        return "list", {"heading": "搜索结果", "posts": POSTS[:2], "search": True}
    if head == "unanswered":
        return "list", {"heading": "待解答", "posts": [POSTS[2]]}
    if head == "lang" and len(parts) > 1:
        return "list", {"heading": "语言 · %s" % parts[1], "posts": POSTS[:1]}
    if head == "votes":
        return "votes", {"votes": VOTES}
    if head == "u" and len(parts) > 1:
        name = parts[1]
        return "profile", {"person": USERS.get(name), "handle": name}
    if head == "notifications":
        return "list", {"heading": "通知", "posts": [], "empty_text": "还没有新的通知。"}
    if head.startswith("announce"):
        # 公告页要长得跟公告页一样，别拿帖子列表糊弄过去
        return "announce", {"anns": [dict(ANNOUNCEMENT, id=7001,
                                          body_html="<p>%s</p>" % ANNOUNCEMENT["body"])]}
    return "home", {}


def render(path):
    """返回 (模板, 上下文)。水印与标题在这一层统一给，模板里就不用各自记得加。"""
    kind, ctx = pick(path)
    return _DEMO_KINDS[kind], ctx
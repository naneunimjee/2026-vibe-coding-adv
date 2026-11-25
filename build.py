"""data/issues/*.json 으로 정적 사이트를 site/ 에 만든다.

사용법: python build.py [출력 폴더]
환경 변수 SITE_URL: RSS에 들어갈 사이트 주소 (예: https://it-newsletter.pages.dev)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from collections import Counter
from datetime import date, datetime
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

ROOT = Path(__file__).parent
WEEKDAYS = "월화수목금토일"
ISSUE_PAGE_LIMIT = 3  # IT 이슈 페이지에 보여 줄 최근 호 수
RANK_LIMIT = 5


def load_issues(data_dir: Path) -> list[dict]:
    issues = [json.loads(p.read_text(encoding="utf-8")) for p in data_dir.glob("*.json")]
    if not issues:
        sys.exit(f"{data_dir} 에 호(JSON)가 하나도 없어요.")
    issues.sort(key=lambda i: i["number"], reverse=True)
    slugs = Counter(i["study"]["slug"] for i in issues)
    dupes = [s for s, n in slugs.items() if n > 1]
    if dupes:
        sys.exit(f"오늘의 공부 slug가 겹쳐요: {', '.join(dupes)}")
    return issues


def tokens_css(tokens: dict) -> str:
    """design/tokens.json → CSS 변수. 다크 값은 prefers-color-scheme: dark 에서 덮어쓴다."""

    def value(v: str) -> str:
        return f"var(--{v[1:-1]})" if v.startswith("{") and v.endswith("}") else v

    light, dark = ["color-scheme: light dark;"], ["color-scheme: dark;"]
    for t in tokens["color"]["tokens"]:
        v = t["value"]
        if isinstance(v, str):
            light.append(f"--{t['name']}: {value(v)};")
        else:
            light.append(f"--{t['name']}: {value(v['light'])};")
            if "dark" in v:
                dark.append(f"--{t['name']}: {value(v['dark'])};")
    for family in ("spacing", "radius", "shadow", "opacity"):
        for t in tokens.get(family, {}).get("tokens", []):
            light.append(f"--{t['name']}: {t['value']};")
    for key, stack in tokens["type"]["families"].items():
        light.append(f"--font-{key}: {stack};")

    body = "\n  ".join(light)
    dark_body = "\n    ".join(dark)
    return (
        "/* design/tokens.json 에서 build.py가 생성. 직접 고치지 마세요. */\n"
        f":root {{\n  {body}\n}}\n"
        f"@media (prefers-color-scheme: dark) {{\n  :root {{\n    {dark_body}\n  }}\n}}\n"
    )


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    def date_ko(s: str) -> str:
        d = date.fromisoformat(s)
        return f"{d.month}월 {d.day}일 ({WEEKDAYS[d.weekday()]})"

    def highlight(text: str, word: str) -> Markup:
        t = escape(text)
        if not word or word not in text:
            return t
        w = escape(word)
        return t.replace(w, Markup(f"<em>{w}</em>"), 1)

    env.filters["date_ko"] = date_ko
    env.filters["date_dot"] = lambda s: s.replace("-", ".")
    env.filters["time_hm"] = lambda s: datetime.fromisoformat(s).strftime("%H:%M")
    env.filters["highlight"] = highlight
    return env


def write(out: Path, rel: str, text: str) -> None:
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rss(issues: list[dict], site_url: str) -> str:
    items = []
    for i in issues[:20]:
        link = f"{site_url}/issue/{i['number']}/"
        pub = format_datetime(datetime.fromisoformat(i["date"] + "T08:00:00+09:00"))
        title = "제{}호 · {}".format(i["number"], i["headline"])
        items.append(
            "<item>"
            f"<title>{xml_escape(title)}</title>"
            f"<link>{xml_escape(link)}</link><guid>{xml_escape(link)}</guid>"
            f"<pubDate>{pub}</pubDate>"
            f"<description>{xml_escape(i['summary'])}</description>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
        f"<title>IT 뉴스레터</title><link>{xml_escape(site_url)}/</link>"
        "<description>매일 아침 IT 트렌드, 이슈, 오늘의 공부 주제를 원문에 근거해 요약해요.</description>"
        "<language>ko</language>" + "".join(items) + "</channel></rss>\n"
    )


def build(out: Path, data_dir: Path = ROOT / "data" / "issues", site_url: str = "") -> None:
    issues = load_issues(data_dir)
    latest = issues[0]
    env = make_env()

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "static", out / "static")
    tokens = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
    write(out, "static/tokens.css", tokens_css(tokens))

    sources = sorted({item["source"] for i in issues for item in i["items"]})
    nav = [
        {"id": "home", "label": "홈", "url": "/"},
        {"id": "trends", "label": "IT 트렌드", "url": "/trends/"},
        {"id": "issues", "label": "IT 이슈", "url": "/issues/"},
        {"id": "study", "label": "오늘의 공부", "url": f"/study/{latest['study']['slug']}/"},
        {"id": "archive", "label": "지난 호", "url": "/archive/"},
        {"id": "about", "label": "소개", "url": "/about/"},
    ]

    def render(rel: str, template: str, active: str, **ctx) -> None:
        html = env.get_template(template).render(nav=nav, active=active, sources=sources, latest=latest, **ctx)
        write(out, rel, html)

    # 1. 홈 + 호별 페이지 (홈은 최신 호)
    for issue in issues:
        ranked = sorted(issue["items"], key=lambda x: x["score"], reverse=True)
        ctx = dict(issue=issue, top=ranked[0], rest=[x for x in issue["items"] if x is not ranked[0]], ranked=ranked[:RANK_LIMIT])
        render(f"issue/{issue['number']}/index.html", "home.html", "archive", is_latest=False, **ctx)
        if issue is latest:
            render("index.html", "home.html", "home", is_latest=True, **ctx)

    # 2. IT 트렌드 (최신 호)
    trends = [x for x in latest["items"] if x["section"] == "trend"]
    topics = Counter(x["topic"] for x in trends).most_common()
    render("trends/index.html", "trends.html", "trends", issue=latest, items=trends, topics=topics)

    # 3. IT 이슈 (최근 몇 개 호, 날짜별)
    groups = []
    for issue in issues[:ISSUE_PAGE_LIMIT]:
        rows = [x for x in issue["items"] if x["section"] == "issue"]
        if rows:
            groups.append({"number": issue["number"], "date": issue["date"], "items": rows, "count": len(rows)})
    render("issues/index.html", "issues.html", "issues", groups=groups)

    # 4. 오늘의 공부 (호마다 한 페이지, 이전 = 더 오래된 호)
    for idx, issue in enumerate(issues):
        prev = issues[idx + 1]["study"] if idx + 1 < len(issues) else None
        nxt = issues[idx - 1]["study"] if idx > 0 else None
        render(f"study/{issue['study']['slug']}/index.html", "study.html", "study", issue=issue, study=issue["study"], prev=prev, next=nxt)

    # 5. 지난 호
    render("archive/index.html", "archive.html", "archive", issues=issues)

    # 6. 소개
    render("about/index.html", "about.html", "about")

    write(out, "feed.xml", rss(issues, site_url.rstrip("/")))


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    build(target, site_url=os.environ.get("SITE_URL") or "http://localhost:8000")
    print(f"사이트를 만들었어요: {target}")

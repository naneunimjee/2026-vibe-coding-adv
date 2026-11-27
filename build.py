"""data/issues/*.json 으로 정적 사이트를 site/ 에 만든다.

사용법: python build.py [--production] [출력 폴더]
환경 변수 SITE_URL: RSS에 들어갈 사이트 주소 (예: https://it-newsletter.pages.dev).
--production 또는 CI 환경에서는 https 주소가 꼭 있어야 한다 (FR-015-AC2).
환경 변수 GA_ID: Google Analytics 4 측정 ID (예: G-XXXXXXXXXX). 없으면 분석 태그를 넣지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from collections import Counter
from datetime import date, datetime
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

from newsletter import issue_store

ROOT = Path(__file__).parent
WEEKDAYS = "월화수목금토일"
ISSUE_PAGE_LIMIT = 3  # IT 이슈 페이지에 보여 줄 최근 호 수
RANK_LIMIT = 5
REPO_ISSUES = "https://github.com/naneunimjee/2026-vibe-coding-adv/issues"  # 삭제 요청 (BP-CONTENT-005)


def load_issues(data_dir: Path) -> list[dict]:
    """모든 호를 issue_store.validate로 검사한다. 하나라도 틀리면 빌드 실패 (NFR-012). 최신 호가 앞."""
    issues = issue_store.load_all(data_dir)
    if not issues:
        sys.exit(f"{data_dir} 에 호(JSON)가 하나도 없어요.")
    errors = []
    for n, issue in enumerate(issues):
        errors += issue_store.validate(issue, issues[:n])
        if issue.get("date") and not (data_dir / f"{issue['date']}.json").is_file():
            errors.append(f"{issue['date']}: file name must be <date>.json")
    if errors:
        sys.exit("호 데이터 검증 실패:\n" + "\n".join(errors))
    issues.sort(key=lambda i: i["number"], reverse=True)
    return issues


def check_out_dir(out: Path) -> None:
    """출력 폴더가 저장소 루트이거나 루트를 품으면 거부. 지우는 건 이전 빌드 결과일 때만."""
    out, root = out.resolve(), ROOT.resolve()
    if out == root or out in root.parents:
        sys.exit(f"출력 폴더로 쓸 수 없어요: {out}")
    if out.exists() and any(out.iterdir()) and not (out / "static" / "tokens.css").is_file():
        sys.exit(f"이전 빌드 결과가 아닌 폴더는 지우지 않아요: {out}")


def site_url_from_env(production: bool) -> str:
    url = os.environ.get("SITE_URL", "").strip().rstrip("/")
    if production or os.environ.get("CI"):
        if not url.startswith("https://"):
            sys.exit("CONFIG_MISSING: SITE_URL (https 주소가 필요해요)")
        return url
    return url or "http://localhost:8000"


def ga_id_from_env() -> str:
    ga_id = os.environ.get("GA_ID", "").strip()
    if ga_id and not re.fullmatch(r"G-[A-Z0-9]+", ga_id):
        sys.exit("CONFIG_INVALID: GA_ID (G-XXXXXXXXXX 형식이어야 해요)")
    return ga_id


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
    def time_ko(s: str, issue_date: str) -> str:
        """BP-TEXT-004: 호 날짜와 같으면 HH:mm, 다르면 M월 D일 HH:mm (KST로 저장돼 있음)."""
        t = datetime.fromisoformat(s)
        if t.date().isoformat() == issue_date:
            return t.strftime("%H:%M")
        return f"{t.month}월 {t.day}일 {t:%H:%M}"

    env.filters["time_ko"] = time_ko
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


def build(out: Path, data_dir: Path = ROOT / "data" / "issues", site_url: str = "", ga_id: str = "") -> None:
    issues = load_issues(data_dir)
    latest = issues[0]
    env = make_env()
    # BP-ERROR-004: 공부가 없는 호도 있으므로 "현재 공부"는 공부가 있는 가장 최근 호
    studied = [i for i in issues if i["study"]]
    current_study = studied[0]["study"] if studied else None

    check_out_dir(out)
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
        {"id": "study", "label": "오늘의 공부", "url": f"/study/{current_study['slug']}/" if current_study else "/"},
        {"id": "archive", "label": "지난 호", "url": "/archive/"},
        {"id": "about", "label": "소개", "url": "/about/"},
    ]

    def render(rel: str, template: str, active: str, **ctx) -> None:
        html = env.get_template(template).render(nav=nav, active=active, sources=sources, latest=latest, repo_issues=REPO_ISSUES, ga_id=ga_id, **ctx)
        write(out, rel, html)

    # 1. 홈 + 호별 페이지 (홈은 최신 호)
    for issue in issues:
        # 첫 항목이 주요 소식 (BP-RANK-008). 많이 이야기된 소식은 반응 수가 있는 것만.
        ranked = sorted([x for x in issue["items"] if x["score"] > 0], key=lambda x: x["score"], reverse=True)
        ctx = dict(issue=issue, top=issue["items"][0], rest=issue["items"][1:], ranked=ranked[:RANK_LIMIT],
                   study=issue["study"] or current_study)
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

    # 4. 오늘의 공부 (공부가 있는 호마다 한 페이지, 이전 = 더 오래된 호)
    for idx, issue in enumerate(studied):
        prev = studied[idx + 1]["study"] if idx + 1 < len(studied) else None
        nxt = studied[idx - 1]["study"] if idx > 0 else None
        render(f"study/{issue['study']['slug']}/index.html", "study.html", "study", issue=issue, study=issue["study"], prev=prev, next=nxt)

    # 5. 지난 호
    render("archive/index.html", "archive.html", "archive", issues=issues)

    # 6. 소개
    render("about/index.html", "about.html", "about")

    # 7. 404 (Cloudflare Pages가 없는 주소에 404 상태로 준다)
    render("404.html", "404.html", "")

    write(out, "feed.xml", rss(issues, site_url.rstrip("/")))


if __name__ == "__main__":
    args = sys.argv[1:]
    production = "--production" in args
    paths = [a for a in args if a != "--production"]
    target = Path(paths[0]) if paths else ROOT / "site"
    start = time.monotonic()
    build(target, site_url=site_url_from_env(production), ga_id=ga_id_from_env())
    pages = sum(1 for _ in target.rglob("*.html"))
    print(f"사이트를 만들었어요: {target} (페이지 {pages}개, {time.monotonic() - start:.1f}초)")

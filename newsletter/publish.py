"""발행 작업 진입점 (상세 설계 5.13).

사용법: python -m newsletter.publish [--dry-run]
종료 코드: 0 저장, 1 CONFIG_MISSING, 2 NO_ITEMS, 3 ISSUE_INVALID, 4 LLM_UNAVAILABLE
"""
from __future__ import annotations

import json
import sys
import time

from newsletter import RunLog, classify, clock, config, http, issue_store, llm, ranking, study, summarize
from newsletter.filtering import apply as filter_candidates
from newsletter.filtering import normalize_url
from newsletter.sources import arxiv, geeknews, github, hackernews

SOURCES = (("GeekNews", geeknews), ("Hacker News", hackernews), ("GitHub", github), ("arXiv", arxiv))


def main(argv: list[str] | None = None) -> int:
    dry_run = "--dry-run" in (argv if argv is not None else sys.argv[1:])
    try:
        cfg = config.load()
    except SystemExit as e:
        return int(e.code)
    llm.init(cfg.api_key)
    log = RunLog()
    http.stats.clear()
    start = time.monotonic()
    code, issue = run(log, cfg, dry_run)
    log.timings["total"] = time.monotonic() - start
    report(log, issue)
    return code


def run(log: RunLog, cfg: config.Config, dry_run: bool) -> tuple[int, dict | None]:
    """수집부터 저장까지. 종료 코드와 만든 호(못 만들었으면 None)를 돌려준다."""
    history = issue_store.load_all(cfg.data_dir)
    now = clock.now_kst()
    today = clock.issue_date(now)
    # 같은 날짜를 다시 돌리면 그 호를 덮어쓰므로, 수집 기간·최근 링크는 오늘보다 앞선 호로 정한다.
    before = [i for i in history if i["date"] < today.isoformat()]
    window = clock.collect_window(before[-1] if before else None, now)

    cands = []
    with log.timed("collect"):
        for name, module in SOURCES:
            source_start = time.monotonic()
            got = module.fetch(window, log)
            log.source_seconds[name] = time.monotonic() - source_start
            log.source_counts[name] = len(got)
            cands += got
    with log.timed("filter"):
        recent_urls = {normalize_url(it["url"]) for i in before[-config.RECENT_ISSUES_FOR_DEDUP :] for it in i["items"]}
        cands = filter_candidates(cands, recent_urls, log)

    try:
        with log.timed("classify"):
            classified = classify.run(cands, log)
            selected = ranking.select(classified)
        for c in classified:
            if c not in selected:
                log.add("OVER_LIMIT", c.cand.id, f"{c.section} importance {c.importance}")
        with log.timed("summarize"):
            items = summarize.run(selected, log)
    except llm.LlmUnavailable as e:
        log.add("LLM_UNAVAILABLE", str(e), "all calls failed")
        return 4, None
    if not items:
        log.add("NO_ITEMS", today.isoformat(), "nothing to publish")
        return 2, None

    cands_by_id = {c.id: c for c in cands}
    with log.timed("study"):
        today_study = study.run(items, cands_by_id, before, log)

    item_dicts = [it.to_json() for it in items]
    number, day = issue_store.next_identity(history, today)
    headline, highlight, summary, minutes = issue_store.build_headline(item_dicts, today_study)
    issue = {
        "schema_version": 1,
        "number": number,
        "date": day,
        "collected_at": now.isoformat(timespec="seconds"),
        "headline": headline,
        "highlight": highlight,
        "summary": summary,
        "read_minutes": minutes,
        "items": item_dicts,
        "study": today_study,
    }
    with log.timed("save"):
        errors = issue_store.validate(issue, history)
        if errors:
            for m in errors:
                log.add("ISSUE_INVALID", day, m)
            return 3, issue
        if dry_run:
            print(json.dumps(issue, ensure_ascii=False, indent=2))
        else:
            print(f"saved {issue_store.save(issue, cfg.data_dir)}")
    return 0, issue


def report(log: RunLog, issue: dict | None) -> None:
    """실행 요약. 원문 텍스트·API 키·LLM 응답 전문은 남기지 않는다."""
    for line in log.errors:
        print(line, file=sys.stderr)
    print("sources " + ", ".join(
        f"{k}={v} ({log.source_seconds[k]:.1f}s)" if k in log.source_seconds else f"{k}={v}"
        for k, v in log.source_counts.items()))
    print("excluded " + (", ".join(f"{k}={v}" for k, v in sorted(log.excluded.items())) or "none"))
    if issue:
        print(f"issue no.{issue['number']} {issue['date']} items={len(issue['items'])} study={'yes' if issue['study'] else 'no'}")
    for line in performance_lines(log):
        print(line)


def performance_lines(log: RunLog) -> list[str]:
    """단계별 시간, 호스트별 HTTP, LLM 호출 요약. 매일 실행을 비교하려고 한 줄씩 고정된 형식으로 낸다."""
    lines = ["timing " + " ".join(f"{k}={v:.1f}s" for k, v in log.timings.items())]
    for host, s in sorted(http.stats.items(), key=lambda kv: -(kv[1].seconds + kv[1].waited)):
        lines.append(f"http {host} requests={s.requests} retries={s.retries} net={s.seconds:.1f}s waited={s.waited:.1f}s")
    calls = log.llm_calls
    if calls:
        failed = sum(not c["ok"] for c in calls)
        total = {k: sum(c[k] for c in calls) for k in ("seconds", "in", "out", "thought")}
        slowest = ",".join(f"{c['target']}:{c['seconds']:.1f}s" for c in sorted(calls, key=lambda c: -c["seconds"])[:3])
        lines.append(f"llm calls={len(calls)} failed={failed} seconds={total['seconds']:.1f} "
                     f"tokens in={total['in']} out={total['out']} thought={total['thought']} slowest={slowest}")
    return lines


if __name__ == "__main__":
    sys.exit(main())

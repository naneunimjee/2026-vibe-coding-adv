"""발행 작업 진입점 (상세 설계 5.13).

사용법: python -m newsletter.publish [--dry-run]
종료 코드: 0 저장, 1 CONFIG_MISSING, 2 NO_ITEMS, 3 ISSUE_INVALID, 4 LLM_UNAVAILABLE
"""
from __future__ import annotations

import json
import sys

from newsletter import RunLog, classify, clock, config, issue_store, llm, ranking, study, summarize
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

    history = issue_store.load_all(cfg.data_dir)
    now = clock.now_kst()
    today = clock.issue_date(now)
    # 같은 날짜를 다시 돌리면 그 호를 덮어쓰므로, 수집 기간·최근 링크는 오늘보다 앞선 호로 정한다.
    before = [i for i in history if i["date"] < today.isoformat()]
    window = clock.collect_window(before[-1] if before else None, now)

    cands = []
    for name, module in SOURCES:
        got = module.fetch(window, log)
        log.source_counts[name] = len(got)
        cands += got
    recent_urls = {normalize_url(it["url"]) for i in before[-config.RECENT_ISSUES_FOR_DEDUP :] for it in i["items"]}
    cands = filter_candidates(cands, recent_urls, log)

    try:
        classified = classify.run(cands, log)
        selected = ranking.select(classified)
        for c in classified:
            if c not in selected:
                log.add("OVER_LIMIT", c.cand.id, f"{c.section} importance {c.importance}")
        items = summarize.run(selected, log)
    except llm.LlmUnavailable as e:
        log.add("LLM_UNAVAILABLE", str(e), "all calls failed")
        report(log, None)
        return 4
    if not items:
        log.add("NO_ITEMS", today.isoformat(), "nothing to publish")
        report(log, None)
        return 2

    cands_by_id = {c.id: c for c in cands}
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
    errors = issue_store.validate(issue, history)
    if errors:
        for m in errors:
            log.add("ISSUE_INVALID", day, m)
        report(log, issue)
        return 3
    if dry_run:
        print(json.dumps(issue, ensure_ascii=False, indent=2))
    else:
        print(f"saved {issue_store.save(issue, cfg.data_dir)}")
    report(log, issue)
    return 0


def report(log: RunLog, issue: dict | None) -> None:
    """실행 요약. 원문 텍스트·API 키·LLM 응답 전문은 남기지 않는다."""
    for line in log.errors:
        print(line, file=sys.stderr)
    print("sources " + ", ".join(f"{k}={v}" for k, v in log.source_counts.items()))
    print("excluded " + (", ".join(f"{k}={v}" for k, v in sorted(log.excluded.items())) or "none"))
    if issue:
        print(f"issue no.{issue['number']} {issue['date']} items={len(issue['items'])} study={'yes' if issue['study'] else 'no'}")


if __name__ == "__main__":
    sys.exit(main())

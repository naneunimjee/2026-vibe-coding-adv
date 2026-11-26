# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project status

A daily IT newsletter published as a **static website** (not email): IT trends, IT issues, and a "today's study topic". The site must have at least 5 pages; it has 6 (home, trends, issues, study, archive, about). Pipeline: collect (GeekNews, Hacker News, GitHub search API, arXiv) → dedupe/filter → LLM classify, rank, and summarize in Korean (summaries grounded only in fetched source text, always with the original link) → write `data/issues/<date>.json` → build the site → deploy. The LLM is Gemini `gemini-3.8-flash` via `google-genai` (SAD ADR-004, revised 2026-11-26). `data/issues/` starts empty; tests use `tests/sample_data.py`.

Stack (chosen with the user): Python + Jinja2 static generation, GitHub Actions for build/schedule, Cloudflare Pages for hosting. The user does not want Next.js/React.

### Commands

```
pip install -r requirements.txt
python build.py                        # writes site/ (SITE_URL env sets RSS links; required https with --production or CI)
GEMINI_API_KEY=... python -m newsletter.publish --dry-run   # real collect + LLM, prints the issue JSON without saving
python -m unittest discover -s tests   # offline: sources, filtering, LLM steps (mocked), issue validation, site build
python -m http.server -d site 8000     # preview at http://localhost:8000
```

### Layout

- `newsletter/` — publish job (`python -m newsletter.publish`): sources → filtering → classify → ranking → summarize → study → issue_store. Exit codes 0 ok, 1 config, 2 no items, 3 invalid issue, 4 LLM unavailable.
- `build.py` — loads and validates `data/issues/*.json` with `issue_store.validate` (newest `number` = home), renders `templates/`, generates `static/tokens.css` from `design/tokens.json`, writes `feed.xml`.
- `templates/` — `base.html` (header/footer/nav), one template per page, `_macros.html`, `_toast.html`.
- `static/site.css` — copy of the design system's `components/bundle.css` plus a few site-only rules at the end. Design system artifact: https://claude.ai/artifact/D1jHCFGWMkQTcqQgAj9KKv (Toss TDS-based, from `docs/DESIGN.md`).
- `.github/workflows/publish.yml` — daily 08:00 KST + manual: publish → commit `data/issues` → test → build → deploy. `deploy.yml` — on push/PR: test → build → deploy (main only). Deploy needs secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` and variable `SITE_URL`; publish needs secret `GEMINI_API_KEY`.
- `waterfall/` — project documents following the waterfall process. Phases 00–03 (planning → detailed design) are written and approved (G0–G3, recorded in `waterfall/08-검토/단계별검토-체크리스트.md`); phase 04 handover is drafted (`waterfall/04-구현/구현-테스트-인계서.md`, G4 pending); 05–07 are still blank templates. Code should follow `waterfall/03-상세설계/상세설계서.md` (module layout under `newsletter/`).

The user communicates in Korean; respond in Korean.

## Working guidelines

### 1. Think before coding
Don't assume. Don't hide confusion. Surface tradeoffs.
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop, name what's confusing, and ask.

### 2. Simplicity first
Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No unrequested "flexibility" or "configurability".
- No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it. Ask: "Would a senior engineer call this overcomplicated?"

### 3. Surgical changes
Touch only what you must. Clean up only your own mess.
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that *your* changes made unused; leave pre-existing dead code unless asked.

Every changed line should trace directly to the user's request.

### 4. Goal-driven execution
Define success criteria and loop until verified.
- "Add validation" → write tests for invalid inputs, then make them pass.
- "Fix the bug" → write a test that reproduces it, then make it pass.
- "Refactor X" → ensure tests pass before and after.

For multi-step tasks, state a brief plan with a verification check per step:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

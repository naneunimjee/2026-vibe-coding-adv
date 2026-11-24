# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project status

The repository currently contains only `README.md` — no code, build system, dependencies, or tests exist yet. When the first code is added, update this file with real build/run/test commands and architecture notes; do not assume a stack until it is chosen.

Planned project: a daily IT newsletter service (IT trends, issues, and a "today's study topic"), discussed as a pipeline of collect (RSS/APIs such as GeekNews, Hacker News, GitHub Trending, arXiv) → dedupe/filter → LLM classify, rank, and summarize in Korean (summaries grounded only in fetched source text, always with the original link) → render the email → send on a daily schedule. The intended first milestone is an MVP that delivers to the author only, before adding subscriber features. Treat this as direction, not a fixed spec — confirm stack choices with the user before implementing.

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

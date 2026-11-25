# 외부 연동·출력 인터페이스 설계서 (API 설계서)

> 이 시스템은 자체 API 서버가 없다. 이 문서는 (1) 발행 작업이 **호출하는** 외부 API의 규격과 (2) 사이트가 **내보내는** 정적 경로·RSS 규격을 정의한다. 템플릿의 인증·페이지네이션·Rate Limit 항목은 이에 맞게 바꿔 썼다.

| 항목 | 내용 |
|------|------|
| **프로젝트명** | IT 뉴스레터 (가칭) |
| **문서 버전** | v1.0 |
| **작성일** | 2026-11-25 |
| **작성자** | Claude (초안 작성) / 임지영 (프로젝트 담당) |
| **승인자** | 임지영 / 프로젝트 담당 |
| **문서 상태** | 승인됨 (G2, 2026-11-25) |

---

## 1. 연동 설계 원칙

### 1.1 외부 호출 공통 규칙

| 규칙 | 설명 | 근거 |
|------|------|------|
| 공식 수단만 | 공식 피드·API만 호출. 웹페이지를 긁지 않는다 | BP-SRC-002 |
| 한 곳에서 호출 | 모든 HTTP 요청은 `newsletter/http.py`, Claude 호출은 `newsletter/llm.py`를 거친다 | SAD 2.2 |
| 식별 가능한 User-Agent | `IT-Newsletter/<버전> (+<저장소 주소>)` | BP-SRC-008 |
| 순차 호출 | 출처 간·출처 안 모두 병렬 요청하지 않는다 | NFR-007 |
| 시간 제한 | 요청당 20초 | 30분 안에 끝내기 위함 |
| 재시도 | 네트워크 오류·5xx만 5초 뒤 1회. 403·404·429는 재시도하지 않는다 | BP-ERROR-005 |
| HTTPS | 모든 요청은 `https://` | NFR-006 |
| 받은 데이터 불신 | 응답의 텍스트·링크는 검증 전까지 신뢰하지 않는다 (링크 https 검사, HTML 미출력) | NFR-006 |

### 1.2 버전 관리

외부 API 버전은 요청에 명시할 수 있으면 고정한다 (GitHub `X-GitHub-Api-Version`). Hacker News API는 "하위 호환이 항상 보장되지 않는다"고 밝히므로, 모르는 필드는 무시하고 필요한 필드가 없으면 그 항목만 버린다.

### 1.3 이름 규칙

| 대상 | 규칙 | 예 |
|------|------|------|
| 사이트 경로 | 소문자, 끝에 `/` (디렉터리 + `index.html`) | `/trends/`, `/study/vector-database/` |
| 데이터 필드 | snake_case | `published_at`, `read_minutes` |
| 오류 코드 (실행 로그) | UPPER_SNAKE_CASE | `SOURCE_FETCH_FAILED` |

### 1.4 변경 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| v0.1 | 2026-11-25 | Claude | 초안 작성 |
| v1.0 | 2026-11-25 | Claude | G2 승인 |

---

## 2. 인증

### 2.1 인증 방식

| 대상 | 방식 | 값 보관 |
|------|------|---------|
| GeekNews 피드 | 없음 | - |
| Hacker News API | 없음 | - |
| GitHub 검색 API | `Authorization: Bearer <GITHUB_TOKEN>` | Actions 기본 토큰 (읽기 권한이면 충분) |
| arXiv API | 없음 | - |
| 위키백과 API | 없음 (User-Agent 필수) | - |
| Claude API | API 키 (SDK가 `ANTHROPIC_API_KEY` 환경 변수에서 읽음) | GitHub Secrets |
| Cloudflare Pages | API 토큰 + 계정 ID | GitHub Secrets |

### 2.2 사이트 접근

사이트와 RSS는 인증 없이 누구나 읽는다 (BP-CONTENT-001). 쓰기 경로는 없다.

---

## 3. 공통 규격

### 3.1 요청 헤더

| 헤더 | 값 | 대상 |
|------|------|------|
| `User-Agent` | `IT-Newsletter/<버전> (+https://github.com/naneunimjee/2026-vibe-coding-adv)` | 모든 HTTP 요청 |
| `Accept` | 출처별 (`application/json`, `application/atom+xml`, `application/vnd.github+json`) | 해당 요청 |
| `X-GitHub-Api-Version` | `2022-11-28` | GitHub |

### 3.2 내부 수집 결과 형식 (후보 소식)

출처 모듈은 모두 아래 형식의 목록을 돌려준다. 저장 형식이 아니라 실행 중 메모리 형식이다.

| 필드 | 타입 | 설명 |
|------|------|------|
| id | string | `<출처 코드>:<출처별 ID>` ([데이터 설계서](데이터베이스설계서.md) 4.2절) |
| source | string | 출처명 |
| title | string | 원문 제목 (원어) |
| url | string | 원문 링크 |
| published_at | datetime | 발행 시각 (시간대 포함) |
| score | int | 반응 수 (없으면 0) |
| source_text | string | 원문 텍스트 (요약 입력용, **저장 금지**) |
| excerpt | string | 분류용 발췌 (`source_text` 앞 1,000자) |

### 3.3 오류 기록 형식 (실행 로그)

`<오류 코드> <대상> <설명>` 한 줄. 예: `SOURCE_FETCH_FAILED arxiv timeout after retry`. 비밀 값과 원문 텍스트는 로그에 쓰지 않는다.

### 3.4 HTTP 상태 코드 처리 규칙

| 상태 | 처리 | 근거 |
|------|------|------|
| 200 | 정상 처리 | |
| 301·302 | 따라간다 (GeekNews 피드는 FeedBurner로 302) | |
| 403 | 차단으로 보고 재시도 없이 그 출처(또는 그 원문) 건너뜀 | BP-SRC-004, BP-ERROR-005 |
| 404 | 재시도 없이 건너뜀 | |
| 429 | 재시도 없이 그 출처 건너뜀 | BP-ERROR-005 |
| 5xx, 연결 오류, 시간 초과 | 5초 뒤 1회 재시도, 실패 시 건너뜀 | BP-ERROR-005 |

---

## 4. 연동 목록

### 4.1 호출하는 외부 엔드포인트 (Outbound)

| ID | 대상 | 메서드 | 주소 | 발행 1회당 요청 수 | 관련 FR |
|----|------|--------|------|------|---------|
| OUT-01 | GeekNews 피드 | GET | `https://news.hada.io/rss/news` | 1 | FR-001 |
| OUT-02 | HN 상위 글 목록 | GET | `https://hacker-news.firebaseio.com/v0/topstories.json` | 1 | FR-001 |
| OUT-03 | HN 글 상세 | GET | `https://hacker-news.firebaseio.com/v0/item/<id>.json` | 최대 30 | FR-001 |
| OUT-04 | HN 외부 원문 | GET | 글의 `url` | 수집 기간 안의 글만 (최대 30) | FR-001 |
| OUT-05 | GitHub 저장소 검색 | GET | `https://api.github.com/search/repositories` | 1 | FR-001 |
| OUT-06 | GitHub README | GET | `https://api.github.com/repos/<owner>/<repo>/readme` | 최대 10 | FR-001 |
| OUT-07 | arXiv 검색 | GET | `https://export.arxiv.org/api/query` | 1 | FR-001 |
| OUT-08 | 위키백과 검색 | GET | `https://<lang>.wikipedia.org/w/api.php` (`action=query&list=search`) | 후보당 1~2 | FR-006 |
| OUT-09 | 위키백과 요약 | GET | `https://<lang>.wikipedia.org/api/rest_v1/page/summary/<title>` | 후보당 1 | FR-006 |
| OUT-10 | Claude 메시지 | POST (SDK) | Anthropic Messages API | 분류 1~2, 요약 최대 12, 공부 2 | FR-003·005·006 |
| OUT-11 | Cloudflare Pages 배포 | wrangler | `pages deploy site` | 1 | FR-008 |

### 4.2 내보내는 인터페이스 (Outbound to 방문자)

| ID | 경로 | 형식 | 설명 | 관련 FR |
|----|------|------|------|---------|
| SITE-01 | `/` | HTML | 홈 (최신 호) | FR-009 |
| SITE-02 | `/trends/` | HTML | IT 트렌드 | FR-010 |
| SITE-03 | `/issues/` | HTML | IT 이슈 | FR-011 |
| SITE-04 | `/study/<slug>/` | HTML | 오늘의 공부 | FR-012 |
| SITE-05 | `/archive/` | HTML | 지난 호 | FR-013 |
| SITE-06 | `/issue/<number>/` | HTML | 호별 페이지 | FR-013 |
| SITE-07 | `/about/` | HTML | 소개 | FR-014 |
| SITE-08 | `/feed.xml` | RSS 2.0 | 최근 20개 호 | FR-015 |
| SITE-09 | `/404.html` | HTML | 없는 주소 (Pages가 404 상태로 제공) | FR-016 |
| SITE-10 | `/static/*.css` | CSS | 디자인 시스템, 토큰 | NFR-005 |

---

## 5. 연동 상세 명세

### 5.1 OUT-01 GeekNews 피드

| 항목 | 내용 |
|------|------|
| 형식 | Atom (`<feed>`, 항목 `<entry>` 약 20개, 최신순). 302로 FeedBurner 주소로 이동 |
| 이용 조건 | robots.txt가 허용. 약관은 과도한 부하의 자동 접근만 금지 → 발행 1회 1요청 |

| 수집 필드 | Atom 요소 | 변환 |
|-----------|-----------|------|
| id | `<id>` 또는 `<link href>`의 `topic?id=` 값 | `gn:<값>` |
| title | `<title>` | 그대로 |
| url | `<link href>` (GeekNews 토론 페이지) | https 확인 (BP-SRC-007) |
| published_at | `<published>`, 없으면 `<updated>` | 시간대 포함 파싱 |
| score | 없음 | 0 |
| source_text | `<content type="html">` | HTML 태그 제거한 텍스트 |

수집 기간 밖의 항목은 버린다.

### 5.2 OUT-02~04 Hacker News

| 항목 | 내용 |
|------|------|
| 형식 | JSON. `topstories`는 ID 배열(최대 500), `item`은 객체 |
| 이용 조건 | 공식 API, 인증 없음, 요청 제한 명시 없음 → 상위 30건만 조회 |

| 수집 필드 | API 필드 | 변환 |
|-----------|----------|------|
| id | `id` | `hn:<id>` |
| title | `title` | 그대로 |
| url | `url`. 없으면 `https://news.ycombinator.com/item?id=<id>` | https 아니면 제외 (BP-SUM-004) |
| published_at | `time` (Unix 초) | UTC → 시간대 포함 |
| score | `score` | 그대로 |
| source_text | `url`이 있으면 원문 페이지(OUT-04)의 본문 텍스트, 없으면 `text` | HTML 태그 제거 |

**처리:** `type == "story"`만. 수집 기간 밖이면 원문(OUT-04)을 요청하지 않는다. 원문이 403·로그인·HTML이 아님이면 `source_text` 없음 → FR-005에서 제외.

### 5.3 OUT-05~06 GitHub

| 항목 | 내용 |
|------|------|
| 형식 | JSON (`items` 배열) |
| 이용 조건 | 공식 검색 API, 인증 시 분당 30회 (발행 1회 1요청) |
| 요청 (제안) | `q=created:>=<수집 기간 시작일> stars:>=50`, `sort=stars`, `order=desc`, `per_page=10` |
| 확인 필요 | `created:` 한정자와 `stars:` 조건의 동작은 03 상세 설계에서 실제 호출로 확인한다 (조사 시 공식 페이지에서 한정자 목록을 확인하지 못함) |

| 수집 필드 | API 필드 | 변환 |
|-----------|----------|------|
| id | `full_name` | `gh:<owner/repo>` |
| title | `full_name` + `description` | 요약 단계에서 한국어 제목으로 |
| url | `html_url` | https |
| published_at | `created_at` | 시간대 포함 |
| score | `stargazers_count` | 그대로 |
| source_text | `description` + README(OUT-06) 앞 4,000자 | README는 Markdown 그대로 텍스트로 |

### 5.4 OUT-07 arXiv

| 항목 | 내용 |
|------|------|
| 형식 | Atom |
| 이용 조건 | 3초에 1회, 연결 1개. 메타데이터는 CC0. PDF를 보관하지 않고 초록 페이지로 링크. arXiv가 보증한다는 표현 금지 |
| 요청 (제안) | `search_query=cat:cs.AI OR cat:cs.CL OR cat:cs.LG OR cat:cs.SE`, `sortBy=submittedDate`, `sortOrder=descending`, `max_results=20` |
| 확인 필요 | 요청 주소·매개변수는 03에서 실제 호출로 확인한다 |

| 수집 필드 | Atom 요소 | 변환 |
|-----------|-----------|------|
| id | `<id>`의 논문 번호 (버전 제외) | `ax:<번호>` |
| title | `<title>` | 줄바꿈 정리 |
| url | `https://arxiv.org/abs/<번호>` | 초록 페이지 |
| published_at | `<published>` | 시간대 포함 |
| score | 없음 | 0 |
| source_text | `<title>` + `<summary>` (초록) | 그대로 |

### 5.5 OUT-08~09 위키백과

| 항목 | 내용 |
|------|------|
| 이용 조건 | 연락처가 담긴 User-Agent 필수(없으면 403), 요청은 직렬로. 본문은 CC BY-SA 4.0 |
| 순서 | ① 한국어 위키백과에서 검색(OUT-08)해 가장 맞는 문서 제목을 찾는다 → ② 요약(OUT-09)을 가져온다 → ③ 없으면 영어 위키백과로 ①② 반복 |
| 확인 필요 | 검색 API(`action=query&list=search`)의 응답 형식은 03에서 실제 호출로 확인한다. 요약 API는 조사 때 응답을 확인했다 |

| 사용 필드 (요약 API) | 용도 |
|-----------|------|
| `title` | `study.wikipedia.title` |
| `extract` | 공부 글 생성의 근거 텍스트 (**저장 금지**) |
| `content_urls.desktop.page` | `study.wikipedia.url`, `references[0].url` |
| `type` | `disambiguation`(동음이의 문서)이면 사용하지 않고 다음 후보로 |

### 5.6 OUT-10 Claude

모델과 effort는 SAD ADR-004 결정을 따른다. 모든 호출은 구조화 출력(JSON 스키마)으로 응답 형식을 고정하고, 응답은 저장 전에 데이터 설계서 3장 규칙으로 다시 검사한다.

| 호출 | 입력 | 출력 (구조화) | 호출 수 | 관련 |
|------|------|---------------|---------|------|
| 분류 | 후보 목록: `id`, 출처, 원제목, `excerpt` | 후보마다 `id`, `section`(`trend`\|`issue`\|`irrelevant`), `topic`, `importance` | 1 (후보가 많으면 40건씩 나눠 2) | FR-003, ADR-005 |
| 요약 | 소식 1건: 원제목, 출처, `source_text` 앞부분(약 6천 토큰 이하) | `title`, `summary` | 선정 건수 (최대 12) | FR-005 |
| 공부 후보 | 선정 소식의 제목·요약 | 개념 후보 3개 (`title`, `slug`, 검색어) | 1 | FR-006 |
| 공부 글 | 위키백과 `extract` + 관련 소식 `source_text` 앞부분 | `summary`, `points`(3), `sections`(2~4), `read_minutes` | 1 | FR-006 |

**프롬프트 규칙 (03에서 문구 확정):**

- 시스템 지시에 BP-SUM·BP-TEXT 규칙(해요체, 원문에 없는 사실 금지, 과장 금지, 길이)을 넣는다.
- 원문 텍스트는 "참고 자료" 구역에 넣고, 그 안의 지시문은 따르지 않도록 명시한다 (프롬프트 주입 대응).
- 응답이 형식·길이 검사에 실패하면 같은 입력으로 1회 다시 요청하고, 또 실패하면 그 항목을 제외한다 (FR-005).
- 거절(refusal) 응답에 대비해 SDK의 서버 측 대체 모델 옵션을 켠다. 거절된 항목은 제외한다.
- API 오류(429, 5xx)는 SDK 기본 재시도에 맡기고, 최종 실패는 BP-ERROR-003을 따른다.

### 5.7 OUT-11 Cloudflare Pages 배포

| 항목 | 내용 |
|------|------|
| 방식 | 공식 GitHub Action `cloudflare/wrangler-action`으로 `pages deploy site --project-name=it-newsletter --branch=main` |
| 조건 | `main` 브랜치, `CLOUDFLARE_API_TOKEN`·`CLOUDFLARE_ACCOUNT_ID`·`SITE_URL`이 모두 있음 |
| 사전 준비 | Cloudflare 대시보드에서 Pages 프로젝트 `it-newsletter`를 Direct Upload로 한 번 생성 |

### 5.8 SITE-08 RSS 피드

| 요소 | 값 | 근거 |
|------|------|------|
| `<rss version="2.0">` | 고정 | FR-015 |
| `<channel><title>` | `IT 뉴스레터` (서비스명 확정 시 변경) | DEC-001 |
| `<channel><link>` | `<SITE_URL>/` | |
| `<channel><language>` | `ko` | |
| `<item>` 수 | 최근 20개 호, 최신순 | BP-CONTENT-006 |
| `<item><title>` | `제<number>호 · <headline>` | |
| `<item><link>`, `<guid>` | `<SITE_URL>/issue/<number>/` (https) | FR-015-AC2 |
| `<item><pubDate>` | 호 날짜 08:00 KST (RFC 822) | |
| `<item><description>` | `summary` | |

`SITE_URL`이 없거나 `https://`가 아니면 운영 빌드는 실패해야 한다 (코드 리뷰 지적 반영, FR-015-AC2).

---

## 6. 오류 코드 테이블 (실행 로그)

### 6.1 수집 오류

| 코드 | 의미 | 처리 |
|------|------|------|
| `SOURCE_FETCH_FAILED` | 출처 요청 실패 (재시도 후) | 그 출처 건너뜀 |
| `SOURCE_BLOCKED` | 403·429 응답 | 그 출처 건너뜀, 재시도 없음 |
| `SOURCE_PARSE_FAILED` | 응답 형식이 예상과 다름 | 그 출처 건너뜀 |
| `ORIGINAL_UNAVAILABLE` | 원문 텍스트를 못 얻음 | 그 소식 제외 |

### 6.2 검증 오류

| 코드 | 의미 | 처리 |
|------|------|------|
| `LINK_NOT_HTTPS` | 링크가 https가 아님 | 그 소식 제외 |
| `LLM_INVALID_OUTPUT` | 형식·값·길이 검사 실패 (재요청 후) | 그 소식 제외 |
| `ISSUE_INVALID` | 호 파일 검증 실패 | 저장·배포 중단, 비정상 종료 |

### 6.3 업무 오류

| 코드 | 의미 | 처리 |
|------|------|------|
| `NO_ITEMS` | 선정 결과 0건 | 호 생성 안 함, 비정상 종료 (BP-ERROR-002) |
| `STUDY_SKIPPED` | 오늘의 공부 생성 실패 | 공부 없이 진행 (BP-ERROR-004) |

### 6.4 시스템 오류

| 코드 | 의미 | 처리 |
|------|------|------|
| `LLM_UNAVAILABLE` | Claude 호출 전체 실패 | 비정상 종료 (BP-ERROR-003) |
| `CONFIG_MISSING` | 필수 환경 변수 없음 (`ANTHROPIC_API_KEY`, 운영 `SITE_URL`) | 비정상 종료 |

---

## 7. 요청 한도 정책 (Rate Limiting)

### 7.1 전체 정책

발행 작업 1회의 외부 요청은 100건 안팎이다. 모든 요청은 순차로 보내고, 호스트별 최소 간격을 지킨다.

### 7.2 호스트별 제한

| 호스트 | 최소 간격 | 1회 실행 최대 요청 | 근거 |
|--------|-----------|-------------------|------|
| news.hada.io / feeds.feedburner.com | - | 1 | GeekNews 약관 제6조 |
| hacker-news.firebaseio.com | 0.2초 | 31 | 제한 명시 없음, 예의상 간격 |
| HN 외부 원문 (각 사이트) | 1초 | 사이트당 수 건 | BP-SRC-003 |
| api.github.com | 2초 | 11 | 검색 분당 30회 |
| export.arxiv.org | 3초 | 1 | arXiv 약관 |
| *.wikipedia.org | 1초 | 6 | 위키미디어 예의 (직렬) |
| Anthropic API | SDK 기본 | 약 16 | 계정 한도 |

### 7.3 한도 초과 응답

429를 받으면 그 출처는 그날 건너뛴다 (재시도 없음). Claude의 429는 SDK가 `retry-after`를 따라 재시도한다.

---

## 8. 연동 변경 관리

### 8.1 출처 형식 변경 대응

출처 응답 형식이 바뀌면 `SOURCE_PARSE_FAILED`가 연속으로 남는다. 같은 출처가 3일 연속 실패하면 운영자가 확인한다 (UC-008 AF-008-01).

### 8.2 깨지는 변경 (Breaking Change)

| 변경 | 대응 |
|------|------|
| 출처 API 주소·필드 변경 | 해당 `sources/` 모듈 수정, 이 문서 5장 갱신 |
| 출처 이용 조건 변경 | 정책 변경 절차로 BP-SRC 갱신, 필요하면 출처 제외 |
| 사이트 경로 변경 | 기존 경로를 유지하거나, 바꾸면 RSS `guid`가 바뀌므로 피하는 것이 원칙 |

### 8.3 깨지지 않는 변경

출처 응답에 새 필드가 생기는 것은 무시한다. 데이터 형식에 선택 필드를 추가하는 것은 `schema_version`을 올리지 않는다 ([데이터 설계서](데이터베이스설계서.md) 5.2절).

### 8.4 연동 변경 로그

| 날짜 | 대상 | 변경 | 사유 |
|------|------|------|------|
| 2026-11-25 | GitHub | Trending 페이지 → 공식 검색 API | GitHub 이용 정책 (SRS ISSUE-01) |

---

## 부록

### A. 확인 필요 항목 (03 상세 설계에서 실제 호출로 확인)

| 항목 | 내용 |
|------|------|
| CHK-01 | GitHub 검색의 `created:`·`stars:` 한정자 동작과 결과 품질 |
| CHK-02 | arXiv API 주소·매개변수·응답 형식 |
| CHK-03 | 위키백과 검색 API 응답 형식과 동음이의 문서 처리 |
| CHK-04 | HN 외부 원문 페이지에서 본문 텍스트를 뽑는 방법(표준 라이브러리 HTML 파서)의 품질 |
| CHK-05 | Claude 구조화 출력 스키마와 SDK 버전 |

### B. 참고 자료

- GeekNews 이용약관 https://news.hada.io/terms
- Hacker News API https://github.com/HackerNews/API
- GitHub 검색 API https://docs.github.com/en/rest/search/search
- arXiv API 이용 약관 https://info.arxiv.org/help/api/tou.html
- 위키미디어 User-Agent 정책 https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
- MediaWiki API 예절 https://www.mediawiki.org/wiki/API:Etiquette

### C. 참조 문서

- [시스템 아키텍처 설계서](시스템아키텍처설계서-SAD.md)
- [데이터 설계서](데이터베이스설계서.md)
- [요구사항 명세서 (SRS)](../01-요구사항분석/요구사항명세서-SRS.md) 5장

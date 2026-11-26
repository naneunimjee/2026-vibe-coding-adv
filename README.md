# IT 뉴스레터

매일 아침 IT 트렌드, IT 이슈, 오늘의 공부 주제를 원문에 근거해 요약해서 보여 주는 정적 웹사이트예요.

- **만드는 법:** 파이썬 + Jinja2로 HTML을 생성해요.
- **자동 실행:** GitHub Actions
- **호스팅:** Cloudflare Pages
- **디자인:** `docs/DESIGN.md`(토스 TDS 정리본)를 바탕으로 만든 디자인 시스템을 써요.

> 지금 `data/issues/`에 있는 3개 호는 **예시 데이터**예요. 링크는 모두 `example.com`이에요. 뉴스 수집·요약 스크립트는 다음 단계에서 붙여요.

## 페이지

| 경로 | 페이지 |
| --- | --- |
| `/` | 홈: 오늘 호 |
| `/trends/` | IT 트렌드: 주제 필터 |
| `/issues/` | IT 이슈: 최근 3개 호, 날짜별 |
| `/study/<slug>/` | 오늘의 공부: 호마다 한 페이지 |
| `/archive/` | 지난 호: 검색 |
| `/about/` | 소개, RSS 주소 복사 |

호마다 `/issue/<번호>/` 페이지도 생기고, `/feed.xml`(RSS)도 만들어져요.

## 로컬에서 실행

파이썬 3.10 이상이 필요해요.

```powershell
pip install -r requirements.txt
```

```powershell
python build.py
```

```powershell
python -m http.server -d site 8000
```

브라우저에서 http://localhost:8000 을 열어요. 테스트는 아래 명령으로 돌려요.

```powershell
python -m unittest discover -s tests -v
```

## 새 호 추가하기

`data/issues/<날짜>.json`을 하나 추가하면 돼요. 형식은 기존 파일을 참고해 주세요.

- `number`가 가장 큰 호가 홈에 나와요.
- 소식(`items`)마다 `section`이 있어요. 트렌드는 `trend`, 이슈는 `issue`로 적어요.
- `score`가 가장 높은 소식이 홈의 주요 소식이 돼요.
- 오늘의 공부 `study.slug`는 호마다 달라야 해요.

## 배포 설정 (한 번만)

1. **Cloudflare 프로젝트 만들기:** Cloudflare 대시보드 → Workers & Pages → Create → Pages → "Upload assets"를 선택해요. 이름은 `it-newsletter`로 만들어요.
2. **API 토큰 발급:** Cloudflare에서 **Cloudflare Pages: Edit** 권한이 있는 API 토큰을 만들어요. 계정 ID도 확인해 둬요.
3. **GitHub에 등록:** 저장소 Settings → Secrets and variables → Actions로 가요.
   - Secrets에 `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`를 넣어요.
   - Variables에 `SITE_URL`(예: `https://it-newsletter.pages.dev`)을 넣어요.
4. 이제 `main`에 푸시하면 Actions가 테스트 → 빌드 → 배포를 해요. 비밀 값을 넣기 전에는 배포 단계만 건너뛰어요.

수집·요약 스크립트가 생기면 `.github/workflows/deploy.yml`의 `schedule` 주석을 풀어요. 그러면 매일 한국 시간 오전 8시에 자동 실행돼요.

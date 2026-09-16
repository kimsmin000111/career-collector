# 기계공학 신입 채용 수집기

Python이 공식 채용페이지를 읽고 SQLite와 JSON을 갱신합니다. 매일 Codex, ChatGPT, GPT API 또는 다른 AI 모델을 호출하지 않습니다. 사이트의 개인 이력·자격·지원 메모는 이 저장소에 포함하지 않습니다.

## 현재 범위와 한계

- 실행 가능한 adapter: 현대모비스 공식 HTML, JOB-ALIO 공식 HTML, LG Careers 공식 공개 API, 설정형 HTML, 설정형 공공 JSON API.
- 초기 registry 75개 항목 중 현대모비스·JOB-ALIO·LG Careers 세 통합 출처를 활성화했습니다. 나머지는 수집 완료 기업이 아니라 정책·selector·규모·공식 주소 검토 후보입니다. JOB-ALIO와 LG Careers는 각각 여러 기관·계열사를 한 번에 확인합니다.
- LG Careers는 목록 제목만 저장하지 않고 신입·신입/경력·인턴 공고의 상세 직무를 분리합니다. 따라서 LG디스플레이의 기구·구조해석, LG전자, LG마그나, 로보스타 등의 기계 관련 세부 직무를 판정할 수 있습니다.
- 삼성 Careers는 공식 목록·상세 요청 방식을 확인했지만 2026-09-15 모집 종료 후 공개 목록이 0건이었고, robots.txt가 정상 정책 문서 대신 오류 응답을 반환해 자동 수집을 켜지 않았습니다. 포스코 공식 채용 사이트는 robots.txt에서 전체 자동 접근을 금지하므로 수집하지 않습니다. SK·한화·HD현대·두산 등은 확인된 공식 API나 허용된 HTML 구조를 추가해야 합니다.
- JOB-ALIO 최초/주간 실행은 최근 7일 등록분, 이후 일일 실행은 마지막 정상 확인 전날부터의 신규 등록분과 이미 저장된 접수중 공고를 확인합니다. 최초 실행 이전에 등록된 오래된 공고까지 전수 수집했다는 뜻은 아닙니다. 페이지 상한 도달은 부분 실패로 보고합니다.
- JOB-ALIO 공고는 여러 직렬·학력·전형이 섞여 있어 기본적으로 `확인 필요`로 보관합니다. GitHub 실행 서버에서 연결이 지연되거나 실패하면 기존 데이터를 보존하고 상태를 오류로 표시합니다. 다른 활성 출처가 정상 갱신되면 그 데이터는 계속 게시합니다. 첨부 PDF/HWP/ZIP을 해석해 직렬별 필수 자격을 분리하는 기능은 아직 없습니다. 따라서 신입 제목만으로 지원 가능을 보증하지 않습니다.
- `지원 가능`은 신입 모집 근거와 기계 관련성의 규칙 판정입니다. 개인별 어학 점수, 자격증, 병역, 입사일, 고졸/석사 전용 전형 등은 원문에서 최종 확인해야 합니다.
- `관련 없음`과 `지원 어려움`도 DB/JSON에 남고 사이트 활성 추천에서는 제외됩니다. 불명확한 공고는 후보로 남습니다.

## 1. 설치

Python 3.12 이상을 설치합니다. 이 폴더 자체가 GitHub 저장소 루트여야 합니다. `career-hub` 전체나 개인 증빙 파일을 업로드하지 마세요.

```sh
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py --init-only
```

## 2. 로컬 실행

```sh
python app.py
python app.py --source mobis
python app.py --source jobalio --max-pages 1
python app.py --source lgcareers
python app.py --mode weekly
python -m unittest discover -s tests -v
```

`--max-pages 1`은 빠른 구조 확인용이며 페이지가 더 있으면 정상 전체 수집으로 표시하지 않습니다. 오류가 있으면 종료코드 2와 출처별 로그를 남깁니다. 성공한 출처의 데이터는 보존합니다. 환경변수는 OS 또는 Actions Secrets로 지정하며 `.env.example`은 설명용입니다. `.env` 자동 로딩은 하지 않습니다.

## 3. GitHub Actions 설정

1. `kimsmin000111/career-collector` 저장소에 이 폴더의 소스만 올립니다. 공개 저장소에는 공개 채용정보와 수집 코드만 저장합니다.
2. `.github/workflows/collect.yml`이 **기본 브랜치 main**에 있어야 합니다.
3. Actions에서 `Collect mechanical graduate jobs` → `Run workflow`를 한 번 실행합니다.
4. 저장소 정책에서 Actions가 허용되어 있고 워크플로에 `contents: write` 권한이 있어야 `collector-data` 브랜치를 갱신할 수 있습니다. 조직 정책이 차단하면 관리자의 설정이 필요합니다.
5. 추가 공공 API 사용 시 Settings → Secrets and variables → Actions → Secrets에 `PUBLIC_JOBS_API_KEY`를 저장합니다. 현재 활성 출처에는 키가 필요 없습니다. 연락처를 User-Agent에 넣으려면 Variables의 `COLLECTOR_CONTACT`를 사용합니다.
6. 실패 알림은 GitHub Actions의 본인 알림 설정을 사용합니다. 이메일·카카오톡을 별도로 발송하지 않습니다.

## 4. 매일·매주 자동 실행과 비용

- 매일 09:00 KST(00:00 UTC): 일일 수집.
- 일요일 10:00 KST(01:00 UTC): 등록 공공 출처의 최근 7일 범위를 다시 확인하고 새 기관을 후보 파일에 저장.
- GitHub가 Ubuntu 실행 환경을 제공하므로 노트북·휴대폰이 꺼져 있어도 동작합니다.
- GitHub의 예약은 정확한 정시 실행을 보장하지 않으며 혼잡 시 지연될 수 있습니다. 공개 저장소 예약은 60일 비활동 등의 GitHub 정책으로 비활성화될 수 있어 Actions 화면을 확인하세요.
- Codex 크레딧과 GPT API 비용은 일상 실행에 사용하지 않습니다. GitHub Actions/저장 공간 이용 정책과 한도는 별개입니다. 유료 서비스 구매나 결제 설정은 하지 않습니다.
- 재배포는 하지 않습니다. Python → `collector-data` 브랜치의 DB/JSON → 기존 사이트가 최신 JSON 읽기 순서입니다.

## 5. 새로운 기업 추가

`config/companies.yaml`의 `sources`에 항목을 추가합니다. 기업명, `type`(large/mid/public_enterprise/public_institution/unknown/small), 산업, 공식 URL, method, API, JavaScript 여부, selectors, allowed_hosts, 정책 확인을 기록합니다. 중견급 매출/인원 근거가 불분명하면 unknown으로 두어 지원 가능 추천을 막습니다. 근거 없이 mid로 바꾸지 마세요.

`enabled: true`와 `terms_reviewed: true`는 구조와 정책을 실제 확인한 후에만 설정합니다. 마지막 성공 시각은 변경이 잦은 YAML 대신 SQLite `sources.success_at`에 기록하며 `health.json`에 실행 결과가 표시됩니다.

## 6. 공공기관 추가와 주간 발견

JOB-ALIO 통합 출처는 별도 기관 하드코딩 없이 여러 기관을 찾습니다. `institution_types`에 확인된 공기업 유형을 보완할 수 있습니다. 기관별 사이트를 더 정확하게 확인하려면 해당 URL과 adapter를 registry에 추가합니다. 나라일터·ALIO·기관 API를 사용하려면 각 공식 명세/정책과 인증키부터 확인합니다. 존재가 확인되지 않은 통합 API 주소를 임의로 만들지 않았습니다.

주간 `output/source-candidates.json`은 수집한 공식 공고에서 처음 발견한 기관의 후보 목록입니다. 전체 인터넷이나 검색엔진을 무제한 탐색하지 않습니다. 새 후보는 기관별 공식 URL·정책을 검토한 뒤 registry에 승격합니다.

## 7. CSS selector 수집기

`config/examples.yaml`의 generic 예시를 복사합니다. `item/link/title/next/empty`는 목록, `detail_selectors`는 상세 필드입니다. 실제 HTML에서 selector를 확인하세요. `single_role: true`는 공고 한 건이 한 직무의 요건만 담는 경우에만 설정합니다. 공고 0개와 selector 깨짐을 구별하기 위해 empty selector가 없고 item이 0개이면 실패합니다.

## 8. 공식 API 수집기

JSON REST 응답을 제공하는 허가된 API에 `public_api`를 사용합니다. `endpoint`, `items_path`, 필드 경로, 페이지/키 파라미터를 명세에 맞춰 설정합니다. `config/examples.yaml`의 주소는 실행 예시가 아닌 비활성 placeholder입니다. XML API는 명세에 맞는 별도 adapter가 필요합니다. 인증키를 포함한 API URL은 HTTP 캐시나 로그에 저장하지 않습니다.

## 9. 사이트 연결

사이트: https://seongmin-career-desk.kimsmin000111.chatgpt.site/

사이트의 `lib/collected-feed.ts`가 다음 URL을 서버에서 읽습니다.

`https://raw.githubusercontent.com/kimsmin000111/career-collector/collector-data/output/jobs.json`

`health.json`으로 마지막 실행과 부분 실패를 확인합니다. 다른 저장소를 사용할 경우 이 고정 주소 두 개를 한 번 변경해야 합니다. 사이트는 JSON 스키마/URL/중복 ID/응답 크기를 검증하고 D1에 마지막 정상 응답을 보관합니다. GitHub 장애 때 빈 목록으로 덮어쓰지 않습니다. 서버 캐시는 5분이며 페이지를 연 상태에서는 새로고침으로 반영합니다. 개인별 지원 메모와 체크리스트는 기존 D1 테이블에 그대로 남습니다. 같은 원문 공고의 기존 ID도 유지합니다.

결과는 기존 사이트의 `채용공고`에서 보고 기업유형·직무·마감·신입 지원 상태로 필터링합니다. `확인 필요` 후보와 `지원 제외`, `마감` 기록은 별도로 조회할 수 있습니다. `자동 수집 상태 → 수집 범위·오류 확인`은 미구현 출처도 표시합니다.

## 10. 실패한 출처 확인

```sh
python app.py --errors
python app.py --source jobalio
```

Actions 실행 Summary, `collection-report` artifact, `output/health.json`을 확인하세요. HTTP 403/429, robots 금지, CAPTCHA, JavaScript 전용, selector 변경은 성공으로 처리하지 않습니다. 해당 출처 오류가 다른 출처의 저장을 막지 않습니다. GitHub 실행 자체가 중지되면 사이트는 마지막 확인이 36시간을 넘었음을 표시합니다.

## 11. 수집 정책·보존·보안

각 호스트의 robots.txt를 확인하고, 실패 시 닫힌 상태로 중단합니다(404/410은 별도 robots 규칙 없음). 호스트당 기본 2초 간격, 30초 읽기 제한, 응답 5MB 제한, 등록된 HTTPS 호스트만 허용합니다. robots crawl-delay가 더 길면 따릅니다. CAPTCHA, 로그인, 차단 우회, 프록시 회전, 이메일 수집은 구현하지 않습니다. 사람인·잡코리아도 승인된 API 없이는 추가하지 않습니다.

공공데이터라도 제3자 저작권이 포함된 첨부물은 별도 정책을 확인해야 합니다. 첨부 파일·사진·이력서는 다운로드하거나 재배포하지 않습니다. 공고의 업무·요건은 원문 링크와 함께 표시하며 원문이 최종 기준입니다.

SQLite는 `collector-data` 브랜치에 보관하므로 Actions artifact 보존기간이 끝나도 채용 이력은 유지됩니다. HTTP 캐시만 Actions cache에 저장하며 유실 시 다시 다운로드합니다. 마감일 변경은 같은 공식 URL의 기록을 갱신하고, 마감 기록은 active=false로 유지합니다. 공식 URL이 서로 다른 신입/경력 공고는 같은 직무·기간이어도 합치지 않습니다. 목록에서 사라졌다는 이유로 마감 처리하지 않습니다. 공식 조기 마감 배지가 별도 추출되지 않는 adapter는 마감일 기준으로만 종료를 판정하므로 원문 확인이 필요합니다.

## 12. Codex가 매일 필요 없는 이유

워크플로는 `python app.py`만 실행합니다. 신입 판정과 기계 관련성·적합도 점수는 `core/filters.py`, `config/keywords.yaml`의 규칙입니다. AI SDK·API 키·모델 호출이 없습니다. Codex는 수집 소스 추가, 오류 수정, 사이트 기능 변경 때만 사용합니다. 이전 Codex 일일·주간 예약은 중복 실행 방지를 위해 중지합니다.

공식 참고: [GitHub 예약 실행](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [JOB-ALIO 정책](https://job.alio.go.kr/right.do), [현대모비스 robots](https://careers.mobis.com/robots.txt).

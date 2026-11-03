# SEA Pulse · 동남아 데일리 브리프 웹페이지

서울대학교 아시아연구소 동남아시아센터의 「동남아 데일리 브리프」를 웹페이지로 게시하고, 구글 드라이브에 새 브리프가 올라오면 자동으로 갱신하는 저장소입니다.

- 게시 주소: https://snuac-seacenter.github.io/sea-pulse/
- 홈페이지 삽입 주소: https://snuac-seacenter.github.io/sea-pulse/?embed=1

## 동작 방식

```
교수님 클로드 → 구글 드라이브 '동남아브리프' 폴더에 YYYY-MM-DD.json 저장
      ↓ (매시 23분 자동 실행: Actions 탭 '브리프 갱신')
형식 검사 · 내부 메모 표현 검사 → 통과한 파일만 briefs/ 에 공개본으로 저장(비공개 필드 제거)
      ↓
페이지를 다시 만들어 GitHub Pages에 게시 → 홈페이지(워드프레스) iframe에 반영
```

## 폴더 구성

| 경로 | 내용 |
|---|---|
| `briefs/` | 게시된 브리프 공개본(날짜별 JSON). 자동 작업이 채움 |
| `web/app.html` | 페이지 화면(디자인·기능) |
| `scripts/sync_drive.py` | 드라이브에서 가져오기, 형식·내부 메모 검사 |
| `scripts/build_site.py` | 목록·국가별·지속 이슈·확인점·검색용 데이터 생성 |
| `scripts/make_html.py` | 게시용 페이지 생성 |
| `schema/brief.schema.json` | 브리프 JSON 형식 정의 |
| `state/reported_problems.json` | 이미 알린 문제 파일 기록(같은 알림 반복 방지) |
| `.github/workflows/update.yml` | 자동 실행 설정 |

## 설정값

| 위치 | 이름 | 값 |
|---|---|---|
| Settings → Secrets and variables → Actions → **Secrets** | `GDRIVE_SA_KEY` | 서비스 계정 키 JSON 파일의 내용 전체 |
| Settings → Secrets and variables → Actions → **Variables** (선택) | `GDRIVE_FOLDER_ID` | 드라이브 폴더 ID. 비워 두면 기본값 `1Ufk983IY9DQ7rIwa3bPz0SLWUuw9hrmb` 사용 |
| Settings → Pages → Build and deployment | Source | **GitHub Actions** |

- 서비스 계정: `brief-reader@astral-comfort-513608-s3.iam.gserviceaccount.com` (구글 클라우드 프로젝트 `astral-comfort-513608-s3`)
- 드라이브 폴더는 이 서비스 계정에 **뷰어**로 공유되어 있어야 합니다.

## 자주 하는 일

**지금 바로 갱신하기** — Actions 탭 → 왼쪽 '브리프 갱신' → 오른쪽 **Run workflow**.

**게시가 안 된 브리프가 있을 때** — 실패 알림 메일이 오면 Actions 탭에서 실패한 실행을 열고 '드라이브에서 브리프 가져오기' 단계의 '게시하지 않은 파일' 목록을 봅니다. 사유는 세 가지입니다.

- 형식 오류: 필드 누락이나 표기 오류. 메시지에 위치가 나옵니다. 드라이브의 파일을 고쳐 다시 저장하면 다음 실행에서 게시됩니다.
- 파일명 날짜와 `date` 필드 불일치.
- 공개 필드에 내부 메모 표현(Gemini, VERIFIED, CLAIM, review pending, 403, 시간초과 등): 해당 문장을 `internal_notes`로 옮겨 다시 저장합니다.

같은 파일·같은 수정 시각의 문제는 한 번만 알립니다. 파일을 고쳐 저장하면 다시 검사합니다.

**게시된 브리프를 내리거나 고칠 때** — 드라이브에서 파일을 지워도 페이지에서는 지워지지 않습니다. 저장소의 `briefs/YYYY-MM-DD.json`을 직접 삭제(또는 수정)하면 자동으로 다시 게시됩니다. 드라이브에 같은 파일이 남아 있으면 다음 실행에서 다시 올라오므로 드라이브 쪽도 함께 정리합니다.

**디자인을 바꿀 때** — `web/app.html`을 수정해 커밋하면 자동으로 다시 게시됩니다.

## 유의 사항

- 공개 저장소입니다. `briefs/`에는 공개본만 저장되며 `internal_notes`는 저장소에 올라오지 않습니다.
- 자동 실행 기록·실패 알림은 저장소 소유 계정(센터 구글 계정) 메일로 갑니다.
- 공개 저장소에서 60일 동안 커밋이 없으면 GitHub이 예약 실행을 멈춥니다. 매일 브리프가 들어오면 해당되지 않으며, 멈췄을 때는 Actions 탭에서 다시 켜면 됩니다.

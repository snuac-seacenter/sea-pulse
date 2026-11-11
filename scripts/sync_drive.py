"""구글 드라이브 폴더의 브리프 JSON을 가져와 공개본으로 briefs/ 에 저장한다.

- 파일명에 YYYY-MM-DD 날짜가 들어 있는 .json 파일이 대상. 같은 날짜가 여럿이면 가장 최근 수정본만 사용
  (구글 문서로 저장된 경우 텍스트로 내보내 읽음)
- 형식 검사(schema/brief.schema.json) 통과 + 공개 필드에 내부 메모 표현이 없을 때만 저장
- 저장할 때 internal_notes 등 비공개 필드는 제거
- 드라이브에서 지워진 파일은 briefs/ 에서 지우지 않음(수동 삭제)
- 문제가 있던 파일은 목록을 남기고, 처음 발견된 문제면 작업을 실패로 표시 → GitHub이 알림 메일을 보냄
  (같은 파일·같은 수정시각의 문제는 state/reported_problems.json 에 기록해 반복 알림을 막음)

환경변수: GDRIVE_SA_KEY (서비스 계정 키 JSON 전문), GDRIVE_FOLDER_ID
"""
import io, json, os, re, sys

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import jsonschema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEFS = os.path.join(ROOT, 'briefs')
SCHEMA = json.load(open(os.path.join(ROOT, 'schema', 'brief.schema.json'), encoding='utf-8'))
# 파일명에 날짜가 들어 있고 .json 으로 끝나면 대상 (예: 2026-11-11.json, 2026-11-11 (1).json, 브리프_2026-11-11.json)
NAME_RE = re.compile(r'(\d{4}-\d{2}-\d{2})[^/]*\.json$', re.IGNORECASE)
PRIVATE = ('internal_notes', '_public_edits', 'pdf')
# 공개 필드에 있으면 게시를 멈추는 표현 (작업 메모가 섞였을 가능성)
BLOCK = [r'Gemini', r'\bVERIFIED(-[A-Z])?\b', r'\bCLAIM\b', r'\bVERIFY\b', r'review[- ]pending', r'복구실행', r'canonical event',
         r'research lead', r'\b403\b', r'시간초과', r'원문을? 확보하지 못', r'읽지 못한 글']
BLOCK_RE = re.compile('|'.join(BLOCK))


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def drive():
    info = json.loads(os.environ['GDRIVE_SA_KEY'])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=['https://www.googleapis.com/auth/drive.readonly'])
    return build('drive', 'v3', credentials=creds, cache_discovery=False)


def list_files(svc, folder):
    files, token = [], None
    while True:
        r = svc.files().list(q=f"'{folder}' in parents and trashed = false",
                             fields='nextPageToken, files(id, name, mimeType, modifiedTime)',
                             pageSize=1000, pageToken=token,
                             supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        files += r.get('files', [])
        token = r.get('nextPageToken')
        if not token:
            return files


def download(svc, f):
    if f['mimeType'] == 'application/vnd.google-apps.document':
        req = svc.files().export_media(fileId=f['id'], mimeType='text/plain')
    else:
        req = svc.files().get_media(fileId=f['id'], supportsAllDrives=True)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue().decode('utf-8-sig')


def main():
    folder = os.environ['GDRIVE_FOLDER_ID']
    svc = drive()
    os.makedirs(BRIEFS, exist_ok=True)
    validator = jsonschema.Draft202012Validator(SCHEMA)
    added, updated, problems = [], [], []
    files = list_files(svc, folder)
    print(f'드라이브 폴더 파일 {len(files)}개')
    # 같은 날짜 파일이 여러 개면(다시 올린 경우) 가장 최근에 수정된 파일만 사용
    latest = {}
    for f in files:
        m = NAME_RE.search(f['name'])
        if m and (m.group(1) not in latest or f['modifiedTime'] > latest[m.group(1)]['modifiedTime']):
            latest[m.group(1)] = f
    for date, f in sorted(latest.items()):
        try:
            b = json.loads(download(svc, f))
        except Exception as e:
            problems.append((f, f"{f['name']}: JSON으로 읽을 수 없음 ({e})"))
            continue
        errs = [f"{'/'.join(map(str, e.path)) or '(최상위)'}: {e.message}" for e in validator.iter_errors(b)]
        if errs:
            problems.append((f, f"{f['name']}: 형식 오류 {len(errs)}건 — " + ' | '.join(errs[:5])))
            continue
        if b['date'] != date:
            problems.append((f, f"{f['name']}: 파일명 날짜({date})와 date 필드({b['date']})가 다름"))
            continue
        pub = {k: v for k, v in b.items() if k not in PRIVATE}
        hits = sorted({h.group(0) for s in strings(pub) for h in BLOCK_RE.finditer(s)})
        if hits:
            problems.append((f, f"{f['name']}: 공개 필드에 내부 메모로 보이는 표현 — {', '.join(hits)} (internal_notes로 옮긴 뒤 다시 저장)"))
            continue
        out = os.path.join(BRIEFS, f'{date}.json')
        text = json.dumps(pub, ensure_ascii=False, indent=1) + '\n'
        old = open(out, encoding='utf-8').read() if os.path.exists(out) else None
        if old == text:
            continue
        open(out, 'w', encoding='utf-8').write(text)
        (updated if old else added).append(date)

    # 같은 문제 파일로 매시간 알림이 반복되지 않도록, 이미 알린 (파일명, 수정시각)은 다시 실패 처리하지 않음
    state_path = os.path.join(ROOT, 'state', 'reported_problems.json')
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    reported = json.load(open(state_path, encoding='utf-8')) if os.path.exists(state_path) else {}
    current = {f['name']: f['modifiedTime'] for f, _ in problems}
    new = [msg for f, msg in problems if reported.get(f['name']) != f['modifiedTime']]
    if current != reported:
        json.dump(current, open(state_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('새로 추가:', ', '.join(added) or '없음')
    print('내용 갱신:', ', '.join(updated) or '없음')
    lines = ['## 브리프 동기화', f'- 새로 추가: {", ".join(added) or "없음"}', f'- 내용 갱신: {", ".join(updated) or "없음"}']
    if problems:
        print('\n게시하지 않은 파일:')
        lines.append('\n### 게시하지 않은 파일')
        for _, msg in problems:
            print(' -', msg)
            lines.append(f'- {msg}')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        open(summary, 'a', encoding='utf-8').write('\n'.join(lines) + '\n')
    # 새로 생긴 문제만 실패 표시 대상으로 넘김 (정상 파일은 위에서 이미 저장됨)
    open(os.path.join(ROOT, '.sync_problems'), 'w', encoding='utf-8').write('\n'.join(new))

if __name__ == '__main__':
    main()

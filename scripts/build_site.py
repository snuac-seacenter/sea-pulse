"""브리프 JSON(v1)으로 게시용 데이터 파일을 만든다.

입력: briefs/*.json (sea-pulse-brief/v1)
출력: _site/data/briefs/<date>.json  공개본(비공개 필드 제거)
      _site/data/index.json           목록(지난 브리프)
      _site/data/agg.json             국가별 · 지속 이슈 · 확인점 모아보기
      _site/data/search.json          검색 색인
"""
import json, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'briefs')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, '_site')

COUNTRIES = ["TH", "VN", "ID", "PH", "MY", "MM", "SG", "KH", "LA", "BN", "TL"]
PRIVATE = ("internal_notes", "_public_edits")
ACTIVE_WINDOW = 3          # 최근 몇 호 안에 나온 이슈를 '진행 중'으로 볼지
CITE = re.compile(r'\s*\[S\d{2,3}(?:\s*[·,;–\-]\s*S?\d{2,3})*\]')

REG = {}
if os.path.exists(os.path.join(ROOT, 'schema', 'issues.json')):
    REG = {k: v for k, v in json.load(open(os.path.join(ROOT, 'schema', 'issues.json'), encoding='utf-8')).items() if not k.startswith('_')}
os.makedirs(f'{OUT}/data/briefs', exist_ok=True)
briefs = []
for fp in sorted(glob.glob(f'{SRC}/*.json')):
    b = json.load(open(fp, encoding='utf-8'))
    if b.get('schema') == 'sea-pulse-brief/v1':
        briefs.append(b)
briefs.sort(key=lambda b: b['date'])
dates = [b['date'] for b in briefs]
recent = set(dates[-ACTIVE_WINDOW:])
latest = dates[-1] if dates else None

index, search = [], []
agg = {"countries": {c: [] for c in COUNTRIES}, "issues": {}, "checks": []}


def plain(s):
    return CITE.sub('', s or '').strip()


def add(d, sec, label, text, anchor):
    t = plain(text)
    if t:
        search.append({"d": d, "s": sec, "l": label or "", "t": t, "a": anchor})


SECNAME = {'regional': '아세안 역내 정세', 'special': '특별 이슈 · 특집', 'country': '국가별 동향', 'country_brief': '국가별 동향 요약',
           'asean': 'ASEAN · 대외관계', 'theme': '주제 포커스', 'deep_dive': '심층 분석', 'macro': '거시경제', 'research': '연구·정책 분석',
           'watchlist': '워치리스트', 'other': '본문'}

for b in briefs:
    d = b['date']
    pub = {k: v for k, v in b.items() if k not in PRIVATE}
    json.dump(pub, open(f'{OUT}/data/briefs/{d}.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    S = b['sections']

    head = b.get('headline') or (b.get('pulse') or [''])[0]
    if not b.get('headline') and len(head) > 160:
        head = head[:158].rstrip() + '…'
    featured = [s['title'] for s in S if s['type'] in ('special', 'deep_dive') and s.get('title')]
    items = [s['title'] for s in S if s['type'] == 'regional' and s.get('title')] or \
            [s['title'] for s in S if s['type'] == 'country' and s.get('title')]
    index.append({"date": d, "weekday": b.get('weekday'), "edition": b.get('edition'), "headline": plain(head),
                  "featured": featured, "items": items})

    add(d, '오늘의 한 줄', '', b.get('headline'), 'top')
    for p in b.get('pulse', []):
        add(d, "Today's Pulse", '', p, 'top')
    for i, s in enumerate(S):
        anchor = f's{i}'
        text = ' '.join(filter(None, [s.get('title'), s.get('lede')] + [p['text'] for p in s.get('paragraphs', [])] +
                                [s.get('point'), s.get('next_check')] +
                                ([' '.join(sum(s['table']['rows'], []))] if s.get('table') else [])))
        add(d, SECNAME.get(s['type'], '본문'), s.get('title') or '', text, anchor)
        if s['type'] != 'macro':
            for c in s.get('countries', []):
                agg['countries'][c].append({"date": d, "kind": s['type'], "title": s.get('title'), "lede": s.get('lede'),
                                            "update": s.get('update'), "paragraphs": s.get('paragraphs', []),
                                            "point": s.get('point'), "next_check": s.get('next_check'), "anchor": anchor})
        if s.get('next_check'):
            cs = s.get('countries', [])
            agg['checks'].append({"date": d, "country": cs[0] if len(cs) == 1 else None, "text": s['next_check']})
    for w in b.get('watch_next', []):
        agg['checks'].append({"date": d, "country": None, "text": w})
        add(d, '다음에 볼 것', '', w, 'watch')
    for p in b.get('bottom_line', []):
        add(d, '정리', '', p, 'bottom')

    # 지속 이슈: 이슈 ID가 있는 크로놀로지 묶음과 모니터 행을 날짜별로 이어 붙임
    day = {}
    for c in b.get('chronology', []):
        add(d, '크로놀로지', c.get('issue') or '', ' '.join(e['date'] + ' ' + e['text'] + ' ' + (e.get('note') or '') for e in c['events']) + ' ' + (c.get('status') or ''), 'chrono')
        if c.get('issue_id'):
            e = day.setdefault(c['issue_id'], {"date": d, "name": c.get('issue')})
            e['events'] = c['events']
            e['status'] = c.get('status')
    for m in b.get('monitor', []):
        add(d, '지속 이슈 모니터', m['issue'], ' '.join(filter(None, [m.get('stage'), m.get('delta'), m.get('next_trigger')])), 'monitor')
        if m.get('issue_id'):
            e = day.setdefault(m['issue_id'], {"date": d, "name": m['issue']})
            e['monitor'] = m
            e.setdefault('name', m['issue'])
    for i, s in enumerate(S):
        for iid in s.get('issue_ids') or []:
            e = day.setdefault(iid, {"date": d, "name": None})
            e.setdefault('sections', []).append({"title": s.get('title'), "type": s['type'], "anchor": f's{i}'})
            if not e.get('name'): e['name'] = s.get('title')
    for iid, e in day.items():
        it = agg['issues'].setdefault(iid, {"id": iid, "name": e.get('name'), "entries": [], "period": None})
        if e.get('monitor') or e.get('events') or not it['name']:
            it['name'] = e.get('name') or it['name']
        it['entries'].append({k: v for k, v in e.items() if k != 'name'})
        if e.get('monitor', {}).get('period'):
            it['period'] = e['monitor']['period']

issues = []
for it in agg['issues'].values():
    it['name'] = REG.get(it['id']) or it['name'] or it['id']
    ds = [e['date'] for e in it['entries']]
    it['first'], it['last'], it['days'] = min(ds), max(ds), len(ds)
    end = (it.get('period') or {}).get('end')
    it['active'] = it['last'] in recent or bool(end and latest and end >= latest)
    issues.append(it)
issues.sort(key=lambda x: (not x['active'], x['last']), reverse=False)
issues.sort(key=lambda x: (x['active'], x['last'], x['days']), reverse=True)
agg['issues'] = issues
index.reverse()
json.dump({"briefs": index, "updated": latest}, open(f'{OUT}/data/index.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump(agg, open(f'{OUT}/data/agg.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump(search, open(f'{OUT}/data/search.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f'{len(briefs)} briefs → {OUT} | issues {len(issues)} | search {len(search)}')

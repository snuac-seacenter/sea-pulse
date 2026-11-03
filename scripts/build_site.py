"""Build the public data files for the SEA Pulse brief site.

Input : briefs/*.json  (one brief per day, schema sea-pulse-brief/v0; may contain internal fields)
Output: _site/data/briefs/<date>.json   public brief (internal fields removed)
        _site/data/index.json           list of briefs for archive + navigation
        _site/data/agg.json             cross-day views: countries, issues, tracker, checks
        _site/data/search.json          flat text index for search
"""
import json, glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'briefs')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, '_site')

COUNTRIES = [("TH", "태국"), ("VN", "베트남"), ("ID", "인도네시아"), ("PH", "필리핀"), ("MY", "말레이시아"),
             ("MM", "미얀마"), ("SG", "싱가포르"), ("KH", "캄보디아"), ("LA", "라오스"), ("BN", "브루나이"), ("TL", "동티모르")]
NAME = dict(COUNTRIES)
ISSUE_NAMES = {"scs": "남중국해 / COC", "th-kh-border": "태국-캄보디아 국경",
               "us-trade": "미국 관세·환적·원산지", "asean-agenda": "ASEAN 일정·대외관계"}
PRIVATE = ("internal_notes", "_public_edits")

os.makedirs(f'{OUT}/data/briefs', exist_ok=True)

briefs = []
for fp in sorted(glob.glob(f'{SRC}/*.json')):
    b = json.load(open(fp, encoding='utf-8'))
    if b.get('schema', '').startswith('sea-pulse-brief/'):
        briefs.append(b)
briefs.sort(key=lambda b: b['date'])

index, search = [], []
agg = {"countries": {c: [] for c, _ in COUNTRIES}, "issues": {}, "tracker": {}, "checks": []}


def add_search(date, section, label, text, anchor):
    if text:
        search.append({"d": date, "s": section, "l": label, "t": text, "a": anchor})


for b in briefs:
    d = b['date']
    pub = {k: v for k, v in b.items() if k not in PRIVATE}
    pub.pop('pdf', None)  # 웹페이지는 PDF를 쓰지 않음
    json.dump(pub, open(f'{OUT}/data/briefs/{d}.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    tags = sorted({c for r in b['regional'] for c in r.get('countries', [])} | {c['code'] for c in b['countries']})
    index.append({"date": d, "weekday": b.get('weekday'), "headline": b['headline'],
                  "special": (b.get('special') or {}).get('title'),
                  "regional": [r['title'] for r in b['regional']]})

    add_search(d, "오늘의 한 줄", "", b['headline'], "top")
    for i, r in enumerate(b['regional']):
        add_search(d, "아세안 역내 정세", r['title'], ' '.join(filter(None, [r['title'], r['body'], r.get('point')])), f"r{i+1}")
        for c in r.get('countries', []):
            agg['countries'][c].append({"date": d, "kind": "regional", "title": r['title'], "text": r['body'],
                                        "point": r.get('point'), "anchor": f"r{i+1}"})
    if b.get('special'):
        sp = b['special']
        add_search(d, "특별 이슈", sp['title'], ' '.join(s['text'] for s in sp['sections']), "special")
    for c in b['countries']:
        add_search(d, "국가별 동향", c['name'],
                   ' '.join([p['field'] + ' ' + p['text'] for p in c['paragraphs']] + [c.get('point') or '', c.get('next_check') or '']),
                   f"c-{c['code']}")
        agg['countries'][c['code']].append({"date": d, "kind": "country", "update": c.get('update'),
                                            "paragraphs": c['paragraphs'], "point": c.get('point'),
                                            "next_check": c.get('next_check'), "anchor": f"c-{c['code']}"})
        if c.get('next_check'):
            agg['checks'].append({"date": d, "country": c['code'], "text": c['next_check']})
    for c in b.get('countries_brief', []):
        add_search(d, "국가별 동향", c['name'], c['trend'] + ' ' + c['next_check'], f"c-{c['code']}")
        agg['countries'][c['code']].append({"date": d, "kind": "brief", "text": c['trend'], "next_check": c['next_check'],
                                            "anchor": "brief5"})
        agg['checks'].append({"date": d, "country": c['code'], "text": c['next_check']})
    for w in b.get('watch_next', []):
        agg['checks'].append({"date": d, "country": None, "text": w})
        add_search(d, "다음에 볼 것", "", w, "watch")
    for ch in b.get('chronology', []):
        it = agg['issues'].setdefault(ch['id'], {"id": ch['id'], "name": ISSUE_NAMES.get(ch['id'], ch['issue']), "entries": []})
        it['entries'].append({"date": d, "label": ch['issue'], "events": ch['events'], "status": ch.get('status')})
        add_search(d, "지속 이슈", ch['issue'], ' '.join(e['date'] + ' ' + e['text'] for e in ch['events']) + ' ' + (ch.get('status') or ''), "chrono")
    for t in b.get('tracker', []):
        tr = agg['tracker'].setdefault(t['id'], {"id": t['id'], "name": t['name'], "history": []})
        tr['name'] = t['name']
        tr['history'].append({"date": d, "level": t.get('level'), "change": t.get('change'),
                              "judgement": t.get('judgement'), "next_check": t.get('next_check')})
    for a in b.get('asean_overview', []):
        add_search(d, "ASEAN 개요", a.get('label') or '', a['text'], "asean")
    for r in b.get('research', []):
        add_search(d, "연구·정책 분석", r['source'], ' '.join(filter(None, [r.get('title'), r['text']])), "research")

agg['issues'] = list(agg['issues'].values())
agg['tracker'] = list(agg['tracker'].values())
agg['country_names'] = COUNTRIES
index.reverse()  # newest first
json.dump({"briefs": index, "updated": briefs[-1]['date'] if briefs else None},
          open(f'{OUT}/data/index.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump(agg, open(f'{OUT}/data/agg.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump(search, open(f'{OUT}/data/search.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f'{len(briefs)} briefs →', OUT, '| search entries', len(search))

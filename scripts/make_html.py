"""web/app.html -> _site/index.html (게시용 페이지). build_site.py 다음에 실행."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
body = open(os.path.join(ROOT, 'web', 'app.html'), encoding='utf-8').read()
head = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n')
i = body.index('</style>') + len('</style>')
out = os.path.join(ROOT, '_site')
os.makedirs(out, exist_ok=True)
open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(head + body[:i] + '\n</head>\n<body>\n' + body[i:] + '\n</body>\n</html>\n')
open(os.path.join(out, '.nojekyll'), 'w').close()
print('_site/index.html')

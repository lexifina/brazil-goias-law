"""Private (not published). Fetches the Leis Complementares of Goiás from the Legisla Goiás API (Casa Civil).

    python -X utf8 fetch.py [--limit N]

One process, one request at a time, 3 s between requests (legisla.casacivil.go.gov.br; robots.txt is the app page, no
rules). Cache: .cache/raw/<sha256(url)>, .cache/requests.jsonl. The list: .cache/lc-index.json (in force, partly revoked
or promulgated; revoked, lapsed, vetoed, void and unconstitutional ones are left out).
"""
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
RAW = CACHE / 'raw'
RAW.mkdir(parents=True, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
API = 'https://legisla.casacivil.go.gov.br/api/v2/pesquisa/legislacoes'
KEEP = {'em vigor', 'revogada parcialmente', 'promulgada'}
_last = [0.0]


def get(url, delay=3.0):
    p = RAW / hashlib.sha256(url.encode()).hexdigest()
    if p.exists():
        return p.read_bytes()
    code = ''
    for i in range(4):
        w = delay - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        r = subprocess.run(['curl', '-sS', '-L', '--compressed', '-m', '120', '-A', UA, '-o', str(p) + '.tmp',
                            '-w', '%{http_code}', url], capture_output=True)
        _last[0] = time.time()
        code = r.stdout.decode().strip()
        with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'url': url, 'status': code, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}) + '\n')
        if code == '200':
            b = Path(str(p) + '.tmp').read_bytes()
            if not b.lstrip()[:1] in (b'{', b'['):
                raise SystemExit(f'{url}: not JSON (challenge?), stopping: {b[:200]!r}')
            os.replace(str(p) + '.tmp', p)
            return b
        if code in ('403', '429') or code.startswith('5'):
            raise SystemExit(f'{url}: HTTP {code}, stopping this host')
        time.sleep(10 * (i + 1))
    raise SystemExit(f'{url}: {code}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    rows, page = [], 1
    while True:
        d = json.loads(get(f'{API}?page={page}&qtd_por_pagina=100&tipo_legislacao=1,15,21&ordenarPor=data'))
        rows += d['resultados']
        if not d['resultados'] or len(rows) >= d['total_resultados']:
            break
        page += 1
    keep = [r for r in rows if (r.get('estado_legislacao') or {}).get('nome', '').lower() in KEEP]
    (CACHE / 'lc-index.json').write_text(json.dumps({'total': len(rows), 'acts': keep}, ensure_ascii=False, indent=0),
                                         encoding='utf-8')
    print(len(rows), 'listed,', len(keep), 'kept', flush=True)
    keep = sorted(keep, key=lambda r: r['id'])
    if a.limit:
        keep = keep[:a.limit]
    for n, r in enumerate(keep):
        get(f"{API}/{r['id']}")
        if n % 20 == 0:
            print(n, r['ano'], r['numero'], flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    sys.exit(main())

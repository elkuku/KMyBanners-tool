"""Compare `ingress-banners-tool build` output with nikp3h's hand-made data.js.

  .venv/bin/python tests/compare_nikp3h.py out/banners.json ~/repos/nikp3h-ingress-stats/mission-banners/data.js
"""
import json
import sys
from pathlib import Path


def load_js(p: Path):
    s = p.read_text(encoding='utf-8')
    return json.loads(s[s.index('['):s.rindex(']') + 1])


def main():
    built = json.loads(Path(sys.argv[1]).read_text())['banners']
    truth = load_js(Path(sys.argv[2]))
    t = {(b.get('id'), b['rows']) for b in truth if b.get('id')}
    got = {(b.get('id'), b['rows']) for b in built if b['status'] == 'match'}
    t_ids = {b['id']: b['rows'] for b in truth if b.get('id')}
    same = got & t
    print(f'hand-made banners with a Bannergress id: {len(t)}')
    print(f'built matches: {len(got)}, same id and rows: {len(same)}')
    for bid, rows in sorted(got - t, key=lambda x: int(x[1].split(',')[0].split('-')[0])):
        print(f'  differs: {bid} rows {rows} (hand-made: {t_ids.get(bid, "not there")})')
    review = [b for b in built if b['status'] == 'review']
    print(f'groups to review: {len(review)} ({sum(len(b["rows"].split(",")) for b in review)} row ranges)')
    missing = {bid for bid, _ in t} - {bid for bid, _ in got}
    print(f'hand-made banners not matched automatically: {len(missing)}')


if __name__ == '__main__':
    main()

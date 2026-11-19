"""Spike: the GitHub calls the Android app will make, with a device-flow token (like the app gets).

  .venv/bin/python tests/spike_github.py <oauth client id> <screenshot> [<screenshot> …]

Prints the sign-in code to enter at https://github.com/login/device, then: creates
<login>/ingress-banners-spike from elkuku/ingress-banners-spike-template, turns on Pages (Actions),
uploads the screenshots to inbox/ in one commit, waits for the workflow and prints the page.
The token is only kept in memory.
"""
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TEMPLATE = 'elkuku/ingress-banners-spike-template'
NAME = 'ingress-banners-spike'
SCOPE = 'public_repo'


def post_form(url: str, data: dict) -> dict:
    body = '&'.join(f'{k}={v}' for k, v in data.items()).encode()
    req = urllib.request.Request(url, body, {'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


class GitHub:
    def __init__(self, token: str):
        self.token = token
        self.scopes = None

    def call(self, method: str, path: str, body=None, ok=(200, 201, 202, 204)):
        req = urllib.request.Request('https://api.github.com' + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Authorization': f'Bearer {self.token}',
                                              'Accept': 'application/vnd.github+json',
                                              'X-GitHub-Api-Version': '2022-11-28'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                self.scopes = r.headers.get('X-OAuth-Scopes', self.scopes)
                data = r.read()
                return r.status, json.loads(data) if data else None
        except urllib.error.HTTPError as e:
            data = e.read()
            return e.code, json.loads(data) if data else None


def step(msg):
    print(f'\n== {msg}', flush=True)


def main():
    client_id, shots = sys.argv[1], [Path(p) for p in sys.argv[2:]]

    step('1. Device flow sign-in')
    d = post_form('https://github.com/login/device/code', {'client_id': client_id, 'scope': SCOPE})
    print(f"CODE: {d['user_code']}  at {d['verification_uri']}", flush=True)
    interval = d.get('interval', 5)
    while True:
        time.sleep(interval)
        t = post_form('https://github.com/login/oauth/access_token',
                      {'client_id': client_id, 'device_code': d['device_code'],
                       'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'})
        if 'access_token' in t:
            print(f"signed in, granted scopes: {t.get('scope')!r}")
            break
        if t.get('error') == 'slow_down':
            interval += 5
        elif t.get('error') != 'authorization_pending':
            sys.exit(f'sign-in failed: {t}')
    gh = GitHub(t['access_token'])
    s, user = gh.call('GET', '/user')
    login = user['login']
    print(f'user {login}, X-OAuth-Scopes: {gh.scopes}')

    step('2. Repo from the template')
    s, r = gh.call('POST', f'/repos/{TEMPLATE}/generate',
                   {'owner': login, 'name': NAME, 'private': False,
                    'description': 'Spike for the ingress-banners app (will be deleted)'})
    print(s, r.get('html_url') if isinstance(r, dict) else r)
    if s not in (200, 201):
        print(json.dumps(r, indent=1))
        if s != 422:
            sys.exit(1)
    repo = f'{login}/{NAME}'
    for _ in range(30):  # the copy takes a moment
        s, ref = gh.call('GET', f'/repos/{repo}/git/ref/heads/main')
        if s == 200:
            break
        time.sleep(2)
    print('main at', ref['object']['sha'])
    s, files = gh.call('GET', f'/repos/{repo}/contents/.github/workflows')
    print('workflows copied:', [f['name'] for f in files] if s == 200 else (s, files))

    step('3. Pages from Actions')
    s, p = gh.call('POST', f'/repos/{repo}/pages', {'build_type': 'workflow'})
    print(s, p.get('html_url') if isinstance(p, dict) and 'html_url' in p else p)

    step('4. Upload the screenshots in one commit (Git Data API)')
    base = ref['object']['sha']
    s, commit = gh.call('GET', f'/repos/{repo}/git/commits/{base}')
    tree = []
    stamp = time.strftime('%Y%m%d-%H%M%S')
    for n, f in enumerate(shots):
        t0 = time.time()
        s, blob = gh.call('POST', f'/repos/{repo}/git/blobs',
                          {'content': base64.b64encode(f.read_bytes()).decode(), 'encoding': 'base64'})
        print(f'  blob {f.name} ({f.stat().st_size / 1e6:.1f} MB): {s} in {time.time() - t0:.1f} s')
        tree.append({'path': f'inbox/{stamp}/{n:02d}.png', 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    s, newtree = gh.call('POST', f'/repos/{repo}/git/trees', {'base_tree': commit['tree']['sha'], 'tree': tree})
    s, newcommit = gh.call('POST', f'/repos/{repo}/git/commits',
                           {'message': f'Add {len(shots)} screenshots', 'tree': newtree['sha'], 'parents': [base]})
    s, r = gh.call('PATCH', f'/repos/{repo}/git/refs/heads/main', {'sha': newcommit['sha']})
    print('ref update:', s, newcommit['sha'][:7])

    step('5. Wait for the workflow')
    run = None
    for _ in range(90):
        s, runs = gh.call('GET', f'/repos/{repo}/actions/runs?head_sha={newcommit["sha"]}')
        if runs and runs.get('workflow_runs'):
            run = runs['workflow_runs'][0]
            if run['status'] == 'completed':
                break
        time.sleep(5)
    print('run:', run and (run['status'], run['conclusion'], run['html_url']))
    s, p = gh.call('GET', f'/repos/{repo}/pages')
    print('page:', s, p.get('html_url') if isinstance(p, dict) else p)


if __name__ == '__main__':
    main()

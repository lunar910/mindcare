"""One more Meshy animation for Pico's rig: 'Talk with Left Hand Raised' (action 310), 3 credits."""
import json, os, subprocess, sys
ENV = dict(os.environ, NODE_USE_ENV_PROXY='1', NODE_EXTRA_CA_CERTS='/root/.ccr/ca-bundle.crt')
BASE = ['npm', 'exec', '--yes', '--package=meshy-cli@0.4.0', '--', 'meshy']
J = ['--output-schema', 'v1', '--format', 'json', '--no-update-check']
def run(args, timeout=1600):
    p = subprocess.run(BASE + args + J, capture_output=True, text=True, env=ENV, timeout=timeout)
    try:
        j = json.loads(p.stdout)
    except Exception:
        print('!! no json', args[:3], p.stdout[-300:], p.stderr[-300:], flush=True); sys.exit(1)
    if not j.get('ok'):
        print('!! error', args[:3], j.get('error'), flush=True); sys.exit(1)
    r = j.get('result') or {}
    return r.get('task', r), r
def dl(url, path):
    subprocess.run(['curl', '-sS', '--max-time', '300', '-o', path, url], check=True)
    print('   saved', path, os.path.getsize(path), flush=True)
RIG = '01a2096f-e289-75e1-a470-7783be064763'
name, act = sys.argv[1], sys.argv[2]
_, r = run(['animate', 'create', '--rig-task-id', RIG, '--action-id', act, '--async', '--operation-id', f'np-pico-anim-{name}-1'])
ta = r['task_id']
json.dump({'task_id': ta, 'action_id': act}, open(f'an2_pico_{name}.json', 'w'))
t, _ = run(['animate', 'wait', ta, '--timeout', '1150'])
print('anim', name, t.get('status'), 'credits', t.get('consumed_credits'), flush=True)
dl(t['result']['animation_glb_url'], f'../models/anim/pico_{name}.glb')
t, r = run(['balance'])
print('balance', r.get('balance', t.get('balance')), flush=True)

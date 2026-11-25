"""Nox v2 (corrected hair): image-to-3d -> remesh 30k -> rig -> 6 animations -> downloads. Prints one line per step."""
import json
import os
import subprocess
import sys

ENV = dict(os.environ, NODE_USE_ENV_PROXY='1', NODE_EXTRA_CA_CERTS='/root/.ccr/ca-bundle.crt')
BASE = ['npm', 'exec', '--yes', '--package=meshy-cli@0.4.0', '--', 'meshy']
J = ['--output-schema', 'v1', '--format', 'json', '--no-update-check']


def run(args, timeout=1600):
    p = subprocess.run(BASE + args + J, capture_output=True, text=True, env=ENV, timeout=timeout)
    try:
        j = json.loads(p.stdout)
    except Exception:
        print('!! no json', args[:3], p.stdout[-300:], p.stderr[-300:], flush=True)
        sys.exit(1)
    if not j.get('ok'):
        print('!! error', args[:3], j.get('error'), flush=True)
        sys.exit(1)
    r = j.get('result') or {}
    return r.get('task', r), r


def dl(url, path):
    subprocess.run(['curl', '-sS', '--max-time', '300', '-o', path, url], check=True)
    print('   saved', path, os.path.getsize(path), flush=True)


img = json.load(open('hairw_C.json'))['result']
img = img.get('task', img)
img_id = img.get('id') or img.get('task_id')
_, r = run(['image-to-3d', 'create', '--input-task-id', img_id, '--model-type', 'standard', '--should-texture', 'true', '--enable-pbr', 'false',
            '--texture-resolution', '2k', '--pose-mode', 't-pose', '--remove-lighting', 'false', '--async', '--operation-id', 'np-nox2-3d-2'])
t3 = r['task_id']; print('3d submitted', t3, flush=True)
t, _ = run(['image-to-3d', 'wait', t3, '--timeout', '1450'])
print('3d', t.get('status'), 'credits', t.get('consumed_credits'), flush=True)
dl(t['model_urls']['glb'], '../models/final_nox2.glb')
_, r = run(['remesh', 'create', '--input-task-id', t3, '--topology', 'triangle', '--target-polycount', '30000', '--target-formats', 'glb', '--async',
            '--operation-id', 'np-nox2-remesh-2'])
tr = r['task_id']
t, _ = run(['remesh', 'wait', tr, '--timeout', '880'])
print('remesh', t.get('status'), 'credits', t.get('consumed_credits'), flush=True)
_, r = run(['rigging', 'create', '--input-task-id', tr, '--height-meters', '1.78', '--async', '--operation-id', 'np-nox2-rig-2'])
tg = r['task_id']
t, _ = run(['rigging', 'wait', tg, '--timeout', '1450'])
print('rig', t.get('status'), 'credits', t.get('consumed_credits'), tg, flush=True)
dl(t['result']['rigged_character_glb_url'], '../models/rig/nox2_rigged.glb')
ids = {}
for name, act in (('idle', 0), ('talkright', 314), ('shrug', 317), ('listen', 47), ('agree', 25), ('talkopen', 313)):
    _, r = run(['animate', 'create', '--rig-task-id', tg, '--action-id', str(act), '--async', '--operation-id', f'np-nox2-anim-{name}-2'])
    ids[name] = r['task_id']
for name, ta in ids.items():
    t, _ = run(['animate', 'wait', ta, '--timeout', '1150'])
    print('anim', name, t.get('status'), 'credits', t.get('consumed_credits'), flush=True)
    dl(t['result']['animation_glb_url'], f'../models/anim/nox2_{name}.glb')
t, r = run(['balance'])
print('balance', r.get('balance', t.get('balance')), flush=True)
print('DONE', flush=True)

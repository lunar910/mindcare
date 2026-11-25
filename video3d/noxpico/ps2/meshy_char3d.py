"""Realistic-style character: concept image -> Meshy image-to-3d (T-pose, textured) -> remesh -> rig.  Prints one line per step.

    python char3d.py NAME IMAGE.png HEIGHT_M        (about 40 credits: 30 + 5 + 5)"""
import json, os, subprocess, sys
ENV = dict(os.environ, NODE_USE_ENV_PROXY='1', NODE_EXTRA_CA_CERTS='/root/.ccr/ca-bundle.crt')
BASE = ['npm', 'exec', '--yes', '--package=meshy-cli@0.4.0', '--', 'meshy']
J = ['--output-schema', 'v1', '--format', 'json', '--no-update-check']
OUT = '/tmp/claude-0/-home-user-mindcare/a7878755-9e4c-5740-b306-7f25e8d8722e/scratchpad/meshy/models'


def run(args, timeout=1700):
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
    subprocess.run(['curl', '-sS', '--max-time', '400', '-o', path, url], check=True)
    print('   saved', os.path.basename(path), os.path.getsize(path), flush=True)


name, image, height = sys.argv[1], sys.argv[2], sys.argv[3]
state_f = f'{name}_state.json'
st = json.load(open(state_f)) if os.path.exists(state_f) else {}


def step(key, create_args, resource, timeout):
    """Submit once (the task id is kept on disk, so a re-run resumes instead of paying again), then wait."""
    if key not in st:
        _, r = run(create_args + ['--async', '--operation-id', f'np-v3-{name}-{key}-1'])
        st[key] = r['task_id']
        json.dump(st, open(state_f, 'w'))
    t, _ = run([resource, 'wait', st[key], '--timeout', str(timeout)], timeout=timeout + 60)
    print(key, t.get('status'), 'credits', t.get('consumed_credits'), flush=True)
    if t.get('status') != 'SUCCEEDED':
        print('!! task not succeeded', t.get('task_error'), flush=True); sys.exit(1)
    return t


t = step('3d', ['image-to-3d', 'create', '--image-url', image, '--model-type', 'standard', '--should-texture', 'true', '--enable-pbr', 'false',
                '--texture-resolution', '4k', '--pose-mode', 't-pose', '--remove-lighting', 'false'], 'image-to-3d', 1500)
if not os.path.exists(f'{OUT}/v3_{name}_raw.glb'):
    dl(t['model_urls']['glb'], f'{OUT}/v3_{name}_raw.glb')
t = step('remesh', ['remesh', 'create', '--input-task-id', st['3d'], '--topology', 'triangle', '--target-polycount', '80000', '--target-formats', 'glb'],
         'remesh', 900)
t = step('rig', ['rigging', 'create', '--input-task-id', st['remesh'], '--height-meters', height], 'rigging', 1500)
dl(t['result']['rigged_character_glb_url'], f'{OUT}/rig/{name}_rigged.glb')
print('DONE', name, flush=True)

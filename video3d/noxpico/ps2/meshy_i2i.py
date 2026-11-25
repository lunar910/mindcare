"""One Meshy image-to-image job (nano-banana-pro, 9 credits): python i2i.py NAME "ref1.png,ref2.png" PROMPT_FILE"""
import json, os, subprocess, sys
ENV = dict(os.environ, NODE_USE_ENV_PROXY='1', NODE_EXTRA_CA_CERTS='/root/.ccr/ca-bundle.crt')
BASE = ['npm', 'exec', '--yes', '--package=meshy-cli@0.4.0', '--', 'meshy']
J = ['--output-schema', 'v1', '--format', 'json', '--no-update-check']
def run(args, timeout=900):
    p = subprocess.run(BASE + args + J, capture_output=True, text=True, env=ENV, timeout=timeout)
    try:
        j = json.loads(p.stdout)
    except Exception:
        print('!! no json', args[:3], p.stdout[-300:], p.stderr[-300:], flush=True); sys.exit(1)
    if not j.get('ok'):
        print('!! error', args[:3], j.get('error'), flush=True); sys.exit(1)
    r = j.get('result') or {}
    return r.get('task', r), r
name, refs, pf = sys.argv[1], sys.argv[2], sys.argv[3]
prompt = open(pf).read().strip()
_, r = run(['image-to-image', 'create', '--ai-model', 'nano-banana-pro', '--aspect-ratio', '3:4', '--reference-image-urls', refs, '--prompt', prompt,
            '--async', '--operation-id', f'np-v3-{name}-3'])
tid = r['task_id']
json.dump({'task_id': tid}, open(f'{name}.json', 'w'))
t, _ = run(['image-to-image', 'wait', tid, '--timeout', '540'])
print(name, t.get('status'), 'credits', t.get('consumed_credits'), flush=True)
url = (t.get('image_urls') or [''])[0]
subprocess.run(['curl', '-sS', '--max-time', '120', '-o', f'{name}.png', url], check=True)
print('saved', f'{name}.png', os.path.getsize(f'{name}.png'))

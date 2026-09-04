from __future__ import annotations
import base64, hashlib, io, lzma, tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
RUNTIME_DIR=ROOT/'runtime'
MARKER=ROOT/'agentcut'/'editor.py'
EXPECTED_SHA256='021d66f059c9848fe0cc81169c7a45c5f5666a022823185300422a417e755aba'

def _runtime_bytes():
    parts=sorted(RUNTIME_DIR.glob('part*.b64'))
    if not parts: raise SystemExit(f'Missing bundled runtime parts in {RUNTIME_DIR}')
    encoded=''.join(p.read_text(encoding='ascii').strip() for p in parts)
    payload=base64.b64decode(encoded,validate=True)
    digest=hashlib.sha256(payload).hexdigest()
    if digest!=EXPECTED_SHA256: raise SystemExit(f'Runtime checksum mismatch: {digest}')
    return payload

def _safe_extract(tf,root):
    rr=root.resolve()
    for member in tf.getmembers():
        target=(root/member.name).resolve()
        if target!=rr and rr not in target.parents: raise RuntimeError(f'Unsafe archive member: {member.name}')
    tf.extractall(root,filter='data')

def main():
    if MARKER.exists(): print('AgentCut runtime already expanded.'); return 0
    raw=lzma.decompress(_runtime_bytes())
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tf: _safe_extract(tf,ROOT)
    if not MARKER.exists(): raise SystemExit('Runtime extraction finished but agentcut/editor.py is missing.')
    print('AgentCut 1.0.0 Remaster runtime expanded successfully.'); return 0

if __name__=='__main__': raise SystemExit(main())

"""Check and apply the small integration patch to the pinned stable LMS only."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

def apply_pinned_patch(root, patch, label='LMS bridge'):
    root=Path(root)
    patch=Path(patch).resolve()
    manifest=json.loads(patch.with_suffix('.json').read_text(encoding='utf-8'))
    states=set()
    normalized={}
    for name, hashes in manifest.items():
        # Normalize Git's Windows checkout line endings, not source content.
        content=(root/name).read_text(encoding='utf-8').encode('utf-8')
        digest=hashlib.sha256(content).hexdigest()
        state=next((state for state, expected in hashes.items() if digest == expected), None)
        if state is None:
            raise RuntimeError(f'Pinned {label} source changed: {name}. Review before building.')
        states.add(state)
        normalized[name]=content
    if len(states) != 1:
        raise RuntimeError(f'{label} is only partially applied. Review before building.')
    # Docker copies Windows checkouts verbatim. Git on Linux cannot match an
    # LF patch against CRLF files, even though their normalized hashes match.
    # Only normalize after every source has passed the pin and state checks.
    for name, content in normalized.items():
        if (root/name).read_bytes() != content:
            (root/name).write_bytes(content)
    check=subprocess.run(['git','apply','--check',str(patch)],cwd=root,capture_output=True)
    if check.returncode:
        reverse=subprocess.run(['git','apply','--reverse','--check',str(patch)],cwd=root,capture_output=True)
        if reverse.returncode:
            raise RuntimeError(f'Stable {label} no longer applies. Review the upstream change before building. '+check.stderr.decode())
    else:
        subprocess.run(['git','apply',str(patch)],cwd=root,check=True)

def apply(root):
    root=Path(root)
    apply_pinned_patch(root, root/'deploy/patches/lms-ai-coach.patch')
    shutil.copyfile(root/'apps/bpo_coach/frontend/src/bridge.js',root/'frontend/src/utils/aiCoach.js')

if __name__=='__main__': apply(Path(__file__).resolve().parents[1])

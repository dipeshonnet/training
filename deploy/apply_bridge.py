"""Check and apply the small integration patch to the pinned stable LMS only."""
from pathlib import Path
import shutil
import subprocess

def apply(root):
    root=Path(root)
    patch=root/'deploy/patches/lms-ai-coach.patch'
    check=subprocess.run(['git','apply','--check',str(patch)],cwd=root,capture_output=True)
    if check.returncode:
        reverse=subprocess.run(['git','apply','--reverse','--check',str(patch)],cwd=root,capture_output=True)
        if reverse.returncode:
            raise RuntimeError('Stable LMS bridge no longer applies. Review the upstream change before building. '+check.stderr.decode())
    else:
        subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
    shutil.copyfile(root/'apps/bpo_coach/frontend/src/bridge.js',root/'frontend/src/utils/aiCoach.js')

if __name__=='__main__': apply(Path(__file__).resolve().parents[1])

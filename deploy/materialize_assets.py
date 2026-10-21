"""Export Bench assets as real files, including app-public symlink targets."""
from pathlib import Path
import shutil
import sys


def materialize(source, destination):
    source, destination = Path(source), Path(destination)
    # copytree follows directory and file symlinks by default. Dangling targets
    # fail the image build instead of shipping broken links to the Nginx stage.
    shutil.copytree(source, destination, symlinks=False)
    if any(path.is_symlink() for path in destination.rglob('*')):
        raise RuntimeError('The exported asset tree still contains symlinks')


if __name__ == '__main__':
    materialize(*sys.argv[1:])

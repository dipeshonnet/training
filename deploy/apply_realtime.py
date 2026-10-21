"""Apply the hash-checked internal realtime routing patch to pinned Frappe."""
from pathlib import Path
import sys

from apply_bridge import apply_pinned_patch


if __name__ == '__main__':
    apply_pinned_patch(Path(sys.argv[1]), Path(__file__).parent / 'patches/frappe-realtime.patch',
                       'Frappe realtime routing')

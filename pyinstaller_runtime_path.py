import os
import sys

if getattr(sys, 'frozen', False):
    base_dir = getattr(sys, '_MEIPASS', '')
    if base_dir:
        for path in (base_dir, os.path.join(base_dir, 'src')):
            if os.path.isdir(path) and path not in sys.path:
                sys.path.insert(0, path)

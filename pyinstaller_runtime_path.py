import importlib
import os
import sys
import types

base_dir = getattr(sys, '_MEIPASS', '') if getattr(sys, 'frozen', False) else ''
for path in (base_dir, os.path.join(base_dir, 'src')):
    if path and os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)

if 'src' not in sys.modules:
    src_module = types.ModuleType('src')
    src_paths = []
    if base_dir:
        src_dir = os.path.join(base_dir, 'src')
        if os.path.isdir(src_dir):
            src_paths.append(src_dir)
    src_module.__path__ = src_paths
    sys.modules['src'] = src_module


def _alias_module(alias: str, target: str) -> None:
    if alias in sys.modules:
        return
    try:
        module = importlib.import_module(target)
    except Exception:
        return
    sys.modules[alias] = module
    parent_name, _, child_name = alias.rpartition('.')
    if not parent_name:
        return
    parent = sys.modules.get(parent_name)
    if parent is None:
        return
    try:
        setattr(parent, child_name, module)
    except Exception:
        return


for alias, target in (
    ('src.app', 'app'),
    ('src.cli', 'cli'),
    ('src.services', 'services'),
    ('src.services.history', 'services.history'),
    ('src.services.security', 'services.security'),
    ('src.services.tests', 'services.tests'),
    ('src.services.updater', 'services.updater'),
    ('src.services.windows', 'services.windows'),
    ('src.services.zapret', 'services.zapret'),
    ('src.ui', 'ui'),
    ('src.utils', 'utils'),
):
    _alias_module(alias, target)

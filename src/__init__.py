import importlib
import sys


_DEF_ALIASES = (
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
)


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


for _alias, _target in _DEF_ALIASES:
    _alias_module(_alias, _target)

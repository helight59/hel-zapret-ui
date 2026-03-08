# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
project_root = os.path.abspath('.')
src_root = os.path.join(project_root, 'src')


def collect_python_sources(root_dir: str) -> list[tuple[str, str]]:
  datas: list[tuple[str, str]] = []
  for current_root, dirs, files in os.walk(root_dir):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    rel_dir = os.path.relpath(current_root, project_root)
    for file_name in files:
      if not file_name.endswith('.py'):
        continue
      datas.append((os.path.join(current_root, file_name), rel_dir))
  return datas


hiddenimports = []
hiddenimports += collect_submodules('PySide6')
hiddenimports += collect_submodules('src.app')
hiddenimports += collect_submodules('src.cli')
hiddenimports += collect_submodules('src.services')
hiddenimports += collect_submodules('src.services.history')
hiddenimports += collect_submodules('src.services.security')
hiddenimports += collect_submodules('src.services.tests')
hiddenimports += collect_submodules('src.services.updater')
hiddenimports += collect_submodules('src.services.windows')
hiddenimports += collect_submodules('src.services.zapret')
hiddenimports += collect_submodules('src.ui')
hiddenimports += collect_submodules('src.utils')

datas = [('assets', 'assets')]
datas += collect_python_sources(src_root)

a = Analysis(
  ['src/main.py'],
  pathex=[project_root, src_root],
  binaries=[],
  datas=datas,
  hiddenimports=hiddenimports,
  hookspath=[],
  hooksconfig={},
  runtime_hooks=['pyinstaller_runtime_path.py'],
  excludes=[],
  win_no_prefer_redirects=False,
  win_private_assemblies=False,
  cipher=block_cipher,
  noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
  pyz,
  a.scripts,
  a.binaries,
  a.zipfiles,
  a.datas,
  [],
  name='hel_zapret_ui',
  icon='assets/app.ico',
  debug=False,
  bootloader_ignore_signals=False,
  strip=False,
  upx=True,
  console=False,
  disable_windowed_traceback=False,
  target_arch=None,
  codesign_identity=None,
  entitlements_file=None,
)

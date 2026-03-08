# -*- mode: python ; coding: utf-8 -*-

# One-file сборка (один exe), чтобы можно было распространять "голый" файл.
# Все данные из папки assets будут внутри exe и распакуются во временную папку
# sys._MEIPASS при старте.

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = []
hiddenimports += collect_submodules('PySide6')

a = Analysis(
  ['src/main.py'],
  pathex=['.'],
  binaries=[],
  datas=[('assets', 'assets')],
  hiddenimports=hiddenimports,
  hookspath=[],
  hooksconfig={},
  runtime_hooks=[],
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

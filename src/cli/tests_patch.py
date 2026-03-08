import re
from pathlib import Path


def ensure_tests_cli_support(zapret_root: Path) -> tuple[bool, str]:
  root = Path(zapret_root)
  if not root.exists():
    return False, 'zapret root does not exist'

  # Support accidental nesting (zip may contain an extra zapret/ folder).
  if not (root / 'service.bat').exists() and (root / 'zapret' / 'service.bat').exists():
    root = root / 'zapret'

  bat = root / 'service.bat'
  ps1 = root / 'utils' / 'test zapret.ps1'

  if not bat.exists():
    return False, 'service.bat not found'
  if not ps1.exists():
    return False, 'utils/test zapret.ps1 not found'

  ok_bat, msg_bat = _patch_service_bat(bat)
  if not ok_bat:
    return False, msg_bat

  ok_ps1, msg_ps1 = _patch_test_ps1(ps1)
  if not ok_ps1:
    return False, msg_ps1

  return True, msg_bat


def _read_text_guess(p: Path) -> tuple[str, str, str]:
  b = p.read_bytes()
  nl = '\r\n' if b'\r\n' in b else '\n'

  for enc in ('utf-8', 'utf-8-sig'):
    try:
      return b.decode(enc), enc, nl
    except Exception:
      pass

  for enc in ('cp866', 'cp1251'):
    try:
      return b.decode(enc), enc, nl
    except Exception:
      pass

  return b.decode('utf-8', errors='replace'), 'utf-8', nl


def _write_text(p: Path, s: str, enc: str) -> None:
  p.write_text(s, encoding=enc, errors='replace', newline='')


def _patch_service_bat(p: Path) -> tuple[bool, str]:
  s, enc, nl = _read_text_guess(p)

  if re.search(r'(?im)^\s*:run_tests_cli\b', s):
    return True, 'already patched'

  lines = s.splitlines(True)
  admin_if_re = re.compile(r'(?im)^\s*if\s+(?:/i\s+)?"%~?1"=="admin"\s*\(')
  admin_else_re = re.compile(r'(?im)^\s*\)\s*else\s*\(\s*$')
  load_lists_re = re.compile(r'(?im)^\s*call\s+:load_user_lists\b')

  admin_idx = -1
  for i, ln in enumerate(lines):
    if admin_if_re.search(ln):
      admin_idx = i
      break
  if admin_idx == -1:
    return False, 'cannot find admin if block'

  else_idx = -1
  for i in range(admin_idx + 1, len(lines)):
    if admin_else_re.search(lines[i]):
      else_idx = i
      break
  if else_idx == -1:
    return False, 'cannot find admin else block'

  insert_idx = admin_idx + 1
  for i in range(admin_idx + 1, else_idx):
    if load_lists_re.search(lines[i]):
      insert_idx = i + 1
      while insert_idx < else_idx and (lines[insert_idx].strip() == ''):
        insert_idx += 1
      break

  indent = '    '
  if 0 <= insert_idx < len(lines):
    m_indent = re.match(r'^(\s*)', lines[insert_idx])
    if m_indent and m_indent.group(1):
      indent = m_indent.group(1)

  injected = (
    indent + 'where powershell.exe >nul 2>&1 || (echo [ERROR] powershell.exe not found& exit /b 2)' + nl
    + nl
    + indent + 'if /i "%~2"=="run_tests_cli" (' + nl
    + indent + '    call :run_tests_cli "%~3" "%~4" "%~5" "%~6"' + nl
    + indent + '    exit /b %errorlevel%' + nl
    + indent + ')' + nl
    + nl
  )

  lines[insert_idx:insert_idx] = injected.splitlines(True)

  run_tests_hdr_re = re.compile(r'(?im)^\s*::\s*RUN\s+TESTS\b')
  hdr_idx = len(lines)
  for i, ln in enumerate(lines):
    if run_tests_hdr_re.search(ln):
      hdr_idx = i
      break

  label = (
    ':: RUN TESTS CLI =============================' + nl
    + ':run_tests_cli' + nl
    + 'set "TEST_TYPE=%~1"' + nl
    + 'set "RUN_MODE=%~2"' + nl
    + 'set "CONFIGS_CSV=%~3"' + nl
    + 'set "JSON_OUT=%~4"' + nl
    + 'if not defined TEST_TYPE set "TEST_TYPE=standard"' + nl
    + 'if not defined RUN_MODE set "RUN_MODE=all"' + nl
    + 'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0utils\\test zapret.ps1" -NonInteractive -TestType "%TEST_TYPE%" -RunMode "%RUN_MODE%" -ConfigsCsv "%CONFIGS_CSV%" -JsonOut "%JSON_OUT%"' + nl
    + 'exit /b %errorlevel%' + nl
    + nl
  )

  lines[hdr_idx:hdr_idx] = label.splitlines(True)
  _write_text(p, ''.join(lines), enc)
  return True, 'patched'


def _patch_test_ps1(p: Path) -> tuple[bool, str]:
  s, enc, nl = _read_text_guess(p)

  if 'NonInteractive' not in s:
    param_block = (
      'param(' + nl
      + '  [switch]$NonInteractive,' + nl
      + "  [ValidateSet('standard','dpi')][string]$TestType = ''," + nl
      + "  [ValidateSet('all','select')][string]$RunMode = ''," + nl
      + "  [string]$ConfigsCsv = ''," + nl
      + "  [string]$JsonOut = ''" + nl
      + ')' + nl + nl
    )
    s = param_block + s

  # Wrap ReadKey calls (avoid blocking in NonInteractive mode).
  s = re.sub(
    r'(?m)^(?P<indent>\s*)\[void\]\[System\.Console\]::ReadKey\(\$true\)\s*$',
    r'\g<indent>if (-not $NonInteractive) { [void][System.Console]::ReadKey($true) }',
    s,
  )

  if '# AUTO: non-interactive automation bridge' not in s:
    bridge = (
      '# AUTO: non-interactive automation bridge (used by hel-zapret-ui)' + nl
      + 'if ($NonInteractive) {' + nl
      + '    $script:__autoStage = 0' + nl + nl
      + '    function Get-AutoSelection {' + nl
      + '        param([array]$allFiles)' + nl
      + '        $names = @()' + nl
      + '        if ($ConfigsCsv) {' + nl
      + "            $names = $ConfigsCsv -split '[;,]+' | ForEach-Object { $_.Trim() } | Where-Object { $_ }" + nl
      + '        }' + nl
      + '        if (-not $names -or $names.Count -eq 0) { return "0" }' + nl
      + '        $map = @{}' + nl
      + '        for ($i = 0; $i -lt $allFiles.Count; $i++) {' + nl
      + '            $n = $allFiles[$i].Name' + nl
      + '            $base = $n' + nl
      + "            if ($base.ToLower().EndsWith('.bat')) { $base = $base.Substring(0, $base.Length - 4) }" + nl
      + '            $map[$n.ToLower()] = $i + 1' + nl
      + '            $map[$base.ToLower()] = $i + 1' + nl
      + '        }' + nl
      + '        $idxs = @()' + nl
      + '        foreach ($name in $names) {' + nl
      + '            $k = $name.ToLower()' + nl
      + "            if ($k.EndsWith('.bat')) { $k = $k.Substring(0, $k.Length - 4) }" + nl
      + '            if ($map.ContainsKey($k)) { $idxs += $map[$k]; continue }' + nl
      + '            if ($map.ContainsKey($k + ".bat")) { $idxs += $map[$k + ".bat"]; continue }' + nl
      + '        }' + nl
      + '        $idxs = $idxs | Sort-Object -Unique' + nl
      + '        if (-not $idxs -or $idxs.Count -eq 0) { return "0" }' + nl
      + '        return ($idxs -join ",")' + nl
      + '    }' + nl + nl
      + '    function global:Read-Host {' + nl
      + '        param([string]$Prompt)' + nl
      + '        $p = (($Prompt | Out-String).Trim()).ToLower()' + nl
      + "        if ($p -like '*enter 1 or 2*') {" + nl
      + '            if ($script:__autoStage -eq 0) {' + nl
      + '                $script:__autoStage = 1' + nl
      + "                if ($TestType -and $TestType.ToLower() -eq 'dpi') { return '2' }" + nl
      + "                return '1'" + nl
      + '            }' + nl
      + '            $script:__autoStage = 2' + nl
      + "            if ($RunMode -and $RunMode.ToLower() -eq 'select') { return '2' }" + nl
      + "            return '1'" + nl
      + '        }' + nl
      + "        if ($p -like '*enter numbers*') {" + nl
      + '            return (Get-AutoSelection -allFiles $batFiles)' + nl
      + '        }' + nl
      + "        return ''" + nl
      + '    }' + nl
      + '}' + nl + nl
    )

    m = re.search(r'function Add-OrSet[\s\S]+?\n\}', s)
    if m:
      insert_at = m.end()
      s = s[:insert_at] + nl + nl + bridge + s[insert_at:]
    else:
      s = bridge + s

  _write_text(p, s, enc)
  return True, 'patched'

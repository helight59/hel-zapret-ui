from __future__ import annotations

from PySide6.QtWidgets import QComboBox


def select_tag(combo: QComboBox, tag: str) -> None:
    value = (tag or '').strip()
    if not value:
        return
    for index in range(combo.count()):
        if str(combo.itemData(index) or '') == value:
            combo.setCurrentIndex(index)
            return


def effective_version(tab, tag: str) -> str:
    value = (tag or '').strip() or 'latest'
    if value == 'latest':
        return (tab._latest_resolved_version or '').strip()
    resolved = (tab._tag_to_version.get(value) or '').strip()
    if resolved:
        return resolved
    if value.lower().startswith('v'):
        return value[1:]
    return value


def update_version_hint(tab) -> None:
    tag = current_tag(tab) or (tab.cfg.zapret_version or 'latest')
    installed = tab._installed_version() or '—'
    tail = f' (текущая {installed})'
    if tag == 'latest':
        latest = tab._latest_resolved_version
        if latest:
            tab.lblVersionHint.setText(f'Будет установлена последняя версия: {latest}{tail}.')
        else:
            tab.lblVersionHint.setText(f'Будет установлена последняя версия (GitHub releases/latest){tail}.')
        return
    version = effective_version(tab, tag)
    tab.lblVersionHint.setText(f'Будет установлена версия: {version or tag}{tail}.')


def update_switch_button(tab) -> None:
    try:
        if tab._install_thread:
            tab.btnSwitchVersion.setEnabled(False)
            tab.btnSwitchVersion.setVisible(True)
            return
        tag = (current_tag(tab) or '').strip()
        if not tag:
            tab.btnSwitchVersion.setVisible(False)
            return
        installed = tab._installed_version()
        wanted = effective_version(tab, tag)
        same = bool(installed and wanted and installed.strip().lower() == wanted.strip().lower())
        tab.btnSwitchVersion.setVisible(not same)
        tab.btnSwitchVersion.setEnabled(not same)
    except Exception:
        try:
            tab.btnSwitchVersion.setVisible(True)
            tab.btnSwitchVersion.setEnabled(True)
        except Exception:
            pass


def current_tag(tab) -> str:
    return str(tab.cmbVersion.currentData() or '').strip()

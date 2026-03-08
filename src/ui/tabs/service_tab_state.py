from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Qt

from src.services.zapret.strategy_name import normalize_strategy_key
from src.ui.tabs.service_tab_view import game_filter_status_text, set_combo_value


def apply_state(tab, state) -> None:
    tab._state = state
    if not state:
        return

    install_mode = bool(state.show_install_zapret)
    tab.installPanel.setVisible(install_mode)
    tab.mainPanel.setVisible(not install_mode)

    tab.lblService.setText(state.service_state)
    tab.lblCapture.setText('RUNNING' if state.capture_running else 'OFF')
    tab.lblStrategy.setText(state.current_strategy or '-')
    tab.lblGameMode.setText(game_filter_status_text(state))
    tab.lblExternal.setVisible(state.external_present and bool(state.external_hint))
    tab.lblExternal.setText(state.external_hint)

    controls_enabled = (not install_mode) and (not state.external_present) and (not tab._tests_running)
    tab.swEnabled.setChecked(state.enabled)
    tab.swEnabled.setEnabled(controls_enabled)
    tab.toggleText.setText('Включено' if state.enabled else ('Выключено' if controls_enabled else 'Недоступно'))
    tab.enabledChanged.emit(state.enabled)

    if install_mode:
        if not state.zapret_present:
            tab.installHint.setText('zapret не найден. Нажми «Установить» — скачаем и настроим.')
        elif state.external_present:
            tab.installHint.setText('Обнаружена внешняя установка/запуск. Нажми «Установить», чтобы поставить версию приложения и не путаться с чужими папками.')
        elif state.service_state == 'NOT_INSTALLED':
            tab.installHint.setText('Служба zapret не установлена. Нажми «Установить» — поставим службу.')
        else:
            tab.installHint.setText('')
    else:
        tab.installHint.setText('')

    tab.combo.setVisible(state.show_strategy_select)
    tab.comboHint.setVisible(state.show_strategy_select)
    if state.show_strategy_select:
        if tab.combo.count() != len(state.strategies):
            tab.combo.blockSignals(True)
            tab.combo.clear()
            for strategy in state.strategies:
                tab.combo.addItem(strategy)
            tab.combo.blockSignals(False)
        tab.combo.setEnabled(controls_enabled)
        if tab._user_picked_strategy:
            want = tab._selected_strategy or ''
        else:
            want = (state.current_strategy or '').strip() or (state.selected_strategy or '').strip()
        if (not want) and state.strategies:
            want = state.strategies[0]
        if want:
            set_combo_value(tab.combo, want)
        tab._selected_strategy = tab.combo.currentText().strip()
        tab.comboHint.setText(f'Текущая: {state.current_strategy or "-"}')
    else:
        tab.combo.clear()
        tab.comboHint.setText('')

    update_apply_button(tab, controls_enabled)

    tab.btnRemove.setEnabled((not install_mode) and (not tab._tests_running))
    tab.btnInstallZapret.setEnabled((not tab._busy) and (not tab._tests_running))

    tab.cardWarn.setVisible(bool(state.warnings))
    tab.warnText.setText('\n'.join(state.warnings))
    tab.btnRemoveGoodbye.setVisible(state.show_remove_goodbyedpi)
    tab.btnRemoveGoodbye.setEnabled((not tab._busy) and (not tab._tests_running))

    emit_tray_state(tab)
    tab.stateRefreshed.emit()


def update_apply_button(tab, controls_enabled: bool) -> None:
    state = tab._state
    if not state:
        tab.btnApplyStrategy.setVisible(False)
        return
    selected = (tab._selected_strategy or tab.combo.currentText() or '').strip()
    current = (state.current_strategy or '').strip()
    base_visible = state.show_strategy_select and (not state.show_install_zapret) and (not state.external_present)
    can_apply = bool(selected) and (normalize_strategy_key(selected) != normalize_strategy_key(current))
    visible = bool(base_visible and can_apply)
    tab.btnApplyStrategy.setVisible(visible)
    if not visible:
        return
    tab.btnApplyStrategy.setEnabled(bool(controls_enabled))
    tab.btnApplyStrategy.setFocusPolicy(Qt.StrongFocus if controls_enabled else Qt.NoFocus)


def handle_settle_state(tab, state) -> None:
    tab._state = state
    pending = tab._pending_toggle
    if pending is None:
        return

    service_state = (state.service_state or '').strip().upper()
    capture = bool(state.capture_running)

    if pending:
        done = (service_state == 'RUNNING') or ((service_state == 'NOT_INSTALLED') and capture)
        progress = service_state == 'START_PENDING'
        if progress:
            set_busy_text(tab, 'Запускаем службу...')
    else:
        done = (service_state in ('STOPPED', 'NOT_INSTALLED')) and (not capture)
        progress = service_state == 'STOP_PENDING'
        if progress:
            set_busy_text(tab, 'Останавливаем службу...')

    if done:
        set_busy(tab, False, '')
        tab._pending_toggle = None
        apply_state(tab, state)
        if tab._settle_ok:
            tab.notifyRequested.emit('hel zapret ui', tab._settle_msg or 'Готово')
        return

    now = time.monotonic()
    if progress:
        tab._settle_deadline = max(tab._settle_deadline, now + 60.0)
    if now < tab._settle_deadline:
        QTimer.singleShot(800, tab.refresh)
        return

    set_busy(tab, False, '')
    tab._pending_toggle = None
    apply_state(tab, state)
    if tab._settle_ok:
        tail = 'Команда отправлена'
        if tab._settle_msg:
            tail = tab._settle_msg + ' (статус ещё не подтвердился)'
        tab.notifyRequested.emit('hel zapret ui', tail)


def handle_post_state(tab, state) -> None:
    title = (tab._post_title or '').strip()

    def install_done() -> bool:
        return bool(state.zapret_present) and (str(state.service_state or '').strip().upper() != 'NOT_INSTALLED')

    def remove_done() -> bool:
        return str(state.service_state or '').strip().upper() == 'NOT_INSTALLED'

    def apply_done() -> bool:
        selected = (tab._selected_strategy or '').strip()
        current = (state.current_strategy or '').strip()
        return bool(selected) and normalize_strategy_key(selected) == normalize_strategy_key(current)

    ok = True
    if title == 'Установка':
        ok = install_done()
    elif title == 'Удаление':
        ok = remove_done()
    elif title == 'Применить':
        ok = apply_done()

    if ok:
        tab._post_waiting = False
        set_busy(tab, False, '')
        apply_state(tab, state)
        if tab._post_notify:
            tab.notifyRequested.emit('hel zapret ui', tab._post_msg or 'Готово')
        return

    if time.monotonic() < tab._post_deadline:
        QTimer.singleShot(700, tab.refresh)
        return

    tab._post_waiting = False
    set_busy(tab, False, '')
    apply_state(tab, state)
    if tab._post_notify:
        tail = 'Команда отправлена'
        if tab._post_msg:
            tail = tab._post_msg + ' (статус ещё обновляется)'
        tab.notifyRequested.emit('hel zapret ui', tail)


def set_busy(tab, value: bool, text: str) -> None:
    tab._busy = bool(value)
    tab.busyStrip.set_busy(tab._busy)
    set_busy_text(tab, text or '')
    if tab._busy:
        tab._timer.stop()
    elif not tab._timer.isActive():
        tab._timer.start(2000)

    for widget in [
        tab.swEnabled,
        tab.combo,
        tab.btnApplyStrategy,
        tab.btnRemove,
        tab.btnInstallZapret,
        tab.btnRemoveGoodbye,
    ]:
        widget.setEnabled((not tab._busy) and (not tab._tests_running))
    emit_tray_state(tab)


def set_busy_text(tab, text: str) -> None:
    tab._busy_text = (text or '').strip()
    tab.appStatusChanged.emit(tab._busy_text if tab._busy else '')


def emit_tray_state(tab) -> None:
    try:
        tab.trayStateChanged.emit(tab.get_tray_model())
    except Exception:
        return

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMessageBox

from src.ui.adapters.fn_worker import FnWorker
from src.ui.tabs.service_tab_state import apply_state, emit_tray_state, handle_post_state, handle_settle_state, set_busy, set_busy_text
from src.ui.tabs.service_tab_view import set_combo_value


log = logging.getLogger('ui.service')


def toggle_requested(tab, on: bool) -> None:
    if tab._busy:
        if tab._pending_toggle is not None:
            tab.swEnabled.setChecked(tab._pending_toggle)
        elif tab._state:
            tab.swEnabled.setChecked(tab._state.enabled)
        return
    if (not tab._state) or tab._tests_running:
        return
    strategy = tab.combo.currentText().strip() if tab.combo.isVisible() else ''
    log.info('toggle requested on=%s strategy=%s', bool(on), strategy)
    tab._pending_toggle = on
    tab._settle_deadline = time.monotonic() + 60.0
    tab._settle_ok = False
    tab._settle_msg = ''
    set_busy(tab, True, 'Включаем zapret...' if on else 'Выключаем zapret...')
    tab.swEnabled.setChecked(on)
    tab.toggleText.setText('Включаем...' if on else 'Выключаем...')
    tab.enabledChanged.emit(on)
    run_action(tab, fn=lambda: tab.ctrl.toggle(on, strategy), title='Запуск' if on else 'Остановка', success_notify=True)


def install_zapret(tab) -> None:
    log.info('install zapret requested')
    if tab._tests_running:
        return
    set_busy(tab, True, 'Устанавливаем zapret...')
    run_action(tab, fn=tab.ctrl.install_zapret, title='Установка', success_notify=True)


def apply_strategy(tab) -> None:
    strategy = tab.combo.currentText().strip()
    log.info('apply strategy requested strategy=%s', strategy)
    if tab._tests_running:
        return
    if not strategy:
        QMessageBox.warning(tab, 'Стратегия', 'Выбери стратегию')
        return
    set_busy(tab, True, 'Применяем стратегию...')
    run_action(tab, fn=lambda: tab.ctrl.apply_strategy(strategy), title='Применить', success_notify=True)


def remove_services(tab) -> None:
    answer = QMessageBox.question(tab, 'Удаление', 'Удалить службы zapret?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if answer != QMessageBox.Yes:
        return
    log.info('remove services requested')
    set_busy(tab, True, 'Удаляем службы через service.bat...')
    run_action(tab, fn=tab.ctrl.remove_services, title='Удаление', success_notify=True)


def remove_goodbye(tab) -> None:
    log.info('remove goodbyedpi requested')
    set_busy(tab, True, 'Удаляем GoodbyeDPI...')
    run_action(tab, fn=tab.ctrl.remove_goodbyedpi, title='GoodbyeDPI', success_notify=True)


def run_action(tab, fn, title: str, success_notify: bool = False) -> None:
    if tab._action_thread:
        return
    log.info('action start title=%s', title)
    tab._action_thread = QThread()
    tab._action_worker = FnWorker(fn)
    tab._action_worker.moveToThread(tab._action_thread)
    tab._action_thread.started.connect(tab._action_worker.run)
    tab._action_worker.done.connect(lambda ok, msg: on_action_done(tab, ok, msg, title, success_notify))
    tab._action_thread.start()


def on_action_done(tab, ok: bool, msg: str, title: str, success_notify: bool) -> None:
    log.info('action done title=%s ok=%s msg=%s', title, bool(ok), msg)
    if tab._action_thread:
        tab._action_thread.quit()
        tab._action_thread.wait(2000)
    tab._action_thread = None
    tab._action_worker = None

    if tab._pending_toggle is not None:
        if not ok:
            set_busy(tab, False, '')
            tab._pending_toggle = None
            QMessageBox.critical(tab, title, msg or 'Ошибка')
            tab.refresh()
            return
        tab._settle_ok = True
        tab._settle_msg = msg or ('включено' if tab._pending_toggle else 'выключено')
        tab._settle_deadline = time.monotonic() + 60.0
        set_busy_text(tab, 'Проверяем статус...')
        tab.refresh()
        return

    if not ok:
        set_busy(tab, False, '')
        QMessageBox.critical(tab, title, msg or 'Ошибка')
        tab.refresh()
        return

    if title in {'Установка', 'Удаление', 'Применить'}:
        tab._post_waiting = True
        tab._post_deadline = time.monotonic() + 25.0
        tab._post_title = title
        tab._post_msg = msg or 'Готово'
        tab._post_notify = bool(success_notify)
        set_busy_text(tab, 'Проверяем статус...')
        tab.refresh()
        return

    set_busy(tab, False, '')
    if success_notify:
        tab.notifyRequested.emit('hel zapret ui', msg or 'Готово')
    tab.refresh()

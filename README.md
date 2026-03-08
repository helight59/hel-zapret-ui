# Hel zapret UI

[![Latest release](https://img.shields.io/github/v/release/helight59/hel-zapret-ui?label=release)](https://github.com/helight59/hel-zapret-ui/releases)
[![Windows](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011-0078D6)](https://github.com/helight59/hel-zapret-ui/releases)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

Portable GUI-приложение для Windows на базе **[zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube)**, которое упрощает работу с `zapret` без ручного ковыряния `.bat`-файлов, PowerShell-меню и внутренних настроек.

Latest release:
https://github.com/helight59/hel-zapret-ui/releases

## ✨ Что умеет

- установка и обновление `zapret`;
- запуск и остановка службы;
- выбор стратегии и игрового режима;
- редактирование пользовательских списков;
- запуск тестов соединения;
- сохранение истории запусков;
- генерация PDF-отчётов;
- работа из системного трея.

> Приложение рассчитано на обычного пользователя: всё основное доступно через интерфейс, без ручной работы с файлами и командами.

---

## 👤 Для кого это

Если тебе нужен `zapret`, но не хочется каждый раз:

- искать нужный `.bat`;
- помнить порядок запуска;
- руками править списки;
- разбираться, какая стратегия реально сработала;
- собирать логи по разным папкам,

то **Hel zapret UI** берёт это на себя.

---

## 🚀 Быстрый старт

1. Скачай [последний релиз](https://github.com/helight59/hel-zapret-ui/releases).
2. Распакуй архив в любую папку.
3. Запусти `hel_zapret_ui.exe`.
4. Подтверди UAC-запрос администратора.
5. Нажми **Установить zapret**, если `zapret` ещё не скачан.
6. Выбери стратегию и включи `zapret`.

---

## 💬 Обратная связь

Есть **идеи** или **пожелания** по новому или существующему функционалу? А так же, если нашел баг.
Пиши в [Issues](https://github.com/helight59/hel-zapret-ui/issues) — постараюсь как можно быстрее посмотреть.

---

## 📦 Основные возможности

### Главная

- показывает текущий статус `zapret`;
- отображает активную стратегию;
- позволяет включить, выключить, установить или перезапустить `zapret`;
- применяет смену стратегии без ручного запуска `.bat`-файлов.

### Настройки → zapret

- переключение игрового режима;
- выбор режима применения игрового фильтра;
- сохранение изменений с перезапуском, если это требуется.

### Настройки → списки

- отдельные компактные таблицы для пользовательских списков;
- кнопки добавления и удаления;
- сохранение списков в конфиге приложения.

### Тесты

- запуск тестов по выбранным стратегиям;
- отслеживание прогресса;
- история запусков;
- PDF-отчёты по результатам.

---

## ⚙️ Требования

- Windows 10 / 11
- права администратора
- Python 3.11+ — только для локального запуска проекта и сборки

> Для обычного использования Python устанавливать не нужно: приложение работает как portable-утилита.

---

## 🛠 Локальный запуск проекта

### 1. Создать виртуальное окружение

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
```

### 2. Запустить приложение

```bat
python -m src.main
```

Если приложение стартует без прав администратора, оно само запросит повышение прав.

---

## 🧱 Локальная сборка

### Установка зависимостей для сборки

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Сборка

```bat
:: onedir
pyinstaller -y hel_zapret_ui.spec

:: onefile
pyinstaller -y hel_zapret_ui_onefile.spec
```

### Результат

- `dist\hel_zapret_ui\` — папочная сборка `onedir`;
- `dist\hel_zapret_ui.exe` — одиночный exe `onefile`.

---

## 📁 Где хранятся данные приложения

По умолчанию приложение использует каталог:

```text
%LOCALAPPDATA%\hel_zapret_ui
```

---

## 📄 License

MIT

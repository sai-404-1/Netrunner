# computer/module

Встроенные («builtin») модули NetRunner и низкоуровневые исполнители SSH/SCP.
Эти модули собираются классом `Modules` (см. `__init__.py`) и регистрируются в
`ModuleRegistry`. Новые модули нужно прописывать в `__init__.py`.

## Низкоуровневые исполнители (вызываются фасадом `Computer`)

### `executor_ssh.py` — выполнение команд по SSH
- `_ssh_common_options()` — общие опции SSH со строгой проверкой ключа хоста
  (читает политику из `config.py`: `StrictHostKeyChecking`, known-hosts и т.п.).
- `_build_ssh_cmd(host, port, command, key_path)` — собирает список аргументов `ssh`.
- `_format_result(host, returncode, stdout, stderr)` — форматирует результат/ошибку.
- `main(host, port, command, key_path)` — синхронный запуск команды.
- `async async_main(host, port, command, key_path)` — асинхронный запуск.

### `executor_scp.py` — копирование файлов по SCP
- `_build_scp_cmd(host, port, path_from, path_to)` — собирает команду `scp`.
- `main(host, port, path_from, path_to)` — выполняет копирование.

### `local_executor.py` — выполнение команд локально
- `main(command)` — запустить команду на самом сервере NetRunner.
- `class LocalComputer` — локальный аналог `Computer` (`local_executor(command)`).

## Базовый класс модулей

### `base_module.py`
- `class CommandModule` — база для простых SSH-команд с подстановкой `$переменных`.
  Достаточно задать `slug`, `title`, `description`, `command`, `schema`; класс сам
  предоставляет `run_for_host` и экранирует значения через `shlex.quote`.
  - `exec()` — запуск в TUI-меню.
  - `_build_command(kwargs)` — подстановка переменных в шаблон команды.
  - `async run_for_host(context, host)` — поштучное асинхронное исполнение для task-runner'а.

## Реестр

### `__init__.py`
- `class _Modules` — коллекция встроенных модулей: `add_update`, `call`, `read`, `get_all`.

## Прикладные встроенные модули

### `apt_package_manager.py` — управление пакетами APT (кастомный парсинг)
- `class AptResult` — структура результата по одному хосту.
- `class UserModule`:
  - `_parse_packages(raw)` — разбор списка пакетов из ввода.
  - `_build_command(action, packages, sudo_password)` — безопасная сборка удалённой команды.
  - `async _run_apt(...)` — выполнение apt по SSH (stdout/stderr/returncode).
  - `_detect_changed/_detect_failed(...)` — эвристики по выводу apt.
  - `_format_output(result)` — форматирование отчёта.
  - `run/async run_async/async run_for_host` — синхронный/асинхронный и поштучный запуск.

### `availability_check.py` — проверка доступности хостов (кастомный парсинг)
- `class UserModule`: `exec`, `_parse_ping_result`, `run`, `async run_for_host`.

### `file_distribute.py` — массовая рассылка файлов (только админ, монолитный)
- `class UserModule` (slug `file_distribute`, `admin_only=True`, `max_parallel` из конфига):
  копирует выбранные загруженные файлы на хост/группу по scp (безопасный билдер с ключом
  хоста), по файлам — по очереди, по хостам — с лимитом параллелизма. Методы:
  `run_for_host`, `_resolve_files`/`_resolve_key_path` (через `context.db`), `_scp_cmd`,
  `_run_cmd`. Файлы берутся из таблицы `uploaded_files` (эндпоинты `/api/uploads*`).

### `inventory_collect.py` — сбор инвентаризации (кастомный парсинг)
- `class UserModule` — читает hostname, ОС, ядро, RAM, диски, пользователя, число
  пакетов (для каждого показателя есть sync- и async-версия `_read_*`), формирует
  `inventory_item`. Методы: `run`, `async run_for_host`, набор `_read_*`/`_clean_*`.

### `agent_provision.py` — установка/переустановка endpoint-агента
- `class UserModule` (slug `agent_provision`): провижинит на хосте выделенного
  сервисного пользователя **`netrunner-svc`** (без пароля), даёт ему root через
  `sudoers.d` (NOPASSWD: ALL) и ставит endpoint-агент. Дальше NetRunner исполняет команды
  под `netrunner-svc` (его per-host ключом), а не под первичным пользователем.
  Повторный запуск на уже провиженном хосте — **переустановка**: не ротирует ключ/токен,
  чинит `sudoers` (через первичного пользователя на машинах старой провизии, где
  netrunner-svc есть, а sudoers-правила ещё нет), обновляет файлы и юнит агента.
  В `config.json` агента пишется **расшифрованный** токен (`AgentService.token_for_config`;
  до 2026-09-17 при переустановке писался зашифрованный, и сервер отвергал агента с 4003).
  Корень сервера из Администрирования (`agent_ca_cert`) кладётся в `/etc/netrunner-agent/ca.crt`;
  для адреса `wss://` без корня установка не начинается. В конце служба **перезапускается**
  (`enable --now` не применял новый код/адрес к уже работающей службе). Нет `websockets`
  после apt/`apt-get update`/pip — установка завершается `[ERROR]`.

### `rotate_password.py` — смена пароля пользователя на хосте
- `class UserModule` (slug `rotate_password`, `admin_only`): генерирует пароль на сервере
  (`secrets.token_urlsafe`, длина 16–32) и меняет его через `sudo chpasswd`. Пароль идёт
  на хост только через stdin (не виден в `ps`) и не попадает в вывод задачи, историю и
  события. Подключение — под первичным пользователем (`to_computer_bootstrap`), sudo
  праймится сохранённым паролем хоста, как в `agent_provision`.
- Пользователь не указан → первичный пользователь хоста; новый пароль сразу шифруется
  и сохраняется в карточке. Указан другой → пароль нигде не сохраняется (в выводе
  предупреждение). Ошибка на хосте → карточка не трогается. Событие `password_rotated`
  в журнал хоста (только имя пользователя).
- Проверено 2026-09-17 на Linux Mint (`.3.7`): sudo по паролю, другой пользователь,
  хост без сохранённого пароля, несуществующий пользователь — 16/16.

### `get_update.py` — обновление системы
- `main()`, `get_update(update)`, `class UserModule(exec)`.

### Утилитарные/TUI-модули
- `ping.py` — `main(ip, port, command)`: ICMP/команда проверки.
- `hard_drive_check.py` — `main(host, port)`: проверка диска.
- `folder_swipe.py` — `main(host, port, dir, key_path)`: ограничение доступа к папке.
- `installer.py` — `load_hosts`, `build_command`, `run_install`, `main`: массовая установка.
- `input.py` — клавиатурный ввод и отрисовка TUI-меню (`read_key`, `render`, `main` и др.).
- `termdraw.py` — низкоуровневая отрисовка в терминале (`move_to`, `write_at`,
  `clear_screen`, `hide_cursor`/`show_cursor` и т.п.).

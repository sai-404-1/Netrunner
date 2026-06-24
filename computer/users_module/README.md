# computer/users_module

Здесь располагаются комплектные пользовательские модули NetRunner. Собираются
классом `UserModules` (см. `__init__.py`) и регистрируются в `ModuleRegistry`.
Это примеры и готовые инструменты, которые можно копировать как шаблон для своих
модулей. Новые модули нужно прописывать в `__init__.py`.

Модуль реализует **один из двух интерфейсов исполнения**:
- `async run_for_host(context, host, **kwargs)` — предпочтительный, исполняется
  по хостам конкурентно;
- `run(context, targets, **kwargs)` — синхронный fallback (в отдельном потоке).
Многие модули также имеют `exec()` — точку входа для интерактивного TUI-меню.

## Файлы

### `__init__.py`
- `class _UserModules` — коллекция пользовательских модулей: `add_update`, `call`,
  `read`, `get_all`.

### Демонстрационные / шаблонные
- `example.py` — минимальный пример модуля (`UserModule.exec`).
- `hello_one.py`, `hello_two.py` — простейшие демо-модули.
- `other_modules.py` — заготовка/заглушка.

### SSH и команды
- `ssh.py` — выполнение произвольной команды по SSH. Поддерживает task-runner:
  `prompt_args`, `run`, `async run_for_host(context, host, command)`.
- `blacklist.py` — `main(host)` + `UserModule.exec`: блокировка/чёрный список.

### Инвентаризация и мониторинг
- `host_info.py` — сбор сведений о хосте (`exec`, `_pick_targets`).
- `process_top.py` — топ процессов (`exec`, `_pick_host`).
- `fs_log_monitor.py` — демо-модуль мониторинга файловой системы: использование диска
  и inode, крупнейшие каталоги/файлы, сводка точек монтирования (`run`, набор `_*`).
- `ssd_test.py` — тест диска с потоками start/status/tail/log/summary
  (`_start_flow`, `_status_flow`, `_build_start_command` и др.).

### Обслуживание и управление
- `apt_maintenance.py` — обслуживание пакетов APT (`exec`, `_pick_targets`).
- `service_manager.py` — управление systemd-сервисами (`exec`, `_pick_host`).
- `power_actions.py` — питание (reboot/shutdown) (`exec`, `_pick_host`).
- `ping_check.py` — проверка доступности (`exec`).

### Прочее
- `notification.py` — `main(title, message)`: отправка уведомления.

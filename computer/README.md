# computer

Слой удалённого исполнения NetRunner. Здесь живёт фасад `Computer`, через который
модули выполняют команды на хостах по SSH/SCP, а также два набора модулей.

## Файлы

### `__init__.py` — фасад `Computer`
Тонкая обёртка, которой пользуются модули (`HostService.to_computer(host)` создаёт
её под конкретный хост с его SSH-ключом).
- `Computer(host, port, key_path)` — конструктор: `host` в формате `user@address`.
- `executor_ssh(command)` — синхронно выполнить команду по SSH, вернуть текст.
- `async async_executor_ssh(command)` — асинхронная версия (используется в task-runner'е).
- `executor_scp(path_from, path_to)` — копирование файлов по SCP.
- `hard_drive_check()` — проверка диска удалённой машины.
- `ping()` — проверка доступности.
- `folder_swipe(dir)` — запрещает доступ к папке через смену владельца (`chown -R`).

## Подпапки
- `module/` — встроенные («builtin») модули и низкоуровневые исполнители SSH/SCP.
  См. `module/README.md`.
- `users_module/` — комплектные пользовательские модули. См. `users_module/README.md`.

> После добавления новых модулей пропишите их в соответствующем `__init__.py`
> (`module/__init__.py` или `users_module/__init__.py`), иначе реестр их не подхватит.

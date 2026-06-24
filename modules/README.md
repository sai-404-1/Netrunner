# modules

Каталог модулей, загруженных с диска (третий источник модулей помимо `computer/module/`
и `computer/users_module/`). `.py`-файлы, попавшие сюда, подхватываются загрузчиком
`_load_user_modules_from_disk` и регистрируются в `ModuleRegistry`.

## Требования к модулю
- Файл должен экспортировать класс с именем **`UserModule`**.
- Модуль реализует один из интерфейсов исполнения: `async run_for_host(context, host, **kwargs)`
  (предпочтительно) или `run(context, targets, **kwargs)`.
- Для простых «выполнить SSH-команду с подстановкой `$переменных`» удобно наследовать
  `CommandModule` из `computer/module/base_module.py`.

## В Docker
Загрузка через API пишет файлы в `/app/modules` (том `netrunner_modules`); локально
загрузчик читает `/app/modules`, затем откатывается на `modules/`.

## Файлы
- `notify_example.py` — пример модуля на базе `CommandModule` (`class UserModule(CommandModule)`).

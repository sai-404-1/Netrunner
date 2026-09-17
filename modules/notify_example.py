from computer.module.base_module import CommandModule


class UserModule(CommandModule):
    slug = "send_notification"
    admin_only = False
    supports_task_runner = True
    # Пользователь для notify-send определяется по активной X11-сессии, а не
    # запрашивается полем формы: имя SSH-пользователя (rmk и т.п.) — это НЕ
    # пользователь графической сессии, а реальный логин на разных машинах
    # одного кабинета отличается (student/cneltyn/studen — опечатки/раскладка
    # при заводе учётки). Раньше поле "Пользователь" по умолчанию было "rmk" —
    # notify-send тихо не показывался никому, т.к. rmk не залогинен в графику.
    command = """
SESSDATA=""
for s in $(loginctl list-sessions --no-legend 2>/dev/null | awk '{print $1}'); do
  eval "$(loginctl show-session "$s" -p Class -p Type -p Display -p Name -p State 2>/dev/null)"
  if [ "$Class" = "user" ] && [ "$Type" = "x11" ] && [ "$State" = "active" ] && [ -n "$Display" ]; then
    SESSDATA="$Name $Display"
    break
  fi
done
if [ -z "$SESSDATA" ]; then
  echo "[ERROR] Нет активной графической сессии — некому показать уведомление"
  exit 0
fi
set -- $SESSDATA
NR_USER="$1"; NR_DISPLAY="$2"
UID_N=$(id -u "$NR_USER")
if ! sudo -u "$NR_USER" env DISPLAY="$NR_DISPLAY" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$UID_N/bus" \
     notify-send --urgency=$level --expire-time=$duration $theme $message; then
  echo "[ERROR] Не удалось показать уведомление (нет notify-send или сессия не приняла)"
  exit 0
fi
echo "Уведомление показано пользователю $NR_USER"
""".strip()

    def __init__(self):
        self.title = "Отправка уведомления"
        self.description = (
            "Показывает desktop-уведомление на рабочем столе — пользователь сессии "
            "определяется автоматически (loginctl), поле вводить не нужно. Полезно "
            "для объявлений всему кабинету разом (цель — группа): «5 минут до звонка», "
            "«тишина», «поднимите руку, кто закончил»."
        )

    schema = {
        "placeholders": [
            ["theme",    "Тема уведомления", "NetRunner",         "text"],
            ["message",  "Сообщение",        "Привет! Это тест.", "textarea"],
            ["level",    "Уровень важности", "normal",            "select",
             [["low", "Низкий"], ["normal", "Обычный"], ["critical", "Критический (не исчезает само)"]]],
            ["duration", "Показывать, мс",   "8000",              "select",
             [["3000", "3 сек"], ["8000", "8 сек"], ["15000", "15 сек"], ["30000", "30 сек"]]],
        ]
    }

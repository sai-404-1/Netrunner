from computer.module.base_module import CommandModule


class UserModule(CommandModule):
    slug = "send_notification"
    command = "sudo -u $user DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u $user)/bus notify-send --urgency=$level \"$theme\" \"$message\""

    def __init__(self):
        self.title = "Отправка уведомления"
        self.description = "Отправляет desktop-уведомление на удалённый хост указанному пользователю через notify-send."

    schema = {
        "placeholders": [
            ["user",    "Пользователь",       "rmk",                "text"],
            ["theme",   "Тема уведомления",   "NetRunner",        "text"],
            ["message", "Сообщение",           "Привет! Это тест.",  "textarea"],
            ["level",   "Уровень важности",    "normal",             "select",
             [["low", "Низкий"], ["normal", "Обычный"], ["critical", "Критический"]]],
        ]
    }

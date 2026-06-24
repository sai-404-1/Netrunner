from computer.module.base_module import CommandModule


class UserModule(CommandModule):
    slug = "send_notification"
    command = "notify-send --urgency=$level $theme $message"

    def __init__(self):
        self.title = "Отправка уведомления"
        self.description = "Отправляет desktop-уведомление на удалённый хост через notify-send."

    schema = {
        "placeholders": [
            ["theme",   "Тема уведомления",   "Приветствие",        "text"],
            ["message", "Сообщение",           "Привет! Это тест.",  "textarea"],
            ["level",   "Уровень важности",    "normal",             "radio",
             [["low", "Низкий"], ["normal", "Обычный"], ["critical", "Критический"]]],
        ]
    }

# frontend/lib

Вспомогательные модули фронтенда: доступ к API, аутентификация, утилиты.

## Файлы

### `api.ts` — доступ к API (сервер + клиент)
Серверные функции (`"use server"`) ходят на бэкенд напрямую с Bearer-токеном из куки;
клиентские — на `/api/python/*` с `credentials: "include"`.
- `getToken()` — прочитать токен из куки.
- `apiGet(path)` / `apiPost(path, body)` — серверные запросы.
- `apiGetClient(path)` / `apiPostClient(path, body)` — клиентские запросы.
- `fetchWithAuthClient(path, options)` — низкоуровневый fetch с авторизацией.
- `fetchReportFile(fileName)` — скачивание файла отчёта.

### `api-client.ts` — клиентские запросы (для `"use client"` компонентов)
- `apiGetClient(path)`, `apiPostClient(path, body)`, `fetchWithAuthClient(path, options)`,
  `fetchReportFile(fileName)` — те же операции, но строго на стороне браузера через
  `/api/python/*` с куки.

### `auth.ts` — работа с токеном
- `getToken()` — получить токен.
- `setToken(token)` — сохранить httpOnly-куки.
- `deleteToken()` — удалить токен (логаут).

### `utils.ts` — утилиты
- `formatDate(iso)` — форматирование даты для UI.
- `toLocalISO(date)` — дата в локальный ISO.
- `escapeHtml(value)` — экранирование HTML.
- `readFileAsBase64(file)` — чтение файла в base64 (загрузка ключей/модулей).

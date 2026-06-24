# frontend

Основной фронтенд NetRunner на Next.js (App Router) + TypeScript + Tailwind. В проде
запускается в режиме `output: "standalone"` (`node server.js`) и проксирует API на
Python-бэкенд под `/api/python/*` (rewrite в `next.config.js` срезает этот префикс).
Контейнер отдаёт фронтенд на порту 3000 (compose маппит `3001:3000`).

## Конфигурация (корень `frontend/`)
- `next.config.js` — `output: standalone` и rewrite `/api/python/* → бэкенд`.
- `middleware.ts` — редиректит неаутентифицированные запросы на `/login`.
- `tsconfig.json` — алиас `@/*`, настройки TypeScript.
- `tailwind.config.js`, `postcss.config.js` — стили.
- `package.json` — скрипты `dev`/`build`/`start`/`lint` и зависимости.

## Подпапки
- `app/` — страницы (App Router) и серверные роуты логина/логаута. См. `app/README.md`.
- `components/` — переиспользуемые React-компоненты. См. `components/README.md`.
- `lib/` — клиент API, аутентификация, утилиты. См. `lib/README.md`.

## Запуск (dev)
```bash
cd frontend && npm install && npm run dev   # http://localhost:3000
```

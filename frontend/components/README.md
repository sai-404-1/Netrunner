# frontend/components

Переиспользуемые React-компоненты панели NetRunner.

## Компоненты

- `Layout.tsx` — основной layout панели (боковое меню навигации, шапка). В сайдбаре —
  ссылка «Профиль» (вместо кнопки выхода); пункты «Статус сервера», «Отчёты»,
  «Обновление» убраны (свёрнуты в другие страницы).
- `ClientLayout.tsx` — клиентская обёртка layout'а (редирект на /login, гейт ролей).
- `Providers.tsx` — корневые провайдеры: `ThemeProvider` → `AuthProvider` → `ToastProvider`.
- `ThemeProvider.tsx` — контекст темы: `ThemeProvider` + хук `useTheme()` (класс `.dark`
  на `<html>` + сохранение в `localStorage`; тема — только по классу, без авто-детекта ОС).
- `AuthProvider.tsx` — контекст аутентификации: `AuthProvider` + хук `useAuth()`
  (`user`, роль, суперпользователь; `login`, `logout`, `refresh` — перечитать `/api/me`).
- `Toast.tsx` — всплывающие уведомления: `ToastProvider` + хук `useToast()`.
- `Modal.tsx` — модальные окна: `Modal` (универсальное) и `OutputModal` (показ вывода задач).
- `DataTable.tsx` — обобщённая таблица `DataTable<T>` с колонками и кастомным рендером ячеек.
- `Badge.tsx` — бейджи статусов: `StatusBadge`, `BooleanBadge`, `LabelBadge`.
- `HostBoardView.tsx` — режим «Доска» на странице хостов: `HostBoardView` (управление досками).
- `BoardCanvas.tsx` — холст доски: `BoardCanvas` (drag-and-drop; канва и палитра адаптированы
  под тёмную тему через `useTheme`).
- `FileManager.tsx` — менеджер файлов на странице запуска модуля `file_distribute`:
  загрузка (с прогресс-баром), список с выбором/скачиванием/удалением (`/api/uploads*`).
- `ReportsView.tsx` — содержимое раздела «Отчёты» (используется во вкладке «Отчёты»
  страницы «История» и на маршруте `/reports`): экспорт + список отчётов.
- `UpdatePanel.tsx` — раздел «Обновление» в админке: конфиг git-репо/токена/интервала,
  статус монитора, «Проверить/Применить», история инцидентов супервизора.

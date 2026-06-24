# frontend/components

Переиспользуемые React-компоненты панели NetRunner.

## Компоненты

- `Layout.tsx` — основной layout панели (боковое меню навигации, шапка).
- `ClientLayout.tsx` — клиентская обёртка layout'а.
- `Providers.tsx` — корневые провайдеры (контексты приложения).
- `AuthProvider.tsx` — контекст аутентификации: `AuthProvider` + хук `useAuth()`
  (даёт текущего `user`, роль, флаг суперпользователя).
- `Toast.tsx` — всплывающие уведомления: `ToastProvider` + хук `useToast()`.
- `Modal.tsx` — модальные окна: `Modal` (универсальное) и `OutputModal` (показ вывода задач).
- `DataTable.tsx` — обобщённая таблица `DataTable<T>` с колонками и кастомным рендером ячеек.
- `Badge.tsx` — бейджи статусов: `StatusBadge`, `BooleanBadge`, `LabelBadge`.
- `HostBoardView.tsx` — режим «Доска» на странице хостов: `HostBoardView` (управление досками).
- `BoardCanvas.tsx` — холст доски: `BoardCanvas` (drag-and-drop размещение хостов, сохранение layout).

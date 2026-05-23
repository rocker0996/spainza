# Документация: Система доступа к списку пользователей

## Обзор

Страница `clients.html` отображает список пользователей в зависимости от роли текущего пользователя. Доступ к странице имеют только пользователи с ролями: **management**, **admin**, **moderator** и **manager**.

## Правила доступа по ролям

### 1. Management (Управление) - уровень 1
- **Доступ**: Видит всех зарегистрированных пользователей
- **Описание**: Полный доступ ко всем пользователям системы
- **API**: Возвращает результат `get_all_users()`

### 2. Admin (Админ) - уровень 2
- **Доступ**: Видит всех пользователей с уровнем доступа ниже чем админ (уровень >= 2)
- **Описание**: Видит админов, модераторов, менеджеров и всех клиентов
- **API**: Возвращает результат `get_users_by_role_level(db, "2")`

### 3. Moderator (Модератор) - уровень 3
- **Доступ**: Видит только менеджеров и пользователей ниже (уровень >= 4)
- **Описание**: Видит менеджеров, digital nomad, golden visa и обычных пользователей
- **API**: Возвращает результат `get_users_by_role_level(db, "4")`

### 4. Manager (Менеджер) - уровень 4
- **Доступ**: Видит только клиентов, закрепленных за ним
- **Описание**: Видит только тех пользователей, которые назначены ему через таблицу `manager_clients`
- **API**: Возвращает результат `get_clients_for_manager(db, manager_id)`

### 5. Остальные роли (Digital Nomad, Golden Visa, User)
- **Доступ**: НЕТ доступа к странице `clients.html`
- **Поведение**: При попытке доступа получают ошибку 403 и перенаправляются на dashboard

## API Endpoint

### GET `/api/users`

Получение списка пользователей с учетом прав доступа текущего пользователя.

**Заголовки запроса:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Успешный ответ (200):**
```json
{
  "success": true,
  "users": [
    {
      "id": 1,
      "name": "Иван Иванов",
      "email": "ivan@example.com",
      "avatar": "https://...",
      "phone": "+7 999 123-45-67",
      "created_at": "2023-10-15T10:30:00",
      "role": {
        "key": "user",
        "level": "6",
        "name_ru": "Пользователь"
      }
    }
  ],
  "viewer_role": {
    "key": "admin",
    "level": "2",
    "name_ru": "Админ"
  }
}
```

**Ошибки:**
- `401 Unauthorized` - Отсутствует или невалидный токен
- `403 Forbidden` - Пользователь не имеет доступа к списку пользователей
- `404 Not Found` - Пользователь не найден

## База данных

### Таблица `manager_clients`

Связывает менеджеров с их клиентами.

**Структура:**
```sql
CREATE TABLE manager_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_id INTEGER NOT NULL,
    client_id INTEGER NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(manager_id, client_id)
)
```

**Функции для работы с таблицей:**

1. `create_manager_clients_table(connection)` - Создание таблицы
2. `assign_client_to_manager(connection, manager_id, client_id)` - Назначение клиента менеджеру
3. `get_clients_for_manager(connection, manager_id)` - Получение всех клиентов менеджера

## Frontend

### Файлы

1. **`frontend/lk/clients.html`** - HTML страница со списком пользователей
2. **`frontend/js/clients.js`** - JavaScript для загрузки и отображения пользователей
3. **`frontend/js/lk.js`** - Обновлен для скрытия ссылки на clients.html для пользователей без доступа

### Основные функции в `clients.js`

- `loadUsers()` - Загрузка пользователей с API
- `renderUsersTable(users)` - Отрисовка таблицы пользователей
- `updateStats(users, viewerRole)` - Обновление статистики
- `checkAccess(userRole)` - Проверка доступа к странице
- `getRoleBadgeColor(roleKey)` - Получение цвета бейджа роли
- `getUserInitials(name, email)` - Получение инициалов пользователя
- `formatDate(dateString)` - Форматирование даты

### Навигация

В `lk.js` добавлена проверка доступа к странице clients.html:

```javascript
const canAccessClients = ["management", "admin", "moderator", "manager"].includes(roleKey);

document.querySelectorAll('a[href="./clients.html"]').forEach((link) => {
  if (!canAccessClients) {
    link.classList.add("hidden");
  }
});
```

## Backend

### Новые функции в `backend/models/user.py`

1. **`create_manager_clients_table(connection)`**
   - Создает таблицу связей менеджер-клиент

2. **`assign_client_to_manager(connection, manager_id, client_id)`**
   - Назначает клиента менеджеру
   - Возвращает `True` при успехе, `False` при дубликате

3. **`get_clients_for_manager(connection, manager_id)`**
   - Возвращает список клиентов, назначенных менеджеру

4. **`get_users_by_role_level(connection, max_level)`**
   - Возвращает пользователей с уровнем >= max_level
   - Используется для фильтрации по ролям

5. **`get_all_users(connection)`**
   - Возвращает всех зарегистрированных пользователей

### Новый endpoint в `backend/routes/lk.py`

**`GET /api/users`** - Получение списка пользователей с фильтрацией по правам доступа

## Примеры использования

### Назначение клиента менеджеру

```python
from models.user import assign_client_to_manager
from utils.db import get_db_connection

db = get_db_connection()
success = assign_client_to_manager(db, manager_id=5, client_id=10)
if success:
    print("Клиент успешно назначен менеджеру")
else:
    print("Клиент уже назначен этому менеджеру")
db.close()
```

### Получение клиентов менеджера

```python
from models.user import get_clients_for_manager
from utils.db import get_db_connection

db = get_db_connection()
clients = get_clients_for_manager(db, manager_id=5)
for client in clients:
    print(f"Клиент: {client['name']} ({client['email']})")
db.close()
```

## Тестирование

### Проверка доступа

1. Войдите как пользователь с ролью **management** - должны видеть всех пользователей
2. Войдите как **admin** - должны видеть всех кроме management
3. Войдите как **moderator** - должны видеть только менеджеров и клиентов
4. Войдите как **manager** - должны видеть только назначенных клиентов
5. Войдите как **user** - не должны видеть ссылку на clients.html, при прямом доступе - ошибка 403

### Проверка UI

1. Таблица должна корректно отображать:
   - ID пользователя
   - Имя и email
   - Аватар или инициалы
   - Роль с цветным бейджем
   - Телефон
   - Дату регистрации

2. При отсутствии пользователей должно показываться сообщение "Пользователи не найдены"

3. Счетчик "Всего пользователей" должен обновляться корректно

## Безопасность

1. **Аутентификация**: Все запросы требуют валидный JWT токен
2. **Авторизация**: Проверка прав доступа на уровне API
3. **Фильтрация данных**: Каждая роль видит только разрешенных пользователей
4. **SQL Injection**: Используются параметризованные запросы
5. **Cascade Delete**: При удалении пользователя автоматически удаляются связи в manager_clients

## Будущие улучшения

1. Добавить пагинацию для больших списков пользователей
2. Добавить фильтры по ролям и статусам
3. Добавить поиск по имени/email
4. Добавить модальное окно с детальной информацией о пользователе
5. Добавить возможность назначения/снятия клиентов для менеджеров
6. Добавить экспорт списка пользователей в CSV/Excel

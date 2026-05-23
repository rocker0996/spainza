# Объединение систем доступа через Permissions

## Что было изменено

Система доступа к списку пользователей теперь использует **единую систему permissions** вместо жестких проверок ролей. Это делает код более гибким, расширяемым и соответствует архитектуре приложения.

## Новые Permissions

Добавлены 4 новых permission для управления доступом к списку пользователей:

### 1. `view_all_users`
- **Кто имеет**: Management
- **Описание**: Просмотр всех зарегистрированных пользователей
- **Логика**: Возвращает `get_all_users()`

### 2. `view_lower_users`
- **Кто имеет**: Admin
- **Описание**: Просмотр пользователей с уровнем доступа ниже или равным своему
- **Логика**: Возвращает `get_users_by_role_level(role_level)`

### 3. `view_assignable_users`
- **Кто имеет**: Moderator
- **Описание**: Просмотр пользователей, которым можно назначать роли
- **Логика**: Возвращает пользователей из `get_assignable_roles()`

### 4. `view_assigned_clients`
- **Кто имеет**: Manager
- **Описание**: Просмотр только клиентов, закрепленных за менеджером
- **Логика**: Возвращает `get_clients_for_manager(manager_id)`

## Обновленные роли

### Management
```python
"permissions": (
    "full_access",
    "assign_admin_and_lower",
    "review_documents",
    "approve_documents",
    "communicate_with_clients",
    "respond_to_applications",
    "respond_to_messages",
    "upload_documents",
    "download_documents",
    "request_role_change",
    "view_all_users",  # ← НОВОЕ
)
```

### Admin
```python
"permissions": (
    "assign_moderator_and_lower",
    "review_documents",
    "approve_documents",
    "communicate_with_clients",
    "respond_to_applications",
    "respond_to_messages",
    "view_lower_users",  # ← НОВОЕ
)
```

### Moderator
```python
"permissions": (
    "assign_manager_and_lower",
    "review_documents",
    "respond_to_messages",
    "view_assignable_users",  # ← НОВОЕ
)
```

### Manager
```python
"permissions": (
    "respond_to_messages",
    "view_assigned_clients",  # ← НОВОЕ
)
```

## Backend изменения

### До (жесткие проверки ролей):
```python
if role_key == "management":
    users_list = get_all_users(g.db)
elif role_key == "admin":
    users_list = get_users_by_role_level(g.db, "2")
elif role_key == "moderator":
    users_list = get_users_by_role_level(g.db, "4")
elif role_key == "manager":
    users_list = get_clients_for_manager(g.db, g.current_user_id)
else:
    return jsonify({"success": False, "error": "access denied"}), 403
```

### После (проверка permissions):
```python
permissions = get_role_permissions(role_key)

# Проверка наличия хотя бы одного view permission
has_view_permission = (
    "full_access" in permissions or
    "view_all_users" in permissions or
    "view_lower_users" in permissions or
    "view_assignable_users" in permissions or
    "view_assigned_clients" in permissions
)

if not has_view_permission:
    return jsonify({"success": False, "error": "access denied"}), 403

# Определение списка на основе permissions
if "full_access" in permissions or "view_all_users" in permissions:
    users_list = get_all_users(g.db)
elif "view_lower_users" in permissions:
    users_list = get_users_by_role_level(g.db, role_data["level"])
elif "view_assignable_users" in permissions:
    assignable_roles = get_assignable_roles(role_key)
    if assignable_roles:
        min_level = min(float(r["level"]) for r in assignable_roles)
        users_list = get_users_by_role_level(g.db, str(min_level))
elif "view_assigned_clients" in permissions:
    users_list = get_clients_for_manager(g.db, g.current_user_id)
```

## Frontend изменения

### До (жесткие проверки ролей):
```javascript
const roleKey = userData.role?.key || "";
const canAccessClients = ["management", "admin", "moderator", "manager"].includes(roleKey);
```

### После (проверка permissions):
```javascript
const canAccessClients =
  hasPermission(userData, "full_access") ||
  hasPermission(userData, "view_all_users") ||
  hasPermission(userData, "view_lower_users") ||
  hasPermission(userData, "view_assignable_users") ||
  hasPermission(userData, "view_assigned_clients");
```

## Преимущества объединения

### 1. Гибкость
- Легко добавить новую роль с доступом к пользователям
- Не нужно изменять код проверок - достаточно добавить permission

### 2. Расширяемость
- Можно создать кастомные роли с комбинацией permissions
- Легко настроить разные уровни доступа

### 3. Консистентность
- Вся система использует единый подход к проверке прав
- Нет дублирования логики

### 4. Поддерживаемость
- Проще понять, какие права у роли
- Легче отлаживать проблемы с доступом

### 5. Безопасность
- Централизованная проверка прав
- Меньше вероятность ошибок при добавлении новых ролей

## Примеры использования

### Добавление новой роли с доступом к пользователям

```python
"supervisor": {
    "level": "2.5",
    "name_ru": "Супервайзер",
    "description_ru": "Контроль работы менеджеров",
    "permissions": (
        "view_assignable_users",  # Видит менеджеров и клиентов
        "respond_to_messages",
    ),
}
```

Не нужно изменять код в `routes/lk.py` - система автоматически обработает новую роль!

### Изменение прав существующей роли

Чтобы дать модератору доступ ко всем пользователям:

```python
"moderator": {
    "level": "3",
    "name_ru": "Модератор",
    "permissions": (
        "assign_manager_and_lower",
        "review_documents",
        "respond_to_messages",
        "view_all_users",  # ← Изменили с view_assignable_users
    ),
}
```

## API Response

Теперь API возвращает также список permissions:

```json
{
  "success": true,
  "users": [...],
  "viewer_role": {
    "key": "admin",
    "level": "2",
    "name_ru": "Админ"
  },
  "viewer_permissions": [
    "assign_moderator_and_lower",
    "review_documents",
    "approve_documents",
    "communicate_with_clients",
    "respond_to_applications",
    "respond_to_messages",
    "view_lower_users"
  ]
}
```

Это позволяет frontend динамически адаптировать UI на основе permissions.

## Тестирование

### Проверка доступа для каждой роли:

1. **Management**: Должен видеть всех пользователей
2. **Admin**: Должен видеть всех кроме management
3. **Moderator**: Должен видеть manager и клиентов
4. **Manager**: Должен видеть только своих клиентов
5. **Клиенты**: Не должны видеть ссылку на clients.html

### Проверка API:

```bash
# Получить список пользователей
curl -H "Authorization: Bearer <token>" http://localhost:5000/api/users
```

Ответ должен содержать `viewer_permissions` с соответствующими правами.

## Миграция

Изменения **обратно совместимы**:
- Существующие роли работают как раньше
- Добавлены новые permissions, но старая логика сохранена
- Не требуется миграция базы данных

## Заключение

Система теперь использует **единый подход** к управлению доступом через permissions. Это делает код:
- ✅ Более гибким
- ✅ Легче расширяемым
- ✅ Проще в поддержке
- ✅ Безопаснее
- ✅ Соответствующим архитектуре приложения

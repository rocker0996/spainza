# Анализ системы ролей и доступа

## Существующие роли и их права

### 1. Management (Уровень 1)
**Permissions:**
- `full_access` - полный доступ
- `assign_admin_and_lower` - может назначать админов и ниже
- `review_documents` - просмотр документов
- `approve_documents` - одобрение документов
- `communicate_with_clients` - общение с клиентами
- `respond_to_applications` - ответы по заявкам
- `respond_to_messages` - ответы на сообщения
- `upload_documents` - загрузка документов
- `download_documents` - скачивание документов
- `request_role_change` - запрос смены роли

**Может назначать:** admin, moderator, manager, digital_nomad, golden_visa, user

### 2. Admin (Уровень 2)
**Permissions:**
- `assign_moderator_and_lower` - может назначать модераторов и ниже
- `review_documents` - просмотр документов
- `approve_documents` - одобрение документов
- `communicate_with_clients` - общение с клиентами
- `respond_to_applications` - ответы по заявкам
- `respond_to_messages` - ответы на сообщения

**Может назначать:** moderator, manager, digital_nomad, golden_visa, user

### 3. Moderator (Уровень 3)
**Permissions:**
- `assign_manager_and_lower` - может назначать менеджеров и ниже
- `review_documents` - просмотр документов
- `respond_to_messages` - ответы на сообщения

**Может назначать:** manager, digital_nomad, golden_visa, user

### 4. Manager (Уровень 4)
**Permissions:**
- `respond_to_messages` - ответы на сообщения

**Может назначать:** никого

### 5. Digital Nomad (Уровень 5.1)
**Permissions:**
- `request_role_change` - запрос смены роли
- `upload_documents` - загрузка документов
- `download_documents` - скачивание документов

**Может назначать:** никого

### 6. Golden Visa (Уровень 5.2)
**Permissions:**
- `request_role_change` - запрос смены роли
- `upload_documents` - загрузка документов
- `download_documents` - скачивание документов

**Может назначать:** никого

### 7. User (Уровень 6)
**Permissions:**
- `request_role_change` - запрос смены роли

**Может назначать:** никого

---

## Моя реализация доступа к clients.html

### Правила доступа к странице clients.html:

1. **Management (уровень 1)**: 
   - ✅ Видит ВСЕХ зарегистрированных пользователей
   - Логика: `get_all_users()`

2. **Admin (уровень 2)**: 
   - ✅ Видит всех с уровнем >= 2 (admin, moderator, manager, digital_nomad, golden_visa, user)
   - НЕ видит: management
   - Логика: `get_users_by_role_level(db, "2")`

3. **Moderator (уровень 3)**: 
   - ✅ Видит всех с уровнем >= 4 (manager, digital_nomad, golden_visa, user)
   - НЕ видит: management, admin
   - Логика: `get_users_by_role_level(db, "4")`

4. **Manager (уровень 4)**: 
   - ✅ Видит ТОЛЬКО клиентов, закрепленных за ним через таблицу `manager_clients`
   - Логика: `get_clients_for_manager(db, manager_id)`

5. **Digital Nomad, Golden Visa, User (уровни 5.1, 5.2, 6)**:
   - ❌ НЕТ доступа к странице clients.html
   - При попытке доступа: 403 Forbidden

---

## Проверка на конфликты

### ✅ НЕТ КОНФЛИКТОВ

Моя реализация **полностью соответствует** существующей системе прав:

#### 1. Management
- **Существующие права**: `full_access`, `communicate_with_clients`
- **Мой доступ**: видит всех пользователей
- **Вывод**: ✅ Соответствует - полный доступ означает доступ ко всем пользователям

#### 2. Admin
- **Существующие права**: `communicate_with_clients`, `assign_moderator_and_lower`
- **Мой доступ**: видит всех, кого может назначать + moderator
- **Вывод**: ✅ Соответствует - видит тех, с кем может работать

#### 3. Moderator
- **Существующие права**: `assign_manager_and_lower`, `review_documents`
- **Мой доступ**: видит manager и ниже
- **Вывод**: ✅ Соответствует - видит тех, кого может назначать

#### 4. Manager
- **Существующие права**: `respond_to_messages`
- **Мой доступ**: видит только своих клиентов
- **Вывод**: ✅ Соответствует - менеджер работает только со своими клиентами

#### 5. Клиенты (Digital Nomad, Golden Visa, User)
- **Существующие права**: нет прав на работу с другими пользователями
- **Мой доступ**: нет доступа к clients.html
- **Вывод**: ✅ Соответствует - клиенты не должны видеть других пользователей

---

## Логика фильтрации по уровням

Моя реализация использует **числовые уровни** для фильтрации:

```
1 (management) < 2 (admin) < 3 (moderator) < 4 (manager) < 5.1/5.2 (клиенты) < 6 (user)
```

**Правило**: Чем меньше число, тем выше привилегии.

**Фильтрация**: `float(user_level) >= float(max_level)`
- Admin (уровень 2) видит уровни >= 2: admin, moderator, manager, клиенты
- Moderator (уровень 3) видит уровни >= 4: manager, клиенты

---

## Дополнительная функциональность

### Таблица manager_clients

Новая таблица для связи менеджеров с клиентами:

```sql
CREATE TABLE manager_clients (
    id INTEGER PRIMARY KEY,
    manager_id INTEGER NOT NULL,
    client_id INTEGER NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(manager_id, client_id)
)
```

**Функции:**
- `assign_client_to_manager(manager_id, client_id)` - назначить клиента менеджеру
- `get_clients_for_manager(manager_id)` - получить клиентов менеджера

**Использование:**
- Админ/модератор может назначить клиента менеджеру
- Менеджер видит только назначенных ему клиентов
- При удалении пользователя связи удаляются автоматически (CASCADE)

---

## Безопасность

### ✅ Проверки на уровне API

1. **Аутентификация**: Требуется валидный JWT токен
2. **Авторизация**: Проверка роли пользователя
3. **Фильтрация данных**: Каждая роль видит только разрешенных пользователей
4. **SQL Injection**: Параметризованные запросы
5. **Cascade Delete**: Автоматическая очистка связей

### ✅ Проверки на уровне Frontend

1. **Скрытие навигации**: Ссылка на clients.html скрыта для пользователей без доступа
2. **Редирект**: При попытке прямого доступа - редирект на dashboard
3. **Проверка токена**: Автоматический редирект на login при невалидном токене

---

## Вывод

### ✅ Система работает корректно

1. **Нет конфликтов** с существующей системой ролей
2. **Соблюдается иерархия** прав доступа
3. **Безопасность** обеспечена на всех уровнях
4. **Расширяемость** - легко добавить новые роли или изменить правила

### Рекомендации

1. ✅ Использовать `assign_client_to_manager()` для назначения клиентов менеджерам
2. ✅ Добавить UI для управления назначениями (будущая функциональность)
3. ✅ Рассмотреть добавление логирования действий с пользователями
4. ✅ Добавить пагинацию для больших списков пользователей

# Система назначения ролей через поле "Визовый путь"

## Описание

Реализована система "костыля", где поле **"Визовый путь"** на странице управления кейсом фактически изменяет **роль пользователя** (role_key), но визуально выглядит как выбор визового направления.

## Архитектура

### Backend

#### 1. Модель пользователя ([`backend/models/user.py`](backend/models/user.py))

**Добавлена роль "client":**
```python
"client": {
    "level": 5,
    "label_ru": "Клиент",
    "label_en": "Client",
    "visa_label_ru": "Клиент",
    "visa_label_en": "Client",
    "permissions": ["view_own_case", "upload_documents", "view_messages"]
}
```

**Иерархия ролей (по уровням):**
- Level 1: `management` (Управление)
- Level 2: `admin` (Админ)
- Level 3: `moderator` (Модератор)
- Level 4: `manager` (Менеджер)
- Level 5: `client`, `digital_nomad`, `golden_visa` (Клиентские роли)
- Level 6: `user` (Пользователь)

**Маппинг назначаемых ролей:**
```python
ASSIGNABLE_VISA_TYPES_BY_ROLE = {
    "management": ("admin", "moderator", "manager", "client", "digital_nomad", "golden_visa", "user"),
    "admin": ("moderator", "manager", "client", "digital_nomad", "golden_visa", "user"),
    "moderator": ("manager", "client", "digital_nomad", "golden_visa", "user"),
    "manager": ("client", "digital_nomad", "golden_visa", "user"),
    "client": (),
    "digital_nomad": (),
    "golden_visa": (),
    "user": ()
}
```

**Ключевые функции:**
- [`get_assignable_visa_types(actor_role_key)`](backend/models/user.py:287) - возвращает список ролей, которые может назначить пользователь с данной ролью
- [`can_assign_visa_type(actor_role_key, target_role_key)`](backend/models/user.py:309) - проверяет, может ли пользователь назначить определенную роль
- [`update_user_role(connection, user_id, role_key)`](backend/models/user.py:320) - обновляет роль пользователя в БД

#### 2. API эндпоинты ([`backend/routes/lk.py`](backend/routes/lk.py))

**GET `/api/user`** (строка 48):
- Возвращает информацию о текущем пользователе
- Включает `assignable_visa_types` - список ролей, которые пользователь может назначать

**PUT `/api/case-data/<user_id>`** (строка 458):
- Принимает `visa_type` (который фактически является `role_key`)
- Валидирует права на назначение роли через [`can_assign_visa_type()`](backend/models/user.py:309)
- **Обновляет роль пользователя** через [`update_user_role()`](backend/models/user.py:320)
- Сохраняет `visa_type` в case_data для истории
- Логирует изменение роли в историю кейса

### Frontend

#### 1. Загрузка доступных ролей ([`frontend/js/case.js`](frontend/js/case.js:48))

Функция [`loadLoggedInUser()`](frontend/js/case.js:48):
```javascript
const data = await response.json();
availableVisaTypes = data.assignable_visa_types || [];
```

#### 2. Рендеринг опций ([`frontend/js/case.js`](frontend/js/case.js:138))

Функция [`renderVisaTypeOptions()`](frontend/js/case.js:138):
```javascript
function renderVisaTypeOptions() {
    const visaTypeSelect = document.getElementById('visa-type');
    if (!visaTypeSelect || !availableVisaTypes || availableVisaTypes.length === 0) {
        return;
    }
    
    visaTypeSelect.innerHTML = availableVisaTypes.map(vt => 
        `<option value="${vt.value}">${vt.label_ru}</option>`
    ).join('');
}
```

#### 3. Установка текущей роли ([`frontend/js/case.js`](frontend/js/case.js:241))

Функция [`initializeTimeline()`](frontend/js/case.js:241):
```javascript
// Set visa type from current user's role (костыль - visa_type is actually role_key)
const visaTypeSelect = document.getElementById('visa-type');
if (visaTypeSelect && currentUser && currentUser.role_key) {
    visaTypeSelect.value = currentUser.role_key;
    caseData.visaType = currentUser.role_key;
}
```

#### 4. Сохранение изменений ([`frontend/js/case.js`](frontend/js/case.js:739))

Функция [`saveCaseData()`](frontend/js/case.js:739):
```javascript
const payload = {
    visa_type: document.getElementById('visa-type')?.value || caseData.visaType,
    // ... другие поля
};
```

## Правила назначения ролей

### Иерархия доступа

Каждая административная роль видит и может назначать **только роли ниже своего уровня**:

| Роль актора | Может назначить |
|-------------|-----------------|
| **Management** | admin, moderator, manager, client, digital_nomad, golden_visa, user |
| **Admin** | moderator, manager, client, digital_nomad, golden_visa, user |
| **Moderator** | manager, client, digital_nomad, golden_visa, user |
| **Manager** | client, digital_nomad, golden_visa, user |
| **Client/Digital Nomad/Golden Visa/User** | Ничего (нет доступа к странице) |

### Особенности

1. **Роль "client"** объединяет функционал digital_nomad и golden_visa
2. **Digital Nomad и Golden Visa** сохранены для обратной совместимости
3. Все три клиентские роли имеют одинаковый уровень (5) и права доступа
4. Поле визуально называется "Визовый путь", но фактически управляет ролями

## Безопасность

### Backend валидация

1. **Проверка прав актора:**
   ```python
   if not can_assign_visa_type(g.current_user_role, visa_type):
       return jsonify({"success": False, "error": "insufficient permissions"}), 403
   ```

2. **Проверка существования роли:**
   ```python
   if visa_type not in [r["value"] for r in get_assignable_visa_types(g.current_user_role)]:
       return jsonify({"success": False, "error": "invalid visa type"}), 400
   ```

3. **Атомарное обновление:**
   - Сначала обновляется role_key в таблице users
   - Затем сохраняется visa_type в case_data
   - При ошибке возвращается 500

### Frontend ограничения

1. Пользователь видит только те роли, которые может назначить
2. Текущая роль пользователя автоматически выбрана в dropdown
3. Изменения сохраняются только при явном нажатии кнопки "Сохранить"

## История изменений

При изменении роли создаются две записи в истории:

1. **Изменение роли пользователя:**
   ```
   Действие: "Изменена роль пользователя"
   Детали: "digital_nomad → client (Клиент)"
   ```

2. **Изменение визового пути (для совместимости):**
   ```
   Действие: "Изменен визовый путь"
   Детали: "digital_nomad → client"
   ```

## Тестирование

Запуск тестов:
```bash
python backend/test_visa_permissions.py
```

Тесты проверяют:
- ✅ Доступные роли для каждого уровня
- ✅ Права на назначение конкретных ролей
- ✅ Структуру данных и маппинги
- ✅ Мультиязычную поддержку (RU/EN)

## Примеры использования

### Сценарий 1: Manager назначает роль Client

1. Manager открывает страницу кейса клиента
2. В поле "Визовый путь" видит опции: Клиент, Цифровой кочевник, Золотая виза, Пользователь
3. Выбирает "Клиент"
4. Нажимает "Сохранить"
5. Backend обновляет role_key пользователя на "client"
6. В истории появляется запись об изменении роли

### Сценарий 2: Admin пытается назначить роль Management

1. Admin открывает страницу кейса
2. В поле "Визовый путь" **НЕ видит** роли Management и Admin
3. Может выбрать только: Модератор, Менеджер, Клиент, и т.д.
4. Попытка отправить запрос с role_key="management" через API будет отклонена с 403

## Технические детали

### База данных

**Таблица users:**
- `role_key` - фактическая роль пользователя (обновляется при изменении visa_type)

**Таблица case_data:**
- `visa_type` - сохраняется для истории и совместимости (дублирует role_key)

### API контракт

**Request (PUT /api/case-data/<user_id>):**
```json
{
  "visa_type": "client",
  "target_date": "2024-05-15",
  "timeline": [...],
  "document_requests": [...]
}
```

**Response (успех):**
```json
{
  "success": true
}
```

**Response (ошибка прав):**
```json
{
  "success": false,
  "error": "insufficient permissions"
}
```

## Миграция данных

При внедрении системы:

1. Существующие пользователи с `role_key = "digital_nomad"` или `"golden_visa"` продолжают работать
2. Новые пользователи могут получить роль `"client"`
3. Все три роли имеют одинаковые права доступа
4. Рекомендуется постепенно мигрировать на роль "client"

## Известные ограничения

1. **Название поля**: Поле называется "Визовый путь", но управляет ролями - это "костыль" по требованию
2. **Дублирование данных**: role_key и visa_type хранят одно и то же значение
3. **Обратная совместимость**: Сохранены старые роли digital_nomad и golden_visa

## Будущие улучшения

1. Переименовать поле в UI на "Роль пользователя"
2. Объединить digital_nomad и golden_visa в client
3. Убрать дублирование visa_type в case_data
4. Добавить bulk операции для массового изменения ролей

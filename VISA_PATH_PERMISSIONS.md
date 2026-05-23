# Система управления визовыми путями на основе ролей

## Обзор

Реализована система контроля доступа к визовым путям (application_type) на основе ролей пользователей. Теперь в поле "Визовый путь" на странице управления кейсом отображаются только те опции, которые пользователь может назначать согласно своей роли.

## Архитектура решения

### Backend (Python/Flask)

#### 1. Модель данных (`backend/models/user.py`)

Добавлены новые константы и функции:

**Маппинг визовых путей к ролям:**
```python
VISA_TYPE_TO_ROLE = {
    "digital_nomad": "digital_nomad",
    "golden_visa": "golden_visa",
    "citizen": "user",
    "other": "user",
}
```

**Доступные визовые пути по ролям:**
```python
ASSIGNABLE_VISA_TYPES_BY_ROLE = {
    "management": ("digital_nomad", "golden_visa", "citizen", "other"),
    "admin": ("digital_nomad", "golden_visa", "citizen", "other"),
    "moderator": ("digital_nomad", "golden_visa", "citizen", "other"),
    "manager": ("digital_nomad", "golden_visa", "citizen", "other"),
    "digital_nomad": (),
    "golden_visa": (),
    "user": (),
}
```

**Новые функции:**

- [`get_assignable_visa_types(actor_role_key)`](backend/models/user.py:263) - возвращает список визовых путей, доступных для назначения
- [`can_assign_visa_type(actor_role_key, visa_type)`](backend/models/user.py:295) - проверяет, может ли роль назначить конкретный визовый путь

#### 2. API Routes (`backend/routes/lk.py`)

**Обновлен endpoint `/api/user`:**
- Теперь возвращает поле `assignable_visa_types` со списком доступных визовых путей
- Формат: `[{"value": "digital_nomad", "label_ru": "Цифровой кочевник", "label_en": "Digital Nomad"}, ...]`

**Обновлен endpoint `/api/case-data/<user_id>` (PUT):**
- Добавлена валидация: проверяется, может ли текущий пользователь назначить выбранный визовый путь
- При попытке назначить недоступный визовый путь возвращается ошибка 403

### Frontend (JavaScript)

#### 1. Глобальное состояние (`frontend/js/case.js`)

Добавлена переменная:
```javascript
let availableVisaTypes = []; // Visa types that logged-in user can assign
```

#### 2. Новые функции

**[`renderVisaTypeOptions()`](frontend/js/case.js:132):**
- Динамически рендерит опции в select элементе на основе доступных визовых путей
- Поддерживает мультиязычность (ru/en)
- Автоматически выбирает текущее значение или первую доступную опцию
- Показывает сообщение, если нет доступных визовых путей

**Обновлена [`loadLoggedInUser()`](frontend/js/case.js:46):**
- Загружает и сохраняет список доступных визовых путей из API
- Сохраняет в глобальную переменную `availableVisaTypes`

**Обновлена [`initializeTimeline()`](frontend/js/case.js:217):**
- Вызывает `renderVisaTypeOptions()` после загрузки данных кейса
- Гарантирует, что визовые пути рендерятся с правильными разрешениями

**Обновлена [`initializeCasePage()`](frontend/js/case.js:860):**
- Загружает данные залогиненного пользователя ПЕРВЫМ делом
- Это критично, так как нужны разрешения для рендеринга визовых путей

## Логика работы по ролям

### Management (Управление) - Уровень 1
- ✅ Может назначать: `digital_nomad`, `golden_visa`, `citizen`, `other`
- Полный доступ ко всем визовым путям

### Admin (Админ) - Уровень 2
- ✅ Может назначать: `digital_nomad`, `golden_visa`, `citizen`, `other`
- Полный доступ ко всем визовым путям

### Moderator (Модератор) - Уровень 3
- ✅ Может назначать: `digital_nomad`, `golden_visa`, `citizen`, `other`
- Полный доступ ко всем визовым путям

### Manager (Менеджер) - Уровень 4
- ✅ Может назначать: `digital_nomad`, `golden_visa`, `citizen`, `other`
- Может назначать клиентские визовые пути

### Digital Nomad, Golden Visa, User (Клиенты) - Уровни 5+
- ❌ Не могут назначать визовые пути
- Не имеют доступа к странице управления кейсами

## Примеры использования

### Пример 1: Админ открывает кейс клиента

1. Админ заходит на страницу `/frontend/lk/case.html?userId=123`
2. Система загружает данные админа и получает `assignable_visa_types`
3. В поле "Визовый путь" отображаются все 4 опции:
   - Цифровой кочевник
   - Золотая виза
   - Гражданство
   - Другое
4. Админ может выбрать любой путь и сохранить

### Пример 2: Попытка назначить недоступный визовый путь через API

```javascript
// Попытка клиента (через взлом) назначить визовый путь
fetch('/api/case-data/123', {
    method: 'PUT',
    headers: {
        'Authorization': 'Bearer <client_token>',
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        visa_type: 'golden_visa',
        // ... other data
    })
});

// Ответ: 403 Forbidden
// { "success": false, "error": "access denied: cannot assign visa type 'golden_visa'" }
```

## Безопасность

### Защита на уровне Frontend
1. ✅ Динамический рендеринг опций - пользователь видит только доступные визовые пути
2. ✅ Проверка при инициализации - если нет доступных путей, select отключается

### Защита на уровне Backend
1. ✅ Валидация при сохранении - проверка через `can_assign_visa_type()`
2. ✅ Возврат 403 при попытке назначить недоступный визовый путь
3. ✅ Логирование действий через `add_security_log()`

## Расширяемость

### Добавление нового визового пути

1. Добавить в `VISA_TYPE_TO_ROLE` в [`backend/models/user.py`](backend/models/user.py:99):
```python
VISA_TYPE_TO_ROLE = {
    # ... existing
    "new_visa_type": "user",  # или другая роль
}
```

2. Добавить в `ASSIGNABLE_VISA_TYPES_BY_ROLE`:
```python
ASSIGNABLE_VISA_TYPES_BY_ROLE = {
    "management": ("digital_nomad", "golden_visa", "citizen", "other", "new_visa_type"),
    # ... update other roles as needed
}
```

3. Добавить метку в функцию `get_assignable_visa_types()`:
```python
visa_type_labels = {
    # ... existing
    "new_visa_type": {
        "value": "new_visa_type",
        "label_ru": "Новый визовый путь",
        "label_en": "New Visa Type"
    }
}
```

4. Frontend автоматически подхватит изменения!

### Изменение прав доступа для роли

Просто обновите `ASSIGNABLE_VISA_TYPES_BY_ROLE` для нужной роли:

```python
ASSIGNABLE_VISA_TYPES_BY_ROLE = {
    "manager": ("digital_nomad", "golden_visa"),  # Убрали "citizen" и "other"
    # ...
}
```

## Тестирование

### Ручное тестирование

1. **Тест 1: Management видит все опции**
   - Войти как Management
   - Открыть любой кейс
   - Проверить, что в select есть все 4 опции

2. **Тест 2: Клиент не имеет доступа**
   - Войти как Digital Nomad
   - Попытаться открыть `/frontend/lk/case.html?userId=X`
   - Должен быть редирект на dashboard (403)

3. **Тест 3: Валидация на backend**
   - Использовать Postman/curl для отправки PUT запроса с недоступным visa_type
   - Проверить, что возвращается 403

### Автоматическое тестирование

```python
# Пример unit-теста для backend
def test_can_assign_visa_type():
    assert can_assign_visa_type("management", "digital_nomad") == True
    assert can_assign_visa_type("manager", "golden_visa") == True
    assert can_assign_visa_type("user", "digital_nomad") == False
    assert can_assign_visa_type("digital_nomad", "citizen") == False
```

## Связанные файлы

### Backend
- [`backend/models/user.py`](backend/models/user.py) - модель пользователя и права доступа
- [`backend/routes/lk.py`](backend/routes/lk.py) - API endpoints

### Frontend
- [`frontend/js/case.js`](frontend/js/case.js) - логика управления кейсом
- [`frontend/lk/case.html`](frontend/lk/case.html) - страница управления кейсом

### Документация
- [`ROLES_ANALYSIS.md`](ROLES_ANALYSIS.md) - анализ системы ролей
- [`PERMISSIONS_INTEGRATION.md`](PERMISSIONS_INTEGRATION.md) - интеграция прав доступа

## Changelog

### 2026-04-30
- ✅ Создан маппинг визовых путей к ролям
- ✅ Добавлены функции `get_assignable_visa_types()` и `can_assign_visa_type()`
- ✅ Обновлен API endpoint `/api/user` для возврата доступных визовых путей
- ✅ Добавлена валидация в endpoint `/api/case-data/<user_id>`
- ✅ Реализован динамический рендеринг опций визовых путей на frontend
- ✅ Добавлена поддержка мультиязычности (ru/en)
- ✅ Создана документация

## Заключение

Система управления визовыми путями на основе ролей полностью интегрирована в существующую архитектуру прав доступа. Решение обеспечивает:

1. **Безопасность** - двойная проверка на frontend и backend
2. **Гибкость** - легко добавлять новые визовые пути и изменять права
3. **Удобство** - пользователи видят только релевантные опции
4. **Масштабируемость** - система готова к расширению

Все изменения обратно совместимы и не нарушают существующую функциональность.

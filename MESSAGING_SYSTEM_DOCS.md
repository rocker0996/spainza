# Система сообщений (Messaging System)

## Обзор

Полнофункциональная система обмена сообщениями между пользователями с поддержкой:
- Создания чатов между пользователями
- Отправки текстовых сообщений
- Загрузки и отправки изображений
- Отслеживания непрочитанных сообщений
- Сохранения истории переписки

## Backend API

### Endpoints

#### 1. Получить список чатов
```
GET /api/conversations
Authorization: Bearer <token>
```

**Ответ:**
```json
[
  {
    "id": "conv_1_2",
    "other_user_id": 2,
    "other_user_name": "Иван Иванов",
    "other_user_role": "client",
    "last_message_at": "2026-04-30T18:00:00",
    "unread_count": 3,
    "last_message": "Привет!",
    "last_message_time": "2026-04-30T18:00:00"
  }
]
```

#### 2. Получить сообщения чата
```
GET /api/conversations/{conversation_id}/messages
Authorization: Bearer <token>
```

**Ответ:**
```json
[
  {
    "id": 1,
    "sender_id": 1,
    "receiver_id": 2,
    "message_text": "Привет!",
    "image_path": null,
    "created_at": "2026-04-30T18:00:00",
    "read_status": 1,
    "sender_name": "Алексей"
  }
]
```

#### 3. Создать новый чат
```
POST /api/conversations/create
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_id": 5
}
```

**Ответ:**
```json
{
  "conversation_id": "conv_1_5",
  "other_user": {
    "id": 5,
    "name": "Мария",
    "email": "maria@example.com",
    "role": "admin"
  },
  "messages": []
}
```

#### 4. Отправить текстовое сообщение
```
POST /api/conversations/{conversation_id}/messages
Authorization: Bearer <token>
Content-Type: application/json

{
  "message_text": "Привет! Как дела?"
}
```

**Ответ:**
```json
{
  "message_id": 123,
  "success": true
}
```

#### 5. Отправить изображение
```
POST /api/conversations/{conversation_id}/messages
Authorization: Bearer <token>
Content-Type: multipart/form-data

image: <file>
message_text: "Смотри какое фото!" (опционально)
```

**Ответ:**
```json
{
  "message_id": 124,
  "success": true
}
```

#### 6. Получить количество непрочитанных
```
GET /api/messages/unread-count
Authorization: Bearer <token>
```

**Ответ:**
```json
{
  "unread_count": 5
}
```

#### 7. Поиск пользователей
```
GET /api/users/search?q=<query>
Authorization: Bearer <token>
```

**Ответ:**
```json
[
  {
    "id": 5,
    "name": "Мария Петрова",
    "email": "maria@example.com",
    "role": "admin"
  }
]
```

## Frontend использование

### Инициализация
Страница [`messages.html`](frontend/lk/messages.html:1) автоматически загружает [`chat.js`](frontend/js/chat.js:1), который:
1. Загружает текущего пользователя
2. Получает список чатов
3. Отображает активный чат

### Создание нового чата
1. Нажать кнопку "Новый чат" (иконка редактирования)
2. Ввести ID пользователя
3. Чат создается автоматически и отображается в списке

### Отправка сообщений
- **Текст**: Ввести текст и нажать Enter или кнопку отправки
- **Изображение**: Нажать иконку изображения, выбрать файл

### Поддерживаемые форматы изображений
- PNG
- JPG/JPEG
- GIF
- WEBP

Максимальный размер: 10 МБ

## База данных

### Таблица `conversations`
```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,              -- Формат: conv_{user1_id}_{user2_id}
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    last_message_at TIMESTAMP,
    created_at TIMESTAMP,
    UNIQUE(user1_id, user2_id)
);
```

### Таблица `messages`
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    message_text TEXT,
    image_path TEXT,
    created_at TIMESTAMP,
    read_status INTEGER DEFAULT 0,    -- 0 = непрочитано, 1 = прочитано
    FOREIGN KEY (sender_id) REFERENCES users (id),
    FOREIGN KEY (receiver_id) REFERENCES users (id)
);
```

## Хранение файлов

Изображения сохраняются в:
```
storage/messages/{user_id}/{unique_filename}.{ext}
```

Доступ к изображениям:
```
GET /storage/messages/{user_id}/{filename}
```

## Безопасность

1. **Аутентификация**: Все endpoints требуют Bearer token
2. **Авторизация**: Пользователь может видеть только свои чаты
3. **Валидация файлов**: 
   - Проверка типа файла
   - Ограничение размера
   - Уникальные имена файлов
4. **Path traversal protection**: Защита от доступа к файлам вне storage

## Тестирование

### Инициализация таблиц
```bash
python backend/scripts/init_messages.py
```

### Запуск тестов
```bash
python backend/scripts/test_messages.py
```

Тесты проверяют:
- Создание чатов
- Отправку сообщений
- Получение сообщений
- Подсчет непрочитанных
- Отметку как прочитанное

## Примеры использования

### Создать чат и отправить сообщение (Python)
```python
from models.message import Message

# Создать чат между пользователями 1 и 2
conv_id = Message.get_or_create_conversation(1, 2)

# Отправить сообщение
Message.send_message(conv_id, 1, 2, "Привет!")

# Получить сообщения
messages = Message.get_messages(conv_id)

# Отметить как прочитанное
Message.mark_as_read(conv_id, 2)
```

### Создать чат через API (JavaScript)
```javascript
// Создать новый чат
const response = await fetch('/api/conversations/create', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ user_id: 5 })
});

const data = await response.json();
console.log('Чат создан:', data.conversation_id);
```

### Отправить изображение (JavaScript)
```javascript
const formData = new FormData();
formData.append('image', fileInput.files[0]);
formData.append('message_text', 'Смотри!');

await fetch(`/api/conversations/${conversationId}/messages`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});
```

## Возможные улучшения

1. **Real-time обновления**: WebSocket для мгновенной доставки
2. **Групповые чаты**: Поддержка чатов с более чем 2 участниками
3. **Типизация сообщений**: Статусы доставки (отправлено/доставлено/прочитано)
4. **Редактирование/удаление**: Возможность редактировать и удалять сообщения
5. **Поиск по сообщениям**: Полнотекстовый поиск
6. **Уведомления**: Push-уведомления о новых сообщениях
7. **Файлы**: Поддержка документов и других типов файлов
8. **Эмодзи и реакции**: Реакции на сообщения

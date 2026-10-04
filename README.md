# SysVault — Local Knowledge Base for SysAdmins

> Secure, fast, self-hosted storage for all your technical information.

## Что это

SysVault — это личное хранилище технической информации для системного администратора.

- Заметки, команды, конфигурации, IP-адреса, серверы
- Markdown с подсветкой кода и кнопкой копирования
- Теги и категории
- Поиск по всем полям (`Ctrl+K`)
- История изменений с возможностью восстановления
- Вложения (файлы, изображения)
- Импорт из TXT, экспорт в JSON/Markdown
- Backup в ZIP-архив
- Работает полностью локально, без внешних API

**Не использует:** AI, LLM, RAG, векторные базы, облачные API, платные сервисы.

---

## Требования

- Docker + Docker Compose (Synology Container Manager использует Docker Compose v2)
- ~200 MB свободного места

---

## Установка через Docker Compose

### 1. Создайте директорию проекта

На Synology откройте File Station и создайте папку, например:
```
/home/docker/sysvault/
```

### 2. Скопируйте файлы

Скопируйте все файлы проекта в эту папку:
- `docker-compose.yml`
- `.env.example` (переименуйте в `.env`)
- папки `backend/` и `frontend/`

### 3. Создайте .env

Скопируйте `.env.example` в `.env` и измените пароль:

```env
SECRET_KEY=your-random-secret-key-here
DATABASE_URL=sqlite+aiosqlite:///./data/database.db
CORS_ORIGINS=http://your-nas-ip:80
SEED_DATA=false
```

> **Важно:** Замените `your-random-secret-key-here` на случайную строку.
> Сгенерировать можно так: `python -c "import secrets; print(secrets.token_hex(32))"`

### 4. Запустите приложение

Откройте SSH на Synology или Terminal и выполните:

```bash
cd /home/docker/sysvault
docker compose up -d
```

Или через **Synology Container Manager** → Project → Import → укажите путь к папке.

### 5. Откройте в браузере

```
http://<IP-вашего-NAS>
```

Логин по умолчанию: **admin** / **admin**

### 6. Смените пароль сразу после первого входа

Меню → Change Password

---

## Структура данных

Все данные хранятся в монтируемой папке `./data`:

```
data/
├── database.db        # SQLite база данных
├── attachments/       # Вложенные файлы
└── backups/          # Резервные копии (.zip)
```

Чтобы данные сохранялись при перезапуске контейнера — **не удаляйте папку `data/`**.

---

## Управление через Container Manager (GUI)

1. Откройте **Container Manager** на Synology
2. **Project** → **Create** → выберите папку с проектом
3. Container Manager автоматически найдёт `docker-compose.yml`
4. Нажмите **Run** — приложение запустится
5. Для обновления: **Project** → выберите проект → **Stop** → **Run**

---

## Логирование

```bash
docker compose logs -f
```

Через Container Manager: вкладка **Project** → ваш проект → **Log**.

---

## Остановка и перезапуск

```bash
# Остановить
docker compose down

# Запустить
docker compose up -d

# Перезапустить (после обновления)
docker compose pull   # если используете образы из репозитория
docker compose up -d --build
```

---

## Backup

### Создание резервной копии

В приложении: меню → **Backup** → **Create Backup**

Скачается ZIP-архив: `sysvault-backup-YYYY-MM-DD-HHMM.zip`

### Ручной backup

```bash
cd /home/docker/sysvault
docker compose exec backend python -c "
from app.services.backup import create_backup
import asyncio
print(asyncio.run(create_backup(None)))
"
```

Или просто скопируйте папку `data/`:
```bash
tar czf sysvault-backup-$(date +%Y%m%d).tar.gz data/
```

### Восстановление

1. Остановите контейнеры: `docker compose down`
2. Замените `data/database.db` и `data/attachments/` из архива
3. Запустите: `docker compose up -d`

---

## Экспорт / Импорт

### Экспорт

Меню → **Export**:
- **Export as JSON** — полная копия всех записей
- **Export as Markdown** — все записи в формате Markdown по категориям

### Импорт TXT

Меню → **Export** → раздел **Import from TXT**:
- Вставьте текстовый файл
- Укажите разделитель (например `===`), чтобы создать несколько записей
- Без разделителя — весь текст станет одной записью

---

## Горячие клавиши

| Клавиша | Действие |
|---------|----------|
| `Ctrl+K` | Открыть поиск |
| `Ctrl+N` | Новая запись |
| `Ctrl+S` | Сохранить (в редакторе) |
| `Esc` | Закрыть поиск/модалку |

---

## Безопасность

- Пароли хранятся в виде bcrypt-хешей
- JWT-токены с временем жизни 7 дней
- CORS настроен только на указанный домен
- Вложения проверяются по MIME-типу и расширению
- SQL-инъекции невозможны (используется SQLAlchemy ORM)
- Секреты задаются через `.env`, не хардкодятся в коде

> ⚠️ Приложение не имеет встроенной защиты от Brute-force. Если вы планируете открывать доступ извне — настройте обратный прокси с базовой аутентификацией (Nginx, Caddy).

---

## Разработка

```bash
# Backend
cd backend
pip install -r requirements.txt
pytest

# Frontend (локально, без Docker)
cd frontend
npm install
npm run dev
# Откроется на http://localhost:5173
```

---

## Тесты

```bash
cd backend
pytest -v
# 17 тестов: CRUD, поиск, категории, теги, история, импорт, экспорт, backup
```

---

## Структура проекта

```
sysvault/
├── docker-compose.yml      # Запуск двух контейнеров
├── .env                    # Секреты (НЕ коммитить!)
├── .env.example            # Шаблон
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI приложение
│   │   ├── database.py     # SQLAlchemy + SQLite
│   │   ├── models.py       # Модели БД
│   │   ├── schemas.py      # Pydantic схемы
│   │   ├── api/            # REST эндпоинты
│   │   └── services/       # Бизнес-логика
│   ├── tests/              # pytest тесты
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/                # React + TypeScript + Tailwind
│   ├── Dockerfile
│   └── nginx.conf
└── data/                   # Монтируемый том ( база + вложения)
    ├── database.db
    ├── attachments/
    └── backups/
```

---

## Решение проблем

**Контейнер не запускается:**
```bash
docker compose logs backend
docker compose logs frontend
```

**Потеря данных:**
Убедитесь, что папка `data/` не удаляется при `docker compose down`. Она должна сохраняться на диске NAS.

**Забыли пароль:**
```bash
# Подключиться к контейнеру и сбросить
docker exec -it sysvault-backend-1 python -c "
from app.database import AsyncSessionLocal, get_db
from app.models import User
from app.services.auth import hash_password
import asyncio

async def reset():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user:
            user.hashed_password = hash_password('newpassword')
            await db.commit()
            print('Password reset to: newpassword')

asyncio.run(reset())
"
```

---

## Лицензия

MIT — используйте свободно.

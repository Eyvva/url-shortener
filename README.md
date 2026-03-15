[🇷🇺 Русский](README_RU.md) | [🇬🇧 English](README_EN.md)
# 🔗 Сервис сокращения ссылок

API-сервис для сокращения длинных ссылок с аналитикой и управлением.

## Возможности

- Создание коротких ссылок (с автогенерацией кода или кастомным alias)
- Редирект по короткому коду с отслеживанием переходов
- Статистика по каждой ссылке
- Поиск ссылок по оригинальному URL
- Группировка ссылок по проектам
- Время жизни ссылки с автоматическим удалением
- История истёкших ссылок
- Регистрация и авторизация пользователей (JWT)
- Кэширование через Redis
- Автоматическая очистка неиспользуемых ссылок

---

## Технологии

| Компонент | Технология |
|---|---|
| Фреймворк | FastAPI |
| База данных | PostgreSQL |
| Кэш | Redis |
| Авторизация | JWT (Bearer token) |
| Контейнеризация | Docker / Docker Compose |
| Базовый образ | Red Hat UBI9 Minimal |

---

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone <url> && cd url-shortener
```

### 2. Запустить через Docker Compose

```bash
docker compose up --build
```

### 3. Открыть документацию

```
http://localhost:8000/docs
```

---

## Структура проекта

```
url-shortener/
├── app/
│   ├── api/v1/
│   │   ├── auth.py          # Регистрация, логин
│   │   ├── links.py         # Эндпоинты для ссылок
│   │   └── projects.py      # Эндпоинты для проектов
│   ├── core/
│   │   ├── config.py        # Настройки приложения
│   │   ├── database.py      # Подключение к PostgreSQL
│   │   ├── cache.py         # Работа с Redis
│   │   └── security.py      # JWT, хэширование паролей
│   ├── models/
│   │   └── models.py        # ORM модели (User, Link, Project)
│   ├── schemas/
│   │   └── schemas.py       # Pydantic схемы запросов/ответов
│   ├── services/
│   │   ├── link_service.py  # Бизнес-логика ссылок
│   │   ├── user_service.py  # Бизнес-логика пользователей
│   │   └── project_service.py
│   ├── utils/
│   │   └── scheduler.py     # Фоновые задачи
│   └── main.py              # Точка входа
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## API эндпоинты

### Авторизация

| Метод | Путь | Доступ | Описание |
|-------|------|--------|----------|
| `POST` | `/api/v1/auth/register` | Все | Регистрация |
| `POST` | `/api/v1/auth/login` | Все | Получить токен |
| `GET` | `/api/v1/auth/me` | 🔒 | Текущий пользователь |

### Ссылки

| Метод | Путь | Доступ | Описание |
|-------|------|--------|----------|
| `POST` | `/api/v1/links/shorten` | Все | Создать короткую ссылку |
| `GET` | `/{short_code}` | Все | Редирект на оригинальный URL |
| `GET` | `/api/v1/links/{short_code}/stats` | Все | Статистика переходов |
| `PUT` | `/api/v1/links/{short_code}` | 🔒 | Обновить ссылку |
| `DELETE` | `/api/v1/links/{short_code}` | 🔒 | Удалить ссылку |
| `GET` | `/api/v1/links/search?original_url=` | Все | Поиск по оригинальному URL |
| `GET` | `/api/v1/links/expired` | 🔒 | История истёкших ссылок |
| `POST` | `/api/v1/links/cleanup` | 🔒 | Очистка неиспользуемых ссылок |

### Проекты

| Метод | Путь | Доступ | Описание |
|-------|------|--------|----------|
| `POST` | `/api/v1/projects` | 🔒 | Создать проект |
| `GET` | `/api/v1/projects` | 🔒 | Список проектов |
| `DELETE` | `/api/v1/projects/{id}` | 🔒 | Удалить проект |

---

## Примеры запросов

### Регистрация

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "ivan", "email": "ivan@example.com", "password": "secret123"}'
```

### Логин

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "ivan", "password": "secret123"}'
```

### Создать короткую ссылку

```bash
curl -X POST http://localhost:8000/api/v1/links/shorten \
  -H "Content-Type: application/json" \
  -d '{"original_url": "https://www.example.com"}'
```

### Создать с кастомным alias и сроком жизни

```bash
curl -X POST http://localhost:8000/api/v1/links/shorten \
  -H "Authorization: Bearer <токен>" \
  -H "Content-Type: application/json" \
  -d '{
    "original_url": "https://www.example.com",
    "custom_alias": "mylink",
    "expires_at": "2026-12-31T23:59:00Z"
  }'
```

### Статистика

```bash
curl http://localhost:8000/api/v1/links/mylink/stats
```

---

## Кэширование

| Данные | Ключ в Redis | Время жизни |
|--------|-------------|-------------|
| Редирект URL | `redirect:{code}` | 5 минут |
| Статистика | `stats:{code}` | 1 час |
| Результаты поиска | `search:{url}` | 1 час |
| Популярные ссылки (≥100 переходов) | `redirect:{code}` | 24 часа |

Кэш автоматически очищается при обновлении и удалении ссылки.

---

## Фоновые задачи

| Задача | Интервал | Действие |
|--------|----------|----------|
| Удаление истёкших ссылок | Каждую минуту | Деактивирует ссылки с истёкшим `expires_at` |
| Очистка неиспользуемых | Каждый час | Удаляет ссылки без переходов за 30 дней |

---

## Настройка

Переменные окружения в `docker-compose.yml`:

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Строка подключения к PostgreSQL |
| `REDIS_URL` | `redis://redis:6379/0` | Строка подключения к Redis |
| `SECRET_KEY` | — | Секрет для JWT (обязательно сменить!) |
| `BASE_URL` | `http://localhost:8000` | Базовый URL сервиса |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Время жизни токена в минутах |
| `UNUSED_LINK_TTL_DAYS` | `30` | Дней до удаления неиспользуемой ссылки |

---

## Авторизация в Swagger

1. Открыть `http://localhost:8000/docs`
2. Выполнить `POST /api/v1/auth/login`
3. Скопировать `access_token` из ответа
4. Нажать кнопку **Authorize 🔒** вверху страницы
5. Вставить токен в поле **HTTPBearer** и нажать **Authorize**

---

## Тестирование

Тесты запускаются **без Docker** — используется SQLite in-memory вместо PostgreSQL и FakeRedis вместо настоящего Redis.

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Запуск тестов с отчётом покрытия

```bash
# Запуск всех тестов + покрытие в терминале и HTML
coverage run -m pytest tests

# Или через pytest (настроено в pytest.ini, включает --cov автоматически)
pytest tests
```

### Просмотр HTML-отчёта покрытия

После запуска тестов откройте файл в браузере:

```
htmlcov/index.html
```

Файл `htmlcov/index.html` визуализирует покрытие построчно для каждого модуля.

### Структура тестов

```
tests/
├── conftest.py            # Фикстуры: SQLite БД, FakeRedis, HTTP-клиент
├── test_auth.py           # Регистрация, логин, /me
├── test_links.py          # CRUD ссылок, редирект, поиск, очистка
├── test_redirect.py       # Кэширование редиректов и статистики
├── test_projects.py       # CRUD проектов
├── test_link_service.py   # Юнит-тесты сервиса (генерация кода, бизнес-логика)
├── test_schemas.py        # Валидация Pydantic схем
├── test_security.py       # JWT, хэширование паролей
├── test_cache.py          # Redis-утилиты (ключи, операции)
├── test_scheduler.py      # Фоновые задачи
├── test_edge_cases.py     # Граничные случаи и невалидные данные
└── test_main.py           # Root-эндпоинт и lifespan приложения
```

### Типы тестов

| Тип | Файлы | Что проверяет |
|-----|-------|---------------|
| Юнит | `test_schemas.py`, `test_security.py`, `test_cache.py`, `test_link_service.py` | Изолированная логика: валидация, JWT, генерация кодов |
| Функциональные | `test_auth.py`, `test_links.py`, `test_projects.py`, `test_redirect.py`, `test_edge_cases.py` | API через TestClient (все CRUD + редирект) |
| Нагрузочные | `locustfile.py` | Производительность под нагрузкой |

### Нагрузочное тестирование (Locust)

```bash
# С UI — открыть http://localhost:8089
locust -f locustfile.py --host=http://localhost:8000

# Без UI (50 пользователей, 10/с нарастание, 60 секунд)
locust -f locustfile.py --host=http://localhost:8000 \
       --headless -u 50 -r 10 --run-time 60s
```

---

## Управление контейнерами

```bash
# Запустить
docker compose up --build

# Остановить
docker compose down

# Остановить и удалить данные
docker compose down -v

# Логи приложения
docker compose logs app --tail=50

# Подключиться к базе данных
docker exec -it url_shortener_db psql -U postgres -d url_shortener
```

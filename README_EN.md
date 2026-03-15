[🇷🇺 Русский](README.md) | [🇬🇧 English](README_EN.md)
# 🔗 URL Shortener Service

An API service for shortening long URLs with analytics and management.

## Features

- Short link creation (auto-generated code or custom alias)
- Redirect by short code with click tracking
- Statistics per link
- Search links by original URL
- Group links by projects
- Link expiry with automatic deletion
- History of expired links
- User registration and authentication (JWT)
- Redis caching
- Automatic cleanup of unused links

---

## Technologies

| Component | Technology |
|---|---|
| Framework | FastAPI |
| Database | PostgreSQL |
| Cache | Redis |
| Authentication | JWT (Bearer token) |
| Containerization | Docker / Docker Compose |
| Base image | Red Hat UBI9 Minimal |

---

## Quick Start

### 1. Clone the repository

```bash
git clone <url> && cd url-shortener
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

### 3. Open the documentation

```
http://localhost:8000/docs
```

---

## Project Structure

```
url-shortener/
├── app/
│   ├── api/v1/
│   │   ├── auth.py          # Registration, login
│   │   ├── links.py         # Link endpoints
│   │   └── projects.py      # Project endpoints
│   ├── core/
│   │   ├── config.py        # Application settings
│   │   ├── database.py      # PostgreSQL connection
│   │   ├── cache.py         # Redis operations
│   │   └── security.py      # JWT, password hashing
│   ├── models/
│   │   └── models.py        # ORM models (User, Link, Project)
│   ├── schemas/
│   │   └── schemas.py       # Pydantic request/response schemas
│   ├── services/
│   │   ├── link_service.py  # Link business logic
│   │   ├── user_service.py  # User business logic
│   │   └── project_service.py
│   ├── utils/
│   │   └── scheduler.py     # Background tasks
│   └── main.py              # Entry point
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## API Endpoints

### Authentication

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| `POST` | `/api/v1/auth/register` | All | Register |
| `POST` | `/api/v1/auth/login` | All | Get token |
| `GET` | `/api/v1/auth/me` | 🔒 | Current user |

### Links

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| `POST` | `/api/v1/links/shorten` | All | Create short link |
| `GET` | `/{short_code}` | All | Redirect to original URL |
| `GET` | `/api/v1/links/{short_code}/stats` | All | Click statistics |
| `PUT` | `/api/v1/links/{short_code}` | 🔒 | Update link |
| `DELETE` | `/api/v1/links/{short_code}` | 🔒 | Delete link |
| `GET` | `/api/v1/links/search?original_url=` | All | Search by original URL |
| `GET` | `/api/v1/links/expired` | 🔒 | Expired links history |
| `POST` | `/api/v1/links/cleanup` | 🔒 | Clean up unused links |

### Projects

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| `POST` | `/api/v1/projects` | 🔒 | Create project |
| `GET` | `/api/v1/projects` | 🔒 | List projects |
| `DELETE` | `/api/v1/projects/{id}` | 🔒 | Delete project |

---

## Request Examples

### Register

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "email": "john@example.com", "password": "secret123"}'
```

### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "password": "secret123"}'
```

### Create a short link

```bash
curl -X POST http://localhost:8000/api/v1/links/shorten \
  -H "Content-Type: application/json" \
  -d '{"original_url": "https://www.example.com"}'
```

### Create with custom alias and expiry

```bash
curl -X POST http://localhost:8000/api/v1/links/shorten \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "original_url": "https://www.example.com",
    "custom_alias": "mylink",
    "expires_at": "2026-12-31T23:59:00Z"
  }'
```

### Get statistics

```bash
curl http://localhost:8000/api/v1/links/mylink/stats
```

---

## Caching

| Data | Redis Key | TTL |
|------|-----------|-----|
| Redirect URL | `redirect:{code}` | 5 minutes |
| Statistics | `stats:{code}` | 1 hour |
| Search results | `search:{url}` | 1 hour |
| Popular links (≥100 clicks) | `redirect:{code}` | 24 hours |

Cache is automatically invalidated on link update and delete.

---

## Background Tasks

| Task | Interval | Action |
|------|----------|--------|
| Expire links | Every minute | Deactivates links past their `expires_at` |
| Clean unused | Every hour | Removes links with no clicks for 30 days |

---

## Configuration

Environment variables in `docker-compose.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `SECRET_KEY` | — | JWT signing secret (change this!) |
| `BASE_URL` | `http://localhost:8000` | Base URL of the service |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token lifetime in minutes |
| `UNUSED_LINK_TTL_DAYS` | `30` | Days before unused link is deleted |

---

## Swagger Authorization

1. Open `http://localhost:8000/docs`
2. Call `POST /api/v1/auth/login`
3. Copy `access_token` from the response
4. Click the **Authorize 🔒** button at the top of the page
5. Paste the token into the **HTTPBearer** field and click **Authorize**

---

## Container Management

```bash
# Start
docker compose up --build

# Stop
docker compose down

# Stop and delete data
docker compose down -v

# Application logs
docker compose logs app --tail=50

# Connect to the database
docker exec -it url_shortener_db psql -U postgres -d url_shortener
```

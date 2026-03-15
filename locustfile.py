"""
Нагрузочные тесты с использованием Locust.

Запуск:
    locust -f locustfile.py --host=http://localhost:8000

Затем открыть http://localhost:8089 и настроить параметры нагрузки.

Или без UI:
    locust -f locustfile.py --host=http://localhost:8000 \
           --headless -u 50 -r 10 --run-time 60s
"""
import random
import string
from locust import HttpUser, task, between, events


def random_string(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


class AnonymousUser(HttpUser):
    """Анонимный пользователь — создаёт и читает ссылки."""
    wait_time = between(0.5, 2)
    short_codes = []

    def on_start(self):
        for _ in range(3):
            self._create_link()

    def _create_link(self):
        url = f"https://www.example.com/{random_string()}"
        with self.client.post(
            "/api/v1/links/shorten",
            json={"original_url": url},
            catch_response=True,
            name="/api/v1/links/shorten [POST]",
        ) as resp:
            if resp.status_code == 201:
                code = resp.json().get("short_code")
                if code:
                    AnonymousUser.short_codes.append(code)
                resp.success()
            else:
                resp.failure(f"Failed to create link: {resp.status_code}")

    @task(3)
    def create_link(self):
        """Создание короткой ссылки — самая частая операция."""
        self._create_link()

    @task(5)
    def redirect(self):
        """Редирект — самая нагруженная операция."""
        if not AnonymousUser.short_codes:
            return
        code = random.choice(AnonymousUser.short_codes)
        with self.client.get(
            f"/{code}",
            allow_redirects=False,
            catch_response=True,
            name="/{short_code} [GET redirect]",
        ) as resp:
            if resp.status_code in (302, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def get_stats(self):
        """Получение статистики ссылки."""
        if not AnonymousUser.short_codes:
            return
        code = random.choice(AnonymousUser.short_codes)
        with self.client.get(
            f"/api/v1/links/{code}/stats",
            catch_response=True,
            name="/api/v1/links/{short_code}/stats [GET]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def search_links(self):
        """Поиск ссылок по оригинальному URL."""
        url = f"https://www.example.com/{random_string()}"
        with self.client.get(
            f"/api/v1/links/search?original_url={url}",
            catch_response=True,
            name="/api/v1/links/search [GET]",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")


class AuthenticatedUser(HttpUser):
    """Авторизованный пользователь — полный CRUD."""
    wait_time = between(1, 3)
    token = None
    own_codes = []

    def on_start(self):
        username = f"locust_{random_string(6)}"
        password = "locust_pass_123"

        self.client.post(
            "/api/v1/auth/register",
            json={"username": username, "email": f"{username}@test.com", "password": password},
            name="/api/v1/auth/register [POST]",
        )

        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
            name="/api/v1/auth/login [POST]",
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token")
            self.own_codes = []

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(3)
    def create_link(self):
        """Создание ссылки авторизованным пользователем."""
        url = f"https://www.example.com/{random_string()}"
        with self.client.post(
            "/api/v1/links/shorten",
            json={"original_url": url},
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/links/shorten [POST] auth",
        ) as resp:
            if resp.status_code == 201:
                code = resp.json().get("short_code")
                if code:
                    self.own_codes.append(code)
                resp.success()
            else:
                resp.failure(f"Failed: {resp.status_code}")

    @task(2)
    def redirect(self):
        """Редирект по ссылке."""
        if not self.own_codes:
            return
        code = random.choice(self.own_codes)
        with self.client.get(
            f"/{code}",
            allow_redirects=False,
            catch_response=True,
            name="/{short_code} [GET redirect] auth",
        ) as resp:
            if resp.status_code in (302, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected: {resp.status_code}")

    @task(1)
    def update_link(self):
        """Обновление ссылки."""
        if not self.own_codes:
            return
        code = random.choice(self.own_codes)
        new_url = f"https://updated.example.com/{random_string()}"
        with self.client.put(
            f"/api/v1/links/{code}",
            json={"original_url": new_url},
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/links/{short_code} [PUT]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Failed: {resp.status_code}")

    @task(1)
    def create_with_alias(self):
        """Создание ссылки с кастомным alias."""
        alias = f"loc{random_string(6)}"
        with self.client.post(
            "/api/v1/links/shorten",
            json={
                "original_url": f"https://alias.example.com/{random_string()}",
                "custom_alias": alias,
            },
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/links/shorten [POST] alias",
        ) as resp:
            if resp.status_code in (201, 409):
                resp.success()
            else:
                resp.failure(f"Failed: {resp.status_code}")

    @task(1)
    def get_projects(self):
        """Получение списка проектов."""
        with self.client.get(
            "/api/v1/projects",
            headers=self._headers(),
            catch_response=True,
            name="/api/v1/projects [GET]",
        ) as resp:
            if resp.status_code in (200, 401):
                resp.success()
            else:
                resp.failure(f"Failed: {resp.status_code}")

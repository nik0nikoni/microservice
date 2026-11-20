from conftest import make_user, wait_for


def test_gateway_health_and_ready(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_protected_route_requires_token(client):
    assert client.get("/api/projects").status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/api/projects", headers=bad).status_code == 401


def test_register_login_errors(client):
    user = make_user(client)
    duplicate = client.post(
        "/api/auth/register", json={"email": user["email"], "password": "password123"}
    )
    assert duplicate.status_code == 409

    wrong = client.post("/api/auth/login", json={"email": user["email"], "password": "wrong-password"})
    assert wrong.status_code == 401


def test_profile_upsert_and_read(client):
    user = make_user(client)
    assert client.get("/api/users/me", headers=user["headers"]).status_code == 404

    r = client.put(
        "/api/users/me",
        json={"display_name": "Tester", "bio": "hello"},
        headers=user["headers"],
    )
    assert r.status_code == 200
    assert r.json()["user_id"] == user["id"]

    r = client.get(f"/api/users/{user['id']}", headers=user["headers"])
    assert r.status_code == 200
    assert r.json()["display_name"] == "Tester"


def test_gateway_ignores_spoofed_identity_header(client):
    """Клиент пытается подделать X-User-Id, но gateway подставляет id из токена."""
    user = make_user(client)
    client.put("/api/users/me", json={"display_name": "Real"}, headers=user["headers"])

    headers = {**user["headers"], "X-User-Id": "1"}
    r = client.get("/api/users/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["user_id"] == user["id"]


def test_internal_endpoints_not_exposed(client):
    user = make_user(client)
    r = client.get("/internal/projects/1/members/1", headers=user["headers"])
    assert r.status_code == 404


def test_project_and_task_access_control(client):
    owner = make_user(client, "owner")
    outsider = make_user(client, "outsider")

    r = client.post("/api/projects", json={"name": "Secret"}, headers=owner["headers"])
    assert r.status_code == 201
    project_id = r.json()["id"]

    r = client.post(
        "/api/tasks",
        json={"project_id": project_id, "title": "Task"},
        headers=owner["headers"],
    )
    assert r.status_code == 201
    task_id = r.json()["id"]

    # посторонний не видит проект и задачу и не может создавать задачи в проекте
    assert client.get(f"/api/projects/{project_id}", headers=outsider["headers"]).status_code == 404
    assert client.get(f"/api/tasks/{task_id}", headers=outsider["headers"]).status_code == 404
    r = client.post(
        "/api/tasks",
        json={"project_id": project_id, "title": "Hack"},
        headers=outsider["headers"],
    )
    assert r.status_code == 404

    # исполнитель обязан быть участником проекта
    r = client.post(
        "/api/tasks",
        json={"project_id": project_id, "title": "Bad", "assignee_id": outsider["id"]},
        headers=owner["headers"],
    )
    assert r.status_code == 400


def test_task_events_create_notifications(client):
    """Асинхронный сценарий: task-service -> RabbitMQ -> notification-service."""
    owner = make_user(client, "owner")
    worker = make_user(client, "worker")

    project = client.post("/api/projects", json={"name": "Async"}, headers=owner["headers"]).json()
    r = client.post(
        f"/api/projects/{project['id']}/members",
        json={"user_id": worker["id"]},
        headers=owner["headers"],
    )
    assert r.status_code == 201

    task = client.post(
        "/api/tasks",
        json={"project_id": project["id"], "title": "Notify me", "assignee_id": worker["id"]},
        headers=owner["headers"],
    ).json()
    r = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=owner["headers"])
    assert r.status_code == 200

    def fetch():
        items = client.get("/api/notifications", headers=worker["headers"]).json()
        return items if len(items) >= 2 else None

    items = wait_for(fetch)
    assert items, "notifications did not arrive in time"
    assert {n["type"] for n in items} == {"task.assigned", "task.status_changed"}

    # автор сам совершал действия, поэтому ему уведомления не приходят
    assert client.get("/api/notifications", headers=owner["headers"]).json() == []

    # отметка прочитанным
    first = items[0]["id"]
    r = client.post(f"/api/notifications/{first}/read", headers=worker["headers"])
    assert r.status_code == 200
    assert r.json()["is_read"] is True
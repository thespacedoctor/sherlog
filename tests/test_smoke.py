import pytest


@pytest.mark.django_db
def test_login_page_loads(client):
    response = client.get("/accounts/login/")
    assert response.status_code == 200

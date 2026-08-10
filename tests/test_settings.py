import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured


def load_settings(monkeypatch, **environment):
    """*re-import sherlog.settings with a patched environment*

    The developer's own ``.env`` is neutralised first: otherwise reloading the
    module reads it back in and these assertions depend on whoever is running
    them having chosen SQLite locally.
    """
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    for name, value in environment.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    return importlib.reload(importlib.import_module("sherlog.settings"))


def test_development_defaults_to_sqlite(monkeypatch):
    settings = load_settings(monkeypatch, DJANGO_ENV=None, DJANGO_DB=None)
    assert settings.DATABASE_BACKEND == "sqlite"
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"


def test_development_can_select_mariadb(monkeypatch):
    settings = load_settings(monkeypatch, DJANGO_ENV=None, DJANGO_DB="mariadb", DB_NAME="sherlog")
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.mysql"
    assert settings.DATABASES["default"]["NAME"] == "sherlog"
    assert settings.DATABASES["default"]["OPTIONS"]["charset"] == "utf8mb4"


def test_production_is_always_mariadb(monkeypatch):
    # EVEN WITH DJANGO_DB=sqlite, WHICH MUST NOT BE ABLE TO DOWNGRADE PRODUCTION
    settings = load_settings(monkeypatch, DJANGO_ENV="production", DJANGO_DB="sqlite")
    assert settings.DATABASE_BACKEND == "mariadb"
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.mysql"


def test_unknown_backend_is_rejected(monkeypatch):
    with pytest.raises(ImproperlyConfigured):
        load_settings(monkeypatch, DJANGO_ENV=None, DJANGO_DB="postgres")


@pytest.fixture(autouse=True)
def restore_settings_module(monkeypatch):
    """*leave sherlog.settings as the live test settings again*

    The tests above reload the module with a doctored environment; without this
    the last one wins for the rest of the session.
    """
    yield
    monkeypatch.undo()
    importlib.reload(importlib.import_module("sherlog.settings"))

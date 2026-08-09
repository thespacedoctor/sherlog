"""*Django settings for sherlog, built on django_fundamentals*"""

import os
from pathlib import Path

from django_fundamentals.settings import (
    ACCOUNT_ADAPTER,
    ACCOUNT_EMAIL_VERIFICATION,
    ACCOUNT_LOGIN_METHODS,
    ACCOUNT_LOGOUT_REDIRECT_URL,
    ACCOUNT_SIGNUP_FIELDS,
    ACCOUNT_UNIQUE_EMAIL,
    ANONYMOUS_USER_NAME,
    BASE_AUTHENTICATION_BACKENDS,
    BASE_INSTALLED_APPS,
    BASE_MIDDLEWARE,
    BASE_REST_FRAMEWORK,
    BASE_TEMPLATE_CONTEXT_PROCESSORS,
    LOGIN_REDIRECT_URL,
    REST_AUTH,
)

# THE django_fundamentals IMPORTS ABOVE ARE RE-EXPORTED AS-IS: DJANGO PICKS UP ANY
# UPPERCASE NAME IN THIS MODULE'S NAMESPACE AS A REAL SETTING, IMPORTED OR NOT.

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "change-me-in-production"  # OVERRIDE VIA ENV VAR IN DEPLOY
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "7.7.7.7"]

AUTH_USER_MODEL = "django_fundamentals.User"
SITE_ID = 1

# --- UI SKELETON -----------------------------------------------------------
# COLOURS AND DIMENSIONS LIVE IN static/src/tokens.css, NOT HERE. THESE TWO
# CONTROL THE CHROME'S *CONTENT*.
DJANGO_FUNDAMENTALS_SITE_NAME = "sherlog"

# SIDEBAR ENTRIES. AN ENTRY WITH "section" IS A GROUP HEADING RATHER THAN A
# LINK; `icon` NAMES ONE OF THE INLINE SVGS IN atoms/icon.html. A url_name THAT
# CANNOT BE REVERSED IS SKIPPED RATHER THAN RAISING, SO IT IS SAFE TO LIST
# ROUTES THAT DON'T EXIST YET.
# ACCOUNT TOOLS DELIBERATELY ABSENT: EMAIL ADDRESSES, PASSWORD, PROFILE AND API
# TOKEN ARE ALL TABS ON /settings/, REACHED FROM THE NAVBAR AVATAR.
DJANGO_FUNDAMENTALS_SIDEBAR_NAV = [
    {"label": "Home", "url_name": "django_fundamentals_home", "icon": "home"},
    {"section": "sherlog"},
    {"label": "Transients", "url_name": "transient_list", "icon": "eye"},
]

INSTALLED_APPS = [*BASE_INSTALLED_APPS, "apps.transients"]
MIDDLEWARE = [*BASE_MIDDLEWARE]
AUTHENTICATION_BACKENDS = BASE_AUTHENTICATION_BACKENDS
REST_FRAMEWORK = BASE_REST_FRAMEWORK

ROOT_URLCONF = "sherlog.urls"
WSGI_APPLICATION = "sherlog.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": BASE_TEMPLATE_CONTEXT_PROCESSORS},
    }
]

if os.environ.get("DJANGO_ENV") == "production":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "sherlog"),
            "USER": os.environ.get("DB_USER", "sherlog"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# WHERE USER UPLOADS (PROFILE PICTURES) ARE WRITTEN. THERE IS NO MEDIA_URL AND
# NO APACHE Alias TO MATCH: django-fundamentals SERVES AVATARS THROUGH A VIEW,
# SO UPLOADS WORK IN DEV AND PRODUCTION WITHOUT ANY WEB-SERVER CONFIGURATION.
# django-fundamentals FALLS BACK TO BASE_DIR / "media" IF THIS IS UNSET, SO IT
# IS DECLARED HERE ONLY TO MAKE THE LOCATION OBVIOUS.
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# EMAIL VERIFICATION IS MANDATORY, SO SIGNUP DEPENDS ON EMAIL WORKING.
# IN DEV THE CONSOLE BACKEND PRINTS THE MESSAGE TO THE runserver TERMINAL (AND
# THE "verify your email" PAGE SHOWS THE LINK DIRECTLY WHILE DEBUG IS ON).
# FOR PRODUCTION SMTP — INCLUDING A GMAIL WALKTHROUGH — SEE django-fundamentals'
# docs/source/email.md
if os.environ.get("DJANGO_ENV") == "production":
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    # PORT 587 USES STARTTLS; PORT 465 WOULD NEED EMAIL_USE_SSL INSTEAD.
    # SETTING BOTH RAISES ImproperlyConfigured.
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
    EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"
    # GMAIL REWRITES OR REJECTS A FROM ADDRESS THAT ISN'T THE AUTHENTICATED
    # ACCOUNT (OR ONE OF ITS ALIASES).
    DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

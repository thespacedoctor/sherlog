# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

sherlog — tools to test and debug the Sherlock contextual classifier for astronomical transients.
Django 5 project built on the external [django-fundamentals](https://github.com/thespacedoctor/django-fundamentals) package, which supplies auth, permissions, the API layer and the entire UI chrome.

## Commands

```bash
conda activate sherlog          # env must be active for the Tailwind build to work
pip install -e ".[dev]"
npm install

npm run build:css               # one-shot Tailwind build
npm run watch:css               # keep running in a second terminal while editing templates

python manage.py migrate
python manage.py runserver

pytest -q                       # all tests
pytest tests/test_smoke.py::test_login_page_loads   # a single test
python manage.py check          # Django system checks (CI runs this before pytest)
```

`PYTHON=/path/to/python npm run build:css` if you cannot activate the env — `tailwind.config.js` shells out to Python to locate the installed `django_fundamentals` package.

Deploy (Ansible, Apache + mod_wsgi-express + MariaDB on Ubuntu 24.04):

```bash
cd deploy/deploy-sherlog
ansible-playbook -i inventory site.yml --extra-vars "db_password=… django_secret_key=…"
```

Re-running the playbook is also the code-update path.

## Architecture

**Everything user-facing comes from `django_fundamentals`, not from this repo.** `sherlog/urls.py` includes `django_fundamentals.urls` at `/`, giving the homepage, auth pages (`/accounts/…`), the `/settings/` page (profile, emails, password, API token) and avatar serving. This repo contains only project config, overrides and (eventually) domain apps.

- **`sherlog/settings.py`** imports uppercase names from `django_fundamentals.settings` and re-exports them by virtue of being in module namespace — the `BASE_*` lists (`BASE_INSTALLED_APPS`, `BASE_MIDDLEWARE`, …) are meant to be spread and extended, not replaced. `AUTH_USER_MODEL` is `django_fundamentals.User`.
- **Environment switch**: `DJANGO_ENV=production` selects MySQL/MariaDB + SMTP; otherwise SQLite + the console email backend. Production secrets come from env vars written by the Ansible `env.j2` template.
- **Email verification is mandatory for signup.** In development the confirmation link is printed to the `runserver` console and shown on the "verify your email" page while `DEBUG` is on, so no SMTP setup is needed.
- **Media**: profile pictures go to `MEDIA_ROOT` (`media/`) and are served by a django-fundamentals *view*. There is deliberately no `MEDIA_URL` and no web-server alias — do not add one.

### Adding features

- New Django apps live in `apps/<name>/` and must be added to `INSTALLED_APPS` in `sherlog/settings.py` and wired into `sherlog/urls.py` below the `django_fundamentals.urls` include.
- Sidebar links are data, not templates: edit `DJANGO_FUNDAMENTALS_SIDEBAR_NAV` in settings. An entry with `"section"` is a heading; an unreversable `url_name` is skipped silently rather than raising.

### Styling

- **`static/src/tokens.css` is the single entry point** for colours, sidebar width, navbar height, radius and fonts, for both light and dark themes. Colours are space-separated RGB channels (not hex) so Tailwind opacity modifiers work. Dark mode re-declares the same variable names under `.dark` at the bottom of the same file.
- The semantic-name → CSS-variable mapping lives in the django-fundamentals Tailwind preset, so it updates via `pip install -U django-fundamentals`.
- `tailwind.config.js` scans the installed package's templates *and* its Python (some class strings are built in code). Editing `content` to drop those globs silently purges the chrome's classes and the app renders unstyled.
- To override a component, drop a file at the matching path under `templates/` (e.g. `templates/django_fundamentals/organisms/footer.html`) — `templates/` is first in `TEMPLATES[0]["DIRS"]`.
- `static/css/tailwind.css` is a build artefact and gitignored, but the Ansible deploy rsyncs the working directory and runs `collectstatic` without an npm build on the server — build the CSS locally before deploying.

## Modules

@~/.claude/modules/code/python/code_python_django_fundamentals.md

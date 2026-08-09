# sherlog

Tools to test and debug the Sherlock contextual classifier for astronomical transients.

Built on [django-fundamentals](https://github.com/thespacedoctor/django-fundamentals) —
update it with `pip install -U django-fundamentals` to pull in shared
auth/permissions/frontend improvements.

## Development

```bash
conda create -n sherlog pip -c conda-forge
conda activate sherlog
pip install -e ".[dev]"
npm install
npm run build:css
python manage.py migrate
python manage.py runserver
```

Then open <http://127.0.0.1:8000/> and sign up with a username and email. Email
verification is required, but in development the confirmation link is shown
directly on the "verify your email" page (and printed to the `runserver`
console), so no SMTP setup is needed to get a working account. You can log in
with either your username or your email address.

## User settings

Signed-in users get a `/settings/` page, reached from the avatar at the top
right, with tabs for their profile, email addresses, password and API token.

Profile pictures are written to `media/` (`MEDIA_ROOT` in
`sherlog/settings.py`) and served by django-fundamentals
through a Django view — there is deliberately no `MEDIA_URL` and no Apache
`Alias` to configure, in development or production. Users without a picture are
shown their initials. Back up `media/` alongside your database.

> **Activate the environment before `npm run build:css`.** The Tailwind build
> asks Python where `django_fundamentals` is installed so it can scan that
> package's templates; without it the build stops with an explanatory error.
> You can also point it explicitly: `PYTHON=/path/to/python npm run build:css`.

Keep `npm run watch:css` running in a second terminal while you work on
templates.

## Changing the look

**`static/src/tokens.css` is the single entry point** for colours, sidebar
width, navbar height, corner radius and fonts — for both light and dark themes.
Edit it, re-run `npm run build:css`, done.

The chrome's *content* is configured in `sherlog/settings.py`:

- `DJANGO_FUNDAMENTALS_SITE_NAME` — shown in the title, brand mark and footer
- `DJANGO_FUNDAMENTALS_SIDEBAR_NAV` — the sidebar links and section headings.
  Account tools are not listed here; they live on the settings page.

To override a component outright, drop a file at the matching path under
`templates/`, e.g. `templates/django_fundamentals/organisms/footer.html`.
See django-fundamentals' `docs/source/ui.md` for the full component list.

## Deploy

See `deploy/deploy-sherlog/` for the Ansible
playbook (Apache + mod_wsgi-express + MariaDB on Ubuntu 24.04 /
DigitalOcean).

Production SMTP (including a Gmail App Password walkthrough) is documented in
django-fundamentals' `docs/source/email.md`.

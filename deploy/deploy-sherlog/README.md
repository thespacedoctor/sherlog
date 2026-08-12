# deploy-sherlog

Ansible playbook that deploys sherlog to a Ubuntu
24.04 droplet: Apache (reverse-proxying to mod_wsgi-express on :8090) + MariaDB.

## Requirements

```bash
ansible-galaxy collection install -r requirements.yml
pip install passlib
npm install --prefix ../..
```

`passlib` runs locally (not on the target) — it's needed to hash
`deploy_user_password` before it's written to the target account. `npm
install` provides the `tailwindcss` CLI — `install-webapp` runs `npm run
build:css` on your machine (not the target) before every sync, so the
compiled `static/css/tailwind.css` is always fresh and never depends on you
remembering to build it yourself.

`tailwind.config.js` introspects `django_fundamentals` via `python`, which it
needs to find on `PATH` — `install-webapp` runs the build through `conda run
-n sherlog` so it always uses the right environment regardless of what's
active in your shell. This does mean the local `sherlog` conda env must
exist (`conda env list` to check) and `conda` itself must be on `PATH`.

## Database

`install-mariadb` installs and starts MariaDB, creates the `sherlog` database
(utf8mb4) and the `sherlog` user with all privileges on it, using the
`db_password` you pass in below. `install-webapp` then writes those same
credentials into the environment file Apache reads, so the app finds the
database with no further configuration.

## Application secrets and ALLOWED_HOSTS

`install-webapp` writes `django_secret_key` and `ansible_host` (as
`DJANGO_ALLOWED_HOSTS`) into the same environment file as the database
credentials. `mod_wsgi-express` is pointed at that file via
`--envvars-script`, so the running app picks all of it up automatically —
`settings.py` reads `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` from the
environment rather than hardcoding them. The `migrate`/`collectstatic` tasks
also get the same variables directly (they run outside Apache, before the
vhost even exists).

## Run

```bash
ansible-playbook -i inventory site.yml -K \
  --extra-vars "ansible_host=TARGET_IP deploy_user=deploy deploy_user_password=CHANGE_ME db_password=CHANGE_ME django_secret_key=CHANGE_ME"
```

`ansible_host` is required on every run — the inventory no longer hardcodes a
target address, so `TARGET_IP` (or hostname) selects which machine gets
deployed to. It also becomes the Apache `ServerName` in the generated vhost.

The first play always connects as `root` (the only account that exists on a
fresh droplet) and bootstraps `deploy_user`: creates the account, adds it to
`sudo`, sets its login password from `deploy_user_password`, and copies
root's `authorized_keys` across so the same SSH key that reaches root also
reaches the new account. This is idempotent — safe to leave in every run,
including redeploys where the account already exists.

The second play (the actual app install) then connects as `deploy_user`
instead of root. `-K` prompts interactively for that user's sudo password —
nothing is passed in plaintext on the command line or committed to this
repo.

Prefer `ansible-vault` over `--extra-vars` on the command line for real
secrets. Re-run this playbook any time you want to push a code update —
`install-webapp` re-syncs the code, re-installs the package into the app's
conda environment, re-runs migrations/collectstatic, and reloads
mod_wsgi-express.

## Python environment

The app runs inside a Miniforge-managed conda environment at
`/home/sherlog/miniforge3/envs/sherlog` (installed and created automatically
by `install-webapp`), not a system Python or venv.

## On the deployed machine

Every deploy writes `/home/sherlog/README.md` on the target host, with start
and stop commands for Apache, MariaDB, mod_wsgi-express, and how to activate
the app's conda environment for one-off management commands.

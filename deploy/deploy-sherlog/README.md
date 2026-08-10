# deploy-sherlog

Ansible playbook that deploys sherlog to a Ubuntu
24.04 droplet: Apache (reverse-proxying to mod_wsgi-express on :8090) + MariaDB.

## Requirements

```bash
ansible-galaxy collection install -r requirements.yml
```

## Database

`install-mariadb` installs and starts MariaDB, creates the `sherlog` database
(utf8mb4) and the `sherlog` user with all privileges on it, using the
`db_password` you pass in below. `install-webapp` then writes those same
credentials into the environment file Apache reads, so the app finds the
database with no further configuration.

## Run

```bash
ansible-playbook -i inventory site.yml \
  --extra-vars "db_password=CHANGE_ME django_secret_key=CHANGE_ME"
```

Prefer `ansible-vault` over `--extra-vars` on the command line for real
secrets. Re-run this playbook any time you want to push a code update —
`install-webapp` re-syncs the code, re-installs the package, re-runs
migrations/collectstatic, and reloads mod_wsgi-express.

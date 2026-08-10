# Changes

* **FEATURE**: development can now run against either SQLite (default) or the local MariaDB via `DJANGO_DB`, with settings and secrets read from an uncommitted `.env`. Production is unchanged and always uses MariaDB.
* **FEATURE**: added `scripts/create_dev_db.sh` to create the local MariaDB database, user and grant from the values in `.env`.
* **ENHANCEMENT**: `import_transients` now takes each row's `origin` from the CSV when present, falling back to `--origin`.
* **ENHANCEMENT**: `Transient.origin` widened from 30 to 75 characters so it can hold a broker filter URL.
* **FIXED**: the Ansible MariaDB role now installs the MySQL client headers and `pkg-config` needed to build `mysqlclient`, creates the database as utf8mb4, and declares its `community.mysql` dependency in `requirements.yml`.

* **FEATURE**: added the `transient` resource — a `Transient` model (uuid, ra, decl, name, origin, url), the five-method singular API at `/api/transient/`, a paginated list API at `/api/transients/`, and matching UI pages at `/transient/`, `/transient/<uuid>/` and `/transients/`.
* **FEATURE**: each transient's page now shows an Aladin Lite v3 sky view of its position, ringed in red, using the deepest survey that covers it — DESI Legacy DR10, then Pan-STARRS DR1, then SDSS9, falling back to DSS2.
* **FEATURE**: added the `import_transients` management command and bundled the 920-object Lasair COSMOS debugging sample it loads by default.

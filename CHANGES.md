# Changes

* **FEATURE**: every transient page now lists the sources Sherlock matched against the transient, read straight from Sherlock's own `sherlock_crossmatches` table. One row per ranked source, best first; where Sherlock merged the same source across several catalogues the row is marked `multiple` and expands to show the individual catalogue matches behind it.
* **FEATURE**: above that table, Sherlock's verdict from `sherlock_classifications` — the classification, its one-line summary and its annotation.
* **REFACTOR**: the transient summary now puts the attributes table above the Aladin sky view, with the crossmatches below it.
* **FEATURE**: added the `sherlock` app, holding unmanaged read-only mirrors of `sherlock_crossmatches` and `sherlock_classifications`. Sherlock creates and owns both tables, so Django never migrates them; the test suite builds them with the schema editor instead.

* **FEATURE**: transients gained a `sherlock_classification` field (10 characters, NULL until Sherlock has classified the transient), exposed in the API, searchable and sortable in the transient and vetting tables, and shown on the detail page and in the admin. The API spells "unclassified" as `null` and rejects `""`, so there is only ever one empty state.

* **REFACTOR**: the transient table is now named `transients` rather than Django's default `transients_transient`, matching the explicitly named `sherlock_vetting` table.

* **FEATURE**: added a human vetting workflow. The `sherlock_vetting` table records, per Sherlock version, whether each transient was classified correctly, by whom, with an optional comment and the rank of the correct host.
* **FEATURE**: each version gets a vetting page with four tabbed tables — all transients, unvetted, correct and incorrect — each showing its count, and a sidebar entry under "Vetting runs".
* **FEATURE**: transients opened from a vetting run gain a form with green "correct" and red "incorrect" buttons; submitting moves straight on to a random unvetted transient, or back to the run page once none are left.
* **FEATURE**: added the `create_vetting_run` management command, which opens a run by creating one unvetted row per transient.
* **REFACTOR**: the list search, sorting and pagination moved out of `TransientListView` into a reusable `SortableSearchableListMixin`, and the transient sky view and attribute table into a shared `transient_summary.html`, so the vetting pages reuse them rather than copying.

* **FEATURE**: development can now run against either SQLite (default) or the local MariaDB via `DJANGO_DB`, with settings and secrets read from an uncommitted `.env`. Production is unchanged and always uses MariaDB.
* **FEATURE**: added `scripts/create_dev_db.sh` to create the local MariaDB database, user and grant from the values in `.env`.
* **ENHANCEMENT**: `import_transients` now takes each row's `origin` from the CSV when present, falling back to `--origin`.
* **ENHANCEMENT**: `Transient.origin` widened from 30 to 75 characters so it can hold a broker filter URL.
* **FIXED**: the Ansible MariaDB role now installs the MySQL client headers and `pkg-config` needed to build `mysqlclient`, creates the database as utf8mb4, and declares its `community.mysql` dependency in `requirements.yml`.

* **FEATURE**: added the `transient` resource — a `Transient` model (uuid, ra, decl, name, origin, url), the five-method singular API at `/api/transient/`, a paginated list API at `/api/transients/`, and matching UI pages at `/transient/`, `/transient/<uuid>/` and `/transients/`.
* **FEATURE**: each transient's page now shows an Aladin Lite v3 sky view of its position, ringed in red, using the deepest survey that covers it — DESI Legacy DR10, then Pan-STARRS DR1, then SDSS9, falling back to DSS2.
* **FEATURE**: added the `import_transients` management command and bundled the 920-object Lasair COSMOS debugging sample it loads by default.

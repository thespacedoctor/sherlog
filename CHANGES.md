# Changes

* **FEATURE**: added the `transient` resource — a `Transient` model (uuid, ra, decl, name, origin, url), the five-method singular API at `/api/transient/`, a paginated list API at `/api/transients/`, and matching UI pages at `/transient/`, `/transient/<uuid>/` and `/transients/`.
* **FEATURE**: each transient's page now shows an Aladin Lite v3 sky view of its position, ringed in red, using the deepest survey that covers it — DESI Legacy DR10, then Pan-STARRS DR1, then SDSS9, falling back to DSS2.
* **FEATURE**: added the `import_transients` management command and bundled the 920-object Lasair COSMOS debugging sample it loads by default.

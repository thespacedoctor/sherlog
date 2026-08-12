# Changes

* **FEATURE**: the triage form gained a third, amber "Ambiguous" verdict alongside Correct/Incorrect, for transients where it's unclear which source is even associated with them — a tooltip on the button explains why. `sherlock_correct` moved from a boolean to a `correct`/`incorrect`/`ambiguous` choice field (still `NULL` for unvetted), so the run page's tabs, counts and the shared transient table's "Vetted as" column all carry a fourth outcome now, not just three.

* **REFACTOR**: vetting runs are keyed on the Sherlock version that produced the data, not on a version typed in by hand. `create_vetting_run` with no argument opens a run for every version in `sherlock_classifications`, covering only the transients that version classified. The made-up `v0.0.0` run has been retired in favour of the real `v3.1.0`.
* **ENHANCEMENT**: the crossmatch table and sky view show one Sherlock version at a time — the run's version on the vetting page, the newest present on the plain transient page — so two runs' ranks can never be interleaved. The "Sherlock says" block names the version it came from, because that table keeps only the latest run's verdict whatever version is being vetted.
* **ENHANCEMENT**: the crossmatch table gained a `Search radius ″` column in the Sherlock group. A merged lead reads as an em-dash rather than 0.00 — Sherlock writes the string "multiple" into that numeric column, so zero means "no single value", not a zero-radius search.
* **REFACTOR**: the triage form asks one question at a time. It opens on nothing but Correct/Incorrect radios and a disabled submit; a verdict reveals the comment box; "incorrect" reveals the reason; "other" reveals a box to type a new one; and "wrong rank" or "correct association - incorrect classification" reveal the one further answer each needs. Every rule is enforced in `clean()` as well as in the markup, so it holds with JavaScript off.

* **REFACTOR**: `Transient.origin` is now `origin_url`, with a new `origin_name` beside it, so the tables can show a readable name that links to the broker filter rather than a bare URL. Existing rows keep their URL and are named "lasair filter". The API renames with it — `origin` is gone in favour of `origin_url` and `origin_name`, and `?search=`/`?ordering=` follow.
* **ENHANCEMENT**: the transient tables lost the UUID and Added columns and the detail page lost UUID, Added and Updated — record-keeping a vetter never needs. `Name` is now `Transient ID`, opening the transient here with a second icon out to the broker, and `Classification` is now `Sherlock Classification`.
* **ENHANCEMENT**: the crossmatch table's group banners are centred, its group dividers darker and its two header rows much fainter, so the rank colours carry the eye instead of the chrome.
* **FEATURE**: clicking a source on the sky view outlines its row in the crossmatch table, and clicking a row highlights its circle — the two are one thing now.
* **FEATURE**: where a catalogue gives the source a semi-major axis it is drawn as a thinner dashed circle in the same colour, with a legend below the sky view keying both circle styles.
* **FEATURE**: the sky view's pill gained a third setting — hide sources, merged sources (the default) or all sources — and each ranked circle carries its rank number at its centre.
* **FIXED**: the overlay-layers button sits below the fullscreen button and its menu opens leftwards instead of off the edge of the view. Aladin injects its stylesheet into the container at runtime, so the override needed more specificity than a single class, not just different values.
* **FEATURE**: the triage form asks why a classification is wrong, from a dropdown of reasons shared by everyone vetting that Sherlock version. A vetter can add a reason and it is offered from then on. "wrong rank" always appears and forces the correct rank to be picked; "correct association - incorrect classification" asks what the classification should have been, from Sherlock's own codes.
* **ENHANCEMENT**: the correct/incorrect buttons moved to the right, incorrect first, in muted colours; and the host rank is a dropdown of that transient's own ranked matches rather than a free number.

* **FEATURE**: the sky view now rings every source Sherlock matched, each circle drawn at the radius the search that found it used, centred on the source — so the circle is the association boundary the transient fell inside. One Aladin overlay per rank, named for it, so the layers control can turn them on and off individually. A control on the view toggles between the ranked lead sources and the individual catalogue matches merged into them.
* **FEATURE**: each ranked source has a colour, carried by both its circle and its table row, which is banded down the left edge of the row. Ranks past the eighth share one muted colour. The hues are tokens (`--color-rank-*`) in `tokens.css`, mirrored in `sky_view.js` because Aladin paints onto a canvas and cannot follow the theme toggle.
* **ENHANCEMENT**: the crossmatch table's 22 columns are now bannered into four groups — Sherlock, Catalogue, Separation and Distance — and `catalogue_view_name` joins the Sherlock group. `Catalogue` was renamed `Cat name` so it no longer collides with the group above it.
* **ENHANCEMENT**: the transient's own marker shrank from 5″ to 0.5″ and its overlay is now named "transient" rather than Aladin's default "overlay".
* **ENHANCEMENT**: the sky view drops the coordinate-system dropdown, the projection selector and the search box, and the overlay-layers button moved beside the fullscreen button. Note that in Aladin v3 the search box and the coordinate readout are one widget, so the readout went with it.

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

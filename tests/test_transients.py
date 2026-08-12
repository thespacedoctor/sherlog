import re
import uuid as uuidlib
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.utils import IntegrityError

from apps.transients.models import Transient

CSV_ROWS = """diaObjectId,ra,decl,uurl
111111111111111111,148.61201,1.609392,https://lasair.lsst.ac.uk/objects/111111111111111111
222222222222222222,151.34058,2.800159,https://lasair.lsst.ac.uk/objects/222222222222222222
333333333333333333,150.43968,-2.541448,https://lasair.lsst.ac.uk/objects/333333333333333333
"""


@pytest.fixture
def csv_file(tmp_path):
    """*a three-row broker CSV on disk*"""
    path = tmp_path / "sample.csv"
    path.write_text(CSV_ROWS, encoding="utf-8")
    return path


@pytest.fixture
def transient(db):
    """*one saved transient*"""
    return Transient.objects.create(
        name="313853517460144141",
        origin_name="lasair filter",
        ra=148.61201,
        decl=1.609392,
        url="https://lasair.lsst.ac.uk/objects/313853517460144141",
    )


def make_transients(count, origin_name="lasair filter"):
    """*bulk-create ``count`` transients with predictable names*"""
    return Transient.objects.bulk_create(
        Transient(name=f"obj{index:04d}", origin_name=origin_name, ra=float(index % 360), decl=float(index % 90))
        for index in range(count)
    )


# --- MODEL -----------------------------------------------------------------


def test_uuid_is_assigned_and_is_the_pk(transient):
    assert isinstance(transient.uuid, uuidlib.UUID)
    assert transient.pk == transient.uuid


def test_str_is_the_name(transient):
    assert str(transient) == "313853517460144141"


def test_absolute_url_points_at_the_detail_page(transient):
    assert transient.get_absolute_url() == f"/transient/{transient.uuid}/"


def test_sherlock_classification_defaults_to_null(transient):
    # NULL, NOT "", SO "SHERLOCK HAS NOT RUN" IS ITS OWN STATE.
    assert transient.sherlock_classification is None


@pytest.mark.django_db
def test_name_and_origin_url_are_unique_together(transient):
    with pytest.raises(IntegrityError):
        Transient.objects.create(name=transient.name, origin_url=transient.origin_url, ra=1.0, decl=1.0)


@pytest.mark.django_db
def test_out_of_range_coordinates_fail_validation():
    with pytest.raises(ValidationError):
        Transient(name="bad", origin_name="lasair filter", ra=400.0, decl=0.0).full_clean()


# --- IMPORT COMMAND --------------------------------------------------------


@pytest.mark.django_db
def test_import_creates_rows_then_updates_them(csv_file):
    output = StringIO()
    call_command("import_transients", str(csv_file), stdout=output)
    assert "3 created, 0 updated, 0 skipped" in output.getvalue()
    assert Transient.objects.count() == 3

    imported = Transient.objects.get(name="111111111111111111")
    assert imported.origin_name == "lasair filter"
    assert imported.ra == pytest.approx(148.61201)
    assert imported.url.endswith("/111111111111111111")

    # RE-RUNNING MUST UPSERT, NOT DUPLICATE
    output = StringIO()
    call_command("import_transients", str(csv_file), stdout=output)
    assert "0 created, 3 updated, 0 skipped" in output.getvalue()
    assert Transient.objects.count() == 3


@pytest.mark.django_db
def test_import_origin_flag(csv_file):
    call_command("import_transients", str(csv_file), origin_name="ztf", stdout=StringIO())
    assert Transient.objects.filter(origin_name="ztf").count() == 3


@pytest.mark.django_db
def test_import_prefers_the_csv_origin_column(tmp_path):
    path = tmp_path / "mixed.csv"
    path.write_text(
        "name,ra,decl,url,origin\n"
        "111111111111111111,148.6,1.6,https://example.org/1,https://example.org/f/1\n"
        "222222222222222222,151.3,2.8,https://example.org/2,https://example.org/f/2\n"
        # BLANK CELL — FALLS BACK TO --origin-url
        "333333333333333333,150.4,-2.5,https://example.org/3,\n",
        encoding="utf-8",
    )
    call_command(
        "import_transients", str(path), origin_url="https://example.org/f/fallback", stdout=StringIO()
    )

    origins = dict(Transient.objects.values_list("name", "origin_url"))
    assert origins["111111111111111111"] == "https://example.org/f/1"
    assert origins["222222222222222222"] == "https://example.org/f/2"
    assert origins["333333333333333333"] == "https://example.org/f/fallback"


@pytest.mark.django_db
def test_import_dry_run_writes_nothing(csv_file):
    output = StringIO()
    call_command("import_transients", str(csv_file), dry_run=True, stdout=output)
    assert "DRY RUN" in output.getvalue()
    assert Transient.objects.count() == 0


@pytest.mark.django_db
def test_import_skips_unusable_rows(tmp_path):
    path = tmp_path / "messy.csv"
    path.write_text(
        "diaObjectId,ra,decl,uurl\n"
        "111111111111111111,148.6,1.6,https://example.org/1\n"
        "222222222222222222,not-a-number,2.8,https://example.org/2\n"
        "333333333333333333,999.9,3.1,https://example.org/3\n",
        encoding="utf-8",
    )
    output = StringIO()
    call_command("import_transients", str(path), stdout=output, stderr=StringIO())
    assert "1 created, 0 updated, 2 skipped" in output.getvalue()


@pytest.mark.django_db
def test_import_rejects_a_csv_with_the_wrong_columns(tmp_path):
    path = tmp_path / "wrong.csv"
    path.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(Exception) as excinfo:
        call_command("import_transients", str(path), stdout=StringIO(), stderr=StringIO())
    assert "missing a column" in str(excinfo.value)


# --- UI --------------------------------------------------------------------


@pytest.mark.django_db
def test_index_page_loads_for_anonymous(client):
    response = client.get("/transient/")
    assert response.status_code == 200
    assert b"/api/transients/" in response.content


@pytest.mark.django_db
def test_detail_page_loads_for_anonymous(client, transient):
    response = client.get(f"/transient/{transient.uuid}/")
    assert response.status_code == 200
    assert transient.name.encode() in response.content


@pytest.mark.django_db
def test_detail_page_carries_the_sky_view(client, transient):
    content = client.get(f"/transient/{transient.uuid}/").content.decode()
    assert "data-sky-view" in content
    # THE COORDINATES THE JAVASCRIPT READS MUST BE THE MODEL'S OWN
    assert 'data-ra="148.612010"' in content
    assert 'data-decl="1.609392"' in content
    assert "vendor/aladin/aladin-3.8.2.js" in content
    assert "js/sky_view.js" in content


@pytest.mark.django_db
def test_detail_page_offers_every_reference_catalogue(client, transient):
    content = client.get(f"/transient/{transient.uuid}/").content.decode()
    assert "data-sky-view-catalogues" in content
    # THE ids HERE ARE THE KEYS sky_view.js LOOKS ITS BUILDERS UP BY, SO A RENAME
    # ON EITHER SIDE ALONE HAS TO FAIL.
    for catalogue in ("desi-dr10", "gaia-dr3", "sdss-dr12", "simbad", "ned"):
        assert f'data-sky-view-catalogue="{catalogue}"' in content


@pytest.mark.django_db
def test_reference_catalogues_are_all_off_by_default(client, transient):
    """OFF BY DEFAULT IS A SERVER-SIDE GUARANTEE, NOT SOMETHING JAVASCRIPT UNDOES:
    EACH TICKED BOX COSTS A CONE SEARCH ON EVERY PAGE LOAD."""
    content = client.get(f"/transient/{transient.uuid}/").content.decode()
    for element in re.findall(r"<input[^>]*data-sky-view-catalogue[^>]*>", content):
        assert "checked" not in element


@pytest.mark.django_db
def test_only_the_detail_page_loads_aladin(client, transient):
    for path in ("/transient/", "/transients/"):
        assert b"aladin.js" not in client.get(path).content


@pytest.mark.django_db
def test_list_page_paginates_at_fifty(client):
    make_transients(60)
    response = client.get("/transients/")
    assert response.status_code == 200
    assert len(response.context["transients"]) == 50
    assert response.context["paginator"].count == 60


@pytest.mark.django_db
def test_list_page_search_narrows_the_queryset(client, transient):
    Transient.objects.create(name="other", origin_name="ztf", ra=10.0, decl=10.0)
    response = client.get("/transients/", {"q": "ztf"})
    assert [t.name for t in response.context["transients"]] == ["other"]


@pytest.mark.django_db
def test_list_page_search_matches_the_classification(client, transient):
    Transient.objects.create(
        name="other", origin_name="ztf", ra=10.0, decl=10.0, sherlock_classification="SN"
    )
    response = client.get("/transients/", {"q": "SN"})
    assert [t.name for t in response.context["transients"]] == ["other"]


@pytest.mark.django_db
def test_list_page_sorts_on_a_whitelisted_column(client):
    make_transients(3)
    response = client.get("/transients/", {"sort": "ra", "dir": "desc"})
    values = [t.ra for t in response.context["transients"]]
    assert values == sorted(values, reverse=True)


@pytest.mark.django_db
def test_list_page_ignores_an_unknown_sort_column(client):
    make_transients(3)
    response = client.get("/transients/", {"sort": "url; DROP TABLE"})
    assert response.status_code == 200
    assert response.context["sort_field"] == "name"


@pytest.mark.django_db
def test_htmx_request_returns_only_the_table(client, transient):
    response = client.get("/transients/", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert b"<html" not in response.content
    assert b'id="transient-table"' in response.content


# --- API -------------------------------------------------------------------


@pytest.mark.django_db
def test_api_list_is_public_and_paginated(client):
    make_transients(60)
    response = client.get("/api/transients/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 60
    assert len(payload["results"]) == 50


@pytest.mark.django_db
def test_api_list_search_and_ordering(client):
    make_transients(3)
    Transient.objects.create(name="ztf-one", origin_name="ztf", ra=5.0, decl=5.0)

    response = client.get("/api/transients/", {"search": "ztf"})
    assert [row["name"] for row in response.json()["results"]] == ["ztf-one"]

    response = client.get("/api/transients/", {"ordering": "-ra"})
    values = [row["ra"] for row in response.json()["results"]]
    assert values == sorted(values, reverse=True)


@pytest.mark.django_db
def test_api_exposes_the_classification_and_accepts_a_write(client, transient):
    response = client.get(f"/api/transient/{transient.uuid}/")
    assert response.json()["sherlock_classification"] is None

    user = get_user_model().objects.create_user(username="dave", email="dave@example.org", password="pw")
    client.force_login(user)
    response = client.patch(
        f"/api/transient/{transient.uuid}/",
        data={"sherlock_classification": "SN"},
        content_type="application/json",
    )
    assert response.status_code == 200
    transient.refresh_from_db()
    assert transient.sherlock_classification == "SN"

    # CLEARING IT MEANS null; "" IS REJECTED RATHER THAN STORED AS A SECOND
    # EMPTY STATE.
    response = client.patch(
        f"/api/transient/{transient.uuid}/",
        data={"sherlock_classification": None},
        content_type="application/json",
    )
    assert response.status_code == 200
    transient.refresh_from_db()
    assert transient.sherlock_classification is None

    response = client.patch(
        f"/api/transient/{transient.uuid}/",
        data={"sherlock_classification": ""},
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_api_detail_is_public(client, transient):
    response = client.get(f"/api/transient/{transient.uuid}/")
    assert response.status_code == 200
    assert response.json()["name"] == transient.name


@pytest.mark.django_db
def test_api_write_requires_authentication(client, transient):
    # 401 RATHER THAN 403: TokenAuthentication IS FIRST IN
    # DEFAULT_AUTHENTICATION_CLASSES AND SUPPLIES A WWW-Authenticate HEADER, SO
    # DRF ANSWERS AN ANONYMOUS WRITE WITH "UNAUTHORIZED".
    payload = {"name": "new", "origin_name": "lasair filter", "ra": 1.0, "decl": 1.0}
    assert client.post("/api/transient/", payload).status_code == 401
    assert client.patch(
        f"/api/transient/{transient.uuid}/", {"ra": 2.0}, content_type="application/json"
    ).status_code == 401
    assert client.delete(f"/api/transient/{transient.uuid}/").status_code == 401
    assert Transient.objects.count() == 1


@pytest.mark.django_db
def test_api_crud_as_an_authenticated_user(client, transient):
    user = get_user_model().objects.create_user(username="dave", email="dave@example.org", password="pw")
    client.force_login(user)

    response = client.post("/api/transient/", {"name": "new", "origin_name": "lasair filter", "ra": 1.0, "decl": 1.0})
    assert response.status_code == 201
    newUuid = response.json()["uuid"]

    response = client.patch(
        f"/api/transient/{newUuid}/", {"ra": 2.5}, content_type="application/json"
    )
    assert response.status_code == 200
    assert response.json()["ra"] == 2.5

    response = client.put(
        f"/api/transient/{newUuid}/",
        {"name": "renamed", "origin_name": "lasair filter", "ra": 3.0, "decl": -3.0, "url": ""},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["name"] == "renamed"

    assert client.delete(f"/api/transient/{newUuid}/").status_code == 204
    assert Transient.objects.count() == 1


@pytest.mark.django_db
def test_api_rejects_a_duplicate_name_and_origin(client, transient):
    user = get_user_model().objects.create_user(username="dave", email="dave@example.org", password="pw")
    client.force_login(user)
    response = client.post(
        "/api/transient/", {"name": transient.name, "origin_url": transient.origin_url, "ra": 1.0, "decl": 1.0}
    )
    assert response.status_code == 400


# --- THE ORIGIN SPLIT -------------------------------------------------------


@pytest.mark.django_db
def test_the_bundled_csv_origin_column_feeds_the_url(csv_file):
    """*the sample's `origin` header holds a filter URL, not a name*"""
    path = csv_file.parent / "urls.csv"
    path.write_text(
        "name,ra,decl,url,origin\n"
        "444444444444444444,10.0,10.0,https://example.org/4,https://example.org/filters/9/\n",
        encoding="utf-8",
    )
    call_command("import_transients", str(path), stdout=StringIO())

    imported = Transient.objects.get(name="444444444444444444")
    assert imported.origin_url == "https://example.org/filters/9/"
    # NOTHING IN THE CSV NAMES THE FILTER, SO THE FLAG'S DEFAULT DOES.
    assert imported.origin_name == "lasair filter"


@pytest.mark.django_db
def test_the_api_exposes_both_origin_fields(client, transient):
    payload = client.get(f"/api/transient/{transient.uuid}/").json()

    assert "origin" not in payload
    assert payload["origin_name"] == transient.origin_name
    assert payload["origin_url"] == transient.origin_url


@pytest.mark.django_db
def test_the_list_table_drops_the_uuid_and_added_columns(client, transient):
    content = client.get("/transients/").content.decode()

    assert ">UUID</th>" not in content
    assert ">Added</th>" not in content
    assert "Transient ID" in content
    assert "Sherlock Classification" in content


@pytest.mark.django_db
def test_the_transient_id_opens_the_detail_page_and_the_broker(client, transient):
    content = client.get("/transients/").content.decode()

    assert f'href="/transient/{transient.uuid}/"' in content
    assert f'href="{transient.url}"' in content


@pytest.mark.django_db
def test_the_origin_links_out_by_name(client, transient):
    transient.origin_url = "https://example.org/filters/9/"
    transient.save()

    content = client.get("/transients/").content.decode()

    assert 'href="https://example.org/filters/9/"' in content
    assert "lasair filter" in content


@pytest.mark.django_db
def test_the_detail_page_hides_the_record_keeping(client, transient):
    content = client.get(f"/transient/{transient.uuid}/").content.decode()

    assert ">UUID</th>" not in content
    assert ">Added</th>" not in content
    assert ">Updated</th>" not in content
    assert ">Sherlock Classification</th>" in content

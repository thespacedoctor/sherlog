from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.utils import IntegrityError

from apps.transients.models import Transient
from apps.vetting.models import SherlockVetting

VERSION = "v0.0.0"


@pytest.fixture
def transients(db):
    """*five transients to vet*"""
    return Transient.objects.bulk_create(
        Transient(name=f"obj{index:03d}", origin="lasair", ra=float(index), decl=float(index))
        for index in range(5)
    )


@pytest.fixture
def run(transients):
    """*an open vetting run over those transients*"""
    call_command("create_vetting_run", VERSION, stdout=StringIO())
    return SherlockVetting.objects.filter(sherlock_version=VERSION)


@pytest.fixture
def vetter(db):
    """*a signed-up user who can vet*"""
    return get_user_model().objects.create_user(
        username="dave", email="dave@example.org", password="pw"
    )


# --- MODEL AND RUN CREATION -------------------------------------------------


def test_run_creates_one_unvetted_row_per_transient(run, transients):
    assert run.count() == len(transients)
    assert run.filter(sherlock_correct__isnull=True).count() == len(transients)


def test_create_vetting_run_is_idempotent(run):
    output = StringIO()
    call_command("create_vetting_run", VERSION, stdout=output)
    assert "0 created" in output.getvalue()
    assert run.count() == 5


@pytest.mark.django_db
def test_one_row_per_transient_per_version(run, transients):
    with pytest.raises(IntegrityError):
        SherlockVetting.objects.create(transient=transients[0], sherlock_version=VERSION)


def test_verdict_reads_back_as_words(run):
    vetting = run.first()
    assert vetting.verdict == "unvetted"
    vetting.sherlock_correct = True
    assert vetting.verdict == "correct"
    vetting.sherlock_correct = False
    assert vetting.verdict == "incorrect"


# --- RUN PAGE ---------------------------------------------------------------


def set_verdicts(run, correct=0, incorrect=0):
    """*mark the first rows of a run correct, then the next incorrect*"""
    rows = list(run.order_by("transient__name"))
    for vetting in rows[:correct]:
        vetting.sherlock_correct = True
        vetting.save()
    for vetting in rows[correct : correct + incorrect]:
        vetting.sherlock_correct = False
        vetting.save()


def test_tab_counts(client, run):
    set_verdicts(run, correct=2, incorrect=1)
    counts = {tab["name"]: tab["count"] for tab in client.get(f"/vetting/{VERSION}/").context["tabs"]}
    assert counts == {"all": 5, "unvetted": 2, "correct": 2, "incorrect": 1}


@pytest.mark.parametrize(
    "tab,expected",
    [("", 5), ("unvetted/", 2), ("correct/", 2), ("incorrect/", 1)],
)
def test_each_tab_lists_the_right_rows(client, run, tab, expected):
    set_verdicts(run, correct=2, incorrect=1)
    response = client.get(f"/vetting/{VERSION}/{tab}")
    assert response.status_code == 200
    assert len(response.context["transients"]) == expected


def test_vetted_as_column_renders_all_three_states(client, run):
    set_verdicts(run, correct=1, incorrect=1)
    content = client.get(f"/vetting/{VERSION}/").content.decode()
    assert "Vetted as" in content
    assert "not vetted" in content
    assert ">Correct<" in content
    assert ">Incorrect<" in content


def test_run_rows_link_to_the_vetting_page(client, run):
    vetting = run.first()
    content = client.get(f"/vetting/{VERSION}/").content.decode()
    assert f"/vetting/{VERSION}/transient/{vetting.transient_id}/" in content


def test_unknown_version_is_404(client, run):
    assert client.get("/vetting/v9.9.9/").status_code == 404


def test_run_page_search_and_sort_still_work(client, run):
    response = client.get(f"/vetting/{VERSION}/", {"q": "obj003"})
    assert [t.name for t in response.context["transients"]] == ["obj003"]

    response = client.get(f"/vetting/{VERSION}/", {"sort": "ra", "dir": "desc"})
    values = [t.ra for t in response.context["transients"]]
    assert values == sorted(values, reverse=True)


# --- VETTING FORM -----------------------------------------------------------


def test_vetting_requires_login(client, run):
    vetting = run.first()
    url = f"/vetting/{VERSION}/transient/{vetting.transient_id}/"

    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]

    client.post(url, {"verdict": "correct"})
    vetting.refresh_from_db()
    assert vetting.sherlock_correct is None


def test_vetting_page_shows_the_transient_and_form(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()
    content = client.get(f"/vetting/{VERSION}/transient/{vetting.transient_id}/").content.decode()
    assert "data-sky-view" in content
    assert 'name="verdict" value="correct"' in content
    assert 'name="verdict" value="incorrect"' in content


def test_posting_a_verdict_saves_and_moves_on(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()

    response = client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/",
        {"verdict": "correct", "user_comment": "clear host", "sherlock_correct_host": "2"},
    )

    vetting.refresh_from_db()
    assert vetting.sherlock_correct is True
    assert vetting.user_comment == "clear host"
    assert vetting.sherlock_correct_host == 2
    assert vetting.user == vetter

    # ON TO A DIFFERENT, STILL-UNVETTED TRANSIENT
    assert response.status_code == 302
    assert response["Location"].startswith(f"/vetting/{VERSION}/transient/")
    assert str(vetting.transient_id) not in response["Location"]


def test_incorrect_verdict_is_recorded_as_false(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()
    client.post(f"/vetting/{VERSION}/transient/{vetting.transient_id}/", {"verdict": "incorrect"})
    vetting.refresh_from_db()
    assert vetting.sherlock_correct is False


def test_vetting_the_last_one_returns_to_the_run_page(client, run, vetter):
    client.force_login(vetter)
    set_verdicts(run, correct=4)
    last = run.get(sherlock_correct__isnull=True)

    response = client.post(
        f"/vetting/{VERSION}/transient/{last.transient_id}/", {"verdict": "correct"}, follow=True
    )

    assert response.redirect_chain[-1][0] == f"/vetting/{VERSION}/"
    assert "All transients have now been vetted" in response.content.decode()


def test_a_bad_verdict_is_rejected(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()
    response = client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/", {"verdict": "maybe"}
    )
    assert response.status_code == 200
    vetting.refresh_from_db()
    assert vetting.sherlock_correct is None


# --- SIDEBAR ----------------------------------------------------------------


def test_sidebar_lists_a_version_once_a_run_exists(client, run):
    content = client.get("/transients/").content.decode()
    assert "Vetting runs" in content
    assert f'href="/vetting/{VERSION}/"' in content


@pytest.mark.django_db
def test_sidebar_has_no_vetting_section_without_runs(client):
    assert "Vetting runs" not in client.get("/transients/").content.decode()

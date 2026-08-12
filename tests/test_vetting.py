from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.utils import IntegrityError

from apps.sherlock.models import SherlockClassification, SherlockCrossmatch
from apps.transients.models import Transient
from apps.vetting.models import (
    DEFAULT_REASONS,
    OTHER_REASON,
    WRONG_RANK,
    SherlockVetting,
    VettingReason,
)

VERSION = "v0.0.0"


@pytest.fixture
def transients(db):
    """*five transients Sherlock has classified, so a run can cover them*

    A run is now derived from ``sherlock_classifications``, so a transient with
    no classification belongs to no run.
    """
    transients = Transient.objects.bulk_create(
        Transient(name=f"obj{index:03d}", origin_name="lasair filter", ra=float(index), decl=float(index))
        for index in range(5)
    )
    SherlockClassification.objects.bulk_create(
        SherlockClassification(transient=transient, classification="SN", sherlock_version=VERSION)
        for transient in transients
    )
    return transients


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
    vetting.sherlock_correct = "correct"
    assert vetting.verdict == "correct"
    vetting.sherlock_correct = "incorrect"
    assert vetting.verdict == "incorrect"
    vetting.sherlock_correct = "ambiguous"
    assert vetting.verdict == "ambiguous"


# --- RUN PAGE ---------------------------------------------------------------


def set_verdicts(run, correct=0, incorrect=0, ambiguous=0):
    """*mark the first rows of a run correct, then the next incorrect, then the next ambiguous*"""
    rows = list(run.order_by("transient__name"))
    for vetting in rows[:correct]:
        vetting.sherlock_correct = "correct"
        vetting.save()
    for vetting in rows[correct : correct + incorrect]:
        vetting.sherlock_correct = "incorrect"
        vetting.save()
    for vetting in rows[correct + incorrect : correct + incorrect + ambiguous]:
        vetting.sherlock_correct = "ambiguous"
        vetting.save()


def test_tab_counts(client, run):
    set_verdicts(run, correct=2, incorrect=1, ambiguous=1)
    counts = {tab["name"]: tab["count"] for tab in client.get(f"/vetting/{VERSION}/").context["tabs"]}
    assert counts == {"all": 5, "unvetted": 1, "correct": 2, "incorrect": 1, "ambiguous": 1}


@pytest.mark.parametrize(
    "tab,expected",
    [("", 5), ("unvetted/", 1), ("correct/", 2), ("incorrect/", 1), ("ambiguous/", 1)],
)
def test_each_tab_lists_the_right_rows(client, run, tab, expected):
    set_verdicts(run, correct=2, incorrect=1, ambiguous=1)
    response = client.get(f"/vetting/{VERSION}/{tab}")
    assert response.status_code == 200
    assert len(response.context["transients"]) == expected


def test_vetted_as_column_renders_all_states(client, run):
    set_verdicts(run, correct=1, incorrect=1, ambiguous=1)
    content = client.get(f"/vetting/{VERSION}/").content.decode()
    assert "Vetted as" in content
    assert "not vetted" in content
    assert ">Correct<" in content
    assert ">Incorrect<" in content
    assert ">Ambiguous<" in content


def test_vetted_as_column_shows_the_vetting_username(client, run, vetter):
    vetting = run.first()
    vetting.sherlock_correct = "correct"
    vetting.user = vetter
    vetting.save()
    content = client.get(f"/vetting/{VERSION}/").content.decode()
    assert "dave" in content


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
    assert 'name="verdict" value="ambiguous"' in content
    assert "Unclear which source is associated with the transient." in content


def test_posting_a_verdict_saves_and_moves_on(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()
    # THE HOST RANK IS A DROPDOWN OF THIS TRANSIENT'S OWN RANKS NOW, SO RANK 2
    # HAS TO EXIST BEFORE IT CAN BE CHOSEN.
    for rank in (1, 2):
        SherlockCrossmatch.objects.create(transient=vetting.transient, rank=rank, sherlock_version=VERSION)

    response = client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/",
        {"verdict": "correct", "user_comment": "clear host", "sherlock_correct_host": "2"},
    )

    vetting.refresh_from_db()
    assert vetting.sherlock_correct == "correct"
    assert vetting.user_comment == "clear host"
    assert vetting.sherlock_correct_host == 2
    assert vetting.user == vetter

    # ON TO A DIFFERENT, STILL-UNVETTED TRANSIENT
    assert response.status_code == 302
    assert response["Location"].startswith(f"/vetting/{VERSION}/transient/")
    assert str(vetting.transient_id) not in response["Location"]


def test_incorrect_verdict_is_recorded(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()
    client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/",
        {"verdict": "incorrect", "incorrect_reason": OTHER_REASON, "new_reason": "nothing there"},
    )
    vetting.refresh_from_db()
    assert vetting.sherlock_correct == "incorrect"


def test_ambiguous_verdict_needs_nothing_else(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()

    client.post(f"/vetting/{VERSION}/transient/{vetting.transient_id}/", {"verdict": "ambiguous"})

    vetting.refresh_from_db()
    assert vetting.sherlock_correct == "ambiguous"


def test_ambiguous_verdict_clears_any_rejection_detail(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()
    vetting.incorrect_reason = "host is a star"
    vetting.corrected_classification = "AGN"
    vetting.save()

    client.post(f"/vetting/{VERSION}/transient/{vetting.transient_id}/", {"verdict": "ambiguous"})

    vetting.refresh_from_db()
    assert vetting.incorrect_reason == ""
    assert vetting.corrected_classification == ""


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


# --- REJECTION REASONS ------------------------------------------------------


def test_the_default_reasons_are_always_offered(db):
    """*even for a version nobody has vetted, and with an empty table*"""
    offered = [value for value, label in VettingReason.choices_for("v9.9.9")]

    # "other" IS ALWAYS LAST — IT IS THE WAY OUT OF THE LIST, NOT A MEMBER.
    assert offered == [*DEFAULT_REASONS, OTHER_REASON]


def test_a_stored_reason_joins_the_defaults(db):
    VettingReason.objects.create(sherlock_version=VERSION, reason="host is a star")

    offered = [value for value, label in VettingReason.choices_for(VERSION)]

    assert offered[: len(DEFAULT_REASONS)] == list(DEFAULT_REASONS)
    assert "host is a star" in offered


def test_reasons_do_not_leak_between_versions(db):
    VettingReason.objects.create(sherlock_version=VERSION, reason="host is a star")

    assert "host is a star" not in [value for value, label in VettingReason.choices_for("v1.1.1")]


def test_a_stored_duplicate_of_a_default_is_not_offered_twice(db):
    VettingReason.objects.create(sherlock_version=VERSION, reason=WRONG_RANK)

    offered = [value for value, label in VettingReason.choices_for(VERSION)]

    assert offered.count(WRONG_RANK) == 1


def test_a_typed_reason_is_kept_for_the_next_transient(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()

    client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/",
        {"verdict": "incorrect", "incorrect_reason": OTHER_REASON, "new_reason": "host is a star"},
    )

    vetting.refresh_from_db()
    assert vetting.incorrect_reason == "host is a star"
    assert VettingReason.objects.filter(sherlock_version=VERSION, reason="host is a star").exists()
    assert VettingReason.objects.get(reason="host is a star").created_by == vetter


def test_wrong_rank_demands_the_rank(client, run, vetter):
    """*the one reason that forces a follow-up answer*"""
    client.force_login(vetter)
    vetting = run.first()
    SherlockCrossmatch.objects.create(transient=vetting.transient, rank=1, sherlock_version=VERSION)

    response = client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/",
        {"verdict": "incorrect", "incorrect_reason": WRONG_RANK},
    )

    assert response.status_code == 200
    vetting.refresh_from_db()
    assert vetting.sherlock_correct is None

    # WITH A RANK CHOSEN IT GOES THROUGH.
    client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/",
        {"verdict": "incorrect", "incorrect_reason": WRONG_RANK, "sherlock_correct_host": "1"},
    )
    vetting.refresh_from_db()
    assert vetting.sherlock_correct == "incorrect"
    assert vetting.sherlock_correct_host == 1


def test_a_reason_without_a_follow_up_is_still_accepted(client, run, vetter):
    """*only some reasons ask a further question; a plain one is enough*"""
    client.force_login(vetter)
    vetting = run.first()
    VettingReason.objects.create(sherlock_version=VERSION, reason="nothing there at all")

    client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/",
        {"verdict": "incorrect", "incorrect_reason": "nothing there at all"},
    )

    vetting.refresh_from_db()
    assert vetting.sherlock_correct == "incorrect"
    assert vetting.incorrect_reason == "nothing there at all"


def test_an_incorrect_verdict_must_say_why(client, run, vetter):
    """*the reason is the one thing a rejection cannot leave out*"""
    client.force_login(vetter)
    vetting = run.first()

    response = client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/", {"verdict": "incorrect"}
    )

    assert response.status_code == 200
    assert "Say why Sherlock got this wrong." in response.content.decode()
    vetting.refresh_from_db()
    assert vetting.sherlock_correct is None


def test_other_demands_the_typed_reason(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()

    response = client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/",
        {"verdict": "incorrect", "incorrect_reason": OTHER_REASON},
    )

    assert response.status_code == 200
    assert "Give the reason." in response.content.decode()
    vetting.refresh_from_db()
    assert vetting.sherlock_correct is None


def test_other_is_never_stored_as_a_reason(client, run, vetter):
    """*it is a sentinel; the typed text is what is kept*"""
    client.force_login(vetter)
    vetting = run.first()

    client.post(
        f"/vetting/{VERSION}/transient/{vetting.transient_id}/",
        {"verdict": "incorrect", "incorrect_reason": OTHER_REASON, "new_reason": "host is a star"},
    )

    assert not VettingReason.objects.filter(reason=OTHER_REASON).exists()
    assert VettingReason.objects.filter(reason="host is a star").exists()


def test_a_correct_verdict_needs_nothing_else(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()

    client.post(f"/vetting/{VERSION}/transient/{vetting.transient_id}/", {"verdict": "correct"})

    vetting.refresh_from_db()
    assert vetting.sherlock_correct == "correct"


def test_a_correct_verdict_clears_any_rejection_detail(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()
    vetting.incorrect_reason = "host is a star"
    vetting.corrected_classification = "AGN"
    vetting.save()

    client.post(f"/vetting/{VERSION}/transient/{vetting.transient_id}/", {"verdict": "correct"})

    vetting.refresh_from_db()
    assert vetting.incorrect_reason == ""
    assert vetting.corrected_classification == ""


def test_the_form_offers_the_classification_codes(client, run, vetter):
    client.force_login(vetter)
    vetting = run.first()

    content = client.get(f"/vetting/{VERSION}/transient/{vetting.transient_id}/").content.decode()

    assert "SN — supernova" in content
    assert WRONG_RANK in content
    # THE BUTTONS MOVED, AND INCORRECT NOW LEADS.
    assert content.index('value="incorrect"') < content.index('value="correct"')


def test_the_form_starts_with_only_the_verdict(client, run, vetter):
    """*everything else is revealed by an answer, not shown up front*"""
    client.force_login(vetter)
    vetting = run.first()

    content = client.get(f"/vetting/{VERSION}/transient/{vetting.transient_id}/").content.decode()

    # THE VERDICT IS RADIOS, NOT TWO SUBMITS, AND INCORRECT STILL LEADS.
    assert 'type="radio" name="verdict" value="incorrect"' in content
    assert 'type="radio" name="verdict" value="correct"' in content
    assert content.index('value="incorrect"') < content.index('value="correct"')

    # NOTHING TO SUBMIT UNTIL ONE IS PICKED.
    assert ':disabled="!verdict"' in content

    # EVERY OTHER FIELD IS IN THE MARKUP BUT HIDDEN BY ALPINE.
    assert 'x-show="verdict === \'incorrect\'"' in content
    assert f"x-show=\"reason === '{OTHER_REASON}'\"" in content
    assert f"x-show=\"reason === '{WRONG_RANK}'\"" in content

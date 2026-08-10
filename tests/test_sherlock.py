import pytest
from django.contrib.auth import get_user_model

from apps.sherlock.models import SherlockClassification, SherlockCrossmatch
from apps.transients.models import Transient

# A LEAD ROW CARRIES A rank AND NO merged_rank; EACH ROW MERGED INTO IT CARRIES
# THAT rank AS ITS merged_rank AND NO rank OF ITS OWN. THE FIXTURES BELOW BUILD
# THAT SHAPE BY HAND RATHER THAN LEANING ON A SHERLOCK RUN.


@pytest.fixture
def transient(db):
    """*one transient to hang crossmatches off*"""
    return Transient.objects.create(name="obj001", origin="lasair", ra=148.6, decl=1.6)


def lead(transient, rank, **kwargs):
    """*a ranked lead crossmatch row*"""
    return SherlockCrossmatch.objects.create(
        transient=transient,
        rank=rank,
        merged_rank=None,
        catalogue_object_id=kwargs.pop("catalogue_object_id", f"LEAD{rank}"),
        **kwargs,
    )


def child(transient, merged_rank, **kwargs):
    """*one catalogue's own match, merged into the lead of that rank*"""
    return SherlockCrossmatch.objects.create(
        transient=transient,
        rank=None,
        merged_rank=merged_rank,
        catalogue_object_id=kwargs.pop("catalogue_object_id", f"CHILD{merged_rank}"),
        **kwargs,
    )


# --- THE TREE ---------------------------------------------------------------


def test_leads_come_back_in_rank_order(transient):
    for rank in (3, 1, 2):
        lead(transient, rank)

    tree = transient.crossmatch_tree()

    assert [item[0].rank for item in tree] == [1, 2, 3]


def test_children_are_grouped_under_their_own_lead(transient):
    lead(transient, 1, catalogue_object_id="MERGED", catalogue_object_subtype="multiple")
    lead(transient, 2, catalogue_object_id="SINGLE", catalogue_object_subtype="G")
    child(transient, 1, catalogue_object_id="FROM_NED", catalogue_table_name="NED")
    child(transient, 1, catalogue_object_id="FROM_PS1", catalogue_table_name="PanSTARRS DR1")

    tree = dict((item[0].catalogue_object_id, item[1]) for item in transient.crossmatch_tree())

    assert [match.catalogue_object_id for match in tree["MERGED"]] == ["FROM_NED", "FROM_PS1"]
    assert tree["SINGLE"] == []


def test_a_transient_with_no_crossmatches_has_an_empty_tree(transient):
    assert transient.crossmatch_tree() == []


def test_another_transients_rows_are_not_borrowed(transient):
    other = Transient.objects.create(name="obj002", origin="lasair", ra=1.0, decl=1.0)
    lead(transient, 1, catalogue_object_id="MINE")
    lead(other, 1, catalogue_object_id="THEIRS")

    assert [item[0].catalogue_object_id for item in transient.crossmatch_tree()] == ["MINE"]


def test_the_tree_costs_one_query(transient, django_assert_num_queries):
    lead(transient, 1, catalogue_object_subtype="multiple")
    child(transient, 1)
    child(transient, 1)

    with django_assert_num_queries(1):
        transient.crossmatch_tree()


# --- ROW HELPERS ------------------------------------------------------------


def test_multiple_marks_a_row_as_merged(transient):
    assert lead(transient, 1, catalogue_object_subtype="multiple").is_merged is True
    assert lead(transient, 2, catalogue_object_subtype="G").is_merged is False


def test_best_magnitude_follows_sherlocks_filter_preference(transient):
    # R OUTRANKS _r, WHICH OUTRANKS J, WHATEVER ORDER THEY ARE SET IN.
    match = lead(transient, 1, mag_J=15.0, mag_r=19.0, mag_R=18.0)

    assert match.best_magnitude == ("R", 18.0)


def test_best_magnitude_strips_the_underscore_off_survey_filters(transient):
    assert lead(transient, 1, mag_r=19.0).best_magnitude == ("r", 19.0)


def test_best_magnitude_is_none_when_no_filter_has_a_value(transient):
    assert lead(transient, 1).best_magnitude is None


def test_reliability_reads_back_as_sherlocks_own_words(transient):
    assert lead(transient, 1, classification_reliability=1).reliability_label == "synonym"
    assert lead(transient, 2, classification_reliability=2).reliability_label == "association"
    assert lead(transient, 3, classification_reliability=3).reliability_label == "annotation"
    assert lead(transient, 4).reliability_label == ""


def test_distance_flag_reads_back_as_words(transient):
    assert lead(transient, 1, best_distance_flag="sz").best_distance_label == "spec-z"
    assert lead(transient, 2, best_distance_flag="dd").best_distance_label == "direct"
    assert lead(transient, 3).best_distance_label == ""


# --- ON THE PAGE ------------------------------------------------------------


@pytest.fixture
def matched(transient):
    """*a transient with one merged match, one plain match and a verdict*"""
    lead(
        transient,
        1,
        catalogue_object_id="COSMOS0242847",
        catalogue_table_name="DESI/NED",
        catalogue_object_subtype="multiple",
        separation_arcsec=3.26,
    )
    child(transient, 1, catalogue_object_id="COSMOS0242847CHILD", catalogue_table_name="NED")
    lead(
        transient,
        2,
        catalogue_object_id="zCOSMOS802046",
        catalogue_table_name="NED",
        catalogue_object_subtype="G",
    )
    SherlockClassification.objects.create(
        transient=transient,
        classification="SN",
        summary='3.3" from galaxy in DESI/NED',
        annotation='Associated with <em><a href="https://ned.example/x">COSMOS0242847</a></em>.',
    )
    return transient


def test_detail_page_lists_the_matched_sources(client, matched):
    content = client.get(f"/transient/{matched.uuid}/").content.decode()

    assert "COSMOS0242847" in content
    assert "zCOSMOS802046" in content


def test_detail_page_shows_sherlocks_verdict_and_annotation(client, matched):
    content = client.get(f"/transient/{matched.uuid}/").content.decode()

    assert '3.3&quot; from galaxy in DESI/NED' in content or '3.3" from galaxy in DESI/NED' in content
    # THE ANNOTATION IS SHERLOCK-WRITTEN HTML AND HAS TO REACH THE PAGE UNESCAPED.
    assert '<a href="https://ned.example/x">COSMOS0242847</a>' in content


def test_merged_rows_ship_their_children_in_the_markup(client, matched):
    """*children are hidden by Alpine, not left out of the response*"""
    content = client.get(f"/transient/{matched.uuid}/").content.decode()

    assert "COSMOS0242847CHILD" in content
    assert 'x-show="open"' in content


def test_only_merged_rows_get_an_expander(client, matched):
    content = client.get(f"/transient/{matched.uuid}/").content.decode()

    # ONE TOGGLE FOR RANK 1; RANK 2 MERGED NOTHING AND GETS NONE.
    assert content.count('@click="open = !open"') == 1


def test_a_transient_with_no_matches_says_so(client, transient):
    content = client.get(f"/transient/{transient.uuid}/").content.decode()

    assert "Sherlock matched no sources against this transient." in content


def test_the_vetting_page_carries_the_same_table(client, matched):
    from django.core.management import call_command
    from io import StringIO

    call_command("create_vetting_run", "v0.0.0", stdout=StringIO())
    get_user_model().objects.create_user(username="dave", email="d@example.org", password="pw")
    client.login(username="dave", password="pw")

    content = client.get(f"/vetting/v0.0.0/transient/{matched.uuid}/").content.decode()

    assert "COSMOS0242847" in content
    assert "Sherlock says" in content

import pytest
from django.contrib.auth import get_user_model

from apps.sherlock.models import SherlockClassification, SherlockCrossmatch
from apps.transients.models import Transient

# A LEAD ROW CARRIES A rank AND NO merged_rank; EACH ROW MERGED INTO IT CARRIES
# THAT rank AS ITS merged_rank AND NO rank OF ITS OWN. THE FIXTURES BELOW BUILD
# THAT SHAPE BY HAND RATHER THAN LEANING ON A SHERLOCK RUN.
#
# EVERY ROW IS STAMPED WITH ONE VERSION, BECAUSE THE TREE IS VERSION-FILTERED:
# ROWS FROM TWO SHERLOCK RUNS ARE NEVER SHOWN TOGETHER.
VERSION = "v0.0.0"


@pytest.fixture
def transient(db):
    """*one transient to hang crossmatches off*"""
    return Transient.objects.create(name="obj001", origin_name="lasair filter", ra=148.6, decl=1.6)


def lead(transient, rank, **kwargs):
    """*a ranked lead crossmatch row*"""
    return SherlockCrossmatch.objects.create(
        transient=transient,
        rank=rank,
        merged_rank=None,
        sherlock_version=kwargs.pop("sherlock_version", VERSION),
        catalogue_object_id=kwargs.pop("catalogue_object_id", f"LEAD{rank}"),
        **kwargs,
    )


def child(transient, merged_rank, **kwargs):
    """*one catalogue's own match, merged into the lead of that rank*"""
    return SherlockCrossmatch.objects.create(
        transient=transient,
        rank=None,
        merged_rank=merged_rank,
        sherlock_version=kwargs.pop("sherlock_version", VERSION),
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
    other = Transient.objects.create(name="obj002", origin_name="lasair filter", ra=1.0, decl=1.0)
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
        ra_deg=149.82053,
        dec_deg=1.62319,
        # ZERO, AS SHERLOCK LEAVES IT ON A MERGED LEAD.
        original_search_radius_arcsec=0.0,
    )
    child(
        transient,
        1,
        catalogue_object_id="COSMOS0242847CHILD",
        catalogue_table_name="NED",
        ra_deg=149.82055,
        dec_deg=1.62320,
        original_search_radius_arcsec=10.0,
    )
    lead(
        transient,
        2,
        catalogue_object_id="zCOSMOS802046",
        catalogue_table_name="NED",
        catalogue_object_subtype="G",
        ra_deg=149.81713,
        dec_deg=1.61561,
        original_search_radius_arcsec=40.0,
    )
    SherlockClassification.objects.create(
        transient=transient,
        classification="SN",
        sherlock_version=VERSION,
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
    # THE EMPTY ROW HAS TO SPAN EVERY COLUMN OR THE TABLE COLLAPSES.
    assert 'colspan="23"' in content


def test_the_header_groups_the_columns(client, matched):
    content = client.get(f"/transient/{matched.uuid}/").content.decode()

    for group, span in (("Sherlock", 7), ("Catalogue", 8), ("Separation", 4), ("Distance", 4)):
        assert f'colspan="{span}"' in content
        assert f">{group}</th>" in content
    # RENAMED SO IT DOES NOT COLLIDE WITH THE "Catalogue" BANNER ABOVE IT.
    assert ">Cat name</th>" in content


# --- THE SKY-VIEW CIRCLES ---------------------------------------------------


def test_a_single_lead_uses_its_own_search_radius(transient):
    lead(transient, 1, ra_deg=1.0, dec_deg=2.0, original_search_radius_arcsec=40.0)

    assert [record["radiusArcsec"] for record in transient.crossmatch_overlays()] == [40.0]


def test_a_merged_lead_borrows_its_smallest_child_radius(transient):
    """*Sherlock writes 0 on a merged lead, so the radius comes from below*"""
    lead(transient, 1, ra_deg=1.0, dec_deg=2.0, original_search_radius_arcsec=0.0,
         catalogue_object_subtype="multiple")
    child(transient, 1, ra_deg=1.0, dec_deg=2.0, original_search_radius_arcsec=20.0)
    child(transient, 1, ra_deg=1.0, dec_deg=2.0, original_search_radius_arcsec=10.0)

    leadRecord = next(r for r in transient.crossmatch_overlays() if r["isLead"])

    assert leadRecord["radiusArcsec"] == 10.0


def test_children_are_drawn_at_their_own_radius(transient):
    lead(transient, 1, ra_deg=1.0, dec_deg=2.0, original_search_radius_arcsec=0.0)
    child(transient, 1, ra_deg=1.5, dec_deg=2.5, original_search_radius_arcsec=20.0)

    records = transient.crossmatch_overlays()
    childRecord = next(r for r in records if not r["isLead"])

    assert (childRecord["radiusArcsec"], childRecord["ra"], childRecord["dec"]) == (20.0, 1.5, 2.5)


def test_a_circle_needs_a_position_and_a_radius(transient):
    lead(transient, 1, ra_deg=None, dec_deg=2.0, original_search_radius_arcsec=10.0)
    lead(transient, 2, ra_deg=1.0, dec_deg=2.0, original_search_radius_arcsec=None)
    lead(transient, 3, ra_deg=1.0, dec_deg=2.0, original_search_radius_arcsec=10.0)

    assert [record["rank"] for record in transient.crossmatch_overlays()] == [3]


def test_a_child_keeps_its_leads_colour(transient):
    lead(transient, 2, ra_deg=1.0, dec_deg=2.0, original_search_radius_arcsec=10.0)
    child(transient, 2, ra_deg=1.0, dec_deg=2.0, original_search_radius_arcsec=10.0)

    assert {record["colourToken"] for record in transient.crossmatch_overlays()} == {"2"}


def test_ranks_past_the_eighth_share_the_muted_colour(transient):
    assert lead(transient, 8).rank_colour_token == "8"
    assert lead(transient, 9).rank_colour_token == "other"
    assert lead(transient, 15).rank_colour_token == "other"


def test_the_page_ships_the_circles_as_json(client, matched):
    import json
    import re

    content = client.get(f"/transient/{matched.uuid}/").content.decode()

    block = re.search(
        r'<script id="sky-view-crossmatches"[^>]*>(.*?)</script>', content, re.DOTALL
    )
    assert block, "the crossmatch overlays were not emitted"

    records = json.loads(block.group(1))
    assert [record["rank"] for record in records if record["isLead"]] == [1, 2]
    # THE MERGED LEAD HAS NO RADIUS OF ITS OWN AND TAKES ITS CHILD'S.
    assert records[0]["radiusArcsec"] == 10.0


def test_the_tree_is_only_queried_once_per_page(transient, django_assert_num_queries):
    """*the table and the sky view share one fetch, not one each*"""
    lead(transient, 1, ra_deg=1.0, dec_deg=2.0, original_search_radius_arcsec=10.0)

    with django_assert_num_queries(1):
        transient.crossmatch_tree()
        transient.crossmatch_overlays()


def test_the_vetting_page_carries_the_same_table(client, matched):
    from django.core.management import call_command
    from io import StringIO

    call_command("create_vetting_run", VERSION, stdout=StringIO())
    get_user_model().objects.create_user(username="dave", email="d@example.org", password="pw")
    client.login(username="dave", password="pw")

    content = client.get(f"/vetting/{VERSION}/transient/{matched.uuid}/").content.decode()

    assert "COSMOS0242847" in content
    assert "Sherlock says" in content


def test_the_search_radius_column_shows_a_real_radius(client, matched):
    """*and reads as "no single value" for a merged lead, which stores 0*"""
    content = client.get(f"/transient/{matched.uuid}/").content.decode()

    assert ">Search radius &Prime;</th>" in content
    # RANK 2 IS A SINGLE LEAD WITH A REAL 40" SEARCH.
    assert "40.00" in content
    # RANK 1 IS MERGED, SO SHERLOCK STORED 0 — WHICH MUST NOT READ AS A CELL OF
    # 0.00. (A BARE "0.00" SUBSTRING WOULD ALSO MATCH INSIDE "40.00".)
    assert ">0.00</td>" not in content

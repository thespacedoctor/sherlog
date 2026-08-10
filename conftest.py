import pytest
from django.db import connection

# SHERLOCK OWNS sherlock_crossmatches AND sherlock_classifications: IT CREATES
# THEM ITSELF, AND DJANGO'S MODELS ARE managed = False MIRRORS WHOSE MIGRATION
# IS STATE-ONLY. SO migrate NEVER BUILDS THEM, AND THE TEST DATABASE — A FRESH
# SQLite FILE BUILT BY RUNNING THE MIGRATIONS — WOULD HAVE NEITHER TABLE IN IT,
# BREAKING EVERY TEST THAT RENDERS A TRANSIENT PAGE.
#
# THE SCHEMA EDITOR BUILDS THEM FROM THE MODELS INSTEAD, ONCE, RIGHT AFTER THE
# TEST DATABASE IS CREATED. NOTE THAT FLIPPING Meta.managed WOULD NOT WORK HERE:
# TABLE CREATION IS DRIVEN BY THE MIGRATION'S RECORDED STATE, NOT BY THE LIVE
# MODEL CLASS.


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """*add Sherlock's own tables to the test database*"""
    from apps.sherlock.models import SherlockClassification, SherlockCrossmatch

    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        editor.create_model(SherlockCrossmatch)
        editor.create_model(SherlockClassification)

    yield

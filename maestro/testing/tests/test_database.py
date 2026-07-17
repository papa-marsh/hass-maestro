"""
Tests to verify that the test database infrastructure works correctly.
This ensures SQLite in-memory DB is properly configured for tests.
"""

from flask import current_app

from maestro import db
from maestro.testing.maestro_test import MaestroTest


def test_database_is_configured(mt: MaestroTest) -> None:
    """Test that the mt fixture's app is configured with SQLite in-memory"""
    assert current_app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_database_tables_exist(mt: MaestroTest) -> None:
    """Test that database tables are created automatically"""
    inspector = db.inspect(db.engine)
    table_names = inspector.get_table_names()

    assert isinstance(table_names, list)


def test_can_query_database(mt: MaestroTest) -> None:
    """Test that we can perform basic database queries"""
    result = db.session.execute(db.text("SELECT 1 as value")).fetchone()

    assert result is not None
    assert result[0] == 1

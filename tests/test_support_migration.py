import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_support_migration_can_upgrade_and_downgrade_without_removing_users():
    migration = importlib.import_module("migrations.versions.f8d029a4c631_add_customer_support")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO users (id) VALUES (1)"))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
            assert {"support_conversations", "support_turns", "support_tickets"}.issubset(inspect(connection).get_table_names())
            assert inspect(connection).get_unique_constraints("support_turns")[0]["column_names"] == ["conversation_id", "request_id"]
            migration.downgrade()
        assert inspect(connection).get_table_names() == ["users"]
        assert connection.scalar(text("SELECT COUNT(*) FROM users")) == 1

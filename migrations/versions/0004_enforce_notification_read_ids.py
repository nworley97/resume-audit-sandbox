"""enforce non-null notification read state

Revision ID: 0004_enforce_notification_read_ids
Revises: 0003_add_missing_prod_columns

The model requires ``user.read_notification_ids`` to be a list. Migration
0003 added the column as nullable so it could be introduced safely for
existing users. Backfill those rows and then enforce the model constraint.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_enforce_notification_read_ids"
down_revision: Union[str, Sequence[str], None] = "0003_add_missing_prod_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # A literal expression keeps Alembic's offline ``--sql`` mode usable;
        # SQLAlchemy has no generic literal renderer for JSON list values.
        op.execute(
            'UPDATE "user" SET read_notification_ids = \'[]\'::json '
            "WHERE read_notification_ids IS NULL"
        )
    else:
        user_table = sa.table(
            "user",
            sa.column("read_notification_ids", sa.JSON()),
        )
        bind.execute(
            user_table.update()
            .where(user_table.c.read_notification_ids.is_(None))
            .values(read_notification_ids=[])
        )

    if bind.dialect.name == "sqlite":
        # SQLite cannot alter a column constraint in place. Batch mode keeps
        # the disposable/local migration test representative of Postgres.
        with op.batch_alter_table("user") as batch_op:
            batch_op.alter_column(
                "read_notification_ids",
                existing_type=sa.JSON(),
                nullable=False,
            )
    else:
        op.alter_column(
            "user",
            "read_notification_ids",
            existing_type=sa.JSON(),
            nullable=False,
        )


def downgrade() -> None:
    """No-op: weakening this invariant is neither required nor desirable."""

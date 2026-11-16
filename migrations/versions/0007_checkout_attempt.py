"""Persist checkout identity and immutable signup snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0007_checkout_attempt"
down_revision = "0006_checkout_fulfillment"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "checkout_attempt",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("active_scope", sa.String(100), nullable=True, unique=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("signup", sa.JSON(), nullable=True),
        sa.Column("session_id", sa.String(255), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_checkout_attempt_scope", "checkout_attempt", ["scope"])


def downgrade():
    op.drop_index("ix_checkout_attempt_scope", table_name="checkout_attempt")
    op.drop_table("checkout_attempt")

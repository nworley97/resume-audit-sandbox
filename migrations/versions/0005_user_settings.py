"""Persist account-specific website settings without changing existing user rows."""
from alembic import op
import sqlalchemy as sa

revision = "0005_user_settings"
down_revision = "0004_enforce_notification_read_ids"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("work_address", sa.String(1000), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("user_settings")

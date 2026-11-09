"""Record checkout fulfillment without changing existing customer data."""
from alembic import op
import sqlalchemy as sa

revision = "0006_checkout_fulfillment"
down_revision = "0005_user_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "checkout_fulfillment",
        sa.Column("session_id", sa.String(255), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("checkout_fulfillment")

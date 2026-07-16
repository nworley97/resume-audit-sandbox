"""add columns that never reached prod (ensure_schema's ALTER TABLE user failed)

Revision ID: 0003_add_missing_prod_columns
Revises: 0002_backfill_status
Create Date: 2026-07-15

Context: the legacy `ensure_schema()` on prod issued
`ALTER TABLE user ADD COLUMN role ...` with `user` UNQUOTED. `user` is a
reserved word in PostgreSQL, so that statement raised a syntax error on every
boot and the columns were never added. A read-only diff (scripts/diff_schema.py,
2026-07-15) confirmed prod is missing exactly these five columns while having
everything else (incl. password_reset_token, candidate.archived/archived_at).

This migration adds them additively (no data is dropped or modified beyond
populating the new NOT NULL `role` with its default). Alembic's op.add_column
quotes the reserved `"user"` identifier correctly, so it succeeds where the
hand-rolled DDL failed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_missing_prod_columns"
down_revision: Union[str, Sequence[str], None] = "0002_backfill_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # candidate.recruiter_note — recruiter's free-text note (nullable, additive)
    op.add_column("candidate", sa.Column("recruiter_note", sa.Text(), nullable=True))

    # user.* — team role / profile / notification read-state.
    # `role` is NOT NULL with a server_default so the 318 existing rows are
    # populated with 'admin' (matches the legacy ensure_schema intent).
    # The rest are nullable; the app reads read_notification_ids as
    # `set(user.read_notification_ids or [])`, so NULL on existing rows is safe.
    op.add_column("user", sa.Column("role", sa.String(length=20), nullable=False, server_default="admin"))
    op.add_column("user", sa.Column("full_name", sa.String(length=200), nullable=True))
    op.add_column("user", sa.Column("company", sa.String(length=200), nullable=True))
    op.add_column("user", sa.Column("read_notification_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    """No-op by design: additive-only on a shared, pre-existing prod DB.

    Dropping these columns could destroy recruiter notes / team-role data and
    is never intended. Downgrading is intentionally a no-op (consistent with
    the 0001 baseline policy).
    """
    pass

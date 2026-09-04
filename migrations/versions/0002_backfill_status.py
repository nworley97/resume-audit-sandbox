"""backfill candidate.status from the legacy archived flag

Standardize the candidate stage on `status` (main's richer workflow:
active/finalist/archived). Any candidate that was flagged via the legacy
Dev-era `archived` boolean but has no `status` gets status='archived'.

Additive/idempotent: only sets status where it is currently empty AND
archived is true. Touches no other app; touches no other table.

Revision ID: 0002_backfill_status
Revises: 0001_baseline
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_backfill_status"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE candidate SET status = 'archived' "
        "WHERE archived IS TRUE AND (status IS NULL OR status = '')"
    )


def downgrade() -> None:
    # Non-destructive backfill; nothing to undo.
    pass

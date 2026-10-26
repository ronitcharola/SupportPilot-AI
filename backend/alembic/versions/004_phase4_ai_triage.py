"""Phase 4 migration: AI urgency score and classification payload

Revision ID: 004_phase4_ai_triage
Revises: 003_phase3_knowledge
Create Date: 2026-10-25 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_phase4_ai_triage"
down_revision: Union[str, None] = "003_phase3_knowledge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("ai_urgency_score", sa.Float(), nullable=True))
    op.add_column("tickets", sa.Column("ai_classification_json", sa.Text(), nullable=True))
    op.create_index(
        "ix_tickets_workspace_escalated",
        "tickets",
        ["workspace_id", "is_escalated"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_workspace_escalated", table_name="tickets")
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_column("ai_classification_json")
        batch_op.drop_column("ai_urgency_score")

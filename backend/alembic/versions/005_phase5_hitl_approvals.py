"""Phase 5 migration: human-in-the-loop action proposals and immutable audit logs

Revision ID: 005_phase5_hitl
Revises: 004_phase4_ai_triage
Create Date: 2026-10-25 18:00:00.000000

The models existed since Phase 1 but had no migration. This revision creates both
tables (and the execution receipt column) and is deliberately defensive: databases
that already have the tables from `Base.metadata.create_all()` are upgraded in place.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_phase5_hitl"
down_revision: Union[str, None] = "004_phase4_ai_triage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(inspector, table: str) -> set:
    return {index["name"] for index in inspector.get_indexes(table)}


def _column_names(inspector, table: str) -> set:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "action_proposals" not in existing_tables:
        op.create_table(
            "action_proposals",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=False),
            sa.Column("ticket_id", sa.String(length=36), nullable=False),
            sa.Column("proposed_by_ai_provider", sa.String(length=100), nullable=False, server_default="mock"),
            sa.Column("action_type", sa.String(length=100), nullable=False),
            sa.Column("action_params_json", sa.Text(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=False),
            sa.Column("ai_confidence", sa.Float(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
            sa.Column("execution_result_json", sa.Text(), nullable=True),
            sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewer_note", sa.Text(), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
            sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key"),
        )
        op.create_index("ix_action_proposals_id", "action_proposals", ["id"], unique=False)
        op.create_index("ix_action_proposals_workspace_id", "action_proposals", ["workspace_id"], unique=False)
        op.create_index("ix_action_proposals_ticket_id", "action_proposals", ["ticket_id"], unique=False)
        op.create_index("ix_action_proposals_status", "action_proposals", ["status"], unique=False)
        op.create_index("ix_action_proposals_idempotency_key", "action_proposals", ["idempotency_key"], unique=True)
        op.create_index("ix_proposals_workspace_status", "action_proposals", ["workspace_id", "status"], unique=False)
        op.create_index("ix_proposals_ticket", "action_proposals", ["ticket_id"], unique=False)
    else:
        if "execution_result_json" not in _column_names(inspector, "action_proposals"):
            with op.batch_alter_table("action_proposals") as batch_op:
                batch_op.add_column(sa.Column("execution_result_json", sa.Text(), nullable=True))

    if "audit_logs" not in existing_tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=False),
            sa.Column("event_category", sa.String(length=50), nullable=False),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("actor_user_id", sa.String(length=36), nullable=True),
            sa.Column("actor_email", sa.String(length=255), nullable=True),
            sa.Column("target_ticket_id", sa.String(length=36), nullable=True),
            sa.Column("target_proposal_id", sa.String(length=36), nullable=True),
            sa.Column("details_json", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_audit_logs_id", "audit_logs", ["id"], unique=False)
        op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"], unique=False)
        op.create_index("ix_audit_logs_event_category", "audit_logs", ["event_category"], unique=False)
        op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"], unique=False)
        op.create_index("ix_audit_logs_target_ticket_id", "audit_logs", ["target_ticket_id"], unique=False)
        op.create_index("ix_audit_logs_target_proposal_id", "audit_logs", ["target_proposal_id"], unique=False)
        op.create_index("ix_audit_workspace_created", "audit_logs", ["workspace_id", "created_at"], unique=False)
        op.create_index("ix_audit_event_type", "audit_logs", ["event_type"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "audit_logs" in existing_tables:
        for index in [
            "ix_audit_event_type",
            "ix_audit_workspace_created",
            "ix_audit_logs_target_proposal_id",
            "ix_audit_logs_target_ticket_id",
            "ix_audit_logs_event_type",
            "ix_audit_logs_event_category",
            "ix_audit_logs_workspace_id",
            "ix_audit_logs_id",
        ]:
            if index in _index_names(inspector, "audit_logs"):
                op.drop_index(index, table_name="audit_logs")
        op.drop_table("audit_logs")

    if "action_proposals" in existing_tables:
        if "execution_result_json" in _column_names(inspector, "action_proposals"):
            with op.batch_alter_table("action_proposals") as batch_op:
                batch_op.drop_column("execution_result_json")
        for index in [
            "ix_proposals_ticket",
            "ix_proposals_workspace_status",
            "ix_action_proposals_idempotency_key",
            "ix_action_proposals_status",
            "ix_action_proposals_ticket_id",
            "ix_action_proposals_workspace_id",
            "ix_action_proposals_id",
        ]:
            if index in _index_names(inspector, "action_proposals"):
                op.drop_index(index, table_name="action_proposals")
        op.drop_table("action_proposals")

"""Phase 2 migration: tickets, ticket_messages, ticket_assignments

Revision ID: 002_phase2_tickets
Revises: 001_phase1_initial
Create Date: 2026-10-24 23:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_phase2_tickets'
down_revision: Union[str, None] = '001_phase1_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. tickets
    op.create_table(
        'tickets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('ticket_number', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('assigned_agent_id', sa.String(length=36), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='open', nullable=False),
        sa.Column('priority', sa.String(length=50), server_default='medium', nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('ai_intent', sa.String(length=100), nullable=True),
        sa.Column('ai_confidence', sa.Float(), nullable=True),
        sa.Column('ai_sentiment', sa.String(length=50), nullable=True),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('is_escalated', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('escalation_reason', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['assigned_agent_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tickets_id', 'tickets', ['id'], unique=False)
    op.create_index('ix_tickets_workspace_id', 'tickets', ['workspace_id'], unique=False)
    op.create_index('ix_tickets_customer_id', 'tickets', ['customer_id'], unique=False)
    op.create_index('ix_tickets_assigned_agent_id', 'tickets', ['assigned_agent_id'], unique=False)
    op.create_index('ix_tickets_ticket_number', 'tickets', ['ticket_number'], unique=False)
    op.create_index('ix_tickets_status', 'tickets', ['status'], unique=False)
    op.create_index('ix_tickets_priority', 'tickets', ['priority'], unique=False)
    op.create_index('ix_tickets_category', 'tickets', ['category'], unique=False)
    op.create_index('ix_tickets_workspace_status', 'tickets', ['workspace_id', 'status'], unique=False)
    op.create_index('ix_tickets_workspace_priority', 'tickets', ['workspace_id', 'priority'], unique=False)
    op.create_index('ix_tickets_workspace_created', 'tickets', ['workspace_id', 'created_at'], unique=False)

    # 2. ticket_messages
    op.create_table(
        'ticket_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('ticket_id', sa.String(length=36), nullable=False),
        sa.Column('sender_type', sa.String(length=20), nullable=False),
        sa.Column('sender_user_id', sa.String(length=36), nullable=True),
        sa.Column('sender_customer_id', sa.String(length=36), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_internal_note', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['sender_customer_id'], ['customers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ticket_messages_id', 'ticket_messages', ['id'], unique=False)
    op.create_index('ix_ticket_messages_workspace_id', 'ticket_messages', ['workspace_id'], unique=False)
    op.create_index('ix_ticket_messages_ticket_id', 'ticket_messages', ['ticket_id'], unique=False)

    # 3. ticket_assignments
    op.create_table(
        'ticket_assignments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('ticket_id', sa.String(length=36), nullable=False),
        sa.Column('assigned_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('assigned_to_user_id', sa.String(length=36), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['assigned_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ticket_assignments_id', 'ticket_assignments', ['id'], unique=False)
    op.create_index('ix_ticket_assignments_workspace_id', 'ticket_assignments', ['workspace_id'], unique=False)
    op.create_index('ix_ticket_assignments_ticket_id', 'ticket_assignments', ['ticket_id'], unique=False)
    op.create_index('ix_ticket_assignments_assigned_to_user_id', 'ticket_assignments', ['assigned_to_user_id'], unique=False)

def downgrade() -> None:
    op.drop_table('ticket_assignments')
    op.drop_table('ticket_messages')
    op.drop_table('tickets')

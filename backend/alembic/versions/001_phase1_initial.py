"""Phase 1 initial migration: workspaces, users, memberships, settings, customers

Revision ID: 001_phase1_initial
Revises: 
Create Date: 2026-10-24 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_phase1_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. workspaces
    op.create_table(
        'workspaces',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('ix_workspaces_id', 'workspaces', ['id'], unique=False)
    op.create_index('ix_workspaces_slug', 'workspaces', ['slug'], unique=True)

    # 2. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_id', 'users', ['id'], unique=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 3. workspace_memberships
    op.create_table(
        'workspace_memberships',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_user')
    )
    op.create_index('ix_workspace_memberships_id', 'workspace_memberships', ['id'], unique=False)
    op.create_index('ix_workspace_memberships_user_id', 'workspace_memberships', ['user_id'], unique=False)
    op.create_index('ix_workspace_memberships_workspace_id', 'workspace_memberships', ['workspace_id'], unique=False)

    # 4. workspace_settings
    op.create_table(
        'workspace_settings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('llm_provider', sa.String(length=50), nullable=False, server_default='mock'),
        sa.Column('llm_model', sa.String(length=100), nullable=False, server_default='mock-gpt-4o'),
        sa.Column('embedding_provider', sa.String(length=50), nullable=False, server_default='mock'),
        sa.Column('embedding_dimension', sa.Integer(), nullable=False, server_default='1536'),
        sa.Column('similarity_threshold', sa.Float(), nullable=False, server_default='0.72'),
        sa.Column('auto_escalate_urgency_threshold', sa.Float(), nullable=False, server_default='0.85'),
        sa.Column('proposal_expiry_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id')
    )
    op.create_index('ix_workspace_settings_id', 'workspace_settings', ['id'], unique=False)
    op.create_index('ix_workspace_settings_workspace_id', 'workspace_settings', ['workspace_id'], unique=True)

    # 5. customers
    op.create_table(
        'customers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('external_reference', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'email', name='uq_workspace_customer_email')
    )
    op.create_index('ix_customers_id', 'customers', ['id'], unique=False)
    op.create_index('ix_customers_workspace_id', 'customers', ['workspace_id'], unique=False)
    op.create_index('ix_customers_email', 'customers', ['email'], unique=False)

def downgrade() -> None:
    op.drop_table('customers')
    op.drop_table('workspace_settings')
    op.drop_table('workspace_memberships')
    op.drop_table('users')
    op.drop_table('workspaces')

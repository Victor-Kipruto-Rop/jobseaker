"""Add separate Google Calendar OAuth and interview event linkage.

Revision ID: 20261104_0020
Revises: 20261104_0019
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0020"
down_revision = "20261104_0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "calendar_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("provider", sa.String(40), nullable=False, server_default="google"),
        sa.Column("email", sa.String(320), nullable=False, server_default=""),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_calendar_provider"),
    )
    op.create_index("ix_calendar_accounts_user_id", "calendar_accounts", ["user_id"])
    op.create_table(
        "calendar_oauth_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_calendar_oauth_states_user_id", "calendar_oauth_states", ["user_id"])
    op.create_index("ix_calendar_oauth_states_state_hash", "calendar_oauth_states", ["state_hash"])
    op.create_index("ix_calendar_oauth_states_expires_at", "calendar_oauth_states", ["expires_at"])
    op.add_column("interviews", sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("interviews", sa.Column("calendar_event_id", sa.String(255), nullable=False, server_default=""))


def downgrade():
    op.drop_column("interviews", "calendar_event_id")
    op.drop_column("interviews", "duration_minutes")
    op.drop_index("ix_calendar_oauth_states_expires_at", table_name="calendar_oauth_states")
    op.drop_index("ix_calendar_oauth_states_state_hash", table_name="calendar_oauth_states")
    op.drop_index("ix_calendar_oauth_states_user_id", table_name="calendar_oauth_states")
    op.drop_table("calendar_oauth_states")
    op.drop_index("ix_calendar_accounts_user_id", table_name="calendar_accounts")
    op.drop_table("calendar_accounts")

"""Add one-time account verification and password reset tokens."""
from alembic import op
from packages.database.models.career import AccountToken

revision = "20261103_0003"
down_revision = "20261103_0002"
branch_labels = None
depends_on = None

def upgrade():
    AccountToken.__table__.create(bind=op.get_bind(), checkfirst=True)

def downgrade():
    AccountToken.__table__.drop(bind=op.get_bind(), checkfirst=True)

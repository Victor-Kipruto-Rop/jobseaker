"""Add Gmail OAuth state and read-only mailbox tables."""
from alembic import op
from packages.database.models.career import EmailAccount, EmailMessage, OAuthState

revision = "20261103_0002"
down_revision = "20261103_0001"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    EmailAccount.__table__.create(bind=bind, checkfirst=True)
    OAuthState.__table__.create(bind=bind, checkfirst=True)
    EmailMessage.__table__.create(bind=bind, checkfirst=True)

def downgrade():
    bind = op.get_bind()
    EmailMessage.__table__.drop(bind=bind, checkfirst=True)
    OAuthState.__table__.drop(bind=bind, checkfirst=True)
    EmailAccount.__table__.drop(bind=bind, checkfirst=True)

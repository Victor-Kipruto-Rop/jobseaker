"""Add encrypted Gmail connection and email metadata tables."""
from alembic import op
from packages.database.models import Base
from packages.database.models import identity, career, entities  # noqa: F401

revision = "20261103_0002"
down_revision = "20261103_0001"
branch_labels = None
depends_on = None

def upgrade():
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)

def downgrade():
    op.drop_table("email_messages")
    op.drop_table("email_accounts")
    op.drop_table("oauth_states")

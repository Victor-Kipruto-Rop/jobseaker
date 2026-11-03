"""Add one-time account verification and password reset tokens."""
from alembic import op
from packages.database.models import Base
from packages.database.models import identity, career, entities  # noqa: F401

revision = "20261103_0003"
down_revision = "20261103_0002"
branch_labels = None
depends_on = None

def upgrade():
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)

def downgrade():
    op.drop_table("account_tokens")

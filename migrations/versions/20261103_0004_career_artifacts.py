"""Add persisted user-owned career intelligence drafts."""
from alembic import op
from packages.database.models import Base
from packages.database.models import identity, career, entities  # noqa: F401

revision = "20261103_0004"
down_revision = "20261103_0003"
branch_labels = None
depends_on = None

def upgrade():
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)

def downgrade():
    op.drop_table("generated_artifacts")

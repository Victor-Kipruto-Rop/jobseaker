"""Store source-verified company identity and brand metadata on imported roles."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0009"
down_revision = "20261104_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidate_opportunities", sa.Column("company_website", sa.String(length=1000), nullable=False, server_default=""))
    op.add_column("candidate_opportunities", sa.Column("company_domain", sa.String(length=253), nullable=False, server_default=""))
    op.add_column("candidate_opportunities", sa.Column("company_logo_url", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("candidate_opportunities", sa.Column("company_favicon_url", sa.String(length=2000), nullable=False, server_default=""))
    op.add_column("candidate_opportunities", sa.Column("company_description", sa.Text(), nullable=False, server_default=""))
    op.add_column("candidate_opportunities", sa.Column("company_brand_source", sa.String(length=1000), nullable=False, server_default=""))


def downgrade():
    op.drop_column("candidate_opportunities", "company_brand_source")
    op.drop_column("candidate_opportunities", "company_description")
    op.drop_column("candidate_opportunities", "company_favicon_url")
    op.drop_column("candidate_opportunities", "company_logo_url")
    op.drop_column("candidate_opportunities", "company_domain")
    op.drop_column("candidate_opportunities", "company_website")

"""Normalize employer identity into reusable per-candidate company records."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0010"
down_revision = "20261104_0009"
branch_labels = None
depends_on = None


def upgrade():
    company_columns = [
        sa.Column("domain", sa.String(length=253), nullable=False, server_default=""),
        sa.Column("industry", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("headquarters", sa.String(length=250), nullable=False, server_default=""),
        sa.Column("logo_url", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("favicon_url", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("brand_color", sa.String(length=7), nullable=False, server_default=""),
        sa.Column("source_provider", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("source_board", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("source_url", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("social_links", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True),
    ]
    for column in company_columns:
        op.add_column("companies", column)
    op.add_column(
        "candidate_opportunities",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_candidate_opportunities_company_id", "candidate_opportunities", ["company_id"])
    op.create_index(
        "uq_company_user_source_board", "companies",
        ["user_id", "source_provider", "source_board"], unique=True,
        sqlite_where=sa.text("source_provider <> ''"),
        postgresql_where=sa.text("source_provider <> ''"),
    )


def downgrade():
    op.drop_index("uq_company_user_source_board", table_name="companies")
    op.drop_index("ix_candidate_opportunities_company_id", table_name="candidate_opportunities")
    op.drop_column("candidate_opportunities", "company_id")
    for column in (
        "last_enriched_at", "verified_at", "social_links", "source_url", "source_board",
        "source_provider", "brand_color", "favicon_url", "logo_url", "headquarters",
        "industry", "domain",
    ):
        op.drop_column("companies", column)

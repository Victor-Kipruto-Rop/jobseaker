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

    # Backfill legacy imported opportunities into reusable, user-owned company
    # records. This keeps existing saved roles connected after the schema change.
    bind = op.get_bind()
    companies = sa.Table("companies", sa.MetaData(), autoload_with=bind)
    opportunities = sa.Table("candidate_opportunities", sa.MetaData(), autoload_with=bind)
    rows = bind.execute(sa.select(
        opportunities.c.id, opportunities.c.user_id, opportunities.c.company,
        opportunities.c.company_website, opportunities.c.company_domain,
        opportunities.c.company_brand_source, opportunities.c.company_description,
        opportunities.c.company_logo_url, opportunities.c.company_favicon_url,
        opportunities.c.company_brand_color,
    ).where(opportunities.c.company != "")).mappings().all()

    grouped = {}
    for row in rows:
        key = (row["user_id"], row["company"].strip().casefold())
        grouped.setdefault(key, []).append(row)

    import hashlib
    for (user_id, normalized_name), records in grouped.items():
        first = records[0]
        existing = bind.execute(sa.select(companies.c.id).where(
            companies.c.user_id == user_id,
            sa.func.lower(companies.c.name) == normalized_name,
        ).limit(1)).first()
        if existing:
            company_id = existing[0]
        else:
            board_key = "legacy-" + hashlib.sha256(normalized_name.encode("utf-8")).hexdigest()[:16]
            inserted = bind.execute(companies.insert().values(
                user_id=user_id,
                name=first["company"].strip()[:250],
                website=first["company_website"] or "",
                domain=first["company_domain"] or "",
                careers_url=first["company_brand_source"] or "",
                description=first["company_description"] or "",
                industry="",
                headquarters="",
                logo_url=first["company_logo_url"] or "",
                favicon_url=first["company_favicon_url"] or "",
                brand_color=first["company_brand_color"] or "",
                source_provider="legacy",
                source_board=board_key,
                source_url=first["company_brand_source"] or "",
                social_links={},
                evidence={"migration": "20261104_0010", "source": "previously imported opportunities"},
                verified_at=None,
                last_enriched_at=None,
            ))
            company_id = inserted.inserted_primary_key[0]
        bind.execute(opportunities.update().where(
            opportunities.c.id.in_([row["id"] for row in records])
        ).values(company_id=company_id))


def downgrade():
    # Remove only migration-created legacy records before dropping their provenance columns.
    op.execute("DELETE FROM companies WHERE source_provider = 'legacy'")
    op.drop_index("uq_company_user_source_board", table_name="companies")
    op.drop_index("ix_candidate_opportunities_company_id", table_name="candidate_opportunities")
    op.drop_column("candidate_opportunities", "company_id")
    for column in (
        "last_enriched_at", "verified_at", "social_links", "source_url", "source_board",
        "source_provider", "brand_color", "favicon_url", "logo_url", "headquarters",
        "industry", "domain",
    ):
        op.drop_column("companies", column)

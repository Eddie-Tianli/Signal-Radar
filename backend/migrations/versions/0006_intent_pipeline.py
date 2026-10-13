"""Natural-language rules, auditable analysis, popularity and Digest provenance."""
from alembic import op
import sqlalchemy as sa
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    # ADD COLUMN preserves rows/FKs on both PostgreSQL and SQLite. Never rebuild topics.
    op.add_column("topics", sa.Column("relevance_threshold", sa.Float(),
                  sa.CheckConstraint("relevance_threshold >= 0 AND relevance_threshold <= 1", name="ck_topics_threshold"),
                  nullable=False, server_default="0.80"))
    op.add_column("topics", sa.Column("last_queries", sa.JSON(), nullable=True))
    op.add_column("topics", sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table("topic_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_type", sa.String(10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("rule_type IN ('include', 'exclude')", name="ck_topic_rules_type"))
    op.create_index("ix_topic_rules_topic_id", "topic_rules", ["topic_id"])
    op.add_column("items", sa.Column("analysis_status", sa.String(20),
                  sa.CheckConstraint("analysis_status IN ('pending', 'valid', 'invalid', 'review', 'failed')", name="ck_items_analysis_status"),
                  nullable=False, server_default="pending"))
    op.add_column("items", sa.Column("analysis_fingerprint", sa.String(64), nullable=True))
    for name in ("relevance_reason", "exclusion_reason", "analysis_error"):
        op.add_column("items", sa.Column(name, sa.Text(), nullable=True))
    op.add_column("items", sa.Column("exclusion_status", sa.String(20),
                  sa.CheckConstraint("exclusion_status IN ('excluded', 'not_excluded', 'uncertain')", name="ck_items_exclusion_status"), nullable=True))
    op.add_column("items", sa.Column("popularity_score", sa.Float(),
                  sa.CheckConstraint("popularity_score >= 0 AND popularity_score <= 1", name="ck_items_popularity_score"), nullable=True))
    op.add_column("items", sa.Column("popularity_metrics", sa.JSON(), nullable=True))
    op.add_column("digests", sa.Column("sources", sa.JSON(), nullable=True))
    op.add_column("digests", sa.Column("input_fingerprint", sa.String(64), nullable=True))


def downgrade():
    for table, constraints, columns in (
        ("digests", [], ["input_fingerprint", "sources"]),
        ("items", ["ck_items_analysis_status", "ck_items_exclusion_status", "ck_items_popularity_score"],
         ["analysis_status", "analysis_fingerprint", "relevance_reason", "exclusion_reason", "analysis_error", "exclusion_status", "popularity_score", "popularity_metrics"]),
    ):
        if op.get_bind().dialect.name != "sqlite":
            for name in constraints:
                op.drop_constraint(name, table, type_="check")
        for name in columns:
            op.drop_column(table, name)
    op.drop_index("ix_topic_rules_topic_id", table_name="topic_rules")
    op.drop_table("topic_rules")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("ck_topics_threshold", "topics", type_="check")
    for name in ("relevance_threshold", "last_queries", "last_scan_at"):
        op.drop_column("topics", name)

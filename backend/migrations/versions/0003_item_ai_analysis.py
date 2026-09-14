"""Add nullable Item AI analysis fields."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("items") as batch:
        batch.add_column(sa.Column("ai_relevant", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("ai_relevance_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("ai_category", sa.String(50), nullable=True))
        batch.add_column(sa.Column("ai_summary", sa.Text(), nullable=True))
        batch.add_column(sa.Column("ai_analyzed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint("ck_items_ai_score", "ai_relevance_score >= 0 AND ai_relevance_score <= 1")


def downgrade():
    with op.batch_alter_table("items") as batch:
        batch.drop_constraint("ck_items_ai_score", type_="check")
        for name in ("ai_analyzed_at", "ai_summary", "ai_category", "ai_relevance_score", "ai_relevant"):
            batch.drop_column(name)

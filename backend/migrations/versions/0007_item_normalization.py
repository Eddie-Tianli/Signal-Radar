"""Topic-independent versioned single-item factual briefs; Raw Item is unchanged."""
from alembic import op
import sqlalchemy as sa
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("item_normalizations",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("item_id",sa.Integer(),sa.ForeignKey("items.id",ondelete="CASCADE"),nullable=False),
        sa.Column("schema_version",sa.String(20),nullable=False),
        sa.Column("revision",sa.Integer(),nullable=False),
        sa.Column("input_fingerprint",sa.String(64),nullable=False),
        sa.Column("normalization_status",sa.String(20),nullable=False),
        sa.Column("headline",sa.Text(),nullable=True),
        sa.Column("summary",sa.Text(),nullable=True),
        sa.Column("entities",sa.JSON(),nullable=True),
        sa.Column("event_type",sa.String(80),nullable=True),
        sa.Column("event_date",sa.Date(),nullable=True),
        sa.Column("keywords",sa.JSON(),nullable=True),
        sa.Column("claims",sa.JSON(),nullable=True),
        sa.Column("warnings",sa.JSON(),nullable=False),
        sa.Column("source_reference",sa.JSON(),nullable=False),
        sa.Column("content_coverage",sa.String(30),nullable=False),
        sa.Column("text_truncated",sa.Boolean(),nullable=False),
        sa.Column("source_metadata",sa.JSON(),nullable=False),
        sa.Column("matching_text",sa.Text(),nullable=False),
        sa.Column("model_name",sa.Text(),nullable=False),
        sa.Column("normalized_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("error",sa.Text(),nullable=True),
        sa.UniqueConstraint("item_id","schema_version","input_fingerprint","revision",name="uq_normalization_revision"),
        sa.CheckConstraint("normalization_status IN ('processing', 'completed', 'failed')",name="ck_normalization_status"))
    op.create_index("ix_item_normalizations_item_id","item_normalizations",["item_id"])


def downgrade():
    op.drop_index("ix_item_normalizations_item_id",table_name="item_normalizations")
    op.drop_table("item_normalizations")

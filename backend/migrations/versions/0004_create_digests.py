"""Create Topic Digest history."""
from alembic import op
import sqlalchemy as sa
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("digests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE", name="fk_digests_topic_id_topics"))
    op.create_index("ix_digests_topic_id", "digests", ["topic_id"])


def downgrade():
    op.drop_index("ix_digests_topic_id", table_name="digests")
    op.drop_table("digests")

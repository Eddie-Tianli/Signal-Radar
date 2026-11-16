"""reading_workspace"""

from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('briefs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_id')
    )
    op.create_table('brief_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('brief_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('content_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('last_update_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('facts', sa.JSON(), nullable=False),
    sa.Column('sources', sa.JSON(), nullable=False),
    sa.Column('warnings', sa.JSON(), nullable=False),
    sa.Column('verification_status', sa.String(length=30), nullable=False),
    sa.Column('generation_status', sa.String(length=20), nullable=False),
    sa.Column('model_name', sa.Text(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("generation_status IN ('processing','completed','fallback')", name='ck_brief_generation'),
    sa.ForeignKeyConstraint(['brief_id'], ['briefs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('brief_id', 'version', name='uq_brief_version')
    )
    op.create_index(op.f('ix_brief_versions_brief_id'), 'brief_versions', ['brief_id'], unique=False)
    op.create_index(op.f('ix_brief_versions_content_fingerprint'), 'brief_versions', ['content_fingerprint'], unique=False)
    op.create_table('reading_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('topic_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('stage', sa.String(length=30), nullable=False),
    sa.Column('stats', sa.JSON(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('report_id', sa.Integer(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['report_id'], ['digests.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reading_runs_topic_id'), 'reading_runs', ['topic_id'], unique=False)
    op.create_table('digest_briefs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('digest_id', sa.Integer(), nullable=False),
    sa.Column('brief_version_id', sa.Integer(), nullable=True),
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.Column('coverage_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['brief_version_id'], ['brief_versions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['digest_id'], ['digests.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('digest_id', 'event_id', name='uq_digest_event')
    )
    op.create_index(op.f('ix_digest_briefs_brief_version_id'), 'digest_briefs', ['brief_version_id'], unique=False)
    op.create_index(op.f('ix_digest_briefs_digest_id'), 'digest_briefs', ['digest_id'], unique=False)
    op.create_index(op.f('ix_digest_briefs_event_id'), 'digest_briefs', ['event_id'], unique=False)
    op.create_table('event_reads',
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('brief_version_id', sa.Integer(), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['brief_version_id'], ['brief_versions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('event_id')
    )
    op.add_column('digests', sa.Column('result_kind', sa.String(length=30), server_default='legacy', nullable=False))
    op.add_column('digests', sa.Column('generation_status', sa.String(length=20), server_default='completed', nullable=False))
    op.add_column('digests', sa.Column('generation_error', sa.Text(), nullable=True))
    op.add_column('digests', sa.Column('model_name', sa.Text(), nullable=True))
    op.add_column('digests', sa.Column('run_stats', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('digests', 'run_stats')
    op.drop_column('digests', 'model_name')
    op.drop_column('digests', 'generation_error')
    op.drop_column('digests', 'generation_status')
    op.drop_column('digests', 'result_kind')
    op.drop_table('event_reads')
    op.drop_index(op.f('ix_digest_briefs_event_id'), table_name='digest_briefs')
    op.drop_index(op.f('ix_digest_briefs_digest_id'), table_name='digest_briefs')
    op.drop_index(op.f('ix_digest_briefs_brief_version_id'), table_name='digest_briefs')
    op.drop_table('digest_briefs')
    op.drop_index(op.f('ix_reading_runs_topic_id'), table_name='reading_runs')
    op.drop_table('reading_runs')
    op.drop_index(op.f('ix_brief_versions_content_fingerprint'), table_name='brief_versions')
    op.drop_index(op.f('ix_brief_versions_brief_id'), table_name='brief_versions')
    op.drop_table('brief_versions')
    op.drop_table('briefs')

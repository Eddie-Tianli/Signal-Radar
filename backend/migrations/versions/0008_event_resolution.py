"""event_resolution"""

from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('identity_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('canonical_title', sa.Text(), nullable=False),
    sa.Column('event_type', sa.String(length=80), nullable=False),
    sa.Column('event_family', sa.String(length=80), nullable=False),
    sa.Column('event_date', sa.Date(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('primary_entities', sa.JSON(), nullable=False),
    sa.Column('facts', sa.JSON(), nullable=False),
    sa.Column('event_status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("event_status IN ('active','developing','closed')", name='ck_event_status'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('identity_fingerprint')
    )
    op.create_index(op.f('ix_events_event_date'), 'events', ['event_date'], unique=False)
    op.create_index(op.f('ix_events_event_family'), 'events', ['event_family'], unique=False)
    op.create_index(op.f('ix_events_updated_at'), 'events', ['updated_at'], unique=False)
    op.create_table('event_entities',
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('entity_key', sa.String(length=240), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('event_id', 'entity_key')
    )
    op.create_index(op.f('ix_event_entities_entity_key'), 'event_entities', ['entity_key'], unique=False)
    op.create_table('event_decisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('normalized_item_id', sa.Integer(), nullable=True),
    sa.Column('resolver_version', sa.String(length=30), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.Column('relation', sa.String(length=30), nullable=False),
    sa.Column('candidate_ids', sa.JSON(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('ai_used', sa.Boolean(), nullable=False),
    sa.Column('processing_status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('attempts', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("relation IN ('new_event','duplicate_report','event_update','uncertain')", name='ck_event_relation'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['normalized_item_id'], ['item_normalizations.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('normalized_item_id', 'resolver_version', name='uq_event_decision')
    )
    op.create_index(op.f('ix_event_decisions_event_id'), 'event_decisions', ['event_id'], unique=False)
    op.create_index(op.f('ix_event_decisions_normalized_item_id'), 'event_decisions', ['normalized_item_id'], unique=False)
    op.create_table('event_sources',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('normalized_item_id', sa.Integer(), nullable=True),
    sa.Column('url_key', sa.String(length=64), nullable=False),
    sa.Column('source_reference', sa.JSON(), nullable=False),
    sa.Column('claims', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['normalized_item_id'], ['item_normalizations.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('normalized_item_id')
    )
    op.create_index(op.f('ix_event_sources_event_id'), 'event_sources', ['event_id'], unique=False)
    op.create_index(op.f('ix_event_sources_url_key'), 'event_sources', ['url_key'], unique=False)
    op.create_table('event_updates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('normalized_item_id', sa.Integer(), nullable=True),
    sa.Column('update_type', sa.String(length=20), nullable=False),
    sa.Column('new_facts', sa.JSON(), nullable=False),
    sa.Column('source_reference', sa.JSON(), nullable=False),
    sa.Column('importance', sa.Float(), nullable=False),
    sa.Column('fact_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("update_type IN ('new_event','new_facts','conflict')", name='ck_event_update_type'),
    sa.CheckConstraint('importance >= 0 AND importance <= 1', name='ck_event_update_importance'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['normalized_item_id'], ['item_normalizations.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_id', 'fact_fingerprint', name='uq_event_update_facts')
    )
    op.create_index(op.f('ix_event_updates_event_id'), 'event_updates', ['event_id'], unique=False)
    op.create_table('topic_matches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('normalized_item_id', sa.Integer(), nullable=False),
    sa.Column('topic_id', sa.Integer(), nullable=False),
    sa.Column('config_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('match_status', sa.String(length=20), nullable=False),
    sa.Column('relevance_score', sa.Float(), nullable=False),
    sa.Column('matched_rules', sa.JSON(), nullable=False),
    sa.Column('exclusion_reason', sa.Text(), nullable=False),
    sa.Column('match_reason', sa.Text(), nullable=False),
    sa.Column('ai_used', sa.Boolean(), nullable=False),
    sa.Column('processing_status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("match_status IN ('matched','unmatched','uncertain')", name='ck_topic_match_status'),
    sa.CheckConstraint('relevance_score >= 0 AND relevance_score <= 1', name='ck_topic_match_score'),
    sa.ForeignKeyConstraint(['normalized_item_id'], ['item_normalizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('normalized_item_id', 'topic_id', 'config_fingerprint', name='uq_topic_match')
    )
    op.create_index(op.f('ix_topic_matches_normalized_item_id'), 'topic_matches', ['normalized_item_id'], unique=False)
    op.create_index(op.f('ix_topic_matches_topic_id'), 'topic_matches', ['topic_id'], unique=False)
    op.create_table('event_notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('topic_id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('event_update_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('pending','sending','sent','failed','suppressed')", name='ck_event_notification_status'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['event_update_id'], ['event_updates.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('topic_id', 'event_id', 'event_update_id', name='uq_event_notification')
    )
    op.create_index(op.f('ix_event_notifications_status'), 'event_notifications', ['status'], unique=False)
    op.create_index(op.f('ix_event_notifications_topic_id'), 'event_notifications', ['topic_id'], unique=False)
    op.create_table('event_topics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('topic_id', sa.Integer(), nullable=False),
    sa.Column('match_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['match_id'], ['topic_matches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_id', 'topic_id', 'match_id', name='uq_event_topic_match')
    )
    op.create_index(op.f('ix_event_topics_event_id'), 'event_topics', ['event_id'], unique=False)
    op.create_index(op.f('ix_event_topics_topic_id'), 'event_topics', ['topic_id'], unique=False)
    op.add_column('items', sa.Column('canonical_url_hash', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_items_canonical_url_hash'), 'items', ['canonical_url_hash'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_items_canonical_url_hash'), table_name='items')
    op.drop_column('items', 'canonical_url_hash')
    op.drop_index(op.f('ix_event_topics_topic_id'), table_name='event_topics')
    op.drop_index(op.f('ix_event_topics_event_id'), table_name='event_topics')
    op.drop_table('event_topics')
    op.drop_index(op.f('ix_event_notifications_topic_id'), table_name='event_notifications')
    op.drop_index(op.f('ix_event_notifications_status'), table_name='event_notifications')
    op.drop_table('event_notifications')
    op.drop_index(op.f('ix_topic_matches_topic_id'), table_name='topic_matches')
    op.drop_index(op.f('ix_topic_matches_normalized_item_id'), table_name='topic_matches')
    op.drop_table('topic_matches')
    op.drop_index(op.f('ix_event_updates_event_id'), table_name='event_updates')
    op.drop_table('event_updates')
    op.drop_index(op.f('ix_event_sources_url_key'), table_name='event_sources')
    op.drop_index(op.f('ix_event_sources_event_id'), table_name='event_sources')
    op.drop_table('event_sources')
    op.drop_index(op.f('ix_event_decisions_normalized_item_id'), table_name='event_decisions')
    op.drop_index(op.f('ix_event_decisions_event_id'), table_name='event_decisions')
    op.drop_table('event_decisions')
    op.drop_index(op.f('ix_event_entities_entity_key'), table_name='event_entities')
    op.drop_table('event_entities')
    op.drop_index(op.f('ix_events_updated_at'), table_name='events')
    op.drop_index(op.f('ix_events_event_family'), table_name='events')
    op.drop_index(op.f('ix_events_event_date'), table_name='events')
    op.drop_table('events')

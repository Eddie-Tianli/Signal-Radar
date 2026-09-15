from alembic import context
from sqlalchemy import create_engine, pool

from app.database import Base, database_url
from app.topics.models import TopicRecord  # noqa: F401
from app.items.models import ItemRecord  # noqa: F401
from app.digests.models import DigestRecord  # noqa: F401


if context.is_offline_mode():
    context.configure(url=database_url(), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    # Tests provide their own isolated connection; normal runs use local PostgreSQL.
    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(database_url(), poolclass=pool.NullPool, connect_args={"connect_timeout": 5})
        try:
            with engine.connect() as connection:
                context.configure(connection=connection, target_metadata=Base.metadata)
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            engine.dispose()

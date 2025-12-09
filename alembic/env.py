from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import your models and settings
from app.models.models import Base  # Make sure Base includes all your models
from app.core.config import settings  # Contains DATABASE_URL

# Alembic Config object
config = context.config

# Configure Python logging from the config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the sqlalchemy.url in Alembic config with our app settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (without a DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode (with a DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Useful for detecting type changes
            render_as_batch=True  # Useful for SQLite or safer migrations
        )

        with context.begin_transaction():
            context.run_migrations()

# Execute the appropriate migration mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

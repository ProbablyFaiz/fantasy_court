from logging.config import fileConfig

from alembic import context
from alembic_utils.replaceable_entity import register_entities

from blank.db.models import Base
from blank.db.pg_objects import PG_OBJECTS
from blank.db.session import ADMIN_POSTGRES_URI, get_engine

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# Register the entities with alembic_utils
register_entities(
    [
        *PG_OBJECTS,
    ]
)


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.
def include_object(obj, name, obj_type, reflected, compare_to):
    if obj_type == "table" and name.startswith("celery"):
        return False
    if obj_type == "grant_table":
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    raise NotImplementedError("This method is not implemented yet.")


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    with get_engine(ADMIN_POSTGRES_URI).connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

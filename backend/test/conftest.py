from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pytest_postgresql import factories
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from blank.api.deps import get_db
from blank.api.main import app
from blank.db.models import Base

# Create a PostgreSQL test database factory
postgresql_proc = factories.postgresql_proc(
    port=None,
    unixsocketdir="/tmp",
)
postgresql = factories.postgresql("postgresql_proc")


@pytest.fixture
def test_engine(postgresql):
    """Create a test database engine."""
    connection_string = (
        f"postgresql://{postgresql.info.user}:@{postgresql.info.host}:"
        f"{postgresql.info.port}/{postgresql.info.dbname}"
    )
    engine = create_engine(connection_string)

    # Create all tables
    Base.metadata.create_all(engine)

    return engine


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()

    # Create session bound to the connection
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()

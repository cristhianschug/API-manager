"""Pytest configuration and fixtures"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from database import Base, get_db
from main import app

# In-memory SQLite for testing (fast, isolated)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

# Global session for sharing between test fixture and client requests
_test_db_session = None

def override_get_db():
    """Override get_db to use test session"""
    global _test_db_session
    if _test_db_session:
        yield _test_db_session
    else:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()


app.dependency_overrides[get_db] = override_get_db

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)

@pytest.fixture
def db_session():
    """Database session for tests"""
    global _test_db_session
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    _test_db_session = session

    yield session

    _test_db_session = None
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def reset_db():
    """Reset database before each test"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

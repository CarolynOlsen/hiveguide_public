import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import pytest
from fastapi.testclient import TestClient
from backend.main import app, Base, engine, SessionLocal, User, Hive, Inspection
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the SessionLocal dependency
app.dependency_overrides[SessionLocal] = lambda: TestingSessionLocal()

# Patch backend.main.SessionLocal and backend.main.engine to use the test database/session for all DB operations during tests.
# This ensures the endpoints use the test DB, not the production one.
import backend.main as main
main.SessionLocal = TestingSessionLocal
main.engine = engine


@pytest.fixture(scope="function", autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def get_auth_cookie(client, email="test@example.com", password="testpass"):
    # Register and approve user
    client.post("/register", json={"email": email, "password": password})
    db = TestingSessionLocal()
    user = db.query(User).filter_by(email=email).first()
    user.is_approved = True
    db.commit()
    db.close()
    # Login
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.cookies.get("session_id")

def test_hive_crud():
    client = TestClient(app)
    session_id = get_auth_cookie(client)
    # Create hive (API expects form data, not JSON)
    resp = client.post(
        "/hives",
        data={"nickname": "Hive1", "location": "Yard", "description": "Test hive"},
        cookies={"session_id": session_id},
    )
    assert resp.status_code == 200
    hive = resp.json()
    assert hive["nickname"] == "Hive1"
    # List hives
    resp = client.get("/hives", cookies={"session_id": session_id})
    assert resp.status_code == 200
    hives = resp.json()
    assert len(hives) == 1
    assert hives[0]["nickname"] == "Hive1"

def test_inspection_crud():
    client = TestClient(app)
    session_id = get_auth_cookie(client)
    # Create hive (API expects form data, not JSON)
    resp = client.post(
        "/hives",
        data={"nickname": "Hive2", "location": "Yard", "description": "Test hive2"},
        cookies={"session_id": session_id},
    )
    hive_id = resp.json()["id"]
    # Create inspection (API expects form data, not JSON)
    resp = client.post(
        "/inspections",
        data={
            "hive_id": hive_id,
            "transcription": "Test transcription",
            "notes": "Test notes",
            "weather": "sunny",
            "temperature": "25",
            "queen_visible": True,
            "eggs_visible": True,
            "larvae_visible": False,
            "capped_brood_visible": False,
            "laying_pattern": "solid",
            "activity_level": "average"
        },
        cookies={"session_id": session_id},
    )
    assert resp.status_code == 200
    inspection = resp.json()
    assert inspection["hive_id"] == hive_id
    assert inspection["transcription"] == "Test transcription"
    # List inspections
    resp = client.get(f"/inspections?hive_id={hive_id}", cookies={"session_id": session_id})
    assert resp.status_code == 200
    inspections = resp.json()
    assert len(inspections) == 1
    assert inspections[0]["hive_id"] == hive_id

def test_auth_required():
    client = TestClient(app)
    # Cannot create hive without login
    resp = client.post("/hives", data={"nickname": "HiveX"})
    assert resp.status_code == 401
    # Cannot create inspection without login
    resp = client.post("/inspections", data={"hive_id": 1})
    assert resp.status_code == 401
    # Cannot list hives/inspections without login
    assert client.get("/hives").status_code == 401
    assert client.get("/inspections").status_code == 401  

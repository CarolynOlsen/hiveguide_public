"""
Tests for Circle functionality
"""
import pytest
import json
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

class TestCircleManagement:
    """Test circle creation and management"""
    
    def test_create_circle_unauthorized(self):
        """Test creating circle without authentication"""
        response = client.post("/circles", json={
            "name": "Test Circle",
            "description": "A test circle"
        })
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]
    
    def test_list_circles_unauthorized(self):
        """Test listing circles without authentication"""
        response = client.get("/circles")
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

class TestCircleMembership:
    """Test circle membership functionality"""
    
    def test_invite_to_circle_unauthorized(self):
        """Test inviting to circle without authentication"""
        response = client.post("/circles/1/invite", json={
            "email": "test@example.com"
        })
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]
    
    def test_list_circle_members_unauthorized(self):
        """Test listing circle members without authentication"""
        response = client.get("/circles/1/members")
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]
    
    def test_remove_circle_member_unauthorized(self):
        """Test removing circle member without authentication"""
        response = client.delete("/circles/1/members/1")
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

class TestCircleAccess:
    """Test circle access control for hives and inspections"""
    
    def test_access_control_on_hive_listing(self):
        """Test that hive listing includes circle access"""
        # This would require setting up test database and authentication
        # For now, just test the endpoint exists
        response = client.get("/hives")
        assert response.status_code == 401  # Should require auth
    
    def test_access_control_on_inspection_creation(self):
        """Test that inspection creation checks circle access"""
        # This would require setting up test database and authentication
        # For now, just test the endpoint exists
        response = client.post("/inspections", data={
            "hive_id": 1,
            "transcription": "Test inspection"
        })
        assert response.status_code == 401  # Should require auth

if __name__ == '__main__':
    pytest.main(['-v', 'test_circles.py'])
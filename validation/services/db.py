"""
Database utilities for validation - self-contained in validation/services/.
Provides SessionLocal and models (User, Hive, Inspection) without importing from backend.
Matches the actual database schema from backend/main.py.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Date, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from validation.services.config import DATABASE_URL

Base = declarative_base()


class User(Base):
    """User model for validation - minimal structure matching backend."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=True)
    hives = relationship("Hive", back_populates="user", cascade="all, delete-orphan")


class Hive(Base):
    """Hive model for validation - minimal structure matching backend."""
    __tablename__ = "hives"
    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String, nullable=False)
    photo_url = Column(String, nullable=True)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="hives")
    inspections = relationship("Inspection", back_populates="hive", cascade="all, delete-orphan")


class Inspection(Base):
    """Inspection model for validation - matches backend/main.py schema exactly."""
    __tablename__ = "inspections"
    id = Column(Integer, primary_key=True, index=True)
    hive_id = Column(Integer, ForeignKey("hives.id"), nullable=False)
    timestamp = Column(DateTime, nullable=True)
    transcription = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    weather = Column(String, nullable=True)
    temperature = Column(String, nullable=True)
    queen_visible = Column(Boolean, nullable=True)
    eggs_visible = Column(Boolean, nullable=True)
    larvae_visible = Column(Boolean, nullable=True)
    capped_brood_visible = Column(Boolean, nullable=True)
    laying_pattern = Column(String, nullable=True)
    activity_level = Column(String, nullable=True)
    photos = Column(JSON, nullable=True)  # JSON column type
    action_items = Column(JSON, nullable=True)  # JSON column type
    action_due_date = Column(Date, nullable=True)
    # Note: inspection_date may exist in some database versions but is not in the base model
    hive = relationship("Hive", back_populates="inspections")


# Create engine and session factory
_engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


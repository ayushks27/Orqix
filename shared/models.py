from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Text, Enum, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from shared.db import Base
import enum

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    RESEARCHER = "RESEARCHER"
    VIEWER = "VIEWER"

class ModelStage(str, enum.Enum):
    DEVELOPMENT = "DEVELOPMENT"
    VALIDATION = "VALIDATION"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"
    ARCHIVED = "ARCHIVED"

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(String(50), primary_key=True)
    org_id = Column(String(50), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.RESEARCHER)
    created_at = Column(DateTime, default=datetime.utcnow)

class Experiment(Base):
    __tablename__ = "experiments"
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    org_id = Column(String(50), ForeignKey("organizations.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    runs = relationship("Run", back_populates="experiment", cascade="all, delete-orphan")

class Run(Base):
    __tablename__ = "runs"
    id = Column(String(50), primary_key=True)
    experiment_id = Column(String(50), ForeignKey("experiments.id"), nullable=False)
    parent_run_id = Column(String(50), ForeignKey("runs.id"), nullable=True) # Supporting nested runs
    status = Column(String(20), default="RUNNING") # RUNNING, COMPLETED, FAILED, CANCELLED
    git_commit = Column(String(40), nullable=True)
    dataset_version = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    experiment = relationship("Experiment", back_populates="runs")
    params = relationship("RunParam", back_populates="run", cascade="all, delete-orphan")
    metrics = relationship("RunMetric", back_populates="run", cascade="all, delete-orphan")
    artifacts = relationship("RunArtifact", back_populates="run", cascade="all, delete-orphan")

class RunParam(Base):
    __tablename__ = "run_params"
    run_id = Column(String(50), ForeignKey("runs.id"), primary_key=True)
    key = Column(String(100), primary_key=True)
    value = Column(String(255), nullable=False)

    run = relationship("Run", back_populates="params")

class RunMetric(Base):
    __tablename__ = "run_metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), ForeignKey("runs.id"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    step = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)

    run = relationship("Run", back_populates="metrics")
    
    __table_args__ = (
        Index("ix_run_metrics_run_key", "run_id", "key"),
    )

class RunArtifact(Base):
    __tablename__ = "run_artifacts"
    id = Column(String(100), primary_key=True) # Full MinIO URI or file path
    run_id = Column(String(50), ForeignKey("runs.id"), nullable=False)
    name = Column(String(100), nullable=False)
    artifact_type = Column(String(50), nullable=False) # e.g. "model", "checkpoint", "log", "plot"
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("Run", back_populates="artifacts")

class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    org_id = Column(String(50), ForeignKey("organizations.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id = Column(String(50), primary_key=True) # dataset_id:version
    dataset_id = Column(String(50), ForeignKey("datasets.id"), nullable=False)
    version = Column(String(50), nullable=False)
    hash = Column(String(64), nullable=False) # sha256 checksum
    size_bytes = Column(Integer, nullable=True)
    storage_uri = Column(String(255), nullable=False)
    parent_version_id = Column(String(50), ForeignKey("dataset_versions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("dataset_id", "version", name="uq_dataset_version"),
    )

class RegisteredModel(Base):
    __tablename__ = "registered_models"
    id = Column(String(50), primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    org_id = Column(String(50), ForeignKey("organizations.id"), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(String(50), primary_key=True) # model_id:version
    model_id = Column(String(50), ForeignKey("registered_models.id"), nullable=False)
    version = Column(String(20), nullable=False)
    run_id = Column(String(50), ForeignKey("runs.id"), nullable=False)
    artifact_uri = Column(String(255), nullable=False)
    stage = Column(Enum(ModelStage), default=ModelStage.DEVELOPMENT)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("model_id", "version", name="uq_model_version"),
    )

class RegistryApproval(Base):
    __tablename__ = "registry_approvals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_version_id = Column(String(50), ForeignKey("model_versions.id"), nullable=False)
    approver_id = Column(String(50), ForeignKey("users.id"), nullable=False)
    from_stage = Column(Enum(ModelStage), nullable=False)
    to_stage = Column(Enum(ModelStage), nullable=False)
    approved = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

class JobExecution(Base):
    __tablename__ = "job_executions"
    id = Column(String(50), primary_key=True) # K8s pod name / job name
    run_id = Column(String(50), ForeignKey("runs.id"), nullable=False)
    cpu_request = Column(Float, nullable=False) # In cores
    gpu_request = Column(Integer, nullable=False) # Count
    memory_request_gb = Column(Float, nullable=False)
    priority_score = Column(Float, default=1.0)
    scheduler_type = Column(String(20), default="HEURISTIC") # HEURISTIC, ML
    predicted_runtime_sec = Column(Float, nullable=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(String(50), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

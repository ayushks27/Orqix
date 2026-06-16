import uuid
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel

from shared.db import get_db
from shared.models import RegisteredModel, ModelVersion, RegistryApproval, ModelStage, Run, UserRole, AuditLog
from shared.auth import get_current_user, RoleChecker
from shared.kafka import event_broker

logger = logging.getLogger("orqix.registry")

app = FastAPI(title="Orqix Model Registry Service", version="1.0.0")

class ModelRegisterRequest(BaseModel):
    name: str
    description: Optional[str] = None

class VersionRegisterRequest(BaseModel):
    version: str
    run_id: str
    artifact_uri: str

class PromotionRequest(BaseModel):
    to_stage: ModelStage
    notes: Optional[str] = None

@app.post("/registry/models", response_model=Dict[str, Any], dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def register_model(
    req: ModelRegisterRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    org_id = current_user["org_id"]
    # Check duplicate
    existing = db.query(RegisteredModel).filter(RegisteredModel.name == req.name, RegisteredModel.org_id == org_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Model '{req.name}' is already registered.")

    model_id = f"mod_{uuid.uuid4().hex[:8]}"
    db_model = RegisteredModel(
        id=model_id,
        name=req.name,
        org_id=org_id,
        description=req.description
    )
    db.add(db_model)
    db.commit()
    db.refresh(db_model)

    event_broker.publish("orqix.models", "ModelRegistered", {
        "model_id": model_id,
        "name": req.name,
        "org_id": org_id,
        "user_id": current_user["id"]
    })

    return {
        "id": db_model.id,
        "name": db_model.name,
        "org_id": db_model.org_id,
        "description": db_model.description,
        "created_at": db_model.created_at
    }

@app.post("/registry/models/{model_id}/versions", response_model=Dict[str, Any], dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def create_model_version(
    model_id: str,
    req: VersionRegisterRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    org_id = current_user["org_id"]
    # Verify model ownership
    model = db.query(RegisteredModel).filter(RegisteredModel.id == model_id, RegisteredModel.org_id == org_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Verify run exists
    run = db.query(Run).filter(Run.id == req.run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Source run ID not found")

    # Check duplicate version
    existing = db.query(ModelVersion).filter(ModelVersion.model_id == model_id, ModelVersion.version == req.version).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Version {req.version} is already registered for this model.")

    version_id = f"mv_{uuid.uuid4().hex[:10]}"
    db_ver = ModelVersion(
        id=version_id,
        model_id=model_id,
        version=req.version,
        run_id=req.run_id,
        artifact_uri=req.artifact_uri,
        stage=ModelStage.DEVELOPMENT
    )
    db.add(db_ver)
    
    # Log audit entry
    audit = AuditLog(
        org_id=org_id,
        user_id=current_user["id"],
        action="CREATE_VERSION",
        resource=f"model/{model_id}",
        details={"version": req.version, "run_id": req.run_id}
    )
    db.add(audit)
    db.commit()
    db.refresh(db_ver)

    return {
        "id": db_ver.id,
        "model_id": db_ver.model_id,
        "version": db_ver.version,
        "run_id": db_ver.run_id,
        "artifact_uri": db_ver.artifact_uri,
        "stage": db_ver.stage,
        "created_at": db_ver.created_at
    }

@app.post("/registry/versions/{version_id}/promote", dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def promote_model_version(
    version_id: str,
    req: PromotionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    org_id = current_user["org_id"]
    ver = db.query(ModelVersion).join(RegisteredModel).filter(
        ModelVersion.id == version_id,
        RegisteredModel.org_id == org_id
    ).first()
    
    if not ver:
        raise HTTPException(status_code=404, detail="Model version not found")

    from_stage = ver.stage
    to_stage = req.to_stage

    if from_stage == to_stage:
        raise HTTPException(status_code=400, detail="Model is already in the target stage")

    # If promoting to PRODUCTION, archiving other production models is recommended standard workflow
    if to_stage == ModelStage.PRODUCTION:
        current_prod = db.query(ModelVersion).filter(
            ModelVersion.model_id == ver.model_id,
            ModelVersion.stage == ModelStage.PRODUCTION
        ).all()
        for p in current_prod:
            p.stage = ModelStage.ARCHIVED

    ver.stage = to_stage
    
    # Log approval
    approval = RegistryApproval(
        model_version_id=version_id,
        approver_id=current_user["id"],
        from_stage=from_stage,
        to_stage=to_stage,
        notes=req.notes
    )
    db.add(approval)

    audit = AuditLog(
        org_id=org_id,
        user_id=current_user["id"],
        action="PROMOTE_VERSION",
        resource=f"version/{version_id}",
        details={"from_stage": from_stage.value, "to_stage": to_stage.value, "notes": req.notes}
    )
    db.add(audit)
    
    db.commit()

    event_broker.publish("orqix.models", "ModelPromoted", {
        "version_id": version_id,
        "model_id": ver.model_id,
        "from_stage": from_stage.value,
        "to_stage": to_stage.value,
        "approver_id": current_user["id"]
    })

    return {
        "version_id": version_id,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "status": "success"
    }

@app.post("/registry/versions/{version_id}/rollback", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
def rollback_model_version(
    version_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Rolls back the model stage status. Demotes current production versions
    and sets this version as PRODUCTION. Restricted to ADMIN.
    """
    org_id = current_user["org_id"]
    ver = db.query(ModelVersion).join(RegisteredModel).filter(
        ModelVersion.id == version_id,
        RegisteredModel.org_id == org_id
    ).first()
    
    if not ver:
        raise HTTPException(status_code=404, detail="Model version not found")

    from_stage = ver.stage
    
    # Transition all current production models to ARCHIVED
    db.query(ModelVersion).filter(
        ModelVersion.model_id == ver.model_id,
        ModelVersion.stage == ModelStage.PRODUCTION
    ).update({ModelVersion.stage: ModelStage.ARCHIVED})

    ver.stage = ModelStage.PRODUCTION
    
    approval = RegistryApproval(
        model_version_id=version_id,
        approver_id=current_user["id"],
        from_stage=from_stage,
        to_stage=ModelStage.PRODUCTION,
        notes="ROLLBACK TRIGGERED"
    )
    db.add(approval)
    db.commit()

    return {"status": "rolled_back", "production_version": ver.version}

@app.get("/registry/models", response_model=List[Dict[str, Any]])
def list_registered_models(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    org_id = current_user["org_id"]
    models = db.query(RegisteredModel).filter(RegisteredModel.org_id == org_id).all()
    
    res = []
    for m in models:
        # Get count of versions
        ver_count = db.query(ModelVersion).filter(ModelVersion.model_id == m.id).count()
        # Find active production version
        prod_ver = db.query(ModelVersion).filter(
            ModelVersion.model_id == m.id,
            ModelVersion.stage == ModelStage.PRODUCTION
        ).first()
        
        res.append({
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "version_count": ver_count,
            "production_version": prod_ver.version if prod_ver else None,
            "created_at": m.created_at
        })
    return res

@app.get("/registry/models/{model_id}/versions", response_model=List[Dict[str, Any]])
def list_model_versions(model_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    org_id = current_user["org_id"]
    model = db.query(RegisteredModel).filter(RegisteredModel.id == model_id, RegisteredModel.org_id == org_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
        
    versions = db.query(ModelVersion).filter(ModelVersion.model_id == model_id).order_by(ModelVersion.created_at.desc()).all()
    
    res = []
    for v in versions:
        # Load approvals
        approvals = db.query(RegistryApproval).filter(RegistryApproval.model_version_id == v.id).all()
        res.append({
            "id": v.id,
            "version": v.version,
            "run_id": v.run_id,
            "artifact_uri": v.artifact_uri,
            "stage": v.stage,
            "created_at": v.created_at,
            "history": [{
                "approver": a.approver_id,
                "from_stage": a.from_stage,
                "to_stage": a.to_stage,
                "approved_at": a.approved,
                "notes": a.notes
            } for a in approvals]
        })
    return res

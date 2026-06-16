import uuid
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime

from shared.db import get_db
from shared.models import Experiment, Run, RunParam, RunMetric, RunArtifact, UserRole
from shared.auth import get_current_user, RoleChecker
from shared.kafka import event_broker

app = FastAPI(title="Orqix Experiment Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections for metric streaming
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket):
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = []
        self.active_connections[run_id].append(websocket)

    def disconnect(self, run_id: str, websocket: WebSocket):
        if run_id in self.active_connections:
            self.active_connections[run_id].remove(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]

    async def broadcast_metric(self, run_id: str, message: dict):
        if run_id in self.active_connections:
            for connection in self.active_connections[run_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

ws_manager = ConnectionManager()

# Experiment Endpoints
@app.post("/experiments", response_model=Dict[str, Any], dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def create_experiment(name: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    org_id = current_user["org_id"]
    exp_id = f"exp_{uuid.uuid4().hex[:8]}"
    db_exp = Experiment(id=exp_id, name=name, org_id=org_id)
    db.add(db_exp)
    db.commit()
    db.refresh(db_exp)
    
    event_broker.publish("orqix.experiment.runs", "ExperimentCreated", {
        "experiment_id": exp_id,
        "name": name,
        "org_id": org_id,
        "user_id": current_user["id"]
    })
    
    return {"id": db_exp.id, "name": db_exp.name, "org_id": db_exp.org_id, "created_at": db_exp.created_at}

@app.get("/experiments", response_model=List[Dict[str, Any]])
def list_experiments(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    org_id = current_user["org_id"]
    exps = db.query(Experiment).filter(Experiment.org_id == org_id).all()
    return [{"id": e.id, "name": e.name, "created_at": e.created_at} for e in exps]

# Run Endpoints
@app.post("/runs", response_model=Dict[str, Any], dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def create_run(
    experiment_id: str, 
    parent_run_id: Optional[str] = None, 
    git_commit: Optional[str] = None,
    dataset_version: Optional[str] = None,
    db: Session = Depends(get_db), 
    current_user: dict = Depends(get_current_user)
):
    # Verify experiment exists
    exp = db.query(Experiment).filter(Experiment.id == experiment_id, Experiment.org_id == current_user["org_id"]).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
        
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    db_run = Run(
        id=run_id,
        experiment_id=experiment_id,
        parent_run_id=parent_run_id,
        status="RUNNING",
        git_commit=git_commit,
        dataset_version=dataset_version
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    
    event_broker.publish("orqix.experiment.runs", "RunStarted", {
        "run_id": run_id,
        "experiment_id": experiment_id,
        "parent_run_id": parent_run_id,
        "org_id": current_user["org_id"],
        "timestamp": db_run.created_at.isoformat()
    })
    
    return {
        "id": db_run.id,
        "experiment_id": db_run.experiment_id,
        "parent_run_id": db_run.parent_run_id,
        "status": db_run.status,
        "git_commit": db_run.git_commit,
        "dataset_version": db_run.dataset_version,
        "created_at": db_run.created_at
    }

@app.post("/runs/{run_id}/status", dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def update_run_status(run_id: str, status: str, failure_reason: Optional[str] = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    run = db.query(Run).join(Experiment).filter(Run.id == run_id, Experiment.org_id == current_user["org_id"]).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    status = status.upper()
    if status not in ["COMPLETED", "FAILED", "CANCELLED"]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    run.status = status
    run.completed_at = datetime.utcnow()
    db.commit()
    
    event_type = f"Run{status.capitalize()}" # e.g. RunCompleted, RunFailed
    event_broker.publish("orqix.experiment.runs", event_type, {
        "run_id": run.id,
        "experiment_id": run.experiment_id,
        "org_id": current_user["org_id"],
        "timestamp": run.completed_at.isoformat(),
        "failure_reason": failure_reason
    })
    
    return {"run_id": run.id, "status": run.status, "completed_at": run.completed_at}

@app.post("/runs/{run_id}/params", dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def log_params(run_id: str, params: Dict[str, str], db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    run = db.query(Run).join(Experiment).filter(Run.id == run_id, Experiment.org_id == current_user["org_id"]).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    for k, v in params.items():
        # Upsert parameter
        param = db.query(RunParam).filter(RunParam.run_id == run_id, RunParam.key == k).first()
        if param:
            param.value = str(v)
        else:
            db.add(RunParam(run_id=run_id, key=k, value=str(v)))
            
    db.commit()
    return {"status": "success", "logged": list(params.keys())}

@app.post("/runs/{run_id}/metrics", dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
async def log_metrics(run_id: str, metrics: Dict[str, float], step: int = 0, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    run = db.query(Run).join(Experiment).filter(Run.id == run_id, Experiment.org_id == current_user["org_id"]).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    timestamp = datetime.utcnow()
    metric_records = []
    for k, v in metrics.items():
        metric_record = RunMetric(run_id=run_id, key=k, value=float(v), step=step, timestamp=timestamp)
        db.add(metric_record)
        metric_records.append({
            "key": k,
            "value": float(v),
            "step": step,
            "timestamp": timestamp.isoformat()
        })
        
    db.commit()
    
    # Broadcast to live WebSockets monitoring this run
    await ws_manager.broadcast_metric(run_id, {
        "run_id": run_id,
        "step": step,
        "metrics": metrics,
        "timestamp": timestamp.isoformat()
    })
    
    return {"status": "success", "logged": metric_records}

@app.get("/runs/{run_id}", response_model=Dict[str, Any])
def get_run_details(run_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    run = db.query(Run).join(Experiment).filter(Run.id == run_id, Experiment.org_id == current_user["org_id"]).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    # Load params
    params = {p.key: p.value for p in run.params}
    
    # Get latest value for each metric
    latest_metrics = {}
    for metric_name_row in db.query(RunMetric.key).filter(RunMetric.run_id == run_id).distinct():
        metric_name = metric_name_row[0]
        latest_val = db.query(RunMetric).filter(RunMetric.run_id == run_id, RunMetric.key == metric_name).order_by(RunMetric.step.desc(), RunMetric.timestamp.desc()).first()
        if latest_val:
            latest_metrics[metric_name] = {
                "value": latest_val.value,
                "step": latest_val.step,
                "timestamp": latest_val.timestamp
            }
            
    artifacts = [{"id": a.id, "name": a.name, "type": a.artifact_type, "size": a.size_bytes} for a in run.artifacts]
    
    return {
        "id": run.id,
        "experiment_id": run.experiment_id,
        "parent_run_id": run.parent_run_id,
        "status": run.status,
        "git_commit": run.git_commit,
        "dataset_version": run.dataset_version,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "parameters": params,
        "metrics": latest_metrics,
        "artifacts": artifacts
    }

@app.get("/experiments/{experiment_id}/runs", response_model=List[Dict[str, Any]])
def list_experiment_runs(
    experiment_id: str,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    query = db.query(Run).join(Experiment).filter(
        Run.experiment_id == experiment_id,
        Experiment.org_id == current_user["org_id"]
    )
    if status_filter:
        query = query.filter(Run.status == status_filter.upper())
        
    runs = query.order_by(Run.created_at.desc()).all()
    
    results = []
    for run in runs:
        params = {p.key: p.value for p in run.params}
        
        # Simple list summary of metrics
        metrics = {}
        for metric_name_row in db.query(RunMetric.key).filter(RunMetric.run_id == run.id).distinct():
            m_key = metric_name_row[0]
            latest = db.query(RunMetric).filter(RunMetric.run_id == run.id, RunMetric.key == m_key).order_by(RunMetric.step.desc()).first()
            if latest:
                metrics[m_key] = latest.value
                
        results.append({
            "id": run.id,
            "parent_run_id": run.parent_run_id,
            "status": run.status,
            "git_commit": run.git_commit,
            "dataset_version": run.dataset_version,
            "created_at": run.created_at,
            "completed_at": run.completed_at,
            "parameters": params,
            "metrics": metrics
        })
    return results

@app.post("/experiments/{experiment_id}/clone", response_model=Dict[str, Any], dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def clone_experiment(experiment_id: str, new_name: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    org_id = current_user["org_id"]
    orig_exp = db.query(Experiment).filter(Experiment.id == experiment_id, Experiment.org_id == org_id).first()
    if not orig_exp:
        raise HTTPException(status_code=404, detail="Original experiment not found")
        
    new_id = f"exp_{uuid.uuid4().hex[:8]}"
    cloned_exp = Experiment(id=new_id, name=new_name, org_id=org_id)
    db.add(cloned_exp)
    db.commit()
    db.refresh(cloned_exp)
    
    # Log audit event
    event_broker.publish("orqix.experiment.runs", "ExperimentCloned", {
        "original_experiment_id": experiment_id,
        "cloned_experiment_id": new_id,
        "org_id": org_id,
        "user_id": current_user["id"]
    })
    
    return {"id": cloned_exp.id, "name": cloned_exp.name, "cloned_from": orig_exp.id}

# WebSocket for metric streaming
@app.websocket("/runs/{run_id}/metrics/stream")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    await ws_manager.connect(run_id, websocket)
    try:
        while True:
            # We just keep the connection alive. Client doesn't need to send messages,
            # but they can send ping/pongs.
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(run_id, websocket)
    except Exception:
        ws_manager.disconnect(run_id, websocket)

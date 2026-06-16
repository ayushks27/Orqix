import uuid
import yaml
import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel

from shared.db import get_db
from shared.auth import get_current_user, RoleChecker
from shared.models import UserRole
from shared.kafka import event_broker

logger = logging.getLogger("orqix.workflow")

app = FastAPI(title="Orqix Workflow Service", version="1.0.0")

# Task step schema
class TaskDefinition(BaseModel):
    name: str
    dependencies: List[str]
    image: Optional[str] = "python:3.10-slim"
    command: Optional[str] = "echo 'Running task'"
    retries: int = 3
    retry_delay_sec: int = 2

class WorkflowDefinition(BaseModel):
    pipeline_name: str
    tasks: List[TaskDefinition]

# Active Workflow Runs memory storage
active_workflows: Dict[str, Dict[str, Any]] = {}

def detect_cycle_and_sort(tasks: List[TaskDefinition]) -> List[str]:
    """
    Performs Depth-First Search for cycle detection and returns the topological ordering.
    """
    adj = {t.name: t.dependencies for t in tasks}
    # Validate dependencies exist in task definitions
    task_names = {t.name for t in tasks}
    for t in tasks:
        for dep in t.dependencies:
            if dep not in task_names:
                raise ValueError(f"Task '{t.name}' depends on unknown task '{dep}'")

    visited = {} # None=unvisited, 1=visiting, 2=visited
    order = []

    def dfs(node):
        visited[node] = 1 # Visiting
        for neighbor in adj.get(node, []):
            if visited.get(neighbor) == 1:
                raise ValueError(f"Cycle detected at task '{node}' -> '{neighbor}'")
            elif neighbor not in visited:
                dfs(neighbor)
        visited[node] = 2 # Visited
        order.append(node)

    for task in tasks:
        if task.name not in visited:
            try:
                dfs(task.name)
            except ValueError as e:
                raise e

    # order is from target to source, so reverse it
    # wait, if node depends on neighbors, it should run after neighbors.
    # so if order is reversed: [dataset_ingestion, preprocessing, ...], it is the execution order
    return order

@app.post("/workflows/validate")
def validate_dag(workflow: WorkflowDefinition):
    try:
        execution_order = detect_cycle_and_sort(workflow.tasks)
        return {"valid": True, "execution_order": execution_order}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"DAG validation failed: {str(e)}")

@app.post("/workflows/submit", dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
async def submit_workflow(
    yaml_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Read YAML file
    content = await yaml_file.read()
    try:
        data = yaml.safe_load(content)
        pipeline_name = data.get("pipeline_name", "Unnamed Pipeline")
        raw_tasks = data.get("pipeline", [])
        
        # Parse into objects
        tasks = []
        for t in raw_tasks:
            tasks.append(TaskDefinition(
                name=t.get("name"),
                dependencies=t.get("dependencies", []),
                image=t.get("image", "python:3.10-slim"),
                command=t.get("command", "echo 'executing step'"),
                retries=int(t.get("retries", 3)),
                retry_delay_sec=int(t.get("retry_delay_sec", 2))
            ))
            
        execution_order = detect_cycle_and_sort(tasks)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid workflow YAML structure or DAG loop: {str(e)}")

    workflow_run_id = f"wf_run_{uuid.uuid4().hex[:12]}"
    
    # Store workflow initial state
    active_workflows[workflow_run_id] = {
        "pipeline_name": pipeline_name,
        "status": "RUNNING",
        "created_at": datetime.utcnow().isoformat(),
        "execution_order": execution_order,
        "tasks_status": {t.name: {"status": "PENDING", "retries_left": t.retries, "logs": []} for t in tasks},
        "tasks_map": {t.name: t for t in tasks}
    }

    # Start execution loop asynchronously (simulating Temporal runner activities)
    asyncio.create_task(run_workflow_loop(workflow_run_id))

    event_broker.publish("orqix.experiment.runs", "WorkflowStarted", {
        "workflow_run_id": workflow_run_id,
        "pipeline_name": pipeline_name,
        "timestamp": datetime.utcnow().isoformat()
    })

    return {
        "workflow_run_id": workflow_run_id,
        "pipeline_name": pipeline_name,
        "execution_order": execution_order,
        "status": "RUNNING"
    }

@app.get("/workflows/{workflow_run_id}/status")
def get_workflow_status(workflow_run_id: str, current_user: dict = Depends(get_current_user)):
    wf = active_workflows.get(workflow_run_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return wf

@app.post("/workflows/{workflow_run_id}/cancel", dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def cancel_workflow(workflow_run_id: str, current_user: dict = Depends(get_current_user)):
    wf = active_workflows.get(workflow_run_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow run not found")
        
    wf["status"] = "CANCELLED"
    for task_name, state in wf["tasks_status"].items():
        if state["status"] in ["PENDING", "RUNNING"]:
            state["status"] = "CANCELLED"
            
    return {"status": "cancelled", "workflow_run_id": workflow_run_id}

# Async simulation of Parallel and topological execution
async def run_workflow_loop(workflow_run_id: str):
    wf = active_workflows.get(workflow_run_id)
    if not wf:
        return

    logger.info(f"Starting DAG Runner Loop for: {workflow_run_id}")
    
    tasks_map: Dict[str, TaskDefinition] = wf["tasks_map"]
    tasks_status = wf["tasks_status"]
    
    # Run loop until all completed or one fails
    while wf["status"] == "RUNNING":
        # Identify tasks whose dependencies are fully COMPLETED and currently PENDING
        ready_tasks = []
        for task_name, defn in tasks_map.items():
            state = tasks_status[task_name]
            if state["status"] != "PENDING":
                continue
                
            deps_satisfied = True
            for dep in defn.dependencies:
                if tasks_status[dep]["status"] != "COMPLETED":
                    deps_satisfied = False
                    break
            if deps_satisfied:
                ready_tasks.append(task_name)
                
        # If no tasks are pending, we are completed
        all_done = all(t["status"] == "COMPLETED" for t in tasks_status.values())
        if all_done:
            wf["status"] = "COMPLETED"
            event_broker.publish("orqix.experiment.runs", "WorkflowCompleted", {
                "workflow_run_id": workflow_run_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            break
            
        any_failed = any(t["status"] == "FAILED" for t in tasks_status.values())
        if any_failed:
            wf["status"] = "FAILED"
            event_broker.publish("orqix.experiment.runs", "WorkflowFailed", {
                "workflow_run_id": workflow_run_id,
                "timestamp": datetime.utcnow().isoformat(),
                "reason": "One or more tasks failed."
            })
            break
            
        if not ready_tasks:
            # Nothing is ready but not all done, wait a bit for active tasks
            await asyncio.sleep(0.5)
            continue

        # Execute all ready tasks in parallel
        await asyncio.gather(*(execute_task_step(workflow_run_id, t_name) for t_name in ready_tasks))

async def execute_task_step(workflow_run_id: str, task_name: str):
    wf = active_workflows.get(workflow_run_id)
    if not wf or wf["status"] != "RUNNING":
        return
        
    state = wf["tasks_status"][task_name]
    defn: TaskDefinition = wf["tasks_map"][task_name]
    
    state["status"] = "RUNNING"
    state["logs"].append(f"[{datetime.utcnow().isoformat()}] Task started.")
    
    # Run retries
    success = False
    for attempt in range(defn.retries + 1):
        if wf["status"] != "RUNNING":
            state["status"] = "CANCELLED"
            return
            
        try:
            state["logs"].append(f"[{datetime.utcnow().isoformat()}] Attempt {attempt + 1}: Executing command: {defn.command}")
            # Simulate execution time
            await asyncio.sleep(1.5)
            
            # Simulate failure check for testing retry policy
            if "fail" in defn.command.lower() and attempt < defn.retries:
                raise Exception("Simulated run step error")
                
            success = True
            break
        except Exception as e:
            state["logs"].append(f"[{datetime.utcnow().isoformat()}] Attempt {attempt + 1} failed: {str(e)}")
            state["retries_left"] -= 1
            if attempt < defn.retries:
                await asyncio.sleep(defn.retry_delay_sec)

    if success:
        state["status"] = "COMPLETED"
        state["logs"].append(f"[{datetime.utcnow().isoformat()}] Task completed successfully.")
    else:
        state["status"] = "FAILED"
        state["logs"].append(f"[{datetime.utcnow().isoformat()}] Task failed after maximum retries.")

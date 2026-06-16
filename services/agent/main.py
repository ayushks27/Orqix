import os
import re
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import requests

from shared.db import get_db
from shared.models import Run, RunParam, RunMetric, RunArtifact, JobExecution, JobStatus, UserRole
from shared.auth import get_current_user

logger = logging.getLogger("orqix.agent")

app = FastAPI(title="Orqix AI Agent Service", version="1.0.0")

class DiagnosticRequest(BaseModel):
    run_id: str

class DiagnosticResult(BaseModel):
    run_id: str
    status: str
    failure_category: str
    root_cause: str
    explanation: str
    recommendations: List[str]

# Mock training log loader helper
def load_mock_logs(run_id: str, status: str, db: Session) -> str:
    # Check if there is an associated JobExecution
    job = db.query(JobExecution).filter(JobExecution.run_id == run_id).first()
    
    # Generate realistic training log based on status
    if status == "FAILED":
        if job and job.gpu_request > 0:
            return """
            [INFO] 2026-06-16 13:52:10 - Loading Dataset version v3 from s3://orqix-datasets/mnist_v3
            [INFO] 2026-06-16 13:52:12 - Model parameters: learning_rate=0.001, batch_size=256
            [INFO] 2026-06-16 13:52:15 - Epoch 1/100: Loss = 2.45
            [INFO] 2026-06-16 13:52:20 - Epoch 2/100: Loss = 1.98
            [INFO] 2026-06-16 13:52:25 - Epoch 3/100: Loss = 1.34
            [ERROR] 2026-06-16 13:52:30 - Torch: CUDA Out of Memory (OOM). Tried to allocate 4.20 GiB. GPU 0 has 11.20 GiB total capacity.
            [ERROR] 2026-06-16 13:52:31 - Process finished with exit code 1
            """
        elif job and job.gpu_request == 0 and job.memory_request_gb < 2:
            return """
            [INFO] 2026-06-16 13:52:10 - Initializing Model architecture: Transformer (12 layers, 768 hidden size)
            [ERROR] 2026-06-16 13:52:12 - Kernel Panic: Out of memory (OOM). Process killed by system daemon.
            """
        else:
            # Check if loss was exploding
            metrics = db.query(RunMetric).filter(RunMetric.run_id == run_id, RunMetric.key == "loss").order_by(RunMetric.step.asc()).all()
            if metrics and len(metrics) > 1 and metrics[-1].value > metrics[0].value * 10:
                return f"""
                [INFO] 2026-06-16 13:52:10 - Epoch 1: Loss = {metrics[0].value}
                [WARNING] 2026-06-16 13:52:15 - Epoch 2: Loss = {metrics[1].value}
                [ERROR] 2026-06-16 13:52:20 - Loss exploded! Value = NaN detected. Halting execution.
                """
            return """
            [INFO] 2026-06-16 13:52:10 - Running evaluation script...
            [ERROR] 2026-06-16 13:52:12 - FileNotFoundError: [Errno 2] No such file or directory: 'checkpoints/best_model.pt'
            """
    else:
        return "[INFO] 2026-06-16 13:52:10 - Training completed successfully."

# Rule-based fallback diagnostics engine
def run_fallback_diagnostics(run_id: str, status: str, logs: str, params: dict, metrics: List[RunMetric]) -> Dict[str, Any]:
    # 1. Out of Memory Checks
    if "CUDA Out of Memory" in logs or "OOM" in logs or "OOM" in logs.upper():
        current_batch_size = params.get("batch_size", "64")
        try:
            bs = int(current_batch_size)
            suggested_bs = max(8, bs // 2)
        except ValueError:
            suggested_bs = 32

        return {
            "failure_category": "GPU/System Out Of Memory (OOM)",
            "root_cause": "Requested GPU tensor allocations exceeded the available capacity of the allocated cluster nodes.",
            "explanation": "The training run failed because the batch size (or model size) requires more memory than the current pod resources have. CUDA failed to allocate additional tensor blocks.",
            "recommendations": [
                f"Reduce your training batch size from {current_batch_size} to {suggested_bs}.",
                "Increase the GPU resource request (e.g. use a node with 16GB or 24GB memory).",
                "Enable gradient accumulation steps to split forward/backward passes."
            ]
        }

    # 2. Gradient Explosion Checks
    if "NaN" in logs or "exploded" in logs.lower():
        current_lr = params.get("learning_rate", "0.001")
        try:
            lr = float(current_lr)
            suggested_lr = lr / 10.0
        except ValueError:
            suggested_lr = 0.0001
            
        return {
            "failure_category": "Gradient Explosion / Loss Divergence",
            "root_cause": "The loss value became NaN (Not-a-Number), indicating numeric overflow inside gradient updates.",
            "explanation": "Numerical overflow occurred because the learning rate is likely too high, or input features were not normalized, leading to exploding gradient vectors.",
            "recommendations": [
                f"Decrease the learning rate from {current_lr} to {suggested_lr}.",
                "Add Gradient Clipping (e.g. clip_grad_norm_ = 1.0) inside your model training loop.",
                "Ensure your input dataset feature layers are scaled (e.g. Standard Scaler / MinMax Scaler)."
            ]
        }

    # 3. Missing Checkpoint/Files
    if "FileNotFoundError" in logs:
        return {
            "failure_category": "Infrastructure / File System Error",
            "root_cause": "The execution script attempted to load a file or checkpoint that does not exist in the worker environment.",
            "explanation": "A file access error occurred. This usually happens when the pipeline checkpoint recovery path points to a deleted directory or a missing volume mount.",
            "recommendations": [
                "Verify that the task inputs are properly checkpointed in the prior DAG pipeline step.",
                "Check the Artifact service path for your models to ensure the S3 file exists."
            ]
        }

    # Default fallback
    return {
        "failure_category": "Unspecified Execution Fault",
        "root_cause": "Process crashed with non-zero exit code during the training iteration.",
        "explanation": "The orchestrator terminated the pod due to an unhandled runtime error. See the diagnostics logs for stack traces.",
        "recommendations": [
            "Review Python traceback logs.",
            "Add exception handling blocks to dump checkpoints before crashing."
        ]
    }

@app.post("/agent/diagnose", response_model=DiagnosticResult)
def diagnose_failed_run(req: DiagnosticRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    org_id = current_user["org_id"]
    
    # Load Run
    run = db.query(Run).filter(Run.id == req.run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    # Gather metadata
    params = {p.key: p.value for p in run.params}
    metrics = db.query(RunMetric).filter(RunMetric.run_id == req.run_id).all()
    logs = load_mock_logs(req.run_id, run.status, db)

    # 1. State Machine Stage 1: Gather & Check Logs
    # We call OpenAI / Gemini if environment keys are present
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if openai_key:
        try:
            # Call OpenAI Chat endpoint to generate detailed failure agent reports
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are Orqix MLOps Agent. Diagnose the failed run logs and metrics, return a JSON output containing: failure_category, root_cause, explanation, recommendations (list of strings)."},
                        {"role": "user", "content": f"Logs: {logs}\nParameters: {params}\nMetricsCount: {len(metrics)}"}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1
                },
                timeout=8
            )
            if response.status_code == 200:
                res_data = response.json()["choices"][0]["message"]["content"]
                import json
                parsed = json.loads(res_data)
                return DiagnosticResult(
                    run_id=req.run_id,
                    status=run.status,
                    failure_category=parsed.get("failure_category", "LLM Diagnosed Failure"),
                    root_cause=parsed.get("root_cause", "N/A"),
                    explanation=parsed.get("explanation", "N/A"),
                    recommendations=parsed.get("recommendations", [])
                )
        except Exception as e:
            logger.warning(f"LLM API diagnosis failed: {e}. Falling back to Rule-based system.")

    # 2. State Machine Fallback: Expert System
    diag = run_fallback_diagnostics(req.run_id, run.status, logs, params, metrics)
    return DiagnosticResult(
        run_id=req.run_id,
        status=run.status,
        failure_category=diag["failure_category"],
        root_cause=diag["root_cause"],
        explanation=diag["explanation"],
        recommendations=diag["recommendations"]
    )

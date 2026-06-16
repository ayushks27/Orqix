import os
import io
import gzip
import shutil
import uuid
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from shared.db import get_db
from shared.models import Run, RunArtifact, UserRole
from shared.auth import get_current_user, RoleChecker
from shared.config import settings

logger = logging.getLogger("orqix.artifact")

app = FastAPI(title="Orqix Artifact Service", version="1.0.0")

# Setup storage fallback folder
LOCAL_STORAGE_DIR = "d:/projects/Orqix/storage/artifacts"
os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)

# Boto3 client configuration for MinIO
MINIO_AVAILABLE = False
s3_client = None

try:
    import boto3
    from botocore.client import Config
    
    # Attempt to initialize S3 client
    s3_client = boto3.client(
        's3',
        endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    # Check connection
    s3_client.list_buckets()
    MINIO_AVAILABLE = True
    logger.info("MinIO connection established.")
except Exception as e:
    logger.warning(f"Could not initialize or connect to MinIO S3 client: {e}. Using local storage fallback: {LOCAL_STORAGE_DIR}")

def ensure_bucket_exists(bucket_name: str):
    if MINIO_AVAILABLE and s3_client:
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except Exception:
            try:
                s3_client.create_bucket(Bucket=bucket_name)
            except Exception as e:
                logger.error(f"Failed to create MinIO bucket {bucket_name}: {e}")

@app.post("/artifacts/upload", dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
async def upload_artifact(
    run_id: str = Form(...),
    name: str = Form(...),
    artifact_type: str = Form(...), # model, checkpoint, log, plot
    compress: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify run exists
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    file_bytes = await file.read()
    content_type = file.content_type
    file_name = file.filename or name
    
    # Run compression if requested and not already zipped
    if compress and not file_name.endswith('.gz'):
        file_bytes = gzip.compress(file_bytes)
        file_name = f"{file_name}.gz"
        content_type = "application/gzip"

    size_bytes = len(file_bytes)
    artifact_id = f"art_{uuid.uuid4().hex[:10]}"
    storage_path = f"{run_id}/{artifact_id}_{file_name}"
    
    # Store the file
    storage_uri = ""
    if MINIO_AVAILABLE and s3_client:
        bucket_name = "orqix-artifacts"
        ensure_bucket_exists(bucket_name)
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=storage_path,
                Body=file_bytes,
                ContentType=content_type
            )
            storage_uri = f"s3://{bucket_name}/{storage_path}"
        except Exception as e:
            logger.error(f"Failed uploading to MinIO S3: {e}. Falling back to local filesystem storage.")
            MINIO_AVAILABLE = False # Trigger fallback
            
    if not storage_uri: # Local filesystem storage
        local_path = os.path.join(LOCAL_STORAGE_DIR, run_id)
        os.makedirs(local_path, exist_ok=True)
        full_file_path = os.path.join(local_path, f"{artifact_id}_{file_name}")
        with open(full_file_path, "wb") as f:
            f.write(file_bytes)
        storage_uri = f"local://{full_file_path}"

    # Log inside PG database
    db_artifact = RunArtifact(
        id=storage_uri,
        run_id=run_id,
        name=name,
        artifact_type=artifact_type,
        size_bytes=size_bytes
    )
    db.add(db_artifact)
    db.commit()
    
    return {
        "artifact_uri": storage_uri,
        "run_id": run_id,
        "name": name,
        "type": artifact_type,
        "size_bytes": size_bytes
    }

@app.get("/artifacts/download")
def download_artifact(
    artifact_uri: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify metadata is registered
    db_art = db.query(RunArtifact).filter(RunArtifact.id == artifact_uri).first()
    if not db_art:
        raise HTTPException(status_code=404, detail="Artifact not found in database records")

    # Serve the file content
    if artifact_uri.startswith("s3://"):
        if not MINIO_AVAILABLE or not s3_client:
            raise HTTPException(status_code=503, detail="MinIO storage connection is offline")
        
        try:
            parts = artifact_uri[5:].split('/', 1)
            bucket = parts[0]
            key = parts[1]
            response = s3_client.get_object(Bucket=bucket, Key=key)
            return StreamingResponse(
                io.BytesIO(response['Body'].read()),
                media_type=response.get('ContentType', 'application/octet-stream'),
                headers={"Content-Disposition": f"attachment; filename={db_art.name}"}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"S3 download failed: {str(e)}")
            
    elif artifact_uri.startswith("local://"):
        local_path = artifact_uri[8:]
        if not os.path.exists(local_path):
            raise HTTPException(status_code=404, detail="Local storage file does not exist")
            
        def iterfile():
            with open(local_path, mode="rb") as f:
                yield from f

        return StreamingResponse(
            iterfile(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={db_art.name}"}
        )
        
    else:
        raise HTTPException(status_code=400, detail="Invalid artifact URI schema")

@app.get("/artifacts/run/{run_id}", response_model=List[Dict[str, Any]])
def list_run_artifacts(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    artifacts = db.query(RunArtifact).filter(RunArtifact.run_id == run_id).all()
    return [{
        "uri": a.id,
        "name": a.name,
        "type": a.artifact_type,
        "size_bytes": a.size_bytes,
        "created_at": a.created_at
    } for a in artifacts]

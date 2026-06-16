import uuid
import hashlib
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime

from shared.db import get_db, neo4j_client
from shared.models import Dataset, DatasetVersion, UserRole
from shared.auth import get_current_user, RoleChecker
from shared.kafka import event_broker

logger = logging.getLogger("orqix.dataset")

app = FastAPI(title="Orqix Dataset & Lineage Service", version="1.0.0")

# Local fallback in-memory graph repository if Neo4j is offline
in_memory_nodes: List[Dict[str, Any]] = []
in_memory_relationships: List[Dict[str, Any]] = []

@app.post("/datasets", response_model=Dict[str, Any], dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def create_dataset(name: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    org_id = current_user["org_id"]
    dataset_id = f"ds_{uuid.uuid4().hex[:8]}"
    
    # Check duplicate
    existing = db.query(Dataset).filter(Dataset.name == name, Dataset.org_id == org_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Dataset with this name already exists")
        
    db_ds = Dataset(id=dataset_id, name=name, org_id=org_id)
    db.add(db_ds)
    db.commit()
    db.refresh(db_ds)
    
    event_broker.publish("orqix.datasets", "DatasetCreated", {
        "dataset_id": dataset_id,
        "name": name,
        "org_id": org_id,
        "user_id": current_user["id"]
    })
    
    # Track node in Neo4j
    query = "MERGE (d:Dataset {id: $id, name: $name, created_at: $created})"
    neo4j_client.execute_query(query, {
        "id": dataset_id,
        "name": name,
        "created": db_ds.created_at.isoformat()
    })
    in_memory_nodes.append({"id": dataset_id, "label": name, "type": "Dataset"})
    
    return {"id": db_ds.id, "name": db_ds.name, "created_at": db_ds.created_at}

@app.post("/datasets/versions", response_model=Dict[str, Any], dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
async def create_dataset_version(
    dataset_id: str = Form(...),
    version: str = Form(...),
    storage_uri: str = Form(...),
    parent_version_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify dataset exists
    ds = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.org_id == current_user["org_id"]).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    # Check duplicate version
    existing = db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id, 
        DatasetVersion.version == version
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="This version was already registered")

    # Read and hash content
    content = await file.read()
    h = hashlib.sha256()
    h.update(content)
    sha256_hash = h.hexdigest()
    size_bytes = len(content)

    version_id = f"dsv_{uuid.uuid4().hex[:10]}"
    db_ver = DatasetVersion(
        id=version_id,
        dataset_id=dataset_id,
        version=version,
        hash=sha256_hash,
        size_bytes=size_bytes,
        storage_uri=storage_uri,
        parent_version_id=parent_version_id
    )
    db.add(db_ver)
    db.commit()
    db.refresh(db_ver)
    
    event_broker.publish("orqix.datasets", "DatasetVersionCreated", {
        "dataset_version_id": version_id,
        "dataset_id": dataset_id,
        "version": version,
        "hash": sha256_hash,
        "timestamp": db_ver.created_at.isoformat()
    })
    
    # Neo4j Log version node
    ver_query = """
    MERGE (dv:DatasetVersion {id: $id, version: $version, hash: $hash, size: $size})
    WITH dv
    MATCH (d:Dataset {id: $ds_id})
    MERGE (d)-[:HAS_VERSION]->(dv)
    """
    neo4j_client.execute_query(ver_query, {
        "id": version_id,
        "version": version,
        "hash": sha256_hash,
        "size": size_bytes,
        "ds_id": dataset_id
    })
    
    if parent_version_id:
        parent_query = """
        MATCH (dv:DatasetVersion {id: $id}), (parent:DatasetVersion {id: $parent_id})
        MERGE (dv)-[:DERIVED_FROM]->(parent)
        """
        neo4j_client.execute_query(parent_query, {"id": version_id, "parent_id": parent_version_id})
        in_memory_relationships.append({"source": version_id, "target": parent_version_id, "type": "DERIVED_FROM"})
        
    in_memory_nodes.append({"id": version_id, "label": f"{ds.name} v{version}", "type": "DatasetVersion"})
    in_memory_relationships.append({"source": dataset_id, "target": version_id, "type": "HAS_VERSION"})
    
    return {
        "id": db_ver.id,
        "dataset_id": db_ver.dataset_id,
        "version": db_ver.version,
        "hash": db_ver.hash,
        "size_bytes": db_ver.size_bytes,
        "storage_uri": db_ver.storage_uri,
        "parent_version_id": db_ver.parent_version_id,
        "created_at": db_ver.created_at
    }

@app.get("/datasets/{dataset_id}/versions", response_model=List[Dict[str, Any]])
def list_dataset_versions(dataset_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # Verify dataset ownership
    ds = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.org_id == current_user["org_id"]).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    versions = db.query(DatasetVersion).filter(DatasetVersion.dataset_id == dataset_id).order_by(DatasetVersion.created_at.desc()).all()
    return [{
        "id": v.id,
        "version": v.version,
        "hash": v.hash,
        "size_bytes": v.size_bytes,
        "storage_uri": v.storage_uri,
        "parent_version_id": v.parent_version_id,
        "created_at": v.created_at
    } for v in versions]

@app.get("/datasets/versions/{v_id}/diff", response_model=Dict[str, Any])
def diff_dataset_versions(v_id: str, compare_with_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    v1 = db.query(DatasetVersion).filter(DatasetVersion.id == v_id).first()
    v2 = db.query(DatasetVersion).filter(DatasetVersion.id == compare_with_id).first()
    
    if not v1 or not v2:
        raise HTTPException(status_code=404, detail="One or both dataset versions not found")
        
    size_diff = v1.size_bytes - v2.size_bytes
    hash_match = v1.hash == v2.hash
    
    return {
        "version_1": v1.version,
        "version_2": v2.version,
        "hash_1": v1.hash,
        "hash_2": v2.hash,
        "hashes_match": hash_match,
        "size_diff_bytes": size_diff,
        "size_diff_percentage": round((size_diff / v2.size_bytes) * 100.0, 2) if v2.size_bytes else 0
    }

# Lineage Graph Endpoints
@app.post("/lineage/node", dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def register_lineage_node(node_id: str, label: str, node_type: str):
    """
    Registers a node (e.g., Run, Model, Deployment) in the Neo4j lineage registry.
    """
    node_type = node_type.capitalize()
    if node_type not in ["Dataset", "Datasetversion", "Run", "Model", "Deployment"]:
         raise HTTPException(status_code=400, detail="Invalid lineage node type")
         
    query = f"MERGE (n:{node_type} {{id: $id, label: $label, created_at: $time}})"
    neo4j_client.execute_query(query, {
        "id": node_id,
        "label": label,
        "time": datetime.utcnow().isoformat()
    })
    
    # Store locally for fallback visualization
    existing = [n for n in in_memory_nodes if n["id"] == node_id]
    if not existing:
        in_memory_nodes.append({"id": node_id, "label": label, "type": node_type})
        
    return {"status": "success", "node_id": node_id}

@app.post("/lineage/edge", dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RESEARCHER]))])
def register_lineage_relationship(
    source_id: str,
    target_id: str,
    rel_type: str # e.g. PREPROCESSED_BY, PRODUCED, REGISTERED_IN, DEPLOYED_TO
):
    rel_type = rel_type.upper()
    
    # Match generic nodes and merge relationship
    query = f"""
    MATCH (s {{id: $source_id}}), (t {{id: $target_id}})
    MERGE (s)-[r:{rel_type}]->(t)
    RETURN count(r) as count
    """
    try:
        neo4j_client.execute_query(query, {
            "source_id": source_id,
            "target_id": target_id
        })
    except Exception as e:
        logger.warning(f"Neo4j edge registration error: {e}")

    # Add to in-memory graph
    edge = {"source": source_id, "target": target_id, "type": rel_type}
    if edge not in in_memory_relationships:
        in_memory_relationships.append(edge)
        
    event_broker.publish("orqix.datasets", "DatasetLineageUpdated", {
        "source_id": source_id,
        "target_id": target_id,
        "relationship_type": rel_type
    })
    
    return {"status": "success", "source": source_id, "target": target_id, "type": rel_type}

@app.get("/lineage/graph")
def get_lineage_graph(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Get the complete lineage tree to display inside visual graph components (e.g. React Flow).
    If Neo4j is offline, returns the in-memory fallback lineage tracking structure.
    """
    # Fetch from Neo4j if available
    query = """
    MATCH (n)
    OPTIONAL MATCH (n)-[r]->(m)
    RETURN n, r, m
    """
    nodes_map = {}
    edges = []
    
    try:
        results = neo4j_client.execute_query(query)
        for row in results:
            n = row.get("n")
            if n:
                n_id = n.get("id")
                # Detect node type from labels
                labels = list(n.labels)
                label_str = labels[0] if labels else "Node"
                nodes_map[n_id] = {
                    "id": n_id,
                    "label": n.get("label") or n.get("name") or n_id,
                    "type": label_str
                }
            
            r = row.get("r")
            m = row.get("m")
            if r and m:
                source = r.start_node.get("id")
                target = r.end_node.get("id")
                edges.append({
                    "source": source,
                    "target": target,
                    "type": r.type
                })
        
        # If we got nodes from Neo4j, return them
        if nodes_map:
            return {"nodes": list(nodes_map.values()), "edges": edges}
    except Exception as e:
        logger.warning(f"Neo4j query failed: {e}. Serving in-memory fallback graph.")
        
    # Return local in-memory mock registry
    return {
        "nodes": in_memory_nodes,
        "edges": in_memory_relationships
    }

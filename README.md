# Orqix: Distributed ML Experiment & Control Plane

Orqix is an AI-native, distributed machine learning experiment tracking, workflow scheduling, and model management platform. It features a microservices control plane built with FastAPI and a modern monochrome frontend cockpit built with Next.js, React Flow, and ChartJS.

---

## Architecture Overview

Orqix operates as a set of distributed Python microservices coupled with database and telemetry infrastructure:

### Backend Services
* **Gateway & Auth Service (Port `8000`)**: Authenticates users (JWT) and coordinates platform access controls. Includes health auditing.
* **Experiment Service (Port `8001`)**: Tracks experiments, runs, hyperparameters, and custom telemetry metrics. Includes websocket streams.
* **Workflow Service (Port `8002`)**: Coordinates execution of DAG pipelines across cluster workers.
* **Scheduler Service (Port `8003`)**: A dynamic, self-optimizing resources orchestrator that runs predictive OOM checks.
* **Dataset Service (Port `8004`)**: Manages dataset registrations, versioning, and object store uploads.
* **Registry Service (Port `8005`)**: Manages model version promotion lifecycle states (`DEV`, `STAGING`, `PRODUCTION`).
* **Agent Service (Port `8006`)**: An AI diagnostic failure agent that scans execution traces and recommends resolutions.

### Infrastructure (Docker Compose)
* **PostgreSQL (Port `5432`)**: Relational storage for experiments, runs, and metadata.
* **Redis (Port `6379`)**: Real-time event broker cache and pub-sub fallback.
* **Redpanda Kafka (Port `9092`)**: High-throughput distributed event streaming.
* **MinIO S3 (Ports `9000`/`9001`)**: Object storage for datasets and model checkpoints.
* **Neo4j (Ports `7474`/`7687`)**: Graph database tracking lineage graphs.
* **Prometheus (Port `9090`)**: Telemetry metrics collector.

---

## Prerequisites

Before starting, ensure you have installed:
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (select **AMD64 / x86_64** version)
* [Python 3.10+](https://www.python.org/)
* [Node.js 18+](https://nodejs.org/)

---

## Quick Start Guide

Follow these steps to run the complete Orqix stack locally:

### Step 1: Start Infrastructure Containers
Launch the database, storage, and message queue containers in detached mode:
```bash
docker compose up -d
```
*(Requires Docker Desktop to be running. If Kafka/Redis are not active, the backend automatically uses SQLite/Redis fallback mechanisms so you can still test.)*

### Step 2: Configure Python Virtual Environment
Navigate to the root directory and install dependencies:

**On Windows (PowerShell)**:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**On macOS / Linux**:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Launch Backend Control Plane
Run the services manager script. This initializes database schemas and seeds default researcher credentials, then spins up the 7 microservices:
```bash
python start_services.py
```
*(Keep this terminal window open)*

### Step 4: Run Frontend Development Cockpit
Open a new terminal window, navigate to the `frontend` directory, and start the Next.js development server:
```bash
cd frontend
npm run dev
```
*(Keep this terminal window open)*

Once compiled, navigate in your browser to:
* **Dashboard App**: `http://localhost:3000`

---

## Verification & Testing

To run the end-to-end platform verification flow (authenticating, submitting experiments, predicting OOM, tracking runs, registering models, and completing promotions):
```bash
# In a terminal with venv active:
python verify_platform.py
```

---

## Default Credentials
Seeded automatically during database startup:
* **Role**: Researcher
  * **Email**: `researcher@orqix.ai`
  * **Password**: `researcher_pass`
* **Role**: Admin
  * **Email**: `admin@orqix.ai`
  * **Password**: `admin_pass`

# Orqix

<p align="center">
  <img src="docs/assets/orqix-banner.png" alt="Orqix Banner" width="100%">
</p>

<p align="center">
  <strong>Distributed ML Experiment & Control Plane</strong>
</p>

<p align="center">
  AI-native platform for experiment tracking, workflow orchestration, lineage management, model lifecycle governance, and intelligent infrastructure scheduling.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-green.svg">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg">
  <img src="https://img.shields.io/badge/fastapi-microservices-green.svg">
  <img src="https://img.shields.io/badge/nextjs-dashboard-black.svg">
  <img src="https://img.shields.io/badge/kafka-event--driven-orange.svg">
  <img src="https://img.shields.io/badge/docker-ready-blue.svg">
</p>

---

## Overview

Orqix is a distributed Machine Learning Experiment Control Plane designed for modern MLOps environments.

The platform combines:

* Experiment Tracking
* Workflow Orchestration
* Dataset Versioning
* Lineage Management
* Model Registry
* Event-Driven Architecture
* AI Failure Diagnostics
* Resource Optimization

into a unified control plane built for scalable ML operations.

Unlike traditional experiment trackers, Orqix introduces a self-optimizing scheduler capable of predicting execution bottlenecks, identifying resource constraints, and assisting researchers through AI-driven diagnostics.

---

## Key Features

### Experiment Tracking

* Experiment lifecycle management
* Run comparison
* Hyperparameter logging
* Metrics tracking
* Artifact association
* Real-time telemetry streams

### Workflow Orchestration

* DAG-based execution engine
* Dependency resolution
* Retry policies
* Parallel execution
* Workflow monitoring

### Dataset Management

* Dataset registration
* Version control
* Metadata tracking
* Object storage integration
* Dataset lineage visualization

### Model Registry

* Version management
* Stage promotion workflows
* Deployment history
* Rollback support

### Intelligent Scheduling

* Predictive OOM detection
* Resource utilization forecasting
* Dynamic workload balancing
* Self-optimizing execution strategies

### AI Diagnostic Agent

* Failure analysis
* Root cause detection
* Infrastructure recommendations
* Experiment optimization insights

### Observability

* Prometheus metrics
* Live dashboards
* Cluster telemetry
* Event tracing

---

## Architecture

```text
                     ┌─────────────────┐
                     │    Frontend     │
                     │     Next.js     │
                     └────────┬────────┘
                              │
                              ▼
                  ┌─────────────────────┐
                  │ Gateway & Auth API  │
                  └─────────┬───────────┘
                            │
 ┌──────────────┬───────────┼───────────┬──────────────┐
 ▼              ▼           ▼           ▼              ▼

Experiment   Workflow   Scheduler   Dataset     Registry
 Service      Service    Service     Service      Service

 └──────────────┬─────────────┬──────────────┬──────────┘
                ▼             ▼              ▼

           PostgreSQL     Kafka       Neo4j Graph

                ▼             ▼              ▼

              Redis      MinIO S3      Prometheus

                              ▼

                        Agent Service
```

---

## Microservices

| Service        | Port | Responsibility                |
| -------------- | ---- | ----------------------------- |
| Gateway & Auth | 8000 | Authentication, Authorization |
| Experiment     | 8001 | Experiments & Runs            |
| Workflow       | 8002 | DAG Execution                 |
| Scheduler      | 8003 | Resource Allocation           |
| Dataset        | 8004 | Dataset Versioning            |
| Registry       | 8005 | Model Registry                |
| Agent          | 8006 | AI Diagnostics                |

---

## Infrastructure Stack

| Component      | Purpose          |
| -------------- | ---------------- |
| PostgreSQL     | Metadata Store   |
| Redis          | Cache & Pub/Sub  |
| Redpanda Kafka | Event Streaming  |
| MinIO          | Object Storage   |
| Neo4j          | Lineage Graph    |
| Prometheus     | Monitoring       |
| Docker         | Containerization |

---

## Quick Start

### 1. Start Infrastructure

```bash
docker compose up -d
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

Windows:

```bash
.\venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Launch Backend

```bash
python start_services.py
```

### 4. Launch Frontend

```bash
cd frontend

npm install

npm run dev
```

Open:

```text
http://localhost:3000
```

---

## Platform Verification

Execute a complete end-to-end validation workflow:

```bash
python verify_platform.py
```

This verifies:

* Authentication
* Experiment Creation
* Run Tracking
* OOM Prediction
* Dataset Registration
* Model Promotion
* Agent Diagnostics

---

## Default Credentials

### Researcher

```text
Email: researcher@orqix.ai
Password: researcher_pass
```

### Administrator

```text
Email: admin@orqix.ai
Password: admin_pass
```

---

## Roadmap

* Kubernetes Native Deployment
* Distributed Worker Pools
* Ray Integration
* Bayesian Hyperparameter Optimization
* AutoML Pipelines
* Multi-Tenant Organizations
* RBAC Enforcement
* LLM Copilot for Experiment Planning
* Cost Prediction Engine
* Runtime Prediction Engine

---

## Security

* JWT Authentication
* Role-Based Access Control
* Service Isolation
* Audit Logging
* Secure Object Storage

---

## License

MIT License

Copyright (c) 2026

Purnendu Raghav Srivastava

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software.

See the LICENSE file for complete details.

---

## Author

### Purnendu Raghav Srivastava

---

⭐ If you find Orqix useful, consider starring the repository.

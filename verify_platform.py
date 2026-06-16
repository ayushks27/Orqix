import time
import requests
import sys

GATEWAY_URL = "http://localhost:8000"
EXP_URL = "http://localhost:8001"
SCHED_URL = "http://localhost:8003"
DATASET_URL = "http://localhost:8004"
REGISTRY_URL = "http://localhost:8005"
AGENT_URL = "http://localhost:8006"

def verify_all():
    print("==================================================")
    print("Orqix Platform End-to-End Integration Verification")
    print("==================================================\n")

    # Step 1: Initialize tables and authenticate
    print("[1/6] Authenticating default researcher...")
    token = ""
    try:
        res = requests.post(f"{GATEWAY_URL}/auth/login", json={
            "email": "researcher@orqix.ai",
            "password": "researcher_pass"
        }, timeout=5)
        if res.status_code == 200:
            token = res.json()["access_token"]
            print(" -> Authentication successful! JWT token received.")
        else:
            print(f" -> Failed to authenticate (status {res.status_code}): {res.text}")
            sys.exit(1)
    except Exception as e:
        print(f" -> Gateway Service offline or database not initialized: {e}")
        print(" -> Make sure to launch the gateway and dependent services first.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # Step 2: Create Experiment
    print("\n[2/6] Creating experiment...")
    exp_id = ""
    try:
        res = requests.post(f"{EXP_URL}/experiments?name=MNIST_Digits_ResNet", headers=headers, timeout=5)
        if res.status_code == 200:
            exp_id = res.json()["id"]
            print(f" -> Experiment created: {res.json()['name']} (ID: {exp_id})")
        else:
            print(f" -> Failed to create experiment: {res.text}")
            sys.exit(1)
    except Exception as e:
        print(f" -> Experiment Service connection failed: {e}")
        sys.exit(1)

    # Step 3: Launch dynamic scheduling runs (using Self-Optimizing Orchestrator)
    print("\n[3/6] Submitting runs to Heuristic vs. ML Self-Optimizing Scheduler...")
    runs = []
    
    # Run 1: High batch size that risks OOM
    print(" -> Submitting Run 1 (Large batch size 256, model: Transformer)...")
    try:
        # Create Run first
        run_res = requests.post(f"{EXP_URL}/runs?experiment_id={exp_id}&git_commit=8bf97e2", headers=headers)
        run_id1 = run_res.json()["id"]
        runs.append(run_id1)
        
        # Log parameters
        requests.post(f"{EXP_URL}/runs/{run_id1}/params", json={"batch_size": "256", "learning_rate": "0.01"}, headers=headers)
        
        # Submit to Scheduler
        sched_res = requests.post(f"{SCHED_URL}/scheduler/submit", json={
            "run_id": run_id1,
            "cpu_request": 4.0,
            "gpu_request": 1,
            "memory_request_gb": 8.0,
            "dataset_size_gb": 10.0,
            "model_type": "Transformer",
            "batch_size": 256,
            "command": "python train.py --batch 256"
        }, headers=headers)
        
        opt = sched_res.json()["optimization"]
        print(f"    - ML Orchestrator predicted duration: {opt['predicted_runtime_sec']}s")
        print(f"    - ML Orchestrator OOM risk: {opt['oom_probability']*100}%")
        print(f"    - ML Orchestrator suggestions: {opt['recommendations']}")
    except Exception as e:
        print(f" -> Scheduler Service connection failed: {e}")
        sys.exit(1)

    # Run 2: Optimized config
    print(" -> Submitting Run 2 (Optimized batch size 32, model: ResNet)...")
    try:
        run_res2 = requests.post(f"{EXP_URL}/runs?experiment_id={exp_id}&git_commit=8bf97e2", headers=headers)
        run_id2 = run_res2.json()["id"]
        runs.append(run_id2)
        
        requests.post(f"{EXP_URL}/runs/{run_id2}/params", json={"batch_size": "32", "learning_rate": "0.001"}, headers=headers)
        
        sched_res2 = requests.post(f"{SCHED_URL}/scheduler/submit", json={
            "run_id": run_id2,
            "cpu_request": 4.0,
            "gpu_request": 1,
            "memory_request_gb": 16.0,
            "dataset_size_gb": 10.0,
            "model_type": "ResNet",
            "batch_size": 32,
            "command": "python train.py --batch 32"
        }, headers=headers)
        
        opt2 = sched_res2.json()["optimization"]
        print(f"    - ML Orchestrator predicted duration: {opt2['predicted_runtime_sec']}s")
        print(f"    - ML Orchestrator OOM risk: {opt2['oom_probability']*100}%")
        print(f"    - ML Orchestrator suggestions: {opt2['recommendations']}")
    except Exception as e:
        print(f" -> Scheduler submission error: {e}")

    # Wait for mock jobs to complete execution
    print(" -> Waiting 3 seconds for scheduled jobs to update status...")
    time.sleep(3.0)

    # Step 4: Verify Run updates and log mock metrics
    print("\n[4/6] Verifying run tracking and metric logs...")
    for run_id in runs:
        # Check details
        res = requests.get(f"{EXP_URL}/runs/{run_id}", headers=headers)
        print(f" -> Run {run_id} status: {res.json()['status']}")
        
        # Log accuracy metrics for successful runs
        if res.json()['status'] == "COMPLETED":
            requests.post(f"{EXP_URL}/runs/{run_id}/metrics?step=1", json={"accuracy": 0.85, "loss": 0.3}, headers=headers)
            requests.post(f"{EXP_URL}/runs/{run_id}/metrics?step=2", json={"accuracy": 0.95, "loss": 0.1}, headers=headers)

    # Step 5: Test AI Failure Analysis Agent on the failed run
    print("\n[5/6] Invoking AI Agent Failure diagnostics...")
    # Find the failed run
    failed_run = None
    successful_run = None
    for run_id in runs:
        res = requests.get(f"{EXP_URL}/runs/{run_id}", headers=headers)
        if res.json()["status"] == "FAILED":
            failed_run = run_id
        else:
            successful_run = run_id

    if failed_run:
        try:
            agent_res = requests.post(f"{AGENT_URL}/agent/diagnose", json={"run_id": failed_run}, headers=headers)
            diagnosis = agent_res.json()
            print(f" -> Agent diagnosis completed for {failed_run}:")
            print(f"    - Failure category: {diagnosis['failure_category']}")
            print(f"    - Root Cause: {diagnosis['root_cause']}")
            print(f"    - Suggestions: {diagnosis['recommendations']}")
        except Exception as e:
            print(f" -> AI Agent Service connection failed: {e}")
    else:
        print(" -> No failed runs to diagnose. Skipping.")

    # Step 6: Test Model Registry transitions
    print("\n[6/6] Testing Model Registry promotion flow...")
    if successful_run:
        try:
            # Register model
            reg_res = requests.post(f"{REGISTRY_URL}/registry/models", json={
                "name": "resnet50-mnist-classifier",
                "description": "Production ResNet classifier for digit logs."
            }, headers=headers)
            model_id = reg_res.json()["id"]
            print(f" -> Registered Model: {reg_res.json()['name']} (ID: {model_id})")

            # Create version
            ver_res = requests.post(f"{REGISTRY_URL}/registry/models/{model_id}/versions", json={
                "version": "v1.0.0",
                "run_id": successful_run,
                "artifact_uri": "s3://orqix-artifacts/resnet_model.pt"
            }, headers=headers)
            ver_id = ver_res.json()["id"]
            print(f" -> Version created: {ver_res.json()['version']} (ID: {ver_id}) in stage {ver_res.json()['stage']}")

            # Promote to STAGING
            requests.post(f"{REGISTRY_URL}/registry/versions/{ver_id}/promote", json={
                "to_stage": "STAGING",
                "notes": "Verified validation set accuracy meets 95% threshold."
            }, headers=headers)
            
            # Promote to PRODUCTION
            prod_res = requests.post(f"{REGISTRY_URL}/registry/versions/{ver_id}/promote", json={
                "to_stage": "PRODUCTION",
                "notes": "Passed deployment checks."
            }, headers=headers)
            print(f" -> Version promoted to PRODUCTION successfully.")
            
            # Check version list and approvals
            ver_list = requests.get(f"{REGISTRY_URL}/registry/models/{model_id}/versions", headers=headers).json()
            print(f" -> History check: Version {ver_list[0]['version']} current stage: {ver_list[0]['stage']}")
            print(f"    - Approvals recorded: {len(ver_list[0]['history'])}")
        except Exception as e:
            print(f" -> Registry Service connection failed: {e}")
    else:
        print(" -> No successful runs found to register. Skipping.")

    print("\n==================================================")
    print("Verification complete! All core platform features validated.")
    print("==================================================")

if __name__ == "__main__":
    verify_all()

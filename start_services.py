import subprocess
import time
import sys
import os

services = [
    {"name": "Gateway (Port 8000)", "command": ["uvicorn", "services.gateway.main:app", "--port", "8000"]},
    {"name": "Experiment (Port 8001)", "command": ["uvicorn", "services.experiment.main:app", "--port", "8001"]},
    {"name": "Workflow (Port 8002)", "command": ["uvicorn", "services.workflow.main:app", "--port", "8002"]},
    {"name": "Scheduler (Port 8003)", "command": ["uvicorn", "services.scheduler.main:app", "--port", "8003"]},
    {"name": "Dataset (Port 8004)", "command": ["uvicorn", "services.dataset.main:app", "--port", "8004"]},
    {"name": "Registry (Port 8005)", "command": ["uvicorn", "services.registry.main:app", "--port", "8005"]},
    {"name": "Agent (Port 8006)", "command": ["uvicorn", "services.agent.main:app", "--port", "8006"]},
]

processes = []

def start_all():
    print("==================================================")
    print("Orqix Backend Microservices Local Runner")
    print("==================================================")
    
    # Check virtualenv environment or pip paths
    os.environ["PYTHONPATH"] = os.getcwd()
    
    # Initialize DB schema first
    print("\nInitializing PostgreSQL database tables...")
    try:
        subprocess.run([sys.executable, "shared/init_db.py"], check=True)
    except Exception as e:
        print(f"Database setup script failed: {e}")
        print("Please ensure PostgreSQL is running and credentials match in settings.")
        sys.exit(1)

    print("\nStarting microservices...")
    for s in services:
        print(f" -> Launching {s['name']}...")
        p = subprocess.Popen(
            [sys.executable, "-m"] + s["command"],
            stdout=None,
            stderr=None,
            text=True
        )
        processes.append((s["name"], p))
        time.sleep(1) # stagger startups

    print("\nAll microservices launched. Press Ctrl+C to terminate all services.\n")
    
    try:
        while True:
            for name, p in processes:
                # check if process has died
                ret = p.poll()
                if ret is not None:
                    print(f"\n[WARNING] {name} terminated with code {ret}")
                    # read output
                    out, err = p.communicate()
                    print(f"Stdout:\n{out}\nStderr:\n{err}")
                    processes.remove((name, p))
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nShutting down all processes...")
        for name, p in processes:
            print(f" -> Terminating {name}...")
            p.terminate()
            p.wait()
        print("All processes stopped.")

if __name__ == "__main__":
    start_all()

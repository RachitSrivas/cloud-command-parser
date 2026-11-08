# Cloud Computing (CS3081) Mini Project: Knowledge Distillation & Microservice Deployment

**Student Name:** Rachit Srivastava  
**Roll Number:** 230101085  
**GitHub Repository:** (https://github.com/RachitSrivas/cloud-command-parser)  

---

## Overview
This repository contains an end-to-end cloud computing and MLOps system that performs sequence-level knowledge distillation from a larger teacher language model (`Phi-3.5-mini-instruct`, 3.8B parameters) into an ultra-compact student model (`EleutherAI/pythia-70m`, 70M parameters) deployed as a containerized microservice on a local Kubernetes (`k3d`) cluster.

The system features:
- **Object Storage:** SeaweedFS (S3-compatible) deployed in the `data` namespace.
- **Microservice:** FastAPI service enforcing a strict 4-key JSON schema with CPU-only PyTorch wheels (<2GB image).
- **Orchestration:** K3d Kubernetes cluster with Traefik Ingress, Liveness/Readiness probes, and Horizontal Pod Autoscaler (HPA).
- **Networking:** Custom VLSM subnetting (`10.20.0.0/16`) and stateless Network Access Control List (NACL) verification.
- **CI/CD:** Automated GitHub Actions pipeline featuring secret scanning (Gitleaks), linting, unit testing, model evaluation, and a 95% JSON validity quality gate.

---

## Directory Structure

```
├── .github/workflows/
│   └── ci.yml               # GitHub Actions CI/CD Quality Gate Pipeline
├── cluster/
│   └── k3d.yaml             # k3d Kubernetes cluster configuration
├── data/
│   ├── commands_pool.jsonl  # 3,000 raw input commands
│   ├── validation.jsonl     # 100 gold validation commands
│   ├── schema.json          # Output schema & intent definitions
│   └── rate_card.json       # Cost evaluation parameters
├── datasets/
│   ├── teacher/             # Raw sharded teacher model outputs
│   └── v1/
│       ├── train.jsonl      # Cleaned training dataset
│       └── train.sha256     # Dataset SHA-256 checksum
├── k8s/
│   ├── deployment.yaml      # Microservice deployment (2 replicas, CPU/mem limits)
│   ├── service.yaml         # Internal ClusterIP service
│   ├── ingress.yaml         # Traefik Ingress routing /parse
│   ├── hpa.yaml             # Horizontal Pod Autoscaler (1-2 replicas, 70% CPU)
│   ├── secret.yaml          # S3 credentials secret
│   ├── seaweedfs.yaml       # S3-compatible SeaweedFS deployment
│   └── pipeline.yaml        # Parallel teacher labelling jobs
├── models/
│   ├── v1/                  # Student model v1 artefacts & checksum
│   └── v2/                  # Student model v2 artefacts & checksum
├── network/
│   ├── nacl.json            # Public subnet stateless firewall rules
│   ├── packets_sample.jsonl # Sample verification packets
│   └── subnets.md           # VLSM subnetting calculations & NACL write-up
├── prompts/
│   └── teacher_prompt.txt   # Prompt template for Phi-3.5-mini teacher
├── report/
│   └── report.pdf           # Comprehensive 8-page architectural report
├── results/                 # Locust load test metrics, evaluations, and logs
├── service/
│   ├── app.py               # FastAPI inference microservice
│   ├── Dockerfile           # Minimal CPU-only container image (<2GB)
│   └── requirements.txt     # Pinned Python dependencies
├── tests/
│   ├── test_data.py         # Unit tests for data schema & intents
│   ├── test_nacl.py         # Unit tests for NACL packet simulator
│   └── test_service.py      # Unit tests for service validation & fault injection
├── tools/
│   ├── locustfile.py        # Locust load testing script
│   ├── nacl_sim.py          # Stateless NACL packet simulator
│   └── score.py             # Evaluation scoring script
├── training/
│   ├── config.yaml          # Hyperparameters and library versions
│   ├── train.py             # CPU-based PyTorch/Transformers training script
│   └── loss.csv             # Epoch-by-epoch training loss records
├── worker/
│   ├── worker.py            # Sharded teacher labelling worker
│   └── clean.py             # Shard aggregation & validation filter script
├── 230101085.pdf            # Scanned 3-page handwritten reflection notes
├── AI_USE.md                # AI usage disclosure and verification methodology
├── Makefile                 # One-command build, deployment, test, and teardown
└── README.md                # Project documentation
```

---

## Quickstart & Execution Instructions

### 1. Build and Deploy (`make up`)
To spin up the local Kubernetes cluster, launch SeaweedFS, build the container image, and deploy the entire microservice:
```bash
make up
```
*Behind the scenes, this executes:*
1. `k3d cluster create --config cluster/k3d.yaml`
2. `kubectl apply -f k8s/seaweedfs.yaml`
3. `docker build -t parser-service:v1 service/` and imports it into k3d, applying all manifests in `k8s/`.

### 2. Testing and Validation
Run all unit tests:
```bash
make test
```
Verify the stateless NACL rules against packet samples:
```bash
make nacl-check
```

### 3. Student Model Training
To train the student model on CPU (with fixed seed=42 and hyperparameters in `training/config.yaml`):
```bash
make train
```
To verify training quickly on a 50-example subset:
```bash
make train SUBSET=50
```

### 4. Load Testing (Locust)
Run the headless Locust benchmark against the ingress endpoint on port 8080:
```bash
locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m --host http://localhost:8080 --csv results/loadtest
```

### 5. Cluster Teardown (`make down`)
To cleanly terminate and delete the k3d cluster and associated resources:
```bash
make down
```

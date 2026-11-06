# AI Use Disclosure and Verification (CS3081 Mini Project)

**Student Name:** Rachit Srivastava  
**Roll Number:** 230101085  
**Course:** Cloud Computing (CS3081)  

---

## 1. AI Tools Used

| Tool / Model | Version / Provider | Purpose in Project |
| :--- | :--- | :--- |
| **Phi-3.5-mini-instruct** | Ollama local runtime (`3.8B` parameters) | Teacher model for Knowledge Distillation (Task 1). Generated 4-key JSON labels on natural language command pool. |
| **EleutherAI/pythia-70m** | Hugging Face Transformers | Student causal language model (`70M` parameters) fine-tuned on CPU via sequence distillation (Task 2). |
| **Antigravity (Gemini)** | Google DeepMind Agentic Assistant | Pair-programming assistant used for code structuring, Kubernetes manifest scaffolding, subnet arithmetic calculation, and LaTeX report preparation. |

---

## 2. Detailed Breakdown of Usage and Tasks

### Task 1: Teacher Prompt Engineering & Sharded Worker Architecture
- **Usage:** Formulating the prompt in `prompts/teacher_prompt.txt` to guide Phi-3.5-mini-instruct to return strictly the four specified keys (`intent`, `date`, `time`, `place`) without markdown code fences or explanatory conversational text.
- **Verification:** Ran test runs on samples from `commands_pool.jsonl`. Verified that the outputs parsed correctly with Python's `json.loads` and strictly followed the 3 slot copying rules and 8 canonical intents.

### Task 2: Sequence-Level Knowledge Distillation Pipeline
- **Usage:** Designing PyTorch and Hugging Face training scripts (`training/train.py`) optimized for CPU training with fixed seeds, memory caching, and subset execution (`SUBSET=50`).
- **Verification:** Tested CPU training loop with `--subset 50` to verify convergence, gradient updates, and epoch loss output in `training/loss.csv`. Evaluated student predictions against `data/validation.jsonl` using `tools/score.py`.

### Task 3 & 4: Microservice Containerization and Local Kubernetes Orchestration
- **Usage:** Writing FastAPI microservice (`service/app.py`), lightweight multi-stage Dockerfile (`service/Dockerfile`), and declarative Kubernetes manifests (`k8s/`).
- **Verification:**
  - Tested container memory constraints (under 1 CPU / 1 GiB memory limit).
  - Validated health probes (`/healthz` returning 200, `/readyz` returning 503 until model weights load).
  - Verified fault injection (`FAULT_INJECT=1` returning HTTP 500 with `{"error": "invalid_model_output"}`).
  - Validated k3d Traefik Ingress routing for `/parse`.

### Task 5: Subnet Allocation & NACL Configuration
- **Usage:** Assisted in cross-checking binary math and CIDR block calculations for partitioning `10.20.0.0/16` into four contiguous subnets (`app`, `public`, `data`, `management`).
- **Verification:** Ran `tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check`, obtaining 100.0% verification score across all sample packets.

### Task 6 & 7: CI/CD Pipeline, Locust Benchmarking & SRE Analysis
- **Usage:** Structuring GitHub Actions workflow stages (`.github/workflows/ci.yml`), Gitleaks integration, cost modeling using `data/rate_card.json`, and SLO/error budget definitions.
- **Verification:** Checked YAML syntax with lint tools, manually validated rate card hourly math, and verified secret scan status.

---

## 3. Human Verification and Quality Control Methodology

1. **Independent Verification of Calculations:** All subnet masks, usable host counts, broadcast addresses, and rate-card cost formulas were manually computed on paper and checked against networking fundamentals before writing to documentation.
2. **Deterministic Code Validation:** Every generated script was run locally with automated test cases (`tests/test_service.py`, `tests/test_data.py`, `tests/test_nacl.py`).
3. **No Blind Acceptance:** Generated model predictions were strictly passed through automated filter scripts (`worker/clean.py` and `tools/score.py`). Any output deviating from the 4-key schema or halluncinating slot values was systematically logged and rejected.

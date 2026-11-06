.PHONY: all up down train test clean-data nacl-check lint docker-build

CLUSTER_NAME = cloud-cluster
SUBSET ?=

all: up

up:
	@echo "=== [1/3] Creating k3d cluster from config ==="
	k3d cluster create --config cluster/k3d.yaml || true
	@echo "=== [2/3] Deploying SeaweedFS in data namespace ==="
	kubectl apply -f k8s/seaweedfs.yaml
	@echo "=== [3/3] Building image and deploying microservice ==="
	docker build -t parser-service:v1 service/
	k3d image import parser-service:v1 -c $(CLUSTER_NAME) || true
	kubectl apply -f k8s/secret.yaml
	kubectl apply -f k8s/deployment.yaml
	kubectl apply -f k8s/service.yaml
	kubectl apply -f k8s/ingress.yaml
	kubectl apply -f k8s/hpa.yaml
	@echo "Deployment complete! Service available via Ingress on http://localhost:8080/parse"

down:
	@echo "=== Deleting k3d cluster ==="
	k3d cluster delete $(CLUSTER_NAME) || true

train:
	@echo "=== Running Student Model Training ==="
	python training/train.py $(if $(SUBSET),--subset $(SUBSET),)

test:
	@echo "=== Running Unit Tests ==="
	pytest -v tests/

clean-data:
	@echo "=== Cleaning Teacher Shard Outputs ==="
	python worker/clean.py --shard-dir datasets/teacher --output datasets/v1/train.jsonl --checksum datasets/v1/train.sha256

nacl-check:
	@echo "=== Verifying Stateless NACL ==="
	python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check

lint:
	flake8 worker/ training/ service/ tests/ tools/ --count --select=E9,F63,F7,F82 --show-source --statistics

docker-build:
	docker build -t parser-service:v1 service/

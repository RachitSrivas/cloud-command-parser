import json
import os
import re
import socket
import sys
import boto3
from botocore.client import Config
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configuration from environment variables
MODEL_URI = os.environ.get("MODEL_URI", "s3://models/v1")
MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://seaweedfs-s3.data.svc.cluster.local:8333")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "64"))
FAULT_INJECT = os.environ.get("FAULT_INJECT", "0")
POD_NAME = os.environ.get("HOSTNAME", socket.gethostname())

VALID_INTENTS = {
    "alarm_set",
    "alarm_query",
    "calendar_set",
    "calendar_query",
    "calendar_remove",
    "weather_query",
    "datetime_query",
    "recommendation_events",
}
EXPECTED_KEYS = {"intent", "date", "time", "place"}

app = FastAPI(title="Command Parsing Microservice")

# Global model state
is_ready = False
model = None
tokenizer = None


class ParseRequest(BaseModel):
    text: str


def download_model_from_s3(s3_uri: str, target_dir: str):
    """Downloads model files from S3/SeaweedFS if configured, or copies local."""
    os.makedirs(target_dir, exist_ok=True)
    if s3_uri.startswith("s3://"):
        parts = s3_uri[5:].split("/", 1)
        bucket_name = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""

        print(f"Connecting to S3: {S3_ENDPOINT}, bucket: {bucket_name}, prefix: {prefix}")
        s3 = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "seaweed_user"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "seaweed_secret"),
            config=Config(signature_version="s3v4"),
        )
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel_path = os.path.relpath(key, prefix) if prefix else key
                dest_path = os.path.join(target_dir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                print(f"Downloading {key} -> {dest_path}")
                s3.download_file(bucket_name, key, dest_path)
    elif os.path.exists(s3_uri):
        import shutil
        print(f"Copying local model from {s3_uri} to {target_dir}")
        for item in os.listdir(s3_uri):
            s = os.path.join(s3_uri, item)
            d = os.path.join(target_dir, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)


@app.on_event("startup")
def startup_event():
    global model, tokenizer, is_ready
    print(f"Starting inference service for model version {MODEL_VERSION} on pod {POD_NAME}")
    local_model_path = "/tmp/model"
    try:
        download_model_from_s3(MODEL_URI, local_model_path)
    except Exception as e:
        print(f"S3 download warning / fallback to local: {e}")
        local_model_path = MODEL_URI

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        print(f"Loading model and tokenizer from {local_model_path}...")
        tokenizer = AutoTokenizer.from_pretrained(local_model_path)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(local_model_path)
        model.eval()
        is_ready = True
        print("Model successfully loaded and ready for traffic.")
    except Exception as e:
        print(f"Failed to load model: {e}", file=sys.stderr)
        # Keep is_ready as False so readyz returns 503


@app.get("/healthz")
def healthz():
    return Response(content="OK", status_code=200, media_type="text/plain")


@app.get("/readyz")
def readyz():
    if is_ready:
        return Response(content="READY", status_code=200, media_type="text/plain")
    return Response(content="NOT_READY", status_code=503, media_type="text/plain")


def validate_prediction(raw_text: str):
    """Strictly validates four-key JSON schema. Returns (is_valid, parsed_obj)."""
    try:
        # Extract json substring if model generates leading/trailing whitespace
        s = raw_text.strip()
        match = re.search(r"\{.*?\}", s, re.DOTALL)
        if not match:
            return False, None
        data = json.loads(match.group(0))
        if not isinstance(data, dict):
            return False, None
        if set(data.keys()) != EXPECTED_KEYS:
            return False, None
        if data.get("intent") not in VALID_INTENTS:
            return False, None
        for k in ("date", "time", "place"):
            v = data.get(k)
            if v is not None and not isinstance(v, str):
                return False, None
        return True, data
    except Exception:
        return False, None


@app.post("/parse")
async def parse_command(req: ParseRequest):
    if not is_ready or model is None or tokenizer is None:
        return Response(content="Service Not Ready", status_code=503)

    fault_inject = os.environ.get("FAULT_INJECT", FAULT_INJECT)
    if fault_inject == "1":
        # Fault injection mode: replace output with 'not json'
        raw_output = "not json"
    else:
        import torch

        prompt = f"Command: {req.text}\nJSON:"
        inputs = tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            output_tokens = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated_text = tokenizer.decode(output_tokens[0], skip_special_tokens=True)
        raw_output = generated_text[len(prompt) :].strip()

    is_valid, parsed_json = validate_prediction(raw_output)

    headers = {
        "X-Model-Version": MODEL_VERSION,
        "X-Served-By": POD_NAME,
    }

    if not is_valid:
        return JSONResponse(
            status_code=500,
            content={"error": "invalid_model_output"},
            headers=headers,
        )

    return JSONResponse(
        status_code=200,
        content=parsed_json,
        headers=headers,
    )

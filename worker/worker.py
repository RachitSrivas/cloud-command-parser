#!/usr/bin/env python3
"""worker.py - Sharded worker that processes commands_pool.jsonl using Ollama teacher model.

Reads:
  - SHARD_INDEX (int, default 0)
  - SHARD_COUNT (int, default 1)
  - OLLAMA_HOST (str, default http://localhost:11434)
  - INPUT_FILE (str, default data/commands_pool.jsonl)
  - OUTPUT_DIR (str, default datasets/teacher)
  - PROMPT_FILE (str, default prompts/teacher_prompt.txt)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

def query_ollama(prompt: str, ollama_host: str, model: str = "phi3.5") -> str:
    url = f"{ollama_host.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "seed": 42
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                res_obj = json.loads(resp.read().decode("utf-8"))
                return res_obj.get("response", "").strip()
        except Exception as e:
            time.sleep(2 ** attempt)
            if attempt == 2:
                print(f"Failed to query Ollama after 3 attempts: {e}", file=sys.stderr)
                return ""


def run_worker():
    shard_index = int(os.environ.get("SHARD_INDEX", "0"))
    shard_count = int(os.environ.get("SHARD_COUNT", "1"))
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    input_file = os.environ.get("INPUT_FILE", "data/commands_pool.jsonl")
    output_dir = os.environ.get("OUTPUT_DIR", "datasets/teacher")
    prompt_file = os.environ.get("PROMPT_FILE", "prompts/teacher_prompt.txt")

    print(f"Starting Worker: Shard {shard_index} / {shard_count}")
    print(f"Input: {input_file}")
    print(f"Ollama: {ollama_host}")

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"shard-{shard_index}.jsonl")

    # Load prompt template
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Load input pool
    commands = []
    with open(input_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            if idx % shard_count == shard_index:
                commands.append((idx, json.loads(line)))

    print(f"Shard {shard_index} processing {len(commands)} assigned commands...")

    # Load existing processed IDs if resuming
    processed_ids = set()
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line.strip())
                    processed_ids.add(item["id"])

    with open(output_file, "a", encoding="utf-8") as out_f:
        for count, (line_no, item) in enumerate(commands, 1):
            cmd_id = item["id"]
            cmd_text = item["text"]
            if cmd_id in processed_ids:
                continue

            full_prompt = prompt_template.replace("{text}", cmd_text)
            reply = query_ollama(full_prompt, ollama_host=ollama_host)

            out_record = {
                "id": cmd_id,
                "text": cmd_text,
                "teacher_raw": reply
            }
            out_f.write(json.dumps(out_record, ensure_ascii=False) + "\n")
            out_f.flush()

            if count % 50 == 0 or count == len(commands):
                print(f"Shard {shard_index}: Completed {count}/{len(commands)} commands")

    print(f"Shard {shard_index} finished successfully -> {output_file}")


if __name__ == "__main__":
    run_worker()

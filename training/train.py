#!/usr/bin/env python3
"""train.py - Fine-tunes EleutherAI/pythia-70m on CPU using Sequence Distillation.

Reads hyperparameters from training/config.yaml.
Supports subset training: --subset N (e.g., make train SUBSET=50).
Outputs:
  - models/v1/ (or models/v2/): config.json, model.safetensors, tokenizer files
  - models/v1/model.sha256
  - training/loss.csv (epoch, loss)
"""

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import numpy as np
import yaml

# Lazy/conditional import for torch & transformers to allow help text and inspection
try:
    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, AdamW, get_linear_schedule_with_warmup
except ImportError:
    torch = None


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    if torch:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def compute_sha256_tree(model_dir: str, output_file: str):
    """Computes SHA-256 checksums of all model files in model_dir."""
    checksums = []
    for root, _, files in os.walk(model_dir):
        for f in sorted(files):
            if f.endswith(".sha256"):
                continue
            fpath = os.path.join(root, f)
            relpath = os.path.relpath(fpath, model_dir)
            sha = hashlib.sha256()
            with open(fpath, "rb") as fh:
                while chunk := fh.read(65536):
                    sha.update(chunk)
            checksums.append(f"{sha.hexdigest()}  {relpath}")

    with open(output_file, "w", encoding="utf-8") as out:
        out.write("\n".join(checksums) + "\n")
    print(f"Generated checksum file: {output_file}")


class CommandJSONDataset(Dataset):
    def __init__(self, data, tokenizer, max_length=128):
        self.examples = []
        for item in data:
            cmd = item.get("text", "")
            # Canonical 4-key JSON string
            json_obj = {
                "intent": item.get("intent"),
                "date": item.get("date"),
                "time": item.get("time"),
                "place": item.get("place")
            }
            json_str = json.dumps(json_obj, ensure_ascii=False)
            prompt = f"Command: {cmd}\nJSON: {json_str}"
            
            enc = tokenizer(
                prompt,
                truncation=True,
                max_length=max_length,
                padding="max_length",
                return_tensors="pt"
            )
            input_ids = enc["input_ids"].squeeze(0)
            attention_mask = enc["attention_mask"].squeeze(0)
            
            # For causal LM, labels are input_ids with pad tokens masked to -100
            labels = input_ids.clone()
            labels[labels == tokenizer.pad_token_id] = -100
            
            self.examples.append({
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": labels
            })

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        return self.examples[idx]


def main():
    parser = argparse.ArgumentParser(description="Train Student Model")
    parser.add_argument("--config", default="training/config.yaml", help="Path to config.yaml")
    parser.add_argument("--data", default="datasets/v1/train.jsonl", help="Path to train.jsonl")
    parser.add_argument("--output-dir", default="models/v1", help="Output model directory")
    parser.add_argument("--subset", type=int, default=None, help="Train on first N records only")
    parser.add_argument("--epochs", type=int, default=None, help="Override number of epochs")
    parser.add_argument("--loss-csv", default="training/loss.csv", help="Loss tracking CSV")
    args = parser.parse_args()

    if torch is None:
        print("Error: PyTorch and Transformers must be installed to run training.", file=sys.stderr)
        sys.exit(1)

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    seed = cfg.get("seed", 42)
    lr = float(cfg.get("learning_rate", 5e-5))
    batch_size = int(cfg.get("batch_size", 8))
    num_epochs = args.epochs or int(cfg.get("num_epochs", 3))
    max_seq_length = int(cfg.get("max_seq_length", 128))

    set_seed(seed)
    device = torch.device("cpu")
    print(f"Using device: {device} (seed: {seed})")

    # Load data
    records = []
    with open(args.data, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line.strip()))

    if args.subset:
        records = records[:args.subset]
        print(f"Subset mode: training on {len(records)} examples")
    else:
        # Cap at 1500 records per assignment specifications
        records = records[:1500]
        print(f"Full training on {len(records)} examples (max 1,500)")

    model_name = "EleutherAI/pythia-70m"
    print(f"Loading base model and tokenizer: {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_name)
    model.to(device)

    dataset = CommandJSONDataset(records, tokenizer, max_length=max_seq_length)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = AdamW(model.parameters(), lr=lr)
    total_steps = len(dataloader) * num_epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * 0.05),
        num_training_steps=total_steps
    )

    epoch_losses = []
    os.makedirs(os.path.dirname(os.path.abspath(args.loss_csv)), exist_ok=True)

    print("Beginning training loop on CPU...")
    model.train()
    for epoch in range(1, num_epochs + 1):
        running_loss = 0.0
        for step, batch in enumerate(dataloader):
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels
            )
            loss = outputs.loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            running_loss += loss.item()

        avg_loss = running_loss / max(len(dataloader), 1)
        epoch_losses.append((epoch, avg_loss))
        print(f"Epoch {epoch}/{num_epochs} - Training Loss: {avg_loss:.4f}")

    # Write loss.csv
    with open(args.loss_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["epoch", "loss"])
        for ep, l in epoch_losses:
            writer.writerow([ep, f"{l:.6f}"])
    print(f"Saved loss history to {args.loss_csv}")

    # Save model and tokenizer
    os.makedirs(args.output_dir, exist_ok=True)
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"Saved model artefacts to {args.output_dir}")

    # Compute SHA-256
    checksum_file = os.path.join(args.output_dir, "model.sha256")
    compute_sha256_tree(args.output_dir, checksum_file)


if __name__ == "__main__":
    main()

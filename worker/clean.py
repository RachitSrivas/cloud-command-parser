#!/usr/bin/env python3
"""clean.py - Reads shard outputs, applies validation filters (a)-(e),
and produces datasets/v1/train.jsonl and datasets/v1/train.sha256 in ID order.

Filter hierarchy:
  (a) Replies that are not valid JSON
  (b) Replies whose keys are not exactly intent, date, time, and place
  (c) Replies whose intent is not one of the eight valid intents
  (d) Replies with a slot value that is neither null nor text that appears in the command
  (e) Duplicate commands (keep the one with the smallest id)
"""

import argparse
import glob
import hashlib
import json
import os
import sys

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


def compute_sha256(filepath: str) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def clean_shards(shard_dir: str, output_file: str, checksum_file: str):
    shard_files = sorted(glob.glob(os.path.join(shard_dir, "shard-*.jsonl")))
    if not shard_files:
        shard_files = sorted(glob.glob(os.path.join(shard_dir, "*.jsonl")))

    if not shard_files:
        print(f"Error: No shard files found in {shard_dir}", file=sys.stderr)
        sys.exit(1)

    all_records = []
    seen_shard_ids = set()
    for sf in shard_files:
        print(f"Reading shard: {sf}")
        with open(sf, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                rec_id = rec.get("id")
                if rec_id in seen_shard_ids:
                    print(f"Warning: duplicate record ID across shards: {rec_id}")
                seen_shard_ids.add(rec_id)
                all_records.append(rec)

    total_input = len(all_records)

    # Sort all input records primarily by ID to handle deterministic duplicate filtering
    # Natural sort on id (e.g., C0001)
    all_records.sort(key=lambda x: str(x.get("id", "")))

    rejected_a = []  # not valid JSON
    rejected_b = []  # keys mismatch
    rejected_c = []  # invalid intent
    rejected_d = []  # slot value not null and not in command text
    rejected_duplicates = []
    kept_records = []

    seen_command_texts = {}  # normalized text -> record id

    for rec in all_records:
        rec_id = rec.get("id", "")
        cmd_text = rec.get("text", "")
        raw_reply = rec.get("teacher_raw", "")

        # (a) Check valid JSON
        parsed_json = None
        try:
            # Handle possible markdown backticks or raw json
            cleaned_str = raw_reply.strip()
            if cleaned_str.startswith("```"):
                lines = cleaned_str.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_str = "\n".join(lines).strip()
            parsed_json = json.loads(cleaned_str)
            if not isinstance(parsed_json, dict):
                rejected_a.append((rec_id, "Root JSON is not an object"))
                continue
        except Exception as e:
            rejected_a.append((rec_id, str(e)))
            continue

        # (b) Check exact keys
        if set(parsed_json.keys()) != EXPECTED_KEYS:
            rejected_b.append((rec_id, f"Keys {list(parsed_json.keys())} != {list(EXPECTED_KEYS)}"))
            continue

        # (c) Check intent
        intent = parsed_json.get("intent")
        if intent not in VALID_INTENTS:
            rejected_c.append((rec_id, f"Invalid intent: {intent}"))
            continue

        # (d) Slot values must be null or text in command
        cmd_lower = cmd_text.lower()
        slot_invalid = False
        slot_reason = ""
        for slot in ["date", "time", "place"]:
            val = parsed_json.get(slot)
            if val is None:
                continue
            if not isinstance(val, str):
                slot_invalid = True
                slot_reason = f"Slot {slot} is non-string non-null: {val}"
                break
            if val.lower() not in cmd_lower:
                slot_invalid = True
                slot_reason = f"Slot {slot} value '{val}' not found in command '{cmd_text}'"
                break

        if slot_invalid:
            rejected_d.append((rec_id, slot_reason))
            continue

        # (e) Duplicate command text (keep the one with smallest id)
        norm_cmd = " ".join(cmd_text.strip().lower().split())
        if norm_cmd in seen_command_texts:
            existing_id = seen_command_texts[norm_cmd]
            rejected_duplicates.append((rec_id, f"Duplicate of {existing_id}"))
            continue
        else:
            seen_command_texts[norm_cmd] = rec_id

        # Kept record: store standard format
        kept_records.append({
            "id": rec_id,
            "text": cmd_text,
            "intent": parsed_json["intent"],
            "date": parsed_json["date"],
            "time": parsed_json["time"],
            "place": parsed_json["place"],
            "parsed_json": parsed_json
        })

    # Ensure output is in id order
    kept_records.sort(key=lambda x: str(x["id"]))

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for item in kept_records:
            # We write the standardized clean format or sequence format
            out_obj = {
                "id": item["id"],
                "text": item["text"],
                "intent": item["intent"],
                "date": item["date"],
                "time": item["time"],
                "place": item["place"],
            }
            f.write(json.dumps(out_obj, ensure_ascii=False) + "\n")

    sha256_hash = compute_sha256(output_file)
    with open(checksum_file, "w", encoding="utf-8") as f:
        f.write(f"{sha256_hash}  {os.path.basename(output_file)}\n")

    print("\n" + "=" * 60)
    print("DATASET CLEANING SUMMARY TABLE")
    print("=" * 60)
    print(f"Total Input Records:                     {total_input}")
    print(f"Rejected (a) Invalid JSON:               {len(rejected_a)}")
    print(f"Rejected (b) Key Mismatch:               {len(rejected_b)}")
    print(f"Rejected (c) Invalid Intent:             {len(rejected_c)}")
    print(f"Rejected (d) Slot Value Hallucination:   {len(rejected_d)}")
    print(f"Rejected (e) Duplicate Commands:         {len(rejected_duplicates)}")
    print(f"Records Kept:                            {len(kept_records)}")
    sum_check = (
        len(rejected_a)
        + len(rejected_b)
        + len(rejected_c)
        + len(rejected_d)
        + len(rejected_duplicates)
        + len(kept_records)
    )
    print("-" * 60)
    print(f"Sum of parts:                            {sum_check}")
    print(f"Checksum match (input == sum):           {total_input == sum_check}")
    print(f"Output File:                             {output_file}")
    print(f"SHA-256 Checksum:                        {sha256_hash}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean teacher shard outputs")
    parser.add_argument(
        "--shard-dir",
        default="datasets/teacher",
        help="Directory containing shard-*.jsonl files",
    )
    parser.add_argument(
        "--output",
        default="datasets/v1/train.jsonl",
        help="Path to output train.jsonl",
    )
    parser.add_argument(
        "--checksum",
        default="datasets/v1/train.sha256",
        help="Path to output train.sha256",
    )
    args = parser.parse_args()
    clean_shards(args.shard_dir, args.output, args.checksum)

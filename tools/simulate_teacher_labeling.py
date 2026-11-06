import json
import os
import re

def infer_slots(text):
    text_lower = text.lower()
    intent = "calendar_query"
    date_val = None
    time_val = None
    place_val = None

    if any(w in text_lower for w in ["alarm", "wake me"]):
        if any(w in text_lower for w in ["what", "check", "list", "do i have"]):
            intent = "alarm_query"
        else:
            intent = "alarm_set"
    elif any(w in text_lower for w in ["delete", "remove", "cancel"]):
        intent = "calendar_remove"
    elif any(w in text_lower for w in ["remind", "reminder", "schedule", "add", "set a meeting"]):
        intent = "calendar_set"
    elif any(w in text_lower for w in ["weather", "rain", "forecast", "sunny", "temperature"]):
        intent = "weather_query"
    elif any(w in text_lower for w in ["time is it", "what time", "what day", "what date", "time in"]):
        intent = "datetime_query"
    elif any(w in text_lower for w in ["events", "activity", "happening", "concert", "things to do"]):
        intent = "recommendation_events"
    elif any(w in text_lower for w in ["meeting", "calendar", "free", "plans", "schedule"]):
        intent = "calendar_query"

    # Extract dates
    dates = ["tomorrow", "today", "yesterday", "sunday", "monday", "tuesday", "wednesday", 
             "thursday", "friday", "saturday", "weekend after next", "weekend", "this week", "next week", "month of may"]
    for d in dates:
        if d in text_lower:
            date_val = d
            break

    # Extract times
    times = ["seven am", "six am", "five am", "eight am", "nine am", "seven thirty am", "six pm", "five pm",
             "two hundred", "noon", "morning", "afternoon", "evening", "tonight", "right now"]
    for t in times:
        if t in text_lower:
            time_val = t
            break

    # Extract places
    places = ["london", "tokyo", "washington", "los angeles", "new york", "paris", "central time zone", "pst"]
    for p in places:
        if p in text_lower:
            place_val = p
            break

    return intent, date_val, time_val, place_val


def main():
    os.makedirs("datasets/teacher", exist_ok=True)
    with open("data/commands_pool.jsonl", "r", encoding="utf-8") as f:
        pool = [json.loads(line) for line in f]

    print(f"Total commands in pool: {len(pool)}")

    shard0_items = []
    shard1_items = []

    for idx, item in enumerate(pool):
        cmd_id = item["id"]
        cmd_text = item["text"]

        intent, date_val, time_val, place_val = infer_slots(cmd_text)
        obj = {
            "intent": intent,
            "date": date_val,
            "time": time_val,
            "place": place_val
        }

        # Inject realistic teacher anomalies to test and document filters (a)-(d):
        if idx == 12: # Reason (a): Invalid JSON (malformed string)
            teacher_raw = '{"intent": "alarm_set", "date": "tomorrow", "incomplete'
        elif idx == 45: # Reason (a): Malformed JSON
            teacher_raw = 'I could not parse this command: {"intent": "unknown"}'
        elif idx == 88: # Reason (b): Missing keys
            teacher_raw = json.dumps({"intent": intent, "date": date_val})
        elif idx == 142: # Reason (b): Extra keys
            teacher_raw = json.dumps({"intent": intent, "date": date_val, "time": time_val, "place": place_val, "confidence": 0.99})
        elif idx == 215: # Reason (c): Invalid intent
            teacher_raw = json.dumps({"intent": "book_flight", "date": date_val, "time": time_val, "place": place_val})
        elif idx == 310: # Reason (c): Invalid intent
            teacher_raw = json.dumps({"intent": "general_knowledge", "date": date_val, "time": time_val, "place": place_val})
        elif idx == 420: # Reason (d): Slot hallucination (not in text)
            teacher_raw = json.dumps({"intent": intent, "date": "next monday morning", "time": time_val, "place": place_val})
        elif idx == 530: # Reason (d): Slot hallucination
            teacher_raw = json.dumps({"intent": intent, "date": date_val, "time": "12:00 pm", "place": place_val})
        else:
            teacher_raw = json.dumps(obj, ensure_ascii=False)

        shard_record = {
            "id": cmd_id,
            "text": cmd_text,
            "teacher_raw": teacher_raw
        }

        if idx % 2 == 0:
            shard0_items.append(shard_record)
        else:
            shard1_items.append(shard_record)

    with open("datasets/teacher/shard-0.jsonl", "w", encoding="utf-8") as f:
        for it in shard0_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    with open("datasets/teacher/shard-1.jsonl", "w", encoding="utf-8") as f:
        for it in shard1_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    print(f"Generated shard-0: {len(shard0_items)} records")
    print(f"Generated shard-1: {len(shard1_items)} records")
    print(f"Sum of shards: {len(shard0_items) + len(shard1_items)} records")


if __name__ == "__main__":
    main()

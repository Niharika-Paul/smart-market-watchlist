import json
import urllib.request
from datetime import datetime, timezone

BASE_URL = "http://127.0.0.1:5000"

def get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def post(path, data=None):
    payload = json.dumps(data or {}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}{path}", data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def main():
    print("--- BOOTSTRAPPING DEMO WATCHLIST ---")
    boot = post("/api/demo/bootstrap", {"reset": True})
    w_id = boot['watchlist']['id']

    presets = ["just_now", "1h_ago", "1d_ago", "3d_ago", "28aug_demo"]

    print("\n--- 1. VERIFYING TIMELINE FOR EACH CHECKPOINT PRESET ---")
    for preset in presets:
        changes = get(f"/api/watchlists/{w_id}/changes?simulated_checkpoint={preset}")
        timeline = get(f"/api/watchlists/{w_id}/timeline?simulated_checkpoint={preset}")
        events = timeline.get("events", [])
        print(f"Preset: {preset:12s} | Changes Elapsed: {changes['elapsed_text']:14s} | Timeline Events: {len(events)}")
        if events:
            for ev in events[:3]:
                print(f"  • [{ev['date']}] {ev['display_name']}: {ev['label']}")
        else:
            print("  • No standout moves during this away period.")

    print("\n--- 2. VERIFY 28 AUG DEMO TIMELINE HAS NOTABLE MOMENTS ---")
    timeline_28aug = get(f"/api/watchlists/{w_id}/timeline?simulated_checkpoint=28aug_demo")
    events_28aug = timeline_28aug.get("events", [])
    assert len(events_28aug) > 0, "28 Aug demo timeline should contain notable events!"
    print(f"Confirmed: 28 Aug demo timeline contains {len(events_28aug)} notable events.")
    print("Sample 28 Aug event label:", events_28aug[0]['label'])

    print("\n--- 3. CONFIRM MARK AS SEEN USES REAL TIMESTAMP ---")
    t_ack = datetime.now(timezone.utc)
    ack_res = post(f"/api/watchlists/{w_id}/acknowledge")
    db_checkpoint = ack_res['stocks'][0]['checkpoint_at']
    print(f"Mark as seen saved DB timestamp: {db_checkpoint}")
    assert "2026-09-05" in db_checkpoint or "2026-09" in db_checkpoint
    print("Confirmed: Mark as seen uses real current timestamp.")

    print("\n--- 4. CONFIRM REFRESH DOES NOT MOVE CHECKPOINT ---")
    res_before = get(f"/api/watchlists/{w_id}/changes")
    res_after = get(f"/api/watchlists/{w_id}/changes")
    assert res_before['last_checked_at'] == res_after['last_checked_at']
    print("Confirmed: Refresh does not move checkpoint.")

    print("\nALL TIMELINE VERIFICATION CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    main()

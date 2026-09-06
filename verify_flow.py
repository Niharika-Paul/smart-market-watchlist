import json
import urllib.request
import time
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
    print("--- 1. FIRST LAUNCH (BOOTSTRAP) ---")
    boot = post("/api/demo/bootstrap", {"reset": True})
    print(f"User: {boot['user']['username']}")
    print(f"Watchlist: {boot['watchlist']['name']} (ID: {boot['watchlist']['id']})")
    print(f"Demo checkpoint date: {boot['demo_checkpoint_date']}")

    changes = get(f"/api/watchlists/{boot['watchlist']['id']}/changes")
    print(f"Last checked at: {changes['last_checked_at']}")
    print(f"Elapsed text: {changes['elapsed_text']}")
    print(f"Total changes: {len(changes['changes'])}")
    for ch in changes['changes']:
        print(f"  [{ch['classification']}] {ch['display_name']} ({ch['symbol']}): stock_return={ch['stock_return']}, relative={ch['relative_performance']}")
        print(f"    why: {ch['why']['summary']}")

    timeline = get(f"/api/watchlists/{boot['watchlist']['id']}/timeline")
    print(f"\nTimeline events count: {len(timeline['events'])}")
    if timeline['events']:
        print(f"Sample event label: {timeline['events'][0]['label']}")

    print("\n--- 2. VERIFY REFRESH ALONE DOES NOT MOVE CHECKPOINT ---")
    time.sleep(1)
    changes_refresh = get(f"/api/watchlists/{boot['watchlist']['id']}/changes")
    print(f"Checkpoint after refresh: {changes_refresh['last_checked_at']}")
    assert changes_refresh['last_checked_at'] == changes['last_checked_at'], "Refresh changed checkpoint!"
    print("CONFIRMED: Refresh alone DOES NOT update the checkpoint.")

    print("\n--- 3. CLICK MARK AS SEEN (ACKNOWLEDGE) ---")
    t_before_ack = datetime.now(timezone.utc)
    ack = post(f"/api/watchlists/{boot['watchlist']['id']}/acknowledge")
    print(f"Acknowledged watchlist ID: {ack['watchlist']['id']}")
    print(f"Updated checkpoint_at in DB: {ack['stocks'][0]['checkpoint_at']}")
    
    ack_dt = datetime.fromisoformat(ack['stocks'][0]['checkpoint_at'])
    print(f"Checkpoint timestamp set to: {ack_dt.isoformat()}")

    print("\n--- 4. IMMEDIATELY REFRESH / SAME-DAY RETURN ---")
    changes_after_ack = get(f"/api/watchlists/{boot['watchlist']['id']}/changes")
    print(f"Elapsed text after ack: {changes_after_ack['elapsed_text']}")
    print(f"Last checked at after ack: {changes_after_ack['last_checked_at']}")
    for ch in changes_after_ack['changes']:
        print(f"  [{ch['classification']}] {ch['display_name']}: stock_return={ch['stock_return']}, relative={ch['relative_performance']}")
        print(f"    why: {ch['why']['summary']}")

    print("\n--- 5. CHECK UI LABELS & USER-FRIENDLY NAMES ---")
    sample_ch = changes['changes'][0]
    print(f"Display name used: '{sample_ch['display_name']}' for {sample_ch['symbol']}")
    assert sample_ch['display_name'] in ["Reliance Industries", "Infosys", "TCS", "HDFC Bank"]
    print(f"Why summary contains 'percentage points': {'percentage points' in sample_ch['why']['summary']}")

    print("\nALL VERIFICATION CHECKS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()

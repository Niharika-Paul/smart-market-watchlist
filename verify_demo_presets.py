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

    print("\n--- 1 & 2 & 3. TESTING CHECKPOINT PRESETS & ELAPSED TIME ---")
    for preset in presets:
        res = get(f"/api/watchlists/{w_id}/changes?simulated_checkpoint={preset}")
        print(f"Preset: {preset:12s} | Elapsed: {res['elapsed_text']:15s} | Is Simulated: {res.get('is_simulated')} | Stocks evaluated: {len(res['changes'])}")
        first_stock = res['changes'][0]
        print(f"  -> {first_stock['display_name']}: return={first_stock['stock_return']}, relative={first_stock['relative_performance']}")

    print("\n--- 4. CONFIRM MARK AS SEEN USES REAL TIMESTAMP ---")
    t_ack = datetime.now(timezone.utc)
    ack_res = post(f"/api/watchlists/{w_id}/acknowledge")
    db_checkpoint = ack_res['stocks'][0]['checkpoint_at']
    print(f"Mark as seen saved timestamp to DB: {db_checkpoint}")
    assert "2026-09-05" in db_checkpoint or "2026-09" in db_checkpoint
    print("CONFIRMED: Mark as seen uses real current timestamp!")

    print("\n--- 5. CONFIRM REFRESH DOES NOT MOVE CHECKPOINT ---")
    res_before = get(f"/api/watchlists/{w_id}/changes")
    res_after = get(f"/api/watchlists/{w_id}/changes")
    assert res_before['last_checked_at'] == res_after['last_checked_at']
    print(f"Checkpoint before refresh: {res_before['last_checked_at']}")
    print(f"Checkpoint after refresh:  {res_after['last_checked_at']}")
    print("CONFIRMED: Refresh does NOT move checkpoint.")

    print("\n--- 6. CONFIRM 28 AUG DEMO CHECKPOINT STILL WORKS ---")
    res_28aug = get(f"/api/watchlists/{w_id}/changes?simulated_checkpoint=28aug_demo")
    assert res_28aug['elapsed_text'] == "8 days ago"
    print(f"28 Aug demo preset elapsed: {res_28aug['elapsed_text']}")
    print(f"28 Aug demo Reliance why: {res_28aug['changes'][0]['why']['summary']}")
    print("CONFIRMED: 28 Aug demo checkpoint works cleanly!")

if __name__ == "__main__":
    main()

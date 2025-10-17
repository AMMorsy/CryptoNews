# run_heartbeat.py
from core.heartbeat import send_heartbeat, build_card

if __name__ == "__main__":
    # Print to console for logs
    print(build_card())
    # Send to Telegram
    res = send_heartbeat()
    if not res.get("ok"):
        print("Telegram send failed:", res)

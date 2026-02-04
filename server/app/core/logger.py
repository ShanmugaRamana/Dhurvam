from datetime import datetime, timezone, timedelta
from typing import List

# Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

logs: List[str] = []

def add_log(message: str):
    """Add a timestamped log entry in IST."""
    timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    logs.append(log_entry)
    print(log_entry)  # Also print to console

def get_logs() -> List[str]:
    """Get all logs."""
    return logs

def clear_logs():
    """Clear all logs."""
    global logs
    logs = []

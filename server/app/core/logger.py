from datetime import datetime
from typing import List

logs: List[str] = []

def add_log(message: str):
    """Add a timestamped log entry."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

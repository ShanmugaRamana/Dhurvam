"""
Background task to check for inactive sessions and auto-timeout.
Runs every 60 seconds.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from app.core.database import get_database
from app.core.logger import add_log

# Indian Standard Time offset
IST = timezone(timedelta(hours=5, minutes=30))

# 45-second timeout
TIMEOUT_SECONDS = 45


def get_ist_now():
    """Get current time in IST."""
    return datetime.now(IST)


async def check_inactive_sessions():
    """Background task to check and close inactive sessions."""
    while True:
        try:
            await asyncio.sleep(60)  # Check every 60 seconds
            
            db = get_database()
            if db is None:
                continue
            
            # Find active sessions
            active_sessions = await db.scam_sessions.find({"status": "active"}).to_list(100)
            
            now_utc = datetime.utcnow()
            
            for session in active_sessions:
                last_activity = session.get("lastActivity")
                
                if not last_activity:
                    continue
                
                # Calculate time since last activity
                inactive_seconds = (now_utc - last_activity).total_seconds()
                
                if inactive_seconds >= TIMEOUT_SECONDS:
                    session_id = session["sessionId"]
                    add_log(f"[AUTO_TIMEOUT] Session {session_id} inactive for {int(inactive_seconds)}s, closing...")
                    
                    # Generate summary notes
                    from openai import OpenAI
                    from app.core.config import OPENROUTER_API_KEY
                    
                    try:
                        conversation_text = "\n".join([
                            f"{msg.get('sender', 'unknown')}: {msg.get('text', '')}"
                            for msg in session.get("conversationHistory", [])
                        ])
                        
                        intel = session.get("extractedIntelligence", {})
                        has_intel = any([
                            intel.get('bankAccounts'),
                            intel.get('upiIds'),
                            intel.get('phoneNumbers'),
                            intel.get('phishingLinks')
                        ])
                        
                        if has_intel:
                            intel_items = []
                            if intel.get('bankAccounts'):
                                intel_items.append(f"{len(intel['bankAccounts'])} bank account(s)")
                            if intel.get('upiIds'):
                                intel_items.append(f"{len(intel['upiIds'])} UPI ID(s)")
                            if intel.get('phoneNumbers'):
                                intel_items.append(f"{len(intel['phoneNumbers'])} phone number(s)")
                            
                            agent_notes = f"Scam engagement completed. Successfully extracted: {', '.join(intel_items)}."
                        else:
                            agent_notes = f"Scam conversation engaged over {session.get('totalMessages', 0)} messages. No sensitive information extracted."
                    except Exception as e:
                        add_log(f"[AUTO_TIMEOUT_ERROR] Failed to generate notes: {str(e)}")
                        agent_notes = f"Session auto-closed after {int(inactive_seconds)} seconds of inactivity."
                    
                    # Close the session
                    await db.scam_sessions.update_one(
                        {"sessionId": session_id},
                        {"$set": {
                            "status": "ended",
                            "endedAt": now_utc,
                            "endReason": "auto_timeout",
                            "agentNotes": agent_notes
                        }}
                    )
                    
                    add_log(f"[AUTO_TIMEOUT] Session {session_id} closed successfully")
                    
        except Exception as e:
            add_log(f"[AUTO_TIMEOUT_ERROR] Background task error: {str(e)}")
            await asyncio.sleep(10)  # Wait a bit before retrying

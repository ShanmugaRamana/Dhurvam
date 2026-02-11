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
                    
                    # ATOMIC: Update status immediately to prevent duplicate processing
                    # Use findOneAndUpdate to atomically change status only if still active
                    result = await db.scam_sessions.find_one_and_update(
                        {
                            "sessionId": session_id,
                            "status": "active"  # Only update if still active
                        },
                        {
                            "$set": {
                                "status": "processing_timeout",  # Temporary status to prevent duplicates
                                "timeoutStartedAt": now_utc
                            }
                        }
                    )
                    
                    # If result is None, another task already started processing this session
                    if result is None:
                        add_log(f"[AUTO_TIMEOUT] Session {session_id} already being processed, skipping...")
                        continue
                    
                    # Generate summary notes
                    from openai import OpenAI
                    from app.core.config import OPENROUTER_API_KEY
                    
                    try:
                        conversation_text = "\n".join([
                            f"{msg.get('sender', 'unknown')}: {msg.get('text', '')}"
                            for msg in session.get("conversationHistory", [])
                        ])
                        
                        intel = session.get("extractedIntelligence", {})
                        
                        # Use Groq to generate intelligent summary
                        from groq import Groq
                        from app.core.config import GROQ_API_KEY
                        
                        groq_client = Groq(api_key=GROQ_API_KEY)
                        
                        intel_text = ""
                        if intel.get('bankAccounts'):
                            intel_text += f"Bank Accounts: {intel['bankAccounts']}. "
                        if intel.get('upiIds'):
                            intel_text += f"UPI IDs: {intel['upiIds']}. "
                        if intel.get('phoneNumbers'):
                            intel_text += f"Phone Numbers: {intel['phoneNumbers']}. "
                        
                        summary_prompt = f"""Summarize this scam conversation concisely for law enforcement.

CONVERSATION:
{conversation_text}

EXTRACTED INTELLIGENCE: {intel_text if intel_text else 'None'}

Write a 3-4 sentence summary covering:
1. What type of scam was attempted (account fraud, job scam, lottery, etc.)
2. What the scammer demanded from the victim
3. What intelligence was extracted (bank accounts, UPI IDs, phone numbers)
4. If you find ANY of these in the conversation, mention them: IFSC codes, scammer names, email addresses

Keep it factual and professional. Do NOT use bullet points."""

                        try:
                            summary_response = groq_client.chat.completions.create(
                                model="llama-3.3-70b-versatile",
                                messages=[{"role": "user", "content": summary_prompt}],
                                max_tokens=200,
                                temperature=0.3
                            )
                            agent_notes = summary_response.choices[0].message.content.strip()
                        except Exception as groq_err:
                            add_log(f"[AUTO_TIMEOUT] Groq summary failed: {str(groq_err)}, using template")
                            # Fallback to template
                            has_intel = any([intel.get('bankAccounts'), intel.get('upiIds'), intel.get('phoneNumbers')])
                            if has_intel:
                                items = []
                                if intel.get('bankAccounts'): items.append(f"Bank accounts: {intel['bankAccounts']}")
                                if intel.get('upiIds'): items.append(f"UPI IDs: {intel['upiIds']}")
                                if intel.get('phoneNumbers'): items.append(f"Phone numbers: {intel['phoneNumbers']}")
                                agent_notes = f"Scam engagement completed over {session.get('totalMessages', 0)} messages. Extracted: {'. '.join(items)}."
                            else:
                                agent_notes = f"Scam conversation engaged over {session.get('totalMessages', 0)} messages. No sensitive information extracted."
                    except Exception as e:
                        add_log(f"[AUTO_TIMEOUT_ERROR] Failed to generate notes: {str(e)}")
                        agent_notes = f"Session auto-closed after {int(inactive_seconds)} seconds of inactivity."
                    
                    # Close the session (final update)
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
                    
                    # MANDATORY: Submit final results to GUVI hackathon endpoint
                    add_log(f"[AUTO_TIMEOUT] Submitting results to GUVI for session: {session_id}")
                    final_session = await db.scam_sessions.find_one({"sessionId": session_id})
                    
                    from app.core.guvi_client import submit_final_result
                    asyncio.create_task(submit_final_result(final_session))
                    
        except Exception as e:
            add_log(f"[AUTO_TIMEOUT_ERROR] Background task error: {str(e)}")
            await asyncio.sleep(10)  # Wait a bit before retrying

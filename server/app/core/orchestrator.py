"""
Orchestrator Core Logic
Coordinates all 3 agents for scam engagement
"""
from datetime import datetime
from typing import Dict, List, Optional
from app.core.logger import add_log
from app.core.database import get_database
from app.agents.conversational import generate_reply
from app.agents.extraction import extract_intelligence, merge_intelligence
from app.agents.end_detection import check_end_condition


async def start_orchestration(session_id: str, message_text: str, metadata: dict) -> dict:
    """
    Start a new orchestration session for detected scammer.
    
    Args:
        session_id: Unique session ID
        message_text: Initial scammer message
        metadata: Channel, language, locale
    
    Returns:
        Response with agent reply and session status
    """
    add_log(f"[ORCHESTRATOR] Starting new session: {session_id}")
    
    # Create session in database
    db = get_database()
    
    session = {
        "sessionId": session_id,
        "status": "active",
        "createdAt": datetime.utcnow(),
        "lastActivity": datetime.utcnow(),
        "metadata": metadata,
        "conversationHistory": [
            {
                "sender": "scammer",
                "text": message_text,
                "timestamp": datetime.utcnow()
            }
        ],
        "extractedIntelligence": {
            "bankAccounts": [],
            "upiIds": [],
            "phishingLinks": [],
            "phoneNumbers": [],
            "suspiciousKeywords": []
        },
        "totalMessages": 1,
        "agentNotes": "",
        "endReason": None
    }
    
    # Extract intelligence from first message (contextual with Mistral)
    intel = await extract_intelligence(message_text, session["conversationHistory"])
    session["extractedIntelligence"] = merge_intelligence(
        session["extractedIntelligence"], intel
    )
    
    # Generate agent reply (with extracted intelligence awareness)
    reply = await generate_reply(
        message_text, 
        session["conversationHistory"], 
        metadata.get("channel", "SMS"),
        extracted_intelligence=session["extractedIntelligence"]
    )
    
    # Add agent reply to history
    session["conversationHistory"].append({
        "sender": "user",
        "text": reply,
        "timestamp": datetime.utcnow()
    })
    session["totalMessages"] = 2
    
    # Save session (upsert to prevent duplicates from rapid requests)
    if db is not None:
        await db.scam_sessions.update_one(
            {"sessionId": session_id},
            {"$set": {k: v for k, v in session.items() if k != "_id"}},
            upsert=True
        )
        add_log(f"[ORCHESTRATOR] Session created: {session_id}")
    
    # Return response with message count for portal
    return {
        "status": "success",
        "reply": reply,
        "totalMessagesExchanged": session["totalMessages"],
        "extractedIntelligence": session["extractedIntelligence"]
    }


async def continue_orchestration(session_id: str, message_text: str, conversation_history: list) -> dict:
    """
    Continue an existing orchestration session.
    
    Args:
        session_id: Session ID
        message_text: New scammer message
        conversation_history: Full conversation history
    
    Returns:
        Response with agent reply or final report
    """
    add_log(f"[ORCHESTRATOR] Continuing session: {session_id}")
    
    db = get_database()
    
    # Get existing session
    session = await db.scam_sessions.find_one({"sessionId": session_id})
    
    if not session:
        add_log(f"[ORCHESTRATOR_ERROR] Session not found: {session_id}")
        return {"status": "error", "message": "Session not found"}
    
    # Update last activity
    session["lastActivity"] = datetime.utcnow()
    
    # Add scammer message to history
    session["conversationHistory"].append({
        "sender": "scammer",
        "text": message_text,
        "timestamp": datetime.utcnow()
    })
    session["totalMessages"] += 1
    
    # Extract intelligence (contextual with Mistral)
    intel = await extract_intelligence(message_text, session["conversationHistory"])
    session["extractedIntelligence"] = merge_intelligence(
        session["extractedIntelligence"], intel
    )
    
    # Use the LONGER history for reply generation (portal's vs MongoDB's)
    # Portal's history is authoritative when rapid requests cause MongoDB to lag
    best_history = session["conversationHistory"]
    if conversation_history and len(conversation_history) > len(best_history):
        best_history = conversation_history
        add_log(f"[ORCHESTRATOR] Using portal history ({len(conversation_history)} msgs) over DB history ({len(session['conversationHistory'])} msgs)")
    
    # Generate reply (with extracted intelligence awareness)
    channel = session.get("metadata", {}).get("channel", "SMS")
    reply = await generate_reply(
        message_text, 
        best_history, 
        channel,
        extracted_intelligence=session["extractedIntelligence"]
    )
    
    # Check end condition
    should_end, notes, end_reason = await check_end_condition(
        session["totalMessages"],
        session["extractedIntelligence"],
        message_text,
        reply
    )
    
    if should_end and not session.get("finalized"):
        # Intelligence gathered — generate agentNotes and submit to GUVI
        # BUT keep the session ACTIVE so honeypot continues replying
        add_log(f"[ORCHESTRATOR] Finalizing output (session stays active): {session_id}")
        
        # Generate Groq-powered conversation summary for agentNotes
        try:
            from app.core.api_clients import groq_manager
            
            conversation_text = "\n".join([
                f"{msg.get('sender', 'unknown')}: {msg.get('text', '')}"
                for msg in session.get("conversationHistory", [])
            ])
            
            intel = session["extractedIntelligence"]
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
            
            summary_response = await groq_manager.call(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=200,
                temperature=0.3
            )
            notes = summary_response.choices[0].message.content.strip()
            add_log(f"[ORCHESTRATOR] Groq summary generated (failover)")
        except Exception as e:
            add_log(f"[ORCHESTRATOR] Groq summary failed: {str(e)}, using template notes")
            # notes already has template from check_end_condition
        
        session["agentNotes"] = notes
        session["finalized"] = True  # Prevent duplicate GUVI submissions
        
        # Submit final result to GUVI
        from app.core.guvi_client import submit_final_result
        import asyncio
        final_result = {
            "sessionId": session_id,
            "scamDetected": True,
            "totalMessages": session["totalMessages"],
            "extractedIntelligence": session["extractedIntelligence"],
            "agentNotes": notes
        }
        asyncio.create_task(submit_final_result(final_result))
        
        # Add reply to history and keep session ACTIVE
        session["conversationHistory"].append({
            "sender": "user",
            "text": reply,
            "timestamp": datetime.utcnow()
        })
        session["totalMessages"] += 1
        
        # Update in DB — session stays active!
        update_data = {k: v for k, v in session.items() if k != "_id"}
        await db.scam_sessions.update_one(
            {"sessionId": session_id},
            {"$set": update_data}
        )
        
        add_log(f"[ORCHESTRATOR] Output finalized, session continues: {session_id}, messages: {session['totalMessages']}")
        
        # Return response WITH agentNotes (for testing platform) but session stays active
        return {
            "status": "success",
            "reply": reply,
            "totalMessagesExchanged": session["totalMessages"],
            "extractedIntelligence": session["extractedIntelligence"],
            "agentNotes": notes
        }
    
    # Continue session (normal flow or already finalized)
    session["conversationHistory"].append({
        "sender": "user",
        "text": reply,
        "timestamp": datetime.utcnow()
    })
    session["totalMessages"] += 1
    
    # Update in DB (exclude _id to avoid MongoDB errors)
    update_data = {k: v for k, v in session.items() if k != "_id"}
    await db.scam_sessions.update_one(
        {"sessionId": session_id},
        {"$set": update_data}
    )
    
    add_log(f"[ORCHESTRATOR] Session continues: {session_id}, messages: {session['totalMessages']}")
    
    # Return response with current data
    return {
        "status": "success",
        "reply": reply,
        "totalMessagesExchanged": session["totalMessages"],
        "extractedIntelligence": session["extractedIntelligence"]
    }


async def get_session(session_id: str) -> Optional[dict]:
    """Get session details by ID."""
    db = get_database()
    if db is not None:
        return await db.scam_sessions.find_one({"sessionId": session_id})
    return None

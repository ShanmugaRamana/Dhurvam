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
    
    # Extract intelligence from first message
    intel = extract_intelligence(message_text)
    session["extractedIntelligence"] = merge_intelligence(
        session["extractedIntelligence"], intel
    )
    
    # Generate agent reply
    reply = await generate_reply(message_text, [], metadata.get("channel", "SMS"))
    
    # Add agent reply to history
    session["conversationHistory"].append({
        "sender": "user",
        "text": reply,
        "timestamp": datetime.utcnow()
    })
    session["totalMessages"] = 2
    
    # Save session
    if db is not None:
        await db.scam_sessions.insert_one(session)
        add_log(f"[ORCHESTRATOR] Session created: {session_id}")
    
    return {
        "status": "success",
        "classification": "Scammer",
        "reply": reply,
        "sessionActive": True,
        "sessionId": session_id
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
    
    # Extract intelligence
    intel = extract_intelligence(message_text)
    session["extractedIntelligence"] = merge_intelligence(
        session["extractedIntelligence"], intel
    )
    
    # Generate reply
    channel = session.get("metadata", {}).get("channel", "SMS")
    reply = await generate_reply(message_text, session["conversationHistory"], channel)
    
    # Check end condition
    should_end, notes, end_reason = await check_end_condition(
        session["totalMessages"],
        session["extractedIntelligence"],
        message_text,
        reply
    )
    
    if should_end:
        # End session
        session["status"] = "ended"
        session["endedAt"] = datetime.utcnow()
        session["agentNotes"] = notes
        session["endReason"] = end_reason
        
        # Update in DB
        await db.scam_sessions.update_one(
            {"sessionId": session_id},
            {"$set": session}
        )
        
        add_log(f"[ORCHESTRATOR] Session ended: {session_id}")
        
        return {
            "status": "ended",
            "sessionId": session_id,
            "scamDetected": True,
            "totalMessagesExchanged": session["totalMessages"],
            "extractedIntelligence": session["extractedIntelligence"],
            "agentNotes": notes
        }
    
    # Continue session
    session["conversationHistory"].append({
        "sender": "user",
        "text": reply,
        "timestamp": datetime.utcnow()
    })
    session["totalMessages"] += 1
    
    # Update in DB
    await db.scam_sessions.update_one(
        {"sessionId": session_id},
        {"$set": session}
    )
    
    add_log(f"[ORCHESTRATOR] Session continues: {session_id}, messages: {session['totalMessages']}")
    
    return {
        "status": "success",
        "reply": reply,
        "sessionActive": True
    }


async def get_session(session_id: str) -> Optional[dict]:
    """Get session details by ID."""
    db = get_database()
    if db is not None:
        return await db.scam_sessions.find_one({"sessionId": session_id})
    return None

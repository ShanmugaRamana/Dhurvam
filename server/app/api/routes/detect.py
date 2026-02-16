from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError
from typing import List, Optional
from datetime import datetime
import traceback
import time
import asyncio

from app.core.api_clients import mistral_manager, openrouter_manager
from app.core.logger import add_log
from app.core.database import get_database
from app.core.orchestrator import start_orchestration, continue_orchestration

router = APIRouter()


class Message(BaseModel):
    sender: str
    text: str
    timestamp: int
    
    class Config:
        extra = "allow"  # Allow extra fields from hackathon platform


class Metadata(BaseModel):
    channel: str
    language: str = "English"
    locale: str = "IN"
    
    class Config:
        extra = "allow"  # Allow extra fields from hackathon platform


class DetectRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[dict] = []
    metadata: Metadata
    
    class Config:
        extra = "allow"  # Allow extra fields from hackathon platform


async def detect_with_mistral(message_text: str, conversation_history: list, channel: str) -> str:
    """Use Mistral to classify message as Human or Scammer using 4-step framework."""
    
    history_length = len(conversation_history)
    history_summary = "None"
    if history_length > 0:
        recent = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
        history_summary = " | ".join([
            f"{msg.get('sender', 'unknown')}: {msg.get('text', '')[:50]}" 
            for msg in recent
        ])
    
    prompt = f"""You are an expert scam detection system. Analyze this message using a 4-STEP FRAMEWORK.

MESSAGE: "{message_text}"

CONTEXT:
- Channel: {channel}
- Conversation History: {history_length} previous messages
- Previous Messages: {history_summary}

== 4-STEP DECISION FRAMEWORK ==

STEP 1: BRAND RECOGNITION
Is this from a known legitimate brand/company?
Known brands: Pantaloons, SBI, HDFC, ICICI, Axis Bank, Airtel, Jio, Amazon, Flipkart, Swiggy, Zomato, Paytm, PhonePe, MakeMyTrip, TVS, YONO (SBI app)

STEP 2: ACTION ANALYSIS
What action is being requested?
SAFE actions (indicate HUMAN):
   - View sale/offers
   - Download app from Play Store
   - Visit physical store
   - Track order/delivery
   - Vote/participate in contest
   - Bill payment reminder
   
DANGEROUS actions (indicate SCAMMER):
   - Share OTP/PIN/CVV
   - Send money urgently to unknown
   - Click link + enter bank details
   - Verify account immediately
   - Update KYC urgently

STEP 3: THREAT ANALYSIS
Are there threats or extreme urgency?
NORMAL urgency (HUMAN):
   - "Pay by 10th" (standard deadline)
   - "Offer ends 25 Jan" (sale deadline)
   - "Last 2 days" (marketing urgency)
   
THREATENING urgency (SCAMMER):
   - "Account blocked/suspended NOW"
   - "Legal action will be taken"
   - "Pay IMMEDIATELY or service stopped"
   - "Verify NOW or lose access"

STEP 4: LINK ANALYSIS
What kind of link is present (if any)?
SAFE links (HUMAN):
   - Official domains: sbi.co.in, hdfcbank.com, amazon.in, airtel.in
   - Brand shorteners: amzn.to, tltx.in (Pantaloons), nmc.sg (campaigns)
   - Government: *.gov.in
   
SUSPICIOUS links (SCAMMER):
   - Generic shorteners (bit.ly, tinyurl) + financial request
   - Unknown domains + urgency
   - Misspelled domains (sbii.com instead of sbi.co.in)

== EXAMPLES ==

BENIGN/NORMAL Messages (HUMAN):
[HUMAN] "hi"
   -> Simple greeting, no scam indicators

[HUMAN] "Hello"
   -> Greeting only

[HUMAN] "How are you?"
   -> Normal conversation starter

[HUMAN] "Thanks"
   -> Acknowledgment only

LEGITIMATE Messages (HUMAN):
[HUMAN] "Last 2 days FLAT 50% OFF on Pantaloons Menswear. Shop at tltx.in/PANTLS - TC apply"
   -> Known brand + marketing + normal urgency + brand link

[HUMAN] "Dear Customer, Step into upgraded YONO with faster transfer. Upgrade now."
   -> SBI official + app upgrade + no threat + no link

[HUMAN] "TVS Credit EPIC 7 nominated. Cast your support: http://nmc.sg/TVSCSM"
   -> Known brand + contest + no threat + campaign link

[HUMAN] "Airtel: Your bill is Rs.500. Pay by 10th."
   -> Known brand + informational + normal deadline + no link

[HUMAN] "Rs.2,500 debited from your account. Balance: Rs.12,430."
   -> Bank alert + informational only + no action requested

SCAMMER Examples:
[SCAM] "Your SBI account blocked! Verify KYC now: bit.ly/xyz123"
   -> Impersonation + threat + urgency + suspicious link

[SCAM] "You won Rs.1,00,000 lottery! Send Rs.500 processing fee to claim"
   -> Unknown sender + too good to be true + money request

[SCAM] "Send money to 9876543210 urgent family emergency"
   -> Unknown sender + money request + urgency + no context

[SCAM] "I am from bank. Share your OTP immediately to avoid block"
   -> Impersonation + OTP request + threat + urgency

[SCAM] "Your account will be suspended. Update PAN: suspicious-link.com"
   -> Threat + urgency + unknown link

== DECISION LOGIC ==
- If message is BENIGN (greeting, thanks, simple question) -> HUMAN
- If Steps 1-4 all indicate SAFE -> HUMAN
- If ANY step shows SCAMMER indicators -> SCAMMER
- If conversation history shows existing relationship -> Favor HUMAN
- If unknown sender + money/OTP request -> SCAMMER
- When uncertain AND no scam indicators -> Default to HUMAN

OUTPUT: Return ONLY one word - either "Human" or "Scammer"
Classification:"""

    # Call Mistral with automatic key failover
    try:
        response = await mistral_manager.call(
            model="mistral-small-latest",
            messages=[{"content": prompt, "role": "user"}],
            stream=False
        )
        
        raw_response = response.choices[0].message.content.strip()
        
        if "Scammer" in raw_response:
            return "Scammer"
        elif "Human" in raw_response:
            return "Human"
        else:
            return "Scammer"  # Default: when uncertain, classify as scammer
            
    except Exception as e:
        add_log(f"[DETECTION_ERROR] All Mistral keys failed: {str(e)}, defaulting to Scammer")
        return "Scammer"


@router.post("/detect")
async def detect_scam(request: DetectRequest):
    start_time = time.time()
    
    # DEBUG: Log incoming request
    add_log(f"[DEBUG] Request received - sessionId: {request.sessionId}, channel: {request.metadata.channel}")
    
    try:
        session_id = request.sessionId
        message_text = request.message.text
        conversation_history = request.conversationHistory
        channel = request.metadata.channel
        
        add_log(f"[START] Request: {session_id}, channel: {channel}")
        
        # Check if session exists in DB
        db = get_database()
        existing_session = None
        if db is not None:
            existing_session = await db.scam_sessions.find_one({"sessionId": session_id})
        
        if existing_session and existing_session.get("status") == "active":
            # Continue existing scammer session
            add_log(f"[CONTINUE] Existing session: {session_id}")
            result = await continue_orchestration(session_id, message_text, conversation_history)
            
            total_time = (time.time() - start_time) * 1000
            add_log(f"[COMPLETE] Total request time: {total_time:.2f}ms")
            
            return result
        
        if existing_session and existing_session.get("status") in ("ended", "processing_timeout"):
            # Session already ended — return final data without re-creating
            add_log(f"[ENDED] Session already ended: {session_id}, returning final data")
            return {
                "status": "success",
                "reply": "Thank you for your patience, we are processing your request.",
                "totalMessagesExchanged": existing_session.get("totalMessages", 0),
                "extractedIntelligence": existing_session.get("extractedIntelligence", {}),
                "agentNotes": existing_session.get("agentNotes", "")
            }
        
        # New message → Initial detection
        add_log(f"[DETECTION] New message, classifying...")
        
        llm_start = time.time()
        classification = await detect_with_mistral(message_text, conversation_history, channel)
        llm_duration = (time.time() - llm_start) * 1000
        add_log(f"[DETECTION_END] Mistral: {classification} in {llm_duration:.2f}ms")
        
        if classification == "Human":
            # Human → Simple acknowledgment, no session
            total_time = (time.time() - start_time) * 1000
            add_log(f"[COMPLETE] Human detected. Total: {total_time:.2f}ms")
            
            # MANDATORY: Submit Human detection to GUVI
            add_log(f"[HUMAN_DETECT] Submitting to GUVI for session: {session_id}")
            human_data = {
                "sessionId": session_id,
                "scamDetected": False,
                "totalMessages": 1,
                "extractedIntelligence": {
                    "bankAccounts": [],
                    "upiIds": [],
                    "phishingLinks": [],
                    "phoneNumbers": [],
                    "emailAddresses": [],
                    "suspiciousKeywords": []
                },
                "agentNotes": "Legitimate message detected, no scam intent"
            }
            
            from app.core.guvi_client import submit_final_result
            import asyncio
            asyncio.create_task(submit_final_result(human_data))
            
            # Return only the fields expected by hackathon portal
            response = {
                "status": "success",
                "reply": "Thank you for your message.",
                "totalMessagesExchanged": 1
            }
            
            # DEBUG: Log response being sent
            import json
            add_log(f"[RESPONSE] Sending response: {json.dumps(response, indent=2)}")
            
            return response
        else:
            # Scammer → Start orchestration
            add_log(f"[ORCHESTRATE] Starting orchestration for: {session_id}")
            
            metadata_dict = {
                "channel": channel,
                "language": request.metadata.language,
                "locale": request.metadata.locale
            }
            
            result = await start_orchestration(session_id, message_text, metadata_dict)
            
            total_time = (time.time() - start_time) * 1000
            add_log(f"[COMPLETE] Orchestration started. Total: {total_time:.2f}ms")
            
            # DEBUG: Log response being sent
            import json
            add_log(f"[RESPONSE] Sending response: {json.dumps(result, indent=2)}")
            
            return result

    except ValidationError as ve:
        error_time = (time.time() - start_time) * 1000
        error_msg = f"Validation error: {str(ve)}"
        add_log(f"[ERROR] {error_msg} after {error_time:.2f}ms")
        
        # Return only fields expected by hackathon portal
        response = {
            "status": "error",
            "reply": error_msg
        }
        
        # DEBUG: Log response being sent
        import json
        add_log(f"[RESPONSE] Sending error response: {json.dumps(response, indent=2)}")
        
        return response
    except Exception as e:
        error_time = (time.time() - start_time) * 1000
        error_msg = f"Unexpected error: {str(e)}"
        add_log(f"[ERROR] {str(e)} after {error_time:.2f}ms")
        
        # Return only fields expected by hackathon portal
        response = {
            "status": "error",
            "reply": error_msg
        }
        
        # DEBUG: Log response being sent
        import json
        add_log(f"[RESPONSE] Sending error response: {json.dumps(response, indent=2)}")
        
        return response


@router.get("/sessions")
async def get_sessions():
    """Get all sessions (active and ended) for the session panel."""
    db = get_database()
    if db is None:
        return {"sessions": []}
    
    try:
        # Get all sessions, sorted by creation time (newest first)
        sessions = await db.scam_sessions.find().sort("createdAt", -1).to_list(100)
        
        result = []
        for session in sessions:
            result.append({
                "sessionId": session["sessionId"],
                "status": session["status"],
                "channel": session.get("metadata", {}).get("channel", "Unknown"),
                "totalMessages": session.get("totalMessages", 0),
                "createdAt": session["createdAt"].isoformat() if session.get("createdAt") else None,
                "endedAt": session.get("endedAt").isoformat() if session.get("endedAt") else None,
                "endReason": session.get("endReason", None)
            })
        
        return {"sessions": result}
    except Exception as e:
        add_log(f"[ERROR] Failed to get sessions: {str(e)}")
        return {"sessions": [], "error": str(e)}


@router.get("/session/{session_id}/output")
async def get_session_output(session_id: str):
    """Get full output for a specific session."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    session = await db.scam_sessions.find_one({"sessionId": session_id})
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Format conversation history for display
    conversation = []
    for msg in session.get("conversationHistory", []):
        conversation.append({
            "sender": msg.get("sender", "unknown"),
            "text": msg.get("text", ""),
            "timestamp": msg.get("timestamp").isoformat() if msg.get("timestamp") else None
        })
    
    return {
        "sessionId": session["sessionId"],
        "status": session["status"],
        "scamDetected": session["status"] == "ended",
        "totalMessagesExchanged": session.get("totalMessages", 0),
        "extractedIntelligence": session.get("extractedIntelligence", {}),
        "agentNotes": session.get("agentNotes", ""),
        "conversationHistory": conversation,
        "metadata": session.get("metadata", {}),
        "createdAt": session.get("createdAt").isoformat() if session.get("createdAt") else None,
        "endedAt": session.get("endedAt").isoformat() if session.get("endedAt") else None,
        "endReason": session.get("endReason", None)
    }


@router.post("/session/{session_id}/timeout")
async def timeout_session(session_id: str):
    """Manually timeout a session (called after 15s inactivity)."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    session = await db.scam_sessions.find_one({"sessionId": session_id})
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session["status"] != "active":
        return {"status": "already_ended", "sessionId": session_id}
    
    # Generate conversation summary using LLM

    
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
    
    # Use OpenRouter to generate summary (with key failover)
    try:
        # Format intelligence in a readable way
        intel_details = []
        if intel.get('bankAccounts'):
            intel_details.append(f"Bank accounts: {', '.join(intel['bankAccounts'])}")
        if intel.get('upiIds'):
            intel_details.append(f"UPI IDs: {', '.join(intel['upiIds'])}")
        if intel.get('phoneNumbers'):
            intel_details.append(f"Phone numbers: {', '.join(intel['phoneNumbers'])}")
        if intel.get('phishingLinks'):
            intel_details.append(f"Links: {', '.join(intel['phishingLinks'][:2])}")  # Limit to 2
        
        intel_formatted = "\n".join(intel_details) if intel_details else "None"
        
        response = await openrouter_manager.call(
            model="google/gemini-2.0-flash-exp:free",
            messages=[{
                "role": "user",
                "content": f"""You are analyzing a scam conversation between a scammer and a honeypot AI agent. Write a concise 2-3 sentence summary.

=== CONVERSATION ===
{conversation_text}

=== EXTRACTED INTELLIGENCE ===
{intel_formatted}

=== INSTRUCTIONS ===
Write a professional summary that:
1. Describes what scam tactic the scammer used (e.g., "fake bank alert", "prize scam", "OTP phishing")
2. Names the specific information extracted (if any)
3. Uses past tense and third person
4. Does NOT mention timeout, session ending, or technical details

Example good summaries:
- "The scammer posed as a bank representative requesting account verification. Successfully extracted the target's UPI ID (username@bank) and phone number."
- "Attempted prize/lottery scam claiming the victim won money. No sensitive information was disclosed during the conversation."
- "Phishing attempt using urgency tactics to obtain OTP code. Extracted one phone number but no financial credentials."

Your summary:"""
            }],
            max_tokens=150,
            temperature=0.7
        )
        
        agent_notes = response.choices[0].message.content.strip()
        
        # Validate LLM output - if it's bad, create manual summary
        if (len(agent_notes) < 30 or 
            "Extracted Intelligence:" in agent_notes or 
            "=== " in agent_notes or
            "Example" in agent_notes):
            
            # Create descriptive manual summary
            if has_intel:
                intel_items = []
                if intel.get('bankAccounts'):
                    intel_items.append(f"{len(intel['bankAccounts'])} bank account(s)")
                if intel.get('upiIds'):
                    intel_items.append(f"{len(intel['upiIds'])} UPI ID(s)")
                if intel.get('phoneNumbers'):
                    intel_items.append(f"{len(intel['phoneNumbers'])} phone number(s)")
                if intel.get('phishingLinks'):
                    intel_items.append(f"{len(intel['phishingLinks'])} phishing link(s)")
                
                agent_notes = f"Scam engagement completed. Successfully extracted: {', '.join(intel_items)}."
            else:
                agent_notes = f"Scam conversation engaged over {session.get('totalMessages', 0)} messages. No sensitive information extracted."
        
    except Exception as e:
        add_log(f"[TIMEOUT_ERROR] Failed to generate notes: {str(e)}")
        # Fallback summary
        if has_intel:
            intel_items = []
            if intel.get('bankAccounts'):
                intel_items.append(f"{len(intel['bankAccounts'])} bank account(s)")
            if intel.get('upiIds'):
                intel_items.append(f"{len(intel['upiIds'])} UPI ID(s)")
            if intel.get('phoneNumbers'):
                intel_items.append(f"{len(intel['phoneNumbers'])} phone number(s)")
            if intel.get('phishingLinks'):
                intel_items.append(f"{len(intel['phishingLinks'])} phishing link(s)")
            
            agent_notes = f"Scam engagement completed. Successfully extracted: {', '.join(intel_items)}."
        else:
            agent_notes = f"Scam conversation engaged over {session.get('totalMessages', 0)} messages. No sensitive information extracted."
    
    # End the session due to timeout
    from datetime import datetime
    await db.scam_sessions.update_one(
        {"sessionId": session_id},
        {"$set": {
            "status": "ended",
            "endedAt": datetime.utcnow(),
            "endReason": "timeout",
            "agentNotes": agent_notes
        }}
    )
    
    add_log(f"[TIMEOUT] Session {session_id} ended due to timeout")
    
    # Get final session data for GUVI submission
    final_session = await db.scam_sessions.find_one({"sessionId": session_id})
    
    # MANDATORY: Submit final results to GUVI hackathon endpoint
    add_log(f"[TIMEOUT] Submitting results to GUVI for session: {session_id}")
    from app.core.guvi_client import submit_final_result
    import asyncio
    asyncio.create_task(submit_final_result(final_session))
    
    # Prepare final output
    final_output = {
        "status": "ended",
        "sessionId": session_id,
        "scamDetected": True,
        "totalMessagesExchanged": final_session.get("totalMessages", 0),
        "extractedIntelligence": final_session.get("extractedIntelligence", {}),
        "agentNotes": agent_notes,
        "endReason": "timeout"
    }

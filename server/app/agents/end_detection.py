"""
Agent 3: End Detection Agent
Provider: OpenRouter (google/gemini-2.0-flash-exp:free)
Purpose: Decide when to end conversation and generate notes
"""
from openai import OpenAI
from app.core.config import OPENROUTER_API_KEY
from app.core.logger import add_log
import time
from typing import Dict, List, Tuple

# Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)


def _build_intel_notes(intel: Dict[str, List[str]]) -> str:
    """Build a comprehensive notes string from extracted intelligence."""
    parts = []
    if intel.get("bankAccounts"):
        parts.append(f"Bank accounts: {intel['bankAccounts']}")
    if intel.get("upiIds"):
        parts.append(f"UPI IDs: {intel['upiIds']}")
    if intel.get("phoneNumbers"):
        parts.append(f"Phone numbers: {intel['phoneNumbers']}")
    if intel.get("phishingLinks"):
        parts.append(f"Phishing links: {intel['phishingLinks']}")
    if intel.get("suspiciousKeywords"):
        parts.append(f"Keywords: {intel['suspiciousKeywords']}")
    
    if parts:
        return "Scammer intelligence extracted: " + ". ".join(parts) + "."
    return ""


async def check_end_condition(
    message_count: int,
    extracted_intelligence: Dict[str, List[str]],
    latest_scammer_msg: str,
    latest_agent_reply: str
) -> Tuple[bool, str, str]:
    """
    Check if enough intelligence has been gathered to generate final output.
    
    IMPORTANT: Returning True here does NOT stop the conversation.
    The orchestrator will generate agentNotes and submit to GUVI,
    but will keep the session ACTIVE so the honeypot continues replying.
    The session only truly ends on 45-second inactivity timeout.
    
    Returns:
        Tuple[bool, str, str]: (ready_to_finalize, notes, reason)
    """
    add_log(f"[AGENT3_START] Checking end condition (msg: {message_count})")
    
    # Check extracted intelligence
    has_bank = len(extracted_intelligence.get("bankAccounts", [])) > 0
    has_upi = len(extracted_intelligence.get("upiIds", [])) > 0
    has_phone = len(extracted_intelligence.get("phoneNumbers", [])) > 0
    intel_count = sum([has_bank, has_upi, has_phone])
    
    # Don't finalize too early — need enough conversation
    if message_count < 8:
        add_log(f"[AGENT3_END] Too early (msg: {message_count}, intel: {intel_count})")
        return False, "Continuing engagement", ""
    
    # Ready to finalize: Got 2+ types of scammer details after enough conversation
    if intel_count >= 2 and message_count >= 10:
        notes = _build_intel_notes(extracted_intelligence)
        add_log(f"[AGENT3_END] Ready to finalize ({intel_count} intel types, {message_count} msgs)")
        return True, notes, "intelligence_gathered"
    
    # Ready to finalize: Got financial details + good conversation
    if (has_bank or has_upi) and message_count >= 12:
        notes = _build_intel_notes(extracted_intelligence)
        add_log(f"[AGENT3_END] Ready to finalize (financial intel, {message_count} msgs)")
        return True, notes, "intelligence_gathered"
    
    # Safety cap
    if message_count >= 50:
        notes = _build_intel_notes(extracted_intelligence)
        add_log(f"[AGENT3_END] Safety cap reached (50 messages)")
        return True, notes or "Maximum conversation limit reached.", "max_messages"
    
    add_log(f"[AGENT3_END] Continuing conversation (msg: {message_count})")
    return False, "Continuing engagement", ""


async def check_timeout(session_id: str, last_activity_timestamp) -> Tuple[bool, str]:
    """
    Check if session should timeout (15 seconds inactivity).
    
    Args:
        session_id: Session ID
        last_activity_timestamp: datetime of last activity
    
    Returns:
        Tuple[bool, str]: (should_timeout, notes)
    """
    from datetime import datetime
    
    if last_activity_timestamp is None:
        return False, ""
    
    time_since_last = (datetime.utcnow() - last_activity_timestamp).total_seconds()
    
    if time_since_last >= 15:
        add_log(f"[AGENT3_TIMEOUT] Session {session_id} timed out after {time_since_last:.1f}s")
        return True, f"Session ended due to 15-second inactivity timeout."
    
    return False, ""

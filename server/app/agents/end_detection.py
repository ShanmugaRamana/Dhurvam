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


async def check_end_condition(
    message_count: int,
    extracted_intelligence: Dict[str, List[str]],
    latest_scammer_msg: str,
    latest_agent_reply: str
) -> Tuple[bool, str, str]:
    """
    Decide if conversation should end and generate notes.
    
    Returns:
        Tuple[bool, str, str]: (should_end, notes, end_reason)
    """
    start_time = time.time()
    add_log(f"[AGENT3_START] Checking end condition (msg: {message_count})")
    
    # Quick checks (no LLM needed)
    if message_count >= 15:
        add_log(f"[AGENT3_END] Max messages reached")
        return True, "Maximum conversation limit reached.", "max_messages"
    
    # Check extracted intelligence
    has_bank = len(extracted_intelligence.get("bankAccounts", [])) > 0
    has_upi = len(extracted_intelligence.get("upiIds", [])) > 0
    has_link = len(extracted_intelligence.get("phishingLinks", [])) > 0
    has_phone = len(extracted_intelligence.get("phoneNumbers", [])) > 0
    keywords = extracted_intelligence.get("suspiciousKeywords", [])
    
    intel_count = sum([has_bank, has_upi, has_phone])
    
    # End conditions - MORE AGGRESSIVE
    if (has_bank or has_upi) and message_count >= 4:
        notes = f"Extracted financial details: "
        if has_bank:
            notes += f"Bank accounts: {extracted_intelligence['bankAccounts']}. "
        if has_upi:
            notes += f"UPI IDs: {extracted_intelligence['upiIds']}. "
        add_log(f"[AGENT3_END] Financial details obtained")
        return True, notes, "intelligence_gathered"
    
    if has_link and has_phone and message_count >= 6:
        add_log(f"[AGENT3_END] Link and phone obtained")
        return True, f"Phishing link and phone number extracted.", "intelligence_gathered"
    
    all_intel = sum([has_bank, has_upi, has_link, has_phone])
    if all_intel >= 2 and message_count >= 8:
        add_log(f"[AGENT3_END] Multiple intel types obtained")
        return True, "Multiple intelligence types extracted.", "intelligence_gathered"
    
    if message_count >= 10:
        try:
            prompt = f"""Scam conversation analysis. Should we END?

Messages: {message_count}
Bank Accounts: {extracted_intelligence.get('bankAccounts', [])}
UPI IDs: {extracted_intelligence.get('upiIds', [])}
Links: {extracted_intelligence.get('phishingLinks', [])}
Phones: {extracted_intelligence.get('phoneNumbers', [])}
Keywords: {keywords}

Scammer said: "{latest_scammer_msg}"

END if: enough info OR scammer suspicious OR conversation looping.
Reply ONLY: END or CONTINUE"""

            response = client.chat.completions.create(
                model="google/gemini-2.0-flash-exp:free",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10
            )
            
            result = response.choices[0].message.content.strip().upper()
            duration = (time.time() - start_time) * 1000
            add_log(f"[AGENT3_END] LLM decision in {duration:.2f}ms: {result}")
            
            if "END" in result:
                return True, "Scammer engagement complete. Intelligence gathered.", "llm_decision"
            
        except Exception as e:
            add_log(f"[AGENT3_ERROR] OpenRouter failed: {str(e)}")
    
    add_log(f"[AGENT3_END] Continuing conversation")
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

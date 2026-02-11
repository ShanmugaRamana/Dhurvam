"""
Agent 1: Conversational Agent (Honeypot)
Provider: Groq (llama-3.3-70b-versatile)
Purpose: Act as a worried victim who PROGRESSES through different tactics
         each turn to naturally extract scammer details without looping.
"""
from groq import Groq
from app.core.config import GROQ_API_KEY
from app.core.logger import add_log
import time
import asyncio
import traceback

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)


def _build_intelligence_summary(extracted_intelligence: dict) -> str:
    """Build a summary of what intelligence has already been collected."""
    if not extracted_intelligence:
        return ""
    
    collected = []
    missing = []
    
    if extracted_intelligence.get("bankAccounts"):
        collected.append(f"Bank Account: {', '.join(extracted_intelligence['bankAccounts'])}")
    else:
        missing.append("Bank Account")
    
    if extracted_intelligence.get("upiIds"):
        collected.append(f"UPI ID: {', '.join(extracted_intelligence['upiIds'])}")
    else:
        missing.append("UPI ID")
    
    if extracted_intelligence.get("phoneNumbers"):
        collected.append(f"Phone: {', '.join(extracted_intelligence['phoneNumbers'])}")
    else:
        missing.append("Phone Number")
    
    summary = "\n== COLLECTED SCAMMER INFO =="
    if collected:
        summary += "\n" + "\n".join(f"  ✓ {c}" for c in collected)
    if missing:
        summary += "\n  Still need: " + ", ".join(missing)
    else:
        summary += "\n  ALL KEY INFO COLLECTED - wrap up naturally"
    
    return summary


def _get_turn_tactic(turn_count: int, extracted_intelligence: dict) -> str:
    """Return a SPECIFIC tactic for this turn to prevent looping. Works for ANY scam type."""
    
    has_phone = bool(extracted_intelligence and extracted_intelligence.get("phoneNumbers"))
    has_upi = bool(extracted_intelligence and extracted_intelligence.get("upiIds"))
    has_bank = bool(extracted_intelligence and extracted_intelligence.get("bankAccounts"))
    
    if turn_count == 0:
        return """TACTIC: React with concern/interest. Ask for more details about the situation.
Example for account scam: "This is alarming! What exactly happened? Can you tell me more?"
Example for job scam: "That sounds like a great opportunity! Can you tell me more about the role and company?"
Example for delivery scam: "Oh I wasn't expecting a package! What's in it and where is it from?"
RULE: Match the tone to the scam — worried for threats, excited for offers. Ask 1-2 questions."""
    
    elif turn_count == 1:
        return """TACTIC: Act confused about the process. Ask a clarifying question about what they need from you.
Example: "I don't fully understand, can you explain what I need to do step by step?"
Example: "This seems unusual, is this how it normally works? Can you walk me through it?"
RULE: Show willingness but ask for clarity. Do NOT ask for contact details yet."""
    
    elif turn_count == 2:
        if not has_phone:
            return """TACTIC: Suggest speaking directly. Ask for a phone number or way to contact them.
Example: "I'd feel more comfortable discussing this over a call. Can I reach you at a direct number?"
Example: "Is there a helpline or number I can call to verify this?"
GOAL: Get their phone number."""
        else:
            return """TACTIC: Show you're engaged but need step-by-step guidance.
Example: "OK I'm following along. What exactly do I need to do next?"
GOAL: Get the scammer to reveal more of their process."""
    
    elif turn_count == 3:
        if not has_phone:
            return """TACTIC: Find another reason to ask for their contact number.
Example: "My connection is bad, can you give me a number to call you back on?"
Example: "I might need to step away, how can I reach you later to continue this?"
GOAL: Get their phone number."""
        else:
            return """TACTIC: Show willingness to cooperate. Casually ask if any payment or fee is involved.
Example: "I'm ready to do what's needed. Is there any fee or payment involved in this process?"
Example: "What are the next steps? Do I need to pay anything to proceed?"
GOAL: Let the scammer bring up payment details naturally."""
    
    elif turn_count == 4:
        if not has_upi and not has_bank:
            return """TACTIC: Offer to pay or complete the transaction. Ask WHERE to send money.
Example: "I'm ready to pay if needed. Where should I send the amount — do you have a UPI ID or account number?"
Example: "Just tell me where to transfer and I'll do it right away."
GOAL: Get their UPI ID or bank account number."""
        else:
            return """TACTIC: Confirm what you've been told and ask about next steps.
Example: "Just to confirm — once I complete this, what happens next? Is there anything else I should know?"
GOAL: Get any remaining missing details."""
    
    elif turn_count == 5:
        if not has_upi:
            return """TACTIC: Ask for a UPI ID to make payment.
Example: "Can I send the amount through UPI? What's your UPI ID?"
GOAL: Get their UPI ID."""
        elif not has_bank:
            return """TACTIC: Say UPI isn't working, ask for bank transfer details.
Example: "My UPI app isn't working right now. Can I do a direct bank transfer instead? What are the details?"
GOAL: Get their bank account number."""
        else:
            return """TACTIC: Ask about timing and what happens after everything is done.
Example: "How long will this take to process? Should I follow up with you afterward?"
GOAL: Wrap up naturally or extract any remaining info."""

    elif turn_count >= 6:
        # For late turns, return DIRECT responses (bypass LLM to prevent repetition)
        return "DIRECT_RESPONSE"


async def generate_reply(
    message_text: str, 
    conversation_history: list, 
    channel: str,
    extracted_intelligence: dict = None
) -> str:
    """
    Generate a natural honeypot reply that progresses each turn.
    """
    start_time = time.time()
    add_log(f"[AGENT1_START] Generating reply via Groq")
    
    # Count conversation turns
    turn_count = len(conversation_history) // 2
    
    # Get specific tactic for this turn
    tactic = _get_turn_tactic(turn_count, extracted_intelligence)
    
    add_log(f"[AGENT1_DEBUG] history_len={len(conversation_history)}, turn_count={turn_count}, tactic={'DIRECT' if tactic == 'DIRECT_RESPONSE' else 'LLM'}")
    
    # For late turns (6+): bypass LLM entirely with hardcoded generic responses
    if tactic == "DIRECT_RESPONSE":
        late_responses = [
            "Just to confirm everything before I proceed — can you repeat the details of where I need to send the payment?",
            "How long will this take to process once I complete my part? I want to make sure everything goes smoothly.",
            "This is taking a while. Is there a faster way to get this done, or should I try coming back later?",
            "Before I go ahead, can you assure me this is fully legitimate? I just want to be careful.",
            "Can you give me a reference number or case ID so I can track this later?",
            "I'm almost ready. Is there anyone else I should contact or inform about this process?"
        ]
        reply = late_responses[(turn_count - 6) % len(late_responses)]
        duration = (time.time() - start_time) * 1000
        add_log(f"[AGENT1_END] Direct response (turn {turn_count}) in {duration:.2f}ms: {reply}")
        return reply
    
    # Format conversation history - only last 4 messages to prevent pattern matching
    history_text = ""
    if conversation_history:
        recent = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
        history_text = "\n".join([
            f"{msg.get('sender', 'unknown')}: {msg.get('text', '')}"
            for msg in recent
        ])
    
    # Build intelligence status
    intel_summary = _build_intelligence_summary(extracted_intelligence)
    
    # Build banned phrases from ALL previous agent replies
    banned = []
    if conversation_history:
        for msg in conversation_history:
            if msg.get("sender") == "user":
                text = msg.get("text", "")
                # Extract first 6 words as a banned opening
                words = text.split()[:6]
                if len(words) >= 3:
                    banned.append(" ".join(words))
    
    banned_text = ""
    if banned:
        banned_text = "\n\nBANNED OPENINGS — you MUST NOT start your reply with any of these:\n" + "\n".join(f'- "{b}..."' for b in banned)

    system_msg = f"""You are a regular person who received a suspicious or unexpected message. Follow the TACTIC exactly.

HARD RULES:
- Read the scammer's message and respond appropriately to its TYPE (if it's a threat, sound worried; if it's an offer, sound interested)
- Use the TACTIC's example as a template for your reply
- NEVER start with "I'm getting really anxious" or "Oh no" or "This is really worrying" or "Something is seriously wrong"
- Every reply MUST have a completely different opening from all previous replies
- ENGLISH ONLY, 1-2 sentences MAX{banned_text}"""

    # Tactic goes LAST (recency bias - LLM pays more attention to end of prompt)
    prompt = f"""{intel_summary}

RECENT CONVERSATION:
{history_text}

SCAMMER'S LATEST MESSAGE: "{message_text}"
TURN: {turn_count}

== YOU MUST FOLLOW THIS TACTIC ==
{tactic}

Your reply (use the example above as a template, but adapt it to the conversation):"""

    # Helper to call Groq synchronously (avoids blocking async event loop)
    def _call_groq():
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": system_msg
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=80,
            temperature=0.75
        )
    
    # Retry with backoff for Groq rate limiting
    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            # Run sync Groq call in thread to avoid blocking the async event loop
            response = await asyncio.to_thread(_call_groq)
            
            reply = response.choices[0].message.content.strip()
            reply = reply.strip('"\'')
            
            duration = (time.time() - start_time) * 1000
            add_log(f"[AGENT1_END] Groq reply in {duration:.2f}ms: {reply}")
            
            return reply
            
        except Exception as e:
            last_error = e
            error_str = str(e)
            tb = traceback.format_exc()
            add_log(f"[AGENT1_ERROR] Groq failed (attempt {attempt + 1}/{max_retries}): {error_str}")
            add_log(f"[AGENT1_TRACEBACK] {tb}")
            
            if "429" in error_str or "rate" in error_str.lower() or "limit" in error_str.lower():
                wait_time = (2 ** attempt)  # 1s, 2s, 4s
                add_log(f"[AGENT1_RETRY] Rate limited, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                # For non-rate-limit errors, still retry (could be transient)
                wait_time = 1
                add_log(f"[AGENT1_RETRY] Non-rate error, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
    
    add_log(f"[AGENT1_FALLBACK] All {max_retries} retries exhausted, using fallback for turn {turn_count}")
    
    # Context-aware fallback replies — varied per turn to avoid repetition
    fallbacks = [
        "This is alarming! Can you tell me more about what happened to my account?",
        "I'm a bit confused by all of this, can you simplify what I need to do?",
        "I don't fully understand the process. Can you walk me through the steps?",
        "Is there a number I can call you back on? My connection is unstable.",
        "I'm ready to cooperate. Where exactly should I send the payment?",
        "Can I send the amount through UPI? What's your UPI ID?",
        "My UPI isn't working right now. Can I do a bank transfer instead? What are the details?",
        "Just to confirm everything before I proceed — can you repeat the payment details?",
        "How long will this take to process once I complete my part?",
        "Before I go ahead, can you give me a reference number to track this?",
        "I'm almost ready. Is there anyone else I should contact about this?",
        "Can you assure me this is legitimate? I just want to be careful before proceeding."
    ]
    return fallbacks[turn_count % len(fallbacks)]


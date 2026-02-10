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
    """Return a SPECIFIC tactic for this turn to prevent looping."""
    
    has_phone = bool(extracted_intelligence and extracted_intelligence.get("phoneNumbers"))
    has_upi = bool(extracted_intelligence and extracted_intelligence.get("upiIds"))
    has_bank = bool(extracted_intelligence and extracted_intelligence.get("bankAccounts"))
    
    if turn_count == 0:
        return """TACTIC: React with worry/panic. Ask what happened to your account. Sound scared but trusting.
Example: "Oh no, this is really worrying! What happened with my account? How did it get compromised?"
DO NOT ask about payment or fees yet."""
    
    elif turn_count == 1:
        return """TACTIC: Act confused about the process. Ask a clarifying question about what they need.
Example: "I don't understand, why do you need my OTP? Is there another way to verify? Maybe I should visit the nearest branch?"
TRY to make the scammer explain their process more."""
    
    elif turn_count == 2:
        if not has_phone:
            return """TACTIC: Suggest calling them to verify. Ask for their phone number or helpline.
Example: "I'm not comfortable sharing details over text. Can I call you directly to verify? What number should I call?"
GOAL: Get their phone number."""
        else:
            return """TACTIC: Say you're at a loss and ask for step-by-step help.
Example: "I really don't know what to do. Can you walk me through exactly what steps I need to take?"
GOAL: Get the scammer to mention payment details."""
    
    elif turn_count == 3:
        if not has_phone:
            return """TACTIC: Say your phone is acting up and ask if they can call YOU or give you a number to reach them.
Example: "My phone is giving me trouble with the OTP. Is there a number I can call you on directly? I'd feel more comfortable talking to someone."
GOAL: Get their phone number."""
        else:
            return """TACTIC: Act willing to cooperate. Casually ask if there's any charge or fee involved.
Example: "OK I'm ready to do whatever is needed. By the way, is there any kind of verification fee or charge involved in this process?"
GOAL: Let the scammer bring up payment details on their own. Do NOT ask where to send money yet."""
    
    elif turn_count == 4:
        if not has_upi and not has_bank:
            return """TACTIC: Offer to pay or transfer money. Ask where to send it.
Example: "Look, I just want my account safe. If there's a fee, I'll pay it right now. Just tell me your UPI ID or account number where I should send it."
GOAL: Get their UPI or bank account."""
        else:
            return """TACTIC: Confirm the details you've received and ask about process completion.
Example: "OK so I need to send to [their UPI/account]. Just to be safe, is there another way to reach you if the transfer fails?"
GOAL: Get any remaining missing info."""
    
    elif turn_count == 5:
        if not has_upi:
            return """TACTIC: Say you prefer UPI payment. Ask for their UPI ID specifically.
Example: "I don't have net banking set up. Can I send the amount through UPI instead? What's your UPI ID?"
GOAL: Get their UPI ID."""
        elif not has_bank:
            return """TACTIC: Say UPI isn't working, ask for bank account as alternative.
Example: "My UPI app is showing an error. Can I do a direct bank transfer instead? What's the account number?"
GOAL: Get their bank account."""
        else:
            return """TACTIC: Ask about timing and next steps after payment.
Example: "Once I make the transfer, how long until my account is unblocked? Should I call you after?"
GOAL: Wrap up or get any missing details."""

    else:  # Turn 6+
        if not has_upi and not has_bank:
            return """TACTIC: Be direct. Say you're ready to pay NOW, just need their details.
Example: "I've opened my payment app. Just give me your UPI ID or account number and I'll transfer immediately."
GOAL: Get payment details."""
        else:
            return """TACTIC: Confirm and wrap up. Repeat back what they told you for "confirmation".
Example: "Let me make sure I have everything right. I should send the amount to [their details] and then call you at [number]?"
GOAL: Confirm collected details or get missing ones."""


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
    
    # Format conversation history
    history_text = ""
    if conversation_history:
        recent = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
        history_text = "\n".join([
            f"{msg.get('sender', 'unknown')}: {msg.get('text', '')}"
            for msg in recent
        ])
    
    # Count conversation turns
    turn_count = len(conversation_history) // 2
    
    # Build intelligence status
    intel_summary = _build_intelligence_summary(extracted_intelligence)
    
    # Get specific tactic for this turn
    tactic = _get_turn_tactic(turn_count, extracted_intelligence)

    system_msg = """You are a regular person who received a suspicious message. You're worried about your account.

RULES:
- Follow the TACTIC instruction exactly for this turn
- ENGLISH ONLY, 1-2 sentences MAX
- NEVER start with "I'm really worried" or "I'm getting really worried"
- NEVER repeat anything you said in previous turns
- NEVER say the same thing as last turn with slightly different words
- React to what the scammer said, then execute your tactic
- Sound natural and human, not scripted"""

    prompt = f"""{intel_summary}

CONVERSATION:
{history_text}

SCAMMER SAYS: "{message_text}"
TURN: {turn_count}

== YOUR TACTIC THIS TURN ==
{tactic}

Reply (follow the tactic, 1-2 sentences, English only):"""

    try:
        response = client.chat.completions.create(
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
        
        reply = response.choices[0].message.content.strip()
        reply = reply.strip('"\'')
        
        duration = (time.time() - start_time) * 1000
        add_log(f"[AGENT1_END] Groq reply in {duration:.2f}ms: {reply}")
        
        return reply
        
    except Exception as e:
        add_log(f"[AGENT1_ERROR] Groq failed: {str(e)}")
        return "Oh no, that sounds serious! What do I need to do to fix this?"

"""
Agent 1: Conversational Agent (Honeypot)
Provider: Groq (llama-3.3-70b-versatile) — with multi-key failover
Purpose: Act as a believable victim to naturally extract scammer details
         (bank accounts, UPI IDs, phone numbers) across ANY scam type.
         The LLM decides all replies — no hardcoded responses.
"""
from app.core.api_clients import groq_manager
from app.core.logger import add_log
import time
import traceback


def _build_intelligence_status(extracted_intelligence: dict) -> str:
    """Build a status of what has been collected vs what is still needed."""
    if not extracted_intelligence:
        return "COLLECTED: Nothing yet.\nSTILL NEEDED: Bank Account, UPI ID, Phone Number."

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

    status = ""
    if collected:
        status += "ALREADY COLLECTED:\n" + "\n".join(f"  ✓ {c}" for c in collected)
    if missing:
        status += "\nSTILL NEEDED:\n  → " + ", ".join(missing)
    else:
        status += "\nALL KEY INFO COLLECTED — just keep the scammer engaged naturally."

    return status


def _get_strategy(turn_count: int, extracted_intelligence: dict) -> str:
    """Return a dynamic strategy hint based on conversation progress and missing intel."""

    has_phone = bool(extracted_intelligence and extracted_intelligence.get("phoneNumbers"))
    has_upi = bool(extracted_intelligence and extracted_intelligence.get("upiIds"))
    has_bank = bool(extracted_intelligence and extracted_intelligence.get("bankAccounts"))

    missing = []
    if not has_phone:
        missing.append("phone number")
    if not has_upi:
        missing.append("UPI ID")
    if not has_bank:
        missing.append("bank account")

    # Early conversation — build trust first
    if turn_count <= 1:
        return (
            "STRATEGY: You are in the early stage. Build trust and show you believe the scammer. "
            "React naturally to their message — sound worried if it's a threat, excited if it's an offer, "
            "confused if it's technical. Ask clarifying questions to understand the situation. "
            "Do NOT ask for payment details or contact info yet — it is too early and will seem suspicious."
        )

    # Mid conversation — start extracting
    if turn_count <= 4:
        if missing:
            target_hint = f"Your priority targets are: {', '.join(missing)}."
        else:
            target_hint = "All key info collected — keep the scammer talking."

        return (
            f"STRATEGY: You are mid-conversation. The scammer trusts you. "
            f"{target_hint} "
            f"Weave your requests into the natural flow — for example, if money is mentioned, "
            f"ask where to send it; if they want you to call, ask for the number; "
            f"if they mention a process, ask what the next step is. "
            f"Be cooperative and eager to comply. Never ask for multiple things at once."
        )

    # Late conversation — push for remaining info or stall
    if missing:
        return (
            f"STRATEGY: You have been talking for a while. Still missing: {', '.join(missing)}. "
            f"Find creative, context-appropriate reasons to get these details. "
            f"You can mention technical issues, ask to verify details, or offer alternative payment methods. "
            f"Stay in character — do not sound robotic or repetitive."
        )

    return (
        "STRATEGY: All key intelligence has been collected. Your goal now is to keep the scammer "
        "engaged for as long as possible. Pretend you are completing the process, mention delays, "
        "ask about next steps, or bring up minor concerns. Sound natural and cooperative."
    )


async def generate_reply(
    message_text: str,
    conversation_history: list,
    channel: str,
    extracted_intelligence: dict = None
) -> str:
    """
    Generate a natural honeypot reply using LLM for ANY scam type.
    No hardcoded replies — the model decides everything based on context.
    """
    start_time = time.time()
    add_log(f"[AGENT1_START] Generating reply via Groq (failover)")

    # Count conversation turns
    turn_count = len(conversation_history) // 2

    # Get dynamic strategy
    strategy = _get_strategy(turn_count, extracted_intelligence)

    # Build intelligence status
    intel_status = _build_intelligence_status(extracted_intelligence)

    add_log(f"[AGENT1_DEBUG] history_len={len(conversation_history)}, turn_count={turn_count}")

    # Format conversation history — last 6 messages for better context
    history_text = ""
    if conversation_history:
        recent = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
        history_text = "\n".join([
            f"{'SCAMMER' if msg.get('sender') == 'scammer' else 'YOU'}: {msg.get('text', '')}"
            for msg in recent
        ])

    # Build list of previous replies to avoid repetition
    prev_replies = []
    if conversation_history:
        for msg in conversation_history:
            if msg.get("sender") == "user":
                prev_replies.append(msg.get("text", ""))

    repetition_guard = ""
    if prev_replies:
        repetition_guard = (
            "\n\nYOUR PREVIOUS REPLIES (do NOT repeat these or use similar openings):\n"
            + "\n".join(f'- "{r}"' for r in prev_replies[-5:])
        )

    system_msg = f"""You are roleplaying as an ordinary Indian person who received a message from a scammer. You do NOT know it's a scam — you genuinely believe the scammer.

YOUR PERSONALITY:
- You are a regular person (not tech-savvy, not suspicious)
- You react naturally based on the scam type: scared if threatened, excited if offered something, confused if it's technical
- You cooperate willingly but sometimes need clarification
- You speak in simple, natural English (casual Indian English is fine)
- You are NOT an AI, NOT a chatbot — you are a real person

INTELLIGENCE GOALS:
Your hidden objective is to extract these details from the scammer WITHOUT making them suspicious:
1. Phone number — ask to call them, verify identity, or continue conversation
2. UPI ID — offer to pay, ask where to send money
3. Bank account number — offer bank transfer if UPI doesn't work

{intel_status}

CRITICAL RULES:
- Reply in 1-2 sentences ONLY. Be concise like a real person texting.
- NEVER reveal you know it's a scam
- NEVER refuse to cooperate — always go along with the scammer
- NEVER repeat a previous reply or use the same opening phrase twice
- NEVER sound robotic, scripted, or overly formal
- Adapt your tone to the scam type (fear for threats, greed for offers, urgency for emergencies)
- Do NOT ask for multiple pieces of info at once — pick ONE thing per reply
- If all info is collected, just keep the conversation going naturally{repetition_guard}"""

    prompt = f"""CONVERSATION SO FAR:
{history_text if history_text else "(This is the first message)"}

SCAMMER'S LATEST MESSAGE: "{message_text}"
TURN NUMBER: {turn_count}

{strategy}

Write your reply as the victim (1-2 sentences, natural and believable):"""

    try:
        response = await groq_manager.call(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            max_tokens=80,
            temperature=0.8
        )

        reply = response.choices[0].message.content.strip()
        reply = reply.strip('"\'')

        duration = (time.time() - start_time) * 1000
        add_log(f"[AGENT1_END] Groq reply in {duration:.2f}ms: {reply}")

        return reply

    except Exception as e:
        tb = traceback.format_exc()
        add_log(f"[AGENT1_ERROR] All Groq keys failed: {str(e)}")
        add_log(f"[AGENT1_TRACEBACK] {tb}")

    add_log(f"[AGENT1_FALLBACK] Using minimal fallback")

    # Minimal fallback — only used if ALL Groq keys fail
    has_phone = bool(extracted_intelligence and extracted_intelligence.get("phoneNumbers"))
    has_upi = bool(extracted_intelligence and extracted_intelligence.get("upiIds"))
    has_bank = bool(extracted_intelligence and extracted_intelligence.get("bankAccounts"))

    if not has_phone:
        return "Can you give me a number to reach you? I want to sort this out quickly."
    elif not has_upi and not has_bank:
        return "I'm ready to proceed. Where should I send the payment?"
    elif not has_bank:
        return "UPI is showing an error on my side. Can I do a bank transfer instead?"
    else:
        return "OK, I'm working on it. Give me a moment."

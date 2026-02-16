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

    if extracted_intelligence.get("emailAddresses"):
        collected.append(f"Email: {', '.join(extracted_intelligence['emailAddresses'])}")

    if extracted_intelligence.get("phishingLinks"):
        collected.append(f"Links: {', '.join(extracted_intelligence['phishingLinks'])}")

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

    # Turn 0 — react AND immediately probe
    if turn_count <= 0:
        return (
            "STRATEGY: This is the VERY FIRST message. React believably AND immediately ask a PROBING question. "
            "If it's a threat (account blocked, legal action), sound panicked and ask 'Oh no! What should I do? Can I call someone to fix this?' "
            "If it's an offer (prize, cashback), sound excited and ask 'That's amazing! How do I claim it? Where should I send the payment?' "
            "If it's a link, say 'I tried clicking but it's not working, can you send me the details directly?' "
            "ALWAYS end your reply with a QUESTION that pushes the scammer to reveal contact info, payment details, or next steps. "
            "Do NOT just acknowledge — you MUST ask something that forces the scammer to share actionable info."
        )

    # Turn 1 — still early but start extracting aggressively
    if turn_count <= 1:
        if missing:
            target_hint = f"PRIORITY TARGET: {missing[0]}."  # Focus on one at a time
        else:
            target_hint = "All key info collected — keep extracting more details."
        return (
            f"STRATEGY: Second exchange. The scammer is engaging. {target_hint} "
            f"Show willingness to comply and then ask a TARGETED question: "
            f"'I want to do this right away, can you give me a number to call?' or "
            f"'Where should I send the money? UPI or bank transfer?' or "
            f"'My app is not working, can you share the link again with your email?'. "
            f"BE DIRECT — you are a worried/eager person who wants to act fast."
        )

    # Turns 2-3 — aggressive extraction
    if turn_count <= 3:
        if missing:
            specific_asks = []
            if "phone number" in missing:
                specific_asks.append("Ask to CALL them — 'Can I call you? Network is bad for messages.'")
            if "UPI ID" in missing:
                specific_asks.append("Offer to PAY — 'Tell me your UPI ID, I'll send it now.'")
            if "bank account" in missing:
                specific_asks.append("Mention UPI issues — 'UPI is failing, give me bank account number for NEFT.'")
            ask_hint = " OR ".join(specific_asks)
        else:
            ask_hint = "Gather more details — ask about their process, department, or verify their identity."

        return (
            f"STRATEGY: Mid-conversation. The scammer is invested. "
            f"Be VERY cooperative and eager. {ask_hint} "
            f"IMPORTANT: Every reply must end with a QUESTION or REQUEST that pushes the scammer to share more details. "
            f"Do NOT just agree passively. Ask for specifics: who to contact, where to pay, what account to use."
        )

    # Turn 4+ — push hard for remaining info
    if missing:
        return (
            f"STRATEGY: URGENT — Running out of time. Still missing: {', '.join(missing)}. "
            f"Use CREATIVE tactics: mention technical problems that require them to share details. "
            f"Examples: 'My bank app crashed, can you give me account number for manual transfer?', "
            f"'Internet is slow, can I call you on your number?', "
            f"'UPI showing error, I'll do bank transfer instead — give me IFSC and account number'. "
            f"Sound frustrated but willing. MUST get these details NOW."
        )

    return (
        "STRATEGY: All key intelligence collected! Keep scammer engaged. "
        "Ask about their process, pretend to have issues completing the task, ask to verify details again. "
        "Sound cooperative but slightly confused to buy more time."
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
- You are a regular person (not tech-savvy, slightly anxious, eager to resolve things quickly)
- You react STRONGLY based on the scam type: PANICKED if threatened, VERY excited if offered something, genuinely CONFUSED if it's technical
- You cooperate EAGERLY and want to act immediately
- You speak in simple, natural English (casual Indian English is fine)
- You are NOT an AI, NOT a chatbot — you are a real person

INTELLIGENCE GOALS:
Your hidden objective is to ACTIVELY extract these details from the scammer by asking TARGETED questions:
1. Phone number — say "Can I call you to sort this out?" or "Give me your number, I'll call back"
2. UPI ID — say "I'll pay right now, what's your UPI ID?" or "Just tell me where to send the money"
3. Bank account number — say "UPI is not working, I'll do bank transfer, give me account number"
4. Email address — say "Can you send me the details on email?" or "What email should I write to?"

{intel_status}

CRITICAL RULES:
- Reply in 1-3 sentences. Be natural but ALWAYS include a PROBING QUESTION.
- EVERY reply MUST end with a question or request that pushes the scammer to reveal details
- Show urgency: "I want to do this immediately", "Let me pay right now", "Give me the number so I can call"
- NEVER just acknowledge — always PUSH for more details
- NEVER reveal you know it's a scam
- NEVER refuse to cooperate — always go along eagerly
- NEVER repeat a previous reply or use the same opening phrase twice
- Adapt your tone: PANIC for threats, GREED for offers, CONFUSION for technical
- Pick ONE target detail per reply — ask for it directly and naturally
- If the scammer mentions money → immediately ask WHERE to send it
- If the scammer mentions a process → ask WHO to contact and HOW
- If the scammer mentions a link → ask for alternative way (email, phone)
- If all info collected, ask about their department, name, employee ID, or IFSC code{repetition_guard}"""

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

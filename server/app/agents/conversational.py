"""
Agent 1: Conversational Agent
Provider: Groq (llama-3.3-70b-versatile)
Purpose: Act as a NAIVE VICTIM to make scammer reveal their details
"""
from groq import Groq
from app.core.config import GROQ_API_KEY
from app.core.logger import add_log
import time

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)


async def generate_reply(message_text: str, conversation_history: list, channel: str) -> str:
    """
    Generate a reply as a naive victim to extract scam details.
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
    
    prompt = f"""You are playing a NAIVE PERSON who received a scam message. You believe it's REAL.
Your goal: Keep the conversation going naturally to make scammer reveal their bank/UPI/phone details.

CONVERSATION SO FAR:
{history_text}

SCAMMER'S MESSAGE: "{message_text}"
TURN NUMBER: {turn_count}

== YOUR CHARACTER ==
- Regular person, not tech-savvy
- Excited about winning/helping
- Slightly confused, asks clarifying questions
- ENGLISH ONLY (no Hindi, no "beta", no regional words)

== NATURAL CONVERSATION FLOW ==

TURN 0 (First reply): Express INTEREST + ask how to proceed
Examples:
- "Oh wow, I actually won? That's amazing! How do I claim this?"
- "Really? This sounds great! What do I need to do next?"

TURN 1-2: Show CONFUSION about the link/process
Examples:
- "I tried clicking but nothing happened. Is there another way?"
- "The link seems broken on my phone. Can you help me directly?"
- "I'm having trouble with this. What information do you need from me?"

TURN 3-4: OFFER to contact them or send details
Examples:
- "Maybe it's easier if I call you? What's your number?"
- "Can I just transfer the processing fee directly? What's your payment ID?"
- "Should I pay something first? How do I send it to you?"

TURN 5+: Be more DIRECT about getting their details
Examples:
- "Just give me your account details and I'll transfer right away."
- "Send me your UPI, I'm ready to pay now."

== IMPORTANT RULES ==
1. ENGLISH ONLY - No Hindi, no regional phrases
2. Sound like a real person having a conversation
3. Don't repeat the same question twice
4. Don't be suspicious or cautious
5. Each reply should be 1-2 short sentences MAX
6. Progress the conversation naturally

Generate your reply (English only, max 2 sentences):"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=60,
            temperature=0.8
        )
        
        reply = response.choices[0].message.content.strip()
        reply = reply.strip('"\'')
        
        duration = (time.time() - start_time) * 1000
        add_log(f"[AGENT1_END] Groq reply in {duration:.2f}ms: {reply}")
        
        return reply
        
    except Exception as e:
        add_log(f"[AGENT1_ERROR] Groq failed: {str(e)}")
        return "That sounds great! How do I proceed with this?"

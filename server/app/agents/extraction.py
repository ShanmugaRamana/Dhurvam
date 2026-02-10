"""
Agent 2: Extraction Agent
Provider: Mistral AI (contextual) + Python Regex (fast fallback)
Purpose: Extract structured intelligence from scammer messages with contextual understanding
"""
import re
import json
import asyncio
from typing import Dict, List
from mistralai import Mistral
from app.core.config import MISTRAL_API_KEY
from app.core.logger import add_log

# Initialize Mistral client for contextual extraction
mistral_client = Mistral(api_key=MISTRAL_API_KEY)

# Extraction patterns (regex - fast first pass)
PATTERNS = {
    "bankAccounts": [
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # 16 digit card with separators
        r"\b\d{11,18}\b",  # 11-18 digit account numbers (excludes 10-digit phones)
    ],
    "upiIds": [
        r"[\w\.\-]+@[\w\-]+",  # upi@bank format
    ],
    "phishingLinks": [
        r"https?://[^\s<>\"']+",  # HTTP/HTTPS URLs
        r"bit\.ly/[^\s]+",  # Bit.ly short URLs
        r"tinyurl\.com/[^\s]+",  # TinyURL
        r"goo\.gl/[^\s]+",  # Google short URLs
    ],
    "phoneNumbers": [
        r"\+91[-\s]?\d{10}",  # Indian with +91
        r"\b[6-9]\d{9}\b",  # Indian 10-digit mobile
    ],
    "suspiciousKeywords": [
        r"\b(urgent|immediately|now|hurry|asap)\b",
        r"\b(verify|blocked|suspended|locked)\b",
        r"\b(prize|lottery|won|winner|claim)\b",
        r"\b(legal action|police|arrest|court)\b",
        r"\b(otp|pin|password|cvv)\b",
    ]
}


def extract_with_regex(text: str) -> Dict[str, List[str]]:
    """
    Fast regex-based extraction (first pass).
    Returns all candidate matches without contextual filtering.
    """
    result = {
        "bankAccounts": [],
        "upiIds": [],
        "phishingLinks": [],
        "phoneNumbers": [],
        "suspiciousKeywords": []
    }
    
    text_lower = text.lower()
    
    # First pass: Extract phone numbers
    for pattern in PATTERNS["phoneNumbers"]:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            clean_match = re.sub(r'[-\s]', '', match)
            if clean_match not in result["phoneNumbers"]:
                result["phoneNumbers"].append(match.strip())
    
    # Get all phone number digits for filtering
    phone_number_digits = [re.sub(r'[-\s+]', '', p) for p in result["phoneNumbers"]]
    
    # Second pass: Extract other categories
    for category, patterns in PATTERNS.items():
        if category == "phoneNumbers":
            continue
            
        for pattern in patterns:
            if category == "suspiciousKeywords":
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
            else:
                matches = re.findall(pattern, text, re.IGNORECASE)
            
            for match in matches:
                match_clean = match.strip()
                
                # Special handling for bank accounts: exclude phone numbers
                if category == "bankAccounts":
                    digits_only = re.sub(r'[-\s]', '', match_clean)
                    if len(digits_only) == 10:
                        continue
                    if digits_only in phone_number_digits:
                        continue
                    if len(digits_only) == 10 and digits_only[0] in '6789':
                        continue
                
                if match_clean not in result[category]:
                    result[category].append(match_clean)
    
    return result


async def extract_with_mistral_context(
    text: str, 
    regex_candidates: Dict[str, List[str]], 
    conversation_history: list = None
) -> Dict[str, List[str]]:
    """
    Use Mistral to contextually validate and filter extracted data.
    Distinguishes between scammer's data vs victim's data or examples.
    """
    add_log(f"[AGENT2_MISTRAL] Starting contextual extraction")
    
    # Build conversation context summary
    context_summary = "No prior conversation."
    if conversation_history and len(conversation_history) > 0:
        recent = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
        context_summary = "\n".join([
            f"{msg.get('sender', 'unknown')}: {msg.get('text', '')[:100]}"
            for msg in recent
        ])
    
    # Build candidate list for Mistral to analyze
    candidates = {k: v for k, v in regex_candidates.items() 
                  if k != "suspiciousKeywords" and len(v) > 0}
    
    if not candidates:
        # Only keywords found, no need for contextual analysis
        return regex_candidates
    
    prompt = f"""You are analyzing a scam conversation to extract the SCAMMER'S payment and contact details.

MESSAGE: "{text}"

CONVERSATION CONTEXT:
{context_summary}

REGEX FOUND THESE CANDIDATES:
{json.dumps(candidates, indent=2)}

YOUR TASK: Determine which of these belong to the SCAMMER (data they want money sent to, or their contact info).

RULES:
1. EXTRACT: Account numbers, UPI IDs, phone numbers the scammer wants the VICTIM to send money/transfer to
2. EXTRACT: Payment details the scammer provides as THEIR OWN receiving details
3. EXTRACT: Any number used with "transfer to", "send to", "pay to" — this is the scammer's receiving account
4. IGNORE: Numbers ONLY mentioned as the victim's account with NO transfer request (e.g. "Your account X was hacked" with no payment request)
5. KEY RULE: If the SAME number is mentioned as "your account" BUT ALSO used as a transfer destination (e.g. "transfer Rs.500 to account X"), then EXTRACT it — the scammer is using it to receive money
6. WHEN UNSURE: INCLUDE the data (better to over-extract than miss scammer details)

Return ONLY valid JSON with these exact keys (include items that are the scammer's OR used as transfer destinations):
{{"bankAccounts": [], "upiIds": [], "phoneNumbers": [], "phishingLinks": []}}"""

    try:
        response = mistral_client.chat.complete(
            model="mistral-small-latest",
            messages=[{"content": prompt, "role": "user"}],
            stream=False,
            max_tokens=200
        )
        
        raw = response.choices[0].message.content.strip()
        add_log(f"[AGENT2_MISTRAL] Response: {raw}")
        
        # Parse JSON from response
        # Handle cases where response is wrapped in markdown code blocks
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        
        parsed = json.loads(raw)
        
        # Build final result, keeping suspiciousKeywords from regex
        final_result = {
            "bankAccounts": parsed.get("bankAccounts", []),
            "upiIds": parsed.get("upiIds", []),
            "phishingLinks": parsed.get("phishingLinks", regex_candidates.get("phishingLinks", [])),
            "phoneNumbers": parsed.get("phoneNumbers", []),
            "suspiciousKeywords": regex_candidates.get("suspiciousKeywords", [])
        }
        
        add_log(f"[AGENT2_MISTRAL] Contextual result: {final_result}")
        return final_result
        
    except json.JSONDecodeError as e:
        add_log(f"[AGENT2_MISTRAL_ERROR] JSON parse failed: {str(e)}, falling back to regex")
        return regex_candidates
    except Exception as e:
        add_log(f"[AGENT2_MISTRAL_ERROR] Mistral failed: {str(e)}, falling back to regex")
        return regex_candidates


async def extract_intelligence(text: str, conversation_history: list = None) -> Dict[str, List[str]]:
    """
    Extract scam-related intelligence from message text.
    Uses hybrid approach: fast regex + contextual Mistral validation.
    
    Args:
        text: The scammer's message
        conversation_history: Previous conversation messages for context
    
    Returns:
        Dict with extracted intelligence (same format as before)
    """
    add_log(f"[AGENT2_START] Extracting intelligence from message")
    
    # Step 1: Fast regex scan
    regex_results = extract_with_regex(text)
    
    # Check if we found any actionable data (not just keywords)
    has_actionable = any(
        len(regex_results.get(k, [])) > 0 
        for k in ["bankAccounts", "upiIds", "phoneNumbers", "phishingLinks"]
    )
    
    if not has_actionable:
        # Only keywords found, no need for LLM
        found = {k: v for k, v in regex_results.items() if v}
        if found:
            add_log(f"[AGENT2_END] Regex only (no actionable data): {found}")
        else:
            add_log(f"[AGENT2_END] No intelligence extracted")
        return regex_results
    
    # Step 2: Contextual validation with Mistral
    try:
        result = await asyncio.wait_for(
            extract_with_mistral_context(text, regex_results, conversation_history),
            timeout=3.0  # 3 second timeout
        )
        
        found = {k: v for k, v in result.items() if v}
        if found:
            add_log(f"[AGENT2_END] Contextual extraction: {found}")
        else:
            add_log(f"[AGENT2_END] No intelligence after contextual filtering")
        return result
        
    except asyncio.TimeoutError:
        add_log(f"[AGENT2_TIMEOUT] Mistral timed out, using regex results")
        return regex_results
    except Exception as e:
        add_log(f"[AGENT2_ERROR] Contextual extraction failed: {str(e)}, using regex")
        return regex_results


def merge_intelligence(existing: Dict[str, List[str]], new: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Merge new extracted intelligence into existing.
    
    Args:
        existing: Previously extracted intelligence
        new: Newly extracted intelligence
    
    Returns:
        Merged dictionary
    """
    merged = {}
    for key in existing.keys():
        merged[key] = list(set(existing.get(key, []) + new.get(key, [])))
    return merged

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
    
    prompt = f"""You are analyzing a scam conversation. Extract ONLY the SCAMMER'S details — NOT the victim's.

MESSAGE: "{text}"

CONVERSATION CONTEXT:
{context_summary}

REGEX FOUND THESE CANDIDATES:
{json.dumps(candidates, indent=2)}

CLASSIFICATION RULES:

PHONE NUMBERS:
- EXTRACT: Any phone number the scammer says to "call", "reach", "contact" them at. This is the scammer's number.
- EXTRACT: Any phone number the scammer provides proactively (e.g. "call us at X", "our number is X", "you can reach me at X")
- IGNORE: Phone numbers the scammer claims belong to the victim (e.g. "OTP sent to YOUR number X")

BANK ACCOUNTS:
- EXTRACT: Account numbers where the scammer asks victim to TRANSFER or SEND money TO (e.g. "transfer to account X", "pay to X")
- IGNORE: Account numbers the scammer refers to as the VICTIM'S account (e.g. "your account X is compromised", "verify your account X")
- KEY TEST: Does the scammer want MONEY SENT TO this account? If yes → extract. If scammer is REFERRING TO the victim's existing account → ignore.

UPI IDs:
- EXTRACT: UPI IDs where the scammer asks victim to SEND PAYMENT (e.g. "transfer fee to X@bank", "pay to X@bank")
- EXTRACT: UPI IDs the scammer provides as their own receiving ID
- IGNORE: UPI IDs the scammer asks the victim to share (e.g. "send me YOUR UPI ID")

PHISHING LINKS:
- EXTRACT: All suspicious links/URLs the scammer shares

Return ONLY valid JSON:
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
    Uses hybrid approach: fast regex + contextual Mistral validation + rule-based boost.
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
    except asyncio.TimeoutError:
        add_log(f"[AGENT2_TIMEOUT] Mistral timed out, using regex results")
        result = regex_results
    except Exception as e:
        add_log(f"[AGENT2_ERROR] Contextual extraction failed: {str(e)}, using regex")
        result = regex_results
    
    # Step 3: Rule-based boost — force-extract data from clear "transfer to" patterns
    # This catches cases Mistral misses
    text_lower = text.lower()
    
    # Force-extract bank accounts when "transfer to account" pattern is present
    transfer_patterns = ["transfer to account", "transfer the", "pay to account", "send to account", 
                         "fee to account", "transfer.*to.*account"]
    for pattern in transfer_patterns:
        if re.search(pattern, text_lower):
            # Find any bank account numbers in the original regex results
            for acc in regex_results.get("bankAccounts", []):
                if acc not in result.get("bankAccounts", []):
                    result.setdefault("bankAccounts", []).append(acc)
                    add_log(f"[AGENT2_BOOST] Force-extracted bank account from transfer pattern: {acc}")
            break
    
    # Force-extract UPI when "transfer/pay to UPI" pattern is present
    upi_transfer = ["transfer.*to.*upi", "fee to upi", "pay.*to.*upi", "transfer.*to.*@", "fee to.*@", "pay to.*@"]
    for pattern in upi_transfer:
        if re.search(pattern, text_lower):
            for upi in regex_results.get("upiIds", []):
                if upi not in result.get("upiIds", []):
                    result.setdefault("upiIds", []).append(upi)
                    add_log(f"[AGENT2_BOOST] Force-extracted UPI from transfer pattern: {upi}")
            break
    
    # Force-extract phone when "call us/me at" pattern is present
    call_patterns = ["call.*at", "reach.*at", "contact.*at", "call me", "call us", "our.*line.*at"]
    for pattern in call_patterns:
        if re.search(pattern, text_lower):
            for phone in regex_results.get("phoneNumbers", []):
                if phone not in result.get("phoneNumbers", []):
                    result.setdefault("phoneNumbers", []).append(phone)
                    add_log(f"[AGENT2_BOOST] Force-extracted phone from call pattern: {phone}")
            break
    
    found = {k: v for k, v in result.items() if v}
    if found:
        add_log(f"[AGENT2_END] Final extraction: {found}")
    else:
        add_log(f"[AGENT2_END] No intelligence after filtering")
    return result


def _normalize_phones(phones: List[str]) -> List[str]:
    """Deduplicate phone numbers by keeping the longest variant of each unique number."""
    if not phones:
        return phones
    
    # Group by raw digits (strip all non-digit characters)
    digit_map = {}
    for phone in phones:
        digits = re.sub(r'\D', '', phone)
        # Remove leading country code (91) for comparison
        key = digits[-10:] if len(digits) >= 10 else digits
        # Keep the longest (most complete) variant
        if key not in digit_map or len(phone) > len(digit_map[key]):
            digit_map[key] = phone
    
    return list(digit_map.values())


def merge_intelligence(existing: Dict[str, List[str]], new: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Merge new extracted intelligence into existing, with phone deduplication."""
    merged = {}
    for key in existing.keys():
        combined = list(set(existing.get(key, []) + new.get(key, [])))
        # Normalize phone numbers to prevent duplicates
        if key == "phoneNumbers":
            combined = _normalize_phones(combined)
        merged[key] = combined
    return merged

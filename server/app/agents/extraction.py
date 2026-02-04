"""
Agent 2: Extraction Agent
Provider: Python Regex (No LLM)
Purpose: Extract structured intelligence from scammer messages
"""
import re
from typing import Dict, List
from app.core.logger import add_log


# Extraction patterns
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


def extract_intelligence(text: str) -> Dict[str, List[str]]:
    """
    Extract scam-related intelligence from message text.
    
    Args:
        text: The scammer's message
    
    Returns:
        Dict with extracted intelligence
    """
    add_log(f"[AGENT2_START] Extracting intelligence from message")
    
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
            # Clean up phone number
            clean_match = re.sub(r'[-\s]', '', match)
            if clean_match not in result["phoneNumbers"]:
                result["phoneNumbers"].append(match.strip())
    
    # Get all phone number digits for filtering
    phone_number_digits = [re.sub(r'[-\s+]', '', p) for p in result["phoneNumbers"]]
    
    # Second pass: Extract other categories
    for category, patterns in PATTERNS.items():
        if category == "phoneNumbers":
            continue  # Already processed
            
        for pattern in patterns:
            if category == "suspiciousKeywords":
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
            else:
                matches = re.findall(pattern, text, re.IGNORECASE)
            
            # Add unique matches
            for match in matches:
                match_clean = match.strip()
                
                # Special handling for bank accounts: exclude phone numbers
                if category == "bankAccounts":
                    # Remove separators and check if it's a phone number
                    digits_only = re.sub(r'[-\s]', '', match_clean)
                    
                    # Skip if it's exactly 10 digits (phone number)
                    if len(digits_only) == 10:
                        continue
                    
                    # Skip if it matches a detected phone number
                    if digits_only in phone_number_digits:
                        continue
                    
                    # Skip if starts with 6-9 and is 10 digits (Indian mobile pattern)
                    if len(digits_only) == 10 and digits_only[0] in '6789':
                        continue
                
                if match_clean not in result[category]:
                    result[category].append(match_clean)
    
    # Log what was found
    found = {k: v for k, v in result.items() if v}
    if found:
        add_log(f"[AGENT2_END] Extracted: {found}")
    else:
        add_log(f"[AGENT2_END] No intelligence extracted")
    
    return result


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

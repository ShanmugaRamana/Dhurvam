import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
PASSWORD = os.getenv("PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
MONGODB_URL = os.getenv("MONGODB_URL")
GUVI_ENDPOINT = os.getenv("GUVI_ENDPOINT")

# Multi-key support: comma-separated lists
GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
MISTRAL_API_KEYS = [k.strip() for k in os.getenv("MISTRAL_API_KEYS", "").split(",") if k.strip()]
OPENROUTER_API_KEYS = [k.strip() for k in os.getenv("OPENROUTER_API_KEYS", "").split(",") if k.strip()]

# Backward-compatible single-key aliases (first key from each list)
GROQ_API_KEY = GROQ_API_KEYS[0] if GROQ_API_KEYS else None
MISTRAL_API_KEY = MISTRAL_API_KEYS[0] if MISTRAL_API_KEYS else None
OPENROUTER_API_KEY = OPENROUTER_API_KEYS[0] if OPENROUTER_API_KEYS else None

if not API_KEY:
    raise ValueError("API_KEY not found in environment variables")
if not PASSWORD:
    raise ValueError("PASSWORD not found in environment variables")
if not ADMIN_EMAIL:
    raise ValueError("ADMIN_EMAIL not found in environment variables")
if not MONGODB_URL:
    raise ValueError("MONGODB_URL not found in environment variables")
if not GROQ_API_KEYS:
    raise ValueError("GROQ_API_KEYS not found in environment variables")
if not MISTRAL_API_KEYS:
    raise ValueError("MISTRAL_API_KEYS not found in environment variables")
if not OPENROUTER_API_KEYS:
    raise ValueError("OPENROUTER_API_KEYS not found in environment variables")
if not GUVI_ENDPOINT:
    raise ValueError("GUVI_ENDPOINT not found in environment variables")

# Initialize failover client managers
from app.core.api_clients import init_clients
init_clients(GROQ_API_KEYS, MISTRAL_API_KEYS, OPENROUTER_API_KEYS)

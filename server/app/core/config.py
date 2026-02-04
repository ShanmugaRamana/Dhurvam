import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
PASSWORD = os.getenv("PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
MONGODB_URL = os.getenv("MONGODB_URL")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GUVI_ENDPOINT = os.getenv("GUVI_ENDPOINT")

if not API_KEY:
    raise ValueError("API_KEY not found in environment variables")
if not PASSWORD:
    raise ValueError("PASSWORD not found in environment variables")
if not ADMIN_EMAIL:
    raise ValueError("ADMIN_EMAIL not found in environment variables")
if not MONGODB_URL:
    raise ValueError("MONGODB_URL not found in environment variables")
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY not found in environment variables")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in environment variables")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables")
if not GUVI_ENDPOINT:
    raise ValueError("GUVI_ENDPOINT not found in environment variables")

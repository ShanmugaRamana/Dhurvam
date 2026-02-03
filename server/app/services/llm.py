import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Create the model
generation_config = {
  "temperature": 0,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 1024, # Increased from 10 to avoid MAX_TOKENS cutoffs
  "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
  model_name="gemini-3-flash-preview",
  generation_config=generation_config,
)

def analyze_message(text: str) -> str:
    """
    Analyzes the message text to determine if it's from a scammer or a human.
    Returns 'scammer' or 'human'.
    """
    try:
        prompt = f"You are a scam detection expert. Analyze the following message and determine if it is sent by a potential scammer or a normal human. Output ONLY one word: 'scammer' or 'human'.\n\nMessage: {text}"
        
        response = model.generate_content(prompt)
        
        # Check if response has parts
        if not response.parts:
             print(f"Gemini response has no parts. Finish Reason: {response.candidates[0].finish_reason}")
             print(f"Safety Ratings: {response.candidates[0].safety_ratings}")
             return "human"

        content = response.text.strip().lower()
        
        if "scammer" in content:
            return "scammer"
        return "human"
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return "human"

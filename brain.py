import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# 1. Configuration
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("⚠️ CRITICAL ERROR: GEMINI_API_KEY is missing in .env")

genai.configure(api_key=api_key)

# 2. Model Setup (STRICT RULE: GEMINI 3)
MODEL_NAME = 'gemini-3-flash-preview'

try:
    model = genai.GenerativeModel(MODEL_NAME)
except Exception as e:
    print(f"❌ Error loading model '{MODEL_NAME}': {e}")
    # Fallback to standard if Gemini 3 is not active on your key yet
    print("⚠️ Falling back to 'gemini-1.5-flash' temporarily so the server doesn't crash.")
    model = genai.GenerativeModel('gemini-1.5-flash')

def analyze_code_vs_docs(diff_text, readme_text, filename):
    print(f"🧠 Asking {MODEL_NAME} about {filename}...")
    
    prompt = f"""
    ROLE: You are DocuGuard, a strict code reviewer.
    
    GOAL: Compare the code changes in '{filename}' against the README.
    
    === CODE DIFF ===
    {diff_text}
    
    === CURRENT README ===
    {readme_text}
    
    TASK:
    1. Identify if any NEW environment variables, API endpoints, or setup steps were added in the code.
    2. Check if the README already explains them.
    3. If they are MISSING from the README, write the exact Markdown text needed to fix it.
    
    OUTPUT FORMAT:
    - If no docs are needed, return exactly: "OK"
    - If docs are missing, return a short explanation followed by a code block with the suggested text.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini API Error: {str(e)}"

# Quick connection test
if __name__ == "__main__":
    try:
        print(f"Testing {MODEL_NAME}...")
        res = model.generate_content("Hello")
        print(f"✅ Success! Response: {res.text}")
    except Exception as e:
        print(f"❌ Failed: {e}")
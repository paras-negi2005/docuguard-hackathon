import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. Load env variables
load_dotenv()

# 2. Setup Gemini with your key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("⚠️ CRITICAL ERROR: GEMINI_API_KEY is missing in .env")
    print("   Please create the .env file and paste your key starting with 'AIza...'")

genai.configure(api_key=api_key)

# 3. Load the Gemini model

# OPTION A: Speed (Recommended for checking docs)
MODEL_NAME = 'gemini-3-flash-preview'

# OPTION B: Reasoning (Use if Flash misses logic errors)
# MODEL_NAME = 'gemini-3-pro-preview' 

try:
    model = genai.GenerativeModel(MODEL_NAME)
except Exception as e:
    print(f"❌ Error loading model '{MODEL_NAME}'.")
    print("   Please check Google AI Studio for the exact model string name.")
    print("   It might be 'gemini-3.0-flash-001' or similar.")
    raise e

def analyze_code_vs_docs(diff_text, readme_text, filename):
    print(f"🧠 asking {MODEL_NAME} about {filename}...")
    
    prompt = f"""
    ROLE: You are a strict Code Reviewer Bot using Gemini 3.
    
    GOAL: Compare the CODE DIFF against the DOCUMENTATION.
    
    FILE: {filename}
    
    === CODE CHANGES ===
    {diff_text}
    
    === CURRENT README ===
    {readme_text}
    
    TASK:
    1. Identify any NEW environment variables, API endpoints, or dependencies.
    2. Check if the README mentions them.
    3. If MISSING, you MUST write the fix using GitHub Suggestion Markdown.
    
    OUTPUT FORMAT:
    If everything is OK, return: "OK"
    
    If edits are needed, return a block like this:
    ```suggestion
    (Put the full corrected line of the README here)
    ```
    (Then add a short explanation below it).
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini API Error: {str(e)}"

# Quick Local Test
if __name__ == "__main__":
    print(f"Testing connection to {MODEL_NAME}...")
    try:
        # Simple "Hello World" to verify API Key and Model Name work
        test_response = model.generate_content("Say 'Gemini 3 is online'")
        print(f"✅ SUCCESS: {test_response.text}")
    except Exception as e:
        print(f"❌ CONNECTION FAILED: {e}")
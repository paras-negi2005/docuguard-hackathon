import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("⚠️ Warning: GEMINI_API_KEY missing.")

genai.configure(api_key=api_key)

# Use gemini-3-flash-preview
MODEL_NAME = 'gemini-3-flash-preview' 

# MODEL_NAME = 'gemini-3-pro'  # Uncomment to use Gemini Pro if available

try:
    model = genai.GenerativeModel(MODEL_NAME)
except:
    model = genai.GenerativeModel('gemini-pro')

def analyze_code_vs_docs(diff_text, readme_text, filename):
    print(f"🧠 Asking Gemini about {filename}...")

    prompt = f"""
    ROLE: You are DocuGuard, a strict code reviewer.
    GOAL: Compare the code changes in '{filename}' against the README.

    === CODE CHANGES ===
    {diff_text}

    === CURRENT README ===
    {readme_text}

    TASK:
    1. Identify NEW environment variables, API endpoints, or setup steps in the code.
    2. Check if the README already explains them.
    3. If MISSING, write the exact Markdown text needed to fix it.

    OUTPUT FORMAT:
    - If everything is documented or no docs needed, return exactly: "OK"
    - If docs are missing, return a short explanation followed by a markdown block with the fix.
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini Error: {str(e)}"
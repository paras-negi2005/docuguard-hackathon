import os
import google.generativeai as genai

def analyze_code_vs_docs(code_diff, readme_content, filename):
    """
    Sends the code diff and documentation to Gemini AI for review.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY not found."

    genai.configure(api_key=api_key)
    
    # Use the flash model for speed and cost efficiency
    model = genai.GenerativeModel('gemini-3-flash-preview')
    # model = genai.GenerativeModel('gemini-3-pro-preview')  # Uncomment for more thorough analysis

    prompt = f"""
    You represent a strict QA system called "DocuGuard".
    
    CONTEXT:
    The developer changed code in '{filename}'.
    
    DOCUMENTATION (README.md):
    {readme_content}
    
    CODE CHANGES (Diff):
    {code_diff}
    
    TASK:
    1. Check if the code changes contradict or violate anything in the documentation.
    2. Check if the code adds new features that are NOT documented yet.
    
    RULES:
    - If everything is consistent, ONLY respond with "OK".
    - If there is a mismatch or missing docs, write a short, friendly comment explaining what needs to be updated.
    - Be concise.
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI Error: {str(e)}"
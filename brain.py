import os
import google.generativeai as genai

def generate_new_readme(diff, current_readme):
    """
    Generates the fully updated README content based on code changes.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3-flash-preview')

    prompt = f"""
    You are an expert technical writer.
    
    Task: Update the following README to reflect the code changes provided.
    
    --- CODE CHANGES ---
    {diff[:5000]}
    
    --- OLD README ---
    {current_readme[:5000]}
    
    --- INSTRUCTIONS ---
    1. Output ONLY the raw markdown of the new, updated README.
    2. Do not add explanations, conversational text, or ```markdown``` blocks.
    3. Keep the existing structure/style, just update the relevant sections (params, endpoints, features).
    """

    try:
        response = model.generate_content(prompt)
        # Clean up if AI adds markdown fences by mistake
        content = response.text.replace("```markdown", "").replace("```", "").strip()
        return content
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return None
import os
import base64
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from ghapi.all import GhApi

# Import the brain function
from brain import analyze_code_vs_docs

# Load environment variables
load_dotenv()

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "DocuGuard is Alive!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. Parse Data
    payload = request.json
    event = request.headers.get('X-GitHub-Event')

    # 2. Filter: Only listen to Pull Request events
    if event == 'pull_request' and payload['action'] in ['opened', 'synchronize', 'reopened']:
        
        try:
            # --- AUTHENTICATION START ---
            
            # Load the Private Key
            # Check if we are on Render (Env Var) or Local (File)
            private_key = os.getenv("PRIVATE_KEY_CONTENT") 
            if not private_key:
                # Fallback for local testing
                with open(os.getenv("PRIVATE_KEY_PATH", "private-key.pem"), 'r') as f:
                    private_key = f.read()

            app_id = os.getenv("APP_ID")
            installation_id = payload['installation']['id']

            # Authenticate as the App (JWT)
            auth_api = GhApi(app_id=app_id, private_key=private_key, token=None)

            # 🛠️ THE FIX IS HERE 🛠️
            # The guide used a deleted function. This is the correct new way:
            token = auth_api.apps.create_installation_access_token(installation_id).token

            # Re-initialize API with the actual Token (to do things)
            repo_api = GhApi(token=token)
            
            # --- AUTHENTICATION END ---

            # 3. Get PR Details
            pr_number = payload['pull_request']['number']
            repo_owner = payload['repository']['owner']['login']
            repo_name = payload['repository']['name']

            print(f"🚀 Processing PR #{pr_number} in {repo_name}...")

            # 4. Get the Diff (Code Changes)
            files = repo_api.pulls.list_files(repo_owner, repo_name, pr_number)
            
            for file in files:
                filename = file.filename
                
                # Only analyze code files, ignore images/configs
                if filename.endswith(('.py', '.js', '.ts', '.go', '.java', '.cpp')):
                    
                    print(f"🔎 Analyzing {filename}...")
                    diff_text = file.patch if hasattr(file, 'patch') else "New File"

                    # 5. Get the README (Simple fetch)
                    try:
                        readme_obj = repo_api.repos.get_content(repo_owner, repo_name, "README.md")
                        readme_content = base64.b64decode(readme_obj.content).decode('utf-8')
                    except:
                        print("⚠️ No README found, assuming empty.")
                        readme_content = ""

                    # 6. ASK GEMINI (The Brain)
                    ai_comment = analyze_code_vs_docs(diff_text, readme_content, filename)

                    # 7. Post Comment if unsafe
                    if ai_comment.strip() != "OK":
                        body = f"### 🤖 DocuGuard Alert\n{ai_comment}"
                        repo_api.issues.create_comment(repo_owner, repo_name, pr_number, body=body)
                        print(f"✅ Comment posted on {filename}")
                    else:
                        print(f"✨ {filename} is safe.")

            return jsonify({"status": "success"}), 200

        except Exception as e:
            print(f"❌ Error processing PR: {e}")
            # Printing the full traceback helps debugging
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    # Run on port 10000 for Render, or default 3000
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
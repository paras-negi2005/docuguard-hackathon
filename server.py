import os
import base64
import hmac
import hashlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from ghapi.all import GhApi
from brain import analyze_code_vs_docs
from utils import find_nearest_readme

load_dotenv()
app = Flask(__name__)

# Config
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
APP_ID = os.getenv("APP_ID")

def verify_signature(payload_body, header_signature):
    """Verifies that the request actually came from GitHub."""
    if not WEBHOOK_SECRET:
        return True 
    if not header_signature:
        return False
    sha_name, signature = header_signature.split('=')
    if sha_name != 'sha256':
        return False
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. Security Check
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        return jsonify({"msg": "Invalid Signature"}), 401

    payload = request.json
    event = request.headers.get('X-GitHub-Event')

    # 2. Filter Events
    if event == 'pull_request' and payload['action'] in ['opened', 'synchronize']:
        try:
            # --- AUTHENTICATION (The Fixed Part) ---
            # Try to get key from Env Var (Render) first, then File (Local)
            private_key = os.getenv("PRIVATE_KEY_CONTENT")
            if not private_key:
                path = os.getenv("PRIVATE_KEY_PATH", "private-key.pem")
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        private_key = f.read()
            
            if not private_key:
                print("❌ Error: Private Key not found!")
                return jsonify({"error": "No Private Key"}), 500

            installation_id = payload['installation']['id']
            
            # Log in as App
            app_api = GhApi(app_id=APP_ID, private_key=private_key)
            
            # Create Token (The CORRECT Command)
            token = app_api.apps.create_installation_access_token(installation_id).token
            
            # Log in as Installation (to post comments)
            repo_api = GhApi(token=token)
            # ---------------------------------------

            pr_number = payload['pull_request']['number']
            repo_full_name = payload['repository']['full_name']
            repo_owner, repo_name = repo_full_name.split('/')

            print(f"🚀 Processing PR #{pr_number} in {repo_name}...")

            # 3. Get Changed Files
            files = repo_api.pulls.list_files(repo_owner, repo_name, pr_number)
            
            # 4. Mock a file list for utils (simplification for hackathon)
            repo_files = [f.filename for f in files] + ["README.md"]

            for file in files:
                filename = file.filename
                # Only check code files
                if filename.endswith(('.py', '.js', '.ts', '.go', '.java')):
                    diff_text = file.patch if hasattr(file, 'patch') else ""
                    
                    # 5. Get README
                    try:
                        # Find the correct README using utils
                        readme_path = find_nearest_readme(filename, repo_files)
                        readme_obj = repo_api.repos.get_content(repo_owner, repo_name, readme_path)
                        readme_text = base64.b64decode(readme_obj.content).decode('utf-8')
                    except:
                        readme_text = ""

                    # 6. Ask Gemini
                    ai_suggestion = analyze_code_vs_docs(diff_text, readme_text, filename)

                    # 7. Post Comment if needed
                    if ai_suggestion.strip().upper() != "OK":
                        print(f"✍️ Posting comment on {filename}...")
                        body = f"### 🛡️ DocuGuard Review\n{ai_suggestion}"
                        repo_api.issues.create_comment(repo_owner, repo_name, pr_number, body=body)

            return jsonify({"status": "success"}), 200

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc() # Print full error to logs
            return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
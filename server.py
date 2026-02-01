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

# Load config
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
APP_ID = os.getenv("APP_ID")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH")

def verify_signature(payload_body, header_signature):
    """Verifies that the request came from GitHub."""
    if not WEBHOOK_SECRET:
        return True # Skip if no secret set (not recommended for production)
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

    # 2. Handle Pull Request Events
    if event == 'pull_request' and payload['action'] in ['opened', 'synchronize']:
        try:
            pr_number = payload['pull_request']['number']
            repo_full_name = payload['repository']['full_name']
            repo_owner, repo_name = repo_full_name.split('/')
            installation_id = payload['installation']['id']
            
            print(f"🚀 Processing PR #{pr_number} in {repo_name}...")

            # 3. Authenticate
            with open(PRIVATE_KEY_PATH, 'r') as f:
                private_key = f.read()
            
            # Use GhApi to get a token
            api = GhApi(app_id=APP_ID, private_key=private_key)
            token = api.get_access_token(installation_id).token
            repo_api = GhApi(token=token)

            # 4. Get Files & README
            files = repo_api.pulls.list_files(repo_owner, repo_name, pr_number)
            
            try:
                readme_obj = repo_api.repos.get_content(repo_owner, repo_name, "README.md")
                readme_text = base64.b64decode(readme_obj.content).decode('utf-8')
            except:
                readme_text = "No README.md found."

            # 5. Analyze Code
            for file in files:
                filename = file.filename
                # Only check code files
                if filename.endswith(('.py', '.js', '.ts', '.java', '.cpp')):
                    diff = file.get('patch', '')
                    if not diff: continue
                    
                    # Call Gemini
                    suggestion = analyze_code_vs_docs(diff, readme_text, filename)
                    
                    # 6. Post Comment
                    if "OK" not in suggestion.upper():
                        print(f"   ✍️ Posting comment on {filename}...")
                        body = f"## 🛡️ DocuGuard Review\nI noticed missing documentation in `{filename}`:\n\n{suggestion}"
                        repo_api.issues.create_comment(
                            repo_owner, repo_name, pr_number, body=body
                        )

            return jsonify({"status": "processed"}), 200

        except Exception as e:
            print(f"❌ Error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    # Running on Port 3000 as requested
    app.run(port=3000)
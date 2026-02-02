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

# --- CONFIG ---
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
# We don't need to load APP_ID from env anymore because we are hardcoding it below.

def verify_signature(payload_body, header_signature):
    if not WEBHOOK_SECRET: return True
    if not header_signature: return False
    sha_name, signature = header_signature.split('=')
    if sha_name != 'sha256': return False
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

@app.route('/webhook', methods=['POST'])
def webhook():
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        return jsonify({"msg": "Invalid Signature"}), 401

    payload = request.json
    event = request.headers.get('X-GitHub-Event')

    if event == 'pull_request' and payload['action'] in ['opened', 'synchronize']:
        try:
            # 1. Get Private Key (with sanitization)
            path = os.getenv("PRIVATE_KEY_PATH", "private-key.pem")
            
            if os.path.exists(path):
                with open(path, 'r') as f:
                    # .strip() removes the invisible 'newline' characters that break Windows keys
                    private_key = f.read().strip()
            else:
                print(f"❌ Error: Key file not found at {path}")
                return jsonify({"error": "Key missing"}), 500

            installation_id = payload['installation']['id']
            
            # 2. Authenticate (HARDCODED ID + SANITIZED KEY)
            # We hardcode 2767721 to guarantee it is an Integer, eliminating the 401 cause.
            app_api = GhApi(app_id=2767721, private_key=private_key)
            
            # Create the token
            token = app_api.apps.create_installation_access_token(installation_id).token
            
            # Login as the Installation
            repo_api = GhApi(token=token)

            # 3. Process PR
            pr_number = payload['pull_request']['number']
            repo_full_name = payload['repository']['full_name']
            repo_owner, repo_name = repo_full_name.split('/')
            
            print(f"🚀 Processing PR #{pr_number} in {repo_name}...")

            files = repo_api.pulls.list_files(repo_owner, repo_name, pr_number)
            repo_files = [f.filename for f in files] + ["README.md"]

            for file in files:
                # Only check code files
                if file.filename.endswith(('.py', '.js', '.ts', '.go', '.java', '.cpp')):
                    diff = file.patch if hasattr(file, 'patch') else ""
                    
                    # Find closest README
                    readme_path = find_nearest_readme(file.filename, repo_files)
                    
                    try:
                        readme_obj = repo_api.repos.get_content(repo_owner, repo_name, readme_path)
                        readme_text = base64.b64decode(readme_obj.content).decode('utf-8')
                    except:
                        readme_text = ""

                    # Ask the Brain
                    suggestion = analyze_code_vs_docs(diff, readme_text, file.filename)
                    
                    # Post comment if needed
                    if suggestion.strip().upper() != "OK":
                        body = f"### 🛡️ DocuGuard Review\n{suggestion}"
                        repo_api.issues.create_comment(repo_owner, repo_name, pr_number, body=body)
                        print(f"✅ Comment posted on {file.filename}")
                    else:
                        print(f"✨ {file.filename} looks good.")

            return jsonify({"status": "success"}), 200

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))
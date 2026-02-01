import os
import base64
import hmac
import hashlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from ghapi.all import GhApi
from brain import analyze_code_vs_docs

load_dotenv()
app = Flask(__name__)

# --- CONFIG ---
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
APP_ID = os.getenv("APP_ID")

# Try to get key from Environment (Render), otherwise from file (Local)
PRIVATE_KEY_CONTENT = os.getenv("PRIVATE_KEY")
if not PRIVATE_KEY_CONTENT:
    path = os.getenv("PRIVATE_KEY_PATH")
    if path and os.path.exists(path):
        with open(path, 'r') as f:
            PRIVATE_KEY_CONTENT = f.read()

# --- HELPER FUNCTIONS ---
def verify_signature(payload_body, header_signature):
    if not WEBHOOK_SECRET: return True
    if not header_signature: return False
    sha_name, signature = header_signature.split('=')
    if sha_name != 'sha256': return False
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

def find_nearest_readme(api, file_path):
    """Finds a README in the same folder or the root folder."""
    # 1. Check the file's own directory
    directory = os.path.dirname(file_path)
    try:
        contents = api.repos.get_content(path=directory)
        if not isinstance(contents, list): contents = [contents]
        for file in contents:
            if file.name.lower() == "readme.md":
                return file
    except:
        pass # Directory might not exist or be empty
        
    # 2. Fallback: Check the Root Directory
    try:
        contents = api.repos.get_content(path="")
        if not isinstance(contents, list): contents = [contents]
        for file in contents:
            if file.name.lower() == "readme.md":
                return file
    except:
        pass
        
    return None

# --- WEBHOOK ROUTE ---
@app.route('/webhook', methods=['POST'])
def webhook():
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        return jsonify({"msg": "Invalid Signature"}), 401

    payload = request.json
    event = request.headers.get('X-GitHub-Event')

    if event == 'pull_request' and payload['action'] in ['opened', 'synchronize']:
        try:
            if not PRIVATE_KEY_CONTENT:
                return jsonify({"error": "No Private Key found"}), 500

            # 1. Setup GitHub API
            installation_id = payload['installation']['id']
            api = GhApi(app_id=APP_ID, private_key=PRIVATE_KEY_CONTENT)
            token = api.get_access_token(installation_id).token
            repo_api = GhApi(token=token, owner=payload['repository']['owner']['login'], repo=payload['repository']['name'])

            # 2. Get the Changed Files
            pr_number = payload['pull_request']['number']
            files = repo_api.pulls.list_files(pr_number)

            for file in files:
                filename = file.filename
                # Only check Python files (skip deletions)
                if filename.endswith('.py') and file.status != 'removed':
                    
                    # A. Get the Code
                    file_content = repo_api.repos.get_content(path=filename)
                    code_text = base64.b64decode(file_content.content).decode('utf-8')

                    # B. Find the Documentation
                    readme_file = find_nearest_readme(repo_api, filename)
                    
                    if readme_file:
                        readme_content = base64.b64decode(readme_file.content).decode('utf-8')
                        
                        # C. Ask AI to Compare them
                        analysis = analyze_code_vs_docs(code_text, readme_content, filename)
                        
                        # D. Post Comment if there are issues
                        if analysis["issues_found"]:
                            comment_body = f"## ⚠️ DocuGuard Alert\n\nI noticed a mismatch in `{filename}`:\n\n{analysis['explanation']}\n\n**Suggested Fix:**\n```markdown\n{analysis['suggested_fix']}\n```"
                            repo_api.issues.create_comment(issue_number=pr_number, body=comment_body)
                            print(f"✅ Commented on {filename}")
                        else:
                            print(f"✨ {filename} matches the docs.")
                    else:
                        print(f"⚠️ No README found for {filename}")

            return jsonify({"status": "processed"}), 200

        except Exception as e:
            print(f"❌ Error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=port)
import os
import base64
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from ghapi.all import GhApi

# Import your AI Brain
from brain import analyze_code_vs_docs
from utils import find_nearest_readme

load_dotenv()

app = Flask(__name__)

# Security: Load App ID and Key
APP_ID = os.getenv("APP_ID")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH")

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.json
    event = request.headers.get('X-GitHub-Event')
    
    # Check if a PR was Opened or Updated
    if event == 'pull_request' and payload['action'] in ['opened', 'synchronize']:
        try:
            process_pull_request(payload)
        except Exception as e:
            print(f"❌ Error processing PR: {e}")
            # Print traceback for easier debugging in Render logs
            import traceback
            traceback.print_exc()
            
    return jsonify({"status": "received"}), 200

def process_pull_request(payload):
    # 1. Setup GitHub API Connection
    installation_id = payload['installation']['id']
    pr_number = payload['pull_request']['number']
    repo_owner = payload['repository']['owner']['login']
    repo_name = payload['repository']['name']

    print(f"🚀 Processing PR #{pr_number} in {repo_name}...")

    # Read the Private Key
    try:
        with open(PRIVATE_KEY_PATH, 'r') as f:
            private_key = f.read()
    except FileNotFoundError:
        print(f"⚠️ Error: Could not find private key at {PRIVATE_KEY_PATH}")
        return

    # Authenticate as the App
    auth_api = GhApi(app_id=APP_ID, private_key=private_key, token=None)
    # FIX: Use the correct method to get the token
    token = auth_api.apps.create_installation_access_token(installation_id).token
    api = GhApi(token=token)

    # 2. Get Changed Files
    files = api.pulls.list_files(repo_owner, repo_name, pr_number)
    
    # Build a fake list of "All Files"
    simulated_repo_files = [f.filename for f in files] + ["README.md"]

    for file in files:
        filename = file.filename
        
        # Skip non-code files
        if not filename.endswith(('.py', '.js', '.ts', '.go', '.java')):
            continue

        print(f"🔎 Analyzing file: {filename}")

        # 3. Find the Doc
        readme_path = find_nearest_readme(filename, simulated_repo_files)
        
        # 4. Get Content (Diff + Readme)
        diff_text = file.patch if hasattr(file, 'patch') else "New File Created"
        
        try:
            readme_obj = api.repos.get_content(repo_owner, repo_name, readme_path)
            readme_content = base64.b64decode(readme_obj.content).decode('utf-8')
        except:
            print(f"   ⚠️ README not found at {readme_path}")
            continue

        # 5. CALL YOUR BRAIN
        ai_comment = analyze_code_vs_docs(diff_text, readme_content, filename)

        # 6. Post Comment if AI has something to say
        if ai_comment.strip() != "OK":
            # Add a clear header to the comment
            comment_body = f"### 🤖 DocuGuard Alert\n{ai_comment}"
            api.issues.create_comment(repo_owner, repo_name, pr_number, body=comment_body)
            print("   ✅ Comment posted to GitHub!")
        else:
            print("   ✨ AI said code is OK.")

if __name__ == '__main__':
    app.run(port=3000)
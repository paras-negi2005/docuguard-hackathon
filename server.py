import os
import base64
import hmac
import hashlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from ghapi.all import GhApi
from brain import generate_new_readme  # Import the new function
from utils import find_nearest_readme

load_dotenv()
app = Flask(__name__)

# --- CONFIG ---
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
APP_ID = os.getenv("APP_ID")

def get_private_key():
    key = os.getenv("PRIVATE_KEY")
    if not key: return None
    return key.replace('\\n', '\n').strip()

def verify_signature(payload_body, header_signature):
    if not WEBHOOK_SECRET: return True
    if not header_signature: return False
    sha_name, signature = header_signature.split('=')
    if sha_name != 'sha256': return False
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

def get_github_client(installation_id):
    private_key = get_private_key()
    app_api = GhApi(app_id=int(APP_ID), private_key=private_key)
    token = app_api.apps.create_installation_access_token(installation_id).token
    return GhApi(token=token)

@app.route('/webhook', methods=['POST'])
def webhook():
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        return jsonify({"msg": "Invalid Signature"}), 401

    payload = request.json
    event = request.headers.get('X-GitHub-Event')

    # ---------------------------------------------------------
    # SCENARIO 1: PR OPENED (The Detection)
    # ---------------------------------------------------------
    if event == 'pull_request' and payload['action'] in ['opened', 'synchronize']:
        repo_api = get_github_client(payload['installation']['id'])
        pr_number = payload['pull_request']['number']
        repo_owner = payload['repository']['owner']['login']
        repo_name = payload['repository']['name']

        # Check files
        files = repo_api.pulls.list_files(repo_owner, repo_name, pr_number)
        file_names = [f.filename for f in files]
        
        # Did they forget the README?
        if "README.md" not in file_names:
            # Simple heuristic: If code changed, but README didn't, ask the user.
            has_code_changes = any(f.endswith(('.py', '.js', '.ts')) for f in file_names)
            
            if has_code_changes:
                msg = (
                    "### ⚠️ DocuGuard Notice\n"
                    "I noticed you updated the code, but the **README.md** was not touched.\n\n"
                    "**Would you like me to update it for you?**\n"
                    "Reply with ` /fix-docs ` to this comment, and I will apply the changes automatically."
                )
                repo_api.issues.create_comment(repo_owner, repo_name, pr_number, body=msg)
                print(f"✅ Posted reminder on PR #{pr_number}")

    # ---------------------------------------------------------
    # SCENARIO 2: USER REPLIES (The Action)
    # ---------------------------------------------------------
    elif event == 'issue_comment' and payload['action'] == 'created':
        # Check if the comment is "/fix-docs"
        comment_body = payload['comment']['body'].strip()
        if "/fix-docs" in comment_body:
            print("🚀 Received /fix-docs command!")
            
            repo_api = get_github_client(payload['installation']['id'])
            pr_number = payload['issue']['number']
            repo_owner = payload['repository']['owner']['login']
            repo_name = payload['repository']['name']

            # 1. Acknowledge command
            reaction = repo_api.reactions.create_for_issue_comment(
                repo_owner, repo_name, payload['comment']['id'], content="+1"
            )

            # 2. Fetch PR Data to get the diffs
            # Note: Webhook doesn't give diffs, we must fetch them
            files = repo_api.pulls.list_files(repo_owner, repo_name, pr_number)
            full_diff = ""
            for f in files:
                if f.filename.endswith(('.py', '.js', '.ts')):
                    full_diff += f"--- {f.filename} ---\n{f.patch}\n\n"

            # 3. Fetch Current README
            try:
                readme_obj = repo_api.repos.get_content(repo_owner, repo_name, "README.md")
                current_text = base64.b64decode(readme_obj.content).decode('utf-8')
                sha = readme_obj.sha # Needed to update the file
            except:
                print("❌ README not found")
                return jsonify({"error": "No README found"}), 404

            # 4. Generate New Content
            new_text = generate_new_readme(full_diff, current_text)
            
            if new_text:
                # 5. COMMIT THE CHANGE DIRECTLY
                # We need the branch name to commit to
                pr_info = repo_api.pulls.get(repo_owner, repo_name, pr_number)
                branch_name = pr_info.head.ref

                repo_api.repos.create_or_update_file_contents(
                    owner=repo_owner,
                    repo=repo_name,
                    path="README.md",
                    message="docs: Auto-update README via DocuGuard",
                    content=base64.b64encode(new_text.encode()).decode(),
                    sha=sha,
                    branch=branch_name
                )
                
                # 6. Notify success
                repo_api.issues.create_comment(
                    repo_owner, repo_name, pr_number, 
                    body="✅ **Done!** I have updated `README.md` and pushed the commit to this branch."
                )

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))
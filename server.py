import os
import base64
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from ghapi.all import GhApi

# Import the brain your friend built
from brain import analyze_code_vs_docs

load_dotenv()
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.json
    event = request.headers.get('X-GitHub-Event')

    # We only care about Pull Requests being opened or updated
    if event == 'pull_request' and payload['action'] in ['opened', 'synchronize']:
        pr_number = payload['pull_request']['number']
        repo_full_name = payload['repository']['full_name']
        repo_owner, repo_name = repo_full_name.split('/')
        installation_id = payload['installation']['id']

        # 1. Authenticate as the GitHub App
        private_key = open(os.getenv("PRIVATE_KEY_PATH")).read()
        api = GhApi(app_id=os.getenv("APP_ID"), private_key=private_key)
        
        # 2. Get a temporary token for this specific repo
        token = api.get_access_token(installation_id).token
        repo_api = GhApi(token=token)

        # 3. Get the list of changed files in the PR
        files = repo_api.pulls.list_files(repo_owner, repo_name, pr_number)

        # 4. Fetch the README content to compare against
        try:
            readme = repo_api.repos.get_content(repo_owner, repo_name, "README.md")
            readme_text = base64.b64decode(readme.content).decode('utf-8')
        except:
            readme_text = "No README.md found."

        # 5. Analyze each code file
        for file in files:
            filename = file.filename
            if filename.endswith(('.py', '.js', '.ts')):
                diff_text = file.get('patch', '') # The actual code changes
                
                # CALL THE BRAIN!
                ai_suggestion = analyze_code_vs_docs(diff_text, readme_text, filename)

                # 6. If Gemini says something is wrong, post a comment
                if ai_suggestion.strip().upper() != "OK":
                    repo_api.issues.create_comment(
                        repo_owner, repo_name, pr_number, 
                        body=f"🔍 **DocuGuard Analysis for `{filename}`**:\n\n{ai_suggestion}"
                    )

        return jsonify({"status": "analyzed"}), 200

    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    app.run(port=3000)
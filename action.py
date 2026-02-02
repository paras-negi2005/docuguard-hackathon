import os
import sys
import json
import base64
from ghapi.all import GhApi
from brain import analyze_code_vs_docs
from utils import find_nearest_readme

def run_review():
    print("🚀 DocuGuard Action Starting...")

    # 1. Get the Automatic Token (No App ID/Key needed!)
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ Error: No GITHUB_TOKEN found. This script must run inside GitHub Actions.")
        sys.exit(1)

    # 2. Connect to GitHub API
    api = GhApi(token=token)
    
    # 3. Read the Event Payload to find out which PR triggered this
    event_path = os.getenv('GITHUB_EVENT_PATH')
    if not event_path:
        print("❌ Error: No Event Path found.")
        sys.exit(1)
        
    with open(event_path, 'r') as f:
        payload = json.load(f)

    # 4. Extract Repo and PR Info
    try:
        # Handle 'pull_request' event
        if 'pull_request' in payload:
            pr_number = payload['pull_request']['number']
            repo_full_name = payload['repository']['full_name']
        else:
            print("⚠️ This event is not a Pull Request. Exiting.")
            sys.exit(0)
            
        repo_owner, repo_name = repo_full_name.split('/')
    except Exception as e:
        print(f"❌ Error parsing event: {e}")
        sys.exit(1)
    
    print(f"📋 Reviewing PR #{pr_number} in {repo_name}...")

    # 5. Get List of Changed Files
    try:
        files = api.pulls.list_files(repo_owner, repo_name, pr_number)
        # Create a list of all files to help find readmes
        repo_files = [f.filename for f in files] + ["README.md"]
    except Exception as e:
        print(f"❌ Error fetching files: {e}")
        sys.exit(1)

    # 6. Analyze Each File
    for file in files:
        # Only check code files (Python, JS, TS, Go, Java, C++)
        if file.filename.endswith(('.py', '.js', '.ts', '.go', '.java', '.cpp')):
            print(f"🔍 Analyzing {file.filename}...")
            
            # Get the Diff (Changes)
            diff = file.patch if hasattr(file, 'patch') else ""
            if not diff:
                print("   (No content changes, skipping)")
                continue
            
            # Find the nearest README
            readme_path = find_nearest_readme(file.filename, repo_files)
            
            # Fetch README content
            try:
                readme_obj = api.repos.get_content(repo_owner, repo_name, readme_path)
                readme_text = base64.b64decode(readme_obj.content).decode('utf-8')
            except:
                print(f"   (Could not find/read {readme_path}, assuming empty docs)")
                readme_text = ""

            # Ask Gemini
            suggestion = analyze_code_vs_docs(diff, readme_text, file.filename)
            
            # Post Comment if not OK
            if suggestion.strip().upper() != "OK":
                body = f"### 🛡️ DocuGuard Review\n{suggestion}"
                try:
                    api.issues.create_comment(repo_owner, repo_name, pr_number, body=body)
                    print(f"✅ Posted comment on {file.filename}")
                except Exception as e:
                    print(f"❌ Failed to post comment: {e}")
            else:
                print(f"✨ {file.filename} is consistent with docs.")

if __name__ == "__main__":
    run_review()
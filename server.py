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

# --- ⚠️ CRITICAL CREDENTIALS SECTION ⚠️ ---
# We are hardcoding the ID and KEY here to eliminate all environment/file errors.
APP_ID_INT = 2767721

# 1. DELETE the text below between the triple quotes (""")
# 2. PASTE your EXACT Private Key content (including BEGIN/END lines)
PRIVATE_KEY_STR = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAnG64zG3HlGMQHrmJZg0czw2570zwS1t+G0EVjRN4SiJaXMVq
n1tLyuOOVX7EfPV79g53Tf663hnqg2MGM+KzhlMjJNXPBg6hSJKgGb9ewzR14+qb
lfXA9zgGdkrBgvTq3BY0swYuL95v5FURHlRVOqYXVmCWPcUi/u5g5UEwEnZXKbLM
lP/Edj5APMSNZvPsVFF557KZmYWyl7p8dPWMG2vC9l7pe1thTIPufEuRzYfAW8pA
c2Y7DOeLzyaSpeziSOxRLaVxzxqRtHF3YZvcwBuMikNopaX7vX9q/BLchm2c5Duf
31cfHu2TOa/SosSev4Ig0YA9jjXi/tyBACBQ2wIDAQABAoIBAGvieJSUSYZu45kt
ADNfa7TolIkTGM3/5XLKaiCHgvgtxQAiLqyEfDsKwQj5im1bqAhEZcdmnF28pd3D
F24FNSa4g45N3p8gy96PMNdRAfvCXGO5U2ASwug8vUgrulWkr6zlq6aj5oqg764b
dNjj9HukPIgXyMYFBWOn5y90y8COxN/sM4aae2HF8qjElkyW5Z0bbNpildWn5vns
dMcIlts3qBjvgRTvYfZntwIInNMEvZkMOxKiYB5/zhLasdKAQovYZ3RB2EX6cNG0
wX5HfzKMXgN8IjzsQcWQ/Bmf3RYl2cmuc40Va7giVgZE5gh3AQIDgP5qfd61MAUO
cdfPX3ECgYEAzb+fRgapYMoHDKH26YNrA2PIwzay3zYWF0HTCy/UpyLxg4yZrwII
BWjqVGOZ02dV+lcn+9Ayb6LFGm5xo5A+50wA9FDRLREVm99sOW9mp6yXNQYd8GcG
M8VetB1Mc4FpGyjuPNEczHJD27lyLwLshxOwTZsOJed1uRaTTxwqJC0CgYEAwqOg
nj/eak83kq0OjfZsS140iTX4K81mIg9HEaR6s/HEu5YtnYAQKBOHw4YuUtHkPduG
l+GwueKkPDB6uidflc5myNkbM3fZoFysxny4YF8Qv5kdEOHvqWs3H3Ukaq9LN1Iz
Sq407SIlCCQd5YXIs2bf+rDkaYuo2MCuSqbixicCgYEArT/LDTs0ywSzVObZNB5u
MQeIGSFpE13G0kSiQkw/Y5GgDqaJDn3GZU/H6dGIySO9mTRkvby9i5VjJXOUiyc+
YKN2NkQLL0iwinVi+yYcKdrB5GtHMJR/+34Z1c7J/oUdDTq1CU8IUftxuoZ4aK+s
nb1tepuzGSXC0lz5I+dScO0CgYBgUTaXeQWoWAEpLUhJigs3FKwsxi9EBcWnzyWd
Hma2C0sOhReXnBriqh+B6zGbPFCVJ8AoAsBAjF43hsoEup07dcM5Wu5x/roL+DBr
nKZk0kZoee1/QD8n+G1zvLVDsfEntB67sw9v1Xi72ZuNzDFwTdVCqiyt6jWo5Via
ipEn+wKBgQCkbBI+v4y9+ui92mKAG3yTTS77iV0McGKXaXna4WSOSC+uPS56ZfNQ
1qgdDd4FO1/kEYLLZymqVjm1e7059B5KPjVniE+Mx9TlL3p+OLrx6UQ/oFktgAQm
+33PgTDD3IYizk2W8hk9drfasR0v/CkOmPoUI/lbH4g0m+h5DFXsmA==
-----END RSA PRIVATE KEY-----"""
# ------------------------------------------

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

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
            installation_id = payload['installation']['id']
            
            # Authenticate using the DIRECT string (No file lookups)
            print(f"🔐 Authenticating App ID {APP_ID_INT}...")
            app_api = GhApi(app_id=APP_ID_INT, private_key=PRIVATE_KEY_STR)
            
            token = app_api.apps.create_installation_access_token(installation_id).token
            print("✅ Authentication Successful! Token received.")
            
            repo_api = GhApi(token=token)

            # Process PR
            pr_number = payload['pull_request']['number']
            repo_full_name = payload['repository']['full_name']
            repo_owner, repo_name = repo_full_name.split('/')
            
            print(f"🚀 Processing PR #{pr_number} in {repo_name}...")

            files = repo_api.pulls.list_files(repo_owner, repo_name, pr_number)
            repo_files = [f.filename for f in files] + ["README.md"]

            for file in files:
                if file.filename.endswith(('.py', '.js', '.ts', '.go', '.java', '.cpp')):
                    diff = file.patch if hasattr(file, 'patch') else ""
                    readme_path = find_nearest_readme(file.filename, repo_files)
                    
                    try:
                        readme_obj = repo_api.repos.get_content(repo_owner, repo_name, readme_path)
                        readme_text = base64.b64decode(readme_obj.content).decode('utf-8')
                    except:
                        readme_text = ""

                    suggestion = analyze_code_vs_docs(diff, readme_text, file.filename)
                    
                    if suggestion.strip().upper() != "OK":
                        body = f"### 🛡️ DocuGuard Review\n{suggestion}"
                        repo_api.issues.create_comment(repo_owner, repo_name, pr_number, body=body)
                        print(f"✅ Comment posted on {file.filename}")

            return jsonify({"status": "success"}), 200

        except Exception as e:
            print(f"❌ CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))
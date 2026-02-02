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

# --- 🔐 CREDENTIALS SECTION 🔐 ---
APP_ID_INT = 2767721  # Checked: This is the correct ID (ends in 721)

# PASTE YOUR *NEW* KEY BELOW (Between the triple quotes)
# It's okay if it looks messy or indented; the code below will fix it.
PRIVATE_KEY_STR = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAwjqv0fTBK6rgK2QPDS+zvu3bIeGwvVbtaC12qPADMXYx7YQI
EHsqWznQV4WvN84BOvetew8Xb7ro3zBUyHgYSxtq5Q2B8Mf5bVEZgAJ/RVYjc7C2
en14SCGVLL12GdVOUDYAOO5PIlvckch4LuJC94jEO9b9LgrgfaEB40WFBNSDE4W8
IaWZXCwaIFYLs3FXD91W8Y/QT86ooCdCHnSq3IwC1Z3EbDiQt8rzMuhJwyKtRtM4
+DPptkC9kI81Tj0iliHldn9JfdYMu+wz6GYQIvSwhsT1i0n/j0R1LzcdrpWw6rBt
hEMgDwWt6xa8uVOV4uLvDT4huqKcT7ZfgEnPeQIDAQABAoIBAQCFVcBpQ7pwfceS
QghLJxof0i2CnuqzsD8eK0ewRcQLanZv9RmMJuE26wNpce6NQrB5iJnhRsTyAL/o
p8csL7WNqe7B+3nej4ldUDVPOWehc7a2rvM2N3ghHFzJ7+5pYZN3YPraGk7c6W8L
7TEEDnOmdo8v/TClMPZXh/ZBzPG6E+2+wXsAXOomV78FLmqZwFP6vOPOMsV3Knt6
/+reuXveqXxSzR+/wrwCv56L2wUP1yNacV8arJPdO1FLBpYpIWT85SmuQKwjuMQM
JTQ6aaZWMGy4F/Nvp3YYgsiEcovmDIMhU8UacxjvIx9WYLuXhd1NbCo+vVJDHkXm
h/+XKwI5AoGBAPTo2B18VSDgf7/layoqKHtSPaYtk3Cw/D9FS8Lmeb2AjsjrV8Lt
R1DJ3wygJzs6E4kgIRVDdcY/ImN3vYSaQLunie92OK3w0VnK2cvYrQ7qixv45Jpo
Oe/gLa2RzpsdSuFdkcOUON9ZTB/qyBWwJPpaB98J+OP6joQLnrVJCo/LAoGBAMsG
UpE3x4RhNvIJxOf6AFJiv0GhdGdNbiW5hbCvahwBohk3xshCX6bA3nQCvSMA8Csp
72QPt/13sTY5ablx24YRHt8HDnR3+JSNE9DGF8DAeJXzdu53+jw6A8e4v8LIgdPs
FVRbQ5/ZD3NXCUFrbmxyarH+srPjA1NnpSTpYS1LAoGAadLKv0LgDcqzqJlbCucY
guDwXoPG96Sh+jzZFag85lNMXyjBzSp17ESuKmhxSzg3BMNrSCLUGwtgspYkv81f
NzaXdW8h4pbx/tiV72z6qj1SSo3rSYTLtAir9BnSqlen6WVi/J1pTajqKchrGGP6
Nmr8h7VpZCj5t7jFpROgiq0CgYBFKn9Al+cx80ibxrY9bY9kgd20h0O32co3se+Y
1PnqVqgZvUXMfchGcBiZH0G+RhiMK/oxdaVyBa/q0D5zfhWSpAyHYMkM5r5aJYHl
s0buVOP/+fS/o0It+HnHNeqmela4kwplNb5hG7rGyZUOo4H4EjbFMwdAf4tng7zg
SV3g5wKBgFCYlScsUcg0xellcfnT4B4ryqgNxZIyv+Bo+qnhkdcdEL4GvWmhDCoq
SIO17g96GnwvSk9VY0Q5TTLUnpNal0niY7Ut6OydjSzLpFQkW9qurS1K1SUMJAlN
WT5WTdsQDYDMM7NIhvA3r3GGpg+WgM9IKkTKyIRMV20mTxplRjj0
-----END RSA PRIVATE KEY-----"""
# ---------------------------------

def clean_pem_key(key_str):
    """
    Repairs the key by removing indentation and extra spaces 
    caused by copy-pasting into VS Code.
    """
    if not key_str: return None
    # Split into lines, trim whitespace from each line, and rejoin
    lines = key_str.strip().split('\n')
    clean_lines = [line.strip() for line in lines if line.strip()]
    return '\n'.join(clean_lines)

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
            
            # --- AUTHENTICATION FIX ---
            final_key = clean_pem_key(PRIVATE_KEY_STR)
            print(f"🔐 Authenticating App ID {APP_ID_INT}...")
            
            app_api = GhApi(app_id=APP_ID_INT, private_key=final_key)
            token = app_api.apps.create_installation_access_token(installation_id).token
            print("✅ Authentication Successful! Token received.")
            
            repo_api = GhApi(token=token)
            
            # --- LOGIC START ---
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
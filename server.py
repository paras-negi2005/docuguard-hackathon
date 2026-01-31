import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.json
    event = request.headers.get('X-GitHub-Event')

    # Filter for PR opened or updated events
    if event == 'pull_request' and payload['action'] in ['opened', 'synchronize']:
        pr_number = payload['pull_request']['number']
        repo_name = payload['repository']['full_name']
        print(f"Detected PR #{pr_number} in {repo_name}")
        return jsonify({"status": "processing"}), 200

    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    app.run(port=3000)
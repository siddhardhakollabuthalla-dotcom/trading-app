import os
import json
import requests
import yfinance as yf
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "ledger_secret_key_antigravity_fullstack"

# Firebase Config
FIREBASE_API_KEY = "AIzaSyBAkFU5JFcQL4jM2AsYkBnp9P_YeO0dwo8"
PROJECT_ID = "trading-app-66077"
AUTH_SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
AUTH_SIGNIN_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
FIRESTORE_BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/users"

# Helper function to get/save data from Firestore
def get_user_firestore_data(local_id):
    try:
        url = f"{FIRESTORE_BASE}/{local_id}?key={FIREBASE_API_KEY}"
        res = requests.get(url).json()
        if "fields" in res:
            fields = res["fields"]
            bal_field = fields.get("balance", {})
            balance = float(bal_field.get("doubleValue", bal_field.get("integerValue", 0.0)))
            investments = json.loads(fields.get("investments", {}).get("stringValue", "[]"))
            journal = json.loads(fields.get("journal", {}).get("stringValue", "[]"))
            challenges = json.loads(fields.get("challenges", {}).get("stringValue", "[]"))
            return {"balance": balance, "investments": investments, "journal": journal, "challenges": challenges}
        else:
            print("Firestore document not found or empty:", res)
    except Exception as e:
        print("Firestore GET error:", e)
    return {"balance": 0.0, "investments": [], "journal": [], "challenges": []}

STORAGE_BUCKET = "trading-app-66077.firebasestorage.app"
STORAGE_UPLOAD_BASE = f"https://firebasestorage.googleapis.com/v1/b/{STORAGE_BUCKET}/o"

def save_user_firestore_data(local_id, id_token, email, data):
    payload = {
        "fields": {
            "email": {"stringValue": email or ""},
            "balance": {"doubleValue": float(data.get("balance", 0.0))},
            "investments": {"stringValue": json.dumps(data.get("investments", []))},
            "journal": {"stringValue": json.dumps(data.get("journal", []))},
            "challenges": {"stringValue": json.dumps(data.get("challenges", []))}
        }
    }
    try:
        # Use updateMask to force field updates / creation in Firestore REST API
        update_mask = "updateMask.fieldPaths=email&updateMask.fieldPaths=balance&updateMask.fieldPaths=investments&updateMask.fieldPaths=journal&updateMask.fieldPaths=challenges"
        url = f"{FIRESTORE_BASE}/{local_id}?key={FIREBASE_API_KEY}&{update_mask}"
        headers = {"Authorization": f"Bearer {id_token}"} if id_token else {}
        res = requests.patch(url, json=payload, headers=headers)
        if res.status_code != 200:
            print(f"Firestore PATCH warning ({res.status_code}):", res.text)
            res2 = requests.patch(url, json=payload)
            if res2.status_code != 200:
                print("Firestore unauth PATCH warning:", res2.text)
        else:
            print(f"Successfully saved user data to Firestore for UID: {local_id}")
    except Exception as e:
        print("Firestore PATCH error:", e)

# Routes
@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', user=session['user'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        is_signup = request.form.get('action') == 'signup'
        url = AUTH_SIGNUP_URL if is_signup else AUTH_SIGNIN_URL
        payload = {"email": email, "password": password, "returnSecureToken": True}
        try:
            res = requests.post(url, json=payload).json()
            if "error" in res:
                raw_err = res["error"]["message"]
                if "CONFIGURATION_NOT_FOUND" in raw_err or "OPERATION_NOT_ALLOWED" in raw_err:
                    error = "Firebase Email/Password Sign-In is not enabled. Please enable 'Email/Password' in your Firebase Console (Authentication -> Sign-in method)."
                else:
                    error = raw_err
            else:
                session['user'] = {
                    "email": email,
                    "localId": res["localId"],
                    "idToken": res["idToken"]
                }
                return redirect(url_for('index'))
        except Exception as e:
            error = str(e)
    return render_template('login.html', error=error)

@app.route('/api/google_login', methods=['POST'])
def google_login():
    try:
        data = request.get_json()
        id_token = data.get('idToken')
        email = data.get('email')
        local_id = data.get('localId')

        if not local_id or not email:
            return jsonify({"error": "Invalid Google Auth payload"}), 400

        session['user'] = {
            "email": email,
            "localId": local_id,
            "idToken": id_token
        }
        return jsonify({"status": "success", "redirect": url_for('index')})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/user_data', methods=['GET'])
def user_data():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user = session['user']
    data = get_user_firestore_data(user['localId'])
    return jsonify(data)

@app.route('/api/save_user_data', methods=['POST'])
def save_data():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user = session['user']
    payload = request.get_json()
    save_user_firestore_data(user['localId'], user['idToken'], user['email'], payload)
    return jsonify({"status": "success"})

@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user = session['user']
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    filename = file.filename
    object_path = f"users/{user['localId']}/{filename}"
    upload_url = f"{STORAGE_UPLOAD_BASE}?name={object_path}&key={FIREBASE_API_KEY}"
    headers = {"Authorization": f"Bearer {user['idToken']}", "Content-Type": file.content_type}
    res = requests.post(upload_url, data=file.read(), headers=headers)
    if res.status_code == 200:
        download_url = f"https://firebasestorage.googleapis.com/v1/b/{STORAGE_BUCKET}/o/{object_path.replace('/', '%2F')}?alt=media"
        return jsonify({"url": download_url, "path": object_path})
    return jsonify({"error": "Upload failed", "details": res.text}), 500

@app.route('/api/stock_quotes', methods=['POST'])
def stock_quotes():
    symbols = request.get_json().get('symbols', [])
    results = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            fast = ticker.fast_info
            price = fast.last_price or 0.0
            prev = fast.previous_close or 0.0
            change = price - prev if prev else 0.0
            pct = (change / prev * 100) if prev else 0.0
            results[sym] = {"price": price, "change": change, "pct": pct}
        except Exception:
            results[sym] = {"price": 0.0, "change": 0.0, "pct": 0.0}
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

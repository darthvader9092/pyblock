from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from database import * 
from blockchain import mine_block, validate_chain, calculate_difficulty 
from smart_contracts import validate_contract, create_contract 
import json
import secrets
import os 

# --- 1. Define the Flask app instance FIRST ---
app = Flask(__name__)

# --- 2. Set the secret key for the app ---
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16)) 

# --- 3. Initialize the database (depends on app context for some operations, or just creates tables) ---
init_db()

# In-memory lists (these don't strictly depend on 'app' being defined yet, but good to place after init)
pending_txs = [] 
smart_contracts = [] 

# --- 4. Define the initial transaction processing function ---
# This function is defined here, but not called yet.
def process_initial_pending_transactions():
    """
    Checks the database for any transactions marked 'pending' (e.g., from initial user generation).
    If found, it mines them into a new block by the 'system' user to establish initial balances.
    This runs once when the Flask app starts.
    """
    global pending_txs 

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT seller, buyer, energy, price FROM transactions WHERE status='pending'")
    db_pending_txs = [{"seller": r[0], "buyer": r[1], "energy": r[2], "price": r[3]} for r in c.fetchall()]
    conn.close()

    if db_pending_txs:
        print(f"Found {len(db_pending_txs)} initial pending transactions. Mining them into a block...")
        
        miner = "system" 
        blocks = get_all_blocks() 
        difficulty = calculate_difficulty(len(blocks)) 
        
        block = mine_block(db_pending_txs, miner, len(blocks), 
                           blocks[-1]["hash"] if blocks else "0", difficulty)
        
        add_block(block["index"], block["hash"], miner, json.dumps(block["data"]), difficulty)
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        for tx in db_pending_txs:
            c.execute("UPDATE transactions SET status='confirmed' WHERE seller=? AND buyer=? AND energy=? AND price=? AND status='pending'",
                      (tx["seller"], tx["buyer"], tx["energy"], tx["price"]))
        conn.commit()
        conn.close()
        
        print(f"Initial block {block['index']} mined by {miner} containing {len(db_pending_txs)} transactions.")
        
        pending_txs.clear() 
    else:
        print("No initial pending transactions to process.")

# --- 5. Call the initial transaction processing function within the app context ---
# This ensures that if any database operations within it require Flask's app context, they have it.
with app.app_context():
    process_initial_pending_transactions()

# --- 6. Define all your routes (these use 'app' as a decorator) ---
@app.route("/")
def home():
    # ... (rest of your home route code) ...
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"])

# ... (all other routes like login, register, admin, add_tx, mine, etc.) ...

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json
        user = authenticate_user(data["username"], data["password"])
        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]
            return jsonify({"status": "success", "role": user["role"]})
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401
    return render_template("login.html")

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    if create_user(data["username"], data["password"], data.get("role", "user")):
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "User exists"}), 400

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin")
def admin():
    if "user" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))
    return render_template("admin.html")

@app.route("/add_tx", methods=["POST"])
def add_tx():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    tx = request.json
    tx["initiator"] = session["user"]
    
    contract_valid, msg = validate_contract(tx, get_user_balance(tx["seller"]))
    if not contract_valid:
        return jsonify({"error": msg}), 400
    
    add_transaction(tx["seller"], tx["buyer"], tx["energy"], tx["price"], "pending")
    pending_txs.append(tx) 
    
    return jsonify({"status": "added", "message": msg})

@app.route("/create_contract", methods=["POST"])
def create_contract_route():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    contract = request.json
    contract["creator"] = session["user"]
    contract_id = create_contract(contract)
    smart_contracts.append(contract)
    
    return jsonify({"status": "created", "id": contract_id})

@app.route("/mine", methods=["POST"])
def mine():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    miner = session["user"]
    blocks = get_all_blocks()
    difficulty = calculate_difficulty(len(blocks))
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT seller, buyer, energy, price FROM transactions WHERE status='pending'")
    txs_to_mine = [{"seller": r[0], "buyer": r[1], "energy": r[2], "price": r[3]} for r in c.fetchall()]
    conn.close()

    if not txs_to_mine:
        return jsonify({"error": "No pending transactions to mine."}), 400

    block = mine_block(txs_to_mine, miner, len(blocks), 
                       blocks[-1]["hash"] if blocks else "0", difficulty)
    
    add_block(block["index"], block["hash"], miner, json.dumps(block["data"]), difficulty)
    
    reward = 10 * difficulty
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for tx in txs_to_mine:
        c.execute("UPDATE transactions SET status='confirmed' WHERE seller=? AND buyer=? AND energy=? AND price=? AND status='pending'",
                  (tx["seller"], tx["buyer"], tx["energy"], tx["price"]))
    conn.commit()
    conn.close()
    
    pending_txs.clear() 

    all_blocks_after_mine = get_all_blocks()
    is_valid, validation_msg = validate_chain(all_blocks_after_mine)
    if not is_valid:
        print(f"CRITICAL ERROR: Chain became invalid after mining! {validation_msg}")
        return jsonify({"message": f"Block mined! Reward: ${reward}. WARNING: Chain invalid after mine: {validation_msg}", "block": block, "chain_valid": False}), 500

    return jsonify({"message": f"Block mined! Reward: ${reward}", "block": block, "chain_valid": True})

@app.route("/balance/<user>")
def balance(user):
    return jsonify(get_user_balance(user))

@app.route("/my_balance")
def my_balance():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify(get_user_balance(session["user"]))

@app.route("/chain")
def get_chain():
    return jsonify(get_all_blocks())

@app.route("/transactions")
def transactions():
    return jsonify(get_all_transactions())

@app.route("/pending")
def pending():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT seller, buyer, energy, price, timestamp FROM transactions WHERE status='pending' ORDER BY timestamp DESC")
    db_pending_txs = [{"seller": r[0], "buyer": r[1], "energy": r[2], "price": r[3], "timestamp": r[4]} for r in c.fetchall()]
    conn.close()
    return jsonify(db_pending_txs)

@app.route("/contracts")
def contracts():
    return jsonify(smart_contracts)

@app.route("/users")
def users():
    if "user" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify(get_all_users())

@app.route("/stats")
def stats():
    blocks = get_all_blocks()
    txs = get_all_transactions()
    users_list = get_all_users()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'")
    pending_tx_count = c.fetchone()[0]
    conn.close()

    return jsonify({
        "total_blocks": len(blocks),
        "total_transactions": len(txs),
        "total_users": len(users_list),
        "pending_txs": pending_tx_count,
        "avg_difficulty": sum(b.get("difficulty", 2) for b in blocks) / len(blocks) if blocks else 0,
        "total_contracts": len(smart_contracts)
    })

@app.route("/validate_blockchain_server", methods=["GET"])
def validate_blockchain_server():
    if "user" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    
    blocks = get_all_blocks()
    is_valid, message = validate_chain(blocks)
    
    return jsonify({"is_valid": is_valid, "message": message})

# --- 7. Main execution block (for local development) ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=False)

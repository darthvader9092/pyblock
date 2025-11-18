from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from database import * # Imports init_db, create_user, authenticate_user, get_all_users, add_block, get_all_blocks, add_transaction, get_all_transactions, get_user_balance
from blockchain import mine_block, validate_chain, calculate_difficulty # Imports mine_block, validate_chain, calculate_difficulty
from smart_contracts import validate_contract, create_contract # Imports validate_contract, create_contract
import json
import secrets
import os # Import os for environment variables
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))


app = Flask(__name__)
# Use an environment variable for the secret key, or generate a random one if not set
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16)) 

# Initialize the database and ensure core tables/users exist
init_db()

# In-memory lists for pending transactions and smart contracts (for quick access)
# Note: Pending transactions are primarily managed in the DB for persistence
pending_txs = [] 
smart_contracts = [] # In a real system, contracts would also be persistent

# --- Function to process initial pending transactions from generate_users.py ---
def process_initial_pending_transactions():
    """
    Checks the database for any transactions marked 'pending' (e.g., from initial user generation).
    If found, it mines them into a new block by the 'system' user to establish initial balances.
    This runs once when the Flask app starts.
    """
    global pending_txs # Refer to the global list, though DB is primary source

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Fetch pending transactions from the database
    c.execute("SELECT seller, buyer, energy, price FROM transactions WHERE status='pending'")
    db_pending_txs = [{"seller": r[0], "buyer": r[1], "energy": r[2], "price": r[3]} for r in c.fetchall()]
    conn.close()

    if db_pending_txs:
        print(f"Found {len(db_pending_txs)} initial pending transactions. Mining them into a block...")
        
        miner = "system" # The system user mines these initial allocation blocks
        blocks = get_all_blocks() # Get current blockchain state
        difficulty = calculate_difficulty(len(blocks)) # Calculate difficulty for the new block
        
        # Mine a new block containing all initial pending transactions
        block = mine_block(db_pending_txs, miner, len(blocks), 
                           blocks[-1]["hash"] if blocks else "0", difficulty)
        
        # Add the newly mined block to the database
        add_block(block["index"], block["hash"], miner, json.dumps(block["data"]), difficulty)
        
        # Update the status of these transactions to 'confirmed' in the database
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        for tx in db_pending_txs:
            c.execute("UPDATE transactions SET status='confirmed' WHERE seller=? AND buyer=? AND energy=? AND price=? AND status='pending'",
                      (tx["seller"], tx["buyer"], tx["energy"], tx["price"]))
        conn.commit()
        conn.close()
        
        print(f"Initial block {block['index']} mined by {miner} containing {len(db_pending_txs)} transactions.")
        
        # Clear the in-memory pending_txs list as they are now confirmed
        pending_txs.clear() 
    else:
        print("No initial pending transactions to process.")

# --- Call this function once at application startup ---
# This ensures initial balances are processed when the server first runs
with app.app_context():
    process_initial_pending_transactions()

# --- Routes ---

@app.route("/")
def home():
    """Renders the main index page, redirects to login if not authenticated."""
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"])

@app.route("/login", methods=["GET", "POST"])
def login():
    """Handles user login."""
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
    """Handles new user registration."""
    data = request.json
    if create_user(data["username"], data["password"], data.get("role", "user")):
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "User exists"}), 400

@app.route("/logout")
def logout():
    """Logs out the current user by clearing the session."""
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin")
def admin():
    """Renders the admin panel, restricted to admin users."""
    if "user" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))
    return render_template("admin.html")

@app.route("/add_tx", methods=["POST"])
def add_tx():
    """Adds a new transaction to the pending pool."""
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    tx = request.json
    tx["initiator"] = session["user"] # Record who initiated the transaction
    
    # Validate the transaction against any active smart contracts
    contract_valid, msg = validate_contract(tx, get_user_balance(tx["seller"]))
    if not contract_valid:
        return jsonify({"error": msg}), 400
    
    # Add the transaction to the database with 'pending' status
    add_transaction(tx["seller"], tx["buyer"], tx["energy"], tx["price"], "pending")
    
    # Also add to in-memory pending_txs for immediate frontend display (non-persistent)
    pending_txs.append(tx) 
    
    return jsonify({"status": "added", "message": msg})

@app.route("/create_contract", methods=["POST"])
def create_contract_route():
    """Creates a new smart contract."""
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    contract = request.json
    contract["creator"] = session["user"]
    contract_id = create_contract(contract) # Store contract in DB (or in-memory for this example)
    smart_contracts.append(contract) # Add to in-memory list
    
    return jsonify({"status": "created", "id": contract_id})

@app.route("/mine", methods=["POST"])
def mine():
    """Mines a new block, including all pending transactions."""
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    miner = session["user"]
    blocks = get_all_blocks() # Get all existing blocks
    difficulty = calculate_difficulty(len(blocks)) # Calculate current mining difficulty
    
    # Fetch pending transactions from the database
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT seller, buyer, energy, price FROM transactions WHERE status='pending'")
    txs_to_mine = [{"seller": r[0], "buyer": r[1], "energy": r[2], "price": r[3]} for r in c.fetchall()]
    conn.close()

    if not txs_to_mine:
        return jsonify({"error": "No pending transactions to mine."}), 400

    # Mine the block
    block = mine_block(txs_to_mine, miner, len(blocks), 
                       blocks[-1]["hash"] if blocks else "0", difficulty)
    
    # Add the newly mined block to the database
    add_block(block["index"], block["hash"], miner, json.dumps(block["data"]), difficulty)
    
    # Calculate mining reward based on difficulty
    reward = 10 * difficulty
    
    # Update status of mined transactions to 'confirmed' in the database
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for tx in txs_to_mine:
        c.execute("UPDATE transactions SET status='confirmed' WHERE seller=? AND buyer=? AND energy=? AND price=? AND status='pending'",
                  (tx["seller"], tx["buyer"], tx["energy"], tx["price"]))
    conn.commit()
    conn.close()
    
    # Clear the in-memory pending_txs list after they've been confirmed
    pending_txs.clear() 

    # --- NEW: Validate chain after mining ---
    all_blocks_after_mine = get_all_blocks()
    is_valid, validation_msg = validate_chain(all_blocks_after_mine)
    if not is_valid:
        print(f"CRITICAL ERROR: Chain became invalid after mining! {validation_msg}")
        # In a real system, this would trigger a rollback, network alert, or more severe action
        return jsonify({"message": f"Block mined! Reward: ${reward}. WARNING: Chain invalid after mine: {validation_msg}", "block": block, "chain_valid": False}), 500

    return jsonify({"message": f"Block mined! Reward: ${reward}", "block": block, "chain_valid": True})

@app.route("/balance/<user>")
def balance(user):
    """Returns the energy and currency balance for a specific user."""
    return jsonify(get_user_balance(user))

@app.route("/my_balance")
def my_balance():
    """Returns the energy and currency balance for the logged-in user."""
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify(get_user_balance(session["user"]))

@app.route("/chain")
def get_chain():
    """Returns the entire blockchain."""
    return jsonify(get_all_blocks())

@app.route("/transactions")
def transactions():
    """Returns a list of all transactions (confirmed and pending)."""
    return jsonify(get_all_transactions())

@app.route("/pending")
def pending():
    """Returns a list of currently pending transactions from the database."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT seller, buyer, energy, price, timestamp FROM transactions WHERE status='pending' ORDER BY timestamp DESC")
    db_pending_txs = [{"seller": r[0], "buyer": r[1], "energy": r[2], "price": r[3], "timestamp": r[4]} for r in c.fetchall()]
    conn.close()
    return jsonify(db_pending_txs)

@app.route("/contracts")
def contracts():
    """Returns a list of active smart contracts."""
    # In a real system, these would be loaded from the DB
    return jsonify(smart_contracts)

@app.route("/users")
def users():
    """Returns a list of all registered users (admin-only)."""
    if "user" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify(get_all_users())

@app.route("/stats")
def stats():
    """Returns various blockchain statistics."""
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

# --- NEW ROUTE FOR SERVER-SIDE CHAIN VALIDATION ---
@app.route("/validate_blockchain_server", methods=["GET"])
def validate_blockchain_server():
    """
    Performs a full blockchain validation on the server and returns the result.
    Restricted to admin users.
    """
    if "user" not in session or session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    
    blocks = get_all_blocks() # Retrieve all blocks from the database
    is_valid, message = validate_chain(blocks) # Call the core validation logic
    
    return jsonify({"is_valid": is_valid, "message": message})

# --- Main execution block ---
if __name__ == "__main__":
    # For production deployment (e.g., Render), use 0.0.0.0 and get port from environment
    # For local development, you can use debug=True for auto-reloading
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=False)

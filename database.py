import sqlite3
import json
import hashlib
import time

DB_NAME = "blockchain.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS blocks
                 (id INTEGER PRIMARY KEY, hash TEXT, miner TEXT, data TEXT, difficulty INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  seller TEXT, buyer TEXT, energy REAL, price REAL, status TEXT, timestamp REAL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE, password_hash TEXT, role TEXT, created_at REAL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS contracts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  contract_type TEXT, params TEXT, creator TEXT, created_at REAL)''')
    
    # Genesis block
    c.execute("SELECT COUNT(*) FROM blocks")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO blocks VALUES (0, 'genesis', 'system', '[]', 1)")
    
    # Default admin user (password: admin123)
    c.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if c.fetchone()[0] == 0:
        pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                  ("admin", pwd_hash, "admin", time.time()))
    
    # Ensure a 'system' user exists for initial allocations (no password needed)
    c.execute("SELECT COUNT(*) FROM users WHERE username='system'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                  ("system", "", "system", time.time())) # Empty password hash for system
    
    conn.commit()
    conn.close()

def create_user(username, password, role="user"):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                  (username, pwd_hash, role, time.time()))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Error creating user {username}: {e}")
        conn.close()
        return False

def authenticate_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT * FROM users WHERE username=? AND password_hash=?", (username, pwd_hash))
    user = c.fetchone()
    conn.close()
    
    if user:
        return {"id": user[0], "username": user[1], "role": user[3]}
    return None

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, role, created_at FROM users")
    rows = c.fetchall()
    conn.close()
    
    return [{"id": r[0], "username": r[1], "role": r[2], "created_at": r[3]} for r in rows]

def add_block(index, hash_val, miner, data, difficulty):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO blocks VALUES (?, ?, ?, ?, ?)", (index, hash_val, miner, data, difficulty))
    conn.commit()
    conn.close()

def get_all_blocks():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM blocks")
    rows = c.fetchall()
    conn.close()
    
    blocks = []
    for row in rows:
        blocks.append({
            "index": row[0],
            "hash": row[1],
            "miner": row[2],
            "data": json.loads(row[3]),
            "difficulty": row[4]
        })
    return blocks

def add_transaction(seller, buyer, energy, price, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO transactions (seller, buyer, energy, price, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (seller, buyer, energy, price, status, time.time()))
    conn.commit()
    conn.close()

def get_all_transactions():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 100")
    rows = c.fetchall()
    conn.close()
    
    return [{"id": r[0], "seller": r[1], "buyer": r[2], "energy": r[3], 
             "price": r[4], "status": r[5], "timestamp": r[6]} for r in rows]

def get_user_balance(user):
    blocks = get_all_blocks()
    energy = currency = 0
    
    for block in blocks:
        if block["miner"] == user:
            currency += 10 * block.get("difficulty", 2)
        
        for tx in block["data"]:
            if tx["seller"] == user:
                energy -= tx["energy"]
                currency += tx["price"]
            if tx["buyer"] == user:
                energy += tx["energy"]
                currency -= tx["price"]
    
    return {"energy": energy, "currency": currency}

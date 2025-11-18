import sqlite3
import hashlib
import time
import random
# Removed 'string' as random strings are no longer used.

DB_NAME = "blockchain.db"

def create_user(username, password, role="user"):
    """
    Creates a new user in the database with a hashed password.
    Returns True on success, False if the username already exists.
    """
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
        # Username already exists (UNIQUE constraint violation)
        if conn:
            conn.close()
        return False
    except Exception as e:
        print(f"Error creating user {username}: {e}")
        if conn:
            conn.close()
        return False

def add_initial_transaction(sender, receiver, energy, price):
    """
    Adds a transaction to the DB with 'pending' status for initial mining.
    Used to initialize user balances (from 'system').
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO transactions (seller, buyer, energy, price, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (sender, receiver, energy, price, "pending", time.time()))
    conn.commit()
    conn.close()

def generate_users(num_users=1000, common_password="1234"):
    """
    Generates a specified number of users with sequential usernames and initial balances.
    The default password is now "1234".
    """
    print(f"Generating {num_users} users with password '{common_password}' and initial balances...")
    
    user_roles = ["consumer", "producer", "prosumer"] 
    
    role_allocations = {
        "consumer": {"energy": random.uniform(0, 10), "currency": random.uniform(500, 1500)},
        "producer": {"energy": random.uniform(500, 1500), "currency": random.uniform(0, 500)},
        "prosumer": {"energy": random.uniform(100, 500), "currency": random.uniform(200, 800)},
        "admin": {"energy": 0, "currency": 0} 
    }

    # Counters for sequential naming (e.g., producer_0001)
    role_counters = {
        "consumer": 0,
        "producer": 0,
        "prosumer": 0,
        "admin": 0
    }

    common_password_hash = hashlib.sha256(common_password.encode()).hexdigest()

    # Determine how many admins to generate (max 5, or 1% of total users)
    num_admins_to_generate = min(num_users // 100, 5) 
    
    # List to track which roles still need users to be created
    roles_remaining = list(user_roles)
    
    for i in range(num_users):
        current_role = random.choice(roles_remaining)
        
        # Admin generation logic: Assign admin role periodically until limit is hit
        if role_counters["admin"] < num_admins_to_generate and i % (num_users // (num_admins_to_generate + 1) if num_admins_to_generate > 0 else num_users + 1) == 0:
            current_role = "admin"
        
        # Increment counter and generate sequential username (4-digit padding)
        role_counters[current_role] += 1
        count = role_counters[current_role]
        username = f"{current_role}_{count:04d}"
        
        
        if create_user(username, common_password, current_role):
            print(f"Created user: {username} (Role: {current_role})")
            
            if current_role != "admin":
                alloc = role_allocations[current_role]
                initial_energy = round(alloc["energy"], 2)
                initial_currency = round(alloc["currency"], 2)
                
                # Add pending transactions from 'system' to the new user
                if initial_currency > 0:
                    # System transfers currency to the user
                    add_initial_transaction("system", username, 0, initial_currency)
                    print(f"  -> Added pending currency tx: system -> {username} (${initial_currency:.2f})")
                if initial_energy > 0:
                    # System transfers energy to the user
                    add_initial_transaction("system", username, initial_energy, 0)
                    print(f"  -> Added pending energy tx: system -> {username} ({initial_energy:.2f} kWh)")
        else:
            print(f"Failed to create user: {username} (might already exist)")
            
    print(f"\nFinished generating {num_users} users and initial pending transactions.")
    print("Next step: Run your Flask application (app.py) to mine these initial transactions into blocks.")

if __name__ == "__main__":
    # --- Database Initialization (Ensures tables and 'system' user exist) ---
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
    
    # Ensure 'system' user exists for initial balance creation
    c.execute("SELECT COUNT(*) FROM users WHERE username='system'")
    if c.fetchone()[0] == 0:
        # 'system' user does not need a password
        c.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                  ("system", "", "system", time.time()))
    conn.commit()
    conn.close()
    # -----------------------------------------------------------------------

    # Call the generator with the requested password
    generate_users(1000, "1234")

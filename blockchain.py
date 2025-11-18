import hashlib
import time
import json

def calculate_difficulty(block_count):
    # Difficulty increases every 5 blocks
    return min(2 + block_count // 5, 6)

def hash_block(block):
    block_copy = {k: v for k, v in block.items() if k != "hash"}
    return hashlib.sha256(json.dumps(block_copy, sort_keys=True).encode()).hexdigest()

def mine_block(data, miner, index, prev_hash, difficulty):
    nonce = 0
    start_time = time.time()
    
    while True:
        block = {
            "index": index,
            "timestamp": time.time(),
            "data": data,
            "prev": prev_hash,
            "nonce": nonce,
            "miner": miner,
            "difficulty": difficulty
        }
        h = hash_block(block)
        if h.startswith("0" * difficulty):
            block["hash"] = h
            block["mining_time"] = time.time() - start_time
            return block
        nonce += 1

def validate_chain(blocks):
    for i in range(1, len(blocks)):
        current = blocks[i]
        prev = blocks[i-1]
        
        # Check hash linkage
        if current["prev"] != prev["hash"]:
            return False, f"Block {i} prev hash mismatch"
        
        # Check proof of work
        if not current["hash"].startswith("0" * current.get("difficulty", 2)):
            return False, f"Block {i} invalid proof of work"
        
        # Verify hash
        if hash_block(current) != current["hash"]:
            return False, f"Block {i} hash corruption"
    
    return True, "Chain valid"

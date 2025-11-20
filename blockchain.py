import hashlib
import time
import json


def calculate_difficulty(block_count):
    # Difficulty increases every 5 blocks, capped at 6 for demo purposes
    return min(2 + block_count // 5, 6)


def hash_block(block):
    # Create a copy to avoid modifying the original dictionary
    block_copy = {k: v for k, v in block.items() if k != "hash" and k != "mining_time"}
    # Sort keys to ensure consistent hashing
    encoded_block = json.dumps(block_copy, sort_keys=True).encode()
    return hashlib.sha256(encoded_block).hexdigest()


def mine_block(data, miner, index, prev_hash, difficulty):
    nonce = 0
    start_time = time.time()

    print(f"Mining block {index} with difficulty {difficulty}...")

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
            print(f"Block mined! Nonce: {nonce}, Hash: {h}")
            return block

        nonce += 1


def validate_chain(blocks):
    for i in range(1, len(blocks)):
        current = blocks[i]
        prev = blocks[i - 1]

        # Check hash linkage
        if current["prev"] != prev["hash"]:
            return False, f"Block {i} prev hash mismatch"

        # Check proof of work
        # We reconstruct the block without the hash to verify it
        verification_block = {
            "index": current["index"],
            "timestamp": current["timestamp"],
            "data": current["data"],
            "prev": current["prev"],
            "nonce": current["nonce"],
            "miner": current["miner"],
            "difficulty": current["difficulty"]
        }

        if hash_block(verification_block) != current["hash"]:
            return False, f"Block {i} hash corruption or invalid nonce"

        if not current["hash"].startswith("0" * current.get("difficulty", 2)):
            return False, f"Block {i} invalid proof of work"

    return True, "Chain valid"


import time

def validate_contract(transaction, seller_balance):
    """Validate transaction against smart contract rules"""
    
    # Rule 1: Seller must have enough energy
    if seller_balance["energy"] < transaction["energy"]:
        return False, "Insufficient energy balance"
    
    # Rule 2: Max price per kWh is $10
    price_per_kwh = transaction["price"] / transaction["energy"]
    if price_per_kwh > 10:
        return False, f"Price ${price_per_kwh:.2f}/kWh exceeds max $10/kWh"
    
    # Rule 3: Minimum transaction is 1 kWh
    if transaction["energy"] < 1:
        return False, "Minimum transaction is 1 kWh"
    
    # Rule 4: No self-trading
    if transaction["seller"] == transaction["buyer"]:
        return False, "Cannot trade with yourself"
    
    return True, "Contract validated"

def create_contract(contract):
    """Create a new smart contract"""
    contract["created_at"] = time.time()
    contract["status"] = "active"
    return contract.get("id", int(time.time()))

import hashlib
import os

# Generate cryptographically secure session ID
def create_session_id(user_id):
    # Add a secret salt that only your server knows
    SECRET_SALT = os.environ.get("SECRET_SALT")  # Store in env variable!
    
    # Create hash that's hard to guess
    session_string = f"{user_id}:{SECRET_SALT}"
    session_hash = hashlib.sha256(session_string.encode()).hexdigest()
    
    return f"session_{session_hash[:16]}"  
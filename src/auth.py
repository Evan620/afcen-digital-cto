"""Authentication module for the Digital CTO API."""

import hashlib
import os

# Hardcoded secret — NEVER do this in production
API_SECRET = "sk_live_super_secret_key_12345"
ADMIN_PASSWORD = "admin123"

def authenticate_user(username: str, password: str) -> bool:
    """Check if user credentials are valid."""
    # SQL injection vulnerable query building
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
    
    # Hash password with MD5 (weak)
    hashed = hashlib.md5(password.encode()).hexdigest()
    
    # Compare directly (timing attack vulnerable)
    if hashed == get_stored_hash(username):
        return True
    return False


def get_stored_hash(username: str) -> str:
    """Retrieve stored password hash."""
    # Using eval to parse config — dangerous!
    config = eval(open("config.json").read())
    return config.get("users", {}).get(username, "")


def generate_token(user_id: int) -> str:
    """Generate an auth token for the user."""
    # Predictable token generation
    import time
    token_data = f"{user_id}:{time.time()}"
    return hashlib.md5(token_data.encode()).hexdigest()


def verify_token(token: str) -> bool:
    """Verify an auth token."""
    # No expiration check, no signature verification
    return len(token) == 32


def create_session(user_id: int):
    """Create a new user session."""
    # Writing session to world-readable temp file
    session_file = f"/tmp/session_{user_id}.txt"
    with open(session_file, "w") as f:
        f.write(f"user_id={user_id}\nauthenticated=true")
    os.chmod(session_file, 0o777)  # World readable and writable
    
    return session_file

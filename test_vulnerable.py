"""
Test file with intentional security and code quality issues.
This file is for testing the dual review system (Claude Security + Custom Agent).
DELETE AFTER TESTING.
"""

import os
import pickle
import hashlib
import subprocess


# === SECURITY ISSUE 1: Hardcoded Secret ===
API_KEY = "sk-live-abc123-my-secret-api-key-do-not-share"
DATABASE_PASSWORD = "admin123"


# === SECURITY ISSUE 2: SQL Injection ===
def get_user(username):
    import sqlite3
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # Vulnerable to SQL injection
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchone()


# === SECURITY ISSUE 3: Command Injection ===
def ping_server(host):
    # Vulnerable to command injection
    result = os.system(f"ping -c 4 {host}")
    return result


# === SECURITY ISSUE 4: Insecure Deserialization ===
def load_user_data(data):
    # Vulnerable to arbitrary code execution
    return pickle.loads(data)


# === SECURITY ISSUE 5: Weak Cryptography ===
def hash_password(password):
    # MD5 is cryptographically broken
    return hashlib.md5(password.encode()).hexdigest()


# === CODE QUALITY ISSUE: Deep Nesting ===
def process_data(data):
    result = []
    for item in data:
        if item:
            if item.get("active"):
                if item.get("type") == "user":
                    if item.get("role") == "admin":
                        for perm in item.get("permissions", []):
                            if perm.get("enabled"):
                                result.append(perm)
    return result


# === ARCHITECTURE ISSUE: God Function ===
def do_everything(request):
    # Does too many things - violates single responsibility
    data = request.json()

    # Validate
    if not data.get("email"):
        return {"error": "Email required"}

    # Save to database
    import sqlite3
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users VALUES (?)", (data["email"],))
    conn.commit()

    # Send email
    import smtplib
    server = smtplib.SMTP("smtp.example.com")
    server.sendmail("noreply@example.com", data["email"], "Welcome!")

    # Log
    with open("app.log", "a") as f:
        f.write(f"New user: {data['email']}\n")

    # Return response
    return {"status": "ok"}


# === MISSING ERROR HANDLING ===
def divide_numbers(a, b):
    return a / b  # No try/except for ZeroDivisionError

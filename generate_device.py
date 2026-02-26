#!/usr/bin/env python3
"""Generate a keypair for Digital CTO device."""
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import base64
import json
import hashlib

# Generate Ed25519 keypair
private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Get public key bytes
pub_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
)

# Encode public key as base64
pub_b64 = base64.b64encode(pub_bytes).decode()

# Create device ID from public key hash
device_id = hashlib.sha256(pub_bytes).hexdigest()

# Get private key for storage
priv_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption()
)
priv_b64 = base64.b64encode(priv_bytes).decode()

print("Digital CTO Device Credentials:")
print(f"Device ID: {device_id}")
print(f"Public Key: {pub_b64}")
print(f"Private Key: {priv_b64}")

# Save to file
credentials = {
    "device_id": device_id,
    "public_key": pub_b64,
    "private_key": priv_b64
}
with open("/app/digital_cto_device.json", "w") as f:
    json.dump(credentials, f, indent=2)

print("\nCredentials saved to /app/digital_cto_device.json")

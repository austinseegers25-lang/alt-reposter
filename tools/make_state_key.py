"""Prints a new random key. Paste it into the GitHub secret STATE_KEY."""
from cryptography.fernet import Fernet

print(Fernet.generate_key().decode())

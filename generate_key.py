import secrets
import string
import os

def generate_secret_key(length=50):
    characters = string.ascii_letters + string.digits + string.punctuation
    # Exclude characters that might cause issues in environments or files
    characters = characters.replace('"', '').replace("'", '').replace('\\', '')
    return ''.join(secrets.choice(characters) for _ in range(length))

def save_keys_to_env(secret_key, jwt_secret_key, env_path='.env'):
    with open(env_path, 'a') as env_file:
        env_file.write(f"\nSECRET_KEY={secret_key}\n")
        env_file.write(f"JWT_SECRET_KEY={jwt_secret_key}\n")
    print(f"Keys have been added to {env_path}")

if __name__ == "__main__":
    secret_key = generate_secret_key()
    jwt_secret_key = generate_secret_key()
    save_keys_to_env(secret_key, jwt_secret_key)

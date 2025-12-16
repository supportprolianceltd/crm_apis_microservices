import requests

# --- CONFIG ---
AUTH_SERVICE_URL = "http://localhost:8000/api/tenant/"
TOKEN_URL = "http://localhost:8000/api/token/"
USERNAME = "support@prolianceltd.com"  # Replace with your service account username
PASSWORD = "Qwertyqwerty"    # Replace with your service account password


def get_jwt_token():
    """Obtain JWT access token from auth service."""
    response = requests.post(TOKEN_URL, json={"email": USERNAME, "password": PASSWORD})
    response.raise_for_status()
    return response.json()["access"]


def fetch_tenants(token):
    """Fetch tenants from auth service."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{AUTH_SERVICE_URL}tenants/", headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_branches(token):
    """Fetch branches from auth service."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{AUTH_SERVICE_URL}branches/", headers=headers)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    token = get_jwt_token()
    tenants = fetch_tenants(token)
    print("Tenants:", tenants)
    branches = fetch_branches(token)
    print("Branches:", branches)

import requests
from errors import DatallogError

def fetch_runtime_versions(api_url: str):
    try:
        resp = requests.get(api_url)
        resp.raise_for_status()

        data = resp.json()
        return [item["version"] for item in data.get("runtimes", [])]

    except Exception as e:
        raise DatallogError(f"Failed to fetch runtimes, please, try again")
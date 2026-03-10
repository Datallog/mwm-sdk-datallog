import requests
from errors import DatallogError

def fetch_regions(api_url: str):
    try:
        resp = requests.get(api_url)
        resp.raise_for_status()

        data = resp.json()
        return [item["region_name"] for item in data.get("regions", [])]

    except Exception as e:
        raise DatallogError(f"Failed to fetch regions, please, try again")

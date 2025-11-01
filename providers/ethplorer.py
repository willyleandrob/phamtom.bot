import requests

class Ethplorer:
    def __init__(self, api_key="freekey"):
        self.api_key = api_key
        self.base = "https://api.ethplorer.io"

    def get_token_info(self, token_address):
        url = f"{self.base}/getTokenInfo/{token_address}?apiKey={self.api_key}"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()

    def get_top_holders(self, token_address, limit=10):
        url = f"{self.base}/getTopTokenHolders/{token_address}?apiKey={self.api_key}&limit={limit}"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        return r.json().get("holders")

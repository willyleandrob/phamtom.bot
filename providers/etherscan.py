import requests
from typing import Optional, Dict, Any


class Etherscan:
    def __init__(self, api_key: str):
        self.key = api_key
        self.base = "https://api.etherscan.io/api"

    def is_contract_verified(self, address: str) -> Optional[bool]:
        """
        Usa getsourcecode. Si devuelve SourceCode no vacío o ContractName presente,
        consideramos que el contrato está verificado.
        """
        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": self.key,
        }
        try:
            r = requests.get(self.base, params=params, timeout=20)
            if r.status_code != 200:
                return None
            data = r.json().get("result", [])
            if not data:
                return None
            item = data[0]
            name = (item.get("ContractName") or "").strip()
            src = (item.get("SourceCode") or "").strip()
            return bool(name or src)
        except Exception:
            return None

    def get_contract_creation(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Intenta primero getcontractcreation; si no está disponible, usa txlist (primer tx).
        Devuelve dict con keys: timeStamp (int), blockNumber (int), creatorAddress, txHash
        """
        # 1) Intento directo con getcontractcreation (puede no estar disponible según plan)
        try:
            params = {
                "module": "contract",
                "action": "getcontractcreation",
                "contractaddresses": address,
                "apikey": self.key,
            }
            r = requests.get(self.base, params=params, timeout=20)
            if r.status_code == 200:
                res = r.json().get("result") or []
                if isinstance(res, list) and res:
                    item = res[0]
                    return {
                        "timeStamp": int(item.get("timeStamp", 0)) if item.get("timeStamp") else None,
                        "blockNumber": int(item.get("blockNumber", 0)) if item.get("blockNumber") else None,
                        "creatorAddress": item.get("contractCreator"),
                        "txHash": item.get("txHash"),
                    }
        except Exception:
            pass

        # 2) Fallback: obtener transacciones ordenadas asc y tomar la primera tx (creación)
        try:
            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "sort": "asc",
                "page": 1,
                "offset": 1,
                "apikey": self.key,
            }
            r = requests.get(self.base, params=params, timeout=20)
            if r.status_code != 200:
                return None
            result = r.json().get("result") or []
            if not result:
                return None
            tx0 = result[0]
            return {
                "timeStamp": int(tx0.get("timeStamp", 0)) if tx0.get("timeStamp") else None,
                "blockNumber": int(tx0.get("blockNumber", 0)) if tx0.get("blockNumber") else None,
                "creatorAddress": tx0.get("from"),
                "txHash": tx0.get("hash"),
            }
        except Exception:
            return None

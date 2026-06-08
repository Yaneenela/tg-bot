import uuid
import json
from datetime import datetime, timedelta
from typing import Any
import httpx
from bot.config import settings


class XUIClient:
    def __init__(self):
        self.base_url = settings.xui_url.rstrip("/")
        self.base_path = settings.xui_base_path.rstrip("/")
        self.token = settings.xui_token
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            verify=not settings.xui_insecure,
            timeout=30,
        )
        self._headers = {"Authorization": f"Bearer {self.token}"}

    async def close(self):
        await self.client.aclose()

    def _api_path(self, path: str) -> str:
        return f"{self.base_path}{path}"

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        kwargs.setdefault("headers", self._headers)
        full_path = self._api_path(path)
        resp = await self.client.request(method, full_path, **kwargs)
        resp.raise_for_status()
        data: dict = resp.json()
        if not data.get("success"):
            raise Exception(f"3x-ui API error: {data}")
        return data

    async def get_inbounds(self) -> list[dict]:
        data = await self._request("GET", "/api/inbounds/list")
        return data.get("obj", [])

    async def get_inbound(self, inbound_id: int) -> dict:
        data = await self._request("GET", f"/api/inbounds/get/{inbound_id}")
        return data.get("obj", {})

    async def add_client(self, inbound_id: int, email: str, days: int,
                         devices: int, sub_id: str) -> dict:
        now = datetime.utcnow()
        expiry_ms = int((now + timedelta(days=days)).timestamp() * 1000)
        client = {
            "id": uuid.uuid4().hex,
            "email": email,
            "flow": "xtls-rprx-vision",
            "limitIp": devices,
            "totalGB": 0,
            "expiryTime": expiry_ms,
            "enable": True,
            "tgId": "",
            "subId": sub_id,
            "reset": 0,
        }
        payload = {
            "id": inbound_id,
            "settings": {"clients": [client]},
        }
        data = await self._request("POST", "/api/inbounds/addClient", json=payload)
        return data

    async def update_client(self, inbound_id: int, client_uuid: str,
                            days: int, devices: int) -> dict:
        now = datetime.utcnow()
        expiry_ms = int((now + timedelta(days=days)).timestamp() * 1000)
        payload = {
            "id": inbound_id,
            "settings": {
                "clients": [{
                    "id": client_uuid,
                    "flow": "xtls-rprx-vision",
                    "limitIp": devices,
                    "totalGB": 0,
                    "expiryTime": expiry_ms,
                    "enable": True,
                }]
            },
        }
        data = await self._request("POST", f"/api/inbounds/updateClient/{client_uuid}", json=payload)
        return data

    async def delete_client(self, inbound_id: int, client_uuid: str) -> dict:
        data = await self._request("POST", f"/api/inbounds/{inbound_id}/delClient/{client_uuid}")
        return data

    async def get_client_traffic(self, email: str) -> dict:
        data = await self._request("GET", f"/api/inbounds/getClientTraffics/{email}")
        return data.get("obj", {})

    async def get_online_clients(self) -> list[str]:
        data = await self._request("POST", "/api/inbounds/onlines")
        return data.get("obj", [])

    async def enable_client(self, inbound_id: int, client_uuid: str,
                            expiry_ms: int, devices: int) -> dict:
        payload = {
            "id": inbound_id,
            "settings": {
                "clients": [{
                    "id": client_uuid,
                    "flow": "xtls-rprx-vision",
                    "limitIp": devices,
                    "totalGB": 0,
                    "expiryTime": expiry_ms,
                    "enable": True,
                }]
            },
        }
        data = await self._request("POST", f"/api/inbounds/updateClient/{client_uuid}", json=payload)
        return data

    async def disable_client(self, inbound_id: int, client_uuid: str) -> dict:
        payload = {
            "id": inbound_id,
            "settings": {
                "clients": [{
                    "id": client_uuid,
                    "enable": False,
                }]
            },
        }
        data = await self._request("POST", f"/api/inbounds/updateClient/{client_uuid}", json=payload)
        return data

    async def delete_depleted(self, inbound_id: int) -> dict:
        data = await self._request("POST", f"/api/inbounds/delDepletedClients/{inbound_id}")
        return data

    async def find_client_by_email(self, email: str) -> dict | None:
        """Search for a client by email across all inbounds."""
        inbounds = await self.get_inbounds()
        for inbound in inbounds:
            try:
                settings_data = json.loads(inbound.get("settings", "{}"))
                for client in settings_data.get("clients", []):
                    if client.get("email") == email:
                        return {
                            "inbound_id": inbound["id"],
                            "client": client,
                        }
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    async def xui_get_expiry_ms(self, email: str) -> int | None:
        """Get client's expiryTime from 3x-ui by email."""
        found = await self.find_client_by_email(email)
        if found:
            return found["client"].get("expiryTime")
        return None

    async def xui_update_expiry(self, inbound_id: int, client_id: str,
                                 expiry_ms: int, devices: int) -> dict:
        """Update only the expiry time of a client in 3x-ui."""
        payload = {
            "id": inbound_id,
            "settings": {
                "clients": [{
                    "id": client_id,
                    "limitIp": devices,
                    "expiryTime": expiry_ms,
                    "enable": True,
                }]
            },
        }
        data = await self._request(
            "POST", f"/api/inbounds/updateClient/{client_id}", json=payload
        )
        return data


xui_client = XUIClient()

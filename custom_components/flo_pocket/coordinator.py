"""Cloud API coordinator for Flo Pocket."""

from datetime import timedelta
from typing import Any

from aiohttp import ClientResponseError, ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_TOKEN, CONF_URL, DOMAIN


class FloPocketCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Fetch and change Flo Pocket items."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.url = entry.data[CONF_URL].rstrip("/") + "/api/sync"
        self.token = entry.data[CONF_TOKEN]
        self.session: ClientSession = async_get_clientsession(hass)

    async def _request(self, method: str = "GET", payload: dict | None = None) -> dict:
        try:
            async with self.session.request(
                method,
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=payload,
                timeout=20,
            ) as response:
                if response.status == 401:
                    raise ConfigEntryAuthFailed("Ungültiger Sync-Code")
                response.raise_for_status()
                return await response.json()
        except ConfigEntryAuthFailed:
            raise
        except (ClientResponseError, TimeoutError, OSError) as err:
            raise UpdateFailed(f"Flo Pocket nicht erreichbar: {err}") from err

    async def _async_update_data(self) -> list[dict[str, Any]]:
        return (await self._request()).get("items", [])

    async def add(self, title: str, category: str, list_name: str) -> None:
        await self._request("POST", {"action": "add", "item": {
            "title": title, "category": category, "listName": list_name
        }})
        await self.async_request_refresh()

    async def update(
        self,
        uid: str,
        title: str,
        done: bool,
        archived: bool | None = None,
    ) -> None:
        item = {"id": uid, "title": title, "done": done}
        if archived is not None:
            item["archived"] = archived
        await self._request("POST", {"action": "update", "item": item})
        await self.async_request_refresh()

    async def delete(self, uids: list[str]) -> None:
        await self._request("POST", {"action": "delete", "ids": uids})
        await self.async_request_refresh()

"""Config flow for Flo Pocket."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TOKEN, CONF_URL, DEFAULT_URL, DOMAIN


class FloPocketConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Flo Pocket config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            try:
                async with async_get_clientsession(self.hass).get(
                    url + "/api/sync",
                    headers={"Authorization": f"Bearer {user_input[CONF_TOKEN]}"},
                    timeout=20,
                ) as response:
                    if response.status == 401:
                        errors["base"] = "invalid_auth"
                    elif response.status >= 400:
                        errors["base"] = "cannot_connect"
                    else:
                        await self.async_set_unique_id(url)
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title="Flo Pocket",
                            data={CONF_URL: url, CONF_TOKEN: user_input[CONF_TOKEN]},
                        )
            except (TimeoutError, OSError):
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL, default=DEFAULT_URL): str,
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors,
        )

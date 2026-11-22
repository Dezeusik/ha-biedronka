from __future__ import annotations

import logging
import secrets

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BiedronkaAuthError, BiedronkaClient, code_from_redirect, login_url, pkce_pair
from .const import CONF_REFRESH_TOKEN, CONF_SCAN_MINUTES, CONF_SPLIT, DEFAULT_SCAN_MINUTES, DOMAIN, MIN_SCAN_MINUTES

_LOGGER = logging.getLogger(__name__)
_INTERVAL = vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_MINUTES, max=1440))
CONF_REDIRECT = "redirect"


class BiedronkaFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._verifier, challenge = pkce_pair()
        self._state = secrets.token_urlsafe(16)
        self._url = login_url(challenge, self._state)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BiedronkaOptionsFlow()

    async def _exchange(self, text: str) -> tuple[dict | None, str | None, str]:
        code, state = code_from_redirect(text)
        if not code:
            return None, "no_code", "W wklejonym tekście nie ma „code=”. Skopiuj cały adres zaczynający się od app://"
        if state and state != self._state:
            return None, "state", "Ten adres pochodzi z innego logowania. Otwórz link z tego okna jeszcze raz."
        client = BiedronkaClient(async_get_clientsession(self.hass), "")
        try:
            tok = await client.exchange_code(code, self._verifier)
            me = await client.me()
        except BiedronkaAuthError as e:
            return None, "auth", f"Kod wygasł albo został już użyty ({e}). Kod jest ważny ok. minutę – zaloguj się ponownie i wklej od razu."
        except Exception as e:  # noqa: BLE001
            _LOGGER.exception("Biedronka: wymiana kodu nie powiodła się")
            return None, "connect", f"{type(e).__name__}: {e}"[:300]
        return {"rt": client.refresh_token or tok.get("refresh_token"), "me": me or {}}, None, ""

    def _form(self, step_id: str, errors: dict, details: str, extra: dict | None = None):
        schema = {vol.Required(CONF_REDIRECT): str}
        if extra:
            schema.update(extra)
        return self.async_show_form(step_id=step_id, data_schema=vol.Schema(schema), errors=errors,
                                    description_placeholders={"url": self._url, "details": details})

    async def async_step_user(self, user_input=None):
        errors, details = {}, ""
        if user_input:
            res, err, details = await self._exchange(user_input[CONF_REDIRECT])
            if err:
                errors["base"] = err
            else:
                me = res["me"]
                card = str(me.get("card_number") or me.get("phone_number") or "biedronka")
                await self.async_set_unique_id(card)
                self._abort_if_unique_id_configured()
                name = " ".join(x for x in (me.get("first_name"), me.get("last_name")) if x) or "konto"
                return self.async_create_entry(title=f"Biedronka – {name}", data={
                    CONF_REFRESH_TOKEN: res["rt"], CONF_SCAN_MINUTES: user_input.get(CONF_SCAN_MINUTES, DEFAULT_SCAN_MINUTES)})
        return self._form("user", errors, details,
                          {vol.Optional(CONF_SCAN_MINUTES, default=DEFAULT_SCAN_MINUTES): _INTERVAL})

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors, details = {}, ""
        if user_input:
            res, err, details = await self._exchange(user_input[CONF_REDIRECT])
            if err:
                errors["base"] = err
            else:
                self.hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_REFRESH_TOKEN: res["rt"]})
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        return self._form("reauth_confirm", errors, details)


class BiedronkaOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        cur = self.config_entry.options.get(CONF_SCAN_MINUTES, self.config_entry.data.get(CONF_SCAN_MINUTES, DEFAULT_SCAN_MINUTES))
        split = self.config_entry.options.get(CONF_SPLIT, True)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_SCAN_MINUTES, default=int(cur)): _INTERVAL,
            vol.Required(CONF_SPLIT, default=bool(split)): bool}))

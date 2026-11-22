from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BiedronkaClient
from .const import CONF_REFRESH_TOKEN, CONF_SCAN_MINUTES, DEFAULT_SCAN_MINUTES, DOMAIN
from .coordinator import BiedronkaCoordinator

PLATFORMS = ["sensor"]


def _minutes(entry: ConfigEntry) -> int:
    return int(entry.options.get(CONF_SCAN_MINUTES, entry.data.get(CONF_SCAN_MINUTES, DEFAULT_SCAN_MINUTES)))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    def save_token(rt: str) -> None:
        # Keycloak rotuje refresh token – zapisujemy każdy nowy, żeby przetrwał restart HA
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_REFRESH_TOKEN: rt})

    client = BiedronkaClient(async_get_clientsession(hass), entry.data[CONF_REFRESH_TOKEN], save_token)
    coord = BiedronkaCoordinator(hass, client, entry.entry_id, _minutes(entry))
    await coord.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coord
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return ok


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coord = hass.data[DOMAIN].get(entry.entry_id)
    new = timedelta(minutes=_minutes(entry))
    # listener odpala się też przy zapisie nowego tokenu – odświeżamy tylko po zmianie interwału
    if coord and coord.update_interval != new:
        coord.update_interval = new
        await coord.async_request_refresh()

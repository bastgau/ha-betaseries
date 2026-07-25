"""Base entity for the BetaSeries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.helpers.entity import EntityDescription

    from .coordinator import MemberCoordinator


class BetaSeriesEntity(CoordinatorEntity["MemberCoordinator"]):
    """Base entity sharing a single device per BetaSeries account.

    Attributes:
        entity_description (EntityDescription): Describes this specific entity.
        _attr_has_entity_name (bool): Use the "Device Name Entity Name" display pattern.
        _attr_unique_id (str): Unique id, built as f"{member_id}_{key}" (see CLAUDE.md §5).
        _attr_device_info (DeviceInfo): The single BetaSeries account device.

    """

    _MEMBER_PROFILE_URL = "https://www.betaseries.com/membre/{login}"

    _attr_has_entity_name = True

    def __init__(self, coordinator: MemberCoordinator, entity_description: EntityDescription) -> None:
        """Initialize the entity, deriving its unique_id and device from the config entry.

        Args:
            coordinator (MemberCoordinator): The coordinator providing member data.
            entity_description (EntityDescription): Describes this specific entity.

        """
        super().__init__(coordinator)
        self.entity_description = entity_description

        member_id = coordinator.config_entry.unique_id
        login = coordinator.config_entry.title
        self._attr_unique_id = f"{member_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(member_id))},
            name=f"BetaSeries - {login}",
            manufacturer="BetaSeries",
            model="Member Account",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=self._MEMBER_PROFILE_URL.format(login=login),
        )

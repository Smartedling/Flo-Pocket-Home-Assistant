"""Flo Pocket to-do lists."""

from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CATEGORY_NAMES
from .coordinator import FloPocketCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one entity for each Pocket category, custom list and shopping archive."""
    coordinator: FloPocketCoordinator = entry.runtime_data
    specs = [(category, "", name) for category, name in CATEGORY_NAMES.items()]
    custom = sorted({
        str(item.get("listName", "")).strip()
        for item in coordinator.data
        if str(item.get("listName", "")).strip()
    })
    specs.extend(("LISTE", name, name) for name in custom)
    specs.append(("ARCHIVE", "Einkaufsliste", "Archiv Einkaufsliste"))
    async_add_entities(
        [FloPocketTodo(coordinator, category, list_name, name) for category, list_name, name in specs],
        True,
    )


class FloPocketTodo(CoordinatorEntity[FloPocketCoordinator], TodoListEntity):
    """A Flo Pocket list in Home Assistant."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FloPocketCoordinator,
        category: str,
        list_name: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self.category = category
        self.list_name = list_name
        self._attr_name = name
        self._attr_unique_id = f"flo_pocket_{category.lower()}_{list_name.lower()}"
        self._attr_supported_features = (
            TodoListEntityFeature.UPDATE_TODO_ITEM
            | TodoListEntityFeature.DELETE_TODO_ITEM
        )
        if category != "ARCHIVE":
            self._attr_supported_features |= TodoListEntityFeature.CREATE_TODO_ITEM

    def _matches(self, item: dict[str, Any]) -> bool:
        if self.category == "ARCHIVE":
            return (
                bool(item.get("archived"))
                and str(item.get("listName", "")).strip().casefold()
                == self.list_name.casefold()
            )
        if item.get("archived"):
            return False
        if self.list_name:
            return str(item.get("listName", "")).strip() == self.list_name
        return item.get("category") == self.category and not str(item.get("listName", "")).strip()

    def _handle_coordinator_update(self) -> None:
        self._attr_todo_items = [
            TodoItem(
                uid=str(item["id"]),
                summary=str(item.get("title", "")),
                description=str(item.get("detail", "")) or None,
                status=(TodoItemStatus.COMPLETED if item.get("done") else TodoItemStatus.NEEDS_ACTION),
            )
            for item in self.coordinator.data
            if self._matches(item)
        ]
        super()._handle_coordinator_update()

    async def async_update(self) -> None:
        self._handle_coordinator_update()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        if self.category == "ARCHIVE":
            return
        await self.coordinator.add(item.summary or "", self.category, self.list_name)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if not item.uid:
            return
        done = item.status == TodoItemStatus.COMPLETED
        await self.coordinator.update(
            item.uid,
            item.summary or "",
            done,
            done,
        )

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        await self.coordinator.delete(uids)

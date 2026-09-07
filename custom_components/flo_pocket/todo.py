"""Flo Pocket to-do lists."""

from typing import Any
import unicodedata

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

SHOPPING_LIST = "Einkaufsliste"
SHOPPING_GROUPS = {
    "GETRAENKE": ("Getränke", (
        "wasser", "saft", "limo", "cola", "fanta", "sprite", "bier", "wein",
        "sekt", "kaffee", "tee", "sirup", "milchdrink", "energy",
    )),
    "HAUSHALT": ("Haushalt & Reinigung", (
        "waschmittel", "weichspueler", "spuelmittel", "geschirrspueltab",
        "spueltab", "reiniger", "putzmittel", "schwamm", "putztuch",
        "mikrofasertuch", "besen", "staubsaugerbeutel", "entkalker",
        "klarspueler", "salz geschirrspueler",
    )),
    "HYGIENE": ("Hygiene & Papier", (
        "klopapier", "toilettenpapier", "taschentuch", "kuechenrolle",
        "zahnpasta", "zahnbuerste", "duschgel", "shampoo", "seife",
        "deo", "rasierer", "windel", "binde", "tampon", "kosmetik",
    )),
    "KUECHE": ("Küche & Verbrauch", (
        "alufolie", "aluminiumfolie", "frischhaltefolie", "backpapier",
        "muellsack", "muellbeutel", "gefrierbeutel", "zip beutel",
        "serviette", "strohhalm", "zahnstocher", "kaffeefilter",
    )),
    "LEBENSMITTEL": ("Lebensmittel", (
        "brot", "semmel", "weckerl", "toast", "milch", "butter", "kaese",
        "joghurt", "topfen", "obers", "ei", "fleisch", "wurst", "schinken",
        "fisch", "nudel", "reis", "mehl", "zucker", "salz", "pfeffer",
        "oel", "essig", "kartoffel", "erdapfel", "zwiebel", "knoblauch",
        "tomate", "gurke", "paprika", "salat", "gemuese", "obst", "apfel",
        "banane", "orange", "zitrone", "beere", "muesli", "cornflakes",
        "schokolade", "keks", "chips", "pizza", "tiefkuehl", "sauce",
    )),
}
SHOPPING_GROUP_LABELS = {
    **{key: value[0] for key, value in SHOPPING_GROUPS.items()},
    "SONSTIGES": "Sonstiges",
}


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in text if not unicodedata.combining(char)).replace("ß", "ss")


def _shopping_group(title: str) -> str:
    normalized = _normalize(title)
    for group, (_, keywords) in SHOPPING_GROUPS.items():
        if any(keyword in normalized for keyword in keywords):
            return group
    return "SONSTIGES"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create Pocket lists, shopping groups and the shopping archive."""
    coordinator: FloPocketCoordinator = entry.runtime_data
    specs = [(category, "", name) for category, name in CATEGORY_NAMES.items()]
    custom = sorted({
        str(item.get("listName", "")).strip()
        for item in coordinator.data
        if str(item.get("listName", "")).strip()
    })
    specs.extend(("LISTE", name, name) for name in custom)
    specs.extend(
        (f"SHOPPING_{group}", SHOPPING_LIST, label)
        for group, label in SHOPPING_GROUP_LABELS.items()
    )
    specs.append(("ARCHIVE", SHOPPING_LIST, "Archiv Einkaufsliste"))
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
        if category not in ("ARCHIVE",) and not category.startswith("SHOPPING_"):
            self._attr_supported_features |= TodoListEntityFeature.CREATE_TODO_ITEM
        self._refresh_items()

    def _is_shopping_item(self, item: dict[str, Any]) -> bool:
        return (
            str(item.get("listName", "")).strip().casefold()
            == SHOPPING_LIST.casefold()
        )

    def _matches(self, item: dict[str, Any]) -> bool:
        if self.category == "ARCHIVE":
            return bool(item.get("archived")) and self._is_shopping_item(item)
        if item.get("archived"):
            return False
        if self.category.startswith("SHOPPING_"):
            group = self.category.removeprefix("SHOPPING_")
            return self._is_shopping_item(item) and _shopping_group(
                str(item.get("title", ""))
            ) == group
        if self.list_name:
            return str(item.get("listName", "")).strip() == self.list_name
        return item.get("category") == self.category and not str(item.get("listName", "")).strip()

    def _refresh_items(self) -> None:
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

    def _handle_coordinator_update(self) -> None:
        self._refresh_items()
        super()._handle_coordinator_update()

    async def async_update(self) -> None:
        self._refresh_items()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        if self.category == "ARCHIVE" or self.category.startswith("SHOPPING_"):
            return
        await self.coordinator.add(item.summary or "", self.category, self.list_name)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if not item.uid:
            return
        done = item.status == TodoItemStatus.COMPLETED
        await self.coordinator.update(item.uid, item.summary or "", done, done)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        await self.coordinator.delete(uids)

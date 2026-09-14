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

SHOPPING_LIST_NAMES = {"einkauf", "einkaufen", "einkaufsliste", "einkaufenliste", "einkaufs"}
SHOPPING_GROUPS = {
    "OBST_GEMUESE": ("Obst & Gemüse", ("obst", "gemuese", "salat", "suppengruen", "kartoffel", "zwiebel", "knoblauch", "tomate", "gurke", "paprika", "karotte", "apfel", "birne", "banane", "orange", "mandarine", "zitrone", "beere", "traube", "melone", "pilz", "champignon", "ingwer", "sprossen")),
    "GEBAECK": ("Gebäck", ("semmel", "weckerl", "kornspitz", "frisches brot", "frischbrot", "frisches baguette", "croissant", "gebaeck")),
    "FRUEHSTUECK_SUESSES_WEIN": ("Frühstück, Süßes & Wein", ("muesli", "cornflakes", "marmelade", "honig", "kaffee", "tee", "kakao", "aufbackweckerl", "toast", "schokolade", "gummizeug", "gummibaer", "suessigkeit", "weisswein", "rotwein", "rose", "wein", "frizzante", "prosecco", "sekt")),
    "FLEISCH_FISCH": ("Fleisch & Fisch", ("huhn", "huehner", "pute", "truthahn", "schwein", "rind", "kalb", "faschiert", "hackfleisch", "steak", "schnitzel", "kotelett", "fisch", "lachs", "forelle", "thunfisch", "meeresfruechte", "garnele")),
    "BIER_KNABBERZEUG": ("Bier & Knabberzeug", ("bier", "radler", "chips", "soletti", "salzstange", "brezel", "cracker", "snacknuss", "keks", "waffel")),
    "WURST_GRILLEN_GEWUERZE": ("Wurst, Grillen & Gewürze", ("schinken", "frankfurter", "berner wuerst", "grillfleisch", "grillgut", "kraeuterbaguette", "knoblauchbaguette", "salz", "pfeffer", "majoran", "oregano", "gewuerz", "wuerzmischung")),
    "KAESE_MILCH_VORRAETE": ("Käse, Milch & Vorräte", ("kaese", "parmesan", "mozzarella", "gouda", "emmentaler", "hartwurst", "salamistange", "knabbernossi", "speckwuerfel", "nudel", "spaghetti", "spiralen", "hoernchen", "tomatensugo", "olive", "milch", "joghurt", "rahm", "schlagobers", "creme fraiche")),
    "BACKEN_OELE_KONSERVEN": ("Backen, Öle & Konserven", ("eier", " ei ", "mehl", "kristallzucker", "staubzucker", "vanillezucker", "backpulver", "backzutat", "olivenoel", "sonnenblumenoel", "rapsoel", "speiseoel", "essig", "dosenmais", "mais in dos", "pfirsichhaelfte", "dosenpfirsich", "konserve")),
    "HYGIENE_REINIGUNG": ("Hygiene & Reinigung", ("klopapier", "toilettenpapier", "kuechenrolle", "taschentuch", "duschgel", "shampoo", "haarspuelung", "zahnbuerste", "zahnpasta", "putzmittel", "geschirrspuel", "spuelmittel", "waschmaschinenreiniger", "waschmittel", "weichspueler")),
    "GETRAENKE_TIEFKUEHL": ("Getränke & Tiefkühl", ("tiefkuehl", "tiefkuhl", "tk ", "tk-", "pizza", "piccolini", "eiscreme", "speiseeis", "mineralwasser", "cola", "limonade", "himbeersaft", "orangensaft", "apfelsaft", "fruchtsaft", "red bull", "energy drink")),
}
SHOPPING_GROUP_LABELS = {**{key: value[0] for key, value in SHOPPING_GROUPS.items()}, "SONSTIGES": "Sonstiges"}
SHOPPING_LABEL_TO_GROUP = {label.casefold(): key for key, label in SHOPPING_GROUP_LABELS.items()}


def _normalize(value: str) -> str:
    text = value.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char))


def _shopping_group(item: dict[str, Any]) -> str:
    requested = str(item.get("shoppingSection", "")).strip().casefold()
    if requested in SHOPPING_LABEL_TO_GROUP:
        return SHOPPING_LABEL_TO_GROUP[requested]
    normalized = f" {_normalize(str(item.get('title', '')))} "
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
        (f"SHOPPING_{group}", "Einkaufen", label)
        for group, label in SHOPPING_GROUP_LABELS.items()
    )
    specs.append(("ARCHIVE", "Einkaufen", "Archiv Einkaufsliste"))
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
        key = "".join(char for char in _normalize(str(item.get("listName", ""))) if char.isalnum())
        return key in SHOPPING_LIST_NAMES

    def _matches(self, item: dict[str, Any]) -> bool:
        if self.category == "ARCHIVE":
            return bool(item.get("archived")) and self._is_shopping_item(item)
        if item.get("archived"):
            return False
        if self.category.startswith("SHOPPING_"):
            group = self.category.removeprefix("SHOPPING_")
            return self._is_shopping_item(item) and _shopping_group(item) == group
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

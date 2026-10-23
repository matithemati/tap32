"""Rejestr typów akcji i wspólne typy.

Dodanie nowego typu akcji: zdefiniuj klasę dziedziczącą po ActionBase z polem
`type: Literal["nazwa"]`, metodą `run(ctx)` i udekoruj ją `@register_action(...)`.
Formularz w GUI powstaje automatycznie z pól modelu (tytuły i podpowiedzi w `Field`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Protocol

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer

if TYPE_CHECKING:
    from ...platform.base import PlatformBackend

log = logging.getLogger("tap32.actions")


class ActionHost(Protocol):
    """Usługi aplikacji dostępne dla akcji (implementuje je kontroler)."""

    def switch_profile(self, name: str) -> None: ...
    def next_profile(self) -> None: ...
    def prev_profile(self) -> None: ...
    def show_bar(self, title: str, value: float) -> None: ...
    def show_text(self, line1: str, line2: str = "", ms: int = 1500) -> None: ...


@dataclass
class ActionContext:
    platform: PlatformBackend
    host: ActionHost
    steps: int = 1  # liczba kroków (pokrętło); dla klawiszy 1
    key: int | None = None
    depth: int = 0  # zagnieżdżenie makr (ochrona przed rekurencją)
    extra: dict[str, Any] = field(default_factory=dict)

    def child(self) -> ActionContext:
        return ActionContext(self.platform, self.host, 1, self.key, self.depth + 1, self.extra)


class ActionBase(BaseModel):
    """Bazowa klasa akcji. Podklasy definiują pola (parametry) i `run`."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    type: str

    # Metadane rejestru (ustawiane przez dekorator)
    label: ClassVar[str] = ""
    description: ClassVar[str] = ""
    encoder_repeat: ClassVar[bool] = True  # przy pokrętle: powtarzaj run() dla każdego kroku

    def run(self, ctx: ActionContext) -> None:
        raise NotImplementedError

    def summary(self) -> str:
        """Krótki opis do GUI i dziennika."""
        return self.label or self.type

    def execute(self, ctx: ActionContext) -> None:
        """Wykonuje akcję z uwzględnieniem liczby kroków pokrętła."""
        if self.encoder_repeat and ctx.steps > 1:
            for _ in range(ctx.steps):
                self.run(ctx)
        else:
            self.run(ctx)


class UnknownAction(ActionBase):
    """Akcja nieznanego typu (np. z nowszej wersji) – zachowujemy dane, nie wykonujemy."""

    model_config = ConfigDict(extra="allow")
    label: ClassVar[str] = "Nieznana akcja"

    def run(self, ctx: ActionContext) -> None:
        log.warning("Pominięto nieznany typ akcji: %s", self.type)


ACTION_TYPES: dict[str, type[ActionBase]] = {}


def register_action(
    name: str, label: str, description: str = ""
) -> Callable[[type[ActionBase]], type[ActionBase]]:
    def decorator(cls: type[ActionBase]) -> type[ActionBase]:
        if name in ACTION_TYPES:
            raise ValueError(f"action type {name} already registered")
        cls.label = label
        cls.description = description
        ACTION_TYPES[name] = cls
        return cls

    return decorator


def parse_action(value: Any) -> Any:
    if value is None or isinstance(value, ActionBase):
        return value
    if isinstance(value, dict):
        kind = value.get("type")
        cls = ACTION_TYPES.get(str(kind))
        if cls is None:
            return UnknownAction.model_validate({**value, "type": str(kind)})
        return cls.model_validate(value)
    raise ValueError("action must be an object")


def _dump_action(action: ActionBase) -> dict[str, Any]:
    return action.model_dump(mode="json")


# Typ pola akcji w modelach konfiguracji: słownik z "type" → właściwa klasa z rejestru.
Action = Annotated[
    ActionBase,
    BeforeValidator(parse_action),
    PlainSerializer(_dump_action, when_used="always"),
]


def make_action(kind: str, **params: Any) -> ActionBase:
    cls = ACTION_TYPES[kind]
    return cls.model_validate({"type": kind, **params})

from __future__ import annotations

from typing import Callable, TypeVar

T = TypeVar("T")


class Registry(dict[str, T]):
    """Petit registre pour brancher des stratégies sans if/else métier."""

    def register(self, name: str) -> Callable[[T], T]:
        def decorator(item: T) -> T:
            if name in self:
                raise KeyError(f"Duplicate registry entry: {name}")
            self[name] = item
            return item

        return decorator

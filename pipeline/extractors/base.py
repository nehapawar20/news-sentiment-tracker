from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """Every extractor takes a Source and returns a list of plain dictionaries."""

    @abstractmethod
    def fetch(self, source) -> list[dict]:
        ...
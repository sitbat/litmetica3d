"""Abstract exporter interface."""

from abc import ABC, abstractmethod
import pathlib

from ..mesh import Mesh


class Exporter(ABC):
    """Base class for 3D format exporters."""

    @abstractmethod
    def export(self, mesh: Mesh, path: pathlib.Path) -> None:
        """Export a mesh to the given file path."""
        ...

    @property
    @abstractmethod
    def extension(self) -> str:
        """File extension for this format (without dot)."""
        ...

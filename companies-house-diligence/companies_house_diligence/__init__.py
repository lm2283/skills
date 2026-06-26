"""Companies House profile toolkit.

Phase-based corporate-structure discovery and Companies House profiling built
on the Companies House Public Data API.
"""

from .client import CompaniesHouseClient
from .graph import StructureGraph
from . import discover, enrich

__all__ = ["CompaniesHouseClient", "StructureGraph", "discover", "enrich"]

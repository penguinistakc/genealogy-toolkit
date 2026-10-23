"""Problems found in a Research Vault."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Finding:
    severity: Literal["error", "warning"]
    file: str
    """Path relative to the Vault root."""
    message: str

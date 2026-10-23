"""Stable IDs for things in the Research Vault."""

import secrets

ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


def new_id(kind: str) -> str:
    """A new random ID such as `media-7k2m9xqa`, never derived from names or content."""
    return f"{kind}-{''.join(secrets.choice(ALPHABET) for _ in range(8))}"

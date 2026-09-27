"""Medical specialties: what a patient searches by and a doctor is filed under.

Hand-curated YAML in `data/specialties.yaml`, loaded and validated by
`loader.load`. Separate from the test taxonomy, which it resembles: aliases
resolve exactly, and a word that could name two specialties never does.
"""

from ratecard.specialties.loader import (
    Category,
    Specialties,
    Specialty,
    SpecialtyError,
    load,
    specialty_key,
)

__all__ = ["Category", "Specialties", "Specialty", "SpecialtyError", "load", "specialty_key"]

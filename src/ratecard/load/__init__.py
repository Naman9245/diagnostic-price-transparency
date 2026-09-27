"""Stage 5: load the pipeline's output into Postgres.

`build` turns the taxonomy, registry and corpus into records and holds every
rule about what may become public. `db` writes them and needs psycopg; import it
only when actually writing.
"""

from ratecard.load.build import (
    LoadError,
    PriceBatch,
    PriceRecord,
    Provider,
    alias_records,
    canonical_test_records,
    load_providers,
    price_records,
    source_records,
)

__all__ = [
    "LoadError", "PriceBatch", "PriceRecord", "Provider", "alias_records",
    "canonical_test_records", "load_providers", "price_records", "source_records",
]

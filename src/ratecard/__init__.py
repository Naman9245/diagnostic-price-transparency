"""Bengaluru Rate Card: hyperlocal diagnostic price transparency.

Six stages, one direction (see docs/architecture):

    1 registry -> 2 fetch -> 3 parse -> 4 normalise -> 5 geo -> 6 api

Everything upstream of the database is a batch pipeline replayable from
immutable raw files. Stage 4 is the technical core.
"""

__version__ = "0.1.0"

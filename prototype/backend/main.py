"""RateCard demo API: the backend for the prototype.

Serves ten fictional Bengaluru hospitals, eight diagnostic tests and their
prices, and the doctors at the partner hospitals, all from mock_data.json.
Nothing is written to disk. Price edits, sign-ins and bookings live in memory
and disappear when the server restarts, which is what a demo wants.

Run it with `uvicorn main:app --reload`, then open http://localhost:8000/docs
for interactive API docs.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import admin
import auth
import bookings
import catalog

app = FastAPI(
    title="RateCard demo API",
    description="Diagnostic test prices and doctors at fictional Bengaluru hospitals. "
    "Every hospital, doctor and price here is made up for the demo.",
    version="0.1.0",
)

# The Vue dev server and the Flutter web build run on other ports, so browsers
# need CORS headers. Allowing every origin is fine for a local demo only.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
def index():
    return {"name": "RateCard demo API", "docs": "/docs", "data": "Fictional demo data"}


for module in (catalog, auth, bookings, admin):
    app.include_router(module.router)

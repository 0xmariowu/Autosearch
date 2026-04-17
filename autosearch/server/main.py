# Source: openperplex_backend_os/main.py:L14-L77 (adapted)
from fastapi import FastAPI

from autosearch import __version__

app = FastAPI(title="AutoSearch", version=__version__)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}

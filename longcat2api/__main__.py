from __future__ import annotations

import os

import uvicorn

from .server import HOST, PORT, app


def main() -> None:
    uvicorn.run(
        app,
        host=os.environ.get("LONGCAT_HOST", HOST),
        port=int(os.environ.get("LONGCAT_PORT", str(PORT))),
        log_level=os.environ.get("LONGCAT_UVICORN_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()


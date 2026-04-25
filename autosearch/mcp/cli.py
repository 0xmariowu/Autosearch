# Self-written, plan v2.3 § 13.5
import sys

import structlog


def main() -> None:
    structlog.configure(
        logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
    )
    from autosearch.mcp.server import create_server

    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()

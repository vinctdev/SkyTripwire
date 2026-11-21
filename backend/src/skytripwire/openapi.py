"""Write the OpenAPI schema as JSON, used to generate the frontend API types.

Usage: ``python -m skytripwire.openapi [OUTPUT_FILE]`` (stdout if no file is given).
The app is only created, not started: no database, no worker, no network access.
"""

import json
import sys
from pathlib import Path

from skytripwire.app import create_app
from skytripwire.config import Settings


def render() -> str:
    schema = create_app(Settings(worker_enabled=False)).openapi()
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    text = render()
    if args:
        Path(args[0]).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()

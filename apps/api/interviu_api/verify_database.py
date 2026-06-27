from __future__ import annotations

import json

from .database import database_backend_name, database_health, init_db


def main() -> None:
    init_db()
    print(
        json.dumps(
            {
                "backend": database_backend_name(),
                "health": database_health(),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

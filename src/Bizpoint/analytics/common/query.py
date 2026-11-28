from typing import Any

from sqlalchemy import text

from Bizpoint.database.connection import engine


def execute_query(
    query: str,
    parameters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Execute a read-only analytics query and return rows as dictionaries.

    Analytics queries must explicitly scope results to a dataset version.
    """

    with engine.connect() as connection:
        result = connection.execute(
            text(query),
            parameters or {},
        )

        return [
            dict(row)
            for row in result.mappings().all()
        ]

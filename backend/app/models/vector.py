"""Portable embedding column type.

Production uses PostgreSQL + pgvector (`vector(dim)`), while local development and
the test suite use SQLite, where the same column is stored as a JSON array and
cosine similarity is computed in Python (see `app/ai/retriever.py`).
"""
import json
from typing import Optional

from sqlalchemy.types import Text, TypeDecorator


class VectorType(TypeDecorator):
    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int = 1536):
        if dimensions <= 0:
            raise ValueError("Vector dimensions must be positive.")
        self.dimensions = dimensions
        super().__init__()

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Optional[list], dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps([float(v) for v in value])

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return list(value)
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None

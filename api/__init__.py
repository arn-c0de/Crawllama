"""API layer for CrawlLama.

Houses the FastAPI-facing building blocks that used to live inline in the
top-level ``app`` module: request/response models, stateless input validators
and shared limits/constants. ``app.py`` re-exports these names, so existing
imports such as ``from app import QueryRequest`` keep working.
"""

"""Normalised evidence snapshot (plan §20).

An :class:`EvidenceSnapshot` captures *what a tool retrieved* in a sanitised,
comparable form so that reasoning can be replayed against frozen inputs. Secrets
(authorization headers, cookies, API keys, query secrets) are never stored — the
recorder is responsible for stripping them before constructing a snapshot.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from arena import SCHEMA_VERSION
from arena.config import content_hash


class EvidenceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    # request identity (what was asked for)
    request_method: str = "GET"
    canonical_url: str = ""
    request_body_digest: str | None = None
    # response (what came back), sanitised
    source_url: str = ""
    http_status: int | None = None
    content_type: str | None = None
    content_digest: str = ""
    extracted_text: str = ""  # sanitised; PII-scrubbed by the recorder
    # provenance
    tool: str | None = None
    provider: str | None = None
    error: str | None = None
    cassette_version: int = 1
    recorded_at: str | None = None  # ISO-8601; injected by the recorder
    license: str | None = None

    def match_key(self) -> str:
        """Stable key for matching a replay request to this snapshot.

        Matches on method, canonical URL and request-body digest (plan §20) — not
        on volatile response fields or timestamps.
        """
        return content_hash(
            {
                "method": self.request_method.upper(),
                "url": self.canonical_url,
                "body": self.request_body_digest or "",
            }
        )


def evidence_set_hash(snapshots: list[EvidenceSnapshot]) -> str:
    """Order-independent fingerprint of an evidence set for the manifest.

    Two runs reasoning over the same evidence share this hash, which is the
    ``evidence`` comparison dimension. Empty set → empty string ("not applicable").
    """
    if not snapshots:
        return ""
    keys = sorted(s.content_digest or s.match_key() for s in snapshots)
    return content_hash(keys)

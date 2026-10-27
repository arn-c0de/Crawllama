"""Pydantic request/response models for the CrawlLama API.

Moved out of ``app.py`` so the endpoint module stays focused on wiring. The
query-bearing models share the same ``sanitize_query`` based validation.
"""
import re
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field, field_validator

from api.constants import MAX_QUERY_LENGTH
from utils.validators import sanitize_query


def _sanitize_query_input(value: str) -> str:
    """Reject empty queries and strip injection attempts (shared by all query models)."""
    if not value or not value.strip():
        raise ValueError("Query cannot be empty")
    sanitized = sanitize_query(value)
    if len(sanitized) > MAX_QUERY_LENGTH:
        raise ValueError(f"Query too long (max {MAX_QUERY_LENGTH} characters)")
    return sanitized


SanitizedQuery = Annotated[str, AfterValidator(_sanitize_query_input)]


class QueryRequest(BaseModel):
    """Query request model."""
    query: SanitizedQuery = Field(..., description="Search query", min_length=1, max_length=MAX_QUERY_LENGTH)
    use_multihop: bool = Field(False, description="Use multi-hop reasoning")
    max_hops: int | None = Field(3, description="Maximum reasoning hops", ge=1, le=5)
    use_tools: bool = Field(True, description="Enable web search tools")
    stream: bool = Field(False, description="Stream response (not yet implemented, reserved for future use)")


class QueryResponse(BaseModel):
    """Query response model."""
    answer: str
    confidence: float | None = None
    steps: int | None = None
    search_queries: list[str] | None = None
    reasoning_path: list[str] | None = None
    elapsed_time: float
    cached: bool = False


class AdaptiveQueryRequest(BaseModel):
    """Adaptive query request model."""
    query: SanitizedQuery = Field(..., description="Search query", min_length=1, max_length=MAX_QUERY_LENGTH)
    force_complexity: str | None = Field(None, description="Force complexity level: low, mid, high")
    enable_escalation: bool = Field(True, description="Enable confidence-based escalation")

    @field_validator('force_complexity')
    @classmethod
    def validate_complexity(cls, v):
        """Validate complexity level."""
        if v is not None and v.lower() not in ["low", "mid", "high"]:
            raise ValueError("force_complexity must be 'low', 'mid', or 'high'")
        return v.lower() if v else None


class AdaptiveQueryResponse(BaseModel):
    """Adaptive query response model."""
    answer: str
    confidence: float | None = None
    strategy: dict[str, Any]
    metadata: dict[str, Any]
    steps: int | None = None
    search_queries: list[str] | None = None
    reasoning_path: list[str] | None = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str
    components: dict[str, str]


class StatsResponse(BaseModel):
    """Statistics response."""
    agent_stats: dict[str, Any]
    resource_stats: dict[str, Any]
    uptime: float


class RoleAssignmentRequest(BaseModel):
    """Role assignment request model."""
    api_key_to_manage: str = Field(..., description="API key (or hash) to assign role to", min_length=8)
    role: str = Field(..., description="Role to assign: admin, user, or read_only")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        """Validate role value."""
        if v.lower() not in ["admin", "user", "read_only"]:
            raise ValueError("Role must be one of: admin, user, read_only")
        return v.lower()


class APIKeyGenerateRequest(BaseModel):
    """API key generation request."""
    user_id: str | None = Field(None, description="User ID (defaults to current user)")
    expiry_days: int | None = Field(90, description="Days until expiration (0 = no expiry)", ge=0, le=365)


class ConfigUpdateRequest(BaseModel):
    """Configuration update request model."""
    category: str = Field(..., description="Config category (llm, search, rag, cache, osint, etc.)")
    key: str = Field(..., description="Configuration key to update")
    value: Any = Field(..., description="New value")


class MemoryRequest(BaseModel):
    """Memory operation request model."""
    category: str = Field(..., max_length=50, description="Memory category (email, phone, ip, username, domain, note)")
    value: str = Field(..., max_length=MAX_QUERY_LENGTH, description="Value to remember")


class ForgetRequest(BaseModel):
    """Forget operation request model."""
    category: str | None = Field(None, description="Category to forget (email, phone, etc.) or 'all' for everything")
    value: str | None = Field(None, description="Specific value to forget")


class OSINTRequest(BaseModel):
    """OSINT query request model."""
    query: SanitizedQuery = Field(..., description="OSINT query with operators (email:, phone:, ip:, etc.)", min_length=1, max_length=MAX_QUERY_LENGTH)


class CompanyOSINTRequest(BaseModel):
    """Company OSINT request model."""
    company_name: str = Field(..., description="Company name to investigate", min_length=1, max_length=200)
    country: str | None = Field(None, description="Optional country hint (e.g., DE, US)")
    region: str | None = Field(None, description="Optional search region hint (e.g., de-de, us-en)")
    language: str | None = Field(None, description="Optional language hint (e.g., de, en)")

    @field_validator('company_name')
    @classmethod
    def sanitize_company_name(cls, v):
        """Sanitize company name input."""
        if not v or not v.strip():
            raise ValueError("Company name cannot be empty")
        sanitized = sanitize_query(v)
        if len(sanitized) > 200:
            raise ValueError("Company name too long (max 200 characters)")
        return sanitized

    @field_validator('country')
    @classmethod
    def sanitize_country(cls, v):
        """Validate optional country code (ISO-2)."""
        if v is None:
            return v
        sanitized = sanitize_query(v).upper()
        if not re.fullmatch(r"[A-Z]{2}", sanitized):
            raise ValueError("country must be ISO-2 format, e.g. DE or US")
        return sanitized

    @field_validator('region')
    @classmethod
    def sanitize_region(cls, v):
        """Validate optional region hint (xx-xx)."""
        if v is None:
            return v
        sanitized = sanitize_query(v).lower()
        if not re.fullmatch(r"[a-z]{2}-[a-z]{2}", sanitized):
            raise ValueError("region must be format xx-xx, e.g. de-de or us-en")
        return sanitized

    @field_validator('language')
    @classmethod
    def sanitize_language(cls, v):
        """Validate optional language code (ISO-2)."""
        if v is None:
            return v
        sanitized = sanitize_query(v).lower()
        if not re.fullmatch(r"[a-z]{2}", sanitized):
            raise ValueError("language must be ISO-2 format, e.g. de or en")
        return sanitized

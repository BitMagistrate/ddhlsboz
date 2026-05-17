"""RFC 7807 error envelopes for RoadPulse public APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ERROR_DOMAIN = "https://errors.roadpulse.vn"


class ProblemDetails(BaseModel):
    """RFC 7807 ``application/problem+json`` payload."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(default=f"{ERROR_DOMAIN}/about:blank")
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    trace_id: str | None = None


class RoadPulseError(Exception):
    """Base class for RoadPulse domain errors.

    Each subclass should set ``title``, ``status_code`` and ``error_type``. Use
    :meth:`to_problem` to produce a public-facing :class:`ProblemDetails` payload that
    the FastAPI exception handler can serialise verbatim.
    """

    status_code: int = 500
    title: str = "Internal Server Error"
    error_type: str = f"{ERROR_DOMAIN}/internal"

    def __init__(self, detail: str | None = None, **extras: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        self.extras: dict[str, Any] = extras

    def to_problem(
        self,
        *,
        instance: str | None = None,
        trace_id: str | None = None,
    ) -> ProblemDetails:
        return ProblemDetails(
            type=self.error_type,
            title=self.title,
            status=self.status_code,
            detail=self.detail,
            instance=instance,
            trace_id=trace_id,
            **self.extras,
        )


class ValidationProblem(RoadPulseError):
    """Raised when input fails Pydantic / business rule validation."""

    status_code = 422
    title = "Validation failed"
    error_type = f"{ERROR_DOMAIN}/validation"


class QuotaExceededError(RoadPulseError):
    """Raised when an API key exceeds its rate-limit or daily quota."""

    status_code = 429
    title = "Quota exceeded"
    error_type = f"{ERROR_DOMAIN}/quota-exceeded"


class PrivacyViolationError(RoadPulseError):
    """Raised when a bucket fails the k-anonymity guard."""

    status_code = 422
    title = "Bucket failed k-anonymity guard"
    error_type = f"{ERROR_DOMAIN}/privacy/k-anon"


class UnknownResourceError(RoadPulseError):
    """Raised when a resource (route, hex, policy) cannot be located."""

    status_code = 404
    title = "Resource not found"
    error_type = f"{ERROR_DOMAIN}/not-found"

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


JobStatus = Literal[
    "review_queued",
    "review_running",
    "review_ready",
    "import_queued",
    "import_running",
    "completed",
    "failed",
]


class CredentialPayload(BaseModel):
    cloudahoy_username: str
    cloudahoy_password: str
    flysto_username: str
    flysto_password: str


class JobCreateRequest(BaseModel):
    credentials: CredentialPayload
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    max_flights: Optional[int] = None


class JobAcceptRequest(BaseModel):
    credentials: CredentialPayload


class FlightSummary(BaseModel):
    flight_id: str
    date: str
    tail_number: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    flight_time_minutes: Optional[int] = None
    status: Optional[str] = None
    message: Optional[str] = None


class ReviewSummary(BaseModel):
    flight_count: int
    total_hours: float
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    missing_tail_numbers: int = 0
    flights: list[FlightSummary] = Field(default_factory=list)


class ImportReport(BaseModel):
    imported_count: int
    skipped_count: int
    failed_count: int


class JobRecord(BaseModel):
    job_id: UUID
    user_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress_percent: Optional[int] = None
    progress_stage: Optional[str] = None
    review_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    max_flights: Optional[int] = None
    review_summary: Optional[ReviewSummary] = None
    import_report: Optional[ImportReport] = None
    error_message: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: list[JobRecord]


class ArtifactListResponse(BaseModel):
    artifacts: list[str]

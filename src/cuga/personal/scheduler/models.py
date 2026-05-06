"""Scheduler data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel

from cuga.personal.gateway.base import DeliveryTarget


class JobState(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ScheduledJob(BaseModel):
    id: str
    name: str
    schedule: str  # cron expression, e.g. "0 16 * * 5"
    skill_name: str
    prompt: str  # message sent to the agent when the job fires
    user_id: str
    delivery: DeliveryTarget  # where to send results
    state: JobState = JobState.ACTIVE
    repeat: int = -1  # -1 = infinite, N = run N times then complete
    runs_completed: int = 0
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime
    metadata: Dict[str, Any] = {}

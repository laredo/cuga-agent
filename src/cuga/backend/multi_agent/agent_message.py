"""Inter-agent message envelope."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AgentMessage:
    sender: str
    recipient: str
    task_id: str
    payload: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

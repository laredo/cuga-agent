"""
Approval System for CUGA event-driven architecture

Implements human-in-the-loop workflows for dangerous or sensitive actions.
Integrates with LangGraph's interrupt pattern for checkpoint/resume functionality.

Key Features:
- Policy-based approval requirements
- Multi-channel notifications (Slack, Email, Web, CLI)
- Async approval waiting with timeout
- Checkpoint/resume support for LangGraph
- Approval history and audit trail
- Flexible approval policies with pattern matching
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, ConfigDict, Field
import asyncio
import uuid
import fnmatch

from cuga.backend.events.models import Event


class ApprovalStatus(str, Enum):
    """Status of an approval request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ApprovalChannel(str, Enum):
    """Channels for approval notifications"""
    SLACK = "slack"
    EMAIL = "email"
    WEB = "web"
    CLI = "cli"


class ApprovalTimeoutError(Exception):
    """Raised when approval request times out"""
    pass


class ApprovalRejectedError(Exception):
    """Raised when approval request is rejected"""
    pass


class ApprovalRequest(BaseModel):
    """
    Request for approval of an action
    
    Attributes:
        request_id: Unique request identifier
        action: Action requiring approval
        description: Human-readable description
        requester: Who/what is requesting approval
        channels: Channels to notify for approval
        status: Current approval status
        timeout_seconds: Timeout for approval
        created_at: When request was created
        context: Additional context for the request
        response: Approval response (if any)
    """
    
    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}
    )
    
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str
    description: str
    requester: str
    channels: List[ApprovalChannel] = Field(
        default_factory=lambda: [ApprovalChannel.SLACK, ApprovalChannel.EMAIL]
    )
    status: ApprovalStatus = ApprovalStatus.PENDING
    timeout_seconds: int = 3600  # 1 hour default
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = Field(default_factory=dict)
    response: Optional['ApprovalResponse'] = None
    
    def is_expired(self) -> bool:
        """
        Check if request has expired
        
        Returns:
            True if expired, False otherwise
        """
        elapsed = datetime.now(timezone.utc) - self.created_at
        return elapsed.total_seconds() > self.timeout_seconds
    
    def is_pending(self) -> bool:
        """
        Check if request is still pending
        
        Returns:
            True if pending, False otherwise
        """
        return self.status == ApprovalStatus.PENDING


class ApprovalResponse(BaseModel):
    """
    Response to an approval request
    
    Attributes:
        request_id: ID of the request being responded to
        status: Approval status (approved/rejected)
        approver: Who approved/rejected
        message: Optional message from approver
        responded_at: When response was given
        metadata: Additional response metadata
    """
    
    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}
    )
    
    request_id: str
    status: ApprovalStatus
    approver: str
    message: Optional[str] = None
    responded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalPolicy(BaseModel):
    """
    Policy defining approval requirements
    
    Attributes:
        name: Policy name
        actions: List of action patterns requiring approval (supports wildcards)
        required: Whether approval is required
        channels: Preferred notification channels
        timeout_seconds: Default timeout for approvals
        description: Policy description
    """
    
    name: str
    actions: List[str]
    required: bool = True
    channels: List[ApprovalChannel] = Field(
        default_factory=lambda: [ApprovalChannel.SLACK, ApprovalChannel.EMAIL]
    )
    timeout_seconds: int = 3600
    description: Optional[str] = None
    
    def matches_action(self, action: str) -> bool:
        """
        Check if this policy matches an action
        
        Args:
            action: Action to check
            
        Returns:
            True if policy matches, False otherwise
        """
        for pattern in self.actions:
            if fnmatch.fnmatch(action, pattern):
                return True
        return False


class ApprovalManager:
    """
    Manages approval requests and policies
    
    The ApprovalManager coordinates approval workflows, including request
    creation, policy matching, approval/rejection, and timeout handling.
    
    Example:
        >>> manager = ApprovalManager()
        >>> policy = ApprovalPolicy(name="delete", actions=["delete_*"])
        >>> manager.register_policy(policy)
        >>> request = manager.create_request(
        ...     action="delete_database",
        ...     description="Delete prod DB",
        ...     requester="agent"
        ... )
        >>> response = await manager.wait_for_approval(request.request_id)
    """
    
    def __init__(self):
        """Initialize the approval manager"""
        self.requests: Dict[str, ApprovalRequest] = {}
        self.policies: List[ApprovalPolicy] = []
        self._approval_events: Dict[str, asyncio.Event] = {}
    
    def register_policy(self, policy: ApprovalPolicy) -> None:
        """
        Register an approval policy
        
        Args:
            policy: Policy to register
        """
        self.policies.append(policy)
    
    def get_policy_for_action(self, action: str) -> Optional[ApprovalPolicy]:
        """
        Get the policy that matches an action
        
        Args:
            action: Action to check
            
        Returns:
            Matching policy if found, None otherwise
        """
        for policy in self.policies:
            if policy.matches_action(action):
                return policy
        return None
    
    def requires_approval(self, action: str) -> bool:
        """
        Check if an action requires approval
        
        Args:
            action: Action to check
            
        Returns:
            True if approval required, False otherwise
        """
        policy = self.get_policy_for_action(action)
        return policy is not None and policy.required
    
    def create_request(
        self,
        action: str,
        description: str,
        requester: str,
        context: Optional[Dict[str, Any]] = None,
        channels: Optional[List[ApprovalChannel]] = None,
        timeout_seconds: Optional[int] = None
    ) -> ApprovalRequest:
        """
        Create an approval request
        
        Args:
            action: Action requiring approval
            description: Description of the action
            requester: Who is requesting approval
            context: Additional context
            channels: Notification channels
            timeout_seconds: Timeout for approval
            
        Returns:
            Created approval request
        """
        # Get policy for action
        policy = self.get_policy_for_action(action)
        
        # Use policy defaults if available
        if channels is None and policy:
            channels = policy.channels
        if timeout_seconds is None and policy:
            timeout_seconds = policy.timeout_seconds
        
        # Create request
        request = ApprovalRequest(
            action=action,
            description=description,
            requester=requester,
            context=context or {},
            channels=channels or [ApprovalChannel.SLACK, ApprovalChannel.EMAIL],
            timeout_seconds=timeout_seconds or 3600
        )
        
        # Store request
        self.requests[request.request_id] = request
        
        # Create event for async waiting
        self._approval_events[request.request_id] = asyncio.Event()
        
        return request
    
    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """
        Get a request by ID
        
        Args:
            request_id: Request identifier
            
        Returns:
            Request if found, None otherwise
        """
        return self.requests.get(request_id)
    
    def approve_request(
        self,
        request_id: str,
        approver: str,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ApprovalResponse:
        """
        Approve a request
        
        Args:
            request_id: Request identifier
            approver: Who is approving
            message: Optional approval message
            metadata: Optional metadata
            
        Returns:
            Approval response
        """
        request = self.requests.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        # Create response
        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.APPROVED,
            approver=approver,
            message=message,
            metadata=metadata or {}
        )
        
        # Update request
        request.status = ApprovalStatus.APPROVED
        request.response = response
        
        # Signal waiting coroutines
        if request_id in self._approval_events:
            self._approval_events[request_id].set()
        
        return response
    
    def reject_request(
        self,
        request_id: str,
        approver: str,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ApprovalResponse:
        """
        Reject a request
        
        Args:
            request_id: Request identifier
            approver: Who is rejecting
            message: Optional rejection message
            metadata: Optional metadata
            
        Returns:
            Rejection response
        """
        request = self.requests.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        # Create response
        response = ApprovalResponse(
            request_id=request_id,
            status=ApprovalStatus.REJECTED,
            approver=approver,
            message=message,
            metadata=metadata or {}
        )
        
        # Update request
        request.status = ApprovalStatus.REJECTED
        request.response = response
        
        # Signal waiting coroutines
        if request_id in self._approval_events:
            self._approval_events[request_id].set()
        
        return response
    
    async def wait_for_approval(
        self,
        request_id: str,
        timeout: Optional[float] = None
    ) -> ApprovalResponse:
        """
        Wait for approval of a request
        
        Args:
            request_id: Request identifier
            timeout: Optional timeout in seconds
            
        Returns:
            Approval response
            
        Raises:
            ApprovalTimeoutError: If request times out
            ApprovalRejectedError: If request is rejected
        """
        request = self.requests.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        # Get or create event
        if request_id not in self._approval_events:
            self._approval_events[request_id] = asyncio.Event()
        
        event = self._approval_events[request_id]
        
        # Wait for approval with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            request.status = ApprovalStatus.TIMEOUT
            raise ApprovalTimeoutError(f"Approval request {request_id} timed out")
        
        # Check result
        if request.status == ApprovalStatus.APPROVED:
            return request.response
        elif request.status == ApprovalStatus.REJECTED:
            raise ApprovalRejectedError(
                f"Approval request {request_id} was rejected: {request.response.message}"
            )
        else:
            raise ApprovalTimeoutError(f"Approval request {request_id} timed out")
    
    def cleanup_expired_requests(self) -> int:
        """
        Clean up expired requests
        
        Returns:
            Number of requests cleaned up
        """
        expired_ids = []
        
        for request_id, request in self.requests.items():
            if request.is_expired() and request.is_pending():
                request.status = ApprovalStatus.TIMEOUT
                expired_ids.append(request_id)
        
        # Remove expired requests
        for request_id in expired_ids:
            del self.requests[request_id]
            if request_id in self._approval_events:
                del self._approval_events[request_id]
        
        return len(expired_ids)
    
    def get_pending_requests(self) -> List[ApprovalRequest]:
        """
        Get all pending requests
        
        Returns:
            List of pending requests
        """
        return [r for r in self.requests.values() if r.is_pending()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get approval statistics
        
        Returns:
            Dictionary containing statistics
        """
        pending = [r for r in self.requests.values() if r.status == ApprovalStatus.PENDING]
        approved = [r for r in self.requests.values() if r.status == ApprovalStatus.APPROVED]
        rejected = [r for r in self.requests.values() if r.status == ApprovalStatus.REJECTED]
        timeout = [r for r in self.requests.values() if r.status == ApprovalStatus.TIMEOUT]
        
        return {
            "total_requests": len(self.requests),
            "pending_requests": len(pending),
            "approved_requests": len(approved),
            "rejected_requests": len(rejected),
            "timeout_requests": len(timeout),
            "total_policies": len(self.policies)
        }

# Made with Bob

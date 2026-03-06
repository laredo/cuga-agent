"""
Unit tests for Approval System
Following TDD approach - tests for human-in-the-loop workflows with LangGraph integration
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from cuga.backend.events.approval_system import (
    ApprovalStatus,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalManager,
    ApprovalPolicy,
    ApprovalChannel,
    ApprovalTimeoutError,
    ApprovalRejectedError
)
from cuga.backend.events.models import Event, EventType, EventSource


class TestApprovalStatus:
    """Test ApprovalStatus enum"""
    
    def test_approval_status_values(self):
        """Test all approval statuses are defined"""
        assert ApprovalStatus.PENDING == "pending"
        assert ApprovalStatus.APPROVED == "approved"
        assert ApprovalStatus.REJECTED == "rejected"
        assert ApprovalStatus.TIMEOUT == "timeout"
    
    def test_approval_status_membership(self):
        """Test approval status membership"""
        assert "pending" in [s.value for s in ApprovalStatus]
        assert "approved" in [s.value for s in ApprovalStatus]


class TestApprovalChannel:
    """Test ApprovalChannel enum"""
    
    def test_approval_channel_values(self):
        """Test all approval channels are defined"""
        assert ApprovalChannel.SLACK == "slack"
        assert ApprovalChannel.EMAIL == "email"
        assert ApprovalChannel.WEB == "web"
        assert ApprovalChannel.CLI == "cli"


class TestApprovalRequest:
    """Test ApprovalRequest model"""
    
    def test_approval_request_creation(self):
        """Test creating an approval request"""
        request = ApprovalRequest(
            action="delete_database",
            description="Delete production database",
            requester="agent",
            channels=[ApprovalChannel.SLACK, ApprovalChannel.EMAIL]
        )
        
        assert request.action == "delete_database"
        assert request.description == "Delete production database"
        assert request.requester == "agent"
        assert len(request.channels) == 2
        assert request.status == ApprovalStatus.PENDING
        assert request.timeout_seconds == 3600
        assert isinstance(request.created_at, datetime)
    
    def test_approval_request_with_context(self):
        """Test creating request with context"""
        context = {"database": "prod", "records": 1000000}
        request = ApprovalRequest(
            action="delete_records",
            description="Delete records",
            requester="agent",
            context=context
        )
        
        assert request.context == context
    
    def test_approval_request_with_custom_timeout(self):
        """Test creating request with custom timeout"""
        request = ApprovalRequest(
            action="test_action",
            description="Test",
            requester="agent",
            timeout_seconds=300
        )
        
        assert request.timeout_seconds == 300
    
    def test_approval_request_is_expired(self):
        """Test checking if request is expired"""
        request = ApprovalRequest(
            action="test",
            description="Test",
            requester="agent",
            timeout_seconds=60
        )
        
        # Fresh request should not be expired
        assert request.is_expired() is False
        
        # Manually set old created_at
        request.created_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        
        # Should be expired now
        assert request.is_expired() is True
    
    def test_approval_request_is_pending(self):
        """Test checking if request is pending"""
        request = ApprovalRequest(
            action="test",
            description="Test",
            requester="agent"
        )
        
        assert request.is_pending() is True
        
        request.status = ApprovalStatus.APPROVED
        assert request.is_pending() is False


class TestApprovalResponse:
    """Test ApprovalResponse model"""
    
    def test_approval_response_approved(self):
        """Test creating an approved response"""
        response = ApprovalResponse(
            request_id="req-123",
            status=ApprovalStatus.APPROVED,
            approver="user@example.com",
            message="Approved for testing"
        )
        
        assert response.request_id == "req-123"
        assert response.status == ApprovalStatus.APPROVED
        assert response.approver == "user@example.com"
        assert response.message == "Approved for testing"
        assert isinstance(response.responded_at, datetime)
    
    def test_approval_response_rejected(self):
        """Test creating a rejected response"""
        response = ApprovalResponse(
            request_id="req-456",
            status=ApprovalStatus.REJECTED,
            approver="admin@example.com",
            message="Too risky"
        )
        
        assert response.status == ApprovalStatus.REJECTED
        assert response.message == "Too risky"
    
    def test_approval_response_with_metadata(self):
        """Test creating response with metadata"""
        metadata = {"ip": "192.168.1.1", "location": "office"}
        response = ApprovalResponse(
            request_id="req-789",
            status=ApprovalStatus.APPROVED,
            approver="user",
            metadata=metadata
        )
        
        assert response.metadata == metadata


class TestApprovalPolicy:
    """Test ApprovalPolicy model"""
    
    def test_approval_policy_creation(self):
        """Test creating an approval policy"""
        policy = ApprovalPolicy(
            name="dangerous_actions",
            actions=["delete_*", "drop_*"],
            required=True
        )
        
        assert policy.name == "dangerous_actions"
        assert len(policy.actions) == 2
        assert policy.required is True
        assert policy.timeout_seconds == 3600
    
    def test_approval_policy_matches_action(self):
        """Test checking if policy matches an action"""
        policy = ApprovalPolicy(
            name="delete_policy",
            actions=["delete_*", "remove_*"]
        )
        
        assert policy.matches_action("delete_database") is True
        assert policy.matches_action("remove_file") is True
        assert policy.matches_action("create_table") is False
    
    def test_approval_policy_exact_match(self):
        """Test exact action matching"""
        policy = ApprovalPolicy(
            name="specific_policy",
            actions=["delete_production_db"]
        )
        
        assert policy.matches_action("delete_production_db") is True
        assert policy.matches_action("delete_staging_db") is False
    
    def test_approval_policy_with_channels(self):
        """Test policy with specific channels"""
        policy = ApprovalPolicy(
            name="critical_policy",
            actions=["shutdown_*"],
            channels=[ApprovalChannel.SLACK, ApprovalChannel.EMAIL]
        )
        
        assert len(policy.channels) == 2
        assert ApprovalChannel.SLACK in policy.channels


class TestApprovalManager:
    """Test ApprovalManager functionality"""
    
    def test_approval_manager_creation(self):
        """Test creating an approval manager"""
        manager = ApprovalManager()
        
        assert len(manager.requests) == 0
        assert len(manager.policies) == 0
    
    def test_register_policy(self):
        """Test registering an approval policy"""
        manager = ApprovalManager()
        
        policy = ApprovalPolicy(
            name="delete_policy",
            actions=["delete_*"]
        )
        
        manager.register_policy(policy)
        
        assert len(manager.policies) == 1
        assert manager.policies[0].name == "delete_policy"
    
    def test_get_policy_for_action(self):
        """Test getting policy for an action"""
        manager = ApprovalManager()
        
        policy1 = ApprovalPolicy(name="delete", actions=["delete_*"])
        policy2 = ApprovalPolicy(name="create", actions=["create_*"])
        
        manager.register_policy(policy1)
        manager.register_policy(policy2)
        
        matched = manager.get_policy_for_action("delete_database")
        
        assert matched is not None
        assert matched.name == "delete"
    
    def test_requires_approval(self):
        """Test checking if action requires approval"""
        manager = ApprovalManager()
        
        policy = ApprovalPolicy(
            name="dangerous",
            actions=["delete_*", "drop_*"],
            required=True
        )
        
        manager.register_policy(policy)
        
        assert manager.requires_approval("delete_table") is True
        assert manager.requires_approval("create_table") is False
    
    def test_create_approval_request(self):
        """Test creating an approval request"""
        manager = ApprovalManager()
        
        request = manager.create_request(
            action="delete_database",
            description="Delete prod DB",
            requester="agent"
        )
        
        assert request.action == "delete_database"
        assert request.status == ApprovalStatus.PENDING
        assert request.request_id in manager.requests
    
    def test_get_request(self):
        """Test retrieving a request"""
        manager = ApprovalManager()
        
        request = manager.create_request(
            action="test_action",
            description="Test",
            requester="agent"
        )
        
        retrieved = manager.get_request(request.request_id)
        
        assert retrieved is not None
        assert retrieved.request_id == request.request_id
    
    def test_approve_request(self):
        """Test approving a request"""
        manager = ApprovalManager()
        
        request = manager.create_request(
            action="delete_file",
            description="Delete temp file",
            requester="agent"
        )
        
        response = manager.approve_request(
            request_id=request.request_id,
            approver="user@example.com",
            message="Approved"
        )
        
        assert response.status == ApprovalStatus.APPROVED
        assert request.status == ApprovalStatus.APPROVED
        assert request.response == response
    
    def test_reject_request(self):
        """Test rejecting a request"""
        manager = ApprovalManager()
        
        request = manager.create_request(
            action="dangerous_action",
            description="Risky operation",
            requester="agent"
        )
        
        response = manager.reject_request(
            request_id=request.request_id,
            approver="admin@example.com",
            message="Too dangerous"
        )
        
        assert response.status == ApprovalStatus.REJECTED
        assert request.status == ApprovalStatus.REJECTED
    
    async def test_wait_for_approval_approved(self):
        """Test waiting for approval that gets approved"""
        manager = ApprovalManager()
        
        request = manager.create_request(
            action="test",
            description="Test",
            requester="agent"
        )
        
        # Simulate approval in background
        import asyncio
        async def approve_later():
            await asyncio.sleep(0.1)
            manager.approve_request(request.request_id, "user", "OK")
        
        asyncio.create_task(approve_later())
        
        # Wait for approval
        result = await manager.wait_for_approval(request.request_id, timeout=1.0)
        
        assert result.status == ApprovalStatus.APPROVED
    
    async def test_wait_for_approval_rejected(self):
        """Test waiting for approval that gets rejected"""
        manager = ApprovalManager()
        
        request = manager.create_request(
            action="test",
            description="Test",
            requester="agent"
        )
        
        # Simulate rejection in background
        import asyncio
        async def reject_later():
            await asyncio.sleep(0.1)
            manager.reject_request(request.request_id, "user", "No")
        
        asyncio.create_task(reject_later())
        
        # Wait for approval - should raise exception
        with pytest.raises(ApprovalRejectedError):
            await manager.wait_for_approval(request.request_id, timeout=1.0)
    
    async def test_wait_for_approval_timeout(self):
        """Test waiting for approval that times out"""
        manager = ApprovalManager()
        
        request = manager.create_request(
            action="test",
            description="Test",
            requester="agent"
        )
        
        # Wait for approval with short timeout
        with pytest.raises(ApprovalTimeoutError):
            await manager.wait_for_approval(request.request_id, timeout=0.1)
    
    def test_cleanup_expired_requests(self):
        """Test cleaning up expired requests"""
        manager = ApprovalManager()
        
        # Create requests
        request1 = manager.create_request(
            action="test1",
            description="Test 1",
            requester="agent",
            timeout_seconds=60
        )
        request2 = manager.create_request(
            action="test2",
            description="Test 2",
            requester="agent",
            timeout_seconds=60
        )
        
        # Manually expire request1
        request1.created_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        
        # Cleanup
        cleaned = manager.cleanup_expired_requests()
        
        assert cleaned == 1
        assert len(manager.requests) == 1
        assert request2.request_id in manager.requests
    
    def test_get_pending_requests(self):
        """Test getting all pending requests"""
        manager = ApprovalManager()
        
        request1 = manager.create_request(
            action="test1",
            description="Test 1",
            requester="agent"
        )
        request2 = manager.create_request(
            action="test2",
            description="Test 2",
            requester="agent"
        )
        
        # Approve one
        manager.approve_request(request1.request_id, "user", "OK")
        
        pending = manager.get_pending_requests()
        
        assert len(pending) == 1
        assert pending[0].request_id == request2.request_id
    
    def test_get_statistics(self):
        """Test getting approval statistics"""
        manager = ApprovalManager()
        
        request1 = manager.create_request(
            action="test1",
            description="Test 1",
            requester="agent"
        )
        request2 = manager.create_request(
            action="test2",
            description="Test 2",
            requester="agent"
        )
        request3 = manager.create_request(
            action="test3",
            description="Test 3",
            requester="agent"
        )
        
        manager.approve_request(request1.request_id, "user", "OK")
        manager.reject_request(request2.request_id, "user", "No")
        
        stats = manager.get_statistics()
        
        assert stats["total_requests"] == 3
        assert stats["pending_requests"] == 1
        assert stats["approved_requests"] == 1
        assert stats["rejected_requests"] == 1


class TestApprovalIntegration:
    """Integration tests for approval system"""
    
    async def test_full_approval_workflow(self):
        """Test complete approval workflow"""
        manager = ApprovalManager()
        
        # Register policy
        policy = ApprovalPolicy(
            name="delete_policy",
            actions=["delete_*"],
            required=True,
            channels=[ApprovalChannel.SLACK]
        )
        manager.register_policy(policy)
        
        # Check if action requires approval
        assert manager.requires_approval("delete_database") is True
        
        # Create approval request
        request = manager.create_request(
            action="delete_database",
            description="Delete production database",
            requester="agent",
            context={"database": "prod", "records": 1000000}
        )
        
        assert request.status == ApprovalStatus.PENDING
        
        # Simulate approval
        import asyncio
        async def approve_later():
            await asyncio.sleep(0.1)
            manager.approve_request(
                request.request_id,
                "admin@example.com",
                "Approved after review"
            )
        
        asyncio.create_task(approve_later())
        
        # Wait for approval
        response = await manager.wait_for_approval(request.request_id, timeout=1.0)
        
        assert response.status == ApprovalStatus.APPROVED
        assert request.status == ApprovalStatus.APPROVED
        
        # Check statistics
        stats = manager.get_statistics()
        assert stats["approved_requests"] == 1

# Made with Bob

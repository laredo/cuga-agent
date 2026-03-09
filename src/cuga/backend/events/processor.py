"""Generic event processor that routes to integration-specific processors"""

from typing import Dict, Optional, Callable, Awaitable
from loguru import logger

from cuga.backend.events.models import Event, EventType
from cuga.backend.events.session_management import SessionRouter, SessionContext


class EventProcessor:
    """Generic event processor that routes events to integration-specific processors
    
    This processor:
    1. Routes events to appropriate sessions (main/isolated)
    2. Delegates to integration-specific processors based on event type
    3. Handles errors and logging
    """
    
    def __init__(self, session_router: SessionRouter):
        """Initialize event processor
        
        Args:
            session_router: Router for session management
        """
        self.session_router = session_router
        self._processors: Dict[EventType, Callable[[Event, SessionContext], Awaitable[None]]] = {}
    
    def register_processor(
        self,
        event_type: EventType,
        processor_func: Callable[[Event, SessionContext], Awaitable[None]]
    ):
        """Register an integration-specific processor
        
        Args:
            event_type: Type of events to handle
            processor_func: Async function that processes events of this type
        """
        self._processors[event_type] = processor_func
        logger.info(f"Registered processor for {event_type} events")
    
    async def process_event(self, event: Event):
        """Process a single event
        
        Args:
            event: Event to process
        """
        logger.info(
            f"Processing event: {event.event_name} "
            f"(id={event.id}, type={event.type}, source={event.source})"
        )
        
        try:
            # Route to appropriate session
            session_context = self.session_router.route_event(event)
            logger.debug(
                f"Event routed to {session_context.session_type} session "
                f"(thread_id={session_context.thread_id})"
            )
            
            # Delegate to integration-specific processor
            processor = self._processors.get(event.type)
            if processor:
                await processor(event, session_context)
            else:
                logger.warning(
                    f"No processor registered for event type: {event.type}. "
                    f"Event will be ignored."
                )
        
        except Exception as e:
            logger.error(f"Error processing event {event.id}: {e}", exc_info=True)
    
    def get_registered_types(self) -> list[EventType]:
        """Get list of registered event types
        
        Returns:
            List of event types that have registered processors
        """
        return list(self._processors.keys())

# Made with Bob

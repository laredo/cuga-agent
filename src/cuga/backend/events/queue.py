"""Event queue for async event processing"""

import asyncio
from typing import Optional, Callable, Awaitable
from loguru import logger

from cuga.backend.events.models import Event


class EventQueue:
    """Simple in-memory event queue for async processing
    
    This is a simple implementation suitable for single-instance deployments.
    For production multi-instance deployments, consider using Redis or RabbitMQ.
    """
    
    def __init__(self, max_size: int = 1000):
        """Initialize event queue
        
        Args:
            max_size: Maximum queue size (default 1000)
        """
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_size)
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False
        self._processed_count = 0
        self._error_count = 0
    
    async def enqueue(self, event: Event):
        """Add event to queue
        
        Args:
            event: Event to enqueue
            
        Raises:
            asyncio.QueueFull: If queue is full
        """
        await self.queue.put(event)
        logger.info(
            f"Enqueued event: {event.event_name} "
            f"(id={event.id}, type={event.type}, queue_size={self.queue.qsize()})"
        )
    
    async def dequeue(self) -> Event:
        """Get next event from queue
        
        Returns:
            Next event in queue
        """
        return await self.queue.get()
    
    def start_processor(self, processor_func: Callable[[Event], Awaitable[None]]):
        """Start background event processor
        
        Args:
            processor_func: Async function that processes events
        """
        if self._running:
            logger.warning("Event processor already running")
            return
        
        self._running = True
        self._processor_task = asyncio.create_task(
            self._process_loop(processor_func)
        )
        logger.info("✅ Event processor started")
    
    async def _process_loop(self, processor_func: Callable[[Event], Awaitable[None]]):
        """Background loop that processes events
        
        Args:
            processor_func: Async function that processes events
        """
        while self._running:
            try:
                event = await self.dequeue()
                
                try:
                    await processor_func(event)
                    self._processed_count += 1
                    logger.debug(
                        f"Event processed successfully: {event.id} "
                        f"(total processed: {self._processed_count})"
                    )
                except Exception as e:
                    self._error_count += 1
                    logger.error(
                        f"Error processing event {event.id}: {e} "
                        f"(total errors: {self._error_count})"
                    )
                finally:
                    # Mark task as done
                    self.queue.task_done()
                    
            except asyncio.CancelledError:
                logger.info("Event processor cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in event processor: {e}")
                # Continue processing other events
                await asyncio.sleep(1)
    
    async def stop(self):
        """Stop the event processor gracefully"""
        if not self._running:
            return
        
        logger.info("Stopping event processor...")
        self._running = False
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        logger.info(
            f"Event processor stopped "
            f"(processed: {self._processed_count}, errors: {self._error_count})"
        )
    
    def get_stats(self) -> dict:
        """Get queue statistics
        
        Returns:
            Dictionary with queue statistics
        """
        return {
            "queue_size": self.queue.qsize(),
            "max_size": self.queue.maxsize,
            "running": self._running,
            "processed_count": self._processed_count,
            "error_count": self._error_count
        }
    
    async def wait_empty(self, timeout: Optional[float] = None):
        """Wait for queue to be empty
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Raises:
            asyncio.TimeoutError: If timeout is reached
        """
        if timeout:
            await asyncio.wait_for(self.queue.join(), timeout=timeout)
        else:
            await self.queue.join()

# Made with Bob

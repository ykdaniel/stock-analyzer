from typing import Any, Optional
import logging
from .interfaces import BrowserDriverInterface
from .telemetry import telemetry
from ..models.telemetry_events import TelemetryEvent, SignalSeverity
from datetime import datetime

logger = logging.getLogger("resilience_adapter.anchor")

class AnchorValidator:
    """
    Verifies that the response is structurally anchored to a User Message.
    Prevents hallucinating context or picking up stale responses.
    """
    def __init__(self, driver: BrowserDriverInterface):
        self.driver = driver

    async def validate_response_continuity(self, user_element: Any, response_element: Any) -> bool:
        """
        Checks if the response_element strictly follows the user_element in the conversation flow.
        This usually means they are siblings or in a container sequence.
        """
        # We use execute_script to check DOM position safely
        script = """
        (args) => {
            const [userEl, responseEl] = args;
            // Simple check: Response should be after User in document order
            // And ideally, close to it.
            const userRect = userEl.getBoundingClientRect();
            const respRect = responseEl.getBoundingClientRect();
            
            // Basic heuristic: Response top should be >= User bottom
            if (respRect.top < userRect.bottom) return false;
            
            // Structural check: Are they in the same container?
            // This is hard to generalize without specific DOM knowledge, 
            // but we can check if they share a common ancestor within N levels.
            
            return true; // For now, assume if selectors matched, we just sanity check order.
        }
        """
        # Note: Implementation details depend on how the driver passes arguments to execute_script.
        # Assuming Playwright-style params ([el1, el2]).
        try:
            is_valid = await self.driver.execute_script(script, [user_element, response_element])
            
            if not is_valid:
                telemetry.log_event(TelemetryEvent(
                    timestamp=datetime.now(),
                    component="AnchorValidator",
                    event_type="AnchorMismatch",
                    severity=SignalSeverity.ERROR,
                    details={"reason": "DOM Order Mismatch"}
                ))
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating anchor: {e}")
            return False # Fail safe

    async def find_last_user_message(self, selector_result) -> Optional[Any]:
        # Implementation depends on how we define the user message selector.
        # This is just a placeholder logic.
        pass

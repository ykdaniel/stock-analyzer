import asyncio
import time
import logging
from .interfaces import BrowserDriverInterface
from .telemetry import telemetry
from ..models.telemetry_events import TelemetryEvent, SignalSeverity
from typing import Any
from datetime import datetime

logger = logging.getLogger("resilience_adapter.convergence")

class ConvergenceEngine:
    """
    Handles streaming responses by sampling until semantic convergence.
    """
    def __init__(self, driver: BrowserDriverInterface):
        self.driver = driver
        self.min_length_threshold = 10
        self.stable_checks_required = 3
        self.check_interval_sec = 0.5
        self.max_wait_sec = 60

    async def wait_for_convergence(self, element: Any) -> str:
        """
        Samples the text of the element until it stops changing.
        """
        start_time = time.time()
        last_text = ""
        stable_count = 0
        
        while time.time() - start_time < self.max_wait_sec:
            current_text = await self.driver.get_text(element)
            
            if len(current_text) < self.min_length_threshold:
                # Too short, probably starting
                stable_count = 0 
            elif current_text == last_text:
                stable_count += 1
                if not current_text.endswith("...") and stable_count >= self.stable_checks_required:
                    # Converged
                    duration = time.time() - start_time
                    telemetry.log_event(TelemetryEvent(
                        timestamp=datetime.now(),
                        component="ConvergenceEngine",
                        event_type="Converged",
                        severity=SignalSeverity.INFO,
                        details={"duration": duration, "length": len(current_text)}
                    ))
                    return current_text
            else:
                stable_count = 0
            
            last_text = current_text
            await asyncio.sleep(self.check_interval_sec)

        # Timeout
        logger.warning("Convergence timed out. Returning partial result.")
        telemetry.log_event(TelemetryEvent(
            timestamp=datetime.now(),
            component="ConvergenceEngine",
            event_type="Timeout",
            severity=SignalSeverity.WARNING,
            details={"partial_length": len(last_text)}
        ))
        return last_text

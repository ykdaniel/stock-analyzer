import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from ..models.telemetry_events import TelemetryEvent, SignalSeverity, TierUsageEvent

# Setup standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("resilience_adapter")

class TelemetryEngine:
    """
    Central telemetry engine to capture degradation signals and health metrics.
    Designed to be observable and structured.
    """
    
    def log_event(self, event: TelemetryEvent):
        """
        Log a structured telemetry event.
        """
        log_entry = event.model_dump_json()
        
        if event.severity == SignalSeverity.CRITICAL:
            logger.critical(log_entry)
        elif event.severity == SignalSeverity.ERROR:
            logger.error(log_entry)
        elif event.severity == SignalSeverity.WARNING:
            logger.warning(log_entry)
        else:
            logger.info(log_entry)

    def log_tier_usage(self, selector_name: str, attempted_tier: int, success_tier: int, duration_ms: float):
        """
        Helper to log specific selector tier usage for degradation tracking.
        """
        severity = SignalSeverity.INFO
        if success_tier > 0:
            severity = SignalSeverity.WARNING  # Tier 0 failed, degradation occurred
            
        event = TierUsageEvent(
            timestamp=datetime.now(),
            component="SelectorEngine",
            event_type="TierResolution",
            severity=severity,
            details={
                "degradation": success_tier > 0,
                "tier_gap": success_tier - 0
            },
            selector_name=selector_name,
            attempted_tier=attempted_tier,
            success_tier=success_tier,
            duration_ms=duration_ms
        )
        self.log_event(event)

# Singleton instance
telemetry = TelemetryEngine()

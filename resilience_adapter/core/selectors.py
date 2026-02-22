from typing import Optional, Any
import logging
from .interfaces import BrowserDriverInterface
from .telemetry import telemetry
from ..models.selectors import SelectorDefinition, ResolutionResult, SelectorTrustTier
import time

logger = logging.getLogger("resilience_adapter.selectors")

class SelectorEngine:
    """
    Handles robust element selection using Trust Tiers.
    """
    def __init__(self, driver: BrowserDriverInterface):
        self.driver = driver

    async def resolve(self, definition: SelectorDefinition) -> ResolutionResult:
        """
        Attempts to resolve an element using the defined tiers.
        """
        start_time = time.time()
        
        for tier in definition.tiers:
            logger.debug(f"Attempting tier {tier.tier_index} ({tier.strategy}): {tier.selector}")
            try:
                element = await self.driver.find_element(tier.selector, tier.strategy)
                
                if element:
                    duration = (time.time() - start_time) * 1000
                    telemetry.log_tier_usage(
                        selector_name=definition.name,
                        attempted_tier=tier.tier_index,
                        success_tier=tier.tier_index,
                        duration_ms=duration
                    )
                    return ResolutionResult(
                        element_handle=element,
                        tier_used=tier,
                        success=True
                    )
            except Exception as e:
                logger.warning(f"Error resolving tier {tier.tier_index} for {definition.name}: {e}")
                continue
        
        # If we reach here, all tiers failed
        duration = (time.time() - start_time) * 1000
        telemetry.log_tier_usage(
            selector_name=definition.name,
            attempted_tier=len(definition.tiers), # Indicates failure
            success_tier=-1, # Failure
            duration_ms=duration
        )
        return ResolutionResult(
            element_handle=None,
            tier_used=definition.tiers[-1], # Return last attempted?
            success=False,
            error_msg="All tiers failed"
        )

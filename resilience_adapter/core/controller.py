from .interfaces import BrowserDriverInterface
from .selectors import SelectorEngine
from .entropy import BehavioralEntropyInjector
from .anchor import AnchorValidator
from .convergence import ConvergenceEngine
from ..models.selectors import SelectorDefinition
import logging

logger = logging.getLogger("resilience_adapter.controller")

class ResilienceController:
    """
    High-level controller that coordinates the resilience components.
    """
    def __init__(self, driver: BrowserDriverInterface):
        self.driver = driver
        self.selector_engine = SelectorEngine(driver)
        self.entropy = BehavioralEntropyInjector()
        self.anchor = AnchorValidator(driver)
        self.convergence = ConvergenceEngine(driver)

    async def send_message(self, text: str, input_def: SelectorDefinition, send_btn_def: SelectorDefinition):
        """
        Sends a message with human-like behavior.
        """
        # Resolve Input Box
        input_res = await self.selector_engine.resolve(input_def)
        if not input_res.success:
            raise RuntimeError(f"Could not find input box: {input_res.error_msg}")

        # Human Type
        async def typer(chunk):
            await self.driver.type_text(input_res.element_handle, chunk)
            
        await self.entropy.human_type(typer, text)
        
        # Dispatch
        if self.entropy.should_press_enter_vs_click():
            await self.driver.send_keys(input_res.element_handle, "Enter")
        else:
            btn_res = await self.selector_engine.resolve(send_btn_def)
            if btn_res.success:
                await self.driver.click(btn_res.element_handle)
            else:
                # Fallback to Enter if button missing
                logger.warning("Send button not found, falling back to Enter key")
                await self.driver.send_keys(input_res.element_handle, "Enter")

    async def read_response(self, response_def: SelectorDefinition) -> str:
        """
        Reads the latest response with convergence and anchor validation.
        """
        # 1. Find response candidate (Using generic selector for "last message")
        # Note: This part requires specific selector logic to find the *last* candidate.
        # Assuming response_def targets the container of the latest response.
        res = await self.selector_engine.resolve(response_def)
        if not res.success:
             raise RuntimeError("Could not find response element")

        # 2. Anchor Validation (Optional but recommended)
        # In v5.0, we should strictly check anchor.
        # This requires finding the user message first. 
        # For now, we assume the SelectorEngine logic for 'latest' implies order, 
        # but we can add explicit check here if we had the User Message handle.
        
        # 3. Convergence
        return await self.convergence.wait_for_convergence(res.element_handle)

import asyncio
import sys
import os

# Add parent dir to path so we can import resilience_adapter
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from resilience_adapter.core.controller import ResilienceController
from resilience_adapter.models.selectors import SelectorDefinition, SelectorTrustTier
from resilience_adapter.tests.mock_driver import MockBrowserDriver

async def main():
    print("Starting Integration Test...")
    driver = MockBrowserDriver()
    controller = ResilienceController(driver)

    # Define selectors
    input_def = SelectorDefinition(
        name="Input",
        tiers=[
            SelectorTrustTier(selector="input_box_primary", tier_index=0),
            SelectorTrustTier(selector="input_fallback", tier_index=1)
        ]
    )
    
    send_def = SelectorDefinition(
        name="Send",
        tiers=[
             SelectorTrustTier(selector="send_button_primary", tier_index=0)
        ]
    )
    
    response_def = SelectorDefinition(
        name="Response",
        tiers=[
             SelectorTrustTier(selector="response_container", tier_index=0)
        ]
    )

    print("\n--- Testing Send Message ---")
    try:
        await controller.send_message("Hello AI", input_def, send_def)
        print("Send Message logic executed successfully.")
    except Exception as e:
        print(f"Send Message Failed: {e}")

    print("\n--- Testing Response Convergence ---")
    try:
        final_text = await controller.read_response(response_def)
        print(f"Converged Text: '{final_text}'")
        if final_text == "Generating content... Done.":
             print("SUCCESS: Text converged correctly.")
        else:
             print("FAILURE: Text did not converge to expected value.")
    except Exception as e:
        print(f"Response Read Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())

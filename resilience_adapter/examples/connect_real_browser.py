import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from resilience_adapter.core.interfaces import BrowserDriverInterface
from resilience_adapter.core.controller import ResilienceController
from resilience_adapter.models.selectors import SelectorDefinition, SelectorTrustTier

# Requires: pip install playwright
try:
    from playwright.async_api import async_playwright, Page, Locator
except ImportError:
    print("Please install playwright: pip install playwright")
    sys.exit(1)

class PlaywrightDriver(BrowserDriverInterface):
    """
    Concrete implementation of BrowserDriverInterface using Playwright.
    Connects to an existing browser session via CDP.
    """
    def __init__(self, page: Page):
        self.page = page

    async def find_element(self, selector: str, strategy: str = "css") -> float:
        # Note: Playwright handles selectors smartly.
        # We return the Locator as the 'handle'.
        try:
            loc = self.page.locator(selector).first
            if await loc.count() > 0 and await loc.is_visible():
                return loc
        except:
            pass
        return None

    async def find_elements(self, selector: str, strategy: str = "css") -> list:
        loc = self.page.locator(selector)
        count = await loc.count()
        return [loc.nth(i) for i in range(count)]

    async def get_text(self, element: Locator) -> str:
        return await element.inner_text()

    async def get_attribute(self, element: Locator, attribute: str) -> str:
        return await element.get_attribute(attribute)

    async def click(self, element: Locator):
        await element.click()

    async def type_text(self, element: Locator, text: str):
        # We use strict typing to simulate keystrokes, but the entropy engine
        # will chunk this. 
        # Playwright's type() is already quite human-like but we want explicit control.
        await element.type(text, delay=0) 

    async def send_keys(self, element: Locator, keys: str):
        await element.press(keys)

    async def execute_script(self, script: str, arg: Any = None) -> Any:
        # Playwright evaluate expects a function or string.
        # Our interface expects a JS function body string usually.
        # Adapting to Playwright's handle handling.
        
        # If args are Locators, Playwright needs them passed as ElementHandles.
        # This is a complex mapping for a simple example.
        # For this demo, we'll assume valid JS execution.
        return await self.page.evaluate(script, arg)

async def main():
    print("Starting Resilience Adapter (Real Browser Mode)...")
    
    # 1. Connect to Browser (Start Chrome with --remote-debugging-port=9222)
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            if not context.pages:
                page = await context.new_page()
            else:
                page = context.pages[0]
                
            print(f"Connected to page: {await page.title()}")
            
            # 2. Setup Driver & Controller
            driver = PlaywrightDriver(page)
            controller = ResilienceController(driver)
            
            # 3. Define Selectors (Example for ChatGPT)
            input_def = SelectorDefinition(
                name="chat_input",
                tiers=[
                    SelectorTrustTier(selector="#prompt-textarea", tier_index=0),
                    SelectorTrustTier(selector="textarea[placeholder='Message ChatGPT']", tier_index=1),
                ]
            )
            
            send_def = SelectorDefinition(
                name="send_button",
                tiers=[
                     SelectorTrustTier(selector="button[data-testid='send-button']", tier_index=0)
                ]
            )
            
            # 4. Action
            await controller.send_message("Hello from Resilience Adapter!", input_def, send_def)
            print("Message sent successfully with human entropy.")
            
            # Keep open for observation
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"Connection failed: {e}")
            print("Ensure Chrome is running with: chrome.exe --remote-debugging-port=9222")

if __name__ == "__main__":
    asyncio.run(main())

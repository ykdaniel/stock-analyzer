from resilience_adapter.core.interfaces import BrowserDriverInterface
from typing import Any, List, Optional
import asyncio

class MockElement:
    def __init__(self, tag, text="", attributes=None):
        self.tag = tag
        self.text = text
        self.attributes = attributes or {}

class MockBrowserDriver(BrowserDriverInterface):
    def __init__(self):
        self.elements = {
            "input_box_primary": MockElement("input"),
            "send_button_primary": MockElement("button"),
            "response_container": MockElement("div", text="Genera"), # Initial partial text
        }
        self.stream_update_count = 0

    async def find_element(self, selector: str, strategy: str = "css") -> Optional[Any]:
        if selector in self.elements:
            return self.elements[selector]
        return None

    async def find_elements(self, selector: str, strategy: str = "css") -> List[Any]:
         if selector in self.elements:
            return [self.elements[selector]]
         return []

    async def get_text(self, element: Any) -> str:
        # Simulate streaming for response_container
        if element == self.elements["response_container"]:
            self.stream_update_count += 1
            if self.stream_update_count < 3:
                return "Genera"
            if self.stream_update_count < 5:
                return "Generating content..."
            return "Generating content... Done."
        return element.text

    async def get_attribute(self, element: Any, attribute: str) -> Optional[str]:
        return element.attributes.get(attribute)

    async def click(self, element: Any):
        print(f"Clicked {element.tag}")

    async def type_text(self, element: Any, text: str):
        print(f"Typed '{text}' into {element.tag}")

    async def send_keys(self, element: Any, keys: str):
        print(f"Sent keys '{keys}' to {element.tag}")
        
    async def execute_script(self, script: str, arg: Any = None) -> Any:
        return True # Mock anchor validation pass

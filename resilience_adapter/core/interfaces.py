from abc import ABC, abstractmethod
from typing import Any, List, Optional

class BrowserDriverInterface(ABC):
    """
    Abstract interface for browser interactions.
    Decouples the Resilience Adapter from specific drivers (Playwright/Selenium/CDP).
    """
    @abstractmethod
    async def find_element(self, selector: str, strategy: str = "css") -> Optional[Any]:
        """Finds a single element. Returns None if not found."""
        pass
    
    @abstractmethod
    async def find_elements(self, selector: str, strategy: str = "css") -> List[Any]:
        """Finds all matching elements."""
        pass

    @abstractmethod
    async def get_text(self, element: Any) -> str:
        """Gets inner text of an element."""
        pass

    @abstractmethod
    async def get_attribute(self, element: Any, attribute: str) -> Optional[str]:
        """Gets an attribute value."""
        pass

    @abstractmethod
    async def click(self, element: Any):
        """Clicks an element."""
        pass

    @abstractmethod
    async def type_text(self, element: Any, text: str):
        """Types text into an element."""
        pass

    @abstractmethod
    async def send_keys(self, element: Any, keys: str):
         """Sends special keys (e.g. Enter)."""
         pass

    @abstractmethod
    async def execute_script(self, script: str, arg: Any = None) -> Any:
        """Executes JavaScript in the context of the page or element."""
        pass

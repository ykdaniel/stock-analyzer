import random
import asyncio
import math
from typing import Callable, Any, Awaitable

class BehavioralEntropyInjector:
    """
    Injects human-like entropy into interactions.
    Asyncio compatible.
    """
    
    def __init__(self):
        self.typing_speed_wpm = 60
        self.jitter_factor = 0.3
    
    def calculate_typing_delay(self) -> float:
        """
        Calculates delay between keystrokes based on WPM and Jitter.
        Using a log-normal distribution approximation or simple randomization.
        """
        # Avg chars per minute = WPM * 5. 
        # Avg delay = 60 / chars_per_min
        avg_delay = 60 / (self.typing_speed_wpm * 5)
        
        # Add Jitter
        jitter = random.uniform(-self.jitter_factor, self.jitter_factor)
        delay = avg_delay * (1 + jitter)
        return max(0.02, delay) # Minimum 20ms

    async def human_type(self, type_callback: Callable[[str], Awaitable[Any]], text: str):
        """
        Types text with human-like delays.
        Args:
            type_callback: Async function to type a single character or chunk.
            text: Full text to type.
        """
        # Chunking: Humans don't type char-by-char perfectly. Sometimes bursts.
        i = 0
        while i < len(text):
            # Decide chunk size (1 to 3 chars)
            chunk_size = random.randint(1, 3)
            chunk = text[i : i + chunk_size]
            
            await type_callback(chunk)
            
            # Delay
            delay = self.calculate_typing_delay() * chunk_size
            # Long pause probability (thinking)
            if random.random() < 0.05:
                delay += random.uniform(0.5, 1.5)
            
            await asyncio.sleep(delay)
            
            i += chunk_size

    def should_press_enter_vs_click(self) -> bool:
        """
        Returns True if we should press Enter, False if we should click Send.
        Humans click 'Send' more often in some UIs, or Enter in others.
        Let's assume 80% click Send to be safe/explicit.
        """
        return random.random() > 0.8

from pydantic import BaseModel
from typing import List, Optional, Any

class SelectorTrustTier(BaseModel):
    selector: str
    tier_index: int  # 0=Primary, 1=Secondary, 2=Fallback
    description: Optional[str] = None
    strategy: str = "css"  # css, xpath, text_content

class SelectorDefinition(BaseModel):
    name: str  # e.g., "chat_input_box"
    tiers: List[SelectorTrustTier]

class ResolutionResult(BaseModel):
    element_handle: Any  # Browser driver specific handle (opaque)
    tier_used: SelectorTrustTier
    success: bool
    error_msg: Optional[str] = None

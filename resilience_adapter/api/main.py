from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from ..models.selectors import SelectorDefinition

app = FastAPI(title="Resilience Adapter API", version="5.0")

class InteractRequest(BaseModel):
    action: str # "send", "read"
    text: Optional[str] = None
    selectors: List[SelectorDefinition]

@app.get("/")
async def root():
    return {"status": "Resilience Adapter v5.0 Running", "mode": "Headless/Attached"}

@app.post("/interact")
async def interact(req: InteractRequest):
    # This would link to the Controller.
    # Since the driver connection is stateful and complex, 
    # this API is likely a control plane for a running worker.
    return {"status": "not_implemented_yet", "message": "Controller injection required"}

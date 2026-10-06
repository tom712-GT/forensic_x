from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CaseCreate(BaseModel):
    """
    Schema for creating a new Case.
    """
    case_name: str = Field(..., description="The name or title of the investigation case.")
    description: Optional[str] = Field(None, description="Detailed description of the case.")

class CaseResponse(BaseModel):
    """
    Schema for returning Case data in responses.
    """
    case_id: str = Field(..., description="Unique identifier for the case.")
    case_name: str
    description: Optional[str] = None
    created_at: datetime
    status: str

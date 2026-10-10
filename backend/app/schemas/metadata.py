from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, Optional

class MetadataResponse(BaseModel):
    metadata_id: str
    subject_type: str
    subject_id: str
    case_id: str
    container: str
    parser_version: str
    status: str
    extracted_at: str
    result: Dict[str, Any]

    model_config = ConfigDict(extra='ignore')

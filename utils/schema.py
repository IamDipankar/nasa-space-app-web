from pydantic import BaseModel, Field

class AnalysisRequest(BaseModel):
    analyzer: str
    location: str
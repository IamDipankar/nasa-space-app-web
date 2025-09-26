from pydantic import BaseModel, Field

class AnalysisRequest(BaseModel):
    analyzer: str = Field(..., description="Type of analysis to perform")
    location: str = Field(..., description="Location for the analysis")
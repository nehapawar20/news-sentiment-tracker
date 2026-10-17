from typing import Literal

from pydantic import BaseModel, Field, field_validator

Topic = Literal[
    "politics",
    "business",
    "technology",
    "sports",
    "health",
    "science",
    "entertainment",
    "world",
    "other",
]


class EnrichmentResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    score: float = Field(ge=-1.0, le=1.0)
    topic: Topic
    entities: list[str] = Field(default_factory=list, max_length=10)
    summary: str = Field(max_length=300)

    @field_validator("sentiment", "topic", mode="before")
    @classmethod
    def normalise_label(cls, value):
        # Accept 'Positive' or ' BUSINESS ' as well as the exact lowercase label.
        return value.strip().lower() if isinstance(value, str) else value
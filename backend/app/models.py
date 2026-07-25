"""Pydantic models for the shared event contract (PRD section 17)."""
from pydantic import BaseModel, Field


class CaptureEvent(BaseModel):
    """What Person 2's extension / capture service sends us."""
    event_id: str
    timestamp: str
    source: str = "chat_application"
    application: str = "supported_ai_tool"
    prompt_text: str
    selected_model: str = "unknown"
    screenshot_path: str | None = None
    session_id: str = "default-session"


class SourceRef(BaseModel):
    """Frontier-knowledge citation for the overlay's source card."""
    text: str
    date: str
    confidence: str = "unverified"
    url: str


class Evaluation(BaseModel):
    """What the intelligence engine (Person 3) returns."""
    overall_score: int = Field(ge=0, le=100)
    primary_category: str
    category_scores: dict[str, int]
    roast: str
    diagnosis: str
    lesson: str
    improved_prompt: str
    severity: int = Field(ge=0, le=3, default=0)
    action: str = "none"   # none | smart_light | desk_buzzer | bell_bot
    source: SourceRef | None = None


class WebhookRegistration(BaseModel):
    url: str
    name: str = "unnamed"
    categories: list[str] = []      # empty = all categories
    min_severity: int = 1


class KnowledgeUpdate(BaseModel):
    product: str
    what_changed: str
    release_date: str | None = None
    source: str | None = None
    previous_option: str | None = None
    new_option: str | None = None
    why_it_matters: str | None = None
    confidence: str = "seeded-demo"


class RssImportRequest(BaseModel):
    url: str
    product: str | None = None      # override product name; defaults to feed title
    limit: int = 10

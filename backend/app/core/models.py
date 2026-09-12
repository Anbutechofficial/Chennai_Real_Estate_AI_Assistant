from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any


class QuestionRequest(BaseModel):
    question: str = ""
    query: Optional[str] = None
    prompt: Optional[str] = None
    message: Optional[str] = None
    text: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def extract_question(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Resolve question from any common field name
            q = (
                data.get("question")
                or data.get("query")
                or data.get("prompt")
                or data.get("message")
                or data.get("text")
                or ""
            )
            data["question"] = str(q).strip()
            if "history" not in data or data["history"] is None:
                data["history"] = []
        elif isinstance(data, str):
            return {"question": data.strip(), "history": []}
        return data


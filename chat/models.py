from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=128)
    user_input: str = Field(min_length=1, max_length=10_000)

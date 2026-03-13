"""
Claude AI Assistant Route
Handles driver queries using Anthropic Claude
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import anthropic
import os

router = APIRouter()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are an AI Senior Driver Copilot — a smart, calm, and experienced logistics assistant for delivery drivers in Singapore.

Your role is to:
1. Guide drivers through delivery challenges step by step
2. Suggest solutions when customers are not home
3. Help interpret difficult addresses or building layouts
4. Provide advice on handling damaged parcels or complaints
5. Suggest efficient delivery sequences
6. Communicate clearly and concisely — drivers are busy

Always be:
- Practical and action-oriented
- Brief and clear (drivers read on mobile while working)
- Knowledgeable about Singapore addresses (HDB blocks, condos, landed)
- Encouraging and supportive

Singapore-specific knowledge:
- HDB addresses format: Block [number] [Street Name], #[floor]-[unit]
- Postal codes are 6 digits
- Common access issues: gated condos, HDB void decks, multi-storey carparks
- Intercom systems, security guards, parcel lockers

Respond in short paragraphs. Use numbered steps for instructions."""


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []
    location: Optional[str] = None
    weather: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    tokens_used: int


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        messages = []

        # Add conversation history
        for msg in request.history[-10:]:  # Keep last 10 messages for context
            messages.append({"role": msg.role, "content": msg.content})

        # Build context-aware user message
        context_prefix = ""
        if request.location:
            context_prefix += f"[Current location: {request.location}] "
        if request.weather:
            context_prefix += f"[Weather: {request.weather}] "

        messages.append({
            "role": "user",
            "content": f"{context_prefix}{request.message}"
        })

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=messages
        )

        return ChatResponse(
            reply=response.content[0].text,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI assistant error: {str(e)}")

"""
Customer Notifications Route
AI-generated ETA messages and delivery status notifications
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import anthropic
import os

router = APIRouter()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


class NotificationRequest(BaseModel):
    scenario: str           # "eta" | "not_home" | "delay" | "delivered" | "attempt_failed"
    customer_name: Optional[str] = None
    eta_minutes: Optional[int] = None
    address: Optional[str] = None
    parcel_count: Optional[int] = 1
    reason: Optional[str] = None    # Delay reason, etc.
    language: str = "english"       # english, chinese, malay, tamil


class NotificationResponse(BaseModel):
    messages: List[str]
    scenario: str
    whatsapp_ready: bool = True


NOTIFICATION_PROMPTS = {
    "eta": "Driver is {eta_minutes} minutes away from delivering to {customer_name} at {address}.",
    "not_home": "Driver arrived but customer {customer_name} was not home at {address}.",
    "delay": "Delivery to {customer_name} is delayed due to {reason}.",
    "delivered": "Parcel successfully delivered to {customer_name} at {address}.",
    "attempt_failed": "Delivery attempt failed for {customer_name} at {address}. Reason: {reason}."
}


@router.post("/generate", response_model=NotificationResponse)
async def generate_notification(request: NotificationRequest):
    """
    Generate customer-friendly notification messages using Claude AI
    Returns 3 message variations for the driver to choose from
    """
    try:
        # Build context string
        context = NOTIFICATION_PROMPTS.get(request.scenario, request.scenario).format(
            customer_name=request.customer_name or "Customer",
            eta_minutes=request.eta_minutes or "a few",
            address=request.address or "your address",
            reason=request.reason or "unforeseen circumstances"
        )

        prompt = f"""Generate 3 short, friendly SMS/WhatsApp notification messages for this delivery scenario:

Scenario: {context}
Language: {request.language}
Parcel count: {request.parcel_count}

Requirements:
- Keep each message under 160 characters (SMS limit)
- Be polite and professional
- Include relevant emojis (1-2 max)
- In {request.language} language
- Practical and informative

Return ONLY a JSON array with exactly 3 message strings. No explanation, no markdown.
Example format: ["Message 1 here", "Message 2 here", "Message 3 here"]"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )

        import json
        result_text = response.content[0].text.strip()

        # Clean JSON
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        messages = json.loads(result_text)

        if not isinstance(messages, list):
            messages = [str(messages)]

        return NotificationResponse(
            messages=messages[:3],
            scenario=request.scenario,
            whatsapp_ready=True
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notification generation error: {str(e)}")


@router.get("/templates")
async def get_notification_templates():
    """
    Get pre-built notification templates for common scenarios
    """
    return {
        "templates": {
            "eta": {
                "label": "ETA Alert",
                "description": "Notify customer driver is arriving soon",
                "icon": "🚚"
            },
            "not_home": {
                "label": "Customer Not Home",
                "description": "Customer was absent during delivery attempt",
                "icon": "🏠"
            },
            "delay": {
                "label": "Delivery Delay",
                "description": "Notify customer about unexpected delay",
                "icon": "⏰"
            },
            "delivered": {
                "label": "Successfully Delivered",
                "description": "Confirm parcel has been delivered",
                "icon": "✅"
            },
            "attempt_failed": {
                "label": "Delivery Failed",
                "description": "Unable to complete delivery this attempt",
                "icon": "❌"
            }
        }
    }

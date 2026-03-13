"""
Parcel Label OCR Route
Uses GPT-4 Vision to extract delivery information from parcel label photos
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import openai
import base64
import os

router = APIRouter()
client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


class ParcelInfo(BaseModel):
    recipient_name: Optional[str] = None
    address: Optional[str] = None
    unit_number: Optional[str] = None
    postal_code: Optional[str] = None
    tracking_number: Optional[str] = None
    phone_number: Optional[str] = None
    raw_text: Optional[str] = None
    confidence: str = "low"


OCR_PROMPT = """You are analyzing a delivery parcel label photo. 
Extract ALL delivery information visible on the label and return a JSON object with these fields:
- recipient_name: Full name of recipient
- address: Street address (block number + street name)  
- unit_number: Unit/flat/apartment number (e.g. #12-34)
- postal_code: 6-digit Singapore postal code
- tracking_number: Parcel tracking/barcode number
- phone_number: Recipient phone number if visible
- raw_text: All text you can read from the label
- confidence: "high" if all key fields found, "medium" if partial, "low" if unclear

Return ONLY valid JSON, no explanation."""


@router.post("/scan", response_model=ParcelInfo)
async def scan_parcel_label(file: UploadFile = File(...)):
    """
    Upload a parcel label photo and extract delivery information using GPT-4 Vision
    """
    try:
        # Read and encode image
        image_data = await file.read()
        base64_image = base64.b64encode(image_data).decode("utf-8")

        # Determine media type
        media_type = file.content_type or "image/jpeg"

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{base64_image}",
                                "detail": "high"
                            }
                        },
                        {
                            "type": "text",
                            "text": OCR_PROMPT
                        }
                    ]
                }
            ]
        )

        import json
        result_text = response.choices[0].message.content.strip()

        # Clean JSON response (remove markdown fences if present)
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        parcel_data = json.loads(result_text)
        return ParcelInfo(**parcel_data)

    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Could not parse label information")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR error: {str(e)}")


@router.post("/scan-base64", response_model=ParcelInfo)
async def scan_parcel_label_base64(payload: dict):
    """
    Scan parcel label from base64 encoded image (for mobile cameras)
    """
    try:
        base64_image = payload.get("image")
        if not base64_image:
            raise HTTPException(status_code=400, detail="No image provided")

        # Strip data URL prefix if present
        if "," in base64_image:
            base64_image = base64_image.split(",")[1]

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "high"
                            }
                        },
                        {"type": "text", "text": OCR_PROMPT}
                    ]
                }
            ]
        )

        import json
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        parcel_data = json.loads(result_text)
        return ParcelInfo(**parcel_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR error: {str(e)}")

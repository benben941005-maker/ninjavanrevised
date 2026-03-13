"""
Weather Monitoring Route
Real-time Singapore weather with delivery impact assessment
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os

router = APIRouter()

WEATHER_API_BASE = "https://api.weatherapi.com/v1"


class WeatherCondition(BaseModel):
    location: str
    temperature_c: float
    condition: str
    condition_icon: str
    humidity: int
    wind_kph: float
    is_raining: bool
    rain_mm: float
    delivery_impact: str       # "none" | "minor" | "moderate" | "severe"
    delivery_advice: str
    alert_color: str           # "green" | "yellow" | "orange" | "red"


def assess_delivery_impact(condition_text: str, rain_mm: float, wind_kph: float) -> dict:
    """Assess how weather affects delivery operations"""
    condition_lower = condition_text.lower()
    is_raining = rain_mm > 0 or "rain" in condition_lower or "drizzle" in condition_lower

    if rain_mm > 10 or "heavy rain" in condition_lower or "thunderstorm" in condition_lower:
        return {
            "impact": "severe",
            "color": "red",
            "advice": "⛈️ Heavy rain/thunderstorm. Seek shelter immediately. Protect parcels from water. Do not attempt outdoor deliveries until it clears."
        }
    elif rain_mm > 3 or "moderate rain" in condition_lower:
        return {
            "impact": "moderate",
            "color": "orange",
            "advice": "🌧️ Moderate rain. Use rain cover for parcels. Prioritize sheltered deliveries (HDB void decks, condos with lobby). Drive carefully."
        }
    elif is_raining:
        return {
            "impact": "minor",
            "color": "yellow",
            "advice": "🌦️ Light rain detected. Keep parcels protected. Deliveries can continue but watch for slippery surfaces."
        }
    elif wind_kph > 40:
        return {
            "impact": "minor",
            "color": "yellow",
            "advice": "💨 Strong winds. Secure lightweight parcels on bike/van. Be careful opening van doors."
        }
    else:
        return {
            "impact": "none",
            "color": "green",
            "advice": "✅ Good weather for deliveries. Conditions are clear."
        }


@router.get("/current", response_model=WeatherCondition)
async def get_current_weather(
    lat: float = Query(1.3521, description="Latitude (default: Singapore)"),
    lng: float = Query(103.8198, description="Longitude (default: Singapore)")
):
    """
    Get current weather at driver's location with delivery impact assessment
    """
    try:
        api_key = os.environ.get("WEATHER_API_KEY")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{WEATHER_API_BASE}/current.json",
                params={
                    "key": api_key,
                    "q": f"{lat},{lng}",
                    "aqi": "no"
                }
            )
            data = response.json()

        current = data["current"]
        location = data["location"]

        condition_text = current["condition"]["text"]
        rain_mm = current.get("precip_mm", 0)
        wind_kph = current.get("wind_kph", 0)

        assessment = assess_delivery_impact(condition_text, rain_mm, wind_kph)

        return WeatherCondition(
            location=f"{location['name']}, {location['region']}",
            temperature_c=current["temp_c"],
            condition=condition_text,
            condition_icon=f"https:{current['condition']['icon']}",
            humidity=current["humidity"],
            wind_kph=wind_kph,
            is_raining=assessment["impact"] != "none" and "wind" not in assessment["advice"],
            rain_mm=rain_mm,
            delivery_impact=assessment["impact"],
            delivery_advice=assessment["advice"],
            alert_color=assessment["color"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather API error: {str(e)}")


@router.get("/forecast")
async def get_weather_forecast(
    lat: float = Query(1.3521),
    lng: float = Query(103.8198),
    hours: int = Query(3, description="Hours ahead to forecast (1-24)")
):
    """
    Get hourly weather forecast to plan delivery schedule
    """
    try:
        api_key = os.environ.get("WEATHER_API_KEY")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{WEATHER_API_BASE}/forecast.json",
                params={
                    "key": api_key,
                    "q": f"{lat},{lng}",
                    "hours": min(hours, 24)
                }
            )
            data = response.json()

        hourly = []
        forecast_hours = data.get("forecast", {}).get("forecastday", [{}])[0].get("hour", [])

        from datetime import datetime
        current_hour = datetime.now().hour

        for h in forecast_hours:
            hour_time = int(h["time"].split(" ")[1].split(":")[0])
            if hour_time >= current_hour and len(hourly) < hours:
                assessment = assess_delivery_impact(
                    h["condition"]["text"],
                    h.get("precip_mm", 0),
                    h.get("wind_kph", 0)
                )
                hourly.append({
                    "time": h["time"],
                    "temp_c": h["temp_c"],
                    "condition": h["condition"]["text"],
                    "rain_mm": h.get("precip_mm", 0),
                    "rain_chance": h.get("chance_of_rain", 0),
                    "delivery_impact": assessment["impact"],
                    "alert_color": assessment["color"]
                })

        return {"forecast": hourly, "location": data["location"]["name"]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast error: {str(e)}")

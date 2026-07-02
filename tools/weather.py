from __future__ import annotations

import requests


def get_weather(city: str) -> dict:
    try:
        response = requests.get(f"https://wttr.in/{city}", params={"format": "j1"}, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"error": str(exc)}

    data = response.json()
    current = data.get("current_condition", [{}])[0]
    nearest_area = data.get("nearest_area", [{}])[0]
    area_name = nearest_area.get("areaName", [{}])[0].get("value", city)
    description = current.get("weatherDesc", [{}])[0].get("value", "")

    return {
        "city": area_name,
        "temperature_c": current.get("temp_C"),
        "feels_like_c": current.get("FeelsLikeC"),
        "description": description,
        "humidity_percent": current.get("humidity"),
        "wind_kmh": current.get("windspeedKmph"),
    }

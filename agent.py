from agno.agent import Agent 
from agno.media import Image
import os, time, uuid, requests
from agno.models.openrouter import OpenRouter
from agno.storage.sqlite import SqliteStorage
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools import tool
from dotenv import load_dotenv

# NEW imports for Maps
import googlemaps
import requests
import re

load_dotenv()
API_KEY = os.getenv("openrouter_api") or os.getenv("OPENROUTER_API")
MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
GRAPHOPPER_KEY = os.getenv("GRAPHOPPER_API_KEY")  # reserved for future use
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "example@example.com")

if not API_KEY:
    print("[WARN] OPENROUTER API key missing; model calls will fail.")
if not MAPS_KEY:
    raise RuntimeError("GOOGLE_MAPS_API_KEY missing. Add it to your .env file.")

# Storage (keep lightweight for teaching)
os.makedirs("tmp", exist_ok=True)
storage = SqliteStorage(table_name="agent_sessions", db_file="tmp/data.db")

STATIC_MAP_ENDPOINT = "https://maps.googleapis.com/maps/api/staticmap"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


@tool
def coordinates_of_location(location: str) -> str:
    """Return (lat, lon) for a location name using OpenStreetMap Nominatim.

    Use when you need precise coordinates before generating a static map or performing distance logic.
    """
    if not location.strip():
        raise ValueError("Location cannot be empty")
    params = {"q": location, "format": "json", "limit": 1}
    headers = {"User-Agent": f"EnforcerBot/1.0 ({CONTACT_EMAIL})"}
    resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"Location '{location}' not found")
    lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
    return f"Coordinates for '{location}': ({lat:.6f}, {lon:.6f})"


@tool
def create_satellite_map(location: str, zoom: int = 16, size: str = "600x400") -> str:
    """Generate a satellite static map PNG for a location name.

    Args:
        location: Free-form place (will be geocoded by Google implicitly).
        zoom: Zoom level (default 16).
        size: WxH in pixels (max 640x640 for free tier). Example: "600x400".
    Returns: Path to generated PNG image.
    """
    if not location.strip():
        raise ValueError("Location cannot be empty")
    params = {
        "center": location,
        "zoom": zoom,
        "size": size,
        "maptype": "satellite",
        "key": MAPS_KEY,
        "scale": 1,
        "format": "png",
        "markers": f"color:red|{location}",
    }
    r = requests.get(STATIC_MAP_ENDPOINT, params=params, timeout=20)
    if r.status_code != 200 or r.headers.get("Content-Type", "").lower().find("image") == -1:
        raise RuntimeError(f"Static map fetch failed: {r.status_code} {r.text[:120]}")
    fname = f"satellite_map_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
    path = os.path.join("tmp", fname)
    with open(path, "wb") as f:
        f.write(r.content)
    return path


INSTRUCTIONS = """
You are the Crime/Location Information Assistant.
You can:
 - Search current info (DuckDuckGoTools)
 - Convert place names to coordinates (coordinates_of_location)
 - Generate a satellite map image (create_satellite_map) and then describe it.

When you generate a map, reference the image file path returned.
Only call a tool if it meaningfully helps answer the user's question.
You willl find the accurate help line info and always be emphathetic and offer polite accurate and concise responses.
You are Enforcer bot and you assist with Law and Order related queries.
Do alll you can to assist the user and direct them to the appropriate authorities if needed by finding the correct contact informatio using the web search too based on Grenada laws.
"""


def agent(message, image=None):
    _agent = Agent(
        name="Crime Information Agent",
        model=OpenRouter(id="qwen/qwq-32b:free", api_key=API_KEY, max_tokens=6000),
        tools=[DuckDuckGoTools(), coordinates_of_location, create_satellite_map],
        tool_choice="auto",
        instructions=INSTRUCTIONS,
        show_tool_calls=True,
        markdown=True,
        storage=storage,
        add_history_to_messages=True,
    )
    if image:
        image = [Image(filepath=image)]
    return _agent.run(message=message, images=image, stream=True)


if __name__ == "__main__":  # simple manual test
    for chunk in agent("Show me a satellite map of Times Square and its coordinates"):
        if getattr(chunk, "content", None):
            print(chunk.content, end="", flush=True)
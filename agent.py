from agno.agent import Agent 
from agno.media import Image
import os
from agno.models.openrouter import OpenRouter
from agno.storage.sqlite import SqliteStorage
from agno.tools.duckduckgo import DuckDuckGoTools
from dotenv import load_dotenv

# NEW imports for Maps
import googlemaps
import requests
import re

load_dotenv()
API_KEY = os.getenv("openrouter_api")
GMAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Create SQLite storage
storage = SqliteStorage(
    table_name="agent_sessions",
    db_file="tmp/data.db"
)

from agno.tools.google_maps import GoogleMapTools

# Create the agent with DuckDuckGo + new Google Maps tool
def agent(message, image=None):
    agent = Agent(
        model=OpenRouter(id="google/gemini-2.0-flash-lite-001", api_key=API_KEY),
        storage=storage,
        tools=[
            DuckDuckGoTools(),
            GoogleMapTools(key=GMAPS_KEY),      # ← add here
        ],
        tool_choice="auto",
        add_history_to_messages=True,
        show_tool_calls=True,
        markdown=True,
        instructions="""
Always remember and use the user's name in every response...
(etc.)
"""
    )
    if image:
        image = [Image(filepath=image)]
    return agent.run(message=message, images=image, stream=True)
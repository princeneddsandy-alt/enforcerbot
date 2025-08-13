"""Agent setup with custom mapping tools (coordinates + satellite map).

Removes dependency on Agno's GoogleMapTools to avoid ADC confusion and demonstrates
simple, teaching-friendly tools. All secrets pulled from environment variables.

Env vars expected (create a .env file):
  OPENROUTER_API            -> OpenRouter API key (named openrouter_api for backward compat)
  GOOGLE_MAPS_API_KEY       -> Google Maps Static/Places/etc. API key
  GRAPHOPPER_API_KEY        -> (Optional) GraphHopper directions key if later extended
  CONTACT_EMAIL             -> Your email (polite User-Agent when calling Nominatim)
"""

from agno.agent import Agent
from agno.media import Image
from agno.models.openrouter import OpenRouter
from agno.storage.sqlite import SqliteStorage
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools import tool
from dotenv import load_dotenv
import os, time, uuid, requests, json, re

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


@tool
def assess_risk_level(situation: str, location: str = "", context: str = "") -> str:
    """Assess the risk level (LOW/MEDIUM/HIGH) of a given situation using AI analysis.
    
    Args:
        situation: Description of the situation or incident
        location: Optional location context
        context: Additional context information
    Returns: Risk assessment with level and reasoning
    """
    # Create a structured prompt for risk assessment
    assessment_prompt = f"""
    Analyze the following situation for risk level assessment:
    
    Situation: {situation}
    Location: {location if location else "Not specified"}
    Additional Context: {context if context else "None provided"}
    
    Please classify this situation's risk level as LOW, MEDIUM, or HIGH based on:
    - Immediate physical danger
    - Potential for escalation
    - Environmental factors
    - Time sensitivity
    - Available resources/help
    
    Provide your assessment in this format:
    RISK LEVEL: [LOW/MEDIUM/HIGH]
    REASONING: [Brief explanation]
    IMMEDIATE ACTIONS: [What should be done now]
    """
    
    try:
        # Use the OpenRouter model for assessment
        model = OpenRouter(id="google/gemini-2.0-flash-lite-001", api_key=API_KEY, max_tokens=1000)
        response = model.invoke(assessment_prompt)
        return f"Risk Assessment Results:\n{response.content}"
    except Exception as e:
        return f"Risk assessment unavailable: {str(e)}. Please seek immediate help if in danger."


@tool  
def get_safety_tips(situation_type: str, location: str = "") -> str:
    """Get dynamic safety tips and best practices for specific situations using web search.
    
    Args:
        situation_type: Type of situation (e.g., "theft", "harassment", "natural disaster", "suspicious activity")
        location: Optional location for location-specific advice
    Returns: Current safety tips and best practices
    """
    ddg = DuckDuckGoTools()
    
    # Multiple search strategies for comprehensive results
    search_queries = [
        f"safety tips {situation_type} prevention what to do",
        f"how to stay safe {situation_type} best practices 2024",
        f"emergency response {situation_type} safety guide"
    ]
    
    if location:
        search_queries.append(f"{location} safety {situation_type} local advice")
    
    all_tips = []
    
    for query in search_queries:
        try:
            result = ddg.search(query, max_results=3)
            if result and len(result.strip()) > 30:
                all_tips.append(result)
        except Exception as search_error:
            continue
    
    if all_tips:
        tips_response = f"🛡️ **Safety Tips for {situation_type.title()}**\n"
        if location:
            tips_response += f"📍 *Location-specific guidance for {location}*\n\n"
        
        tips_response += "💡 **Current Best Practices:**\n\n"
        
        for i, tips in enumerate(all_tips, 1):
            tips_response += f"**Source {i}:**\n{tips}\n\n"
        
        tips_response += "⚠️ **Remember:** If you feel unsafe or threatened, trust your instincts and seek help immediately!"
        return tips_response
    else:
        # Fallback with general safety advice
        tips_response = f"🛡️ **General Safety Tips for {situation_type.title()}**\n\n"
        tips_response += "💡 **Universal Safety Principles:**\n"
        tips_response += "• Trust your instincts - if something feels wrong, it probably is\n"
        tips_response += "• Stay aware of your surroundings at all times\n"
        tips_response += "• Keep emergency contacts readily available\n"
        tips_response += "• Have an exit plan or escape route when possible\n"
        tips_response += "• Don't hesitate to call for help or emergency services\n"
        tips_response += "• Document incidents when safe to do so\n\n"
        tips_response += "⚠️ **Unable to retrieve current web-based safety tips. For specific guidance, contact local authorities or safety experts.**"
        return tips_response


@tool
def find_nearby_resources(location: str, resource_type: str = "emergency services") -> str:
    """Find nearby emergency resources like police stations, hospitals, safe houses, etc.
    
    Args:
        location: Location to search around
        resource_type: Type of resource ("police", "hospital", "safe house", "emergency services", "shelter")
    Returns: Information about nearby resources
    """
    try:
        # First get coordinates for more precise searching
        coords_result = coordinates_of_location(location)
        
        # Multiple search strategies for better results
        ddg = DuckDuckGoTools()
        
        # Strategy 1: Direct resource search
        search_queries = [
            f"{resource_type} near {location}",
            f"{location} {resource_type} directory",
            f"{location} emergency services contact",
            f"find {resource_type} {location} address phone"
        ]
        
        all_results = []
        for query in search_queries:
            try:
                result = ddg.search(query, max_results=3)
                if result and len(result.strip()) > 50:  # Only add meaningful results
                    all_results.append(f"Search: '{query}'\n{result}\n")
            except Exception as search_error:
                continue
        
        # Strategy 2: Location-specific emergency information
        emergency_query = f"{location} emergency contacts police hospital fire department"
        try:
            emergency_results = ddg.search(emergency_query, max_results=4)
            if emergency_results and len(emergency_results.strip()) > 50:
                all_results.append(f"Emergency Services in {location}:\n{emergency_results}\n")
        except Exception:
            pass
        
        # Strategy 3: Government/official resources
        official_query = f"{location} government emergency services official directory"
        try:
            official_results = ddg.search(official_query, max_results=3)
            if official_results and len(official_results.strip()) > 50:
                all_results.append(f"Official Resources:\n{official_results}\n")
        except Exception:
            pass
        
        # Compile response
        if all_results:
            response = f"🚨 {resource_type.title()} Resources for {location}:\n\n"
            response += f"📍 {coords_result}\n\n"
            response += "🔍 **Found Resources:**\n"
            response += "\n".join(all_results)
            response += f"\n\n⚠️ **Emergency Numbers:**\n"
            response += "- US/Canada: 911\n- UK: 999\n- EU: 112\n- Australia: 000\n"
            response += f"- **Always call your local emergency number immediately if in danger**"
            return response
        else:
            # Fallback response with general guidance
            response = f"🚨 Unable to find specific {resource_type} near {location} through web search.\n\n"
            response += f"📍 {coords_result}\n\n"
            response += "🔍 **Alternative Options:**\n"
            response += f"1. Call your local emergency services immediately: 911 (US), 999 (UK), 112 (EU)\n"
            response += f"2. Use Google Maps or Apple Maps to search '{resource_type} near me'\n"
            response += f"3. Contact local directory assistance\n"
            response += f"4. Visit your local government website for emergency service listings\n\n"
            response += "⚠️ **If this is an emergency, don't hesitate - call emergency services now!**"
            return response
            
    except Exception as e:
        return f"🚨 Unable to locate resources due to technical error: {str(e)}\n\n⚠️ **EMERGENCY ACTION:**\nCall emergency services immediately:\n- US: 911\n- UK: 999\n- EU: 112\n- If in immediate danger, don't wait - get help now!"


@tool
def get_legal_information(country: str, legal_topic: str, situation: str = "") -> str:
    """Get relevant legal information and laws for specific countries and situations.
    
    Args:
        country: Country or jurisdiction
        legal_topic: Legal area (e.g., "harassment", "theft", "assault", "privacy", "stalking")
        situation: Optional specific situation for more targeted legal info
    Returns: Relevant legal information and rights
    """
    ddg = DuckDuckGoTools()
    
    # Multiple targeted searches for comprehensive legal information
    search_queries = [
        f"{country} {legal_topic} laws legal rights what to do",
        f"{country} legal system {legal_topic} victim rights",
        f"{country} criminal law {legal_topic} penalties punishment"
    ]
    
    if situation:
        search_queries.append(f"{country} {legal_topic} {situation} legal advice")
    
    legal_results = []
    
    for query in search_queries:
        try:
            result = ddg.search(query, max_results=2)
            if result and len(result.strip()) > 40:
                legal_results.append(result)
        except Exception:
            continue
    
    if legal_results:
        response = f"⚖️ **Legal Information: {country} - {legal_topic.title()}**\n\n"
        
        if situation:
            response += f"📋 *Specific to: {situation}*\n\n"
        
        response += "📚 **Current Legal Framework and Rights:**\n\n"
        
        for i, legal_info in enumerate(legal_results, 1):
            response += f"**Legal Resource {i}:**\n{legal_info}\n\n"
        
        response += "⚖️ **IMPORTANT LEGAL DISCLAIMER:**\n"
        response += "• This information is for general guidance only\n"
        response += "• Laws change frequently and vary by jurisdiction\n"
        response += "• Consult with a qualified legal professional for specific advice\n"
        response += "• Contact local authorities for immediate legal protection\n"
        response += "• Keep documentation of any incidents or evidence\n\n"
        response += "🔗 **Next Steps:** Contact local legal aid services or law enforcement for professional assistance."
        
        return response
    else:
        # Fallback with general legal guidance
        response = f"⚖️ **Legal Guidance: {country} - {legal_topic.title()}**\n\n"
        response += "📋 **Unable to retrieve specific legal information via web search.**\n\n"
        response += "🔍 **Recommended Actions:**\n"
        response += f"1. Contact {country} legal aid services or legal helplines\n"
        response += "2. Consult with a local attorney specializing in this area\n"
        response += "3. Contact local law enforcement if criminal activity is involved\n"
        response += "4. Visit official government legal information websites\n"
        response += "5. Reach out to victim advocacy organizations\n\n"
        response += "⚖️ **Emergency Legal Protection:** If in immediate danger, contact emergency services first, then seek legal counsel."
        
        return response


@tool
def analyze_threat_patterns(incident_description: str, location: str = "") -> str:
    """Analyze incident patterns to identify potential threats and provide intelligence.
    
    Args:
        incident_description: Detailed description of the incident or concern
        location: Location where incident occurred or is expected
    Returns: Threat pattern analysis and recommendations
    """
    analysis_prompt = f"""
    Analyze this incident for threat patterns and provide security intelligence:
    
    Incident: {incident_description}
    Location: {location if location else "Not specified"}
    
    Please analyze for:
    - Pattern recognition (is this part of a larger trend?)
    - Threat indicators
    - Escalation potential
    - Preventive measures
    - Situational awareness tips
    
    Provide actionable intelligence and recommendations.
    """
    
    try:
        model = OpenRouter(id="google/gemini-2.0-flash-lite-001", api_key=API_KEY, max_tokens=1200)
        response = model.invoke(analysis_prompt)
        
        # Also search for similar incidents in the area
        if location:
            search_query = f"recent incidents {location} crime pattern security alerts"
            ddg = DuckDuckGoTools()
            search_results = ddg.search(search_query, max_results=3)
            
            final_response = f"Threat Pattern Analysis:\n{response.content}\n\n"
            final_response += f"Recent Area Intelligence:\n{search_results}"
            return final_response
        else:
            return f"Threat Pattern Analysis:\n{response.content}"
            
    except Exception as e:
        return f"Threat analysis unavailable: {str(e)}. Exercise heightened awareness and contact authorities if concerned."


INSTRUCTIONS = """
You are the Advanced Crime/Location Information & Safety Assistant.

Your capabilities include:
 - Search current info and news (DuckDuckGoTools)
 - Convert place names to coordinates (coordinates_of_location)
 - Generate satellite map images (create_satellite_map) for visual context
 - Assess risk levels dynamically (assess_risk_level) - LOW/MEDIUM/HIGH classification
 - Provide current safety tips (get_safety_tips) based on situation and location
 - Find nearby emergency resources (find_nearby_resources) - police, hospitals, shelters
 - Get legal information (get_legal_information) for different countries and situations
 - Analyze threat patterns (analyze_threat_patterns) for security intelligence

Key principles:
- Always prioritize user safety and immediate danger assessment
- Use dynamic, current information rather than static responses
- Provide actionable, specific guidance based on context
- Cross-reference multiple sources when possible
- Escalate to emergency services when warranted
- If web searches return limited results, provide comprehensive fallback guidance
- Always include emergency contact information for high-risk situations

When analyzing situations:
1. First assess immediate risk level
2. Provide relevant safety tips for the specific situation
3. Locate nearby resources if location is provided
4. Include relevant legal context if applicable
5. Look for threat patterns if concerning incidents

Tool Usage Guidelines:
- Use find_nearby_resources for location-specific emergency services
- Use get_safety_tips for situation-specific safety advice
- Use get_legal_information for legal rights and laws by country
- Use assess_risk_level for AI-powered threat assessment
- Use analyze_threat_patterns for security intelligence
- Use create_satellite_map for visual location context
- Use coordinates_of_location for precise location data

If any tool returns limited information due to search limitations, supplement with:
- General best practices and universal safety principles
- Emergency contact numbers
- Alternative resources and next steps
- Clear action items for the user

Always maintain a helpful, professional tone while emphasizing safety and urgency when appropriate.
"""


def agent(message, image=None):
    _agent = Agent(
        name="Advanced Crime Information & Safety Agent",
        model=OpenRouter(id="google/gemini-2.0-flash-lite-001", api_key=API_KEY, max_tokens=6000),
        tools=[
            DuckDuckGoTools(), 
            coordinates_of_location, 
            create_satellite_map,
            assess_risk_level,
            get_safety_tips,
            find_nearby_resources,
            get_legal_information,
            analyze_threat_patterns
        ],
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


if __name__ == "__main__":  # Enhanced test examples
    print("=== Testing Enhanced Crime/Safety Agent ===\n")
    
    # Test 1: Risk Assessment
    print("Test 1: Risk Assessment")
    for chunk in agent("I'm being followed by someone suspicious in downtown Chicago at night. What's the risk level?"):
        if getattr(chunk, "content", None):
            print(chunk.content, end="", flush=True)
    print("\n" + "="*50 + "\n")
    
    # Test 2: Safety Tips  
    print("Test 2: Safety Tips")
    for chunk in agent("Give me safety tips for walking alone at night in an urban area"):
        if getattr(chunk, "content", None):
            print(chunk.content, end="", flush=True)
    print("\n" + "="*50 + "\n")
    
    # Test 3: Resource Location
    print("Test 3: Finding Nearby Resources")
    for chunk in agent("Find nearest police station and hospital in Manhattan, NYC"):
        if getattr(chunk, "content", None):
            print(chunk.content, end="", flush=True)
    print("\n" + "="*50 + "\n")
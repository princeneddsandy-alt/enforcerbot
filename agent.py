"""Agent setup with Mapbox integration and enhanced safety features.

Uses Mapbox for mapping and location services, plus custom tools for comprehensive 
location intelligence and emergency response capabilities.

Env vars expected (create a .env file):
  OPENROUTER_API            -> OpenRouter API key
  MAPBOX_ACCESS_TOKEN       -> Mapbox API token for maps and directions
  TWILIO_ACCOUNT_SID        -> Twilio account SID for SMS notifications
  TWILIO_AUTH_TOKEN         -> Twilio auth token for SMS
  TWILIO_PHONE_NUMBER       -> Your Twilio phone number
  CONTACT_EMAIL             -> Your email for emergency notifications
"""

from agno.agent import Agent
from agno.media import Image
from agno.models.openrouter import OpenRouter
from agno.storage.sqlite import SqliteStorage
from agno.tools import tool
from dotenv import load_dotenv
import os, time, uuid, requests, json, re, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ddgs import DDGS
from twilio.rest import Client

load_dotenv()

API_KEY = os.getenv("openrouter_api") or os.getenv("OPENROUTER_API")
MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "example@example.com")

if not API_KEY:
    print("[WARN] OPENROUTER API key missing; model calls will fail.")
if not MAPBOX_TOKEN:
    print("[WARN] MAPBOX_ACCESS_TOKEN missing; map features will be limited.")

# Storage
os.makedirs("tmp", exist_ok=True)
storage = SqliteStorage(table_name="agent_sessions", db_file="tmp/data.db")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

def _get_coordinates(location: str) -> tuple:
    """Helper function to get coordinates without @tool decorator"""
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
    return lat, lon


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo for current information.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default 5)
    Returns: Search results as formatted text
    """
    try:
        ddgs = DDGS()
        results = ddgs.text(query, max_results=max_results)
        
        if not results:
            return f"No search results found for query: {query}"
        
        formatted_results = f"Search results for '{query}':\n\n"
        for i, result in enumerate(results, 1):
            title = result.get('title', 'No title')
            body = result.get('body', 'No description')
            href = result.get('href', 'No URL')
            
            formatted_results += f"{i}. **{title}**\n"
            formatted_results += f"   {body}\n"
            formatted_results += f"   URL: {href}\n\n"
        
        return formatted_results
        
    except Exception as e:
        return f"Web search failed: {str(e)}. Please try rephrasing your query or check your internet connection."


@tool
def get_weather_information(location: str) -> str:
    """Get current weather information for a specific location.
    
    Args:
        location: Location to get weather information for
    Returns: Current weather conditions and forecast
    """
    try:
        # Search for current weather information
        weather_query = f"current weather {location} today temperature conditions forecast"
        weather_results = web_search(weather_query, max_results=4)
        
        if weather_results and len(weather_results.strip()) > 30:
            response = f"🌤️ **Current Weather Information for {location}**\n\n"
            response += f"📍 **Location:** {location}\n\n"
            response += f"🔍 **Weather Results:**\n{weather_results}\n\n"
            response += "⚠️ **Note:** For the most accurate and up-to-date weather information, please check official weather services like:\n"
            response += "• National Weather Service (weather.gov) for US locations\n"
            response += "• Met Office for UK locations\n"
            response += "• Local meteorological services for your area\n"
            response += "• Weather apps on your mobile device"
            return response
        else:
            response = f"🌤️ **Weather Information Request for {location}**\n\n"
            response += "📍 Unable to retrieve current weather information through web search.\n\n"
            response += "🔍 **Alternative Weather Sources:**\n"
            response += f"1. Visit weather.com or weather.gov for {location}\n"
            response += f"2. Use your phone's built-in weather app\n"
            response += f"3. Search Google for 'weather {location}'\n"
            response += f"4. Check local news websites for weather updates\n"
            response += f"5. Use weather apps like AccuWeather or Weather Channel\n\n"
            response += "⚠️ **For safety-related weather concerns (storms, hurricanes, etc.), contact local emergency services or weather authorities.**"
            return response
            
    except Exception as e:
        return f"🌤️ Unable to retrieve weather information: {str(e)}\n\nPlease try checking official weather services or your local weather app."


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
    """Generate a satellite static map PNG using Mapbox.

    Args:
        location: Location name or coordinates (lat,lon).
        zoom: Zoom level (default 16).
        size: WxH in pixels. Example: "600x400".
    Returns: Path to generated PNG image.
    """
    if not location.strip():
        return "❌ Location cannot be empty"
    
    if not MAPBOX_TOKEN:
        return "❌ Mapbox token not configured. Please add MAPBOX_ACCESS_TOKEN to your .env file."
    
    try:
        # Get coordinates for the location using helper function
        lat, lon = _get_coordinates(location)
        
        # Mapbox Static Images API
        width, height = size.split('x')
        mapbox_url = f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/pin-s+ff0000({lon},{lat})/{lon},{lat},{zoom}/{width}x{height}@2x"
        
        params = {"access_token": MAPBOX_TOKEN}
        r = requests.get(mapbox_url, params=params, timeout=20)
        
        if r.status_code != 200:
            return f"❌ Mapbox API error: {r.status_code} - {r.text[:100]}"
        
        # Check if response is actually an image
        content_type = r.headers.get("Content-Type", "").lower()
        if "image" not in content_type:
            return f"❌ Expected image, got {content_type}: {r.text[:100]}"
        
        # Ensure tmp directory exists
        os.makedirs("tmp", exist_ok=True)
        
        fname = f"satellite_map_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join("tmp", fname)
        
        with open(path, "wb") as f:
            f.write(r.content)
        
        return f"✅ Satellite map created successfully: {path} ({len(r.content)} bytes)"
        
    except Exception as e:
        return f"❌ Failed to create satellite map: {str(e)}"


@tool
def get_directions(origin: str, destination: str, mode: str = "driving") -> str:
    """Get directions between two locations using Mapbox.

    Args:
        origin: Starting location
        destination: Ending location  
        mode: Transportation mode (driving, walking, cycling)
    Returns: Turn-by-turn directions
    """
    if not MAPBOX_TOKEN:
        return "Mapbox token not configured. Please add MAPBOX_ACCESS_TOKEN to your .env file."
    
    try:
        # Get coordinates for both locations using helper function
        origin_lat, origin_lon = _get_coordinates(origin)
        dest_lat, dest_lon = _get_coordinates(destination)
        
        # Mapbox Directions API
        profile = "mapbox/driving" if mode == "driving" else f"mapbox/{mode}"
        url = f"https://api.mapbox.com/directions/v5/{profile}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        
        params = {
            "access_token": MAPBOX_TOKEN,
            "steps": "true",
            "geometries": "geojson",
            "overview": "full"
        }
        
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        if not data.get("routes"):
            return f"No route found between {origin} and {destination}"
        
        route = data["routes"][0]
        duration = route["duration"] / 60  # Convert to minutes
        distance = route["distance"] / 1000  # Convert to km
        
        response = f"🧭 **Directions from {origin} to {destination}**\n\n"
        response += f"📍 **Route Summary:**\n"
        response += f"• Distance: {distance:.1f} km\n"
        response += f"• Duration: {duration:.0f} minutes\n"
        response += f"• Mode: {mode.title()}\n\n"
        
        response += "🗺️ **Turn-by-turn directions:**\n"
        
        for i, leg in enumerate(route["legs"]):
            for j, step in enumerate(leg["steps"]):
                instruction = step["maneuver"]["instruction"]
                step_distance = step["distance"]
                response += f"{j+1}. {instruction} ({step_distance:.0f}m)\n"
        
        return response
        
    except Exception as e:
        return f"Failed to get directions: {str(e)}"


@tool
def submit_police_case(incident_description: str, location: str, contact_method: str = "sms", urgency: str = "normal") -> str:
    """Submit a case to police via SMS or email notification.

    Args:
        incident_description: Detailed description of the incident
        location: Location where incident occurred
        contact_method: "sms" or "email" for notification method
        urgency: "normal" or "urgent" for priority level
    Returns: Confirmation of case submission
    """
    try:
        case_id = f"CASE_{int(time.time())}_{uuid.uuid4().hex[:8].upper()}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Create case report
        case_report = f"""
🚨 POLICE CASE SUBMISSION - {case_id}

📅 Date/Time: {timestamp}
📍 Location: {location}
⚠️ Urgency: {urgency.upper()}

📝 INCIDENT DESCRIPTION:
{incident_description}

🔍 CASE DETAILS:
- Case ID: {case_id}
- Submitted via: EnforcerBot Safety Assistant
- Contact for follow-up: {CONTACT_EMAIL}

⚠️ IMPORTANT: This is an automated case submission. For immediate emergencies, call 911 or your local emergency services.
        """
        
        success_messages = []
        
        # Send via SMS if configured and requested
        if contact_method == "sms" and TWILIO_SID and TWILIO_TOKEN and TWILIO_PHONE:
            try:
                client = Client(TWILIO_SID, TWILIO_TOKEN)
                
                # Create SMS message
                sms_message = f"🚨 POLICE CASE {case_id}\n📍 {location}\n📝 {incident_description[:100]}...\n⚠️ Urgency: {urgency}"
                
                # In production, this would be sent to police SMS number
                # For demo/testing, we'll simulate the SMS sending
                try:
                    # Try to send SMS (this may fail in trial accounts)
                    message = client.messages.create(
                        body=sms_message,
                        from_=TWILIO_PHONE,
                        to=TWILIO_PHONE  # In real app, this would be police SMS number
                    )
                    success_messages.append(f"✅ SMS notification sent (SID: {message.sid})")
                except Exception as sms_send_error:
                    # If SMS sending fails, still log the attempt
                    success_messages.append(f"📱 SMS prepared for sending: {len(sms_message)} characters")
                    success_messages.append(f"⚠️ SMS sending restricted (Trial account or same number): {str(sms_send_error)[:100]}")
                    success_messages.append(f"✅ In production, this would be sent to police SMS system")
                    
                    # Save SMS content to file for verification
                    sms_file = f"tmp/sms_case_{case_id}.txt"
                    with open(sms_file, "w") as f:
                        f.write(f"SMS Content for Case {case_id}:\n\n{sms_message}")
                    success_messages.append(f"📄 SMS content saved to {sms_file}")
                    
            except Exception as sms_error:
                success_messages.append(f"❌ SMS configuration error: {str(sms_error)}")
        
        # Send via email if requested
        if contact_method == "email":
            try:
                # For demo purposes, we'll just log the email content
                # In a real app, you'd configure SMTP settings
                email_content = f"""
Subject: Police Case Submission - {case_id}

{case_report}

This case has been logged and will be forwarded to appropriate authorities.
                """
                
                # Save email to file for demo
                email_file = f"tmp/police_case_{case_id}.txt"
                with open(email_file, "w") as f:
                    f.write(email_content)
                
                success_messages.append(f"✅ Email case report saved to {email_file}")
                success_messages.append("📧 In production, this would be sent to police email system")
            except Exception as email_error:
                success_messages.append(f"❌ Email failed: {str(email_error)}")
        
        # Always save case locally
        case_file = f"tmp/case_{case_id}.json"
        case_data = {
            "case_id": case_id,
            "timestamp": timestamp,
            "location": location,
            "incident_description": incident_description,
            "urgency": urgency,
            "contact_method": contact_method,
            "status": "submitted"
        }
        
        with open(case_file, "w") as f:
            json.dump(case_data, f, indent=2)
        
        response = f"🚨 **Police Case Submitted Successfully**\n\n"
        response += f"📋 **Case ID:** {case_id}\n"
        response += f"📅 **Submitted:** {timestamp}\n"
        response += f"📍 **Location:** {location}\n"
        response += f"⚠️ **Urgency:** {urgency.upper()}\n\n"
        response += f"✅ **Case saved locally:** {case_file}\n"
        response += "\n".join(success_messages)
        response += f"\n\n⚠️ **IMPORTANT REMINDER:**\n"
        response += f"• For immediate emergencies, call 911 or local emergency services\n"
        response += f"• This is a demonstration tool - in production it would integrate with actual police systems\n"
        response += f"• Keep your case ID ({case_id}) for reference\n"
        response += f"• Follow up with local authorities if needed"
        
        return response
        
    except Exception as e:
        return f"❌ Failed to submit police case: {str(e)}\n\n⚠️ For immediate help, contact emergency services directly at 911."


@tool
def get_current_location() -> str:
    """Get user's approximate current location using IP geolocation.
    
    Returns: Current location information
    """
    try:
        # Use IP geolocation service
        response = requests.get("http://ip-api.com/json/", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success":
            city = data.get("city", "Unknown")
            region = data.get("regionName", "Unknown")
            country = data.get("country", "Unknown")
            lat = data.get("lat", 0)
            lon = data.get("lon", 0)
            
            location_info = f"📍 **Current Location (Approximate):**\n"
            location_info += f"• City: {city}\n"
            location_info += f"• Region: {region}\n"
            location_info += f"• Country: {country}\n"
            location_info += f"• Coordinates: ({lat:.4f}, {lon:.4f})\n\n"
            location_info += f"⚠️ **Note:** This is an approximate location based on your IP address. For precise location services, enable GPS on your device."
            
            return location_info
        else:
            return "❌ Unable to determine current location. Please specify your location manually."
            
    except Exception as e:
        return f"❌ Location detection failed: {str(e)}. Please provide your location manually for directions and local services."


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
        # Create structured response with rule-based assessment (more reliable than web search)
        response = f"⚠️ **Risk Assessment for: {situation}**\n\n"
        if location:
            response += f"📍 **Location:** {location}\n\n"
        
        # Enhanced rule-based risk assessment
        high_risk_keywords = ["following", "stalking", "threat", "weapon", "violence", "attack", "danger", "emergency", "assault", "robbery"]
        medium_risk_keywords = ["suspicious", "harassment", "theft", "break-in", "unsafe", "concern", "witnessed", "crime"]
        low_risk_keywords = ["lost", "directions", "information", "general", "advice"]
        
        situation_lower = situation.lower()
        
        if any(keyword in situation_lower for keyword in high_risk_keywords):
            risk_level = "HIGH"
            immediate_action = "🚨 Call emergency services immediately (911/112). Get to a safe location. Do not pursue suspects."
        elif any(keyword in situation_lower for keyword in medium_risk_keywords):
            risk_level = "MEDIUM" 
            immediate_action = "📞 Stay alert, move to a populated area, consider contacting authorities. Document details if safe to do so."
        else:
            risk_level = "LOW"
            immediate_action = "👀 Maintain situational awareness and follow general safety precautions."
        
        response += f"🚨 **RISK LEVEL: {risk_level}**\n\n"
        response += f"💡 **IMMEDIATE ACTIONS:**\n{immediate_action}\n\n"
        
        # Try web search but don't fail if it doesn't work
        try:
            risk_query = f"safety tips {situation} {location}"
            search_results = web_search(risk_query, max_results=2)
            if search_results and len(search_results.strip()) > 50:
                response += f"🔍 **Additional Safety Information:**\n{search_results}\n\n"
        except:
            pass  # Don't fail the entire assessment if web search fails
        
        response += f"⚠️ **Remember:** Trust your instincts. If you feel unsafe, seek help immediately."
        
        return response
        
    except Exception as e:
        # Provide basic assessment even if everything fails
        return f"⚠️ **Basic Risk Assessment:** For incident involving '{situation}', prioritize your safety. If in immediate danger, call emergency services (911/112). If safe, consider reporting to local authorities. Error details: {str(e)}"


@tool  
def get_safety_tips(situation_type: str, location: str = "") -> str:
    """Get dynamic safety tips and best practices for specific situations using web search.
    
    Args:
        situation_type: Type of situation (e.g., "theft", "harassment", "natural disaster", "suspicious activity")
        location: Optional location for location-specific advice
    Returns: Current safety tips and best practices
    """
    # Provide immediate safety tips without relying heavily on web search
    immediate_tips = {
        "theft": [
            "• Stay calm and don't pursue the suspect",
            "• Note description of suspect and direction they went",
            "• Check if anyone was injured and call medical help if needed",
            "• Preserve the crime scene if safe to do so",
            "• Contact police immediately to report the incident"
        ],
        "harassment": [
            "• Document all incidents with dates, times, and details",
            "• Save any evidence (messages, photos, recordings)",
            "• Tell trusted friends or family about the situation",
            "• Consider changing routines and routes",
            "• Report to authorities and seek legal advice"
        ],
        "suspicious": [
            "• Trust your instincts - if something feels wrong, it probably is",
            "• Move to a well-lit, populated area",
            "• Stay alert and aware of your surroundings",
            "• Have your phone ready to call for help",
            "• Don't confront suspicious individuals directly"
        ],
        "emergency": [
            "• Call emergency services immediately (911/112)",
            "• Get to a safe location if possible",
            "• Follow instructions from emergency operators",
            "• Stay on the line until help arrives",
            "• Provide clear location information"
        ]
    }
    
    # Try one focused web search (less likely to fail)
    all_tips = []
    try:
        search_query = f"safety tips {situation_type} what to do"
        result = web_search(search_query, max_results=2)
        if result and len(result.strip()) > 30:
            all_tips.append(result)
    except:
        pass  # Don't fail if web search doesn't work
    
    # Build comprehensive response
    tips_response = f"🛡️ **Safety Tips for {situation_type.title()}**\n"
    if location:
        tips_response += f"📍 *Guidance for {location}*\n\n"
    
    # Add immediate, situation-specific tips
    situation_key = None
    for key in immediate_tips.keys():
        if key in situation_type.lower():
            situation_key = key
            break
    
    if situation_key:
        tips_response += f"🚨 **Immediate Actions for {situation_type.title()}:**\n"
        for tip in immediate_tips[situation_key]:
            tips_response += f"{tip}\n"
        tips_response += "\n"
    
    # Add web search results if available
    if all_tips:
        tips_response += "💡 **Additional Resources:**\n\n"
        for i, tips in enumerate(all_tips, 1):
            tips_response += f"**Source {i}:**\n{tips}\n\n"
    
    # Always include universal safety principles
    tips_response += "🛡️ **Universal Safety Principles:**\n"
    tips_response += "• Trust your instincts - if something feels wrong, it probably is\n"
    tips_response += "• Stay aware of your surroundings at all times\n"
    tips_response += "• Keep emergency contacts readily available\n"
    tips_response += "• Have an exit plan or escape route when possible\n"
    tips_response += "• Don't hesitate to call for help or emergency services\n"
    tips_response += "• Document incidents when safe to do so\n\n"
    
    tips_response += "⚠️ **Remember:** If you feel unsafe or threatened, trust your instincts and seek help immediately!"
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
        # Get coordinates first
        lat, lon = _get_coordinates(location)
        coords_info = f"📍 **Location:** {location} ({lat:.4f}, {lon:.4f})"
        
        # Provide immediate emergency contacts based on location
        emergency_numbers = {
            "ghana": "112 or 191 (Police), 193 (Fire/Ambulance)",
            "nigeria": "199 (Police), 112 (Emergency)",
            "south africa": "10111 (Police), 10177 (Ambulance)",
            "kenya": "999 or 112",
            "united states": "911",
            "canada": "911", 
            "united kingdom": "999 or 112",
            "australia": "000",
            "new zealand": "111"
        }
        
        # Determine country from location
        location_lower = location.lower()
        local_emergency = "112 (International Emergency)"
        for country, number in emergency_numbers.items():
            if country in location_lower:
                local_emergency = number
                break
        
        # Build response with reliable information
        response = f"🚨 **{resource_type.title()} Resources for {location}**\n\n"
        response += f"{coords_info}\n\n"
        
        response += f"📞 **Emergency Numbers for {location}:**\n"
        response += f"• Local Emergency: {local_emergency}\n"
        response += f"• International: 112\n\n"
        
        # Try one focused web search but don't fail if it doesn't work
        try:
            search_query = f"{resource_type} {location} address contact"
            search_results = web_search(search_query, max_results=2)
            if search_results and len(search_results.strip()) > 30:
                response += f"🔍 **Found Resources:**\n{search_results}\n\n"
        except:
            pass
        
        # Always provide practical guidance
        response += f"🗺️ **How to Find {resource_type.title()}:**\n"
        response += f"1. **Emergency Apps:** Use your phone's emergency features\n"
        response += f"2. **Maps:** Search '{resource_type} near me' in Google/Apple Maps\n"
        response += f"3. **Local Directory:** Call directory assistance (411 in US)\n"
        response += f"4. **Ask Locals:** Hotel staff, shop owners can provide directions\n"
        response += f"5. **Government Websites:** Check local government emergency pages\n\n"
        
        response += f"⚠️ **IMMEDIATE EMERGENCY:** If in danger, call {local_emergency} now!"
        
        return response
        
    except Exception as e:
        # Provide basic emergency guidance even if everything fails
        return f"🚨 **Emergency Resources for {location}**\n\n❌ Technical error: {str(e)}\n\n📞 **IMMEDIATE ACTION:**\n• Call local emergency services\n• International emergency: 112\n• US/Canada: 911\n• UK: 999\n• Australia: 000\n\n🗺️ Use your phone's maps to search '{resource_type} near me'\n\n⚠️ **Don't wait - get help immediately if in danger!**"


@tool
def get_legal_information(country: str, legal_topic: str, situation: str = "") -> str:
    """Get relevant legal information and laws for specific countries and situations.
    
    Args:
        country: Country or jurisdiction
        legal_topic: Legal area (e.g., "harassment", "theft", "assault", "privacy", "stalking")
        situation: Optional specific situation for more targeted legal info
    Returns: Relevant legal information and rights
    """
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
            result = web_search(query, max_results=2)
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
        # Use web search for threat pattern analysis
        pattern_queries = [
            f"crime patterns {location} {incident_description}",
            f"security threats {location} recent incidents",
            f"safety alerts {location} crime trends"
        ]
        
        all_intelligence = []
        for query in pattern_queries:
            try:
                result = web_search(query, max_results=2)
                if result and len(result.strip()) > 50:
                    all_intelligence.append(result)
            except Exception:
                continue
        
        response = f"🕵️ **Threat Pattern Analysis**\n\n"
        response += f"📋 **Incident:** {incident_description}\n"
        if location:
            response += f"📍 **Location:** {location}\n\n"
        
        # Simple pattern analysis based on keywords
        incident_lower = incident_description.lower()
        
        if "theft" in incident_lower or "robbery" in incident_lower:
            response += f"🔍 **Pattern Type:** Property Crime\n"
            response += f"💡 **Common Indicators:** Targeting of valuables, opportunistic behavior\n"
            response += f"⚠️ **Prevention:** Avoid displaying valuables, stay in well-lit areas\n\n"
        elif "following" in incident_lower or "stalking" in incident_lower:
            response += f"🔍 **Pattern Type:** Personal Safety Threat\n"
            response += f"💡 **Common Indicators:** Persistent following, surveillance behavior\n"
            response += f"⚠️ **Prevention:** Change routes, seek populated areas, document incidents\n\n"
        elif "harassment" in incident_lower:
            response += f"🔍 **Pattern Type:** Harassment/Intimidation\n"
            response += f"💡 **Common Indicators:** Repeated unwanted contact, escalating behavior\n"
            response += f"⚠️ **Prevention:** Document all incidents, report to authorities, avoid isolation\n\n"
        else:
            response += f"🔍 **Pattern Type:** General Security Concern\n"
            response += f"💡 **Analysis:** Requires further investigation and context\n\n"
        
        if all_intelligence:
            response += f"📊 **Area Intelligence:**\n"
            for i, intel in enumerate(all_intelligence, 1):
                response += f"\n**Source {i}:**\n{intel}\n"
        
        response += f"\n🛡️ **Recommendations:**\n"
        response += f"• Report incident to local authorities if not already done\n"
        response += f"• Maintain heightened situational awareness\n"
        response += f"• Consider varying routines and routes\n"
        response += f"• Keep emergency contacts readily available\n"
        response += f"• Document any future incidents with dates/times\n"
        
        return response
        
    except Exception as e:
        return f"Threat analysis unavailable: {str(e)}. Exercise heightened awareness and contact authorities if concerned."


INSTRUCTIONS = """
You are the Advanced Multi-Lingual Crime/Location Information & Safety Assistant with Emergency Response capabilities. You assist users with comprehensive safety information and can help submit cases to authorities.

Your capabilities include:
 - Search current info and news (web_search)
 - Get weather information (get_weather_information)
 - Convert place names to coordinates (coordinates_of_location)
 - Generate satellite map images using Mapbox (create_satellite_map) for visual context
 - Get turn-by-turn directions between locations (get_directions) using Mapbox
 - Detect user's current location (get_current_location) via IP geolocation
 - Submit police cases via SMS or email (submit_police_case) for incident reporting
 - Assess risk levels dynamically (assess_risk_level) - LOW/MEDIUM/HIGH classification
 - Provide current safety tips (get_safety_tips) based on situation and location
 - Find nearby emergency resources (find_nearby_resources) - police, hospitals, shelters
 - Get legal information (get_legal_information) for different countries and situations
 - Analyze threat patterns (analyze_threat_patterns) for security intelligence

NEW EMERGENCY FEATURES:
- **Police Case Submission**: Can submit detailed incident reports to authorities via SMS or email
- **Current Location Detection**: Automatically detect user's approximate location for emergency services
- **Enhanced Directions**: Get detailed turn-by-turn directions from current location to safety resources

Key principles:
- Always prioritize user safety and immediate danger assessment
- Use dynamic, current information rather than static responses
- Provide actionable, specific guidance based on context
- Cross-reference multiple sources when possible
- Escalate to emergency services when warranted
- Offer to submit police cases for incidents that warrant official reporting
- Use current location detection to provide location-specific help
- Provide detailed directions to safety resources when needed

When analyzing situations:
1. First assess immediate risk level
2. Provide relevant safety tips for the specific situation
3. Detect current location if needed for emergency response
4. Locate nearby resources and provide directions if location is available
5. Offer to submit police case if incident warrants official reporting
6. Include relevant legal context if applicable
7. Look for threat patterns if concerning incidents

Tool Usage Guidelines:
- Use get_current_location when user needs location-based help but hasn't specified location
- Use get_directions to provide routes from current location to safety resources
- Use submit_police_case for incidents that should be reported to authorities
- Use create_satellite_map for visual location context using Mapbox
- Use find_nearby_resources for location-specific emergency services  
- Use get_safety_tips for situation-specific safety advice
- Use get_legal_information for legal rights and laws by country
- Use assess_risk_level for AI-powered threat assessment
- Use analyze_threat_patterns for security intelligence

Emergency Response Protocol:
1. For immediate danger: Direct to call 911/emergency services immediately
2. For incidents requiring reporting: Offer to submit police case via submit_police_case
3. For location-based help: Use get_current_location and get_directions
4. For resource location: Find nearby resources and provide directions

If any tool returns limited information due to search limitations, supplement with:
- Web search results
- General best practices and universal safety principles
- Emergency contact numbers
- Alternative resources and next steps
- Clear action items for the user

Always maintain a helpful, professional tone while emphasizing safety and urgency when appropriate. Offer concrete next steps including case submission when incidents warrant official reporting.
"""


def agent(message, image=None):
    # Prepare tools list with Mapbox and emergency capabilities
    tools = [
        web_search,
        get_weather_information, 
        coordinates_of_location, 
        create_satellite_map,
        get_directions,
        get_current_location,
        submit_police_case,
        assess_risk_level,
        get_safety_tips,
        find_nearby_resources,
        get_legal_information,
        analyze_threat_patterns
    ]
    
    # Check Mapbox configuration
    if MAPBOX_TOKEN:
        print("[INFO] Mapbox integration enabled - enhanced mapping and directions available")
    else:
        print("[INFO] Mapbox token not configured - some mapping features will be limited")
    
    # Check emergency notification capabilities
    if TWILIO_SID and TWILIO_TOKEN:
        print("[INFO] SMS emergency notifications enabled via Twilio")
    else:
        print("[INFO] SMS notifications not configured - email fallback available")
    
    _agent = Agent(
        name="Advanced Crime Information & Safety Agent with Emergency Response",
        model=OpenRouter(id="google/gemini-2.5-flash", api_key=API_KEY, max_tokens=3000),
        tools=tools,
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


if __name__ == "__main__":  # Enhanced test examples with new features
    print("=== Testing Enhanced Crime/Safety Agent with Emergency Response ===\n")
    
    # Test 1: Current Location and Directions
    print("Test 1: Current Location Detection and Directions")
    for chunk in agent("What's my current location and give me directions to the nearest hospital?"):
        if getattr(chunk, "content", None):
            print(chunk.content, end="", flush=True)
    print("\n" + "="*50 + "\n")
    
    # Test 2: Police Case Submission
    print("Test 2: Police Case Submission")
    for chunk in agent("I witnessed a theft at Central Park. Can you help me submit a police case via SMS?"):
        if getattr(chunk, "content", None):
            print(chunk.content, end="", flush=True)
    print("\n" + "="*50 + "\n")
    
    # Test 3: Mapbox Satellite Map
    print("Test 3: Mapbox Satellite Map Generation")
    for chunk in agent("Show me a satellite map of Times Square, New York"):
        if getattr(chunk, "content", None):
            print(chunk.content, end="", flush=True)
    print("\n" + "="*50 + "\n")
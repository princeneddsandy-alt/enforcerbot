import streamlit as st
import tempfile 
import os, glob
from agent import agent

st.set_page_config(
    page_title="� EnforcerBot - Advanced Safety & Crime Intelligence �", 
    page_icon="🔍",
    layout="wide"
)

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar with features and examples
with st.sidebar:
    st.header("🚨 EnforcerBot Features")
    st.markdown("""
    **Advanced Safety & Crime Intelligence Assistant with Emergency Response**
    
    🎯 **Core Capabilities:**
    - 🔍 Risk Assessment (Low/Medium/High)
    - 💡 Dynamic Safety Tips & Best Practices  
    - 📍 Emergency Resource Location & Directions
    """)
    
    st.subheader("📋 Example Use Cases")
    
    example_scenarios = {
        "🚶‍♀️ Personal Safety": "I'm walking alone at night in downtown Seattle and feel like someone is following me. What should I do and help me submit a police case?",
        "🏠 Home Security": "Assess the risk level of recent break-ins in my neighborhood in Austin, Texas and give me safety tips",
    }
    
    for scenario, prompt in example_scenarios.items():
        if st.button(scenario, key=scenario, help="Click to try this example"):
            st.session_state.example_prompt = prompt
    
    st.markdown("---")
    st.markdown("**⚠️ Emergency Disclaimer:**")
    st.markdown("*If you are in immediate danger, call local emergency services immediately (911, 999, 112)*")

# Main content area
col1, col2 = st.columns([3, 1])

with col1:
    st.title("🚨 EnforcerBot")
    st.markdown("*Advanced Safety & Crime Intelligence Assistant*")
    
with col2:
    st.markdown("### � Emergency Numbers")
    st.markdown("**Grenada:** 911")


# Display chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("image"):
            st.image(msg["image"])
        st.markdown(msg["content"])
        # Display any tool-returned images
        if msg.get("tool_images"):
            for img_path in msg["tool_images"]:
                if os.path.exists(img_path):
                    st.image(img_path, caption="🗺️ Satellite Map View")

# Handle example prompts from sidebar
example_prompt = st.session_state.get("example_prompt", "")
if example_prompt:
    st.session_state.messages.append({"role": "user", "content": example_prompt})
    st.session_state.example_prompt = ""  # Clear it
    st.rerun()

# Chat input
prompt_placeholder = "🔍 Ask about safety, crime, legal rights, emergency resources, threat assessment, or location intelligence..."
if data := st.chat_input(prompt_placeholder, accept_file=True):
    prompt = data.get("text", "")
    uploaded = data.get("files")
    user_msg = {"role": "user", "content": prompt}
    if uploaded:
        user_msg["image"] = uploaded
    st.session_state.messages.append(user_msg)
    
    # Echo user
    with st.chat_message("user"):
        if uploaded:
            st.image(uploaded, width=200)
        st.markdown(prompt)

    # Assistant reply
    map_images = []  # collected satellite map image paths
    # Snapshot existing satellite map files so we can detect new ones produced during this run
    existing_maps = set(glob.glob("tmp/satellite_map_*.png"))
    full = ""  # Ensure 'full' is always defined
    with st.chat_message("assistant"):
        ph = st.empty()
        action_ph = st.empty()
        try:
            image_path = None
            if uploaded:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded[0].name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded[0].getvalue()); image_path = tmp.name

            stream = agent(st.session_state.messages, image_path)
            current_tool = None

            for chunk in stream:
                if hasattr(chunk, "event"):
                    if chunk.event == "RunResponseContent" and getattr(chunk, "content", None):
                        full += chunk.content
                        if current_tool:
                            action_ph.empty(); current_tool = None
                    elif chunk.event == "ToolCallStarted":
                        current_tool = chunk.tool.tool_name
                        tool_emoji = {
                            "assess_risk_level": "⚠️",
                            "get_safety_tips": "💡", 
                            "find_nearby_resources": "📍",
                            "get_legal_information": "⚖️",
                            "analyze_threat_patterns": "🕵️",
                            "create_satellite_map": "🗺️",
                            "coordinates_of_location": "📌",
                            "web_search": "🔍",
                            "get_weather_information": "🌤️",
                            "get_directions": "🧭", 
                            "get_current_location": "📍",
                            "submit_police_case": "🚨"
                        }.get(current_tool, "🔧")
                        action_ph.info(f"{tool_emoji} {current_tool.replace('_', ' ').title()}...")
                    elif chunk.event == "ToolCallCompleted":
                        # Detect newly created satellite map images after create_satellite_map tool finishes
                        if current_tool == "create_satellite_map":
                            new_maps = set(glob.glob("tmp/satellite_map_*.png")) - existing_maps
                            for mp in sorted(new_maps):
                                if os.path.exists(mp):
                                    map_images.append(mp)
                                    ph.image(mp, caption="🗺️ Satellite View")
                            existing_maps |= new_maps
                        action_ph.success(f"✅ {current_tool.replace('_', ' ').title()} completed")
                if full:
                    ph.markdown(full + "▌")

            if image_path: os.unlink(image_path)
            action_ph.empty()
            ph.markdown(full)

        except Exception as e:
            action_ph.empty()
            ph.markdown(f"Error: {e}")

    # Store assistant msg
    asst = {"role": "assistant", "content": full}
    if map_images:
        asst["tool_images"] = map_images
    st.session_state.messages.append(asst)

# # Footer with additional info
# st.markdown("---")
# st.markdown("""
# <div style='text-align: center; color: #666; font-size: 0.8em;'>
# <p><strong>🚨 EnforcerBot</strong> - Advanced Safety & Crime Intelligence Assistant with Emergency Response</p>
# <p>Features: Risk Assessment • Safety Tips • Resource Location • Legal Information • Threat Analysis • Mapbox Maps • Police Case Submission • Current Location • Directions</p>
# <p><em>Always contact emergency services immediately if you are in immediate danger</em></p>
# </div>
# """, unsafe_allow_html=True)

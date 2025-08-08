import streamlit as st
import tempfile 
import os, glob
from agent import agent

st.set_page_config(page_title="👮The Enforcer Bot👮", page_icon="🔍")

if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("👮The Enforcer👮")

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
                    st.image(img_path, caption="🗺️ Map View")

# Chat input
if data := st.chat_input("Ask me about anything...", accept_file=True):
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
    map_images = []
    existing_maps= set(glob.glob("tmp/satellite_map_*.png"))
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
                        action_ph.info(f"🔧 Calling {current_tool}...")
                    elif chunk.event == "ToolCallCompleted":
                        if current_tool == "google_maps":
                            mp = "static_map.png"
                            if os.path.exists(mp):
                                map_images.append(mp)
                                ph.image(mp, caption="🗺️ Map View")
                        action_ph.success("✅ Tool call completed")
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

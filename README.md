# EnforcerBot - Safety & Crime Intelligence Assistant

A web-based AI assistant providing real-time safety guidance, threat assessment, and emergency response support.

## What It Does

- Risk assessment with threat level ratings (Low/Medium/High)
- Safety guidance and best practices
- Emergency resource location (police, hospitals, shelters)
- Location services and satellite map generation
- Police case reporting with auto-generated case IDs
- Legal information by jurisdiction
- Real-time web search for safety information

## Available Tools

- **analyze_situation** - Threat assessment and safety recommendations
- **web_search** - Current safety and crime information
- **get_current_location** - IP-based location detection
- **coordinates_of_location** - Location to GPS conversion
- **create_satellite_map** - Satellite map generation
- **find_nearby_resources** - Emergency services locator
- **submit_police_case** - Police case report submission

## Installation Requirements

- Python 3.8 or higher
- pip package manager
- Internet connection for API calls

## Step-by-Step Installation

1. Navigate to project directory:
   ```bash
   cd enforcerbot
   ```

2. Install all required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create environment file `.env` in project root

4. Add required API keys to `.env` file:
   ```
   OPENROUTER_API=your_openrouter_api_key_here
   ```

5. Add optional API keys (recommended):
   ```
   MAPBOX_ACCESS_TOKEN=your_mapbox_token_here
   TWILIO_ACCOUNT_SID=your_twilio_sid_here
   TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
   TWILIO_PHONE_NUMBER=your_twilio_phone_number_here
   CONTACT_EMAIL=your_email@example.com
   ```

## Environment Variables Explained

**Required Variables:**
- `OPENROUTER_API` - Your OpenRouter API key for AI model access

**Optional Variables:**
- `MAPBOX_ACCESS_TOKEN` - For satellite map generation and location services
- `TWILIO_ACCOUNT_SID` - For SMS emergency notifications
- `TWILIO_AUTH_TOKEN` - For SMS emergency notifications  
- `TWILIO_PHONE_NUMBER` - Your Twilio phone number for SMS
- `CONTACT_EMAIL` - Contact email for API requests and notifications

## Getting API Keys

1. **OpenRouter API** (Required):
   - Visit https://openrouter.ai
   - Create account and generate API key
   - Add to `.env` as `OPENROUTER_API=your_key`

2. **Mapbox Token** (Optional but recommended):
   - Visit https://mapbox.com
   - Create account and get access token
   - Add to `.env` as `MAPBOX_ACCESS_TOKEN=your_token`

3. **Twilio Credentials** (Optional):
   - Visit https://twilio.com
   - Create account and get SID, Auth Token, and Phone Number
   - Add all three to `.env` file

## Running the Application

Primary method:
```bash
streamlit run app.py
```

If above doesn't work, use:
```bash
python3 -m streamlit run app.py
```

## Accessing the App

1. Open web browser
2. Navigate to `http://localhost:8501`
3. Use sidebar buttons for quick actions
4. Type questions in chat interface
5. AI automatically selects appropriate tools

## Troubleshooting

- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check `.env` file exists and contains required keys
- Verify Python version is 3.8 or higher: `python --version`
- Try alternative run command: `python3 -m streamlit run app.py`
- Check internet connection for API calls

## Usage Tips

- Use sidebar quick action buttons for common tasks
- Ask specific questions about safety concerns
- Request maps by mentioning locations
- Report incidents for case submission
- Emergency numbers are displayed in top right

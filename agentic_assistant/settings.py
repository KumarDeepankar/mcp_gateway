# agentic_assistant/settings.py
import os
import google.generativeai as genai

# --- Environment-Aware Configuration ---
ENV_TYPE = os.environ.get('ENV_TYPE', 'local')

print(f"DEBUG_AGENT_SETTINGS: Running in '{ENV_TYPE}' environment.")

# Define configurations for different environments
CONFIG = {
    'local': {
        'APP_HOST': '127.0.0.1',
        'MCP_SERVER_BASE_URL': 'http://localhost:8021',
        'AGENT_INTERFACE_BASE_URL': 'http://localhost:8051',
        'EVAL_SERVICE_URL': 'http://localhost:8011',
    },
    'docker': {
        'APP_HOST': '0.0.0.0',
        'MCP_SERVER_BASE_URL': 'http://mcp-toolbox:8021',
        'AGENT_INTERFACE_BASE_URL': 'http://agent-interface:8051',
        'EVAL_SERVICE_URL': 'http://eval-service:8011',
    },
    'k8s': {
        'APP_HOST': '0.0.0.0',
        'MCP_SERVER_BASE_URL': 'http://mcp-toolbox.default.svc.cluster.local:8021',
        'AGENT_INTERFACE_BASE_URL': 'http://agent-interface.default.svc.cluster.local:8051',
        'EVAL_SERVICE_URL': 'http://eval-service.default.svc.cluster.local:8011',
    }
}

# Select the active configuration based on the environment type
ACTIVE_CONFIG = CONFIG.get(ENV_TYPE, CONFIG['local'])


# --- Secrets Configuration ---
# As requested, secrets are kept in this file.
# WARNING: This is NOT a recommended practice for production.
# For production, use environment variables or a secrets management system.
GEMINI_API_KEY = 'AIzaSyDw43aTfcsXFwDk0OBwxQEfZScVGX4Fo74'


# --- Gemini Model Initialization ---
gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        print("DEBUG_AGENT_SETTINGS: Gemini Pro model initialized successfully.")
    except Exception as e:
        print(f"DEBUG_AGENT_SETTINGS: CRITICAL ERROR initializing Gemini: {e}. Gemini functionalities will be disabled.")
else:
    print("DEBUG_AGENT_SETTINGS: Gemini API key is missing. Gemini functionalities will be disabled.")


# --- Dynamic Application Settings ---
# These variables are now set based on the ACTIVE_CONFIG selected above.
APP_HOST = ACTIVE_CONFIG['APP_HOST']
APP_PORT = int(os.environ.get("APP_PORT", 8000)) # Port can still be overridden for flexibility
MCP_SERVER_BASE_URL = ACTIVE_CONFIG['MCP_SERVER_BASE_URL']
AGENT_INTERFACE_BASE_URL = ACTIVE_CONFIG['AGENT_INTERFACE_BASE_URL']
EVAL_SERVICE_URL = ACTIVE_CONFIG['EVAL_SERVICE_URL']

# --- MODERNIZED MCP ENDPOINT ---
# This single endpoint is used for all MCP communication (list, call, etc.)
# in the new Streamable HTTP architecture. It will now correctly point to the toolbox.
MCP_MESSAGE_ENDPOINT = f"{MCP_SERVER_BASE_URL}/mcp"


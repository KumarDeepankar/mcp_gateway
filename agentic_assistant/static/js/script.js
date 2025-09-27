// agentic_assistant/static/js/script.js
document.getElementById('copyright-year').textContent = new Date().getFullYear();

// Declare variables for DOM elements in a higher scope
let chatConsole, messageInput, sendButton, chatMainContent, pageLogo,
    sidebar, sidebarToggleIcon, settingsModal, settingsToolButton,
    modalCloseButton, modalThinkingToggleCheckbox, queryModeButton,
    researchModeButton, researchPlanModal, researchModalCloseButton,
    researchPlanEditor, researchTaskDescriptionEl, addPlanStepButton,
    cancelResearchPlanButton, submitResearchPlanButton, uploadButton, fileUploadInput, fileStagingArea,
    stagedFileNameEl, removeStagedFileBtn, toolListButton, toolListModal,
    resourceListContainer, newConversationButton, conversationHistoryList;

// Global state variables
let currentSessionId = null;
let currentAiMessageElement = null;
let currentTurnExchangeContainer = null;
let showThinking = true;
let currentMode = 'query';
let currentResearchQuery = '';
let conversationHistory = [];
let streamedHtmlContent = '';
let isChatSessionStarted = false;
let stagedFileContent = null;
let userToolSelections = new Set();
let userAgentSelections = new Set();
let availableTools = new Map();
let availableAgents = new Map();

// Dynamic endpoint configuration based environment detection
function detectEnvironment() {
    const hostname = window.location.hostname;
    const port = window.location.port;
    
    // K8s detection - Emissary ingress typically uses port 8080 via port-forward
    const isK8sEmissary = (hostname === 'localhost' || hostname === '127.0.0.1') && 
                         port && parseInt(port) === 8080;
    
    // Advanced K8s detection - NodePort services often use localhost with high ports
    const isK8sNodePort = (hostname === 'localhost' || hostname === '127.0.0.1') && 
                         port && parseInt(port) >= 30000 && parseInt(port) <= 32767;
    
    // Kubernetes detection
    if (isK8sEmissary || isK8sNodePort ||
        hostname.includes('.svc.cluster.local') || 
        hostname.includes('k8s') || 
        hostname.includes('cluster') ||
        (!port || port === '80' || port === '443') && hostname !== 'localhost' && hostname !== '127.0.0.1') {
        return 'k8s';
    }
    
    // Local development detection (localhost with standard dev ports)
    // Exception: port 8080 is likely kubectl port-forward for k8s services
    if ((hostname === 'localhost' || hostname === '127.0.0.1') && 
        port && port === '8080') {
        return 'k8s';
    }
    
    if ((hostname === 'localhost' || hostname === '127.0.0.1') && 
        (!port || parseInt(port) < 30000)) {
        return 'local';
    }
    
    // Docker detection (usually uses container names or Docker bridge IPs)
    return 'docker';
}

function getServiceEndpoints() {
    const env = detectEnvironment();
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const currentOrigin = window.location.origin;
    
    const endpoints = {
        local: {
            mcp_toolbox: 'http://localhost:8021/mcp',
            agent_interface: 'http://localhost:8051/rpc',
            logo_service: 'http://localhost:5004'
        },
        docker: {
            // For Docker, try the current host first, then fallback to service names
            mcp_toolbox: `${protocol}//${hostname}:8021/mcp`,
            agent_interface: `${protocol}//${hostname}:8051/rpc`,
            logo_service: `${protocol}//${hostname}:5004`
        },
        k8s: {
            // In K8s with Emissary ingress, services are exposed via path-based routing
            // Based on emissary-mappings.yaml:
            // - /toolbox/ -> mcp-toolbox:8021 (MCP protocol endpoint)
            // - /agent-interface/ -> agent-interface:8051 (JSON-RPC endpoint) 
            // - /logos/ -> logo-service:5004 (Logo service endpoint)
            mcp_toolbox: `${currentOrigin}/toolbox/mcp`,
            agent_interface: `${currentOrigin}/agent-interface/rpc`,
            logo_service: `${currentOrigin}/logos`
        }
    };
    
    // Smart fallback: try to construct URLs based on current location
    const fallbackEndpoints = {
        mcp_toolbox: `${protocol}//${hostname}:8021/mcp`,
        agent_interface: `${protocol}//${hostname}:8051/rpc`,
        logo_service: `${protocol}//${hostname}:5004`
    };
    
    // If hostname suggests K8s but using non-standard setup, try port-based access
    // Exception: Don't override k8s endpoints if we're in a proper k8s environment
    if (env === 'k8s' && (hostname.includes('localhost') || hostname.match(/^\d+\.\d+\.\d+\.\d+$/))) {
        // Only use fallback if not in a proper ingress setup  
        // Special case: If we're on localhost:8080, this is likely kubectl port-forward, use k8s paths
        if (hostname === 'localhost' && window.location.port === '8080') {
            console.log('Detected kubectl port-forward setup, using k8s endpoints');
            // Use k8s endpoints but don't return fallback
        } else if (!currentOrigin.includes('http') || (hostname === 'localhost' && window.location.port !== '8080')) {
            console.log('Using fallback endpoints for k8s environment');
            return fallbackEndpoints;
        }
    }
    
    return endpoints[env] || fallbackEndpoints;
}

// Initialize endpoints dynamically
const SERVICE_ENDPOINTS = getServiceEndpoints();
const detectedEnv = detectEnvironment();
console.log('Detected environment:', detectedEnv);
console.log('Current origin:', window.location.origin);
console.log('Service endpoints:', SERVICE_ENDPOINTS);

const FASTAPI_QUERY_ENDPOINT = '/chat';
const FASTAPI_RESEARCH_START_PLAN_ENDPOINT = '/research/start_plan';
const FASTAPI_RESEARCH_EXECUTE_PLAN_ENDPOINT = '/research/execute_plan';
const FASTAPI_UPLOAD_ENDPOINT = '/upload-document';
const MCP_TOOLBOX_ENDPOINT = SERVICE_ENDPOINTS.mcp_toolbox;
const AGENT_INTERFACE_RPC_ENDPOINT = SERVICE_ENDPOINTS.agent_interface;

// Smart endpoint resolver with fallback logic
async function getWorkingEndpoint(baseEndpoints, endpointType = 'agent_interface') {
    let possibleUrls = [];
    
    if (endpointType === 'agent_interface') {
        possibleUrls = [
            baseEndpoints.agent_interface,
            // Fallback URLs to try
            `${window.location.protocol}//${window.location.hostname}:8051/rpc`,
            `http://${window.location.hostname}:8051/rpc`,
            `${window.location.origin}/agent-interface/rpc`,
        ];
    } else if (endpointType === 'mcp_toolbox') {
        const origin = window.location.origin;
        const protocol = window.location.protocol;
        const hostname = window.location.hostname;
        
        possibleUrls = [
            baseEndpoints.mcp_toolbox,
            // Emissary ingress paths (based on k8/emissary-mappings.yaml)
            `${origin}/toolbox/mcp`,
            `${origin}/toolbox/mcp`, 
            `${origin}/tools/mcp`, 
            // Direct port access fallbacks
            `${protocol}//${hostname}:8021/mcp`,
            `http://${hostname}:8021/mcp`,
            // Alternative ingress patterns
            `${origin}/toolbox/mcp`,
            `${origin}/api/toolbox/mcp`,
        ];
    } else if (endpointType === 'logo_service') {
        const origin = window.location.origin;
        const protocol = window.location.protocol;
        const hostname = window.location.hostname;
        
        possibleUrls = [
            baseEndpoints.logo_service,
            // Emissary ingress path (based on k8/emissary-mappings.yaml)
            `${origin}/logos`,
            // Try direct service access for kubectl port-forward scenarios
            `${protocol}//${hostname}:5004`,
            `http://${hostname}:5004`,
            // Alternative k8s ingress patterns
            `${origin}/logos/`,
            `${origin}/logo-service`,
            `${origin}/api/logos`,
            // Additional k8s service patterns
            `${origin}/logo`,
            `${origin}/logo-svc`,
            // Development and testing patterns
            `http://localhost:5004`,
            `http://127.0.0.1:5004`,
        ];
    }
    
    console.log(`Testing ${possibleUrls.length} possible URLs for ${endpointType}:`, possibleUrls);
    
    for (const url of possibleUrls) {
        console.log(`Testing ${endpointType} endpoint: ${url}`);
        try {
            // Quick test to see if endpoint is reachable
            let testPayload;
            
            if (endpointType === 'mcp_toolbox') {
                // MCP toolbox expects specific MCP protocol format
                testPayload = {
                    jsonrpc: "2.0",
                    method: "initialize",
                    params: {
                        protocolVersion: "2025-06-18",
                        clientInfo: {
                            name: "connectivity-test",
                            version: "1.0.0"
                        }
                    },
                    id: "connectivity-test"
                };
            } else if (endpointType === 'logo_service') {
                // Logo service - test with health endpoint first
                try {
                    const healthResponse = await fetch(`${url}/health`, {
                        method: 'GET',
                        headers: { 'Accept': 'application/json' },
                        timeout: 5000
                    });
                    
                    if (healthResponse.ok) {
                        console.log(`✅ Logo service endpoint found via health check: ${url}`);
                        return url;
                    }
                } catch (healthError) {
                    console.log(`Health check failed for ${url}, trying direct endpoint test:`, healthError.message);
                }
                
                // Fallback: test generate-form-raw endpoint directly
                try {
                    const testPayload = {
                        name: "connectivity-test",
                        parameters: { test: "connectivity" }
                    };
                    
                    const testResponse = await fetch(`${url}/generate-form-raw`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(testPayload),
                        timeout: 5000
                    });
                    
                    if (testResponse.ok || testResponse.status === 422) {
                        // 422 is ok - means endpoint exists but validation failed
                        console.log(`✅ Logo service endpoint found via direct test: ${url}`);
                        return url;
                    }
                } catch (testError) {
                    console.log(`Direct endpoint test failed for ${url}: ${testError.message}`);
                }
                continue;
            } else {
                // Agent interface expects JSON-RPC format
                testPayload = {
                    jsonrpc: "2.0",
                    method: "system.ping",
                    params: {},
                    id: "connectivity-test"
                };
            }
            
            const headers = { 'Content-Type': 'application/json' };
            if (endpointType === 'mcp_toolbox') {
                headers['Accept'] = 'application/json, text/event-stream';
            }
            
            const testResponse = await fetch(url, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(testPayload)
            });
            
            if (testResponse.ok || testResponse.status === 404) {
                // 404 is ok - means server is there but method not found
                console.log(`Working ${endpointType} endpoint found: ${url}`);
                return url;
            }
        } catch (error) {
            console.log(`Failed to connect to ${url}: ${error.message}`);
            continue;
        }
    }
    
    // If nothing works, return the original endpoint and let it fail naturally
    console.warn(`No working ${endpointType} endpoint found, using original`);
    if (endpointType === 'mcp_toolbox') return baseEndpoints.mcp_toolbox;
    if (endpointType === 'logo_service') return baseEndpoints.logo_service;
    return baseEndpoints.agent_interface;
}

async function getLogoServiceEndpoint() {
    // Use cached working endpoint or discover it
    if (!window.workingLogoEndpoint) {
        window.workingLogoEndpoint = await getWorkingEndpoint(SERVICE_ENDPOINTS, 'logo_service');
    }
    return window.workingLogoEndpoint;
}

async function testLogoServiceDiagnostics(endpoint) {
    console.log('🔍 Running logo service diagnostics...');
    
    // Test 1: Health endpoint
    try {
        const healthResponse = await fetch(`${endpoint}/health`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });
        console.log(`✅ Health check: ${healthResponse.status} ${healthResponse.statusText}`);
        if (healthResponse.ok) {
            const healthData = await healthResponse.json();
            console.log('Health data:', healthData);
        }
    } catch (error) {
        console.log(`❌ Health check failed: ${error.message}`);
    }
    
    // Test 2: List logos endpoint
    try {
        const logosResponse = await fetch(`${endpoint}/logos`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });
        console.log(`✅ List logos: ${logosResponse.status} ${logosResponse.statusText}`);
        if (logosResponse.ok) {
            const logosData = await logosResponse.json();
            console.log('Available logos:', logosData);
        }
    } catch (error) {
        console.log(`❌ List logos failed: ${error.message}`);
    }
    
    // Test 3: Direct port access (if port-forwarded)
    if (endpoint.includes('localhost:8080')) {
        try {
            const directResponse = await fetch('http://localhost:5004/health', {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });
            console.log(`✅ Direct port 5004 access: ${directResponse.status} ${directResponse.statusText}`);
        } catch (error) {
            console.log(`❌ Direct port 5004 access failed: ${error.message}`);
        }
    }
    
    // Test 4: Generate form endpoint with test data
    try {
        const testPayload = {
            name: "diagnostic-test",
            parameters: { test_param: "test_value" }
        };
        
        const formResponse = await fetch(`${endpoint}/generate-form-raw`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(testPayload)
        });
        console.log(`✅ Generate form test: ${formResponse.status} ${formResponse.statusText}`);
        if (!formResponse.ok) {
            const errorText = await formResponse.text();
            console.log('Generate form error:', errorText);
        }
    } catch (error) {
        console.log(`❌ Generate form test failed: ${error.message}`);
    }
    
    console.log('🔍 Logo service diagnostics complete');
}

async function getLogoUrl(name, isDefault = false) {
    try {
        const logoEndpoint = await getLogoServiceEndpoint();
        const logoName = isDefault ? 'default' : name;
        return `${logoEndpoint}/logo/${logoName}`;
    } catch (error) {
        console.warn(`Failed to get logo service endpoint: ${error.message}`);
        // Fallback to basic endpoint detection
        const endpoints = getServiceEndpoints();
        const logoName = isDefault ? 'default' : name;
        return `${endpoints.logo_service}/logo/${logoName}`;
    }
}

// Function to annotate dynamic parameters with metadata for form rendering
function annotateDynamicParameters(parameters) {
    function processValue(value, path = '') {
        if (typeof value === 'string' && value.startsWith('{{REPLACE_FROM_STEP_') && value.endsWith('}}')) {
            // Extract step number from placeholder
            const stepMatch = value.match(/{{REPLACE_FROM_STEP_(\d+)}}/);
            if (stepMatch) {
                const stepNum = parseInt(stepMatch[1]);
                return {
                    _isDynamicParameter: true,
                    _placeholder: value,
                    _stepNumber: stepNum,
                    _description: `This value will be replaced with data from step ${stepNum}`,
                    _defaultValue: `[Data from Step ${stepNum}]`,
                    _originalValue: value
                };
            }
        } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            // Recursively process object properties
            const processed = {};
            for (const [key, val] of Object.entries(value)) {
                processed[key] = processValue(val, path ? `${path}.${key}` : key);
            }
            return processed;
        } else if (Array.isArray(value)) {
            // Recursively process array items
            return value.map((item, index) => processValue(item, path ? `${path}[${index}]` : `[${index}]`));
        }
        return value;
    }
    
    return processValue(parameters);
}

// Helper function to find original parameter by name in processed parameters
function findOriginalParameter(processedParams, paramName) {
    function searchInObject(obj, name) {
        if (typeof obj !== 'object' || obj === null) return null;
        
        if (Array.isArray(obj)) {
            for (const item of obj) {
                const found = searchInObject(item, name);
                if (found) return found;
            }
        } else {
            // Check if this object has the parameter name as a key
            if (obj.hasOwnProperty(name)) {
                return obj[name];
            }
            
            // Check if this object is itself a dynamic parameter for the name
            if (obj._isDynamicParameter && obj._parameterName === name) {
                return obj;
            }
            
            // Recursively search in nested objects
            for (const value of Object.values(obj)) {
                const found = searchInObject(value, name);
                if (found) return found;
            }
        }
        return null;
    }
    
    return searchInObject(processedParams, paramName);
}

// Function to generate form from logo_service using raw JSON parameters
async function generateFormFromLogoService(toolName, parameters, container) {
    console.log('Generating form via logo_service for:', toolName, 'with raw parameters:', parameters);
    
    const logoEndpoint = await getLogoServiceEndpoint();
    console.log('Using logo endpoint:', logoEndpoint);
    
    // Check for dynamic parameters and annotate them
    const processedParameters = annotateDynamicParameters(parameters);
    
    // Prepare raw parameters for logo_service
    const rawParams = {
        name: toolName,
        parameters: processedParameters
    };
    
    const fullUrl = `${logoEndpoint}/generate-form-raw`;
    console.log('Full URL for form generation:', fullUrl);
    
    const response = await fetch(fullUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(rawParams)
    });
    
    console.log('Response status:', response.status, response.statusText);
    
    if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unable to read error response');
        console.error('Logo service error response:', errorText);
        throw new Error(`HTTP ${response.status}: ${response.statusText} - ${errorText}`);
    }
    
    const htmlContent = await response.text();
    
    // Extract form content from the HTML
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlContent, 'text/html');
    const form = doc.querySelector('form');
    
    if (!form) {
        throw new Error('Invalid response: no form element found');
    }
    
    // Remove any submit buttons and result divs from the form (since we integrate with popup workflow)
    const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
    submitButtons.forEach(btn => btn.remove());
    
    const resultDivs = doc.querySelectorAll('#result, .result');
    resultDivs.forEach(div => div.remove());
    
    // Remove any scripts (we don't need the form's own submission logic)
    const scripts = doc.querySelectorAll('script');
    scripts.forEach(script => script.remove());
    
    // Extract just the form fields content, not the entire form wrapper
    const formFields = form.innerHTML;
    
    // Clear container and add form fields
    container.innerHTML = `<div class="dynamic-form-fields">${formFields}</div>`;
    
    // Create interface compatible with existing code
    const formElements = {};
    const validators = {};
    
    // Collect all form inputs from the container
    const inputs = container.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        const paramName = input.name || input.id;
        if (paramName) {
            // Check if this parameter was a dynamic parameter from the processed parameters
            const originalParam = findOriginalParameter(processedParameters, paramName);
            if (originalParam && originalParam._isDynamicParameter) {
                // Store metadata about the dynamic parameter
                input.dataset.originalDynamicValue = originalParam._originalValue;
                input.dataset.defaultDisplayValue = originalParam._defaultValue;
                input.dataset.stepNumber = originalParam._stepNumber;
                input.dataset.isDynamicParameter = 'true';
                
                // Add visual indication that this is a dynamic parameter
                input.classList.add('dynamic-parameter-input');
                input.title = originalParam._description;
                
                // Set the display value
                if (input.type !== 'checkbox') {
                    input.value = originalParam._defaultValue;
                }
            }
            
            formElements[paramName] = input;
            validators[paramName] = () => ({ isValid: true, message: '' });
        }
    });
    
    return {
        elements: formElements,
        validators: validators,
        getData: () => {
            const data = {};
            Object.entries(formElements).forEach(([paramName, input]) => {
                let value;
                if (input.type === 'checkbox') {
                    value = input.checked;
                } else if (input.type === 'number') {
                    value = input.value === '' ? null : parseFloat(input.value);
                } else {
                    value = input.value;
                }
                
                // Check if this was a dynamic parameter and restore placeholder if unchanged
                if (input.dataset && input.dataset.originalDynamicValue) {
                    const originalPlaceholder = input.dataset.originalDynamicValue;
                    const defaultDisplayValue = input.dataset.defaultDisplayValue;
                    
                    // If the user didn't change the default display value, restore the placeholder
                    if (value === defaultDisplayValue || value === `[Data from Step ${input.dataset.stepNumber}]`) {
                        value = originalPlaceholder;
                    }
                }
                
                data[paramName] = value;
            });
            return data;
        },
        validate: () => {
            let allValid = true;
            Object.values(formElements).forEach(input => {
                if (input.required && !input.value.trim()) {
                    allValid = false;
                    input.classList.add('invalid');
                } else {
                    input.classList.remove('invalid');
                }
            });
            return allValid;
        }
    };
}

// JSON-RPC 2.0 Helper Function for Agent Interface with smart endpoint resolution
async function callAgentInterfaceRPC(method, params = {}) {
    // Use cached working endpoint or discover it
    if (!window.workingAgentEndpoint) {
        window.workingAgentEndpoint = await getWorkingEndpoint(SERVICE_ENDPOINTS, 'agent_interface');
    }
    
    const request = {
        jsonrpc: "2.0",
        method: method,
        params: params,
        id: Date.now()
    };
    
    try {
        const response = await fetch(window.workingAgentEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const jsonResponse = await response.json();
        
        if (jsonResponse.error) {
            throw new Error(`RPC Error ${jsonResponse.error.code}: ${jsonResponse.error.message}`);
        }
        
        return jsonResponse.result;
        
    } catch (error) {
        // If the cached endpoint fails, try to rediscover
        console.warn(`Cached endpoint failed: ${error.message}, attempting rediscovery`);
        window.workingAgentEndpoint = await getWorkingEndpoint(SERVICE_ENDPOINTS, 'agent_interface');
        
        // Retry once with new endpoint
        const retryResponse = await fetch(window.workingAgentEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        });
        
        if (!retryResponse.ok) {
            throw new Error(`HTTP ${retryResponse.status}: ${retryResponse.statusText}`);
        }
        
        const jsonResponse = await retryResponse.json();
        
        if (jsonResponse.error) {
            throw new Error(`RPC Error ${jsonResponse.error.code}: ${jsonResponse.error.message}`);
        }
        
        return jsonResponse.result;
    }
}

// Smart MCP Toolbox communication with dynamic endpoint resolution
async function callMCPToolbox(method, params = {}, sessionId = null) {
    // Use cached working endpoint or discover it
    if (!window.workingMCPEndpoint) {
        window.workingMCPEndpoint = await getWorkingEndpoint(SERVICE_ENDPOINTS, 'mcp_toolbox');
    }
    
    const headers = { 
        'Content-Type': 'application/json', 
        'Accept': 'application/json, text/event-stream',
        'MCP-Protocol-Version': '2025-06-18'
    };
    
    if (sessionId) {
        headers['Mcp-Session-Id'] = sessionId;
    }
    
    const request = {
        jsonrpc: "2.0",
        method: method,
        params: params,
        id: Date.now()
    };
    
    try {
        const response = await fetch(window.workingMCPEndpoint, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(request)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const jsonResponse = await response.json();
        
        if (jsonResponse.error) {
            throw new Error(`MCP Error ${jsonResponse.error.code}: ${jsonResponse.error.message}`);
        }
        
        // Return both result and session ID for MCP protocol
        return {
            result: jsonResponse.result,
            sessionId: response.headers.get('Mcp-Session-Id')
        };
        
    } catch (error) {
        // If the cached endpoint fails, try to rediscover
        console.warn(`Cached MCP endpoint failed: ${error.message}, attempting rediscovery`);
        window.workingMCPEndpoint = await getWorkingEndpoint(SERVICE_ENDPOINTS, 'mcp_toolbox');
        
        // Retry once with new endpoint
        const retryResponse = await fetch(window.workingMCPEndpoint, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(request)
        });
        
        if (!retryResponse.ok) {
            throw new Error(`HTTP ${retryResponse.status}: ${retryResponse.statusText}`);
        }
        
        const jsonResponse = await retryResponse.json();
        
        if (jsonResponse.error) {
            throw new Error(`MCP Error ${jsonResponse.error.code}: ${jsonResponse.error.message}`);
        }
        
        return {
            result: jsonResponse.result,
            sessionId: retryResponse.headers.get('Mcp-Session-Id')
        };
    }
}

// Function to get all available skills from agent interface
async function getAvailableSkills() {
    try {
        const skillsData = await callAgentInterfaceRPC('agent.skills');
        return skillsData.available_skills || {};
    } catch (error) {
        console.error('Error fetching skills from agent interface:', error);
        return {};
    }
}

// Function to execute a skill via agent interface
async function executeSkill(skillId, content, data = null, agentId = null) {
    try {
        const params = {
            skill_id: skillId,
            content: content,
            context_id: `agentic-assistant-${Date.now()}`
        };
        
        if (data) {
            params.data = data;
        }
        
        if (agentId) {
            params.agent_id = agentId;
        }
        
        const result = await callAgentInterfaceRPC('skill.execute', params);
        return result;
    } catch (error) {
        console.error('Error executing skill via agent interface:', error);
        throw error;
    }
}

const MODE_STATUS_CLASS = 'mode-status-indicator';

document.addEventListener('DOMContentLoaded', () => {
    // Assign all DOM elements to variables
    chatConsole = document.getElementById('chat-console');
    messageInput = document.getElementById('message-input');
    sendButton = document.getElementById('send-button');
    chatMainContent = document.getElementById('chat-main-content');
    pageLogo = document.getElementById('left-page-logo');
    sidebar = document.getElementById('left-sidebar');
    sidebarToggleIcon = document.getElementById('sidebar-toggle-icon');
    settingsModal = document.getElementById('settings-modal');
    settingsToolButton = document.getElementById('settings-tool-button');
    if (settingsModal) {
        modalCloseButton = settingsModal.querySelector('.modal-close-button');
    }
    modalThinkingToggleCheckbox = document.getElementById('thinking-toggle-checkbox');
    queryModeButton = document.getElementById('query-mode-button');
    researchModeButton = document.getElementById('research-mode-button');
    researchPlanModal = document.getElementById('research-plan-modal');
    if (researchPlanModal) {
        researchModalCloseButton = researchPlanModal.querySelector('#research-modal-close-button');
    }
    researchPlanEditor = document.getElementById('research-plan-editor');
    researchTaskDescriptionEl = document.getElementById('research-task-description');
    addPlanStepButton = document.getElementById('add-plan-step-button');
    cancelResearchPlanButton = document.getElementById('cancel-research-plan-button');
    submitResearchPlanButton = document.getElementById('submit-research-plan-button');
    uploadButton = document.getElementById('upload-button');
    fileUploadInput = document.getElementById('file-upload-input');
    fileStagingArea = document.getElementById('file-staging-area');
    stagedFileNameEl = document.getElementById('staged-file-name');
    removeStagedFileBtn = document.getElementById('remove-staged-file-button');
    toolListButton = document.getElementById('tool-list-button');
    toolListModal = document.getElementById('tool-list-modal');
    resourceListContainer = document.getElementById('resource-list-container');
    newConversationButton = document.getElementById('new-conversation-button');
    conversationHistoryList = document.getElementById('conversation-history-list');

    // Set up the initial state and all event listeners
    initializePreChatState();
    setupEventListeners();
    loadConversationHistory();
    
    // Initialize logo service endpoint early for better popup performance
    getLogoServiceEndpoint().then((endpoint) => {
        console.log('Logo service endpoint initialized successfully:', endpoint);
        // Test diagnostic endpoints
        testLogoServiceDiagnostics(endpoint);
    }).catch(error => {
        console.warn('Failed to initialize logo service endpoint:', error);
    });
});

function setupEventListeners() {
    if (sidebarToggleIcon && sidebar) {
        sidebarToggleIcon.addEventListener('click', (e) => {
            e.stopPropagation();
            
            // Synchronize sidebar and body transitions
            const isOpening = !sidebar.classList.contains('open');
            
            if (isOpening) {
                // Opening: sidebar first, then body padding
                sidebar.classList.remove('hidden-state');
                sidebar.classList.add('open');
                // Sync body padding transition with sidebar
                requestAnimationFrame(() => {
                    document.body.classList.add('sidebar-open');
                });
            } else {
                // Closing: both simultaneously for faster feel
                sidebar.classList.remove('open');
                document.body.classList.remove('sidebar-open');
            }
        });
    }

    if (settingsToolButton && settingsModal) {
        settingsToolButton.addEventListener('click', (e) => {
            e.stopPropagation();
            settingsModal.classList.remove('hidden');
            settingsModal.classList.add('visible');
        });
    }

    if (modalCloseButton && settingsModal) {
        modalCloseButton.addEventListener('click', () => {
            settingsModal.classList.add('hidden');
            settingsModal.classList.remove('visible');
        });
    }

    if (toolListButton && toolListModal) {
        toolListButton.addEventListener('click', (e) => {
            e.stopPropagation();
            fetchAndShowResources();
        });
        const closeButton = toolListModal.querySelector('.modal-close-button');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                toolListModal.classList.add('hidden');
                toolListModal.classList.remove('visible');
            });
        }
    }

    if (resourceListContainer) {
        resourceListContainer.addEventListener('change', (event) => {
            if (event.target.type === 'checkbox') {
                const resourceName = event.target.value;
                const resourceType = event.target.name;
                if (event.target.checked) {
                    if (resourceType === 'tool') userToolSelections.add(resourceName);
                    else if (resourceType === 'agent') userAgentSelections.add(resourceName);
                } else {
                    if (resourceType === 'tool') userToolSelections.delete(resourceName);
                    else if (resourceType === 'agent') userAgentSelections.delete(resourceName);
                }
            }
        });
    }

    window.addEventListener('click', (event) => {
        if (isChatSessionStarted && chatMainContent && !chatMainContent.contains(event.target)) {
            // Check if any modal is currently visible - don't shrink if so
            const isAnyModalVisible = (settingsModal && !settingsModal.classList.contains('hidden')) ||
                                    (toolListModal && !toolListModal.classList.contains('hidden')) ||
                                    (researchPlanModal && !researchPlanModal.classList.contains('hidden'));
            
            if (isAnyModalVisible) {
                return; // Don't shrink chat when modal is open
            }
            
            if (!sidebar.contains(event.target) && !settingsModal.contains(event.target) && !toolListModal.contains(event.target) && !researchPlanModal.contains(event.target)) {
                shrinkChatWindow();
            }
        }

        if (settingsModal && event.target === settingsModal) {
            settingsModal.classList.add('hidden');
            settingsModal.classList.remove('visible');
        }
        if (researchPlanModal && event.target === researchPlanModal) {
            researchPlanModal.classList.add('hidden');
            researchPlanModal.classList.remove('visible');
            if (sendButton) sendButton.disabled = false;
            // Focus without triggering session expansion if chat is already started
            if (messageInput && isChatSessionStarted && chatMainContent && !chatMainContent.classList.contains('pre-chat')) {
                messageInput.focus();
            }
        }
        if (toolListModal && event.target === toolListModal) {
            toolListModal.classList.add('hidden');
            toolListModal.classList.remove('visible');
        }
    });

    if (modalThinkingToggleCheckbox) {
        modalThinkingToggleCheckbox.addEventListener('change', function() {
            showThinking = this.checked;
            updateExistingThinkingMessagesVisibility();
        });
    }

    if (queryModeButton && researchModeButton && messageInput && chatMainContent) {
        queryModeButton.addEventListener('click', (e) => {
            e.stopPropagation();
            if (currentMode !== 'query') {
                currentMode = 'query';
                updateModeUI();
            }
        });

        researchModeButton.addEventListener('click', (e) => {
            e.stopPropagation();
            if (currentMode !== 'research') {
                currentMode = 'research';
                updateModeUI();
            }
        });
    }

    if (researchModalCloseButton && researchPlanModal && sendButton && messageInput) {
        researchModalCloseButton.addEventListener('click', () => {
            researchPlanModal.classList.add('hidden');
            researchPlanModal.classList.remove('visible');
            sendButton.disabled = false;
            // Focus without triggering session expansion if chat is already started
            if (isChatSessionStarted && chatMainContent && !chatMainContent.classList.contains('pre-chat')) {
                messageInput.focus();
            }
        });
    }

    if (addPlanStepButton && researchPlanEditor) {
        addPlanStepButton.addEventListener('click', () => {
            const newIndex = researchPlanEditor.children.length;
            researchPlanEditor.appendChild(createPlanStepInput(`New Step ${newIndex + 1}`, newIndex));
            researchPlanEditor.scrollTop = researchPlanEditor.scrollHeight;
        });
    }

    if (cancelResearchPlanButton) {
        cancelResearchPlanButton.addEventListener('click', handleCancelResearchPlan);
    }
    if (submitResearchPlanButton) {
        submitResearchPlanButton.addEventListener('click', handleSubmitResearchPlan);
    }

    if (uploadButton) {
        uploadButton.addEventListener('click', (e) => {
            e.stopPropagation();
            if (fileUploadInput) {
                fileUploadInput.click();
            }
        });
    }

    if (fileUploadInput) {
        fileUploadInput.addEventListener('change', handleFileUpload);
    }

    if (removeStagedFileBtn) {
        removeStagedFileBtn.addEventListener('click', clearStagedFile);
    }

    if (sendButton) {
        sendButton.addEventListener('click', (e) => {
            e.stopPropagation();
            handleSend();
        });
    }
    if (messageInput && chatMainContent && sendButton) {
        messageInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter' && !event.shiftKey && !sendButton.disabled) {
                event.preventDefault();
                handleSend();
            }
        });
        messageInput.addEventListener('click', e => e.stopPropagation());
        
        // Auto-collapse sidebar when user starts typing
        messageInput.addEventListener('focus', function() {
            // Don't collapse sidebar if research modal is open
            if (researchPlanModal && !researchPlanModal.classList.contains('hidden')) {
                return;
            }
            if (sidebar && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                document.body.classList.remove('sidebar-open');
            }
        });
        
        // Also collapse on first keypress for better UX
        messageInput.addEventListener('input', function() {
            // Don't collapse sidebar if research modal is open
            if (researchPlanModal && !researchPlanModal.classList.contains('hidden')) {
                return;
            }
            if (sidebar && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                document.body.classList.remove('sidebar-open');
            }
        });
    }

    // New Conversation button event listener
    if (newConversationButton) {
        newConversationButton.addEventListener('click', handleNewConversation);
    }
}

function initializePreChatState() {
    if (chatMainContent) {
        chatMainContent.classList.add('pre-chat');
        chatMainContent.classList.remove('session-started');
        if (messageInput) {
            messageInput.placeholder = "How can we help you?";
            messageInput.removeEventListener('focus', startChatSession);
            messageInput.addEventListener('focus', startChatSession, { once: true });
        }
    }
    if (sidebar) sidebar.classList.remove('open');
    // Reset chat window position by removing sidebar-open class from body
    document.body.classList.remove('sidebar-open');
    if (pageLogo) pageLogo.style.opacity = '1';
    if (chatConsole) chatConsole.innerHTML = '';
    
    // Show doodle in pre-chat state
    document.body.classList.add('pre-chat-active');
    
    isChatSessionStarted = false;
    clearStagedFile();
    updateModeUI();
}

function shrinkChatWindow() {
    // Force layout calculation before transition to prevent jumping
    if (chatMainContent) {
        chatMainContent.offsetHeight; // Force reflow
    }
    
    // Coordinate all transitions to happen together in single frame
    requestAnimationFrame(() => {
        // Batch all DOM changes together to prevent layout thrashing
        const batch = () => {
            if (chatMainContent) {
                chatMainContent.classList.add('pre-chat');
                chatMainContent.classList.remove('session-started');
                if (messageInput) {
                    messageInput.placeholder = "How can we help you?";
                    messageInput.removeEventListener('focus', expandChatWindow);
                    messageInput.addEventListener('focus', expandChatWindow, { once: true });
                }
            }
            if (sidebar) {
                sidebar.classList.remove('open');
                document.body.classList.remove('sidebar-open');
            }
            if (pageLogo) {
                pageLogo.style.opacity = '1';
            }
        };
        
        batch();
    });
}

function expandChatWindow() {
    // Don't expand chat window if research modal is open
    if (researchPlanModal && !researchPlanModal.classList.contains('hidden')) {
        return;
    }
    
    // Force layout calculation before transition to prevent jumping
    if (chatMainContent) {
        chatMainContent.offsetHeight; // Force reflow
    }
    
    // Coordinate all transitions to happen together for snappy feel
    requestAnimationFrame(() => {
        // Batch all DOM changes together
        const batch = () => {
            if (chatMainContent) {
                chatMainContent.classList.remove('pre-chat');
                chatMainContent.classList.add('session-started');
                if (messageInput) {
                    messageInput.placeholder = currentMode === 'query' ? "Type your query..." : "Type your assistant query...";
                }
            }
            if (pageLogo) {
                pageLogo.style.opacity = '0';
            }
        };
        
        batch();
    });
    
    // Reduced timeout to match faster CSS transition
    setTimeout(() => { if(messageInput) messageInput.focus(); }, 80);
}

function startChatSession(event) {
    if(event) event.stopPropagation();
    
    // Don't expand chat window if research modal is open
    if (researchPlanModal && !researchPlanModal.classList.contains('hidden')) {
        return;
    }
    
    if (isChatSessionStarted) {
        expandChatWindow();
        return;
    }
    isChatSessionStarted = true;

    if (!chatMainContent || !messageInput || !chatConsole) return;

    expandChatWindow();

    // Hide doodle when chat session starts
    document.body.classList.remove('pre-chat-active');

    if (!stagedFileContent) {
        messageInput.placeholder = currentMode === 'query' ? "Type your query..." : "Type your assistant query...";
    }

    const messagesToClear = chatConsole.querySelectorAll(`.${MODE_STATUS_CLASS}, .system-message-generic, .initial-ai-greeting-container`);
    messagesToClear.forEach(msg => msg.remove());

    const initialTurnContainer = createTurnContainer();
    if (initialTurnContainer) {
        initialTurnContainer.classList.add('initial-ai-greeting-container');
        const initialAiMessage = createMessageElement("Hello! How can I help you today?", 'ai-message');
        initialTurnContainer.appendChild(initialAiMessage);
        chatConsole.appendChild(initialTurnContainer);
    }

    if (chatConsole) chatConsole.scrollTop = chatConsole.scrollHeight;

    setTimeout(() => { if(messageInput) messageInput.focus(); }, 50);
}

function finalizeThinkingButton(answerTabContentCtx, thinkingToggleBtnCtx) {
    if (!answerTabContentCtx || !thinkingToggleBtnCtx) return;

    // FIX: Directly target the spinner icon within the button
    const spinner = thinkingToggleBtnCtx.querySelector('.spinner-icon');
    if (spinner) {
        spinner.style.display = 'none';
    }

    const buttonTextEl = thinkingToggleBtnCtx.querySelector('.button-text');
    if (buttonTextEl) {
        // Check both tabs for thinking messages - they should be in Steps tab after final response
        const turnContainer = answerTabContentCtx.closest('.turn-container');
        const stepsTabContent = turnContainer ? turnContainer.querySelector('.tab-content[data-tab="steps"]') : null;
        
        // First check Steps tab (after final response), then Answer tab (fallback)
        let thinkingMessagesInGroup = [];
        if (stepsTabContent) {
            thinkingMessagesInGroup = stepsTabContent.querySelectorAll('.ai-thinking-message');
        }
        if (thinkingMessagesInGroup.length === 0) {
            thinkingMessagesInGroup = answerTabContentCtx.querySelectorAll('.ai-thinking-message');
        }
        
        if (thinkingMessagesInGroup.length > 0) {
            let anythingVisibleInGroup = Array.from(thinkingMessagesInGroup).some(msg => !msg.classList.contains('hidden-thought'));
            buttonTextEl.textContent = anythingVisibleInGroup ? 'Hide Related Thinking' : 'Show Related Thinking';
            thinkingToggleBtnCtx.disabled = false;
        } else {
            buttonTextEl.textContent = 'Show Related Thinking';
            thinkingToggleBtnCtx.disabled = true;
        }
    }
}

function displayModeStatusMessage(text) {
    if (!chatConsole) return;
    const existingMessages = chatConsole.querySelectorAll('.' + MODE_STATUS_CLASS);
    existingMessages.forEach(msg => msg.remove());
    const messageDiv = createMessageElement(text, 'system-message', MODE_STATUS_CLASS);
    const firstTurnOrGreeting = chatConsole.querySelector('.turn-container, .initial-ai-greeting-container');
    if (firstTurnOrGreeting) chatConsole.insertBefore(messageDiv, firstTurnOrGreeting);
    else chatConsole.appendChild(messageDiv);
    if (chatConsole) chatConsole.scrollTop = chatConsole.scrollHeight;
}

function updateModeUI() {
    if (!queryModeButton || !researchModeButton || !messageInput) return;
    if (stagedFileContent) return;
    if (currentMode === 'query') {
        queryModeButton.classList.add('active-mode');
        researchModeButton.classList.remove('active-mode');
        if (!chatMainContent || !chatMainContent.classList.contains('pre-chat')) {
             messageInput.placeholder = "Type your query...";
        }
    } else {
        researchModeButton.classList.add('active-mode');
        queryModeButton.classList.remove('active-mode');
         if (!chatMainContent || !chatMainContent.classList.contains('pre-chat')) {
            messageInput.placeholder = "Type your research query...";
        }
    }
}
async function fetchAndShowResources() {
    if (!resourceListContainer || !toolListModal) return;
    resourceListContainer.innerHTML = '<p>Loading tools and agents...</p>';
    toolListModal.classList.remove('hidden');
    toolListModal.classList.add('visible');

    // Initialize variables for tools and agents
    let tools = [];
    let agentCards = {};
    let toolsError = null;
    let agentsError = null;

    // Fetch tools from mcp_toolbox service using dynamic endpoint resolution
    try {
        // First, initialize MCP session
        const initResult = await callMCPToolbox("initialize", {
            protocolVersion: "2025-06-18",
            capabilities: {},
            clientInfo: {
                name: "agentic-assistant-frontend",
                version: "1.0.0"
            }
        });
        
        let sessionId = initResult.sessionId;
        
        // Send initialization notification as per MCP spec
        if (sessionId) {
            await callMCPToolbox("notifications/initialized", {}, sessionId);
        }

        // Then fetch tools list
        const toolsResult = await callMCPToolbox("tools/list", {}, sessionId);
        tools = toolsResult.result?.tools || [];
    } catch (error) {
        console.error('Error fetching tools:', error);
        toolsError = `Tool service unavailable: ${error.message}`;
    }

    // Fetch agents from agent_interface service using JSON-RPC
    try {
        const agentCardsData = await callAgentInterfaceRPC('agent.list', { format: 'cards' });
        agentCards = agentCardsData.agent_cards || {};
        console.log('Successfully fetched agents via JSON-RPC:', Object.keys(agentCards));
    } catch (error) {
        console.error('Error fetching agents via JSON-RPC:', error);
        agentsError = `Agent Interface service unavailable: ${error.message}`;
    }

    // Also fetch available skills for enhanced UI
    let availableSkills = {};
    try {
        availableSkills = await getAvailableSkills();
        console.log('Successfully fetched skills via JSON-RPC:', Object.keys(availableSkills));
    } catch (error) {
        console.warn('Could not fetch skills, continuing with agent cards only:', error);
    }

    // Clear and populate available resources
    availableTools.clear();
    availableAgents.clear();

    // Process tools if available
    if (tools.length > 0) {
        tools.forEach(tool => availableTools.set(tool.name, tool));
    }

    // Process agent cards if available
    if (Object.keys(agentCards).length > 0) {
        Object.entries(agentCards).forEach(([agentId, agentCard]) => {
            // Store the agent with its original card data intact
            availableAgents.set(agentId, { 
                id: agentId, 
                name: agentCard.name,
                description: agentCard.description,
                version: agentCard.version,
                url: agentCard.service_endpoint,
                agentCard: agentCard, // Store the complete original agent card
                capabilities: agentCard.skills // Use original skills without modification
            });
        });
    }

    // Render the resources with error information if needed
    renderResourceList(tools, availableAgents, toolsError, agentsError);
}

// Removed convertSchemaToInputSchema function - now handling schema transformation inline



function renderResourceList(tools, agents, toolsError = null, agentsError = null) {
    if (!resourceListContainer) return;
    resourceListContainer.innerHTML = '';

    const toolsSection = document.createElement('div');
    toolsSection.innerHTML = '<h4>Tools</h4>';
    
    if (toolsError) {
        toolsSection.innerHTML += `<p style="color: orange; font-size: 0.9em; margin: 0.5rem 0;">⚠️ ${toolsError}</p>`;
    }
    
    if (tools.length > 0) {
        // Create grid container for tools
        const toolsGrid = document.createElement('div');
        toolsGrid.style.display = 'grid';
        toolsGrid.style.gridTemplateColumns = 'repeat(4, 1fr)';
        toolsGrid.style.gap = '12px';
        toolsGrid.style.marginTop = '10px';
        
        tools.forEach(tool => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'resource-item';
            itemDiv.style.display = 'flex';
            itemDiv.style.flexDirection = 'column';
            itemDiv.style.alignItems = 'center';
            itemDiv.style.justifyContent = 'center';
            itemDiv.style.padding = '8px';
            itemDiv.style.border = 'none';
            itemDiv.style.borderRadius = '6px';
            itemDiv.style.cursor = 'pointer';
            itemDiv.style.transition = 'all 0.2s ease';
            itemDiv.style.backgroundColor = 'white';
            itemDiv.style.minHeight = '100px';
            itemDiv.dataset.toolName = tool.name;
            itemDiv.dataset.resourceType = 'tool';
            
            // Apply selected state if tool is selected
            if (userToolSelections.has(tool.name)) {
                itemDiv.style.border = 'none';
                itemDiv.style.backgroundColor = '#e3f2fd';
                itemDiv.style.boxShadow = '0 4px 12px rgba(0, 123, 255, 0.3)';
            }
            
            // Add hover effects
            itemDiv.addEventListener('mouseenter', function() {
                if (!userToolSelections.has(tool.name)) {
                    this.style.backgroundColor = '#e9ecef';
                    this.style.transform = 'translateY(-2px)';
                    this.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.1)';
                }
            });
            
            itemDiv.addEventListener('mouseleave', function() {
                if (!userToolSelections.has(tool.name)) {
                    this.style.backgroundColor = 'white';
                    this.style.transform = 'translateY(0)';
                    this.style.boxShadow = 'none';
                }
            });
            
            // Add click handler for selection
            itemDiv.addEventListener('click', function() {
                const toolName = this.dataset.toolName;
                if (userToolSelections.has(toolName)) {
                    userToolSelections.delete(toolName);
                    this.style.border = 'none';
                    this.style.backgroundColor = 'white';
                    this.style.boxShadow = 'none';
                } else {
                    userToolSelections.add(toolName);
                    this.style.border = 'none';
                    this.style.backgroundColor = '#e3f2fd';
                    this.style.boxShadow = '0 4px 12px rgba(0, 123, 255, 0.3)';
                }
            });
            
            // Create logo image
            const logoImg = document.createElement('img');
            logoImg.alt = `${tool.name} logo`;
            logoImg.style.width = '48px';
            logoImg.style.height = '48px';
            logoImg.style.objectFit = 'contain';
            logoImg.style.borderRadius = '6px';
            logoImg.style.maxWidth = '48px';
            logoImg.style.maxHeight = '48px';
            logoImg.style.minWidth = '48px';
            logoImg.style.minHeight = '48px';
            logoImg.style.marginBottom = '4px';
            logoImg.title = `${tool.name}: ${tool.description || 'No description'}`;
            
            // Set logo URL with smart endpoint resolution and retry logic
            getLogoUrl(tool.name).then(logoUrl => {
                logoImg.src = logoUrl;
            }).catch(error => {
                console.warn(`Failed to get logo URL for ${tool.name}:`, error);
                // Final fallback to basic endpoint
                const endpoints = getServiceEndpoints();
                logoImg.src = `${endpoints.logo_service}/logo/${tool.name}`;
            });
            
            // Fallback to default logo on image load error with retry logic
            logoImg.onerror = async function() {
                if (!this.dataset.retryAttempted) {
                    this.dataset.retryAttempted = 'true';
                    try {
                        // Try to get default logo with smart endpoint resolution
                        const defaultLogoUrl = await getLogoUrl('default', true);
                        this.src = defaultLogoUrl;
                    } catch (error) {
                        console.warn(`Failed to get default logo URL:`, error);
                        // Final fallback
                        const endpoints = getServiceEndpoints();
                        this.src = `${endpoints.logo_service}/logo/default`;
                    }
                }
            };
            
            // Add click handler to logo to trigger parent selection
            logoImg.addEventListener('click', function(e) {
                e.stopPropagation();
                itemDiv.click();
            });
            
            // Create name label
            const nameLabel = document.createElement('div');
            nameLabel.textContent = tool.name;
            nameLabel.style.fontSize = '11px';
            nameLabel.style.fontWeight = '500';
            nameLabel.style.textAlign = 'center';
            nameLabel.style.color = '#333';
            nameLabel.style.lineHeight = '1.2';
            nameLabel.style.maxWidth = '100%';
            nameLabel.style.overflow = 'hidden';
            nameLabel.style.textOverflow = 'ellipsis';
            nameLabel.style.whiteSpace = 'nowrap';
            
            itemDiv.appendChild(logoImg);
            itemDiv.appendChild(nameLabel);
            toolsGrid.appendChild(itemDiv);
        });
        
        toolsSection.appendChild(toolsGrid);
    } else if (!toolsError) {
        toolsSection.innerHTML += '<p>No tools available.</p>';
    }
    resourceListContainer.appendChild(toolsSection);

    // Add agents section with error handling
    const agentsSection = document.createElement('div');
    agentsSection.innerHTML = '<hr style="margin: 1rem 0;"><h4>Agents</h4>';
    
    if (agentsError) {
        agentsSection.innerHTML += `<p style="color: orange; font-size: 0.9em; margin: 0.5rem 0;">⚠️ ${agentsError}</p>`;
    }
    
    if (agents.size > 0) {
        // Create grid container for agents
        const agentsGrid = document.createElement('div');
        agentsGrid.style.display = 'grid';
        agentsGrid.style.gridTemplateColumns = 'repeat(4, 1fr)';
        agentsGrid.style.gap = '12px';
        agentsGrid.style.marginTop = '10px';
        
        agents.forEach(agent => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'resource-item';
            itemDiv.style.display = 'flex';
            itemDiv.style.flexDirection = 'column';
            itemDiv.style.alignItems = 'center';
            itemDiv.style.justifyContent = 'center';
            itemDiv.style.padding = '8px';
            itemDiv.style.border = 'none';
            itemDiv.style.borderRadius = '6px';
            itemDiv.style.cursor = 'pointer';
            itemDiv.style.transition = 'all 0.2s ease';
            itemDiv.style.backgroundColor = 'white';
            itemDiv.style.minHeight = '100px';
            itemDiv.dataset.agentId = agent.id;
            itemDiv.dataset.resourceType = 'agent';
            
            // Apply selected state if agent is selected
            if (userAgentSelections.has(agent.id)) {
                itemDiv.style.border = 'none';
                itemDiv.style.backgroundColor = '#e8f5e8';
                itemDiv.style.boxShadow = '0 4px 12px rgba(40, 167, 69, 0.3)';
            }
            
            // Add hover effects
            itemDiv.addEventListener('mouseenter', function() {
                if (!userAgentSelections.has(agent.id)) {
                    this.style.backgroundColor = '#e9ecef';
                    this.style.transform = 'translateY(-2px)';
                    this.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.1)';
                }
            });
            
            itemDiv.addEventListener('mouseleave', function() {
                if (!userAgentSelections.has(agent.id)) {
                    this.style.backgroundColor = 'white';
                    this.style.transform = 'translateY(0)';
                    this.style.boxShadow = 'none';
                }
            });
            
            // Add click handler for selection
            itemDiv.addEventListener('click', function() {
                const agentId = this.dataset.agentId;
                if (userAgentSelections.has(agentId)) {
                    userAgentSelections.delete(agentId);
                    this.style.border = 'none';
                    this.style.backgroundColor = 'white';
                    this.style.boxShadow = 'none';
                } else {
                    userAgentSelections.add(agentId);
                    this.style.border = 'none';
                    this.style.backgroundColor = '#e8f5e8';
                    this.style.boxShadow = '0 4px 12px rgba(40, 167, 69, 0.3)';
                }
            });
            
            // Create logo image for agent
            const logoImg = document.createElement('img');
            logoImg.alt = `${agent.name || agent.id} logo`;
            logoImg.style.width = '48px';
            logoImg.style.height = '48px';
            logoImg.style.objectFit = 'contain';
            logoImg.style.borderRadius = '6px';
            logoImg.style.maxWidth = '48px';
            logoImg.style.maxHeight = '48px';
            logoImg.style.minWidth = '48px';
            logoImg.style.minHeight = '48px';
            logoImg.style.marginBottom = '4px';
            const skillsCount = agent.capabilities?.length || 0;
            const skillsList = agent.capabilities?.map(cap => cap.name).join(', ') || 'No skills';
            logoImg.title = `${agent.name || agent.id}: ${agent.description || 'No description'} | Skills: ${skillsList} | Version: ${agent.version || 'Unknown'}`;
            
            // Set logo URL with smart endpoint resolution and retry logic
            getLogoUrl(agent.id).then(logoUrl => {
                logoImg.src = logoUrl;
            }).catch(error => {
                console.warn(`Failed to get logo URL for ${agent.id}:`, error);
                // Final fallback to basic endpoint
                const endpoints = getServiceEndpoints();
                logoImg.src = `${endpoints.logo_service}/logo/${agent.id}`;
            });
            
            // Fallback to default logo on image load error with retry logic
            logoImg.onerror = async function() {
                if (!this.dataset.retryAttempted) {
                    this.dataset.retryAttempted = 'true';
                    try {
                        // Try to get default logo with smart endpoint resolution
                        const defaultLogoUrl = await getLogoUrl('default', true);
                        this.src = defaultLogoUrl;
                    } catch (error) {
                        console.warn(`Failed to get default logo URL:`, error);
                        // Final fallback
                        const endpoints = getServiceEndpoints();
                        this.src = `${endpoints.logo_service}/logo/default`;
                    }
                }
            };
            
            // Add click handler to logo to trigger parent selection
            logoImg.addEventListener('click', function(e) {
                e.stopPropagation();
                itemDiv.click();
            });
            
            // Create name label for agent
            const nameLabel = document.createElement('div');
            nameLabel.textContent = agent.name || agent.id;
            nameLabel.style.fontSize = '11px';
            nameLabel.style.fontWeight = '500';
            nameLabel.style.textAlign = 'center';
            nameLabel.style.color = '#333';
            nameLabel.style.lineHeight = '1.2';
            nameLabel.style.maxWidth = '100%';
            nameLabel.style.overflow = 'hidden';
            nameLabel.style.textOverflow = 'ellipsis';
            nameLabel.style.whiteSpace = 'nowrap';
            
            itemDiv.appendChild(logoImg);
            itemDiv.appendChild(nameLabel);
            agentsGrid.appendChild(itemDiv);
        });
        
        agentsSection.appendChild(agentsGrid);
    } else if (!agentsError) {
        agentsSection.innerHTML += '<p>No agents available.</p>';
    }
    
    resourceListContainer.appendChild(agentsSection);

    // Add summary message if both services have errors
    if (toolsError && agentsError) {
        const errorSummary = document.createElement('div');
        errorSummary.innerHTML = '<hr style="margin: 1rem 0;"><p style="color: #d9534f; font-weight: 500;">Both tool and agent services are currently unavailable. Please ensure the services are running and try again.</p>';
        resourceListContainer.appendChild(errorSummary);
    } else if (tools.length > 0 || agents.size > 0) {
        const successMessage = document.createElement('div');
        successMessage.innerHTML = '<hr style="margin: 1rem 0;"><p style="color: #5cb85c; font-size: 0.9em;">✓ Select the tools and agents you want to use for your query.</p>';
        resourceListContainer.appendChild(successMessage);
    }
}

async function handleSend() {
    if (!messageInput || !chatConsole || !sendButton) return;
    const userQuery = messageInput.value.trim();
    if (!userQuery && !stagedFileContent) return;

    if (!isChatSessionStarted) {
        startChatSession();
    }

    const existingModeMessages = chatConsole.querySelectorAll('.' + MODE_STATUS_CLASS);
    existingModeMessages.forEach(msg => msg.remove());
    const initialGreeting = chatConsole.querySelector('.initial-ai-greeting-container');
    if(initialGreeting) initialGreeting.remove();

    currentTurnExchangeContainer = createTurnContainer();

    let processingText = '';
    if (stagedFileContent) {
        processingText += `--- Document Content ---\n${stagedFileContent}\n--- End Document ---`;
    }

    const selectedTools = Array.from(userToolSelections)
        .map(toolName => availableTools.get(toolName)).filter(Boolean);
    
    // DEBUG: Log tool selection
    console.log('DEBUG: userToolSelections:', Array.from(userToolSelections));
    console.log('DEBUG: availableTools:', availableTools);
    console.log('DEBUG: selectedTools:', selectedTools);

    const selectedAgents = [];
    for (const agentId of userAgentSelections) {
        const agentData = availableAgents.get(agentId);
        if (agentData && agentData.capabilities) {
            // Pass complete skill objects without corruption
            agentData.capabilities.forEach(skill => {
                // Determine if this is a chart tool based on skill tags
                const skillTags = skill.metadata?.tags || [];
                const isChartTool = skillTags.some(tag => 
                    ['visualization', 'data_analysis'].includes(tag)
                );
                
                selectedAgents.push({
                    // Use skill name for LLM display/matching (not skill_id)
                    name: skill.name,
                    // Include human-readable description combining name and description  
                    description: `${skill.name}: ${skill.description}`,
                    // Pass through all skill fields as-is without duplication
                    ...skill,
                    // Add routing information
                    is_a2a_tool: true,
                    is_chart_tool: isChartTool,  // Add chart tool detection
                    agent_id: agentId
                });
            });
        }
    }
    
    // DEBUG: Log agent selection
    console.log('DEBUG: userAgentSelections:', Array.from(userAgentSelections));
    console.log('DEBUG: availableAgents:', availableAgents);
    console.log('DEBUG: selectedAgents:', selectedAgents);

    if (selectedTools.length > 0) {
        processingText += `\n\n--- Selected Tools ---\n${JSON.stringify(selectedTools)}`;
        console.log('DEBUG: Added Selected Tools section to processingText');
    }
    if (selectedAgents.length > 0) {
        processingText += `\n\n--- Selected Agents ---\n${JSON.stringify(selectedAgents)}`;
        console.log('DEBUG: Added Selected Agents section to processingText');
    }

    if (userQuery) {
        if (processingText) {
            processingText += `\n\n--- User Query ---\n${userQuery}`;
        } else {
            processingText = userQuery;
        }
    }

    // Display only the user query in the chat interface
    // The processingText (with file and tool metadata) is sent to the backend
    // but displayText (clean user query) is shown in the UI
    const displayText = userQuery;

    const userMessageDiv = createMessageElement(displayText, 'user-message');
    currentTurnExchangeContainer.appendChild(userMessageDiv);
    chatConsole.appendChild(currentTurnExchangeContainer);

    clearStagedFile();

    conversationHistory.push({ role: 'user', content: processingText });
    if (!currentSessionId) {
        currentSessionId = `client-${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 7)}`;
    }

    messageInput.value = '';
    sendButton.disabled = true;
    currentAiMessageElement = null;
    streamedHtmlContent = '';

    const isResearchTurn = (currentMode === 'research');
    const aiResponseElements = createAIResponseArea(currentTurnExchangeContainer, isResearchTurn);
    currentTurnExchangeContainer.appendChild(aiResponseElements.tabNav);
    currentTurnExchangeContainer.appendChild(aiResponseElements.messageContentArea);

    if (chatConsole) chatConsole.scrollTop = chatConsole.scrollHeight;

    const answerTabContent = currentTurnExchangeContainer.querySelector('.ai-response-area .tab-content[data-tab="answer"]');
    const thinkingToggleBtn = answerTabContent ? answerTabContent.querySelector('.related-thinking-toggle') : null;

    if (currentMode === 'query') {
        await handleQueryModeSend(processingText, answerTabContent, thinkingToggleBtn);
    } else {
        currentResearchQuery = processingText;
        await handleResearchModeSend(processingText, answerTabContent, thinkingToggleBtn);
    }
}

async function handleQueryModeSend(messageText, answerTabContentRef, thinkingToggleBtnRef) {
    if (!answerTabContentRef || !thinkingToggleBtnRef) {
        if(sendButton) sendButton.disabled = false; return;
    }
    const existingAiMessage = answerTabContentRef.querySelector('.message.ai-message');
    if (existingAiMessage) existingAiMessage.remove();
    currentAiMessageElement = null;

    const params = new URLSearchParams();
    params.append('human_message', messageText);
    params.append('session_id', currentSessionId);
    try {
        const response = await fetch(`${FASTAPI_QUERY_ENDPOINT}?${params.toString()}`, {
            method: 'POST', headers: { 'Accept': 'text/plain' },
        });
        if (!response.ok) {
            const errorText = await response.text().catch(() => "Unknown server error.");
            const errorMsgEl = createMessageElement(`Error: ${response.status} ${response.statusText}. ${errorText}`, 'error-message');
            if (answerTabContentRef) answerTabContentRef.appendChild(errorMsgEl);
            if (thinkingToggleBtnRef) finalizeThinkingButton(answerTabContentRef, thinkingToggleBtnRef);
            return;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
            const { value, done } = await reader.read();
            if (done) { if (buffer.trim()) await processLine(buffer.trim(), answerTabContentRef, thinkingToggleBtnRef, false); break; }
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            let newlineIndex;
            while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
                const line = buffer.substring(0, newlineIndex).trim();
                buffer = buffer.substring(newlineIndex + 1);
                if (line.length > 0) await processLine(line, answerTabContentRef, thinkingToggleBtnRef, false);
            }
        }
    } catch (error) {
        console.error("CLIENT: Fetch error (Query Mode):", error);
        const errorMsgEl = createMessageElement(`Network or fetch error: ${error.message}`, 'error-message');
        if (answerTabContentRef) answerTabContentRef.appendChild(errorMsgEl);
        if (thinkingToggleBtnRef) finalizeThinkingButton(answerTabContentRef, thinkingToggleBtnRef);
    } finally {
        if(sendButton) sendButton.disabled = false;
        if (messageInput && chatMainContent && !chatMainContent.classList.contains('pre-chat')) messageInput.focus();
    }
}

async function handleResearchModeSend(researchQuery, answerTabContentRef, thinkingToggleBtnRef) {
    if (!answerTabContentRef || !thinkingToggleBtnRef) {
        if(sendButton) sendButton.disabled = false; return;
    }
    const existingAiMessage = answerTabContentRef.querySelector('.message.ai-message');
    if (existingAiMessage) existingAiMessage.remove();
    currentAiMessageElement = null;

    const requestBody = {
        research_query: researchQuery,
        session_id: currentSessionId,
        conversation_history: conversationHistory.slice(-6, -1)
    };

    const planGenThinkingMsg = createMessageElement("Generating research plan...", 'ai-thinking-message');
    if (!showThinking) planGenThinkingMsg.classList.add('hidden-thought');
    const controlsBar = answerTabContentRef.querySelector('.ai-controls-bar');
    answerTabContentRef.insertBefore(planGenThinkingMsg, controlsBar);
    if (chatConsole) chatConsole.scrollTop = chatConsole.scrollHeight;

    try {
        const response = await fetch(FASTAPI_RESEARCH_START_PLAN_ENDPOINT, {
            method: 'POST',
            headers: { 'Accept': 'text/plain', 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            if(planGenThinkingMsg.parentElement) planGenThinkingMsg.remove();
            const errorText = await response.text().catch(() => "Unknown error fetching plan.");
            const errorMsgEl = createMessageElement(`Failed to get research plan: ${errorText}`, 'error-message');
            answerTabContentRef.appendChild(errorMsgEl);
            if(sendButton) sendButton.disabled = false;
            finalizeThinkingButton(answerTabContentRef, thinkingToggleBtnRef);
            return;
        }

        // Stream the planning process
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let planData = null;

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.trim() === '') continue;

                    if (line.startsWith('THINKING:')) {
                        const thinkingText = line.substring('THINKING:'.length);
                        
                        // Use timeline container for chain linkage display
                        let timelineContainer = answerTabContentRef.querySelector('.thinking-timeline-container');
                        if (!timelineContainer) {
                            timelineContainer = document.createElement('div');
                            timelineContainer.classList.add('thinking-timeline-container');
                            if (controlsBar) {
                                answerTabContentRef.insertBefore(timelineContainer, controlsBar);
                            } else {
                                answerTabContentRef.appendChild(timelineContainer);
                            }
                        }
                        const lastGlowingMessage = timelineContainer.querySelector('.ai-thinking-message.thinking-glow');
                        if (lastGlowingMessage) lastGlowingMessage.classList.remove('thinking-glow');

                        const thoughtEl = createMessageElement(thinkingText, 'ai-thinking-message');
                        thoughtEl.classList.add('thinking-glow');
                        timelineContainer.appendChild(thoughtEl);
                        
                        if (!showThinking) thoughtEl.classList.add('hidden-thought');
                        if (chatConsole) chatConsole.scrollTop = chatConsole.scrollHeight;
                    } else if (line.startsWith('PLAN_READY:')) {
                        const planJson = line.substring('PLAN_READY:'.length);
                        planData = JSON.parse(planJson);
                        currentSessionId = planData.session_id;
                    } else if (line.startsWith('RESEARCH_COMPLETE:')) {
                        const completeJson = line.substring('RESEARCH_COMPLETE:'.length);
                        const completeData = JSON.parse(completeJson);
                        currentSessionId = completeData.session_id;
                        // Handle direct completion (no review needed)
                        planData = completeData;
                    } else if (line.startsWith('ERROR:')) {
                        const errorText = line.substring('ERROR:'.length);
                        const errorMsgEl = createMessageElement(`Research planning error: ${errorText}`, 'error-message');
                        answerTabContentRef.appendChild(errorMsgEl);
                    } else if (line === 'STREAM_ENDED_SESSION_DONE') {
                        break;
                    }
                }
            }
        } finally {
            reader.releaseLock();
            if(planGenThinkingMsg.parentElement) planGenThinkingMsg.remove();
        }

        if (!planData) {
            const errorMsgEl = createMessageElement('Failed to receive plan data from server', 'error-message');
            answerTabContentRef.appendChild(errorMsgEl);
            if(sendButton) sendButton.disabled = false;
            finalizeThinkingButton(answerTabContentRef, thinkingToggleBtnRef);
            return;
        }

        const data = planData;

        if (data.final_report_direct) {
            displayModeStatusMessage("Research process completed before plan review stage.");
            if (data.thinking_steps && Array.isArray(data.thinking_steps)) {
                // Use timeline container for chain linkage display
                let timelineContainer = answerTabContentRef.querySelector('.thinking-timeline-container');
                if (!timelineContainer) {
                    timelineContainer = document.createElement('div');
                    timelineContainer.classList.add('thinking-timeline-container');
                    if (controlsBar) {
                        answerTabContentRef.insertBefore(timelineContainer, controlsBar);
                    } else {
                        answerTabContentRef.appendChild(timelineContainer);
                    }
                }
                
                data.thinking_steps.forEach(thought => {
                    const thoughtEl = createMessageElement(thought, 'ai-thinking-message');
                    if(!showThinking) thoughtEl.classList.add('hidden-thought');
                    timelineContainer.appendChild(thoughtEl);
                });
            }
            if (data.turn_sources && Array.isArray(data.turn_sources) && data.turn_sources.length > 0) {
                // Add Sources tab dynamically when data is available
                addSourcesTab(currentTurnExchangeContainer);
                const sourcesTabContent = currentTurnExchangeContainer.querySelector('.ai-response-area .tab-content[data-tab="sources"]');
                if (sourcesTabContent) displaySources(data.turn_sources, sourcesTabContent);
            }

            currentAiMessageElement = createMessageElement('', 'ai-message');
            answerTabContentRef.appendChild(currentAiMessageElement);
            await simulateTypingHTML(data.final_report_direct, currentAiMessageElement);
            
            // Add feedback buttons to the research response
            const messageId = `msg-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
            currentAiMessageElement.dataset.messageId = messageId;
            const feedbackButtons = createFeedbackButtons(messageId);
            currentAiMessageElement.appendChild(feedbackButtons);

            // Move thinking content to Steps tab when research completes
            const turnContainer = answerTabContentRef.closest('.turn-container');
            moveThinkingToStepsTab(answerTabContentRef, turnContainer);
            
            finalizeThinkingButton(answerTabContentRef, thinkingToggleBtnRef);
            conversationHistory.push({role: 'ai', content: data.final_report_direct });
            if(sendButton) sendButton.disabled = false;
            return;
        }
        if (data.plan_to_review && data.session_id) {
            populateAndShowResearchPlanModal(data.plan_to_review, data.task_description);
        } else {
            const errorMsgEl = createMessageElement("Received invalid plan data from server.", 'error-message');
            answerTabContentRef.appendChild(errorMsgEl);
            if(sendButton) sendButton.disabled = false;
            finalizeThinkingButton(answerTabContentRef, thinkingToggleBtnRef);
        }
    } catch (error) {
        console.error('CLIENT: Error starting research plan:', error);
        if(planGenThinkingMsg.parentElement) planGenThinkingMsg.remove();
        const errorMsgEl = createMessageElement(`Error fetching research plan: ${error.message}`, 'error-message');
        answerTabContentRef.appendChild(errorMsgEl);
        if(sendButton) sendButton.disabled = false;
        finalizeThinkingButton(answerTabContentRef, thinkingToggleBtnRef);
    }
}
async function processLine(line, answerTabContentCtx, thinkingToggleBtnCtx, isResearchStream = false) {
    try {
        if (!answerTabContentCtx) {
            console.error("processLine: Context missing for line:", line);
            return;
        }
        const btnInGroup = thinkingToggleBtnCtx || answerTabContentCtx.querySelector('.related-thinking-toggle');
        const controlsBar = answerTabContentCtx.querySelector('.ai-controls-bar');

        if (line.startsWith('THINKING:')) {
            const thinkingText = line.substring('THINKING:'.length);
            
            // Initially display thinking in Answer tab
            let timelineContainer = answerTabContentCtx.querySelector('.thinking-timeline-container');
            if (!timelineContainer) {
                timelineContainer = document.createElement('div');
                timelineContainer.classList.add('thinking-timeline-container');
                if (controlsBar) {
                    answerTabContentCtx.insertBefore(timelineContainer, controlsBar);
                } else {
                    answerTabContentCtx.appendChild(timelineContainer);
                }
            }
            const lastGlowingMessage = timelineContainer.querySelector('.ai-thinking-message.thinking-glow');
            if (lastGlowingMessage) lastGlowingMessage.classList.remove('thinking-glow');

            const thinkingMsgEl = createMessageElement(thinkingText, 'ai-thinking-message');
            thinkingMsgEl.classList.add('thinking-glow');
            timelineContainer.appendChild(thinkingMsgEl);

            if (!showThinking) thinkingMsgEl.classList.add('hidden-thought');
            if (btnInGroup && btnInGroup.disabled) btnInGroup.disabled = false;

            return;
        }

        if (line.startsWith('SOURCES_DATA:')) {
            const sourcesJson = line.substring('SOURCES_DATA:'.length);
            const sourcesArray = JSON.parse(sourcesJson);
            const turnContainerForSources = answerTabContentCtx.closest('.turn-container');
            if (turnContainerForSources && Array.isArray(sourcesArray) && sourcesArray.length > 0) {
                // Add Sources tab dynamically when data is available
                addSourcesTab(turnContainerForSources);
                const sourcesTabContent = turnContainerForSources.querySelector('.ai-response-area .tab-content[data-tab="sources"]');
                if (sourcesTabContent) displaySources(sourcesArray, sourcesTabContent);
            }
            return;
        }

        if (line.startsWith('CHART_DATA:')) {
            const chartJson = line.substring('CHART_DATA:'.length);
            console.log("Received CHART_DATA JSON string:", chartJson);

            try {
                const wrapperObject = JSON.parse(chartJson);
                console.log("Parsed CHART_DATA wrapper object:", wrapperObject);

                if (wrapperObject && Array.isArray(wrapperObject.chart_options)) {
                    const chartsToRender = wrapperObject.chart_options;
                    const turnContainer = answerTabContentCtx.closest('.turn-container');

                    if (turnContainer && chartsToRender.length > 0) {
                        // Add Images tab dynamically when chart data is available
                        addImagesTab(turnContainer);
                        const imagesTabContent = turnContainer.querySelector('.ai-response-area .tab-content[data-tab="images"]');
                        if (imagesTabContent) {
                            chartsToRender.forEach(chartSpec => {
                                const chartContainer = document.createElement('div');
                                chartContainer.classList.add('chart-render-container');
                                imagesTabContent.appendChild(chartContainer);

                                if (typeof window.ChartRenderer !== 'undefined') {
                                    window.ChartRenderer.renderChart(chartSpec, chartContainer);
                                } else {
                                    chartContainer.innerHTML = '<p style="color: red;">ChartRenderer is not available.</p>';
                                }
                            });
                        }

                        const primaryChartSpec = chartsToRender[0];
                        if (primaryChartSpec) {
                            answerTabContentCtx.dataset.primaryChartSpec = JSON.stringify(primaryChartSpec);
                        }
                    }
                } else {
                    console.warn("Received CHART_DATA but chart_options array was not found.", wrapperObject);
                }
            } catch (e) {
                console.error("Failed to parse or render CHART_DATA:", e);
                const errorContainer = document.createElement('div');
                errorContainer.style.padding = "10px";
                errorContainer.innerHTML = `<p style="color: red; font-weight: bold;">Could not process chart data.</p><p>Raw Data:</p><pre>${chartJson}</pre>`;
                const imagesTabContent = answerTabContentCtx.closest('.turn-container')?.querySelector('.tab-content[data-tab="images"]');
                if (imagesTabContent) imagesTabContent.appendChild(errorContainer);
            }
            return;
        }

        if (line.startsWith('ANSWER_DATA_ENCODED:')) {
            const encodedHtml = line.substring('ANSWER_DATA_ENCODED:'.length);
            
            try {
                // Decode base64 HTML content with proper UTF-8 handling
                const binaryString = atob(encodedHtml);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                const decodedHtml = new TextDecoder('utf-8').decode(bytes);
                streamedHtmlContent += decodedHtml;
            } catch (error) {
                console.error('Error decoding HTML:', error);
            }
            return;
        }
        
        if (line.startsWith('ANSWER_DATA:')) {
            const htmlPart = line.substring('ANSWER_DATA:'.length);
            streamedHtmlContent += htmlPart;
            return;
        }

        if (line === 'STREAM_ENDED_SESSION_DONE') {
            // Remove thinking glow from Answer tab first (where it currently is)
            const lastGlowingMessage = answerTabContentCtx.querySelector('.ai-thinking-message.thinking-glow');
            if (lastGlowingMessage) lastGlowingMessage.classList.remove('thinking-glow');
            
            // Move thinking content and toggle button to Steps tab when final response appears
            const turnContainer = answerTabContentCtx.closest('.turn-container');
            moveThinkingToStepsTab(answerTabContentCtx, turnContainer);
            
            finalizeThinkingButton(answerTabContentCtx, btnInGroup);

            if (streamedHtmlContent) {
                currentAiMessageElement = createMessageElement('', 'ai-message');
                answerTabContentCtx.appendChild(currentAiMessageElement);
                await simulateTypingHTML(streamedHtmlContent, currentAiMessageElement);
                conversationHistory.push({ role: 'ai', content: streamedHtmlContent });
                
                // Add feedback buttons to the AI message
                const messageId = `msg-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
                currentAiMessageElement.dataset.messageId = messageId;
                const feedbackButtons = createFeedbackButtons(messageId);
                currentAiMessageElement.appendChild(feedbackButtons);
            }

            if (answerTabContentCtx.dataset.primaryChartSpec) {
                const primaryChartSpec = JSON.parse(answerTabContentCtx.dataset.primaryChartSpec);
                const chartContainerInAnswer = document.createElement('div');
                chartContainerInAnswer.classList.add('chart-render-container', 'chart-in-answer');
                answerTabContentCtx.appendChild(chartContainerInAnswer);
                if (typeof window.ChartRenderer !== 'undefined') {
                    window.ChartRenderer.renderChart(primaryChartSpec, chartContainerInAnswer);
                }
                delete answerTabContentCtx.dataset.primaryChartSpec;
            }
            streamedHtmlContent = '';
            return;
        }

        if (line.startsWith('ERROR:')) {
            const errorText = line.substring('ERROR:'.length);
            const errorMsgEl = createMessageElement(errorText, 'error-message');
            if (controlsBar) answerTabContentCtx.insertBefore(errorMsgEl, controlsBar);
            else answerTabContentCtx.appendChild(errorMsgEl);
            currentAiMessageElement = null;
            return;
        }

    } catch (e) {
        console.error("Fatal error in processLine:", e, "Original line:", line);
    } finally {
        if (chatConsole) chatConsole.scrollTop = chatConsole.scrollHeight;
    }
}
function handleFileUpload() {
    if (!fileUploadInput.files.length) return;
    const file = fileUploadInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    fetch(FASTAPI_UPLOAD_ENDPOINT, {
        method: 'POST',
        body: formData,
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.detail || 'File upload failed'); });
        }
        return response.json();
    })
    .then(data => {
        stagedFileContent = data.content;
        stagedFileNameEl.textContent = data.filename;
        fileStagingArea.classList.remove('hidden');
        messageInput.placeholder = 'Describe what to do with the document...';
    })
    .catch(error => {
        console.error('Error uploading file:', error);
        alert(`Error: ${error.message}`);
        clearStagedFile();
    });
}
function clearStagedFile() {
    stagedFileContent = null;
    if (stagedFileNameEl) stagedFileNameEl.textContent = '';
    if (fileStagingArea) fileStagingArea.classList.add('hidden');
    if (fileUploadInput) fileUploadInput.value = '';
    if (messageInput) {
        messageInput.placeholder = currentMode === 'query' ? 'Type your query...' : 'Type your assistant query...';
    }
}
function createMessageElement(textOrHtml, type, additionalClass = null) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', type);
    if (additionalClass) messageElement.classList.add(additionalClass);
    if (['ai-message', 'error-message', 'ai-prompt', 'system-message', 'ai-thinking-message'].includes(type)) {
        messageElement.innerHTML = textOrHtml;
    } else {
        messageElement.textContent = textOrHtml;
    }
    return messageElement;
}
function createTurnContainer() {
    const turnContainer = document.createElement('div');
    turnContainer.classList.add('turn-container');
    return turnContainer;
}
function createAIResponseArea(turnContainerRef, isResearchTurn = false) {
    const tabNav = document.createElement('div');
    tabNav.classList.add('tab-navigation', 'ai-response-tabs');
    
    // Start with just the Answer tab - others will be added dynamically when data is available
    const tabs = [
        { 
            id: 'answer', 
            text: 'Answer',
            icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>`
        },
        { 
            id: 'steps', 
            text: 'Steps',
            icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path>
            </svg>`
        }
    ];
    
    tabs.forEach(tabInfo => {
        const tabButton = document.createElement('button');
        tabButton.classList.add('tab-button');
        tabButton.dataset.tab = tabInfo.id;
        tabButton.innerHTML = `${tabInfo.icon}<span>${tabInfo.text}</span>`;
        if (tabInfo.id === 'answer') tabButton.classList.add('active');
        tabNav.appendChild(tabButton);
    });

    const messageContentArea = document.createElement('div');
    messageContentArea.classList.add('message-content-area', 'ai-response-area');
    
    // Create Answer tab content
    const answerTabContent = document.createElement('div');
    answerTabContent.classList.add('tab-content', 'active');
    answerTabContent.dataset.tab = 'answer';
    const controlsBar = document.createElement('div');
    controlsBar.classList.add('ai-controls-bar');
    const toggleBtn = createToggleButton();
    controlsBar.appendChild(toggleBtn);
    answerTabContent.appendChild(controlsBar);
    messageContentArea.appendChild(answerTabContent);

    // Create Steps tab content
    const stepsTabContent = document.createElement('div');
    stepsTabContent.classList.add('tab-content');
    stepsTabContent.dataset.tab = 'steps';
    messageContentArea.appendChild(stepsTabContent);

    tabNav.addEventListener('click', (event) => {
        if (event.target.classList.contains('tab-button') || event.target.closest('.tab-button')) {
            const tabButton = event.target.classList.contains('tab-button') ? event.target : event.target.closest('.tab-button');
            const targetTabId = tabButton.dataset.tab;
            const currentTurn = tabButton.closest('.turn-container');
            if (currentTurn) {
                const aiTabsContainer = currentTurn.querySelector('.ai-response-tabs');
                const aiContentArea = currentTurn.querySelector('.ai-response-area');
                if (aiTabsContainer && aiContentArea) {
                    aiTabsContainer.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
                    tabButton.classList.add('active');
                    aiContentArea.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
                    const targetContent = aiContentArea.querySelector(`.tab-content[data-tab="${targetTabId}"]`);
                    if (targetContent) targetContent.classList.add('active');
                }
            }
        }
    });
    return { tabNav, messageContentArea };
}

// Function to add Sources tab when sources data is available
function addSourcesTab(turnContainer) {
    const tabNav = turnContainer.querySelector('.ai-response-tabs');
    const messageContentArea = turnContainer.querySelector('.ai-response-area');
    
    // Check if Sources tab already exists
    if (tabNav.querySelector('[data-tab="sources"]')) return;
    
    // Create Sources tab button
    const sourcesTabButton = document.createElement('button');
    sourcesTabButton.classList.add('tab-button');
    sourcesTabButton.dataset.tab = 'sources';
    sourcesTabButton.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
        <span>Sources</span>
    `;
    tabNav.appendChild(sourcesTabButton);
    
    // Create Sources tab content
    const sourcesTabContent = document.createElement('div');
    sourcesTabContent.classList.add('tab-content');
    sourcesTabContent.dataset.tab = 'sources';
    messageContentArea.appendChild(sourcesTabContent);
}

// Function to add Images tab when images data is available
function addImagesTab(turnContainer) {
    const tabNav = turnContainer.querySelector('.ai-response-tabs');
    const messageContentArea = turnContainer.querySelector('.ai-response-area');
    
    // Check if Images tab already exists
    if (tabNav.querySelector('[data-tab="images"]')) return;
    
    // Create Images tab button
    const imagesTabButton = document.createElement('button');
    imagesTabButton.classList.add('tab-button');
    imagesTabButton.dataset.tab = 'images';
    imagesTabButton.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <polyline points="21 15 16 10 5 21"></polyline>
        </svg>
        <span>Images</span>
    `;
    tabNav.appendChild(imagesTabButton);
    
    // Create Images tab content
    const imagesTabContent = document.createElement('div');
    imagesTabContent.classList.add('tab-content');
    imagesTabContent.dataset.tab = 'images';
    messageContentArea.appendChild(imagesTabContent);
}
function moveThinkingToStepsTab(answerTabContentCtx, turnContainer) {
    if (!turnContainer) return;
    
    const stepsTabContent = turnContainer.querySelector('.tab-content[data-tab="steps"]');
    if (!stepsTabContent) return;
    
    // Move thinking timeline from answer tab to steps tab
    const answerTimelineContainer = answerTabContentCtx.querySelector('.thinking-timeline-container');
    if (answerTimelineContainer) {
        // Create controls bar in steps tab if it doesn't exist
        let stepsControlsBar = stepsTabContent.querySelector('.ai-controls-bar');
        if (!stepsControlsBar) {
            stepsControlsBar = document.createElement('div');
            stepsControlsBar.classList.add('ai-controls-bar');
            stepsTabContent.appendChild(stepsControlsBar);
        }
        
        // Move the timeline container to steps tab
        stepsTabContent.insertBefore(answerTimelineContainer, stepsControlsBar);
    }
    
    // Move toggle button from answer tab to steps tab
    const answerToggleBtn = answerTabContentCtx.querySelector('.related-thinking-toggle');
    if (answerToggleBtn) {
        let stepsControlsBar = stepsTabContent.querySelector('.ai-controls-bar');
        if (!stepsControlsBar) {
            stepsControlsBar = document.createElement('div');
            stepsControlsBar.classList.add('ai-controls-bar');
            stepsTabContent.appendChild(stepsControlsBar);
        }
        stepsControlsBar.appendChild(answerToggleBtn);
    }
}

function createToggleButton() {
    const toggleBtn = document.createElement('button');
    toggleBtn.classList.add('related-thinking-toggle');
    const buttonTextEl = document.createElement('span');
    buttonTextEl.classList.add('button-text');
    buttonTextEl.textContent = showThinking ? 'Hide Related Thinking' : 'Show Related Thinking';
    const spinnerEl = document.createElement('span');
    spinnerEl.classList.add('spinner-icon');
    spinnerEl.innerHTML = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" class="spinner-svg"><style>.spinner-svg{animation:rt-spin 1s linear infinite}@keyframes rt-spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}</style><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3.5" fill="none" stroke-dasharray="20 11.415" stroke-linecap="round"></circle></svg>`;
    spinnerEl.style.display = 'inline-flex';
    toggleBtn.appendChild(buttonTextEl);
    toggleBtn.appendChild(spinnerEl);
    toggleBtn.disabled = true;

    toggleBtn.addEventListener('click', function() {
        // Check both tabs for thinking messages - they might be in Answer tab initially, then Steps tab after final response
        const turnContainer = this.closest('.turn-container');
        const stepsTabContent = turnContainer ? turnContainer.querySelector('.tab-content[data-tab="steps"]') : null;
        const answerTabContent = turnContainer ? turnContainer.querySelector('.tab-content[data-tab="answer"]') : null;
        
        // First check Steps tab (after final response), then Answer tab (during thinking)
        let targetContainer = null;
        let thinkingMessagesInGroup = [];
        
        if (stepsTabContent) {
            thinkingMessagesInGroup = stepsTabContent.querySelectorAll('.ai-thinking-message');
            if (thinkingMessagesInGroup.length > 0) {
                targetContainer = stepsTabContent;
            }
        }
        
        if (!targetContainer && answerTabContent) {
            thinkingMessagesInGroup = answerTabContent.querySelectorAll('.ai-thinking-message');
            if (thinkingMessagesInGroup.length > 0) {
                targetContainer = answerTabContent;
            }
        }
        
        const currentTextEl = this.querySelector('.button-text');
        if (!currentTextEl || thinkingMessagesInGroup.length === 0) return;
        
        let currentlyAnythingVisibleInGroup = Array.from(thinkingMessagesInGroup).some(msg => !msg.classList.contains('hidden-thought'));
        if (currentlyAnythingVisibleInGroup) {
            thinkingMessagesInGroup.forEach(msg => msg.classList.add('hidden-thought'));
            currentTextEl.textContent = 'Show Related Thinking';
        } else {
            thinkingMessagesInGroup.forEach(msg => msg.classList.remove('hidden-thought'));
            currentTextEl.textContent = 'Hide Related Thinking';
        }
    });
    return toggleBtn;
}
function populateAndShowResearchPlanModal(plan, description) {
    if (!researchPlanModal || !researchPlanEditor || !researchTaskDescriptionEl) return;
    researchPlanEditor.innerHTML = '';
    plan.forEach((step, index) => {
        researchPlanEditor.appendChild(createPlanStepInput(step, index));
    });
    researchTaskDescriptionEl.textContent = description || '';
    researchPlanModal.classList.remove('hidden');
    researchPlanModal.classList.add('visible');
}
function createPlanStepInput(stepText, index) {
    const container = document.createElement('div');
    container.className = 'plan-step-container';
    container.dataset.index = index;
    
    // Check if step contains tool/agent call with JSON parameters
    const parameterMatch = detectToolCallWithParameters(stepText);
    
    if (parameterMatch) {
        // Create dynamic parameter form
        return createDynamicParameterStepInput(parameterMatch, stepText, index, container);
    } else {
        // Create regular textarea input
        return createRegularStepInput(stepText, index, container);
    }
}

function detectToolCallWithParameters(stepText) {
    // Look for patterns like:
    // "TOOL_CALL: tool_name with arguments {json}"
    // "AGENT_CALL: agent_name with arguments {json}"
    // "Use tool_name with parameters: {json}"
    // "Call agent_name with: {json}"
    // "Execute tool with {json}"
    
    console.log('Detecting parameters in step text:', stepText);
    
    // Function to find and extract JSON from text
    function findJsonInText(text, startKeyword) {
        const keywordIndex = text.toLowerCase().indexOf(startKeyword.toLowerCase());
        if (keywordIndex === -1) return null;
        
        // Look for opening brace after the keyword
        let searchStart = keywordIndex + startKeyword.length;
        let braceIndex = text.indexOf('{', searchStart);
        if (braceIndex === -1) return null;
        
        // Find matching closing brace
        let braceCount = 0;
        let jsonStart = braceIndex;
        let jsonEnd = -1;
        
        for (let i = braceIndex; i < text.length; i++) {
            if (text[i] === '{') {
                braceCount++;
            } else if (text[i] === '}') {
                braceCount--;
                if (braceCount === 0) {
                    jsonEnd = i;
                    break;
                }
            }
        }
        
        if (jsonEnd === -1) return null;
        
        return {
            jsonString: text.substring(jsonStart, jsonEnd + 1),
            beforeJson: text.substring(0, jsonStart).trim(),
            afterJson: text.substring(jsonEnd + 1).trim()
        };
    }
    
    // Function to extract tool/agent name from a line
    function extractToolName(line, prefix) {
        const prefixPattern = new RegExp(`${prefix}:\\s*([^\\n]+?)\\s+with\\s+arguments`, 'i');
        const match = line.match(prefixPattern);
        if (match) {
            return match[1].trim();
        }
        
        // Fallback - just get the text after prefix and before "with"
        const simplePattern = new RegExp(`${prefix}:\\s*([^\\n]+?)\\s+with`, 'i');
        const simpleMatch = line.match(simplePattern);
        return simpleMatch ? simpleMatch[1].trim() : null;
    }
    
    // Try different detection approaches
    const detectionApproaches = [
        // Approach 1: TOOL_CALL/AGENT_CALL with arguments
        () => {
            if (stepText.includes('TOOL_CALL:') && stepText.includes('with arguments')) {
                const jsonInfo = findJsonInText(stepText, 'with arguments');
                if (jsonInfo) {
                    const toolName = extractToolName(stepText, 'TOOL_CALL');
                    if (toolName) {
                        return { toolName, stepType: 'TOOL_CALL', jsonInfo };
                    }
                }
            }
            
            if (stepText.includes('AGENT_CALL:') && stepText.includes('with arguments')) {
                const jsonInfo = findJsonInText(stepText, 'with arguments');
                if (jsonInfo) {
                    const toolName = extractToolName(stepText, 'AGENT_CALL');
                    if (toolName) {
                        return { toolName, stepType: 'AGENT_CALL', jsonInfo };
                    }
                }
            }
            
            return null;
        },
        
        // Approach 2: Look for any JSON and infer context
        () => {
            const jsonInfo = findJsonInText(stepText, '');
            if (!jsonInfo) return null;
            
            const beforeJson = jsonInfo.beforeJson.toLowerCase();
            
            // Look for tool/agent indicators
            let toolName = 'Unknown Tool';
            let stepType = 'TOOL_CALL';
            
            // Check for explicit markers
            if (beforeJson.includes('agent_call:') || beforeJson.includes('agent call:')) {
                stepType = 'AGENT_CALL';
                const agentMatch = jsonInfo.beforeJson.match(/agent[_\s]call:\s*([^\n,]+)/i);
                if (agentMatch) toolName = agentMatch[1].trim();
            } else if (beforeJson.includes('tool_call:') || beforeJson.includes('tool call:')) {
                stepType = 'TOOL_CALL';
                const toolMatch = jsonInfo.beforeJson.match(/tool[_\s]call:\s*([^\n,]+)/i);
                if (toolMatch) toolName = toolMatch[1].trim();
            }
            
            // Infer from content
            if (beforeJson.includes('chart') || beforeJson.includes('visualiz') || beforeJson.includes('graph')) {
                stepType = 'AGENT_CALL';
                if (toolName === 'Unknown Tool') {
                    toolName = 'Chart Generation';
                }
            }
            
            return { toolName, stepType, jsonInfo };
        }
    ];
    
    // Try each approach
    for (const approach of detectionApproaches) {
        try {
            const result = approach();
            if (result) {
                const { toolName, stepType, jsonInfo } = result;
                
                // Validate JSON
                const parsedJson = JSON.parse(jsonInfo.jsonString);
                if (typeof parsedJson === 'object' && parsedJson !== null) {
                    console.log('Successfully detected:', { toolName, stepType, parameters: parsedJson });
                    
                    return {
                        toolName: toolName,
                        stepType: stepType,
                        parametersJson: jsonInfo.jsonString,
                        parameters: parsedJson,
                        fullText: stepText,
                        beforeJson: jsonInfo.beforeJson,
                        afterJson: jsonInfo.afterJson
                    };
                }
            }
        } catch (e) {
            console.log('Approach failed:', e);
            continue;
        }
    }
    
    console.log('No tool call detected in:', stepText);
    return null;
}

function createDynamicParameterStepInput(parameterMatch, stepText, index, container) {
    container.classList.add('dynamic-parameter-step');
    
    // Determine display information based on step type
    const isAgent = parameterMatch.stepType === 'AGENT_CALL';
    const typeIcon = isAgent ? '🤖' : '🔧';
    const typeLabel = isAgent ? 'Agent' : 'Tool';
    const stepTypeClass = isAgent ? 'agent-call-step' : 'tool-call-step';
    
    container.classList.add(stepTypeClass);
    
    // Create header with proper tool/agent distinction
    const header = document.createElement('div');
    header.className = 'step-header';
    header.innerHTML = `
        <span class="step-title">${typeIcon} Step ${index + 1}: ${parameterMatch.toolName}</span>
        <span class="step-type-badge ${stepTypeClass}">${typeLabel}</span>
        <div class="step-actions">
            <button class="toggle-raw-button" title="Toggle Raw/Form View">📝</button>
            <button class="remove-step-button" title="Remove step">&times;</button>
        </div>
    `;
    
    // Create description input if there's text before/after JSON
    const descriptionContainer = document.createElement('div');
    descriptionContainer.className = 'step-description-container';
    
    const descriptionLabel = document.createElement('label');
    descriptionLabel.textContent = 'Description:';
    descriptionLabel.className = 'step-description-label';
    
    const descriptionInput = document.createElement('input');
    descriptionInput.type = 'text';
    descriptionInput.className = 'step-description-input';
    descriptionInput.value = extractDescription(parameterMatch);
    descriptionInput.placeholder = 'Enter step description...';
    
    descriptionContainer.appendChild(descriptionLabel);
    descriptionContainer.appendChild(descriptionInput);
    
    // Create parameter form container
    const parameterContainer = document.createElement('div');
    parameterContainer.className = 'parameter-form-container';
    
    // Create raw textarea (initially hidden)
    const rawTextarea = document.createElement('textarea');
    rawTextarea.className = 'raw-step-textarea hidden';
    rawTextarea.value = stepText;
    rawTextarea.rows = 4;
    
    // Initialize form elements using logo_service
    let formElements = null;
    
    // Show loading indicator
    parameterContainer.innerHTML = '<div class="loading-indicator">🔄 Generating form...</div>';
    
    // Store reference for later access
    container.formElements = null;
    
    // Generate form asynchronously
    generateFormFromLogoService(parameterMatch.toolName, parameterMatch.parameters, parameterContainer)
        .then(formData => {
            formElements = formData;
            container.formElements = formData;  // Store on container for getStepData access
            console.log('Successfully created form elements from logo_service:', formElements);
        })
        .catch(e => {
            console.error('Error creating parameter form from logo_service:', e);
            parameterContainer.innerHTML = `<div class="error-message">
                <strong>Form Generation Failed</strong><br>
                Unable to generate form from logo_service: ${e.message}<br>
                <small>Please check that logo_service is running and accessible.</small>
            </div>`;
        });
    
    // Event handlers
    const toggleButton = header.querySelector('.toggle-raw-button');
    const removeButton = header.querySelector('.remove-step-button');
    
    let isRawMode = false;
    
    toggleButton.addEventListener('click', () => {
        isRawMode = !isRawMode;
        
        if (isRawMode) {
            // Switch to raw mode
            parameterContainer.classList.add('hidden');
            rawTextarea.classList.remove('hidden');
            toggleButton.textContent = '📋';
            toggleButton.title = 'Switch to Form View';
        } else {
            // Switch to form mode
            if (container.formElements || parameterContainer.querySelector('.dynamic-form-fields')) {
                parameterContainer.classList.remove('hidden');
                rawTextarea.classList.add('hidden');
                toggleButton.textContent = '📝';
                toggleButton.title = 'Switch to Raw View';
            }
        }
    });
    
    removeButton.addEventListener('click', () => container.remove());
    
    // Store data for later retrieval
    container.dataset.parameterHandler = 'true';
    container.dataset.toolName = parameterMatch.toolName;
    
    // Custom getData function for this container
    container.getStepData = () => {
        if (isRawMode) {
            return rawTextarea.value.trim();
        } else {
            const description = descriptionInput.value.trim();
            if (container.formElements && container.formElements.getData) {
                const paramData = container.formElements.getData();
                const jsonStr = JSON.stringify(paramData);
                
                // Use the detected step type to format the output correctly
                const stepPrefix = parameterMatch.stepType || 'TOOL_CALL';
                const beforeText = description ? `${description}\n` : '';
                
                if (stepPrefix === 'AGENT_CALL') {
                    return `${beforeText}AGENT_CALL: ${parameterMatch.toolName} with arguments ${jsonStr}`;
                } else if (stepPrefix === 'TOOL_CALL') {
                    return `${beforeText}TOOL_CALL: ${parameterMatch.toolName} with arguments ${jsonStr}`;
                } else if (description) {
                    return `${description} using ${parameterMatch.toolName} with parameters: ${JSON.stringify(paramData, null, 2)}`;
                } else {
                    return `Use ${parameterMatch.toolName} with parameters: ${JSON.stringify(paramData, null, 2)}`;
                }
            } else {
                return rawTextarea.value.trim();
            }
        }
    };
    
    // Build the container
    container.appendChild(header);
    container.appendChild(descriptionContainer);
    container.appendChild(parameterContainer);
    container.appendChild(rawTextarea);
    
    return container;
}

function createRegularStepInput(stepText, index, container) {
    const textarea = document.createElement('textarea');
    textarea.value = stepText;
    textarea.rows = 2;
    textarea.className = 'regular-step-textarea';
    
    const removeBtn = document.createElement('button');
    removeBtn.className = 'remove-step-button';
    removeBtn.innerHTML = '&times;';
    removeBtn.title = 'Remove step';
    removeBtn.onclick = () => container.remove();
    
    // Custom getData function
    container.getStepData = () => textarea.value.trim();
    
    container.appendChild(textarea);
    container.appendChild(removeBtn);
    return container;
}

function extractDescription(parameterMatch) {
    // Extract meaningful description from the text before the JSON
    const beforeText = parameterMatch.beforeJson.trim();
    const afterText = parameterMatch.afterJson.trim();
    
    // Clean the before text to get meaningful description
    let description = beforeText;
    
    // Remove TOOL_CALL:/AGENT_CALL: patterns
    description = description.replace(/^.*?(?:TOOL_CALL|AGENT_CALL):\s*[^\n]*?\s+with\s+arguments\s*$/i, '').trim();
    
    // Remove common patterns that aren't descriptive
    description = description.replace(/(?:use|call|execute)\s+\w+\s*(?:with\s*(?:parameters?|args?)?:?\s*)?$/i, '').trim();
    
    // If we have a good description from before the call, use it
    if (description && description.length > 10 && !description.match(/^(use|call|execute)\s/i)) {
        return description;
    }
    
    // Try to extract from after text
    if (afterText && afterText.length > 5) {
        return afterText;
    }
    
    // Look for description in the full text before the tool/agent call
    const lines = parameterMatch.fullText.split('\n');
    for (const line of lines) {
        const cleanLine = line.trim();
        // Look for descriptive lines that aren't the call itself
        if (cleanLine && 
            !cleanLine.match(/^(TOOL_CALL|AGENT_CALL):/i) && 
            !cleanLine.match(/^\s*\{/) && 
            cleanLine.length > 10) {
            return cleanLine;
        }
    }
    
    // Default fallback
    return `Execute ${parameterMatch.toolName}`;
}
function handleCancelResearchPlan() {
    if (!researchPlanModal || !sendButton || !messageInput) return;
    
    // Hide the modal
    researchPlanModal.classList.add('hidden');
    researchPlanModal.classList.remove('visible');
    
    // Get the answer tab content to add cancellation message
    const answerTabContent = currentTurnExchangeContainer?.querySelector('.ai-response-area .tab-content[data-tab="answer"]');
    const thinkingToggleBtn = answerTabContent?.querySelector('.related-thinking-toggle');
    
    if (answerTabContent) {
        // Add cancellation message to the chat
        const cancellationMessage = createMessageElement("Research plan rejected by user. Ready for next query.", 'ai-message');
        answerTabContent.appendChild(cancellationMessage);
        
        // Hide the thinking button completely since no thinking content was generated
        if (thinkingToggleBtn) {
            thinkingToggleBtn.style.display = 'none';
        }
        
        // Scroll to show the new message
        if (chatConsole) chatConsole.scrollTop = chatConsole.scrollHeight;
    }
    
    // Re-enable the send button and focus message input
    sendButton.disabled = false;
    // Focus without triggering session expansion if chat is already started
    if (isChatSessionStarted && chatMainContent && !chatMainContent.classList.contains('pre-chat')) {
        messageInput.focus();
    }
    
    // Clear the current session ID to properly reset state
    currentSessionId = null;
}

async function handleSubmitResearchPlan() {
    if (!researchPlanEditor || !researchPlanModal || !sendButton || !messageInput) return;
    
    // Collect data from all step containers, using custom getData method if available
    const editedPlanSteps = Array.from(researchPlanEditor.querySelectorAll('.plan-step-container'))
        .map(container => {
            if (container.getStepData) {
                return container.getStepData();
            } else {
                // Fallback for old-style containers
                const textarea = container.querySelector('textarea');
                return textarea ? textarea.value.trim() : '';
            }
        })
        .filter(Boolean);

    researchPlanModal.classList.add('hidden');
    researchPlanModal.classList.remove('visible');

    if (editedPlanSteps.length === 0) {
        displayModeStatusMessage("Research cancelled: Plan was empty.");
        sendButton.disabled = false;
        // Focus without triggering session expansion if chat is already started
        if (isChatSessionStarted && chatMainContent && !chatMainContent.classList.contains('pre-chat')) {
            messageInput.focus();
        }
        return;
    }

    const answerTabContent = currentTurnExchangeContainer.querySelector('.ai-response-area .tab-content[data-tab="answer"]');
    const thinkingToggleBtn = answerTabContent ? answerTabContent.querySelector('.related-thinking-toggle') : null;

    if (!answerTabContent) {
        sendButton.disabled = false; return;
    }

    const requestBody = {
        session_id: currentSessionId,
        edited_plan: editedPlanSteps,
        original_query: currentResearchQuery,
        conversation_history: conversationHistory.slice(-6)
    };

    try {
        const response = await fetch(FASTAPI_RESEARCH_EXECUTE_PLAN_ENDPOINT, {
            method: 'POST',
            headers: { 'Accept': 'text/plain', 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => "Unknown server error executing plan.");
            const errorMsgEl = createMessageElement(`Error executing plan: ${errorText}`, 'error-message');
            answerTabContent.appendChild(errorMsgEl);
            if (thinkingToggleBtn) finalizeThinkingButton(answerTabContent, thinkingToggleBtn);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
            const { value, done } = await reader.read();
            if (done) { if (buffer.trim()) await processLine(buffer.trim(), answerTabContent, thinkingToggleBtn, true); break; }
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            let newlineIndex;
            while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
                const line = buffer.substring(0, newlineIndex).trim();
                buffer = buffer.substring(newlineIndex + 1);
                if (line.length > 0) await processLine(line, answerTabContent, thinkingToggleBtn, true);
            }
        }
    } catch (error) {
        console.error("CLIENT: Fetch error (Execute Plan):", error);
        const errorMsgEl = createMessageElement(`Network error during plan execution: ${error.message}`, 'error-message');
        answerTabContent.appendChild(errorMsgEl);
        if (thinkingToggleBtn) finalizeThinkingButton(answerTabContent, thinkingToggleBtn);
    } finally {
        sendButton.disabled = false;
        if (messageInput && !chatMainContent.classList.contains('pre-chat')) messageInput.focus();
    }
}
function displaySources(sources, container) {
    if (!container || !sources || sources.length === 0) return;
    const placeholder = container.querySelector('.tab-placeholder');
    if (placeholder) placeholder.remove();
    sources.forEach(source => {
        const item = document.createElement('div');
        item.className = 'source-item';
        const title = document.createElement('a');
        title.className = 'source-title';
        title.href = source.url || '#';
        title.textContent = source.title || 'Untitled Source';
        title.target = '_blank';
        const url = document.createElement('p');
        url.className = 'source-url';
        url.textContent = source.url || '';
        const snippet = document.createElement('p');
        snippet.className = 'source-snippet';
        snippet.textContent = source.snippet || '';
        item.appendChild(title);
        item.appendChild(url);
        item.appendChild(snippet);
        container.appendChild(item);
    });
}
async function simulateTypingHTML(htmlContent, element, speed = 1) {
    element.innerHTML = htmlContent;
    if (chatConsole) chatConsole.scrollTop = chatConsole.scrollHeight;
}

// Create feedback buttons for AI messages
function createFeedbackButtons(messageId) {
    const feedbackContainer = document.createElement('div');
    feedbackContainer.classList.add('message-feedback-buttons');
    feedbackContainer.dataset.messageId = messageId;
    
    // Like button
    const likeButton = document.createElement('button');
    likeButton.classList.add('feedback-button', 'like-button');
    likeButton.title = 'Like this response (click again to undo)';
    likeButton.innerHTML = `
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M7.493 18.75c-.425 0-.82-.236-.975-.632A7.48 7.48 0 016 15.375c0-1.75.599-3.358 1.602-4.634.151-.192.373-.309.6-.397.473-.183.89-.514 1.212-.924a9.042 9.042 0 012.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 00.322-1.672V3a.75.75 0 01.75-.75 2.25 2.25 0 012.25 2.25c0 1.152-.26 2.243-.723 3.218-.266.558-.107 1.282.725 1.282h3.126c1.026 0 1.945.694 2.054 1.715.045.422.068.85.068 1.285a11.95 11.95 0 01-2.649 7.521c-.388.482-.987.729-1.605.729H14.23c-.483 0-.964-.078-1.423-.23l-3.114-1.04a4.501 4.501 0 00-1.423-.23h-.777zM2.331 10.977a11.969 11.969 0 00-.831 4.398 12 12 0 00.52 3.507c.26.85 1.084 1.368 1.973 1.368H4.9c.445 0 .72-.498.523-.898a8.963 8.963 0 01-.924-3.977c0-1.708.476-3.305 1.302-4.666.245-.403-.028-.959-.5-.959H4.25c-.832 0-1.612.453-1.918 1.227z"/>
        </svg>
    `;
    
    // Dislike button
    const dislikeButton = document.createElement('button');
    dislikeButton.classList.add('feedback-button', 'dislike-button');
    dislikeButton.title = 'Dislike this response (click again to undo)';
    dislikeButton.innerHTML = `
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M15.73 5.25h1.035A7.465 7.465 0 0118 9.375a7.465 7.465 0 01-1.235 4.125h-.148c-.806 0-1.534.446-2.031 1.08a9.04 9.04 0 01-2.861 2.4c-.723.384-1.35.956-1.653 1.715a4.498 4.498 0 00-.322 1.672V21a.75.75 0 01-.75.75 2.25 2.25 0 01-2.25-2.25c0-1.152.26-2.243.723-3.218C7.74 15.724 7.366 15 6.748 15H3.622c-1.026 0-1.945-.694-2.054-1.715A12.134 12.134 0 011.5 12c0-2.848.992-5.464 2.649-7.521C4.537 3.997 5.136 3.75 5.754 3.75H9.77a4.5 4.5 0 011.423.23l3.114 1.04a4.5 4.5 0 001.423.23zM21.669 14.023c.536-1.362.831-2.845.831-4.398 0-1.22-.182-2.398-.52-3.507-.26-.85-1.084-1.368-1.973-1.368H19.1c-.445 0-.72.498-.523.898.591 1.2.924 2.55.924 3.977a8.958 8.958 0 01-1.302 4.666c-.245.403.028.959.5.959h1.053c.832 0 1.612-.453 1.918-1.227z"/>
        </svg>
    `;
    
    // Feedback button
    const feedbackButton = document.createElement('button');
    feedbackButton.classList.add('feedback-text-button');
    feedbackButton.textContent = 'Feedback';
    feedbackButton.title = 'Provide detailed feedback';
    
    // Add event listeners
    likeButton.addEventListener('click', () => handleFeedback(messageId, 'like', likeButton, dislikeButton));
    dislikeButton.addEventListener('click', () => handleFeedback(messageId, 'dislike', likeButton, dislikeButton));
    feedbackButton.addEventListener('click', () => showFeedbackModal(messageId));
    
    feedbackContainer.appendChild(likeButton);
    feedbackContainer.appendChild(dislikeButton);
    feedbackContainer.appendChild(feedbackButton);
    
    return feedbackContainer;
}

// Handle like/dislike feedback with undo functionality
function handleFeedback(messageId, type, likeButton, dislikeButton) {
    const isCurrentlyActive = (type === 'like') ? 
        likeButton.classList.contains('active-like') : 
        dislikeButton.classList.contains('active-dislike');
    
    // Remove active states from both buttons
    likeButton.classList.remove('active-like');
    dislikeButton.classList.remove('active-dislike');
    
    // If clicking the same button that was active, it's an undo
    if (isCurrentlyActive) {
        console.log(`Message ${messageId} feedback: undo ${type}`);
        // Optional: Send undo to backend
        // sendFeedbackToServer(messageId, 'undo', type);
        return;
    }
    
    // Add active state to clicked button
    if (type === 'like') {
        likeButton.classList.add('active-like');
    } else {
        dislikeButton.classList.add('active-dislike');
    }
    
    // Store feedback (you can send this to your backend)
    console.log(`Message ${messageId} feedback: ${type}`);
    
    // Optional: Send to backend
    // sendFeedbackToServer(messageId, type);
}

// Show feedback modal (placeholder)
function showFeedbackModal(messageId) {
    // For now, just prompt for feedback
    const feedback = prompt('Please provide your feedback:');
    if (feedback && feedback.trim()) {
        console.log(`Message ${messageId} detailed feedback:`, feedback);
        // Optional: Send to backend
        // sendDetailedFeedbackToServer(messageId, feedback);
        alert('Thank you for your feedback!');
    }
}
function updateExistingThinkingMessagesVisibility() {
    const allThinkingMessages = document.querySelectorAll('.ai-thinking-message');
    allThinkingMessages.forEach(msg => {
        if (showThinking) {
            msg.classList.remove('hidden-thought');
        } else {
            msg.classList.add('hidden-thought');
        }
    });
}

// Conversation History Management Functions
async function loadConversationHistory() {
    try {
        const response = await fetch('/conversation/history');
        if (!response.ok) throw new Error('Failed to load conversation history');
        
        const data = await response.json();
        displayConversationHistory(data.conversations);
    } catch (error) {
        console.error('Error loading conversation history:', error);
    }
}

function displayConversationHistory(conversations) {
    if (!conversationHistoryList) return;
    
    conversationHistoryList.innerHTML = '';
    
    if (!conversations || conversations.length === 0) {
        conversationHistoryList.innerHTML = '<p style="color: #888; font-size: 12px; padding: 0.5rem 1rem;">No recent conversations</p>';
        return;
    }
    
    conversations.forEach(conversation => {
        const item = document.createElement('div');
        item.className = 'conversation-history-item';
        item.dataset.sessionId = conversation.session_id;
        
        const title = document.createElement('div');
        title.className = 'conversation-title';
        title.textContent = conversation.title;
        
        const timestamp = document.createElement('div');
        timestamp.className = 'conversation-timestamp';
        timestamp.textContent = formatTimestamp(conversation.timestamp);
        
        item.appendChild(title);
        item.appendChild(timestamp);
        
        // Add click handler to load conversation
        item.addEventListener('click', () => loadConversation(conversation.session_id));
        
        conversationHistoryList.appendChild(item);
    });
}

function formatTimestamp(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffHours = diffMs / (1000 * 60 * 60);
    const diffDays = diffMs / (1000 * 60 * 60 * 24);
    
    if (diffHours < 1) {
        return 'Just now';
    } else if (diffHours < 24) {
        return `${Math.floor(diffHours)}h ago`;
    } else if (diffDays < 7) {
        return `${Math.floor(diffDays)}d ago`;
    } else {
        return date.toLocaleDateString();
    }
}

async function handleNewConversation() {
    // Save current conversation if it has messages
    if (isChatSessionStarted && conversationHistory.length > 0) {
        await saveCurrentConversation();
    }
    
    // Reset conversation state
    resetConversationState();
    
    // Start new conversation
    try {
        const response = await fetch('/conversation/new', { method: 'POST' });
        if (!response.ok) throw new Error('Failed to start new conversation');
        
        const data = await response.json();
        currentSessionId = data.session_id;
        
        // Reload conversation history
        await loadConversationHistory();
        
        console.log('Started new conversation:', currentSessionId);
    } catch (error) {
        console.error('Error starting new conversation:', error);
        // Generate fallback session ID
        currentSessionId = `client-generated-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }
}

function resetConversationState() {
    // Clear chat console
    if (chatConsole) {
        chatConsole.innerHTML = '';
    }
    
    // Reset state variables
    conversationHistory = [];
    currentAiMessageElement = null;
    currentTurnExchangeContainer = null;
    streamedHtmlContent = '';
    isChatSessionStarted = false;
    
    // Reset UI
    initializePreChatState();
    
    // Clear any staged files
    clearStagedFile();
    
    // Clear tool/agent selections
    userToolSelections.clear();
    userAgentSelections.clear();
}

async function saveCurrentConversation(title = null) {
    if (!currentSessionId || conversationHistory.length === 0) return;
    
    try {
        const response = await fetch('/conversation/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                messages: conversationHistory,
                title: title
            })
        });
        
        if (!response.ok) throw new Error('Failed to save conversation');
        
        console.log('Conversation saved successfully');
    } catch (error) {
        console.error('Error saving conversation:', error);
    }
}

async function loadConversation(sessionId) {
    try {
        // Save current conversation first if it has messages
        if (isChatSessionStarted && conversationHistory.length > 0 && currentSessionId !== sessionId) {
            await saveCurrentConversation();
        }
        
        const response = await fetch(`/conversation/${sessionId}`);
        if (!response.ok) throw new Error('Failed to load conversation');
        
        const conversation = await response.json();
        
        // Reset current state
        resetConversationState();
        
        // Set up loaded conversation
        currentSessionId = sessionId;
        conversationHistory = conversation.messages || [];
        
        // Reconstruct chat UI from messages
        reconstructChatFromMessages(conversationHistory);
        
        // Update active state in history list
        updateActiveConversation(sessionId);
        
        console.log('Loaded conversation:', sessionId);
    } catch (error) {
        console.error('Error loading conversation:', error);
    }
}

function reconstructChatFromMessages(messages) {
    if (!chatConsole || !messages || messages.length === 0) return;
    
    chatConsole.innerHTML = '';
    isChatSessionStarted = true;
    
    // Remove pre-chat state
    if (chatMainContent) {
        chatMainContent.classList.remove('pre-chat');
    }
    document.body.classList.remove('pre-chat-active');
    
    let currentTurn = null;
    
    messages.forEach((message, index) => {
        if (message.role === 'user') {
            // Create new turn for user message
            currentTurn = createTurnContainer();
            chatConsole.appendChild(currentTurn);
            
            const userMessage = createMessageElement(message.content, 'user-message');
            currentTurn.appendChild(userMessage);
        } else if (message.role === 'assistant' && currentTurn) {
            // Add AI response to current turn
            const aiResponse = createAIResponseArea(currentTurn, false);
            const answerContent = aiResponse.tabNav.parentElement.querySelector('[data-tab="answer"]');
            
            if (answerContent) {
                answerContent.innerHTML = message.content;
            }
        }
    });
    
    if (chatConsole) {
        chatConsole.scrollTop = chatConsole.scrollHeight;
    }
}

function updateActiveConversation(activeSessionId) {
    const historyItems = document.querySelectorAll('.conversation-history-item');
    historyItems.forEach(item => {
        if (item.dataset.sessionId === activeSessionId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// Auto-save conversation when user sends a message
function trackConversationMessage(role, content) {
    conversationHistory.push({
        role: role,
        content: content,
        timestamp: new Date().toISOString()
    });
}

// Override the original handleSend function to track messages
const originalHandleSend = handleSend;
window.handleSend = async function() {
    const messageText = messageInput ? messageInput.value.trim() : '';
    if (messageText) {
        trackConversationMessage('user', messageText);
    }
    
    // Call original function
    await originalHandleSend();
    
    // Auto-save after a delay (in case there are multiple rapid messages)
    setTimeout(() => {
        if (isChatSessionStarted && conversationHistory.length > 0) {
            saveCurrentConversation();
        }
    }, 5000);
};
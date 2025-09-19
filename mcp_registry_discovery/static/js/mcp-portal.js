// MCP Portal JavaScript
// Dynamic URL configuration for both local development and Kubernetes deployment
const MANAGE_URL = (() => {
    const pathname = window.location.pathname;
    const hostname = window.location.hostname;
    
    console.log('MCP Portal URL Detection:', { pathname, hostname });
    
    // Detect if we're running in Kubernetes by checking the URL path prefix
    if (pathname.startsWith('/toolbox/')) {
        console.log('Detected Kubernetes deployment with /toolbox/ prefix');
        return '/toolbox/manage';
    }
    
    // Local development (localhost with any port) or direct access
    if (hostname === 'localhost' || hostname === '127.0.0.1' || pathname === '/') {
        console.log('Detected local development environment');
        return '/manage';
    }
    
    // Fallback - try relative path
    console.log('Using fallback relative path');
    return 'manage';
})();

console.log('MCP Portal using MANAGE_URL:', MANAGE_URL);

// Dynamic MCP endpoint URL configuration
const MCP_URL = (() => {
    const pathname = window.location.pathname;
    const hostname = window.location.hostname;
    
    console.log('MCP URL Detection:', { pathname, hostname });
    
    // Detect if we're running in Kubernetes by checking the URL path prefix
    if (pathname.startsWith('/toolbox/')) {
        console.log('Detected Kubernetes deployment with /toolbox/ prefix for MCP');
        return '/toolbox/mcp';
    }
    
    // Local development (localhost with any port) or direct access
    if (hostname === 'localhost' || hostname === '127.0.0.1' || pathname === '/') {
        console.log('Detected local development environment for MCP');
        return '/mcp';
    }
    
    // Fallback - try relative path
    console.log('Using fallback relative path for MCP');
    return 'mcp';
})();

console.log('MCP Portal using MCP_URL:', MCP_URL);

let currentServers = {};
let discoveredTools = [];
let currentCapabilities = {};
let currentTab = 'servers';

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeTabNavigation();
    loadServers();
});

// Tab Navigation
function initializeTabNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update navigation
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabName).classList.add('active');

    // Update header title
    const titles = {
        'servers': 'MCP Servers',
        'tools': 'Tool Discovery',
        'capabilities': 'Tool Capabilities',
        'testing': 'Tool Testing'
    };
    document.querySelector('.header-title').textContent = titles[tabName] || 'Dashboard';

    currentTab = tabName;

    // Load data for specific tabs
    if (tabName === 'tools' && discoveredTools.length === 0) {
        discoverTools();
    } else if (tabName === 'capabilities' && Object.keys(currentCapabilities).length === 0) {
        loadCapabilities();
    }
}

// Server Management
async function loadServers() {
    try {
        const response = await fetch(MANAGE_URL, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "server.list",
                id: `load-servers-${Date.now()}`
            })
        });

        const data = await response.json();
        if (data.result && data.result.server_cards) {
            currentServers = data.result.server_cards;
            displayServers(currentServers);
        } else {
            // No servers found, show empty state
            currentServers = {};
            displayServers(currentServers);
        }
    } catch (error) {
        console.error('Failed to load servers:', error);
        showAlert('Failed to load servers: ' + error.message, 'error');
    }
}

function displayServers(servers) {
    const tableBody = document.getElementById('serversTableBody');
    
    if (Object.keys(servers).length === 0) {
        tableBody.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-server"></i>
                <h3>No MCP Servers</h3>
                <p>Add your first MCP server to get started</p>
                <button class="btn btn-primary" onclick="showAddServerModal()">
                    <i class="fas fa-plus"></i>
                    Add Server
                </button>
            </div>
        `;
        return;
    }

    let html = '';
    for (const [serverId, server] of Object.entries(servers)) {
        const status = getServerStatus(server);
        const statusClass = status.toLowerCase();
        
        html += `
            <div class="server-row">
                <div class="col-checkbox">
                    <input type="checkbox" class="server-checkbox" data-server-id="${serverId}">
                </div>
                <div class="col-status">
                    <span class="status-badge status-${statusClass}">${status}</span>
                </div>
                <div class="col-name">
                    <div class="server-name">${server.name}</div>
                    <div class="server-id">${serverId}</div>
                </div>
                <div class="col-endpoint">
                    <div class="endpoint-url">${server.url}</div>
                </div>
                <div class="col-capabilities">
                    <span class="capabilities-count">${Object.keys(server.capabilities || {}).length}</span>
                </div>
                <div class="col-version">
                    <span class="version-tag">${server.metadata?.protocol_version || 'N/A'}</span>
                </div>
                <div class="col-actions">
                    <div class="action-buttons">
                        <button class="action-btn" onclick="testServer('${serverId}')" title="Test Connection">
                            <i class="fas fa-plug"></i>
                        </button>
                        <button class="action-btn" onclick="viewServerDetails('${serverId}')" title="View Details">
                            <i class="fas fa-info-circle"></i>
                        </button>
                        <button class="action-btn danger" onclick="deleteServer('${serverId}')" title="Delete Server">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    tableBody.innerHTML = html;
}

function getServerStatus(server) {
    // Simple status determination - you could enhance this with actual health checks
    const now = new Date();
    const updated = new Date(server.updated_at);
    const diffHours = (now - updated) / (1000 * 60 * 60);
    
    if (diffHours < 1) return 'Online';
    if (diffHours < 24) return 'Pending';
    return 'Offline';
}

// Add Server Modal
function showAddServerModal() {
    document.getElementById('addServerModal').style.display = 'block';
}

function closeAddServerModal() {
    document.getElementById('addServerModal').style.display = 'none';
    document.getElementById('modalServerUrl').value = '';
    document.getElementById('modalServerDescription').value = '';
}

async function addServer() {
    const serverUrl = document.getElementById('modalServerUrl').value.trim();
    const description = document.getElementById('modalServerDescription').value.trim();

    if (!serverUrl) {
        showAlert('Please enter a server URL', 'warning');
        return;
    }

    try {
        const response = await fetch(MANAGE_URL, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "server.add",
                params: {
                    server_url: serverUrl,
                    description: description
                },
                id: `add-server-${Date.now()}`
            })
        });

        const data = await response.json();
        if (data.result && data.result.success) {
            showAlert('Server added successfully!', 'success');
            closeAddServerModal();
            loadServers();
        } else {
            throw new Error(data.error ? data.error.message : 'Failed to add server');
        }
    } catch (error) {
        console.error('Failed to add server:', error);
        showAlert('Failed to add server: ' + error.message, 'error');
    }
}

// Server Actions
async function testServer(serverId) {
    try {
        const response = await fetch(MANAGE_URL, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "server.test",
                params: { server_id: serverId },
                id: `test-server-${Date.now()}`
            })
        });

        const data = await response.json();
        if (data.result) {
            const result = data.result;
            const statusIcon = result.status === 'healthy' ? '✅' : '❌';
            showAlert(`${statusIcon} Server Test: ${result.status} (${Math.round(result.response_time * 1000)}ms)`, 
                     result.status === 'healthy' ? 'success' : 'error');
        } else {
            throw new Error(data.error ? data.error.message : 'Test failed');
        }
    } catch (error) {
        console.error('Server test failed:', error);
        showAlert('Server test failed: ' + error.message, 'error');
    }
}

function viewServerDetails(serverId) {
    const server = currentServers[serverId];
    if (!server) return;

    const detailsHtml = `
        <div class="server-details">
            <div class="form-group">
                <label class="form-label">Server ID</label>
                <input type="text" class="form-control" value="${serverId}" readonly>
            </div>
            <div class="form-group">
                <label class="form-label">Name</label>
                <input type="text" class="form-control" value="${server.name}" readonly>
            </div>
            <div class="form-group">
                <label class="form-label">URL</label>
                <input type="text" class="form-control" value="${server.url}" readonly>
            </div>
            <div class="form-group">
                <label class="form-label">Description</label>
                <textarea class="form-control" rows="2" readonly>${server.description || 'No description'}</textarea>
            </div>
            <div class="form-group">
                <label class="form-label">Capabilities</label>
                <pre class="test-results">${JSON.stringify(server.capabilities, null, 2)}</pre>
            </div>
            <div class="form-group">
                <label class="form-label">Metadata</label>
                <pre class="test-results">${JSON.stringify(server.metadata, null, 2)}</pre>
            </div>
        </div>
    `;

    document.getElementById('serverDetailsContent').innerHTML = detailsHtml;
    document.getElementById('serverDetailsModal').style.display = 'block';
}

async function deleteServer(serverId) {
    const server = currentServers[serverId];
    if (!server) return;

    if (!confirm(`Are you sure you want to delete server "${server.name}"?`)) return;

    try {
        const response = await fetch(MANAGE_URL, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "server.remove",
                params: { server_id: serverId },
                id: `remove-server-${Date.now()}`
            })
        });

        const data = await response.json();
        if (data.result && data.result.success) {
            showAlert('Server deleted successfully!', 'success');
            loadServers();
        } else {
            throw new Error(data.error ? data.error.message : 'Failed to delete server');
        }
    } catch (error) {
        console.error('Failed to delete server:', error);
        showAlert('Failed to delete server: ' + error.message, 'error');
    }
}

// Tool Discovery
async function discoverTools() {
    console.log('🔧 discoverTools() called');
    console.log('🔧 MANAGE_URL:', MANAGE_URL);
    console.log('🔧 MCP_URL:', MCP_URL);
    console.log('🔧 Current location:', window.location.href);

    const loadingElement = document.getElementById('toolsTableBody');
    loadingElement.innerHTML = '<div class="loading">Discovering tools...</div>';

    try {
        // Step 1: Initialize MCP session
        console.log('🔧 Step 1: Initializing MCP session at:', MCP_URL);
        const initResponse = await fetch(MCP_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2025-06-18'
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "initialize",
                params: {
                    protocolVersion: "2025-06-18",
                    clientInfo: {
                        name: "mcp-portal-ui",
                        version: "1.0.0"
                    }
                },
                id: `init-${Date.now()}`
            })
        });

        console.log('🔧 Init response status:', initResponse.status);
        const initData = await initResponse.json();
        console.log('🔧 Init response data:', initData);
        const sessionId = initResponse.headers.get('Mcp-Session-Id');
        console.log('🔧 Session ID:', sessionId);

        if (!initData.result || !sessionId) {
            throw new Error('Failed to initialize MCP session');
        }

        // Step 2: Send initialized notification
        await fetch(MCP_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2025-06-18',
                'Mcp-Session-Id': sessionId
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "notifications/initialized"
            })
        });

        // Step 3: Get tools list with session
        const response = await fetch(MCP_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2025-06-18',
                'Mcp-Session-Id': sessionId
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "tools/list",
                id: `tools-list-${Date.now()}`
            })
        });

        const data = await response.json();
        if (data.result && data.result.tools) {
            discoveredTools = data.result.tools;
            displayTools(discoveredTools);
            populateToolSelect(discoveredTools);
        } else {
            throw new Error(data.error ? data.error.message : 'Failed to discover tools');
        }
    } catch (error) {
        console.error('Failed to discover tools:', error);
        showAlert('Failed to discover tools: ' + error.message, 'error');
        loadingElement.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Discovery Failed</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function displayTools(tools) {
    const tableBody = document.getElementById('toolsTableBody');
    
    if (tools.length === 0) {
        tableBody.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-tools"></i>
                <h3>No Tools Found</h3>
                <p>No tools were discovered from the registered servers</p>
            </div>
        `;
        return;
    }

    let html = '';
    tools.forEach(tool => {
        const paramCount = getParameterCount(tool.inputSchema);
        html += `
            <div class="server-row">
                <div class="col-name">
                    <div class="server-name">${tool.name}</div>
                    <div class="server-id">${tool._server_url || 'Unknown Server'}</div>
                </div>
                <div class="col-endpoint">
                    <div style="font-size: 0.875rem; color: var(--text-secondary);">
                        ${tool.description || 'No description available'}
                    </div>
                </div>
                <div class="col-capabilities">
                    <span class="capabilities-count">${paramCount}</span>
                </div>
                <div class="col-actions">
                    <div class="action-buttons">
                        <button class="action-btn" onclick="selectToolForTesting('${tool.name}')" title="Test Tool">
                            <i class="fas fa-play"></i>
                        </button>
                        <button class="action-btn" onclick="viewToolDetails('${tool.name}')" title="View Details">
                            <i class="fas fa-info-circle"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    });

    tableBody.innerHTML = html;
}

function getParameterCount(inputSchema) {
    if (!inputSchema || !inputSchema.properties) return 0;
    return Object.keys(inputSchema.properties).length;
}

function populateToolSelect(tools) {
    const select = document.getElementById('testToolSelect');
    select.innerHTML = '<option value="">Select a tool...</option>';

    tools.forEach(tool => {
        const option = document.createElement('option');
        option.value = tool.name;
        option.textContent = `${tool.name} - ${tool.description || 'No description'}`;
        select.appendChild(option);
    });

    select.addEventListener('change', function() {
        const selectedTool = discoveredTools.find(t => t.name === this.value);
        if (selectedTool) {
            displayToolParameters(selectedTool);
            document.getElementById('executeToolBtn').disabled = false;
        } else {
            document.getElementById('toolParameters').innerHTML = '';
            document.getElementById('executeToolBtn').disabled = true;
        }
    });
}

function selectToolForTesting(toolName) {
    // Switch to testing tab and select the tool
    switchTab('testing');
    document.getElementById('testToolSelect').value = toolName;
    document.getElementById('testToolSelect').dispatchEvent(new Event('change'));
}

function viewToolDetails(toolName) {
    const tool = discoveredTools.find(t => t.name === toolName);
    if (!tool) return;

    const detailsHtml = `
        <div class="tool-details">
            <div class="form-group">
                <label class="form-label">Tool Name</label>
                <input type="text" class="form-control" value="${tool.name}" readonly>
            </div>
            <div class="form-group">
                <label class="form-label">Description</label>
                <textarea class="form-control" rows="2" readonly>${tool.description || 'No description'}</textarea>
            </div>
            <div class="form-group">
                <label class="form-label">Server URL</label>
                <input type="text" class="form-control" value="${tool._server_url || 'Unknown'}" readonly>
            </div>
            <div class="form-group">
                <label class="form-label">Input Schema</label>
                <pre class="test-results">${JSON.stringify(tool.inputSchema, null, 2)}</pre>
            </div>
        </div>
    `;

    document.getElementById('toolDetailsContent').innerHTML = detailsHtml;
    document.getElementById('toolDetailsModal').style.display = 'block';
}

// Tool Testing
function displayToolParameters(tool) {
    const container = document.getElementById('toolParameters');
    const schema = tool.inputSchema;

    if (!schema || !schema.properties) {
        container.innerHTML = '<p class="text-muted">This tool requires no parameters.</p>';
        return;
    }

    let html = '<div class="form-row">';
    for (const [key, param] of Object.entries(schema.properties)) {
        const required = schema.required && schema.required.includes(key);
        const type = param.type || 'string';
        const description = param.description || '';

        html += `
            <div class="form-group">
                <label class="form-label">
                    ${key} ${required ? '<span style="color: var(--error-color);">*</span>' : ''}
                    <small class="text-muted">(${type})</small>
                </label>
                <input type="text" class="form-control" id="param-${key}" 
                       placeholder="${description}" ${required ? 'required' : ''}>
                ${description ? `<small class="text-muted">${description}</small>` : ''}
            </div>
        `;
    }
    html += '</div>';

    container.innerHTML = html;
}

async function executeTool() {
    const toolName = document.getElementById('testToolSelect').value;
    if (!toolName) return;

    const selectedTool = discoveredTools.find(t => t.name === toolName);
    if (!selectedTool) return;

    const executeBtn = document.getElementById('executeToolBtn');
    const originalText = executeBtn.innerHTML;
    executeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Executing...';
    executeBtn.disabled = true;

    // Collect parameters
    const params = {};
    const schema = selectedTool.inputSchema;

    if (schema && schema.properties) {
        for (const [key, param] of Object.entries(schema.properties)) {
            const element = document.getElementById(`param-${key}`);
            if (element && element.value) {
                let value = element.value;
                if (param.type === 'number') {
                    value = parseFloat(value);
                } else if (param.type === 'boolean') {
                    value = value.toLowerCase() === 'true';
                } else if (param.type === 'array' || param.type === 'object') {
                    try {
                        value = JSON.parse(value);
                    } catch (e) {
                        // Keep as string if parsing fails
                    }
                }
                params[key] = value;
            }
        }
    }

    try {
        // Step 1: Initialize MCP session for tool execution
        const initResponse = await fetch(MCP_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2025-06-18'
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "initialize",
                params: {
                    protocolVersion: "2025-06-18",
                    clientInfo: {
                        name: "mcp-portal-ui",
                        version: "1.0.0"
                    }
                },
                id: `init-exec-${Date.now()}`
            })
        });

        const initData = await initResponse.json();
        const sessionId = initResponse.headers.get('Mcp-Session-Id');

        if (!initData.result || !sessionId) {
            throw new Error('Failed to initialize MCP session for tool execution');
        }

        // Step 2: Send initialized notification
        await fetch(MCP_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2025-06-18',
                'Mcp-Session-Id': sessionId
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "notifications/initialized"
            })
        });

        // Step 3: Execute tool with session
        const response = await fetch(MCP_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2025-06-18',
                'Mcp-Session-Id': sessionId
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "tools/call",
                params: {
                    name: toolName,
                    arguments: params
                },
                id: `execution-${Date.now()}`
            })
        });

        if (response.headers.get('Content-Type')?.includes('text/event-stream')) {
            await handleStreamingResponse(response);
        } else {
            const data = await response.json();
            displayTestResults(data);
        }
    } catch (error) {
        console.error('Tool execution failed:', error);
        displayTestResults({ error: { message: error.message } });
    } finally {
        executeBtn.innerHTML = originalText;
        executeBtn.disabled = false;
    }
}

async function handleStreamingResponse(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let responses = [];

    const resultsContainer = document.getElementById('testResults');
    resultsContainer.style.display = 'block';
    resultsContainer.innerHTML = 'Streaming response...\n\n';

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
            const message = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);

            const lines = message.split('\n');
            let data = '';
            lines.forEach(line => {
                if (line.startsWith('data:')) {
                    data += line.substring(5).trim();
                }
            });

            if (data) {
                try {
                    const jsonData = JSON.parse(data);
                    responses.push(jsonData);
                    resultsContainer.innerHTML += '\n---\n' + JSON.stringify(jsonData, null, 2);
                    resultsContainer.scrollTop = resultsContainer.scrollHeight;
                } catch (e) {
                    console.error('Failed to parse streaming data:', e);
                }
            }
        }
    }
}

function displayTestResults(data) {
    const resultsContainer = document.getElementById('testResults');
    resultsContainer.style.display = 'block';
    resultsContainer.innerHTML = JSON.stringify(data, null, 2);
}

// Utility Functions
// Tool Capabilities
async function loadCapabilities() {
    const container = document.getElementById('capabilitiesContainer');
    container.innerHTML = '<div class="loading">Loading tool capabilities...</div>';

    try {
        // Step 1: Initialize MCP session
        const initResponse = await fetch(MCP_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2025-06-18'
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "initialize",
                params: {
                    protocolVersion: "2025-06-18",
                    clientInfo: {
                        name: "mcp-portal-ui",
                        version: "1.0.0"
                    }
                },
                id: `init-${Date.now()}`
            })
        });

        const initData = await initResponse.json();
        const sessionId = initResponse.headers.get('Mcp-Session-Id');

        if (!initData.result || !sessionId) {
            throw new Error('Failed to initialize MCP session');
        }

        // Step 2: Send initialized notification
        await fetch(MCP_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2025-06-18',
                'Mcp-Session-Id': sessionId
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "notifications/initialized"
            })
        });

        // Step 3: Get tools using existing endpoint
        const toolsResponse = await fetch(MCP_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2025-06-18',
                'Mcp-Session-Id': sessionId
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "tools/list",
                id: `tools-${Date.now()}`
            })
        });

        const toolsData = await toolsResponse.json();

        if (toolsData.result) {
            const tools = toolsData.result.tools || [];
            
            // Group tools by server URL
            const serverUrls = [...new Set(tools.map(tool => tool._server_url).filter(Boolean))];
            const capabilities = {};
            
            serverUrls.forEach(url => {
                const serverTools = tools.filter(tool => tool._server_url === url);
                if (serverTools.length > 0) {
                    const serverId = url.replace('http://', '').replace('https://', '').replace(/[^a-zA-Z0-9]/g, '_');
                    capabilities[serverId] = {
                        server_info: {
                            server_id: serverId,
                            name: url.replace('http://', '').replace('https://', ''),
                            url: url,
                            description: `MCP Server at ${url}`,
                            protocol_version: "2025-06-18"
                        },
                        tools: serverTools.map(tool => ({
                            name: tool.name,
                            description: tool.description,
                            input_schema: tool.inputSchema,
                            raw_json: tool,
                            parameter_count: Object.keys(tool.inputSchema?.properties || {}).length,
                            required_params: tool.inputSchema?.required || [],
                            discovery_timestamp: tool._discovery_timestamp,
                            server_url: tool._server_url
                        }))
                    };
                }
            });
            
            currentCapabilities = capabilities;
            displayCapabilities(currentCapabilities);
        } else {
            throw new Error('Failed to load tools');
        }
    } catch (error) {
        console.error('Failed to load capabilities:', error);
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Loading Failed</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function displayCapabilities(capabilities) {
    const container = document.getElementById('capabilitiesContainer');
    
    if (Object.keys(capabilities).length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-brain"></i>
                <h3>No Capabilities Found</h3>
                <p>No tool capabilities were discovered from the registered servers</p>
            </div>
        `;
        return;
    }

    let html = '';
    for (const [serverId, capabilityData] of Object.entries(capabilities)) {
        const server = capabilityData.server_info;
        const tools = capabilityData.tools;
        
        html += `
            <div class="capability-card">
                <div class="capability-card-header">
                    <div class="capability-card-title">${server.name}</div>
                    <div class="capability-card-info">${tools.length} tools</div>
                </div>
                <div style="margin-bottom: 1rem;">
                    <div style="font-size: 0.875rem; color: var(--text-secondary);">${server.description}</div>
                    <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">
                        <strong>URL:</strong> ${server.url}<br>
                        <strong>Protocol:</strong> ${server.protocol_version}
                    </div>
                </div>
                <div class="capability-tools">
                    <div class="capability-tools-header">Available Tools</div>
                    ${tools.map(tool => `
                        <div class="tool-capability-item" data-tool="${tool.name}">
                            <div class="tool-capability-header">
                                <div class="tool-capability-name">${tool.name}</div>
                                <div class="tool-capability-params">${tool.parameter_count} params</div>
                            </div>
                            <div class="tool-capability-description">${tool.description || 'No description'}</div>
                            <div class="tool-capability-actions">
                                <button class="btn btn-sm btn-outline" onclick="toggleRawJson('${serverId}-${tool.name}')">
                                    <i class="fas fa-code"></i>
                                    Raw JSON
                                </button>
                                <button class="btn btn-sm btn-primary" onclick="testToolFromCapabilities('${tool.name}')">
                                    <i class="fas fa-play"></i>
                                    Test
                                </button>
                            </div>
                            <div id="raw-${serverId}-${tool.name}" class="raw-json-viewer">
                                ${syntaxHighlight(JSON.stringify(tool.raw_json, null, 2))}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
}

function toggleRawJson(toolId) {
    const viewer = document.getElementById(`raw-${toolId}`);
    viewer.classList.toggle('show');
}

function testToolFromCapabilities(toolName) {
    // Switch to testing tab and select the tool
    switchTab('testing');
    document.getElementById('testToolSelect').value = toolName;
    document.getElementById('testToolSelect').dispatchEvent(new Event('change'));
}

function exportCapabilities() {
    if (Object.keys(currentCapabilities).length === 0) {
        showAlert('No capabilities to export. Please load capabilities first.', 'warning');
        return;
    }

    const dataStr = JSON.stringify(currentCapabilities, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(dataBlob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `mcp-tool-capabilities-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showAlert('Capabilities exported successfully!', 'success');
}

function filterCapabilities() {
    const searchTerm = document.getElementById('capabilitySearch').value.toLowerCase();
    const capabilityCards = document.querySelectorAll('.capability-card');
    
    capabilityCards.forEach(card => {
        const title = card.querySelector('.capability-card-title')?.textContent.toLowerCase() || '';
        const tools = Array.from(card.querySelectorAll('.tool-capability-name')).map(el => el.textContent.toLowerCase()).join(' ');
        const description = card.querySelector('.tool-capability-description')?.textContent.toLowerCase() || '';
        
        const matches = searchTerm === '' || title.includes(searchTerm) || tools.includes(searchTerm) || description.includes(searchTerm);
        card.style.display = matches ? 'block' : 'none';
    });
}

function syntaxHighlight(json) {
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        var cls = 'json-number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'json-key';
            } else {
                cls = 'json-string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'json-boolean';
        } else if (/null/.test(match)) {
            cls = 'json-null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
}

function refreshAll() {
    if (currentTab === 'servers') {
        loadServers();
    } else if (currentTab === 'tools') {
        discoverTools();
    } else if (currentTab === 'capabilities') {
        loadCapabilities();
    }
}

function showAlert(message, type = 'info') {
    // Create alert element
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()" style="float: right; background: none; border: none; font-size: 1.2rem; cursor: pointer;">&times;</button>
    `;

    // Insert at top of content area
    const contentArea = document.querySelector('.content-area');
    contentArea.insertBefore(alert, contentArea.firstChild);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alert.parentElement) {
            alert.remove();
        }
    }, 5000);
}

function hideModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Bulk operations
function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.server-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
}

function bulkDeleteServers() {
    const checkedBoxes = document.querySelectorAll('.server-checkbox:checked');
    if (checkedBoxes.length === 0) {
        showAlert('Please select servers to delete', 'warning');
        return;
    }

    if (!confirm(`Are you sure you want to delete ${checkedBoxes.length} selected server(s)?`)) {
        return;
    }

    // Delete each selected server
    checkedBoxes.forEach(async (checkbox) => {
        const serverId = checkbox.getAttribute('data-server-id');
        await deleteServer(serverId);
    });
}

// Search and filtering
function filterServers() {
    const searchTerm = document.getElementById('serverSearch').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value.toLowerCase();
    
    const serverRows = document.querySelectorAll('.server-row');
    
    serverRows.forEach(row => {
        const name = row.querySelector('.server-name')?.textContent.toLowerCase() || '';
        const url = row.querySelector('.endpoint-url')?.textContent.toLowerCase() || '';
        const status = row.querySelector('.status-badge')?.textContent.toLowerCase() || '';
        
        const matchesSearch = searchTerm === '' || name.includes(searchTerm) || url.includes(searchTerm);
        const matchesStatus = statusFilter === '' || status.includes(statusFilter);
        
        row.style.display = matchesSearch && matchesStatus ? 'flex' : 'none';
    });
}

function filterTools() {
    const searchTerm = document.getElementById('toolSearch').value.toLowerCase();
    
    const toolRows = document.querySelectorAll('#toolsTableBody .server-row');
    
    toolRows.forEach(row => {
        const name = row.querySelector('.server-name')?.textContent.toLowerCase() || '';
        const description = row.querySelector('.col-endpoint')?.textContent.toLowerCase() || '';
        
        const matches = searchTerm === '' || name.includes(searchTerm) || description.includes(searchTerm);
        row.style.display = matches ? 'flex' : 'none';
    });
}
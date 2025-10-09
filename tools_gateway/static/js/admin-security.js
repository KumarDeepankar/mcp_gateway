/**
 * Admin Security Management
 * OAuth Provider and RBAC Management
 */

// Global state
let currentUser = null;
let authToken = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Check for token in URL (from OAuth callback)
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (token) {
        authToken = token;
        localStorage.setItem('mcp_auth_token', token);
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    } else {
        authToken = localStorage.getItem('mcp_auth_token');
    }

    if (authToken) {
        await loadCurrentUser();
    }

    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    // OAuth Provider Management
    const oauthTab = document.querySelector('[data-tab="oauth"]');
    if (oauthTab) {
        oauthTab.addEventListener('click', () => loadOAuthProviders());
    }

    // RBAC Management
    const usersTab = document.querySelector('[data-tab="users"]');
    if (usersTab) {
        usersTab.addEventListener('click', () => {
            loadADConfig();
            loadADMappings();
            loadUsers();
        });
    }

    const rolesTab = document.querySelector('[data-tab="roles"]');
    if (rolesTab) {
        rolesTab.addEventListener('click', () => loadRoles());
    }

    // Audit Logs
    const auditTab = document.querySelector('[data-tab="audit"]');
    if (auditTab) {
        auditTab.addEventListener('click', () => loadAuditLogs());
    }
}

// Authentication Functions
async function loadCurrentUser() {
    try {
        const response = await fetch('/auth/user', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            currentUser = await response.json();
            updateUserInterface();
        } else {
            // Token invalid, clear and redirect to login
            localStorage.removeItem('mcp_auth_token');
            authToken = null;
            showLoginInterface();
        }
    } catch (error) {
        console.error('Error loading user:', error);
        showLoginInterface();
    }
}

function updateUserInterface() {
    const userInfo = document.getElementById('currentUserInfo');
    if (userInfo && currentUser) {
        userInfo.innerHTML = `
            <div class="user-badge">
                <i class="fas fa-user-circle"></i>
                <span>${currentUser.name || currentUser.email}</span>
                <span class="user-role">${currentUser.roles[0] || 'User'}</span>
            </div>
        `;
    }
}

function showLoginInterface() {
    // Show OAuth login options
    loadOAuthProviders();
}

async function initiateOAuthLogin(providerId) {
    try {
        const response = await fetch(`/auth/login?provider_id=${providerId}`, {
            method: 'POST'
        });

        if (response.ok) {
            const data = await response.json();
            // Redirect to OAuth provider
            window.location.href = data.url;
        } else {
            showNotification('Failed to initiate login', 'error');
        }
    } catch (error) {
        console.error('OAuth login error:', error);
        showNotification('Login error: ' + error.message, 'error');
    }
}

function logout() {
    localStorage.removeItem('mcp_auth_token');
    authToken = null;
    currentUser = null;
    window.location.href = '/auth/welcome';
}

// OAuth Provider Management

// Provider templates with pre-filled configurations
const PROVIDER_TEMPLATES = {
    google: {
        provider_id: 'google',
        provider_name: 'Google',
        authorize_url: 'https://accounts.google.com/o/oauth2/v2/auth',
        token_url: 'https://oauth2.googleapis.com/token',
        userinfo_url: 'https://www.googleapis.com/oauth2/v2/userinfo',
        scopes: ['openid', 'email', 'profile']
    },
    microsoft: {
        provider_id: 'microsoft',
        provider_name: 'Microsoft',
        authorize_url: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
        token_url: 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        userinfo_url: 'https://graph.microsoft.com/v1.0/me',
        scopes: ['openid', 'email', 'profile']
    },
    github: {
        provider_id: 'github',
        provider_name: 'GitHub',
        authorize_url: 'https://github.com/login/oauth/authorize',
        token_url: 'https://github.com/login/oauth/access_token',
        userinfo_url: 'https://api.github.com/user',
        scopes: ['read:user', 'user:email']
    }
};

// Current scopes array
let currentScopes = ['openid', 'email', 'profile'];

async function loadOAuthProviders() {
    try {
        const response = await fetch('/auth/providers');
        const data = await response.json();

        displayOAuthProviders(data.providers);
    } catch (error) {
        console.error('Error loading OAuth providers:', error);
    }
}

function displayOAuthProviders(providers) {
    const container = document.getElementById('oauthProvidersContainer');
    if (!container) return;

    // Always show management interface in the OAuth Providers tab
    // (This is the OAuth management section, not the login page)
    if (!authToken && providers.length > 0) {
        // Providers exist but user not logged in - show minimal interface with login option
        container.innerHTML = `
            <div class="alert alert-info" style="margin-bottom: 20px;">
                <i class="fas fa-info-circle"></i>
                <strong>Authentication Required</strong>
                <p>Please sign in to manage OAuth providers.</p>
            </div>
            <div class="login-container">
                <h3>Sign In</h3>
                <p>Choose your authentication provider:</p>
                <div class="oauth-providers">
                    ${providers.map(p => `
                        <button class="btn btn-provider" onclick="initiateOAuthLogin('${p.provider_id}')">
                            <i class="fab fa-${p.provider_id}"></i>
                            Sign in with ${p.provider_name}
                        </button>
                    `).join('')}
                </div>
            </div>
            <div class="alert alert-warning" style="margin-top: 20px;">
                <i class="fas fa-shield-alt"></i>
                <strong>Want to add or manage providers?</strong>
                <p>First-time setup allows adding providers without login. If you need to manage existing providers, please sign in as an administrator.</p>
            </div>
        `;
    } else if (!authToken && providers.length === 0) {
        // No providers and not logged in - allow first-time setup
        container.innerHTML = `
            <div class="alert alert-warning" style="margin-bottom: 20px;">
                <i class="fas fa-exclamation-triangle"></i>
                <strong>No OAuth providers configured</strong>
                <p>Configure your first OAuth provider to enable authentication. This is a one-time setup.</p>
            </div>
            <div class="toolbar">
                <button class="btn btn-primary" onclick="showAddOAuthProviderModal()">
                    <i class="fas fa-plus"></i> Add OAuth Provider
                </button>
                <button class="btn btn-outline" onclick="showOAuthSetupGuide()">
                    <i class="fas fa-book"></i> Setup Guide
                </button>
            </div>
            <div class="alert alert-info" style="margin-top: 20px;">
                <i class="fas fa-info-circle"></i>
                <strong>First-time setup:</strong>
                <p>Add Google, Microsoft, or GitHub authentication to enable user login. After adding a provider, you'll be able to sign in and manage additional settings.</p>
            </div>
        `;
    } else {
        // Show management interface
        container.innerHTML = `
            <div class="toolbar">
                <button class="btn btn-primary" onclick="showAddOAuthProviderModal()">
                    <i class="fas fa-plus"></i> Add OAuth Provider
                </button>
                <button class="btn btn-outline" onclick="showOAuthSetupGuide()">
                    <i class="fas fa-book"></i> Setup Guide
                </button>
                <button class="btn btn-outline" onclick="loadOAuthProviders()">
                    <i class="fas fa-sync"></i> Refresh
                </button>
            </div>
            ${providers.length === 0 ? `
                <div class="alert alert-info" style="margin-top: 20px;">
                    <i class="fas fa-info-circle"></i>
                    <strong>No providers configured yet</strong>
                    <p>Click "Add OAuth Provider" to configure Google, Microsoft, or GitHub authentication.</p>
                </div>
            ` : `
                <div class="providers-list">
                    ${providers.map(p => `
                        <div class="provider-card">
                            <div class="provider-icon">
                                <i class="fab fa-${p.provider_id}"></i>
                            </div>
                            <div class="provider-info">
                                <h4>${p.provider_name}</h4>
                                <p>Provider ID: ${p.provider_id}</p>
                                <p>Scopes: ${p.scopes.join(', ')}</p>
                                <span class="badge ${p.enabled ? 'badge-success' : 'badge-danger'}">
                                    ${p.enabled ? 'Enabled' : 'Disabled'}
                                </span>
                            </div>
                            <div class="provider-actions">
                                <button class="btn btn-sm btn-danger" onclick="removeOAuthProvider('${p.provider_id}')">
                                    <i class="fas fa-trash"></i> Remove
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `}
        `;
    }
}

// Show Add OAuth Provider Modal
function showAddOAuthProviderModal() {
    // Reset form
    document.getElementById('oauthProviderForm').reset();
    document.getElementById('providerTemplate').value = '';
    currentScopes = ['openid', 'email', 'profile'];
    updateScopesDisplay();

    showModal('addOAuthProviderModal');
}

// Close OAuth Modal
function closeOAuthModal() {
    closeModal('addOAuthProviderModal');
}

// Load Provider Template
function loadProviderTemplate() {
    const templateSelect = document.getElementById('providerTemplate');
    const template = PROVIDER_TEMPLATES[templateSelect.value];

    if (template) {
        document.getElementById('providerId').value = template.provider_id;
        document.getElementById('providerName').value = template.provider_name;
        document.getElementById('authorizeUrl').value = template.authorize_url;
        document.getElementById('tokenUrl').value = template.token_url;
        document.getElementById('userinfoUrl').value = template.userinfo_url;

        currentScopes = [...template.scopes];
        updateScopesDisplay();

        showNotification(`Loaded ${template.provider_name} template. Add your Client ID and Client Secret.`, 'info');
    } else {
        // Clear form for custom provider
        document.getElementById('providerId').value = '';
        document.getElementById('providerName').value = '';
        document.getElementById('authorizeUrl').value = '';
        document.getElementById('tokenUrl').value = '';
        document.getElementById('userinfoUrl').value = '';
        currentScopes = [];
        updateScopesDisplay();
    }
}

// Scopes Management
function updateScopesDisplay() {
    const container = document.getElementById('scopesContainer');
    container.innerHTML = currentScopes.map(scope => `
        <span class="tag">${scope} <button type="button" onclick="removeScope('${scope}')">×</button></span>
    `).join('');
}

function addScope() {
    const input = document.getElementById('newScope');
    const scope = input.value.trim();

    if (scope && !currentScopes.includes(scope)) {
        currentScopes.push(scope);
        updateScopesDisplay();
        input.value = '';
    } else if (currentScopes.includes(scope)) {
        showNotification('Scope already added', 'warning');
    }
}

function removeScope(scope) {
    currentScopes = currentScopes.filter(s => s !== scope);
    updateScopesDisplay();
}

// Save OAuth Provider
async function saveOAuthProvider() {
    const providerId = document.getElementById('providerId').value.trim();
    const providerName = document.getElementById('providerName').value.trim();
    const clientId = document.getElementById('clientId').value.trim();
    const clientSecret = document.getElementById('clientSecret').value.trim();
    const authorizeUrl = document.getElementById('authorizeUrl').value.trim();
    const tokenUrl = document.getElementById('tokenUrl').value.trim();
    const userinfoUrl = document.getElementById('userinfoUrl').value.trim();
    const enabled = document.getElementById('providerEnabled').checked;

    // Validation
    if (!providerId || !providerName || !clientId || !clientSecret ||
        !authorizeUrl || !tokenUrl || !userinfoUrl) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }

    // Validate provider ID format (lowercase, no spaces)
    if (!/^[a-z0-9_-]+$/.test(providerId)) {
        showNotification('Provider ID must be lowercase letters, numbers, hyphens, or underscores only', 'error');
        return;
    }

    if (currentScopes.length === 0) {
        showNotification('Please add at least one scope', 'error');
        return;
    }

    const providerData = {
        provider_id: providerId,
        client_id: clientId,
        client_secret: clientSecret,
        provider_name: providerName,
        authorize_url: authorizeUrl,
        token_url: tokenUrl,
        userinfo_url: userinfoUrl,
        scopes: currentScopes,
        enabled: enabled
    };

    try {
        await addOAuthProvider(providerData);
    } catch (error) {
        console.error('Error saving provider:', error);
    }
}

// Show OAuth Setup Guide
function showOAuthSetupGuide() {
    showModal('oauthSetupGuideModal');
}

async function addOAuthProvider(providerData) {
    try {
        const headers = {
            'Content-Type': 'application/json'
        };

        // Only add auth token if we have one
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }

        const response = await fetch('/admin/oauth/providers', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(providerData)
        });

        if (response.ok) {
            showNotification('OAuth provider added successfully! You can now sign in with this provider.', 'success');
            loadOAuthProviders();
            closeModal('addOAuthProviderModal');
        } else {
            const error = await response.json();
            showNotification('Failed to add provider: ' + (error.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error adding OAuth provider:', error);
        showNotification('Error adding provider: ' + error.message, 'error');
    }
}

async function removeOAuthProvider(providerId) {
    if (!confirm('Are you sure you want to remove this OAuth provider?')) return;

    try {
        const response = await fetch(`/admin/oauth/providers/${providerId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            showNotification('OAuth provider removed', 'success');
            loadOAuthProviders();
        } else {
            showNotification('Failed to remove provider', 'error');
        }
    } catch (error) {
        console.error('Error removing provider:', error);
    }
}

// User Management (RBAC)
async function loadUsers() {
    const container = document.getElementById('usersContainer');

    // Check if user is authenticated
    if (!authToken) {
        container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i>
                <strong>Authentication Required</strong>
                <p>Please sign in to view and manage users.</p>
            </div>
        `;
        return;
    }

    try {
        const response = await fetch('/admin/users', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            displayUsers(data.users);
        } else if (response.status === 403) {
            container.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-lock"></i>
                    <strong>Access Restricted</strong>
                    <p>You don't have permission to view users. Please contact your administrator for USER_VIEW permission.</p>
                </div>
            `;
        } else if (response.status === 401) {
            container.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i>
                    <strong>Session Expired</strong>
                    <p>Your session has expired. Please sign in again.</p>
                </div>
            `;
            // Clear invalid token
            localStorage.removeItem('mcp_auth_token');
            authToken = null;
        } else {
            container.innerHTML = `
                <div class="alert alert-error">
                    <i class="fas fa-exclamation-circle"></i>
                    <strong>Error Loading Users</strong>
                    <p>Failed to load user list. Please try again.</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading users:', error);
        container.innerHTML = `
            <div class="alert alert-error">
                <i class="fas fa-exclamation-circle"></i>
                <strong>Network Error</strong>
                <p>Could not connect to server. Please check your connection.</p>
            </div>
        `;
    }
}

function displayUsers(users) {
    const container = document.getElementById('usersContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="toolbar">
            <button class="btn btn-primary" onclick="showAddUserModal()">
                <i class="fas fa-user-plus"></i> Add User
            </button>
            <button class="btn btn-outline" onclick="showADSyncModal()">
                <i class="fas fa-sync"></i> Sync from AD
            </button>
            <button class="btn btn-outline" onclick="loadUsers()">
                <i class="fas fa-refresh"></i> Refresh
            </button>
        </div>
        <table class="admin-table" style="margin-top: 15px;">
            <thead>
                <tr>
                    <th>Email</th>
                    <th>Name</th>
                    <th>Provider</th>
                    <th>Roles</th>
                    <th>Status</th>
                    <th>Last Login</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${users.length === 0 ? `
                    <tr>
                        <td colspan="7" style="text-align: center; padding: 40px;">
                            <i class="fas fa-users" style="font-size: 48px; color: #ccc;"></i>
                            <p style="margin-top: 20px; color: #999;">No users yet. Add users manually or sync from Active Directory.</p>
                        </td>
                    </tr>
                ` : users.map(u => `
                    <tr>
                        <td>${u.email}</td>
                        <td>${u.name || '-'}</td>
                        <td><span class="badge">${u.provider || 'local'}</span></td>
                        <td>${u.roles.join(', ')}</td>
                        <td>
                            <span class="badge ${u.enabled ? 'badge-success' : 'badge-danger'}">
                                ${u.enabled ? 'Active' : 'Disabled'}
                            </span>
                        </td>
                        <td>${u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}</td>
                        <td>
                            <button class="btn btn-sm" onclick="manageUserRoles('${u.user_id}', '${u.email}')">
                                <i class="fas fa-user-cog"></i> Manage Roles
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function manageUserRoles(userId, userEmail) {
    // Load available roles
    const rolesResponse = await fetch('/admin/roles', {
        headers: { 'Authorization': `Bearer ${authToken}` }
    });
    const rolesData = await rolesResponse.json();

    // Show modal with role assignment
    showModal('userRolesModal', {
        userId: userId,
        userEmail: userEmail,
        availableRoles: rolesData.roles
    });
}

async function assignRole(userId, roleId) {
    try {
        const response = await fetch(`/admin/users/${userId}/roles`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ role_id: roleId })
        });

        if (response.ok) {
            showNotification('Role assigned successfully', 'success');
            loadUsers();
        } else {
            showNotification('Failed to assign role', 'error');
        }
    } catch (error) {
        console.error('Error assigning role:', error);
    }
}

// Role Management
async function loadRoles() {
    const container = document.getElementById('rolesContainer');

    // Check if user is authenticated
    if (!authToken) {
        container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i>
                <strong>Authentication Required</strong>
                <p>Please sign in to view and manage roles.</p>
            </div>
        `;
        return;
    }

    try {
        const response = await fetch('/admin/roles', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            displayRoles(data.roles);
        } else if (response.status === 403) {
            container.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-lock"></i>
                    <strong>Access Restricted</strong>
                    <p>You don't have permission to view roles. Please contact your administrator for ROLE_VIEW permission.</p>
                </div>
            `;
        } else if (response.status === 401) {
            container.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i>
                    <strong>Session Expired</strong>
                    <p>Your session has expired. Please sign in again.</p>
                </div>
            `;
            localStorage.removeItem('mcp_auth_token');
            authToken = null;
        } else {
            container.innerHTML = `
                <div class="alert alert-error">
                    <i class="fas fa-exclamation-circle"></i>
                    <strong>Error Loading Roles</strong>
                    <p>Failed to load roles list. Please try again.</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading roles:', error);
        container.innerHTML = `
            <div class="alert alert-error">
                <i class="fas fa-exclamation-circle"></i>
                <strong>Network Error</strong>
                <p>Could not connect to server. Please check your connection.</p>
            </div>
        `;
    }
}

function displayRoles(roles) {
    const container = document.getElementById('rolesContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="toolbar">
            <button class="btn btn-primary" onclick="showCreateRoleModal()">
                <i class="fas fa-plus"></i> Create Role
            </button>
        </div>
        <div class="roles-grid">
            ${roles.map(r => `
                <div class="role-card ${r.is_system ? 'system-role' : ''}">
                    <div class="role-header">
                        <h4>${r.role_name}</h4>
                        ${r.is_system ? '<span class="badge badge-info">System</span>' : ''}
                    </div>
                    <p class="role-description">${r.description}</p>
                    <div class="role-stats">
                        <span><i class="fas fa-users"></i> ${r.user_count} users</span>
                        <span><i class="fas fa-key"></i> ${r.permissions.length} permissions</span>
                    </div>
                    <div class="role-permissions">
                        ${r.permissions.slice(0, 5).map(p => `<span class="permission-badge">${p}</span>`).join('')}
                        ${r.permissions.length > 5 ? `<span class="more">+${r.permissions.length - 5} more</span>` : ''}
                    </div>
                    ${!r.is_system ? `
                        <button class="btn btn-sm btn-danger" onclick="deleteRole('${r.role_id}')">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                    ` : ''}
                </div>
            `).join('')}
        </div>
    `;
}

// Audit Logs
async function loadAuditLogs() {
    try {
        const response = await fetch('/admin/audit/events?limit=100', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            displayAuditLogs(data.events);
        }

        // Also load statistics
        loadAuditStatistics();
    } catch (error) {
        console.error('Error loading audit logs:', error);
    }
}

function displayAuditLogs(events) {
    const container = document.getElementById('auditLogsContainer');
    if (!container) return;

    container.innerHTML = `
        <table class="admin-table">
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Event Type</th>
                    <th>User</th>
                    <th>Action</th>
                    <th>Severity</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${events.map(e => `
                    <tr class="${e.success ? '' : 'event-failed'}">
                        <td>${new Date(e.timestamp).toLocaleString()}</td>
                        <td><code>${e.event_type}</code></td>
                        <td>${e.user_email || 'System'}</td>
                        <td>${e.action || '-'}</td>
                        <td>
                            <span class="badge badge-${getSeverityClass(e.severity)}">
                                ${e.severity}
                            </span>
                        </td>
                        <td>
                            <i class="fas fa-${e.success ? 'check text-success' : 'times text-danger'}"></i>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function loadAuditStatistics() {
    try {
        const response = await fetch('/admin/audit/statistics?hours=24', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            const stats = await response.json();
            displayAuditStatistics(stats);
        }
    } catch (error) {
        console.error('Error loading audit statistics:', error);
    }
}

function displayAuditStatistics(stats) {
    const container = document.getElementById('auditStatsContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">${stats.total_events}</div>
                <div class="stat-label">Total Events (24h)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.severity_counts.error || 0}</div>
                <div class="stat-label">Errors</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.severity_counts.warning || 0}</div>
                <div class="stat-label">Warnings</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.top_users.length}</div>
                <div class="stat-label">Active Users</div>
            </div>
        </div>
    `;
}

// Utility Functions
function getSeverityClass(severity) {
    const map = {
        'info': 'info',
        'warning': 'warning',
        'error': 'danger',
        'critical': 'danger'
    };
    return map[severity] || 'secondary';
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `toast toast-${type}`;
    notification.innerHTML = `
        <div class="toast-content">
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${message}</span>
        </div>
    `;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${getNotificationColor(type)};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
        min-width: 300px;
        max-width: 500px;
        font-family: 'Inter', sans-serif;
    `;

    document.body.appendChild(notification);

    // Auto-remove after 4 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 4000);
}

function getNotificationIcon(type) {
    const icons = {
        'success': 'check-circle',
        'error': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

function getNotificationColor(type) {
    const colors = {
        'success': '#10b981',
        'error': '#ef4444',
        'warning': '#f59e0b',
        'info': '#3b82f6'
    };
    return colors[type] || '#3b82f6';
}

// Add CSS animations for notifications
if (!document.getElementById('toast-animations')) {
    const style = document.createElement('style');
    style.id = 'toast-animations';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
        .toast-content {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .toast-content i {
            font-size: 20px;
        }
    `;
    document.head.appendChild(style);
}

function showModal(modalId, data) {
    // Modal management
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

// ==========================================
// User Management Functions
// ==========================================

// Show Add User Modal
function showAddUserModal() {
    // Load available roles first
    loadRolesForUserModal();
    showModal('addUserModal');
}

// Load roles for the Add User Modal
async function loadRolesForUserModal() {
    try {
        const response = await fetch('/admin/roles', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            const rolesSelect = document.getElementById('userRoles');

            rolesSelect.innerHTML = data.roles.map(role => `
                <label class="checkbox-item">
                    <input type="checkbox" name="roles" value="${role.role_id}">
                    <span>${role.role_name}</span>
                    <small>${role.description}</small>
                </label>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading roles:', error);
    }
}

// Save New User
async function saveNewUser() {
    const email = document.getElementById('userName').value.trim();
    const name = document.getElementById('userDisplayName').value.trim();
    const password = document.getElementById('userPassword').value;

    // Get selected roles
    const selectedRoles = Array.from(document.querySelectorAll('#userRoles input[name="roles"]:checked'))
        .map(cb => cb.value);

    // Validation
    if (!email || !password) {
        showNotification('Email and password are required', 'error');
        return;
    }

    if (selectedRoles.length === 0) {
        showNotification('Please select at least one role', 'error');
        return;
    }

    try {
        const response = await fetch('/admin/users', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email,
                name: name,
                password: password,
                roles: selectedRoles,
                provider: 'local'
            })
        });

        if (response.ok) {
            showNotification('User added successfully', 'success');
            closeModal('addUserModal');
            loadUsers();
        } else {
            const error = await response.json();
            showNotification('Failed to add user: ' + (error.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error adding user:', error);
        showNotification('Error adding user: ' + error.message, 'error');
    }
}

// ==========================================
// Role Management Functions
// ==========================================

// Show Create Role Modal
function showCreateRoleModal() {
    loadPermissionsGrid();
    showModal('createRoleModal');
}

// Load all available permissions into the grid
async function loadPermissionsGrid() {
    const permissionsGrid = document.getElementById('permissionsGrid');

    // All available permissions (16 total)
    const allPermissions = [
        { id: 'SERVER_READ', name: 'Server Read', description: 'View MCP servers and configurations' },
        { id: 'SERVER_WRITE', name: 'Server Write', description: 'Add, modify, or remove MCP servers' },
        { id: 'TOOL_EXECUTE', name: 'Tool Execute', description: 'Execute tools from MCP servers' },
        { id: 'RESOURCE_READ', name: 'Resource Read', description: 'Access resources from MCP servers' },
        { id: 'PROMPT_READ', name: 'Prompt Read', description: 'View available prompts' },
        { id: 'PROMPT_EXECUTE', name: 'Prompt Execute', description: 'Execute prompts' },
        { id: 'CONFIG_READ', name: 'Config Read', description: 'View gateway configuration' },
        { id: 'CONFIG_WRITE', name: 'Config Write', description: 'Modify gateway configuration' },
        { id: 'USER_READ', name: 'User Read', description: 'View users and their information' },
        { id: 'USER_WRITE', name: 'User Write', description: 'Add, modify, or remove users' },
        { id: 'ROLE_READ', name: 'Role Read', description: 'View roles and permissions' },
        { id: 'ROLE_WRITE', name: 'Role Write', description: 'Create, modify, or delete roles' },
        { id: 'AUDIT_READ', name: 'Audit Read', description: 'View audit logs and statistics' },
        { id: 'OAUTH_MANAGE', name: 'OAuth Manage', description: 'Manage OAuth providers' },
        { id: 'ADMIN', name: 'Admin', description: 'Full administrative access' },
        { id: 'SYSTEM', name: 'System', description: 'System-level operations (reserved)' }
    ];

    permissionsGrid.innerHTML = allPermissions.map(perm => `
        <label class="checkbox-item">
            <input type="checkbox" name="permissions" value="${perm.id}">
            <div>
                <strong>${perm.name}</strong>
                <small>${perm.description}</small>
            </div>
        </label>
    `).join('');
}

// Save New Role
async function saveNewRole() {
    const roleName = document.getElementById('roleName').value.trim();
    const description = document.getElementById('roleDescription').value.trim();

    // Get selected permissions
    const selectedPermissions = Array.from(document.querySelectorAll('#permissionsGrid input[name="permissions"]:checked'))
        .map(cb => cb.value);

    // Validation
    if (!roleName) {
        showNotification('Role name is required', 'error');
        return;
    }

    if (selectedPermissions.length === 0) {
        showNotification('Please select at least one permission', 'error');
        return;
    }

    try {
        const response = await fetch('/admin/roles', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                role_name: roleName,
                description: description,
                permissions: selectedPermissions
            })
        });

        if (response.ok) {
            showNotification('Role created successfully', 'success');
            closeModal('createRoleModal');
            loadRoles();
        } else {
            const error = await response.json();
            showNotification('Failed to create role: ' + (error.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error creating role:', error);
        showNotification('Error creating role: ' + error.message, 'error');
    }
}

// Delete Role
async function deleteRole(roleId) {
    if (!confirm('Are you sure you want to delete this role? Users with this role will lose their assigned permissions.')) {
        return;
    }

    try {
        const response = await fetch(`/admin/roles/${roleId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            showNotification('Role deleted successfully', 'success');
            loadRoles();
        } else {
            const error = await response.json();
            showNotification('Failed to delete role: ' + (error.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error deleting role:', error);
        showNotification('Error deleting role: ' + error.message, 'error');
    }
}

// ==========================================
// Active Directory Integration Functions
// ==========================================

// Global AD config storage
let adConfigData = {
    server: '',
    port: 389,
    base_dn: '',
    bind_dn: '',
    bind_password: '',
    group_filter: '(objectClass=organizationalUnit)',
    use_ssl: false
};

// Test AD Connection
async function testADConnection() {
    const server = document.getElementById('adConfigServer').value.trim();
    const port = parseInt(document.getElementById('adConfigPort').value);
    const baseDN = document.getElementById('adConfigBaseDN').value.trim();
    const bindDN = document.getElementById('adConfigBindDN').value.trim();
    const bindPassword = document.getElementById('adConfigPassword').value;
    const useSSL = document.getElementById('adConfigUseSSL').checked;

    if (!server || !baseDN || !bindDN || !bindPassword) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }

    const statusDiv = document.getElementById('adConfigStatus');
    statusDiv.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Testing connection...</div>';

    try {
        const response = await fetch('/admin/ad/query-groups', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                server: server,
                port: port,
                bind_dn: bindDN,
                bind_password: bindPassword,
                base_dn: baseDN,
                group_filter: '(objectClass=organizationalUnit)',  // Standard LDAP filter for organizational units
                use_ssl: useSSL
            })
        });

        if (response.ok) {
            statusDiv.innerHTML = `
                <div class="alert alert-success">
                    <i class="fas fa-check-circle"></i>
                    <strong>Connection Successful!</strong>
                    <p>Successfully connected to Active Directory server.</p>
                </div>
            `;
            showNotification('AD connection test successful', 'success');
        } else {
            const error = await response.json();
            statusDiv.innerHTML = `
                <div class="alert alert-error">
                    <i class="fas fa-exclamation-circle"></i>
                    <strong>Connection Failed</strong>
                    <p>${error.detail || 'Could not connect to Active Directory'}</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error testing AD connection:', error);
        statusDiv.innerHTML = `
            <div class="alert alert-error">
                <i class="fas fa-exclamation-circle"></i>
                <strong>Connection Error</strong>
                <p>${error.message}</p>
            </div>
        `;
    }
}

// Save AD Configuration
async function saveADConfig() {
    const server = document.getElementById('adConfigServer').value.trim();
    const port = parseInt(document.getElementById('adConfigPort').value);
    const baseDN = document.getElementById('adConfigBaseDN').value.trim();
    const bindDN = document.getElementById('adConfigBindDN').value.trim();
    const bindPassword = document.getElementById('adConfigPassword').value;
    const groupFilter = document.getElementById('adConfigGroupFilter').value.trim();
    const useSSL = document.getElementById('adConfigUseSSL').checked;

    if (!server || !baseDN || !bindDN || !bindPassword) {
        showNotification('Please fill in all required fields', 'error');
        return;
    }

    // Store configuration in memory (including password for session)
    adConfigData = {
        server: server,
        port: port,
        base_dn: baseDN,
        bind_dn: bindDN,
        bind_password: bindPassword,
        group_filter: groupFilter,
        use_ssl: useSSL
    };

    try {
        // Save to database (password excluded for security)
        const headers = {
            'Content-Type': 'application/json'
        };

        // Only add auth token if we have one
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }

        const response = await fetch('/admin/ad/config', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                server: server,
                port: port,
                base_dn: baseDN,
                bind_dn: bindDN,
                group_filter: groupFilter,
                use_ssl: useSSL
            })
        });

        if (response.ok) {
            showNotification('AD configuration saved to database successfully', 'success');
            // Load existing mappings
            loadADMappings();
        } else {
            const error = await response.json();
            showNotification('Failed to save AD configuration: ' + (error.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error saving AD configuration:', error);
        showNotification('Error saving AD configuration: ' + error.message, 'error');
    }
}

// Load AD Configuration from database
async function loadADConfig() {
    try {
        const headers = {};

        // Only add auth token if we have one
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }

        const response = await fetch('/admin/ad/config', {
            headers: headers
        });

        if (response.ok) {
            const data = await response.json();
            const config = data.config;

            if (config && Object.keys(config).length > 0) {
                document.getElementById('adConfigServer').value = config.server || '';
                document.getElementById('adConfigPort').value = config.port || 389;
                document.getElementById('adConfigBaseDN').value = config.base_dn || '';
                document.getElementById('adConfigBindDN').value = config.bind_dn || '';
                document.getElementById('adConfigGroupFilter').value = config.group_filter || '(objectClass=organizationalUnit)';
                document.getElementById('adConfigUseSSL').checked = config.use_ssl || false;

                // Update adConfigData (password needs to be re-entered)
                adConfigData = { ...config, bind_password: '' };

                console.log('AD configuration loaded from database');
            }
        } else if (response.status !== 403 && response.status !== 401) {
            console.error('Failed to load AD configuration');
        }
    } catch (error) {
        console.error('Error loading AD configuration:', error);
    }
}

// Query AD Groups from saved configuration
async function queryADGroupsFromConfig() {
    // Get current form values
    const server = document.getElementById('adConfigServer').value.trim();
    const port = parseInt(document.getElementById('adConfigPort').value);
    const baseDN = document.getElementById('adConfigBaseDN').value.trim();
    const bindDN = document.getElementById('adConfigBindDN').value.trim();
    const bindPassword = document.getElementById('adConfigPassword').value;
    const groupFilter = document.getElementById('adConfigGroupFilter').value.trim();
    const useSSL = document.getElementById('adConfigUseSSL').checked;

    if (!server || !baseDN || !bindDN || !bindPassword) {
        showNotification('Please fill in and save AD configuration first', 'error');
        return;
    }

    // Update adConfigData
    adConfigData = {
        server: server,
        port: port,
        base_dn: baseDN,
        bind_dn: bindDN,
        bind_password: bindPassword,
        group_filter: groupFilter,
        use_ssl: useSSL
    };

    // Show modal with results
    showADSyncModal();
    queryADGroups();
}

// Load AD Group Mappings
async function loadADMappings() {
    const container = document.getElementById('adMappingsContainer');

    // Check if user is authenticated
    if (!authToken) {
        container.innerHTML = '<p class="text-muted">Sign in to view AD group mappings.</p>';
        return;
    }

    try {
        const response = await fetch('/admin/ad/group-mappings', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            displayADMappings(data.mappings);
        } else if (response.status === 403 || response.status === 401) {
            container.innerHTML = '<p class="text-muted">You don\'t have permission to view AD mappings.</p>';
        } else {
            container.innerHTML = '<p class="text-muted">No AD group mappings configured.</p>';
        }
    } catch (error) {
        console.error('Error loading AD mappings:', error);
        container.innerHTML = '<p class="text-muted">No AD group mappings configured. Query groups and map them to roles.</p>';
    }
}

// Display AD Mappings
async function displayADMappings(mappings) {
    const container = document.getElementById('adMappingsContainer');

    if (!mappings || mappings.length === 0) {
        container.innerHTML = '<p class="text-muted">No AD group mappings configured. Query groups and map them to roles.</p>';
        return;
    }

    // Load roles to display role names
    let rolesMap = {};
    try {
        const response = await fetch('/admin/roles', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            rolesMap = Object.fromEntries(data.roles.map(r => [r.role_id, r.role_name]));
        }
    } catch (error) {
        console.error('Error loading roles:', error);
    }

    container.innerHTML = `
        <table class="admin-table">
            <thead>
                <tr>
                    <th>AD Group</th>
                    <th>Mapped Role</th>
                    <th>Auto-Sync</th>
                    <th>Last Sync</th>
                    <th>Synced Users</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${mappings.map(m => `
                    <tr>
                        <td><code style="font-size: 11px;">${m.group_dn}</code></td>
                        <td><span class="badge">${rolesMap[m.role_id] || m.role_id}</span></td>
                        <td>
                            <span class="badge ${m.auto_sync ? 'badge-success' : 'badge-secondary'}">
                                ${m.auto_sync ? 'Enabled' : 'Disabled'}
                            </span>
                        </td>
                        <td>${m.last_sync ? new Date(m.last_sync).toLocaleString() : 'Never'}</td>
                        <td>${m.synced_users || 0} users</td>
                        <td>
                            <button class="btn btn-sm btn-danger" onclick="deleteADMapping('${m.mapping_id}')">
                                <i class="fas fa-trash"></i> Remove
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Delete AD Mapping
async function deleteADMapping(mappingId) {
    if (!confirm('Are you sure you want to remove this AD group mapping?')) {
        return;
    }

    try {
        const response = await fetch(`/admin/ad/group-mappings/${mappingId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            showNotification('AD mapping removed successfully', 'success');
            loadADMappings();
        } else {
            showNotification('Failed to remove mapping', 'error');
        }
    } catch (error) {
        console.error('Error removing mapping:', error);
        showNotification('Error removing mapping: ' + error.message, 'error');
    }
}

// Show AD Sync Modal
function showADSyncModal() {
    // Pre-fill form from saved config
    if (adConfigData.server) {
        document.getElementById('adServer').value = adConfigData.server;
        document.getElementById('adPort').value = adConfigData.port;
        document.getElementById('adBindDN').value = adConfigData.bind_dn;
        document.getElementById('adPassword').value = adConfigData.bind_password;
        document.getElementById('adBaseDN').value = adConfigData.base_dn;
        document.getElementById('adGroupFilter').value = adConfigData.group_filter;
    }

    // Clear previous results
    document.getElementById('adGroupsResult').innerHTML = '';
    showModal('adSyncModal');
}

// Query Active Directory Groups
async function queryADGroups() {
    const adServer = document.getElementById('adServer').value.trim();
    const adPort = document.getElementById('adPort').value;
    const bindDN = document.getElementById('adBindDN').value.trim();
    const bindPassword = document.getElementById('adBindPassword').value;
    const baseDN = document.getElementById('adBaseDN').value.trim();
    const groupFilter = document.getElementById('adGroupFilter').value.trim();

    // Validation
    if (!adServer || !bindDN || !bindPassword || !baseDN) {
        showNotification('Please fill in all required AD connection fields', 'error');
        return;
    }

    const resultDiv = document.getElementById('adGroupsResult');
    resultDiv.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Querying Active Directory...</div>';

    try {
        const response = await fetch('/admin/ad/query-groups', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                server: adServer,
                port: parseInt(adPort),
                bind_dn: bindDN,
                bind_password: bindPassword,
                base_dn: baseDN,
                group_filter: groupFilter
            })
        });

        if (response.ok) {
            const data = await response.json();
            displayADGroups(data.groups);

            // Store fetched groups locally
            if (typeof storeFetchedADData === 'function') {
                storeFetchedADData(data.groups, []);
            }
        } else {
            const error = await response.json();
            resultDiv.innerHTML = `
                <div class="alert alert-error">
                    <i class="fas fa-exclamation-circle"></i>
                    <strong>AD Query Failed</strong>
                    <p>${error.detail || 'Failed to connect to Active Directory'}</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error querying AD:', error);
        resultDiv.innerHTML = `
            <div class="alert alert-error">
                <i class="fas fa-exclamation-circle"></i>
                <strong>Connection Error</strong>
                <p>${error.message}</p>
            </div>
        `;
    }
}

// Display AD Groups with mapping options
function displayADGroups(groups) {
    const resultDiv = document.getElementById('adGroupsResult');

    if (groups.length === 0) {
        resultDiv.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i>
                <strong>No groups found</strong>
                <p>No groups matched the search criteria. Try adjusting your filter.</p>
            </div>
        `;
        return;
    }

    resultDiv.innerHTML = `
        <div class="alert alert-success">
            <i class="fas fa-check-circle"></i>
            <strong>Found ${groups.length} groups</strong>
            <p>Click "Map to Role" to assign users from these groups to RBAC roles.</p>
        </div>
        <table class="admin-table" style="margin-top: 15px;">
            <thead>
                <tr>
                    <th>Group Name</th>
                    <th>Distinguished Name</th>
                    <th>Members</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${groups.map(group => `
                    <tr>
                        <td><strong>${group.name}</strong></td>
                        <td><code style="font-size: 11px;">${group.dn}</code></td>
                        <td>${group.member_count || 0} users</td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="showGroupMappingModal('${group.dn}', '${group.name}')">
                                <i class="fas fa-link"></i> Map to Role
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Show Group to Role Mapping Modal
async function showGroupMappingModal(groupDN, groupName) {
    // Store group info in the modal
    document.getElementById('selectedGroupDN').value = groupDN;
    document.getElementById('selectedGroupName').textContent = groupName;

    // Load available roles
    try {
        const response = await fetch('/admin/roles', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            const roleSelect = document.getElementById('mappingRoleId');

            roleSelect.innerHTML = '<option value="">Select a role...</option>' +
                data.roles.map(role => `
                    <option value="${role.role_id}">${role.role_name} - ${role.description}</option>
                `).join('');
        }
    } catch (error) {
        console.error('Error loading roles:', error);
    }

    closeModal('adSyncModal');
    showModal('groupMappingModal');
}

// Save Group to Role Mapping and Sync Users
async function saveGroupMapping() {
    const groupDN = document.getElementById('selectedGroupDN').value;
    const roleId = document.getElementById('mappingRoleId').value;
    const autoSync = document.getElementById('autoSyncEnabled').checked;

    if (!roleId) {
        showNotification('Please select a role', 'error');
        return;
    }

    try {
        const response = await fetch('/admin/ad/group-mappings', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                group_dn: groupDN,
                role_id: roleId,
                auto_sync: autoSync
            })
        });

        if (response.ok) {
            const data = await response.json();
            showNotification(`Group mapping saved! Synced ${data.synced_users} users.`, 'success');
            closeModal('groupMappingModal');
            loadUsers(); // Refresh users list
        } else {
            const error = await response.json();
            showNotification('Failed to save mapping: ' + (error.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error saving group mapping:', error);
        showNotification('Error saving mapping: ' + error.message, 'error');
    }
}

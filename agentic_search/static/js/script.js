// Agentic Search JavaScript

class AgenticSearch {
    constructor() {
        this.currentSessionId = null;
        this.isSearching = false;
        this.availableTools = [];
        this.enabledTools = [];
        this.showThinking = true;
        this.currentQueryContainer = null; // Track current query container

        this.initializeElements();
        this.setupEventListeners();
        this.loadSettings();
        this.loadAvailableTools();

        // Set copyright year
        document.getElementById('copyright-year').textContent = new Date().getFullYear();
    }

    initializeElements() {
        this.chatConsole = document.getElementById('chat-console');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.newSearchInputBtn = document.getElementById('new-search-input-btn');
        this.sidebar = document.getElementById('left-sidebar');
        this.searchBranding = document.getElementById('search-branding-container');
        this.mainContent = document.getElementById('chat-main-content');
        this.pageLogo = document.getElementById('left-page-logo');

        // Tool management - now inline in sidebar
        this.toolSelectionContainer = document.getElementById('tool-selection-container');
        this.processingToggleButton = document.getElementById('processing-toggle-button');

        // Sidebar toggle
        this.sidebarToggleBtn = document.getElementById('sidebar-toggle-btn');
        this.sidebarOverlay = document.getElementById('sidebar-overlay');
        this.sidebarVisible = true; // Track sidebar state
    }

    setupEventListeners() {
        // Send message
        this.sendButton.addEventListener('click', () => this.sendSearch());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendSearch();
            }
        });

        // Processing toggle
        this.processingToggleButton.addEventListener('click', () => this.toggleProcessingDisplay());

        // Sidebar toggle button
        this.sidebarToggleBtn.addEventListener('click', () => this.toggleSidebar());

        // Close sidebar when clicking overlay (mobile)
        this.sidebarOverlay.addEventListener('click', () => this.toggleSidebar());

        // Tool management - now inline
        document.getElementById('refresh-tools-button').addEventListener('click', () => {
            this.loadAvailableTools();
        });

        // New search - sidebar button
        document.getElementById('new-search-button').addEventListener('click', () => {
            this.startNewSearch();
        });

        // New search - input area button
        this.newSearchInputBtn.addEventListener('click', () => {
            this.startNewSearch();
        });

        // Window resize handler
        window.addEventListener('resize', () => this.handleWindowResize());
    }

    toggleProcessingDisplay() {
        this.showThinking = !this.showThinking;

        // Update button text
        const label = this.processingToggleButton.querySelector('.tool-label');
        label.textContent = this.showThinking ? 'Hide Processing' : 'Show Processing';

        // Toggle visibility of existing processing steps across all query containers
        const stepChains = this.chatConsole.querySelectorAll('.step-chain');
        stepChains.forEach(chain => {
            chain.style.display = this.showThinking ? 'block' : 'none';
        });

        this.saveSettings();
    }

    toggleSidebar() {
        this.sidebarVisible = !this.sidebarVisible;

        if (this.sidebarVisible) {
            this.sidebar.classList.remove('sidebar-hidden');
            this.sidebar.classList.add('sidebar-visible');
            this.mainContent.classList.remove('sidebar-hidden');
        } else {
            this.sidebar.classList.remove('sidebar-visible');
            this.sidebar.classList.add('sidebar-hidden');
            this.mainContent.classList.add('sidebar-hidden');
        }

        // Save preference
        localStorage.setItem('sidebarVisible', this.sidebarVisible);
    }

    handleWindowResize() {
        const windowWidth = window.innerWidth;

        // Auto-show sidebar on larger screens if it was hidden
        if (windowWidth >= 900 && !this.sidebarVisible) {
            // Optionally auto-show on large screens
            // this.toggleSidebar();
        }
    }

    startNewSearch() {
        this.currentSessionId = null;
        this.clearChat();
        this.showSearchBranding();
        this.messageInput.placeholder = "Enter your search query..."; // Reset placeholder
        this.newSearchInputBtn.classList.remove('visible'); // Hide the button
    }

    clearChat() {
        this.chatConsole.innerHTML = '';
        this.currentQueryContainer = null; // Reset current container reference
    }


    createNewQueryContainer(query) {
        // Create a new container for this entire query-response interaction
        const queryContainer = document.createElement('div');
        queryContainer.classList.add('query-container');

        // Add user message to the container
        const userMessage = document.createElement('div');
        userMessage.classList.add('message', 'user');
        const userContent = document.createElement('div');
        userContent.classList.add('message-content');
        userContent.textContent = query;
        userMessage.appendChild(userContent);
        queryContainer.appendChild(userMessage);

        // Add to chat console
        this.chatConsole.appendChild(queryContainer);
        this.currentQueryContainer = queryContainer;
        this.scrollToBottom();
    }

    showSearchBranding() {
        this.searchBranding.classList.remove('hidden');
    }

    hideSearchBranding() {
        this.searchBranding.classList.add('hidden');
    }

    async loadAvailableTools() {
        try {
            this.toolSelectionContainer.innerHTML = '<p class="loading-message">Loading tools...</p>';

            const response = await fetch('/tools');
            const data = await response.json();

            this.availableTools = data.tools || [];
            this.renderInlineToolList();

        } catch (error) {
            console.error('Error loading tools:', error);
            this.toolSelectionContainer.innerHTML = '<p class="error-message">Error loading tools. Please try again.</p>';
        }
    }

    renderInlineToolList() {
        if (this.availableTools.length === 0) {
            this.toolSelectionContainer.innerHTML = '<p class="no-tools-message">No tools available. Make sure MCP Registry Discovery is running.</p>';
            return;
        }

        const toolsHtml = this.availableTools.map(tool => `
            <div class="inline-tool-item">
                <label class="tool-checkbox-label">
                    <input type="checkbox" class="tool-checkbox"
                           data-tool-name="${tool.name}"
                           ${this.enabledTools.includes(tool.name) ? 'checked' : ''}>
                    <span class="checkmark"></span>
                    <div class="tool-details">
                        <div class="tool-name">${tool.name}</div>
                        <div class="tool-description">${tool.description || 'No description available'}</div>
                    </div>
                </label>
            </div>
        `).join('');

        this.toolSelectionContainer.innerHTML = toolsHtml;

        // Add change listeners to save selections immediately
        this.toolSelectionContainer.querySelectorAll('.tool-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateToolSelection();
            });
        });
    }

    updateToolSelection() {
        const checkboxes = this.toolSelectionContainer.querySelectorAll('.tool-checkbox');
        this.enabledTools = Array.from(checkboxes)
            .filter(checkbox => checkbox.checked)
            .map(checkbox => checkbox.dataset.toolName);

        this.saveSettings();
    }

    async sendSearch() {
        const query = this.messageInput.value.trim();
        if (!query || this.isSearching) return;

        this.hideSearchBranding();
        this.isSearching = true;
        this.sendButton.disabled = true;

        // Determine if this is a followup query
        const isFollowup = this.currentSessionId !== null && this.messageInput.placeholder.includes("followup");

        this.messageInput.value = '';
        this.messageInput.placeholder = "Enter your search query..."; // Reset placeholder

        // Generate session ID if needed
        if (!this.currentSessionId) {
            this.currentSessionId = 'search-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        }

        // Create a new query container for this query-response interaction
        this.createNewQueryContainer(query);

        try {
            // Prepare search request
            const searchData = {
                query: query,
                enabled_tools: this.enabledTools,
                session_id: this.currentSessionId,
                is_followup: isFollowup
            };

            const response = await fetch('/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(searchData)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Handle streaming response
            await this.handleStreamingResponse(response);

        } catch (error) {
            console.error('Search error:', error);
            this.addMessage('error', `Search failed: ${error.message}`);
        } finally {
            this.isSearching = false;
            this.sendButton.disabled = false;

            // Change input placeholder for follow-up queries and show New Search button
            if (this.currentSessionId) {
                this.messageInput.placeholder = "Ask a follow-up question...";
                this.newSearchInputBtn.classList.add('visible');
            }
        }
    }

    async handleStreamingResponse(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let currentAssistantMessage = null;
        let currentStepChain = null;
        let finalResponseStarted = false;
        let htmlContentMode = false;

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.trim()) continue;

                    if (line.startsWith('PROCESSING_STEP:')) {
                        if (this.showThinking) {
                            const processStepText = line.substring(16);
                            // All thinking_steps entries go directly to processing chain
                            this.addProgressToChain(processStepText);
                        }
                    } else if (line.startsWith('THINKING:')) {
                        if (this.showThinking) {
                            const thinkingText = line.substring(9);

                            // Check if this is a step completion
                            if (thinkingText.startsWith('✓ Completed:')) {
                                this.addStepToChain(thinkingText.substring(13).trim());
                            }
                            // All other THINKING messages are ignored to keep it simple
                        }
                    } else if (line.startsWith('ERROR:')) {
                        const errorText = line.substring(6);
                        this.addMessage('error', errorText);
                    } else if (line.startsWith('FINAL_RESPONSE_START:')) {
                        finalResponseStarted = true;
                        // Add a separator before final response
                        this.addResponseSeparator();
                    } else if (line.startsWith('HTML_CONTENT_START:')) {
                        htmlContentMode = true;
                        if (!currentAssistantMessage) {
                            currentAssistantMessage = this.addMessage('assistant', '');
                        }
                    } else if (line.startsWith('HTML_CONTENT_END:')) {
                        htmlContentMode = false;
                    } else if (finalResponseStarted) {
                        // This is part of the final response
                        if (!currentAssistantMessage) {
                            currentAssistantMessage = this.addMessage('assistant', '');
                        }
                        if (htmlContentMode) {
                            // For HTML content, use innerHTML directly
                            currentAssistantMessage.innerHTML += line;
                        } else {
                            // For regular text, append normally
                            this.appendToMessage(currentAssistantMessage, line);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error reading stream:', error);
            this.addMessage('error', 'Error reading response stream');
        } finally {
            // Add explanation toggle button after streaming completes
            if (finalResponseStarted) {
                this.addExplanationToggle();
            }
        }
    }

    addMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', type);

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content');
        contentDiv.textContent = content;

        messageDiv.appendChild(contentDiv);

        // Add to current query container if it exists, otherwise to chat console
        const targetContainer = this.currentQueryContainer || this.chatConsole;
        targetContainer.appendChild(messageDiv);
        this.scrollToBottom();

        return contentDiv; // Return for appending to streaming messages
    }

    appendToMessage(messageElement, content) {
        // Check if content contains HTML tags
        if (content.includes('<') && content.includes('>')) {
            // Content appears to be HTML, use innerHTML
            messageElement.innerHTML += content;
        } else {
            // Plain text content, use textContent
            messageElement.textContent += content;
        }
        this.scrollToBottom();
    }

    // Removed follow-up button - now using input placeholder only

    // Removed complex filtering logic - keeping it simple
    // thinking_steps entries come through PROCESSING_STEP: prefix and go directly to processing chain
    // THINKING: messages are only used for step completions

    addProgressToChain(progressText) {
        // Create or update the step chain - always use the most recent one
        let stepChain = this.getCurrentStepChain();

        if (!stepChain) {
            stepChain = this.createNewStepChain();
        }

        const chainSteps = stepChain.querySelector('.chain-steps');
        const progressElement = document.createElement('div');
        progressElement.classList.add('chain-progress');

        // Choose appropriate icon based on content
        let icon = '⚡';
        let iconClass = 'progress-icon';

        // Check for decision messages first (highest priority)
        if (progressText.includes('🤔 Decision: PLAN_AND_EXECUTE')) {
            icon = '🧭';
            iconClass = 'progress-icon decision-planning';
        } else if (progressText.includes('🤔 Decision: EXECUTE_NEXT_STEP')) {
            icon = '▶️';
            iconClass = 'progress-icon decision-executing';
        } else if (progressText.includes('🤔 Decision: GENERATE_RESPONSE')) {
            icon = '📝';
            iconClass = 'progress-icon decision-responding';
        } else if (progressText.includes('Discovered') || progressText.includes('tools')) {
            icon = '🔧';
        } else if (progressText.includes('Enabled tools')) {
            icon = '✅';
        } else if (progressText.includes('Received response')) {
            icon = '💭';
        } else if (progressText.includes('Created plan')) {
            icon = '📋';
        } else if (progressText.includes('executed successfully')) {
            icon = '🎯';
            iconClass = 'progress-icon tool-success';
        } else if (progressText.includes('Reasoning')) {
            icon = '🤔';
        } else if (progressText.includes('Cleaned JSON')) {
            icon = '🧹';
        } else if (progressText.includes('Skipping invalid')) {
            icon = '⏭️';
        } else if (progressText.includes('Generated final response')) {
            icon = '✨';
        } else if (progressText.includes('JSON parsing failed')) {
            icon = '⚠️';
        } else if (progressText.includes('Preparing step')) {
            icon = '⚙️';
        } else if (progressText.includes('Executing tool')) {
            icon = '🔄';
            iconClass = 'progress-icon tool-executing';
        } else if (progressText.includes('Performing reasoning')) {
            icon = '🧠';
        } else if (progressText.includes('Calling MCP service')) {
            icon = '📡';
            iconClass = 'progress-icon tool-calling';
        }

        progressElement.innerHTML = `
            <div class="${iconClass}">${icon}</div>
            <div class="progress-text">${progressText}</div>
        `;

        chainSteps.appendChild(progressElement);

        // Add animation
        setTimeout(() => {
            progressElement.classList.add('progress-visible');
        }, 100);

        this.scrollToBottom();
    }

    addStepToChain(stepName) {
        // Create or update the step chain - always use the most recent one
        let stepChain = this.getCurrentStepChain();

        if (!stepChain) {
            stepChain = this.createNewStepChain();
        }

        const chainSteps = stepChain.querySelector('.chain-steps');
        const stepElement = document.createElement('div');
        stepElement.classList.add('chain-step');
        stepElement.innerHTML = `
            <div class="step-icon">✓</div>
            <div class="step-name">${stepName}</div>
            <div class="step-connector"></div>
        `;

        chainSteps.appendChild(stepElement);

        // Add animation
        setTimeout(() => {
            stepElement.classList.add('step-completed');
        }, 100);

        this.scrollToBottom();
    }

    addResponseSeparator() {
        // Collapse the thinking stream when final response starts
        const stepChain = this.getCurrentStepChain();
        if (stepChain) {
            stepChain.classList.add('collapsed');
        }

        // Separator is now hidden via CSS
        const separator = document.createElement('div');
        separator.classList.add('response-separator');
        separator.innerHTML = `
            <div class="separator-line"></div>
            <div class="separator-text">🤖 Final Response</div>
            <div class="separator-line"></div>
        `;

        // Add to current query container if it exists, otherwise to chat console
        const targetContainer = this.currentQueryContainer || this.chatConsole;
        targetContainer.appendChild(separator);
        this.scrollToBottom();
    }

    addExplanationToggle() {
        // Add explanation toggle button after the final response
        if (!this.currentQueryContainer) return;

        const stepChain = this.getCurrentStepChain();
        if (!stepChain) return;

        const toggleBtn = document.createElement('button');
        toggleBtn.classList.add('explanation-toggle');
        toggleBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
            <span>Explanation</span>
        `;

        toggleBtn.addEventListener('click', () => {
            const isExpanded = toggleBtn.classList.toggle('expanded');
            if (isExpanded) {
                stepChain.classList.remove('collapsed');
            } else {
                stepChain.classList.add('collapsed');
            }
        });

        this.currentQueryContainer.appendChild(toggleBtn);
    }

    scrollToBottom() {
        this.chatConsole.scrollTop = this.chatConsole.scrollHeight;
    }

    getCurrentStepChain() {
        // Get the step chain in the current query container
        if (!this.currentQueryContainer) {
            return null;
        }
        return this.currentQueryContainer.querySelector('.step-chain');
    }

    createNewStepChain() {
        // Create a new step chain for the current query container
        if (!this.currentQueryContainer) {
            return null;
        }

        const stepChain = document.createElement('div');
        stepChain.classList.add('step-chain');
        stepChain.innerHTML = '<div class="chain-title">🔗 Processing Steps</div><div class="chain-steps"></div>';

        // Apply visibility based on current settings
        if (!this.showThinking) {
            stepChain.style.display = 'none';
        }

        this.currentQueryContainer.appendChild(stepChain);
        return stepChain;
    }

    loadSettings() {
        const settings = JSON.parse(localStorage.getItem('agenticSearchSettings') || '{}');

        this.showThinking = settings.showThinking !== false; // Default to true
        this.enabledTools = settings.enabledTools || [];

        // Load sidebar visibility preference (default to true/visible)
        const sidebarVisible = localStorage.getItem('sidebarVisible');
        if (sidebarVisible === 'false') {
            this.sidebarVisible = false;
            this.sidebar.classList.add('sidebar-hidden');
            this.sidebar.classList.remove('sidebar-visible');
            this.mainContent.classList.add('sidebar-hidden');
        }

        // Update processing toggle button text
        const label = this.processingToggleButton.querySelector('.tool-label');
        label.textContent = this.showThinking ? 'Hide Processing' : 'Show Processing';
    }

    saveSettings() {
        const settings = {
            showThinking: this.showThinking,
            enabledTools: this.enabledTools
        };

        localStorage.setItem('agenticSearchSettings', JSON.stringify(settings));
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new AgenticSearch();
});
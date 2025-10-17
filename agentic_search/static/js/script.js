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
        this.loadUserProfile(); // Load user info

        // Set copyright year
        document.getElementById('copyright-year').textContent = new Date().getFullYear();
    }

    initializeElements() {
        this.chatConsole = document.getElementById('chat-console');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.newSearchInputBtn = document.getElementById('new-search-input-btn');
        this.inputArea = document.getElementById('input-area');
        this.sidebar = document.getElementById('left-sidebar');
        this.searchBranding = document.getElementById('search-branding-container');
        this.mainContent = document.getElementById('chat-main-content');
        this.pageLogo = document.getElementById('left-page-logo');

        // Tool management - now inline in sidebar
        this.toolSelectionContainer = document.getElementById('tool-selection-container');
        this.processingToggleButton = document.getElementById('processing-toggle-button');

        // Sidebar toggle
        this.sidebarToggleBtn = document.getElementById('sidebar-toggle-btn');
        this.sidebarCollapseBtn = document.getElementById('sidebar-collapse-btn');
        this.sidebarOverlay = document.getElementById('sidebar-overlay');
        this.sidebarVisible = false; // Start collapsed by default

        // Right sidebar for sources
        this.rightSidebar = document.getElementById('right-sidebar');
        this.rightSidebarToggleBtn = document.getElementById('right-sidebar-toggle-btn');
        this.rightSidebarCollapseBtn = document.getElementById('right-sidebar-collapse-btn');
        this.sourcesContainer = document.getElementById('sources-container');
        this.rightSidebarVisible = false; // Start hidden by default

        // Theme selector
        this.themeToggleBtn = document.getElementById('theme-toggle-btn');
        this.themeDropdown = document.getElementById('theme-dropdown');

        // Set initial centered state
        this.inputArea.classList.add('centered');

        // Set left sidebar to hidden initially
        this.sidebar.classList.add('sidebar-hidden');
        this.sidebar.classList.remove('sidebar-visible');
        this.mainContent.classList.add('sidebar-hidden');

        // Right sidebar is hidden initially but doesn't shift main content
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
        this.processingToggleButton.addEventListener('click', () => {
            this.toggleProcessingDisplay();
        });

        // Sidebar toggle button
        this.sidebarToggleBtn.addEventListener('click', () => this.toggleSidebar());

        // Sidebar collapse button
        this.sidebarCollapseBtn.addEventListener('click', () => this.toggleSidebar());

        // Close sidebar when clicking overlay (mobile)
        this.sidebarOverlay.addEventListener('click', () => this.toggleSidebar());

        // Right sidebar toggle button
        this.rightSidebarToggleBtn.addEventListener('click', () => this.toggleRightSidebar());

        // Right sidebar collapse button
        this.rightSidebarCollapseBtn.addEventListener('click', () => this.toggleRightSidebar());

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

        // Logout button
        document.getElementById('logout-button').addEventListener('click', () => {
            this.handleLogout();
        });

        // Theme selector
        this.themeToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleThemeDropdown();
        });

        // Theme options
        document.querySelectorAll('.theme-option').forEach(option => {
            option.addEventListener('click', (e) => {
                const theme = option.dataset.theme;
                this.changeTheme(theme);
            });
        });

        // Close theme dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.themeDropdown.contains(e.target) && e.target !== this.themeToggleBtn) {
                this.themeDropdown.classList.add('hidden');
            }
        });
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

        // Adjust input area position when in bottom state
        if (this.inputArea.classList.contains('bottom')) {
            // Wait for layout to update and reflow
            setTimeout(() => {
                this.adjustInputAreaPosition();
            }, 100);
        }

        this.saveSettings();
    }

    adjustInputAreaPosition() {
        // CSS handles positioning with margin-top: 20px
        // No JavaScript adjustment needed
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

    toggleRightSidebar() {
        this.rightSidebarVisible = !this.rightSidebarVisible;

        if (this.rightSidebarVisible) {
            this.rightSidebar.classList.remove('sidebar-hidden');
            this.rightSidebar.classList.add('sidebar-visible');
            // Don't shift main content - let sidebar overlay
        } else {
            this.rightSidebar.classList.remove('sidebar-visible');
            this.rightSidebar.classList.add('sidebar-hidden');
        }

        // Save preference
        localStorage.setItem('rightSidebarVisible', this.rightSidebarVisible);
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

        // Move input back to center
        this.inputArea.classList.remove('bottom');
        this.inputArea.classList.add('centered');
    }

    clearChat() {
        this.chatConsole.innerHTML = '';
        this.currentQueryContainer = null; // Reset current container reference
        this.clearSources(); // Clear sources when clearing chat
    }

    clearSources() {
        // Reset sources panel to placeholder
        this.sourcesContainer.innerHTML = `
            <div class="sources-placeholder">
                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.3; margin-bottom: 12px;">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                </svg>
                <p>No sources yet</p>
                <small>Sources and URLs will appear here when you perform a search</small>
            </div>
        `;

        // Hide the sources toggle button
        this.rightSidebarToggleBtn.classList.add('hidden');

        // Hide the right sidebar when clearing sources
        if (this.rightSidebarVisible) {
            this.rightSidebarVisible = false;
            this.rightSidebar.classList.remove('sidebar-visible');
            this.rightSidebar.classList.add('sidebar-hidden');
            // Don't shift main content
            localStorage.setItem('rightSidebarVisible', this.rightSidebarVisible);
        }
    }

    extractSourcesFromResponse(responseText) {
        // Extract sources from JSON data in the response
        const sources = [];


        try {
            // Strategy 1: Look for properly formatted JSON arrays (double quotes)
            const jsonArrayPattern = /\[\s*\{[\s\S]*?"(?:url|rid|docid|id)"[\s\S]*?\}\s*\]/g;
            let jsonMatches = responseText.match(jsonArrayPattern);

            if (jsonMatches) {
                for (const jsonStr of jsonMatches) {
                    try {
                        const data = JSON.parse(jsonStr);
                        if (Array.isArray(data)) {
                            data.forEach(item => {
                                // Check if item has source fields
                                if (item.url || item.rid || item.docid || item.id) {
                                    const source = {
                                        url: item.url || '',
                                        rid: item.rid || '',
                                        docid: item.docid || '',
                                        title: item.title || item.event_title || 'Untitled',
                                        id: item.id || item.docid || item.rid || Math.random().toString(36).substr(2, 9)
                                    };
                                    sources.push(source);
                                }
                            });
                        }
                    } catch (e) {
                        console.warn('Failed to parse JSON block:', e);
                    }
                }
            }

            // Strategy 2: Extract individual JSON objects with double quotes
            const objectPattern = /\{\s*"id"\s*:\s*"[^"]+"\s*,\s*"score"\s*:[\s\S]*?\}/g;
            const objectMatches = responseText.match(objectPattern);

            if (objectMatches) {
                for (const objStr of objectMatches) {
                    try {
                        const item = JSON.parse(objStr);
                        if (item.url || item.rid || item.docid || item.id) {
                            const source = {
                                url: item.url || '',
                                rid: item.rid || '',
                                docid: item.docid || '',
                                title: item.title || item.event_title || 'Untitled',
                                id: item.id || item.docid || item.rid || Math.random().toString(36).substr(2, 9)
                            };
                            sources.push(source);
                        }
                    } catch (e) {
                        // Skip invalid JSON
                    }
                }
            }

            // Strategy 3: Manual extraction of key fields using regex
            if (sources.length === 0) {
                // Look for patterns like: "id": "...", "title": "...", "url": "..."
                const idPattern = /"id"\s*:\s*"([^"]+)"/g;
                const titlePattern = /"(?:title|event_title)"\s*:\s*"([^"]+)"/g;
                const urlPattern = /"url"\s*:\s*"([^"]+)"/g;
                const ridPattern = /"rid"\s*:\s*"([^"]+)"/g;
                const docidPattern = /"docid"\s*:\s*"([^"]+)"/g;

                let idMatch;
                const ids = [];
                while ((idMatch = idPattern.exec(responseText)) !== null) {
                    ids.push({ index: idMatch.index, id: idMatch[1] });
                }

                // For each ID, try to extract other fields nearby
                ids.forEach(({ index, id }) => {
                    // Look in a window around this ID (500 chars before and after)
                    const start = Math.max(0, index - 500);
                    const end = Math.min(responseText.length, index + 500);
                    const snippet = responseText.substring(start, end);

                    const titleMatch = /"(?:title|event_title)"\s*:\s*"([^"]+)"/.exec(snippet);
                    const urlMatch = /"url"\s*:\s*"([^"]+)"/.exec(snippet);
                    const ridMatch = /"rid"\s*:\s*"([^"]+)"/.exec(snippet);
                    const docidMatch = /"docid"\s*:\s*"([^"]+)"/.exec(snippet);

                    const source = {
                        id: id,
                        title: titleMatch ? titleMatch[1] : 'Untitled',
                        url: urlMatch ? urlMatch[1] : '',
                        rid: ridMatch ? ridMatch[1] : '',
                        docid: docidMatch ? docidMatch[1] : ''
                    };

                    // Only add if we have at least one source field
                    if (source.url || source.rid || source.docid) {
                        sources.push(source);
                    }
                });
            }
        } catch (error) {
            console.error('Error extracting sources:', error);
        }

        return sources;
    }

    displaySources(sources) {
        if (!sources || sources.length === 0) {
            return;
        }

        // Remove duplicates based on id
        const uniqueSources = sources.filter((source, index, self) =>
            index === self.findIndex((s) => s.id === source.id)
        );

        // Create sources HTML
        const sourcesHtml = uniqueSources.map((source, index) => `
            <div class="source-item" data-source-id="${source.id}">
                <div class="source-number">${index + 1}</div>
                <div class="source-details">
                    <div class="source-title">${this.escapeHtml(source.title)}</div>
                    ${source.url ? `
                        <div class="source-url">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                            </svg>
                            <a href="${source.url}" target="_blank" rel="noopener noreferrer">${this.truncateUrl(source.url)}</a>
                        </div>
                    ` : ''}
                    ${source.rid ? `<div class="source-meta">RID: ${this.escapeHtml(source.rid)}</div>` : ''}
                    ${source.docid ? `<div class="source-meta">Doc ID: ${this.escapeHtml(source.docid)}</div>` : ''}
                </div>
            </div>
        `).join('');

        const html = `
            <div class="sources-header">
                <span class="sources-count">${uniqueSources.length} source${uniqueSources.length !== 1 ? 's' : ''} found</span>
            </div>
            <div class="sources-list">
                ${sourcesHtml}
            </div>
        `;

        this.sourcesContainer.innerHTML = html;

        // Show the sources toggle button
        this.rightSidebarToggleBtn.classList.remove('hidden');

        // Automatically show the right sidebar when sources are available
        if (!this.rightSidebarVisible) {
            this.rightSidebarVisible = true;
            this.rightSidebar.classList.remove('sidebar-hidden');
            this.rightSidebar.classList.add('sidebar-visible');
            // Don't shift main content - let sidebar overlay
            localStorage.setItem('rightSidebarVisible', this.rightSidebarVisible);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    truncateUrl(url, maxLength = 50) {
        if (url.length <= maxLength) return url;
        return url.substring(0, maxLength - 3) + '...';
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

        // Move input to bottom on first search
        if (this.inputArea.classList.contains('centered')) {
            this.inputArea.classList.remove('centered');
            this.inputArea.classList.add('bottom');
        }

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

            // Adjust input area position if processing steps are hidden
            setTimeout(() => {
                this.adjustInputAreaPosition();
            }, 300);
        }
    }

    async handleStreamingResponse(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let currentAssistantMessage = null;
        let currentStepChain = null;
        let finalResponseStarted = false;
        let htmlContentMode = false;
        let accumulatedResponseText = ''; // Accumulate response for source extraction
        let htmlBuffer = ''; // Buffer for accumulating HTML content
        let messageCentered = false; // Track if we've centered the message

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.trim()) continue;

                    if (line.startsWith('PROCESSING_STEP:')) {
                        const processStepText = line.substring(16);
                        // Always accumulate for source extraction (regardless of showThinking)
                        accumulatedResponseText += processStepText + '\n';

                        // Only display if showThinking is enabled
                        if (this.showThinking) {
                            // All thinking_steps entries go directly to processing chain
                            this.addProgressToChain(processStepText);
                        }
                    } else if (line.startsWith('THINKING:')) {
                        if (this.showThinking) {
                            const thinkingText = line.substring(9);

                            // Check if this is a node start message (▶ prefix)
                            if (thinkingText.startsWith('▶')) {
                                // Add node start to chain immediately
                                this.addProgressToChain(thinkingText);
                            }
                            // Ignore completion messages since we already showed the node at start
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
                        htmlBuffer = ''; // Reset buffer
                        if (!currentAssistantMessage) {
                            currentAssistantMessage = this.addMessage('assistant', '');
                            // Center the message box
                            setTimeout(() => {
                                this.scrollToMessage(currentAssistantMessage.parentElement);
                                messageCentered = true;
                            }, 100);
                            // Trigger glow effect after message is created
                            setTimeout(() => this.triggerAnswerGlow(), 100);
                        }
                    } else if (line.startsWith('HTML_CONTENT_END:')) {
                        htmlContentMode = false;
                        // Process accumulated HTML
                        if (htmlBuffer && currentAssistantMessage) {
                            this.revealHTMLContent(currentAssistantMessage, htmlBuffer);
                        }
                        htmlBuffer = '';
                    } else if (finalResponseStarted) {
                        // This is part of the final response
                        if (!currentAssistantMessage) {
                            currentAssistantMessage = this.addMessage('assistant', '');
                            // Center the message box
                            setTimeout(() => {
                                this.scrollToMessage(currentAssistantMessage.parentElement);
                                messageCentered = true;
                            }, 100);
                            // Trigger glow effect after message is created
                            setTimeout(() => this.triggerAnswerGlow(), 100);
                        }
                        if (htmlContentMode) {
                            // Accumulate HTML content
                            htmlBuffer += line + '\n';
                            accumulatedResponseText += line + '\n';
                        } else {
                            // For regular text, append normally
                            this.appendToMessage(currentAssistantMessage, line);
                            accumulatedResponseText += line + '\n';
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

            // Extract and display sources from accumulated response
            if (accumulatedResponseText) {
                const sources = this.extractSourcesFromResponse(accumulatedResponseText);
                if (sources.length > 0) {
                    this.displaySources(sources);
                }
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

        // Adjust input position after adding message
        setTimeout(() => this.adjustInputAreaPosition(), 50);

        return contentDiv; // Return for appending to streaming messages
    }

    appendToMessage(messageElement, content) {
        // For streaming content, just append directly
        // Progressive reveal is handled by revealHTMLContent when HTML_CONTENT_END is received
        if (content.includes('<') && content.includes('>')) {
            // Content appears to be HTML
            messageElement.innerHTML += content;
        } else {
            // Plain text content, use textContent
            messageElement.textContent += content;
        }
        this.scrollToBottom();
        setTimeout(() => this.adjustInputAreaPosition(), 50);
    }

    revealHTMLContent(messageElement, htmlContent) {
        // Clear the message element first
        messageElement.innerHTML = '';

        // Create a temporary container to parse the HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = htmlContent.trim();

        // Get all child elements (direct children of the div wrapper)
        const elements = Array.from(tempDiv.children);

        if (elements.length === 0) {
            // If no block elements, just set innerHTML
            messageElement.innerHTML = htmlContent;
            return;
        }

        // Progressive reveal each element
        elements.forEach((element, index) => {
            // Wrap element in a reveal container
            const revealWrapper = document.createElement('div');
            revealWrapper.classList.add('reveal-line');
            revealWrapper.appendChild(element.cloneNode(true));

            // Add with delay - progressive reveal
            setTimeout(() => {
                messageElement.appendChild(revealWrapper);
            }, index * 200); // 200ms delay between each element
        });
    }

    scrollToMessage(messageDiv) {
        // Scroll to center the assistant message box on screen
        if (messageDiv) {
            messageDiv.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'nearest'
            });
        }
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

        // Adjust input position after adding content
        setTimeout(() => this.adjustInputAreaPosition(), 50);
        const progressElement = document.createElement('div');
        progressElement.classList.add('chain-progress');

        // Choose appropriate icon based on content
        let icon = '⚡';
        let iconClass = 'progress-icon';

        // Check for node start messages first (highest priority) - add green checkmark
        if (progressText.startsWith('▶')) {
            icon = '✓';
            iconClass = 'progress-icon node-start-icon';
        }
        // Check for decision messages
        else if (progressText.includes('🤔 Decision: PLAN_AND_EXECUTE')) {
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
        // Auto-collapse the processing steps when final response starts
        const stepChain = this.getCurrentStepChain();
        if (stepChain && !stepChain.classList.contains('collapsed')) {
            stepChain.classList.add('collapsed');

            // Update the collapse button icon to down arrow
            const collapseBtn = stepChain.querySelector('.chain-collapse-btn');
            if (collapseBtn) {
                collapseBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="6 9 12 15 18 9"></polyline>
                </svg>`;
            }
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

    triggerAnswerGlow() {
        // Add glow effect to assistant message content when final answer appears
        if (this.currentQueryContainer) {
            // Find the last assistant message's content element
            const assistantMessages = this.currentQueryContainer.querySelectorAll('.message.assistant .message-content');
            if (assistantMessages.length > 0) {
                const lastMessageContent = assistantMessages[assistantMessages.length - 1];
                // Only add the class if it doesn't already exist
                if (!lastMessageContent.classList.contains('answer-glow')) {
                    lastMessageContent.classList.add('answer-glow');
                }
            }
            // Don't remove the class - let the animation complete and stay at 100% state
        }
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
            <span>Show Thinking</span>
        `;

        toggleBtn.addEventListener('click', () => {
            const isExpanded = toggleBtn.classList.toggle('expanded');
            if (isExpanded) {
                stepChain.classList.remove('collapsed');
                toggleBtn.querySelector('span').textContent = 'Hide Thinking';
                // Update collapse button icon to up arrow
                const collapseBtn = stepChain.querySelector('.chain-collapse-btn');
                if (collapseBtn) {
                    collapseBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="18 15 12 9 6 15"></polyline>
                    </svg>`;
                }
            } else {
                stepChain.classList.add('collapsed');
                toggleBtn.querySelector('span').textContent = 'Show Thinking';
                // Update collapse button icon to down arrow
                const collapseBtn = stepChain.querySelector('.chain-collapse-btn');
                if (collapseBtn) {
                    collapseBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>`;
                }
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
        stepChain.innerHTML = `
            <div class="chain-title">
                <span>🔗 Processing Steps</span>
                <button class="chain-collapse-btn" title="Collapse">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="18 15 12 9 6 15"></polyline>
                    </svg>
                </button>
            </div>
            <div class="chain-steps"></div>
        `;

        // Apply visibility based on current settings
        if (!this.showThinking) {
            stepChain.style.display = 'none';
        }

        // Add collapse button event listener
        const collapseBtn = stepChain.querySelector('.chain-collapse-btn');
        collapseBtn.addEventListener('click', () => {
            stepChain.classList.toggle('collapsed');
            // Update button icon direction
            const isCollapsed = stepChain.classList.contains('collapsed');
            collapseBtn.innerHTML = isCollapsed ?
                `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="6 9 12 15 18 9"></polyline>
                </svg>` :
                `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="18 15 12 9 6 15"></polyline>
                </svg>`;
        });

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

        // Load theme preference
        const savedTheme = settings.theme || 'ocean';
        this.applyTheme(savedTheme);

        // Update processing toggle button text
        const label = this.processingToggleButton.querySelector('.tool-label');
        label.textContent = this.showThinking ? 'Hide Processing' : 'Show Processing';
    }

    saveSettings() {
        const settings = {
            showThinking: this.showThinking,
            enabledTools: this.enabledTools,
            theme: this.currentTheme || 'ocean'
        };

        localStorage.setItem('agenticSearchSettings', JSON.stringify(settings));
    }

    toggleThemeDropdown() {
        this.themeDropdown.classList.toggle('hidden');
    }

    changeTheme(theme) {
        this.currentTheme = theme;
        this.applyTheme(theme);
        this.saveSettings();
        this.themeDropdown.classList.add('hidden');
    }

    applyTheme(theme) {
        // Remove all theme classes
        document.body.classList.remove('theme-ocean', 'theme-sunset', 'theme-forest', 'theme-lavender', 'theme-minimal');

        // Add theme class
        document.body.classList.add(`theme-${theme}`);

        // Update active state in dropdown
        document.querySelectorAll('.theme-option').forEach(option => {
            option.classList.remove('active');
            if (option.dataset.theme === theme) {
                option.classList.add('active');
            }
        });

        this.currentTheme = theme;
    }

    async loadUserProfile() {
        try {
            const response = await fetch('/auth/user');
            if (response.ok) {
                const userData = await response.json();
                this.displayUserInfo(userData);
            } else {
                console.error('Failed to load user info');
                document.getElementById('user-name-display').textContent = 'Guest';
            }
        } catch (error) {
            console.error('Error loading user profile:', error);
            document.getElementById('user-name-display').textContent = 'Guest';
        }
    }

    displayUserInfo(userData) {
        const userNameDisplay = document.getElementById('user-name-display');
        // Display name if available, otherwise email
        const displayName = userData.name || userData.email || 'User';
        userNameDisplay.textContent = displayName;
    }

    async handleLogout() {
        try {
            const response = await fetch('/auth/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                // Redirect to login page after successful logout
                window.location.href = '/auth/login';
            } else {
                console.error('Logout failed');
                alert('Logout failed. Please try again.');
            }
        } catch (error) {
            console.error('Error during logout:', error);
            alert('Error during logout. Please try again.');
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new AgenticSearch();
});
// Conversational Medical Assistant - Enhanced JavaScript

class MedicalChat {
    constructor() {
        this.sessionId = this.generateSessionId();
        this.messages = [];
        this.isProcessing = false;
        this.initializeElements();
        this.bindEvents();
        this.loadSession();
    }

    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    initializeElements() {
        this.chatMessages = document.getElementById('chatMessages');
        this.chatInput = document.getElementById('chatInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.sessionIdElement = document.getElementById('sessionId');
        this.messageCountElement = document.getElementById('messageCount');
        
        // Update session display
        if (this.sessionIdElement) {
            this.sessionIdElement.textContent = this.sessionId;
        }
    }

    bindEvents() {
        // Send message on button click
        if (this.sendBtn) {
            this.sendBtn.addEventListener('click', () => this.sendMessage());
        }

        // Send message on Enter key (Shift+Enter for new line)
        if (this.chatInput) {
            this.chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            // Auto-resize textarea
            this.chatInput.addEventListener('input', () => {
                this.autoResizeTextarea();
            });

            // Focus enhancement
            this.chatInput.addEventListener('focus', () => {
                this.chatInput.parentElement.classList.add('focused');
            });

            this.chatInput.addEventListener('blur', () => {
                this.chatInput.parentElement.classList.remove('focused');
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + Enter to send message
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                if (document.activeElement === this.chatInput) {
                    e.preventDefault();
                    this.sendMessage();
                }
            }
        });
    }

    autoResizeTextarea() {
        if (this.chatInput) {
            this.chatInput.style.height = 'auto';
            this.chatInput.style.height = Math.min(this.chatInput.scrollHeight, 120) + 'px';
        }
    }

    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message || this.isProcessing) return;

        // Add user message to chat
        this.addMessage(message, 'user');
        this.chatInput.value = '';
        this.autoResizeTextarea();

        // Show typing indicator
        this.showTypingIndicator();

        // Disable input during processing
        this.setProcessingState(true);

        try {
            // Send message to backend
            const response = await this.sendToBackend(message);
            
            // Hide typing indicator
            this.hideTypingIndicator();
            
            // Add assistant response
            this.addMessage(response, 'assistant');
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.hideTypingIndicator();
            this.addMessage('I apologize, but I encountered an error processing your request. Please try again.', 'assistant');
        } finally {
            this.setProcessingState(false);
        }
    }

    async sendToBackend(message) {
        const requestData = {
            message: message,
            session_id: this.sessionId,
            conversation_history: this.getConversationHistory()
        };

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        return data.response;
    }

    addMessage(content, sender) {
        const message = {
            id: Date.now(),
            content: content,
            sender: sender,
            timestamp: new Date()
        };

        this.messages.push(message);
        this.renderMessage(message);
        this.updateMessageCount();
        this.saveSession();
        this.scrollToBottom();
    }

    renderMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${message.sender}`;
        messageElement.id = `message-${message.id}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        
        if (message.sender === 'user') {
            avatar.innerHTML = '<i class="fas fa-user"></i>';
        } else {
            avatar.innerHTML = '<i class="fas fa-user-md"></i>';
        }

        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = message.content;

        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = this.formatTime(message.timestamp);

        messageElement.appendChild(avatar);
        messageElement.appendChild(content);
        messageElement.appendChild(time);

        // Remove welcome message if it exists
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }

        this.chatMessages.appendChild(messageElement);
    }

    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    showTypingIndicator() {
        if (this.typingIndicator) {
            this.typingIndicator.classList.add('show');
            this.scrollToBottom();
        }
    }

    hideTypingIndicator() {
        if (this.typingIndicator) {
            this.typingIndicator.classList.remove('show');
        }
    }

    setProcessingState(processing) {
        this.isProcessing = processing;
        
        if (this.sendBtn) {
            this.sendBtn.disabled = processing;
            if (processing) {
                this.sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            } else {
                this.sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
            }
        }

        if (this.chatInput) {
            this.chatInput.disabled = processing;
        }
    }

    scrollToBottom() {
        setTimeout(() => {
            if (this.chatMessages) {
                this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
            }
        }, 100);
    }

    updateMessageCount() {
        if (this.messageCountElement) {
            this.messageCountElement.textContent = this.messages.length;
        }
    }

    getConversationHistory() {
        return this.messages.map(msg => ({
            role: msg.sender === 'user' ? 'user' : 'assistant',
            content: msg.content,
            timestamp: msg.timestamp
        }));
    }

    saveSession() {
        try {
            const sessionData = {
                sessionId: this.sessionId,
                messages: this.messages,
                timestamp: Date.now()
            };
            localStorage.setItem('medicalChatSession', JSON.stringify(sessionData));
        } catch (error) {
            console.error('Error saving session:', error);
        }
    }

    loadSession() {
        try {
            const savedSession = localStorage.getItem('medicalChatSession');
            if (savedSession) {
                const sessionData = JSON.parse(savedSession);
                
                // Check if session is from today (within 24 hours)
                const sessionAge = Date.now() - sessionData.timestamp;
                const oneDay = 24 * 60 * 60 * 1000;
                
                if (sessionAge < oneDay) {
                    this.sessionId = sessionData.sessionId;
                    this.messages = sessionData.messages.map(msg => ({
                        ...msg,
                        timestamp: new Date(msg.timestamp)
                    }));
                    
                    // Update session display
                    if (this.sessionIdElement) {
                        this.sessionIdElement.textContent = this.sessionId;
                    }
                    
                    // Render existing messages
                    this.messages.forEach(msg => this.renderMessage(msg));
                    this.updateMessageCount();
                }
            }
        } catch (error) {
            console.error('Error loading session:', error);
        }
    }

    clearChat() {
        if (confirm('Are you sure you want to clear the chat history? This action cannot be undone.')) {
            this.messages = [];
            this.sessionId = this.generateSessionId();
            
            // Clear localStorage
            localStorage.removeItem('medicalChatSession');
            
            // Clear chat display
            if (this.chatMessages) {
                this.chatMessages.innerHTML = `
                    <div class="welcome-message">
                        <i class="fas fa-heartbeat" style="font-size: 2rem; color: #667eea; margin-bottom: 10px;"></i>
                        <p>Hello! I'm Dr. AI Assistant. How can I help you today?</p>
                        <p style="font-size: 0.9rem; margin-top: 10px;">Please describe your symptoms, medical concerns, or ask any health-related questions.</p>
                    </div>
                `;
            }
            
            // Update session display
            if (this.sessionIdElement) {
                this.sessionIdElement.textContent = this.sessionId;
            }
            
            this.updateMessageCount();
        }
    }
}

// Global functions for HTML onclick handlers
function sendMessage() {
    if (window.medicalChat) {
        window.medicalChat.sendMessage();
    }
}

function clearChat() {
    if (window.medicalChat) {
        window.medicalChat.clearChat();
    }
}

// Initialize the chat when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.medicalChat = new MedicalChat();
    
    // Enhanced feature card interactions
    const features = document.querySelectorAll('.feature');
    features.forEach(feature => {
        feature.addEventListener('click', function() {
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });

    // Enhanced doctor avatar interaction
    const doctorAvatar = document.querySelector('.doctor-avatar i');
    if (doctorAvatar) {
        doctorAvatar.addEventListener('click', function() {
            this.style.animation = 'pulse 0.5s ease';
            setTimeout(() => {
                this.style.animation = 'pulse 2s infinite';
            }, 500);
        });
    }

    // Accessibility enhancements
    const focusableElements = document.querySelectorAll('button, textarea, input, select, a[href]');
    focusableElements.forEach(element => {
        element.addEventListener('focus', function() {
            this.style.outline = '2px solid #667eea';
            this.style.outlineOffset = '2px';
        });

        element.addEventListener('blur', function() {
            this.style.outline = '';
            this.style.outlineOffset = '';
        });
    });

    // Performance optimization - lazy loading for animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '50px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe elements for animation
    document.querySelectorAll('.doctor-section, .chat-section').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
});

// Utility functions
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'error' ? 'exclamation-triangle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#fee' : '#efe'};
        color: ${type === 'error' ? '#c33' : '#363'};
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid ${type === 'error' ? '#c33' : '#363'};
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1000;
        transform: translateX(100%);
        transition: transform 0.3s ease;
        max-width: 300px;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 100);
    
    setTimeout(() => {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (document.body.contains(notification)) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// Export for potential use in other scripts
window.MedicalApp = {
    showNotification,
    // Add other utility functions as needed
}; 
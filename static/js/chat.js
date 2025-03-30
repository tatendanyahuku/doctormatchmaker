// Chat functionality for MedConsult consultation rooms

class ChatSystem {
    constructor(consultationId, userId, userName) {
        this.consultationId = consultationId;
        this.userId = userId;
        this.userName = userName;
        this.messagesList = document.getElementById('messages-list');
        this.messageForm = document.getElementById('message-form');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-message-btn');
        
        this.setupEventListeners();
        this.loadMessages();
    }
    
    setupEventListeners() {
        // Handle message form submission
        if (this.messageForm) {
            this.messageForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }
    }
    
    async loadMessages() {
        if (!this.messagesList) return;
        
        try {
            const response = await fetch(`/api/consultation/${this.consultationId}/messages`);
            const data = await response.json();
            
            if (data.success) {
                // Clear existing messages
                this.messagesList.innerHTML = '';
                
                // Display messages
                data.messages.forEach(message => {
                    this.displayMessage(message);
                });
                
                // Scroll to the bottom
                this.scrollToBottom();
            } else {
                console.error('Error loading messages:', data.error);
            }
        } catch (error) {
            console.error('Error loading messages:', error);
        }
    }
    
    async sendMessage() {
        const messageContent = this.messageInput.value.trim();
        
        if (!messageContent) return;
        
        try {
            const response = await fetch(`/api/consultation/${this.consultationId}/send-message`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ content: messageContent })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Clear input field
                this.messageInput.value = '';
                
                // Display the sent message
                this.displayMessage(data.message);
                
                // Scroll to the bottom
                this.scrollToBottom();
            } else {
                console.error('Error sending message:', data.error);
            }
        } catch (error) {
            console.error('Error sending message:', error);
        }
    }
    
    displayMessage(message) {
        if (!this.messagesList) return;
        
        const isCurrentUser = parseInt(message.sender_id) === parseInt(this.userId);
        const messageElement = document.createElement('div');
        
        messageElement.className = `message-item d-flex ${isCurrentUser ? 'justify-content-end' : 'justify-content-start'} mb-2`;
        
        const messageContent = `
            <div class="message-content ${isCurrentUser ? 'bg-primary text-white' : 'bg-light text-dark'} p-2 rounded">
                <div class="message-sender small ${isCurrentUser ? 'text-white-50' : 'text-muted'}">
                    ${isCurrentUser ? 'You' : message.sender_name} (${message.sender_role})
                </div>
                <div class="message-text">
                    ${this.escapeHtml(message.content)}
                </div>
                <div class="message-time small ${isCurrentUser ? 'text-white-50' : 'text-muted'} text-end">
                    ${this.formatTimestamp(message.timestamp)}
                </div>
            </div>
        `;
        
        messageElement.innerHTML = messageContent;
        this.messagesList.appendChild(messageElement);
    }
    
    scrollToBottom() {
        if (this.messagesList) {
            this.messagesList.scrollTop = this.messagesList.scrollHeight;
        }
    }
    
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        
        // Format: HH:MM
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Start polling for new messages
    startPolling(interval = 5000) {
        this.pollingInterval = setInterval(() => {
            this.loadMessages();
        }, interval);
    }
    
    // Stop polling for new messages
    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
    }
}

// Initialize chat system when page loads
document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('chat-container');
    
    if (chatContainer) {
        const consultationId = chatContainer.getAttribute('data-consultation-id');
        const userId = chatContainer.getAttribute('data-user-id');
        const userName = chatContainer.getAttribute('data-user-name');
        
        if (consultationId && userId && userName) {
            // Create and initialize chat system
            const chatSystem = new ChatSystem(consultationId, userId, userName);
            
            // Start polling for new messages
            chatSystem.startPolling();
            
            // Expose the chat system object for debugging
            window.chatSystem = chatSystem;
        }
    }
});

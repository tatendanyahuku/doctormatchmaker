// WebRTC Video Call Implementation for MedConsult

class VideoConsultation {
    constructor(consultationId, userId, userRole) {
        this.consultationId = consultationId;
        this.userId = userId;
        this.userRole = userRole; // 'doctor' or 'patient'
        this.peerConnection = null;
        this.localStream = null;
        this.remoteStream = null;
        this.isCallInitiator = this.userRole === 'doctor'; // Doctor initiates the call
        
        this.localVideo = document.getElementById('local-video');
        this.remoteVideo = document.getElementById('remote-video');
        this.startCallBtn = document.getElementById('start-call-btn');
        this.endCallBtn = document.getElementById('end-call-btn');
        this.muteAudioBtn = document.getElementById('mute-audio-btn');
        this.muteVideoBtn = document.getElementById('mute-video-btn');
        this.connectionStatus = document.getElementById('connection-status');
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        if (this.startCallBtn) {
            this.startCallBtn.addEventListener('click', () => this.startCall());
        }
        
        if (this.endCallBtn) {
            this.endCallBtn.addEventListener('click', () => this.endCall());
        }
        
        if (this.muteAudioBtn) {
            this.muteAudioBtn.addEventListener('click', () => this.toggleAudio());
        }
        
        if (this.muteVideoBtn) {
            this.muteVideoBtn.addEventListener('click', () => this.toggleVideo());
        }
    }
    
    async startCall() {
        try {
            // Update UI
            this.updateConnectionStatus('Connecting...');
            this.startCallBtn.disabled = true;
            
            // Get local media stream
            this.localStream = await navigator.mediaDevices.getUserMedia({ 
                audio: true, 
                video: true 
            });
            
            // Display local video
            this.localVideo.srcObject = this.localStream;
            
            // Initialize remote stream
            this.remoteStream = new MediaStream();
            this.remoteVideo.srcObject = this.remoteStream;
            
            // Create peer connection
            this.createPeerConnection();
            
            // Add local tracks to peer connection
            this.localStream.getTracks().forEach(track => {
                this.peerConnection.addTrack(track, this.localStream);
            });
            
            // If doctor, create and send offer
            if (this.isCallInitiator) {
                const offer = await this.peerConnection.createOffer();
                await this.peerConnection.setLocalDescription(offer);
                
                // Send offer to server
                this.sendSignalingData({ offer: offer });
            }
            
            // Show end call button and mute controls
            this.endCallBtn.classList.remove('d-none');
            this.muteAudioBtn.classList.remove('d-none');
            this.muteVideoBtn.classList.remove('d-none');
            
        } catch (error) {
            console.error('Error starting video call:', error);
            this.updateConnectionStatus('Failed to start call: ' + error.message);
            this.startCallBtn.disabled = false;
        }
    }
    
    createPeerConnection() {
        // STUN servers for NAT traversal
        const configuration = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ]
        };
        
        this.peerConnection = new RTCPeerConnection(configuration);
        
        // Handle ICE candidates
        this.peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                // Send ICE candidate to the other peer via server
                this.sendSignalingData({ candidate: event.candidate });
            }
        };
        
        // Handle connection state changes
        this.peerConnection.onconnectionstatechange = () => {
            this.updateConnectionStatus(this.peerConnection.connectionState);
        };
        
        // Handle ICE connection state changes
        this.peerConnection.oniceconnectionstatechange = () => {
            if (this.peerConnection.iceConnectionState === 'disconnected' ||
                this.peerConnection.iceConnectionState === 'failed' ||
                this.peerConnection.iceConnectionState === 'closed') {
                this.updateConnectionStatus('Connection lost');
            }
        };
        
        // Handle incoming tracks
        this.peerConnection.ontrack = (event) => {
            event.streams[0].getTracks().forEach(track => {
                this.remoteStream.addTrack(track);
            });
        };
    }
    
    async handleSignalingData(data) {
        try {
            // Handle WebRTC offer
            if (data.offer && !this.isCallInitiator) {
                await this.peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
                const answer = await this.peerConnection.createAnswer();
                await this.peerConnection.setLocalDescription(answer);
                
                // Send answer back
                this.sendSignalingData({ answer: answer });
            }
            
            // Handle WebRTC answer
            if (data.answer && this.isCallInitiator) {
                await this.peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
            }
            
            // Handle ICE candidates
            if (data.candidate) {
                await this.peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
            }
        } catch (error) {
            console.error('Error handling signaling data:', error);
        }
    }
    
    sendSignalingData(data) {
        // Send signaling data to the server
        const endpoint = `/api/consultation/${this.consultationId}/${data.offer ? 'offer' : data.answer ? 'answer' : 'ice-candidate'}`;
        
        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (!result.success) {
                console.error('Signaling data send error:', result.error);
            }
        })
        .catch(error => {
            console.error('Error sending signaling data:', error);
        });
    }
    
    endCall() {
        // Stop all tracks
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
        }
        
        // Close peer connection
        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
        }
        
        // Reset video elements
        this.localVideo.srcObject = null;
        this.remoteVideo.srcObject = null;
        
        // Update UI
        this.updateConnectionStatus('Call ended');
        this.startCallBtn.disabled = false;
        this.endCallBtn.classList.add('d-none');
        this.muteAudioBtn.classList.add('d-none');
        this.muteVideoBtn.classList.add('d-none');
    }
    
    toggleAudio() {
        if (this.localStream) {
            const audioTrack = this.localStream.getAudioTracks()[0];
            if (audioTrack) {
                audioTrack.enabled = !audioTrack.enabled;
                
                // Update button text
                this.muteAudioBtn.textContent = audioTrack.enabled ? 'Mute Audio' : 'Unmute Audio';
                this.muteAudioBtn.classList.toggle('btn-danger', !audioTrack.enabled);
                this.muteAudioBtn.classList.toggle('btn-primary', audioTrack.enabled);
            }
        }
    }
    
    toggleVideo() {
        if (this.localStream) {
            const videoTrack = this.localStream.getVideoTracks()[0];
            if (videoTrack) {
                videoTrack.enabled = !videoTrack.enabled;
                
                // Update button text
                this.muteVideoBtn.textContent = videoTrack.enabled ? 'Turn Off Video' : 'Turn On Video';
                this.muteVideoBtn.classList.toggle('btn-danger', !videoTrack.enabled);
                this.muteVideoBtn.classList.toggle('btn-primary', videoTrack.enabled);
            }
        }
    }
    
    updateConnectionStatus(status) {
        if (this.connectionStatus) {
            this.connectionStatus.textContent = 'Connection status: ' + status;
            
            // Apply appropriate styling based on status
            this.connectionStatus.className = 'alert';
            
            if (status === 'connected') {
                this.connectionStatus.classList.add('alert-success');
            } else if (status === 'connecting' || status === 'Connecting...') {
                this.connectionStatus.classList.add('alert-warning');
            } else if (status === 'disconnected' || status === 'failed' || status === 'Connection lost' || status.includes('Failed')) {
                this.connectionStatus.classList.add('alert-danger');
            } else {
                this.connectionStatus.classList.add('alert-info');
            }
        }
    }
    
    // Method to join an existing consultation
    async joinConsultation() {
        try {
            // Join the consultation via the server
            const response = await fetch(`/api/consultation/${this.consultationId}/join`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Enable the start call button
                if (this.startCallBtn) {
                    this.startCallBtn.disabled = false;
                }
                
                this.updateConnectionStatus('Ready to start call');
                return true;
            } else {
                this.updateConnectionStatus('Failed to join: ' + data.error);
                return false;
            }
        } catch (error) {
            console.error('Error joining consultation:', error);
            this.updateConnectionStatus('Error joining consultation');
            return false;
        }
    }
}

// Initialize video consultation when page loads
document.addEventListener('DOMContentLoaded', function() {
    const consultationRoom = document.getElementById('consultation-room');
    
    if (consultationRoom) {
        const consultationId = consultationRoom.getAttribute('data-consultation-id');
        const userId = consultationRoom.getAttribute('data-user-id');
        const userRole = consultationRoom.getAttribute('data-user-role');
        
        if (consultationId && userId && userRole) {
            // Create and initialize video consultation
            const videoConsultation = new VideoConsultation(consultationId, userId, userRole);
            
            // Join the consultation
            videoConsultation.joinConsultation().then(success => {
                if (success) {
                    console.log('Successfully joined the consultation');
                    
                    // Set up polling for signaling data
                    const pollSignalingData = async () => {
                        try {
                            // In a real app, you would use websockets or server-sent events
                            // Here we're just simulating with a timeout
                            // This is just for demonstration purposes
                            setTimeout(pollSignalingData, 3000);
                        } catch (error) {
                            console.error('Error polling signaling data:', error);
                        }
                    };
                    
                    // Start polling
                    pollSignalingData();
                }
            });
            
            // Expose the video consultation object for debugging
            window.videoConsultation = videoConsultation;
        }
    }
});

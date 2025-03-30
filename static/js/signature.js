// Electronic Signature functionality for MedConsult
// Used for doctor's prescription signatures

class SignatureCanvas {
    constructor(canvasId, hiddenInputId, clearBtnId) {
        this.canvas = document.getElementById(canvasId);
        this.hiddenInput = document.getElementById(hiddenInputId);
        this.clearBtn = document.getElementById(clearBtnId);
        
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        this.isDrawing = false;
        this.points = [];
        
        this.setupCanvas();
        this.setupEventListeners();
    }
    
    setupCanvas() {
        // Set canvas size
        this.canvas.width = this.canvas.offsetWidth;
        this.canvas.height = this.canvas.offsetHeight;
        
        // Set up drawing style
        this.ctx.lineWidth = 2;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.strokeStyle = '#000';
        
        // Clear canvas
        this.clearCanvas();
    }
    
    setupEventListeners() {
        // Mouse events
        this.canvas.addEventListener('mousedown', this.startDrawing.bind(this));
        this.canvas.addEventListener('mousemove', this.draw.bind(this));
        this.canvas.addEventListener('mouseup', this.stopDrawing.bind(this));
        this.canvas.addEventListener('mouseout', this.stopDrawing.bind(this));
        
        // Touch events for mobile devices
        this.canvas.addEventListener('touchstart', this.handleTouchStart.bind(this));
        this.canvas.addEventListener('touchmove', this.handleTouchMove.bind(this));
        this.canvas.addEventListener('touchend', this.stopDrawing.bind(this));
        
        // Clear button
        if (this.clearBtn) {
            this.clearBtn.addEventListener('click', this.clearCanvas.bind(this));
        }
        
        // Window resize
        window.addEventListener('resize', this.handleResize.bind(this));
    }
    
    startDrawing(e) {
        this.isDrawing = true;
        this.points = [];
        
        const pos = this.getPosition(e);
        this.points.push(pos);
        
        this.ctx.beginPath();
        this.ctx.moveTo(pos.x, pos.y);
        
        // Prevent scrolling on touch devices
        e.preventDefault();
    }
    
    draw(e) {
        if (!this.isDrawing) return;
        
        const pos = this.getPosition(e);
        this.points.push(pos);
        
        // Draw a line to the new position
        this.ctx.lineTo(pos.x, pos.y);
        this.ctx.stroke();
        
        // Prevent scrolling on touch devices
        e.preventDefault();
    }
    
    stopDrawing() {
        if (!this.isDrawing) return;
        
        this.isDrawing = false;
        
        // Save signature data to hidden input
        this.saveSignature();
    }
    
    handleTouchStart(e) {
        if (e.touches.length === 1) {
            this.startDrawing(e.touches[0]);
        }
    }
    
    handleTouchMove(e) {
        if (e.touches.length === 1) {
            this.draw(e.touches[0]);
        }
    }
    
    getPosition(e) {
        const rect = this.canvas.getBoundingClientRect();
        
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }
    
    clearCanvas() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Add a light gray border to show the signature area
        this.ctx.strokeStyle = '#ccc';
        this.ctx.lineWidth = 1;
        this.ctx.strokeRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Reset stroke style for drawing
        this.ctx.strokeStyle = '#000';
        this.ctx.lineWidth = 2;
        
        // Clear hidden input
        if (this.hiddenInput) {
            this.hiddenInput.value = '';
        }
        
        this.points = [];
    }
    
    saveSignature() {
        if (this.points.length > 0 && this.hiddenInput) {
            // Convert the canvas to a data URL and store it in the hidden input
            const signatureData = this.canvas.toDataURL();
            this.hiddenInput.value = signatureData;
        }
    }
    
    handleResize() {
        // Save current signature data
        const signatureData = this.canvas.toDataURL();
        
        // Resize canvas
        this.canvas.width = this.canvas.offsetWidth;
        this.canvas.height = this.canvas.offsetHeight;
        
        // Restore drawing settings
        this.ctx.lineWidth = 2;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.strokeStyle = '#000';
        
        // Restore signature if it exists
        if (this.points.length > 0) {
            const img = new Image();
            img.onload = () => {
                this.ctx.drawImage(img, 0, 0);
            };
            img.src = signatureData;
        } else {
            this.clearCanvas();
        }
    }
    
    // Load existing signature data (used when editing a prescription)
    loadSignature(signatureData) {
        if (signatureData && this.canvas) {
            const img = new Image();
            img.onload = () => {
                this.ctx.drawImage(img, 0, 0);
                this.saveSignature();
            };
            img.src = signatureData;
        }
    }
}

// Initialize signature canvas when page loads
document.addEventListener('DOMContentLoaded', function() {
    const signatureCanvasElement = document.getElementById('signature-canvas');
    
    if (signatureCanvasElement) {
        // Create and initialize signature canvas
        const signatureCanvas = new SignatureCanvas(
            'signature-canvas',
            'signature',
            'clear-signature-btn'
        );
        
        // Load existing signature if it exists
        const existingSignature = document.getElementById('existing-signature');
        if (existingSignature) {
            signatureCanvas.loadSignature(existingSignature.value);
        }
        
        // Expose the signature canvas object for debugging
        window.signatureCanvas = signatureCanvas;
        
        // Validate signature before form submission
        const prescriptionForm = document.getElementById('prescription-form');
        if (prescriptionForm) {
            prescriptionForm.addEventListener('submit', function(e) {
                const signatureInput = document.getElementById('signature');
                
                if (!signatureInput || !signatureInput.value) {
                    e.preventDefault();
                    alert('Please sign the prescription before submitting');
                }
            });
        }
    }
});

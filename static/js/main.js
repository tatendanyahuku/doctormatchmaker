// Main JavaScript file for the MedConsult application

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    // Initialize Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'))
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl)
    });
    
    // Fee validation for patient search form
    const specialtySelect = document.getElementById('specialty');
    const proposedFeeInput = document.getElementById('proposed_fee');
    const searchForm = document.getElementById('search-doctor-form');
    const feeRangeInfo = document.getElementById('fee-range-info');
    
    if (specialtySelect && proposedFeeInput && searchForm) {
        specialtySelect.addEventListener('change', function() {
            updateFeeRangeInfo();
        });
        
        proposedFeeInput.addEventListener('input', function() {
            validateFee();
        });
        
        searchForm.addEventListener('submit', function(e) {
            if (!validateFee()) {
                e.preventDefault();
            }
        });
        
        // Initial update
        updateFeeRangeInfo();
    }
    
    function updateFeeRangeInfo() {
        if (!feeRangeInfo) return;
        
        const specialty = specialtySelect.value;
        
        // Get fee range for selected specialty from data attributes
        const minFee = feeRangeInfo.getAttribute(`data-min-${specialty.toLowerCase().replace(' ', '-')}`);
        const maxFee = feeRangeInfo.getAttribute(`data-max-${specialty.toLowerCase().replace(' ', '-')}`);
        
        if (minFee && maxFee) {
            feeRangeInfo.textContent = `Fee range for ${specialty}: $${minFee} - $${maxFee}`;
            feeRangeInfo.classList.remove('d-none');
        } else {
            feeRangeInfo.classList.add('d-none');
        }
    }
    
    function validateFee() {
        if (!feeRangeInfo) return true;
        
        const specialty = specialtySelect.value;
        const proposedFee = parseFloat(proposedFeeInput.value);
        
        // Get fee range for selected specialty
        const minFee = parseFloat(feeRangeInfo.getAttribute(`data-min-${specialty.toLowerCase().replace(' ', '-')}`));
        
        if (isNaN(proposedFee)) {
            showFeeError('Please enter a valid fee amount');
            return false;
        }
        
        if (proposedFee < minFee) {
            showFeeError(`Proposed fee must be at least $${minFee} for ${specialty}`);
            return false;
        }
        
        clearFeeError();
        return true;
    }
    
    function showFeeError(message) {
        let errorElement = document.getElementById('fee-error');
        
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.id = 'fee-error';
            errorElement.className = 'invalid-feedback d-block';
            proposedFeeInput.parentNode.appendChild(errorElement);
        }
        
        errorElement.textContent = message;
        proposedFeeInput.classList.add('is-invalid');
    }
    
    function clearFeeError() {
        const errorElement = document.getElementById('fee-error');
        
        if (errorElement) {
            errorElement.textContent = '';
            errorElement.classList.add('d-none');
        }
        
        proposedFeeInput.classList.remove('is-invalid');
    }
    
    // Handle scheduled time for consultation acceptance
    const acceptConsultationForms = document.querySelectorAll('.accept-consultation-form');
    
    acceptConsultationForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const scheduledTimeInput = this.querySelector('input[name="scheduled_time"]');
            
            if (!scheduledTimeInput.value) {
                e.preventDefault();
                alert('Please select a scheduled time for the consultation');
            }
        });
    });
    
    // Toggle consultation details
    const toggleDetailsBtns = document.querySelectorAll('.toggle-details-btn');
    
    toggleDetailsBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const detailsId = this.getAttribute('data-details-id');
            const detailsContainer = document.getElementById(detailsId);
            
            if (detailsContainer) {
                detailsContainer.classList.toggle('d-none');
                
                if (detailsContainer.classList.contains('d-none')) {
                    this.textContent = 'Show Details';
                } else {
                    this.textContent = 'Hide Details';
                }
            }
        });
    });
});

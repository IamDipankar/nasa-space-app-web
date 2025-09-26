document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const selectAllBtn = document.getElementById('selectAllBtn');
    const runAnalysisBtn = document.getElementById('runAnalysisBtn');
    const statusMessage = document.getElementById('statusMessage');
    const locationInput = document.getElementById('location');
    const checkboxes = document.querySelectorAll('input[name="analysis[]"]');
    const btnText = runAnalysisBtn.querySelector('.btn-text');
    const btnLoading = runAnalysisBtn.querySelector('.btn-loading');

    // State variables
    let isAnalyzing = false;
    let allSelected = false;

    // Initialize
    updateSelectAllButton();
    updateRunAnalysisButton();

    // Event listeners
    selectAllBtn.addEventListener('click', toggleSelectAll);
    runAnalysisBtn.addEventListener('click', runAnalysis);
    locationInput.addEventListener('input', updateRunAnalysisButton);
    
    // Add event listeners to checkboxes
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateSelectAllButton();
            updateRunAnalysisButton();
        });
    });

    // Functions
    function toggleSelectAll() {
        if (isAnalyzing) return;
        
        allSelected = !allSelected;
        checkboxes.forEach(checkbox => {
            checkbox.checked = allSelected;
        });
        
        updateSelectAllButton();
        updateRunAnalysisButton();
        
        // Add visual feedback
        selectAllBtn.style.transform = 'scale(0.95)';
        setTimeout(() => {
            selectAllBtn.style.transform = 'scale(1)';
        }, 150);
    }

    function updateSelectAllButton() {
        const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        const totalCount = checkboxes.length;
        
        allSelected = checkedCount === totalCount;
        
        if (allSelected) {
            selectAllBtn.innerHTML = '<i class="fas fa-check-double"></i> Deselect All';
            selectAllBtn.style.background = 'var(--primary-color)';
            selectAllBtn.style.color = 'white';
            selectAllBtn.style.borderColor = 'var(--primary-color)';
        } else {
            selectAllBtn.innerHTML = '<i class="fas fa-check-double"></i> Select All';
            selectAllBtn.style.background = 'var(--bg-accent)';
            selectAllBtn.style.color = 'var(--text-secondary)';
            selectAllBtn.style.borderColor = 'var(--border-color)';
        }
    }

    function updateRunAnalysisButton() {
        const hasLocation = locationInput.value.trim().length > 0;
        const hasSelectedAnalysis = Array.from(checkboxes).some(cb => cb.checked);
        
        const canRun = hasLocation && hasSelectedAnalysis && !isAnalyzing;
        
        runAnalysisBtn.disabled = !canRun;
        
        if (!hasLocation && !hasSelectedAnalysis) {
            runAnalysisBtn.title = 'Please enter a location and select at least one analysis option';
        } else if (!hasLocation) {
            runAnalysisBtn.title = 'Please enter a location';
        } else if (!hasSelectedAnalysis) {
            runAnalysisBtn.title = 'Please select at least one analysis option';
        } else {
            runAnalysisBtn.title = '';
        }
    }

    function runAnalysis() {
        if (isAnalyzing) return;
        
        const location = locationInput.value.trim();
        const selectedAnalysis = Array.from(checkboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);
        
        if (!location || selectedAnalysis.length === 0) {
            showNotification('Please enter a location and select at least one analysis option', 'error');
            return;
        }
        
        // Start analysis
        isAnalyzing = true;
        
        // Update button state
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';
        runAnalysisBtn.disabled = true;
        
        // Show status message
        statusMessage.style.display = 'flex';
        
        // Disable form elements
        locationInput.disabled = true;
        selectAllBtn.disabled = true;
        checkboxes.forEach(cb => cb.disabled = true);
        
        // Add visual feedback to selected analysis options
        checkboxes.forEach(checkbox => {
            if (checkbox.checked) {
                const label = checkbox.nextElementSibling;
                label.style.opacity = '0.7';
                label.style.transform = 'scale(0.98)';
            }
        });
        
        console.log('Starting analysis for:', {
            location: location,
            analyses: selectedAnalysis
        });
        
        // Here you would typically make an AJAX request to your backend
        // For now, we'll simulate the analysis process
        simulateAnalysis(location, selectedAnalysis);
    }
    
    function simulateAnalysis(location, analyses) {
        // This is a simulation - replace with actual API call
        setTimeout(() => {
            // Reset form state
            resetForm();
            
            // Show completion message
            showNotification(`Analysis completed for ${location}!`, 'success');
            
            // You could redirect to results page or show results here
            // window.location.href = '/results';
        }, 3000); // Simulate 3 seconds of analysis
    }
    
    function resetForm() {
        isAnalyzing = false;
        
        // Reset button state
        btnText.style.display = 'flex';
        btnLoading.style.display = 'none';
        runAnalysisBtn.disabled = false;
        
        // Hide status message
        statusMessage.style.display = 'none';
        
        // Re-enable form elements
        locationInput.disabled = false;
        selectAllBtn.disabled = false;
        checkboxes.forEach(cb => cb.disabled = false);
        
        // Reset visual feedback
        checkboxes.forEach(checkbox => {
            const label = checkbox.nextElementSibling;
            label.style.opacity = '1';
            label.style.transform = 'scale(1)';
        });
        
        updateRunAnalysisButton();
    }
    
    function showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${message}</span>
        `;
        
        // Style notification
        Object.assign(notification.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            background: getNotificationColor(type),
            color: 'white',
            padding: '1rem 1.5rem',
            borderRadius: '0.5rem',
            boxShadow: 'var(--shadow-lg)',
            zIndex: '1000',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.875rem',
            fontWeight: '500',
            maxWidth: '300px',
            transform: 'translateX(100%)',
            transition: 'transform 0.3s ease'
        });
        
        // Add to DOM
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 10);
        
        // Remove after delay
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 4000);
    }
    
    function getNotificationIcon(type) {
        switch (type) {
            case 'success': return 'check-circle';
            case 'error': return 'exclamation-circle';
            case 'warning': return 'exclamation-triangle';
            default: return 'info-circle';
        }
    }
    
    function getNotificationColor(type) {
        switch (type) {
            case 'success': return 'var(--success-color)';
            case 'error': return 'var(--danger-color)';
            case 'warning': return 'var(--warning-color)';
            default: return 'var(--primary-color)';
        }
    }
    
    // Add some nice interactions
    locationInput.addEventListener('focus', function() {
        this.parentElement.style.transform = 'translateY(-2px)';
    });
    
    locationInput.addEventListener('blur', function() {
        this.parentElement.style.transform = 'translateY(0)';
    });
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + Enter to run analysis
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            if (!runAnalysisBtn.disabled) {
                runAnalysis();
            }
        }
        
        // Ctrl/Cmd + A to select all (when not focused on input)
        if ((e.ctrlKey || e.metaKey) && e.key === 'a' && document.activeElement !== locationInput) {
            e.preventDefault();
            if (!isAnalyzing) {
                toggleSelectAll();
            }
        }
    });
    
    // Add loading animation to form while analyzing
    function addLoadingOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'loadingOverlay';
        overlay.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Processing your analysis...</p>
            </div>
        `;
        
        Object.assign(overlay.style, {
            position: 'fixed',
            top: '0',
            left: '0',
            right: '0',
            bottom: '0',
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: '9999',
            backdropFilter: 'blur(5px)'
        });
        
        const spinner = overlay.querySelector('.loading-spinner');
        Object.assign(spinner.style, {
            background: 'white',
            padding: '2rem',
            borderRadius: '1rem',
            textAlign: 'center',
            boxShadow: 'var(--shadow-xl)'
        });
        
        document.body.appendChild(overlay);
    }
});
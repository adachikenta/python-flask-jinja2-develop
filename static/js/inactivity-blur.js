/**
 * Inactivity Blur Overlay
 * Creates a blur overlay after 5 minutes of inactivity
 * Any browser interaction (mouse movement, click, keypress) will remove the overlay
 */

// Configuration
//const INACTIVITY_TIMEOUT = 5 * 60 * 1000; // 5 minutes in milliseconds
const INACTIVITY_TIMEOUT = 30 * 1000; // 30 seconds in milliseconds

// State tracking
let inactivityTimer = null;
let overlayActive = false;

// Initialize when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Create the overlay element but don't add it to the DOM yet
    createOverlay();
    
    // Start monitoring for inactivity
    resetInactivityTimer();
    
    // Add event listeners for user activity
    setupActivityListeners();
});

// Create the overlay element
function createOverlay() {
    // Check if overlay already exists (in case of page refreshes)
    if (document.getElementById('inactivity-overlay')) {
        return;
    }
    
    // Create the overlay element
    const overlay = document.createElement('div');
    overlay.id = 'inactivity-overlay';
    
    // Add styles for the overlay
    const style = document.createElement('style');
    style.textContent = `
        #inactivity-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(255, 255, 255, 0.3);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            z-index: 9999;
            display: none;
            transition: opacity 0.3s ease;
            opacity: 0;
        }
        
        #inactivity-overlay.active {
            display: block;
            opacity: 1;
        }
    `;
    
    // Add the style to the document head
    document.head.appendChild(style);
    
    // Add the overlay to the document body (but keep it hidden)
    document.body.appendChild(overlay);
}

// Reset the inactivity timer
function resetInactivityTimer() {
    // Clear any existing timer
    if (inactivityTimer) {
        clearTimeout(inactivityTimer);
    }
    
    // Set a new timer
    inactivityTimer = setTimeout(() => {
        showOverlay();
    }, INACTIVITY_TIMEOUT);
}

// Show the overlay
function showOverlay() {
    const overlay = document.getElementById('inactivity-overlay');
    if (overlay && !overlayActive) {
        overlay.classList.add('active');
        overlayActive = true;
    }
}

// Hide the overlay
function hideOverlay() {
    const overlay = document.getElementById('inactivity-overlay');
    if (overlay && overlayActive) {
        overlay.classList.remove('active');
        overlayActive = false;
        
        // Reset the timer when the overlay is hidden
        resetInactivityTimer();
    }
}

// Set up event listeners for user activity
function setupActivityListeners() {
    // List of events to monitor
    const events = [
        'mousemove', 
        'mousedown', 
        'click', 
        'touchstart', 
        'touchmove', 
        'keydown', 
        'wheel', 
        'DOMMouseScroll', 
        'mousewheel'
    ];
    
    // Add event listeners for each event type
    events.forEach(event => {
        document.addEventListener(event, handleUserActivity, { passive: true });
    });
}

// Handle user activity
function handleUserActivity() {
    // If overlay is active, hide it
    if (overlayActive) {
        hideOverlay();
    }
    
    // Reset the inactivity timer
    resetInactivityTimer();
}

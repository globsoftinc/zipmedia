document.addEventListener('DOMContentLoaded', () => {
    const convertBtn = document.getElementById('convert-btn');
    const videoUrlInput = document.getElementById('video-url');

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
            // Close mobile menu if open
            document.querySelector('.nav-links').classList.remove('active');
        });
    });

    // Hamburger Menu Toggle
    const hamburger = document.querySelector('.hamburger-menu');
    const navLinks = document.querySelector('.nav-links');

    if (hamburger) {
        hamburger.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });
    }

    // Basic input validation and button interaction
    convertBtn.addEventListener('click', async () => {
        const url = videoUrlInput.value.trim();

        if (!url) {
            shakeInput();
            return;
        }

        if (!isValidUrl(url)) {
            showFlashMessage('Please enter a valid YouTube URL', 'error');
            return;
        }

        // Backend integration
        const originalText = convertBtn.innerHTML;
        convertBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
        convertBtn.disabled = true;

        try {
            // Collect browser headers to avoid IP blocking
            const browserHeaders = getBrowserHeaders();
            
            console.log('Sending request with browser fingerprint');

            const response = await fetch('/api/convert', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    url: url,
                    quality: 4,  // High quality audio
                    headers: browserHeaders  // Send browser headers to backend
                }),
            });

            const data = await response.json();

            if (data.error) {
                showFlashMessage('Error: ' + data.error, 'error');
            } else {
                // Show cache status
                if (data.cached) {
                    showFlashMessage('Found in cache!  Starting instant download...', 'success');
                } else {
                    showFlashMessage('Conversion complete! Starting download...', 'success');
                }
                
                // Trigger download
                const a = document.createElement('a');
                a.href = data.download_url;
                a.download = '';  // Browser handles filename from Content-Disposition
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }
        } catch (error) {
            console.error('Error:', error);
            showFlashMessage('An error occurred. Please try again.', 'error');
        } finally {
            convertBtn.innerHTML = originalText;
            convertBtn.disabled = false;
        }
    });

    function shakeInput() {
        const inputGroup = document.querySelector('.input-group');
        inputGroup.style.animation = 'shake 0.5s';
        inputGroup.style.borderColor = '#ff0080';

        setTimeout(() => {
            inputGroup.style.animation = 'none';
            inputGroup.style.borderColor = 'rgba(255, 255, 255, 0.1)';
        }, 500);
    }

    function isValidUrl(string) {
    try {
        const urlObj = new URL(string);
        // Check for all YouTube domains
        const validDomains = ['youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com'];
        return validDomains.some(domain => urlObj.hostname === domain || urlObj.hostname.endsWith('.' + domain));
    } catch (_) {
        return false;
    }
}

    // Add shake animation keyframes dynamically
    const styleSheet = document.createElement("style");
    styleSheet.innerText = `
        @keyframes shake {
            0% { transform: translateX(0); }
            25% { transform: translateX(-10px); }
            50% { transform: translateX(10px); }
            75% { transform: translateX(-10px); }
            100% { transform: translateX(0); }
        }
    `;
    document.head.appendChild(styleSheet);
});


/**
 * Collect browser headers to send to backend
 * This helps avoid IP blocking by using user's real browser fingerprint
 */
function getBrowserHeaders() {
    return {
        "User-Agent": navigator.userAgent,
        "Accept-Language": navigator.language || navigator.userLanguage || "en-US",
        "Sec-Ch-Ua": getSecChUa(),
        "Sec-Ch-Ua-Mobile": isMobile() ? "?1" : "?0",
        "Sec-Ch-Ua-Platform": getPlatform(),
        "Screen-Resolution": `${window.screen.width}x${window.screen.height}`,
        "Timezone": Intl.DateTimeFormat().resolvedOptions().timeZone,
        "Color-Depth": window.screen.colorDepth.toString(),
    };
}


/**
 * Generate Sec-Ch-Ua header based on browser
 */
function getSecChUa() {
    const ua = navigator.userAgent;
    
    if (ua.includes('Edg/')) {
        const version = ua.match(/Edg\/(\d+)/)?.[1] || '120';
        return `"Microsoft Edge";v="${version}", "Chromium";v="${version}", "Not_A Brand";v="99"`;
    } else if (ua.includes('Chrome/')) {
        const version = ua.match(/Chrome\/(\d+)/)?.[1] || '120';
        return `"Chromium";v="${version}", "Google Chrome";v="${version}", "Not_A Brand";v="99"`;
    } else if (ua.includes('Firefox/')) {
        return ''; // Firefox doesn't send this header
    } else if (ua.includes('Safari/') && !ua.includes('Chrome')) {
        return ''; // Safari doesn't send this header
    }
    
    return '';
}


/**
 * Detect if user is on mobile
 */
function isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}


/**
 * Get platform name for Sec-Ch-Ua-Platform header
 */
function getPlatform() {
    const ua = navigator.userAgent;
    
    if (ua.includes('Windows')) return '"Windows"';
    if (ua.includes('Mac')) return '"macOS"';
    if (ua.includes('Linux') && ! ua.includes('Android')) return '"Linux"';
    if (ua.includes('Android')) return '"Android"';
    if (ua.includes('iPhone') || ua.includes('iPad')) return '"iOS"';
    if (ua.includes('CrOS')) return '"Chrome OS"';
    
    return '"Unknown"';
}


/**
 * Show flash message with type (success/error)
 */
function showFlashMessage(message, type = 'success') {
    // Remove existing flash messages
    const existingFlash = document.querySelector('.flash-message');
    if (existingFlash) {
        existingFlash.remove();
    }
    
    const flashDiv = document.createElement('div');
    flashDiv.className = `flash-message flash-${type}`;
    
    const icon = type === 'success' 
        ? '<i class="fa-solid fa-circle-check"></i>' 
        : '<i class="fa-solid fa-circle-exclamation"></i>';
    
    flashDiv.innerHTML = `${icon} ${message}`;
    document.body.appendChild(flashDiv);

    // Remove after 3 seconds
    setTimeout(() => {
        flashDiv.style.animation = 'slideOut 0.5s ease-in forwards';
        setTimeout(() => {
            if (document.body.contains(flashDiv)) {
                document.body.removeChild(flashDiv);
            }
        }, 500);
    }, 3000);
}

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
    convertBtn.addEventListener('click', () => {
        const url = videoUrlInput.value.trim();

        if (!url) {
            shakeInput();
            return;
        }

        if (!isValidUrl(url)) {
            alert('Please enter a valid YouTube URL');
            return;
        }

        // Backend integration
        const originalText = convertBtn.innerHTML;
        convertBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
        convertBtn.disabled = true;

        fetch('/api/convert', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url }),
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                } else {
                    // Trigger download
                    const a = document.createElement('a');
                    a.href = data.download_url;
                    a.download = ''; // Browser handles filename from Content-Disposition
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            })
            .finally(() => {
                convertBtn.innerHTML = originalText;
                convertBtn.disabled = false;
            });
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
            new URL(string);
            return string.includes('youtube.com') || string.includes('youtu.be');
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

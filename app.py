from flask import Flask, render_template, request, jsonify, Response, stream_with_context, make_response
import yt_dlp
import requests
from datetime import datetime
import logging
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/convert', methods=['POST'])
def convert():
    data = request.get_json()
    url = data.get('url')
    user_cookies = data.get('cookies', {})  # Get cookies from frontend

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        logger.info(f"Converting video: {url}")
        logger.info(f"Received {len(user_cookies)} cookies from user")
        
        # Convert cookies dict to cookie file format for yt-dlp
        cookie_file = '/tmp/cookies.txt'
        if user_cookies:
            with open(cookie_file, 'w') as f:
                f.write('# Netscape HTTP Cookie File\n')
                for key, value in user_cookies.items():
                    # Format: domain flag path secure expiration name value
                    f.write(f'.youtube.com\tTRUE\t/\tTRUE\t0\t{key}\t{value}\n')
            logger.info("Cookie file created successfully")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'socket_timeout': 30,
        }
        
        # Add cookie file if cookies were provided
        if user_cookies:
            ydl_opts['cookiefile'] = cookie_file
            logger.info("Using user cookies for extraction")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info['url']
            title = info.get('title', 'audio')
            
            # Always MP3/Audio
            ext = 'mp3'
            
            logger.info(f"Successfully processed: {title}")
            logger.info(f"Video URL: {video_url[:100]}...")
            
            # FIX: Use urlencode to properly format query parameters
            download_params = urllib.parse.urlencode({
                'url': video_url,
                'title': title,
                'ext': ext
            })
            
            return jsonify({
                'title': title,
                'download_url': f'/api/download?{download_params}'
            })

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        error_msg = str(e)
        
        # Provide helpful error messages
        if "Sign in to confirm you're not a bot" in error_msg:
            return jsonify({'error': 'Please log in to your YouTube account and try again'}), 400
        elif "Login required" in error_msg or "age-restricted" in error_msg.lower():
            return jsonify({'error': 'This video requires age verification.  Please log in to YouTube and try again'}), 400
        else:
            return jsonify({'error': error_msg}), 500

@app.route('/api/download')
def download():
    url = request.args.get('url')
    title = request.args.get('title', 'audio')
    ext = request.args.get('ext', 'mp3')
    
    if not url:
        logger.error("Missing URL in download request")
        return "Missing URL", 400

    try:
        logger.info(f"Starting download for: {title}")
        req = requests.get(url, stream=True, timeout=30)
        
        if req.status_code != 200:
            logger.error(f"Failed to get video URL: {req.status_code}")
            return f"Failed to download: HTTP {req.status_code}", 400
        
        # Sanitize title for the filename header to avoid UnicodeEncodeError
        safe_title = title.encode('ascii', 'ignore').decode('ascii')
        safe_title = "".join([c if c.isalnum() or c in " .-_" else "_" for c in safe_title])
        
        logger.info(f"Downloading: {safe_title}. {ext}")
        
        return Response(
            stream_with_context(req.iter_content(chunk_size=8192)),
            content_type='audio/mpeg',
            headers={
                'Content-Disposition': f'attachment; filename="{safe_title}.{ext}"',
                'Content-Length': req.headers.get('content-length', '')
            }
        )
    except requests.exceptions. Timeout:
        logger.error("Download timeout")
        return "Download timed out", 504
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return f"Download failed: {str(e)}", 500

@app.route("/robots.txt")
def robots():
    """Serve robots.txt"""
    return app.send_static_file('robots.txt')

@app.route("/sitemap.xml")
def sitemap():
    """Generate sitemap.xml for ZipMedia"""
    pages = []
    
    # Homepage
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'daily',
        'priority': '1.0'
    })
    
    # Converter Page
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/converter',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'weekly',
        'priority': '0.9'
    })
    
    # Features Page
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/features',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'monthly',
        'priority': '0.8'
    })
    
    # How It Works Page
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/how-it-works',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'monthly',
        'priority': '0.8'
    })
    
    # FAQ Page
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/faq',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'monthly',
        'priority': '0.7'
    })
    
    # About Page
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/about',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'monthly',
        'priority': '0.7'
    })
    
    # Privacy Policy
    pages.append({
        'loc': 'https://globsoft.tech/privacy-policy',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'quarterly',
        'priority': '0.6'
    })
    
    # Terms of Service
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/terms',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'quarterly',
        'priority': '0.6'
    })
    
    # Contact Page
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/contact',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'monthly',
        'priority': '0.6'
    })
    
    # API Documentation
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/api/docs',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'weekly',
        'priority': '0.7'
    })
    
    # Blog/Resources
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/blog',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'weekly',
        'priority': '0.8'
    })
    
    # Build XML
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{page["loc"]}</loc>\n'
        sitemap_xml += f'    <lastmod>{page["lastmod"]}</lastmod>\n'
        sitemap_xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        sitemap_xml += f'    <priority>{page["priority"]}</priority>\n'
        sitemap_xml += '  </url>\n'
    
    sitemap_xml += '</urlset>'
    
    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response

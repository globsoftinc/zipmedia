from flask import Flask, render_template, request, jsonify, Response, stream_with_context, make_response
import requests
from datetime import datetime
import logging
import urllib.parse
import re
from urllib.parse import urlparse, parse_qs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================
# YouTube to MP3 Converter (cnvmp3)
# ============================================

class YouTubeToMP3Converter:
    """Handles YouTube to MP3 conversion via cnvmp3.com API"""
    
    BASE_URL = "https://cnvmp3.com"
    
    def __init__(self, user_headers=None, user_ip=None):
        """
        Initialize converter with user's browser headers
        
        Args:
            user_headers: Headers from user's browser request
            user_ip: User's IP address for X-Forwarded-For
        """
        self.session = requests.Session()
        self.user_ip = user_ip
        
        # Build headers from user's browser (passed from frontend)
        self.session.headers.update({
            "User-Agent": user_headers.get("User-Agent", "Mozilla/5.0"),
            "Accept": "*/*",
            "Accept-Language": user_headers.get("Accept-Language", "en-US,en;q=0.9"),
            "Content-Type": "application/json",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/v51",
            "sec-ch-ua": user_headers.get("Sec-Ch-Ua", ""),
            "sec-ch-ua-mobile": user_headers.get("Sec-Ch-Ua-Mobile", "?0"),
            "sec-ch-ua-platform": user_headers.get("Sec-Ch-Ua-Platform", ""),
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        
        # Forward user's IP if available
        if user_ip:
            self.session.headers["X-Forwarded-For"] = user_ip
            self.session.headers["X-Real-IP"] = user_ip
    
    @staticmethod
    def extract_video_id(url):
        """Extract YouTube video ID from URL"""
        parsed = urlparse(url)
        if parsed.hostname in ('www.youtube.com', 'youtube.com'):
            if parsed.path == '/watch':
                return parse_qs(parsed.query).get('v', [None])[0]
            elif parsed.path.startswith('/shorts/'):
                return parsed.path.split('/')[2]
        elif parsed.hostname == 'youtu.be':
            return parsed.path[1:]
        return None
    
    def _post(self, endpoint, payload):
        """Make POST request to cnvmp3 API"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = self.session.post(url, json=payload, timeout=60)
            
            if not response.content:
                return {"success": False, "error": "Empty response from server"}
            
            try:
                return response.json()
            except requests.exceptions.JSONDecodeError:
                return {"success": False, "error": f"Invalid response: {response.text[:100]}"}
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
    
    def check_database(self, youtube_id, quality=4, format_value=1):
        """Check if video exists in cnvmp3 cache"""
        payload = {
            "youtube_id": youtube_id,
            "quality": quality,
            "formatValue": format_value
        }
        return self._post("check_database.php", payload)
    
    def get_video_data(self, youtube_url, token="1234"):
        """Get video metadata (title)"""
        payload = {
            "url": youtube_url,
            "token": token
        }
        return self._post("get_video_data.php", payload)
    
    def download_video_ucep(self, youtube_url, title, quality=4, format_value=1):
        """Request conversion and get download URL"""
        payload = {
            "url": youtube_url,
            "quality": quality,
            "formatValue": format_value,
            "title": title
        }
        return self._post("download_video_ucep.php", payload)
    
    def insert_to_database(self, youtube_id, title, server_path, quality=4, format_value=1):
        """Cache the conversion result"""
        payload = {
            "youtube_id": youtube_id,
            "title": title,
            "server_path": server_path,
            "quality": quality,
            "formatValue": format_value
        }
        return self._post("insert_to_database.php", payload)
    
    def convert(self, youtube_url, quality=4):
        """
        Main conversion method
        
        Returns:
            dict with 'success', 'title', 'download_url' or 'error'
        """
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            return {"success": False, "error": "Invalid YouTube URL"}
        
        logger.info(f"Processing video ID: {video_id}")
        
        # Step 1: Check cache
        db_check = self.check_database(video_id, quality)
        
        if db_check.get('success') and db_check.get('data'):
            cached_data = db_check['data']
            logger.info(f"Found in cache: {cached_data.get('title')}")
            return {
                "success": True,
                "title": cached_data.get('title', f'video_{video_id}'),
                "download_url": cached_data.get('server_path'),
                "cached": True
            }
        
        # Step 2: Get video info
        video_data = self.get_video_data(youtube_url)
        
        if not video_data.get('success'):
            return {"success": False, "error": video_data.get('error', 'Failed to get video info')}
        
        title = video_data.get('title', f'video_{video_id}')
        logger.info(f"Video title: {title}")
        
        # Step 3: Convert
        conversion = self.download_video_ucep(youtube_url, title, quality)
        
        if not conversion.get('success'):
            return {"success": False, "error": conversion.get('error', 'Conversion failed')}
        
        download_url = conversion.get('download_link')
        
        if not download_url:
            return {"success": False, "error": "No download link received"}
        
        # Step 4: Cache for future (non-blocking, ignore errors)
        try:
            self.insert_to_database(video_id, title, download_url, quality)
        except Exception as e:
            logger.warning(f"Failed to cache: {e}")
        
        return {
            "success": True,
            "title": title,
            "download_url": download_url,
            "cached": False
        }


def get_user_ip(req):
    """Extract real user IP from request"""
    # Check common proxy headers
    if req.headers.get('X-Forwarded-For'):
        # X-Forwarded-For can contain multiple IPs, first one is the client
        return req.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif req.headers.get('X-Real-IP'):
        return req.headers.get('X-Real-IP')
    elif req.headers.get('CF-Connecting-IP'):  # Cloudflare
        return req.headers.get('CF-Connecting-IP')
    else:
        return req.remote_addr


def get_user_headers(req):
    """Extract relevant headers from user's request"""
    return {
        "User-Agent": req.headers.get("User-Agent", ""),
        "Accept-Language": req.headers.get("Accept-Language", "en-US,en;q=0.9"),
        "Sec-Ch-Ua": req.headers.get("Sec-Ch-Ua", ""),
        "Sec-Ch-Ua-Mobile": req.headers.get("Sec-Ch-Ua-Mobile", "?0"),
        "Sec-Ch-Ua-Platform": req.headers.get("Sec-Ch-Ua-Platform", ""),
    }


# ============================================
# Routes
# ============================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/convert', methods=['POST'])
def convert():
    data = request.get_json()
    url = data.get('url')
    quality = data.get('quality', 4)  # Default quality
    
    # Get browser info from frontend (optional, fallback to server-side extraction)
    frontend_headers = data.get('headers', {})
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Validate YouTube URL
    if 'youtube.com' not in url and 'youtu.be' not in url:
        return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
    
    try:
        logger.info(f"Converting video: {url}")
        
        # Get user's real IP and headers
        user_ip = get_user_ip(request)
        
        # Merge frontend headers with server-extracted headers (frontend takes priority)
        user_headers = get_user_headers(request)
        user_headers.update(frontend_headers)
        
        logger.info(f"User IP: {user_ip}")
        logger.info(f"User-Agent: {user_headers.get('User-Agent', 'unknown')[:50]}...")
        
        # Initialize converter with user's browser fingerprint
        converter = YouTubeToMP3Converter(
            user_headers=user_headers,
            user_ip=user_ip
        )
        
        # Convert video
        result = converter.convert(url, quality=quality)
        
        if not result.get('success'):
            return jsonify({'error': result.get('error', 'Conversion failed')}), 400
        
        title = result['title']
        download_url = result['download_url']
        
        logger.info(f"Successfully processed: {title} (cached: {result.get('cached', False)})")
        
        # Build proxy download URL
        download_params = urllib.parse.urlencode({
            'url': download_url,
            'title': title,
            'ext': 'mp3'
        })
        
        return jsonify({
            'title': title,
            'download_url': f'/api/download?{download_params}',
            'cached': result.get('cached', False)
        })

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


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
        
        # Use user's headers for the download request too
        user_headers = get_user_headers(request)
        user_ip = get_user_ip(request)
        
        download_headers = {
            "User-Agent": user_headers.get("User-Agent", "Mozilla/5.0"),
            "Accept": "*/*",
            "Accept-Language": user_headers.get("Accept-Language", "en-US,en;q=0.9"),
            "Referer": "https://cnvmp3.com/",
        }
        
        if user_ip:
            download_headers["X-Forwarded-For"] = user_ip
        
        req = requests.get(url, headers=download_headers, stream=True, timeout=120)
        
        if req.status_code != 200:
            logger.error(f"Failed to get audio: {req.status_code}")
            return f"Failed to download: HTTP {req.status_code}", 400
        
        # Sanitize title for the filename header
        safe_title = title.encode('ascii', 'ignore').decode('ascii')
        safe_title = "".join([c if c.isalnum() or c in " .-_" else "_" for c in safe_title])
        
        if not safe_title:
            safe_title = "audio"
        
        logger.info(f"Downloading: {safe_title}.{ext}")
        
        return Response(
            stream_with_context(req.iter_content(chunk_size=8192)),
            content_type='audio/mpeg',
            headers={
                'Content-Disposition': f'attachment; filename="{safe_title}.{ext}"',
                'Content-Length': req.headers.get('content-length', '')
            }
        )
    except requests.exceptions.Timeout:
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
    pages = [
        {'loc': 'https://zipmedia.globsoft.tech/', 'changefreq': 'daily', 'priority': '1.0'},
        {'loc': 'https://zipmedia.globsoft.tech/converter', 'changefreq': 'weekly', 'priority': '0.9'},
        {'loc': 'https://zipmedia.globsoft.tech/features', 'changefreq': 'monthly', 'priority': '0.8'},
        {'loc': 'https://zipmedia.globsoft.tech/how-it-works', 'changefreq': 'monthly', 'priority': '0.8'},
        {'loc': 'https://zipmedia.globsoft.tech/faq', 'changefreq': 'monthly', 'priority': '0.7'},
        {'loc': 'https://zipmedia.globsoft.tech/about', 'changefreq': 'monthly', 'priority': '0.7'},
        {'loc': 'https://globsoft.tech/privacy-policy', 'changefreq': 'quarterly', 'priority': '0.6'},
        {'loc': 'https://zipmedia.globsoft.tech/terms', 'changefreq': 'quarterly', 'priority': '0.6'},
        {'loc': 'https://zipmedia.globsoft.tech/contact', 'changefreq': 'monthly', 'priority': '0.6'},
        {'loc': 'https://zipmedia.globsoft.tech/api/docs', 'changefreq': 'weekly', 'priority': '0.7'},
        {'loc': 'https://zipmedia.globsoft.tech/blog', 'changefreq': 'weekly', 'priority': '0.8'},
    ]
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{page["loc"]}</loc>\n'
        sitemap_xml += f'    <lastmod>{today}</lastmod>\n'
        sitemap_xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        sitemap_xml += f'    <priority>{page["priority"]}</priority>\n'
        sitemap_xml += '  </url>\n'
    
    sitemap_xml += '</urlset>'
    
    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response
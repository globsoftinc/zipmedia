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
# YouTube to MP3 Converter (cnvmp3 API ONLY)
# ============================================

class YouTubeToMP3Converter:
    """Handles YouTube to MP3 conversion via cnvmp3.com API"""
    
    BASE_URL = "https://cnvmp3.com"
    
    def __init__(self, user_headers=None, user_ip=None):
        self.session = requests.Session()
        self.user_ip = user_ip
        
        if user_headers is None:
            user_headers = {}
        
        self.session.headers.update({
            "User-Agent": user_headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            "Accept": "*/*",
            "Accept-Language": user_headers.get("Accept-Language", "en-US,en;q=0.9"),
            "Content-Type": "application/json",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/v51",
            "sec-ch-ua": user_headers.get("Sec-Ch-Ua", '"Chromium";v="120", "Google Chrome";v="120"'),
            "sec-ch-ua-mobile": user_headers.get("Sec-Ch-Ua-Mobile", "? 0"),
            "sec-ch-ua-platform": user_headers.get("Sec-Ch-Ua-Platform", '"Windows"'),
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        
        if user_ip:
            self.session.headers["X-Forwarded-For"] = user_ip
            self.session.headers["X-Real-IP"] = user_ip
    
    @staticmethod
    def extract_video_id(url):
        """Extract YouTube video ID from any YouTube URL format"""
        if not url:
            return None
            
        # Clean the URL
        url = url.strip()
        
        parsed = urlparse(url)
        
        # Standard youtube.com/watch?v=VIDEO_ID
        if parsed.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
            if parsed.path == '/watch':
                return parse_qs(parsed.query).get('v', [None])[0]
            # Shorts: youtube.com/shorts/VIDEO_ID
            elif '/shorts/' in parsed.path:
                parts = parsed.path.split('/shorts/')
                if len(parts) > 1:
                    video_id = parts[1].split('/')[0].split('?')[0]
                    return video_id if video_id else None
            # Embed: youtube.com/embed/VIDEO_ID
            elif '/embed/' in parsed.path:
                parts = parsed.path.split('/embed/')
                if len(parts) > 1:
                    video_id = parts[1].split('/')[0].split('?')[0]
                    return video_id if video_id else None
            # Live: youtube.com/live/VIDEO_ID
            elif '/live/' in parsed.path:
                parts = parsed.path.split('/live/')
                if len(parts) > 1:
                    video_id = parts[1].split('/')[0].split('?')[0]
                    return video_id if video_id else None
        
        # Short URL: youtu.be/VIDEO_ID? si=TRACKING
        elif parsed.hostname == 'youtu.be':
            # Path is /VIDEO_ID
            video_id = parsed.path.lstrip('/')
            # Remove any trailing stuff
            video_id = video_id.split('/')[0].split('?')[0]
            return video_id if video_id else None
        
        return None
    
    @staticmethod
    def normalize_youtube_url(url):
        """Convert any YouTube URL to standard format"""
        video_id = YouTubeToMP3Converter.extract_video_id(url)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return None
    
    def _post(self, endpoint, payload):
        """Make POST request to cnvmp3 API"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        logger.info(f"API Call: {endpoint}")
        logger.debug(f"Payload: {payload}")
        
        try:
            response = self.session.post(url, json=payload, timeout=60)
            
            logger.info(f"Response status: {response.status_code}")
            
            if not response.content:
                logger.error("Empty response from server")
                return {"success": False, "error": "Empty response from server"}
            
            try:
                result = response.json()
                logger.debug(f"Response: {result}")
                return result
            except Exception as e:
                logger.error(f"JSON decode error: {e}")
                logger.error(f"Raw response: {response.text[:500]}")
                return {"success": False, "error": f"Invalid response: {response.text[:100]}"}
                
        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            return {"success": False, "error": "Request timed out"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
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
        # Extract video ID
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            return {"success": False, "error": "Invalid YouTube URL - could not extract video ID"}
        
        # Normalize URL to standard format
        normalized_url = self.normalize_youtube_url(youtube_url)
        
        logger.info(f"Video ID: {video_id}")
        logger.info(f"Normalized URL: {normalized_url}")
        
        # Step 1: Check cache
        logger.info("Step 1: Checking cache...")
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
        
        logger.info("Not in cache, proceeding with conversion...")
        
        # Step 2: Get video info
        logger.info("Step 2: Getting video info...")
        video_data = self.get_video_data(normalized_url)
        
        if not video_data.get('success'):
            error_msg = video_data.get('error', 'Failed to get video info')
            logger.error(f"Failed to get video data: {error_msg}")
            return {"success": False, "error": error_msg}
        
        title = video_data.get('title', f'video_{video_id}')
        logger.info(f"Video title: {title}")
        
        # Step 3: Convert
        logger.info("Step 3: Converting...")
        conversion = self.download_video_ucep(normalized_url, title, quality)
        
        if not conversion.get('success'):
            error_msg = conversion.get('error', 'Conversion failed')
            logger.error(f"Conversion failed: {error_msg}")
            return {"success": False, "error": error_msg}
        
        download_url = conversion.get('download_link')
        
        if not download_url:
            logger.error("No download link in response")
            return {"success": False, "error": "No download link received"}
        
        logger.info(f"Download URL: {download_url}")
        
        # Step 4: Cache for future
        logger.info("Step 4: Caching result...")
        try:
            self.insert_to_database(video_id, title, download_url, quality)
            logger.info("Cached successfully")
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
    if req.headers.get('X-Forwarded-For'):
        return req.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif req.headers.get('X-Real-IP'):
        return req.headers.get('X-Real-IP')
    elif req.headers.get('CF-Connecting-IP'):
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
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    url = data.get('url', '').strip()
    quality = data.get('quality', 4)
    frontend_headers = data.get('headers', {})
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Validate YouTube URL
    valid_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com']
    if not any(domain in url for domain in valid_domains):
        return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
    
    try:
        logger.info(f"=== New conversion request ===")
        logger.info(f"Original URL: {url}")
        
        # Get user's real IP and headers
        user_ip = get_user_ip(request)
        user_headers = get_user_headers(request)
        user_headers.update(frontend_headers)
        
        logger.info(f"User IP: {user_ip}")
        
        # Initialize converter
        converter = YouTubeToMP3Converter(
            user_headers=user_headers,
            user_ip=user_ip
        )
        
        # Convert video
        result = converter.convert(url, quality=quality)
        
        if not result.get('success'):
            error_msg = result.get('error', 'Conversion failed')
            logger.error(f"Conversion failed: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        title = result['title']
        download_url = result['download_url']
        
        logger.info(f"Success! Title: {title}")
        
        # Sanitize title for URL
        safe_title = re.sub(r'[^\w\s\-]', '', title)
        safe_title = re.sub(r'\s+', ' ', safe_title).strip()
        if not safe_title:
            safe_title = "audio"
        
        # Build proxy download URL
        download_params = urllib.parse.urlencode({
            'url': download_url,
            'title': safe_title,
            'ext': 'mp3'
        }, quote_via=urllib.parse.quote)
        
        return jsonify({
            'title': title,
            'download_url': f'/api/download?{download_params}',
            'cached': result.get('cached', False)
        })

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500


@app.route('/api/download')
def download():
    url = request.args.get('url')
    title = request.args.get('title', 'audio')
    ext = request.args.get('ext', 'mp3')
    
    if not url:
        logger.error("Missing URL in download request")
        return "Missing URL", 400

    try:
        logger.info(f"=== Download request ===")
        logger.info(f"Title: {title}")
        logger.info(f"URL: {url[:100]}...")
        
        user_headers = get_user_headers(request)
        user_ip = get_user_ip(request)
        
        download_headers = {
            "User-Agent": user_headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
            "Accept": "*/*",
            "Accept-Language": user_headers.get("Accept-Language", "en-US,en;q=0.9"),
            "Referer": "https://cnvmp3.com/",
        }
        
        if user_ip:
            download_headers["X-Forwarded-For"] = user_ip
        
        req = requests.get(url, headers=download_headers, stream=True, timeout=120)
        
        logger.info(f"Download response: {req.status_code}")
        
        if req.status_code != 200:
            logger.error(f"Download failed: HTTP {req.status_code}")
            return f"Failed to download: HTTP {req.status_code}", 400
        
        # Sanitize filename
        safe_title = re.sub(r'[^\w\s\-\.]', '', title)
        safe_title = re.sub(r'\s+', ' ', safe_title).strip()
        if not safe_title or len(safe_title) < 2:
            safe_title = "audio_download"
        
        filename = f"{safe_title}.{ext}"
        logger.info(f"Filename: {filename}")
        
        content_length = req.headers.get('content-length', '')
        
        response = Response(
            stream_with_context(req.iter_content(chunk_size=8192)),
            content_type='audio/mpeg'
        )
        
        # Set download headers
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{urllib.parse.quote(filename)}'
        if content_length:
            response.headers['Content-Length'] = content_length
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        
        return response
        
    except requests.exceptions.Timeout:
        logger.error("Download timeout")
        return "Download timed out", 504
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Download failed: {str(e)}", 500


@app.route("/robots.txt")
def robots():
    return app.send_static_file('robots.txt')


@app.route("/sitemap.xml")
def sitemap():
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
        sitemap_xml += f'  <url>\n'
        sitemap_xml += f'    <loc>{page["loc"]}</loc>\n'
        sitemap_xml += f'    <lastmod>{today}</lastmod>\n'
        sitemap_xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        sitemap_xml += f'    <priority>{page["priority"]}</priority>\n'
        sitemap_xml += f'  </url>\n'
    
    sitemap_xml += '</urlset>'
    
    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response

from flask import Flask, render_template, request, jsonify, Response, stream_with_context, make_response
from pytube import YouTube
import requests
from datetime import datetime
import urllib.parse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app. route('/api/convert', methods=['POST'])
def convert():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        # Timeout for YouTube object creation
        yt = YouTube(url, timeout=10)
        
        # Get the best audio stream
        audio_stream = yt.streams.filter(only_audio=True).first()
        
        if not audio_stream:
            return jsonify({'error': 'No audio stream available'}), 400
        
        title = yt.title
        ext = 'mp3'
        filesize = audio_stream.filesize
        
        # Warn if file is very large
        if filesize > 50 * 1024 * 1024:  # 50 MB
            logger.warning(f"Large audio file: {filesize / 1024 / 1024:.2f} MB")
        
        # Get the actual download URL from pytube
        download_url = audio_stream.url
        
        logger.info(f"Successfully processed: {title} ({filesize / 1024 / 1024:.2f} MB)")
        
        return jsonify({
            'title': title,
            'download_url': f'/api/download? url={urllib.parse.quote(download_url)}&title={urllib.parse.quote(title)}&ext={ext}',
            'filesize': filesize
        })

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out.  Please try again.'}), 504
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': 'Failed to process video. Please try another video.'}), 500

@app.route('/api/download')
def download():
    url = request.args.get('url')
    title = request.args.get('title')
    ext = request.args.get('ext')
    
    if not url:
        return "Missing URL", 400

    try:
        req = requests.get(url, stream=True, timeout=30)
        
        # Sanitize title for the filename header
        safe_title = title.encode('ascii', 'ignore').decode('ascii')
        safe_title = "".join([c if c.isalnum() or c in " .-_" else "_" for c in safe_title])
        
        return Response(
            stream_with_context(req.iter_content(chunk_size=8192)),
            content_type=req.headers.get('content-type', 'audio/mpeg'),
            headers={
                'Content-Disposition': f'attachment; filename="{safe_title}.{ext}"',
                'Content-Length': req.headers.get('content-length')
            }
        )
    except requests.exceptions.Timeout:
        return "Download timed out", 504
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return "Download failed", 500

@app.route("/robots.txt")
def robots():
    """Serve robots.txt"""
    return app.send_static_file('robots.txt')

@app. route("/sitemap.xml")
def sitemap():
    """Generate sitemap.xml for ZipMedia"""
    pages = []
    
    # Homepage
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/',
        'lastmod': datetime.utcnow(). strftime('%Y-%m-%d'),
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
        'lastmod': datetime.utcnow(). strftime('%Y-%m-%d'),
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
        'lastmod': datetime.utcnow(). strftime('%Y-%m-%d'),
        'changefreq': 'monthly',
        'priority': '0.7'
    })
    
    # Privacy Policy
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/privacy-policy',
        'lastmod': datetime.utcnow(). strftime('%Y-%m-%d'),
        'changefreq': 'quarterly',
        'priority': '0.6'
    })
    
    # Terms of Service
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/terms',
        'lastmod': datetime. utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'quarterly',
        'priority': '0.6'
    })
    
    # Contact Page
    pages.append({
        'loc': 'https://zipmedia. globsoft.tech/contact',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'monthly',
        'priority': '0. 6'
    })
    
    # API Documentation
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/api/docs',
        'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
        'changefreq': 'weekly',
        'priority': '0. 7'
    })
    
    # Blog/Resources
    pages. append({
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


if __name__ == '__main__':
    app.run(debug=True)

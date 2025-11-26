from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import yt_dlp
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/convert', methods=['POST'])
def convert():
    data = request.get_json()
    url = data.get('url')
    # fmt = data.get('format', 'mp3') # Removed format selection

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        ydl_opts = {
            'format': 'bestaudio/best', # Always best audio
            'noplaylist': True,
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info['url']
            title = info.get('title', 'audio')
            
            # Always MP3/Audio
            ext = 'mp3'
            
            return jsonify({
                'title': title,
                'download_url': f'/api/download?url={requests.utils.quote(video_url)}&title={requests.utils.quote(title)}&ext={ext}'
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download')
def download():
    url = request.args.get('url')
    title = request.args.get('title')
    ext = request.args.get('ext')
    
    if not url:
        return "Missing URL", 400

    req = requests.get(url, stream=True)
    
    # Sanitize title for the filename header to avoid UnicodeEncodeError
    # Werkzeug/HTTP headers must be latin-1 safe.
    # We'll replace non-ascii characters with underscores or similar.
    safe_title = title.encode('ascii', 'ignore').decode('ascii')
    safe_title = "".join([c if c.isalnum() or c in " .-_" else "_" for c in safe_title])
    
    return Response(
        stream_with_context(req.iter_content(chunk_size=1024)),
        content_type=req.headers['content-type'],
        headers={
            'Content-Disposition': f'attachment; filename="{safe_title}.{ext}"'
        }
    )

@app.route("/robots.txt")
def robots():
    """Serve robots.txt"""
    return app.send_static_file('robots.txt')

@app.route("/sitemap. xml")
def sitemap():
    """Generate sitemap.xml for ZipMedia"""
    pages = []
    
    # Homepage
    pages.append({
        'loc': 'https://zipmedia.globsoft.tech/',
        'lastmod': datetime. utcnow().strftime('%Y-%m-%d'),
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

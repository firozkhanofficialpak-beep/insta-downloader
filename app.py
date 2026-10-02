import os
import re
import logging
from flask import Flask, render_template, request, jsonify
import yt_dlp

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instagram URL validation regex
INSTAGRAM_URL_REGEX = re.compile(
    r'^https?://(www\.)?instagram\.com/(reel|p|tv)/[a-zA-Z0-9_-]+/?'
)

def is_valid_instagram_url(url):
    """Check if the provided URL is a valid public Instagram reel/video URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(INSTAGRAM_URL_REGEX.match(url.strip()))

def extract_video_info(url):
    """
    Use yt-dlp to extract video information from a public Instagram URL.
    Returns a dict with success status and either download_url or error message.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'format': 'best[ext=mp4]/best',
        'noplaylist': True,
        'extract_flat': False,
        # Do not use any authentication or cookies
        'cookiefile': None,
        'username': None,
        'password': None,
        'videopassword': None,
        'cachedir': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if not info:
                return {
                    'success': False,
                    'error': 'Could not extract video information. The content may be private or unavailable.'
                }

            # Try to get the direct video URL
            download_url = info.get('url')

            # If no direct URL, look through formats
            if not download_url and 'formats' in info:
                # Prefer mp4 formats, highest quality
                mp4_formats = [
                    f for f in info['formats']
                    if f.get('ext') == 'mp4' and f.get('url')
                ]
                if mp4_formats:
                    # Sort by quality (height) descending
                    mp4_formats.sort(
                        key=lambda x: x.get('height') or 0,
                        reverse=True
                    )
                    download_url = mp4_formats[0]['url']
                else:
                    # Fallback to any format with a URL
                    for f in info['formats']:
                        if f.get('url'):
                            download_url = f['url']
                            break

            if not download_url:
                return {
                    'success': False,
                    'error': 'No downloadable video URL found. This content may be a photo or unavailable.'
                }

            return {
                'success': True,
                'download_url': download_url
            }

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        logger.warning(f"yt-dlp DownloadError: {error_msg}")

        if 'private' in error_msg or 'login' in error_msg or 'rate-limit' in error_msg:
            return {
                'success': False,
                'error': 'This content is private, requires login, or is currently rate-limited. Only public reels are supported.'
            }
        elif 'not found' in error_msg or '404' in error_msg:
            return {
                'success': False,
                'error': 'The video could not be found. Please check the URL and try again.'
            }
        elif 'unsupported' in error_msg:
            return {
                'success': False,
                'error': 'This URL is not supported. Please provide a valid public Instagram reel or video link.'
            }
        else:
            return {
                'success': False,
                'error': 'Unable to process this video. It may be private, restricted, or temporarily unavailable.'
            }
    except Exception as e:
        logger.error(f"Unexpected error during extraction: {type(e).__name__}")
        return {
            'success': False,
            'error': 'An unexpected error occurred. Please try again later.'
        }

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/get-download-link', methods=['POST'])
def get_download_link():
    """Handle AJAX request to extract video download link."""
    try:
        data = request.get_json(silent=True)

        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'No URL provided. Please enter an Instagram Reel or video link.'
            }), 400

        url = data.get('url', '').strip()

        if not url:
            return jsonify({
                'success': False,
                'error': 'Please enter a valid Instagram URL.'
            }), 400

        if not is_valid_instagram_url(url):
            return jsonify({
                'success': False,
                'error': 'Invalid URL. Please provide a valid public Instagram Reel, Post, or IGTV link.'
            }), 400

        result = extract_video_info(url)

        if result['success']:
            return jsonify({
                'success': True,
                'download_url': result['download_url']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400

    except Exception as e:
        logger.error(f"Error in /get-download-link: {type(e).__name__}")
        return jsonify({
            'success': False,
            'error': 'An unexpected server error occurred. Please try again.'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
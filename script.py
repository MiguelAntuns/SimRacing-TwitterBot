import praw
import json
import requests
import tweepy
import time
import os
import urllib.parse
from glob import glob
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Twitter API credentials from environment variables
ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN', '')
ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET', '')
CONSUMER_KEY = os.getenv('TWITTER_CONSUMER_KEY', '')
CONSUMER_SECRET = os.getenv('TWITTER_CONSUMER_SECRET', '')

# Reddit API credentials from environment variables
REDDIT_USERNAME = os.getenv('REDDIT_USERNAME', '')
REDDIT_PASSWORD = os.getenv('REDDIT_PASSWORD', '')
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID', '')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET', '')

# Subreddit from which it will collect data
SUBREDDIT_NAME = 'simracing'
# Path where post images and videos will be downloaded
MEDIA_DIR = 'media'
# File where tweeted posts are logged to avoid duplicates
LOG = 'log.txt'
# Maximum number of lines the log file will store, to prevent the file from getting too large
MAX_LOG_LINES = 60

def connect_reddit():

    print('[bot] Connecting bot to reddit...')
    try:
        reddit_connection = praw.Reddit(username=REDDIT_USERNAME,
                                        password=REDDIT_PASSWORD,
                                        client_id=REDDIT_CLIENT_ID,
                                        client_secret=REDDIT_CLIENT_SECRET,
                                        user_agent='SimRacing subreddit to twitter bot')
        # Test connection
        reddit_connection.user.me()
        return reddit_connection
    except Exception as e:
        print(f'[bot] Error connecting to Reddit: {e}')
        raise

# Gets the 5 hot posts from the selected subreddit. If none can be tweeted, it stops.
def get_posts(reddit):

    subreddit = reddit.subreddit(SUBREDDIT_NAME)
    print('[bot] Checking hot posts...')
    
    for submission in subreddit.hot(limit=10):
        post_id = submission.id
        post_title = submission.title
        post_url = submission.url
        print(f'[bot] Checking post: {post_id} - {post_title[:50]}...')
        
        # Try to create tweet, returns True if successful
        if create_tweet(post_id, post_title, post_url):
            print('[bot] Successfully tweeted! Stopping.')
            return True
    
    print('[bot] None of the posts could be tweeted. Stopping bot')
    delete_media()
    return False

def create_tweet(post_id, post_title, post_url):
    """
    Attempts to create a tweet from a Reddit post.
    Returns True if tweet was successfully published, False otherwise.
    """
    if is_duplicate(post_id):
        print(f'[bot] Post {post_id} already tweeted, skipping')
        return False
    
    media = download_media(post_url)
    if media is False:
        print(f'[bot] Post {post_id} is not an image or video, skipping')
        return False
    
    try:
        success = publish_tweet(post_title, media, post_id)
        return success
    except Exception as e:
        print(f'[bot] Error publishing tweet: {e}')
        # Clean up downloaded media on error
        if os.path.exists(media):
            os.remove(media)
        return False

# Checks if a post has already been tweeted
def is_duplicate(post_id):
    if not os.path.exists(LOG):
        return False
    
    try:
        with open(LOG, 'r') as log:
            for line in log:
                # Strip whitespace and check exact match
                if post_id == line.strip():
                    return True
        return False
    except Exception as e:
        print(f'[bot] Error reading log file: {e}')
        return False

# download_media() checks if the URL points to an image or video, and downloads it to the 'media' folder.
# This function returns the path to the downloaded file. Example: media/q3588wtf.png or media/video123.mp4
def download_media(post_url):
    """
    Checks if URL is an image or video and downloads it.
    Returns media file path if successful, False otherwise.
    """
    # Common image and video extensions
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    video_extensions = ['.mp4', '.mov', '.webm', '.gifv']
    media_domains = ['imgur.com', 'i.redd.it', 'i.reddit.com', 'preview.redd.it', 'v.redd.it']
    
    # Check if URL ends with media extension
    url_lower = post_url.lower()
    is_image_url = any(url_lower.endswith(ext) for ext in image_extensions)
    is_video_url = any(url_lower.endswith(ext) for ext in video_extensions)
    
    # Check if URL is from known media domains
    is_media_domain = any(domain in url_lower for domain in media_domains)
    
    # Special handling for v.redd.it (Reddit video) and gifv (Imgur video)
    if 'v.redd.it' in url_lower:
        # Reddit videos need special handling - they're usually in DASH format
        print(f'[bot] Detected Reddit video: {post_url}')
        return download_reddit_video(post_url)
    elif url_lower.endswith('.gifv'):
        # Convert .gifv to .mp4 for Imgur
        post_url = post_url.replace('.gifv', '.mp4')
        is_video_url = True
    
    if not (is_image_url or is_video_url or is_media_domain):
        print(f'[bot] URL does not appear to be media: {post_url}')
        return False
    
    # Handle imgur links that might need extension
    if 'imgur.com' in post_url and not (is_image_url or is_video_url):
        # Try image first, then video
        test_url = post_url + '.jpg'
        try:
            test_response = requests.head(test_url, timeout=5)
            if test_response.status_code == 200:
                post_url = test_url
                is_image_url = True
        except:
            pass
    
    try:
        # Get filename from URL
        parsed = urllib.parse.urlsplit(post_url)
        media_name = os.path.basename(parsed.path)
        
        # Determine file extension based on content or URL
        if not any(media_name.lower().endswith(ext) for ext in image_extensions + video_extensions):
            # Default to .jpg for images, .mp4 for videos
            if is_video_url or 'video' in url_lower:
                media_name = media_name + '.mp4'
            else:
                media_name = media_name + '.jpg'
        
        media_path = os.path.join(MEDIA_DIR, media_name)
        print(f'[bot] Downloading media from {post_url} to {media_path}')
        
        # Download with timeout and proper headers
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(post_url, stream=True, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            
            # Determine if it's video or image
            is_video = 'video' in content_type or any(media_path.lower().endswith(ext) for ext in video_extensions)
            is_image = 'image' in content_type or any(media_path.lower().endswith(ext) for ext in image_extensions)
            
            if not (is_video or is_image):
                print(f'[bot] URL does not return media (content-type: {content_type})')
                return False
            
            # Download the file
            with open(media_path, 'wb') as media_file:
                for chunk in response.iter_content(chunk_size=8192):
                    media_file.write(chunk)
            
            # Verify file was created and has content
            if os.path.exists(media_path) and os.path.getsize(media_path) > 0:
                file_size_mb = os.path.getsize(media_path) / (1024 * 1024)
                media_type = 'video' if is_video else 'image'
                print(f'[bot] Downloaded {media_type}: {media_path} ({file_size_mb:.2f} MB)')
                return media_path
            else:
                print('[bot] Downloaded file is empty or missing')
                return False
        else:
            print(f'[bot] Failed to download media: HTTP {response.status_code}')
            return False
            
    except requests.exceptions.RequestException as e:
        print(f'[bot] Error downloading media: {e}')
        return False
    except Exception as e:
        print(f'[bot] Unexpected error processing media: {e}')
        return False

def download_reddit_video(post_url):
    """
    Downloads Reddit video. Reddit videos are tricky - they use DASH format.
    This function tries to get the direct video URL.
    """
    try:
        # Reddit video URLs often need to be accessed differently
        # Try to get the direct video link
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        # For v.redd.it, we need to get the actual video URL
        # Reddit embeds videos in a JSON structure
        # Try common video URL patterns
        video_id = os.path.basename(urllib.parse.urlsplit(post_url).path)
        
        # Try DASH playlist URL (most common)
        dash_url = f"https://v.redd.it/{video_id}/DASH_720.mp4"
        
        response = requests.head(dash_url, headers=headers, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            # Download the video
            media_name = f"{video_id}.mp4"
            media_path = os.path.join(MEDIA_DIR, media_name)
            
            print(f'[bot] Downloading Reddit video from {dash_url}')
            video_response = requests.get(dash_url, stream=True, headers=headers, timeout=60)
            
            if video_response.status_code == 200:
                with open(media_path, 'wb') as video_file:
                    for chunk in video_response.iter_content(chunk_size=8192):
                        video_file.write(chunk)
                
                if os.path.exists(media_path) and os.path.getsize(media_path) > 0:
                    file_size_mb = os.path.getsize(media_path) / (1024 * 1024)
                    print(f'[bot] Downloaded video: {media_path} ({file_size_mb:.2f} MB)')
                    return media_path
        
        # If DASH_720 doesn't work, try lower quality
        for quality in ['480', '360', '240']:
            dash_url = f"https://v.redd.it/{video_id}/DASH_{quality}.mp4"
            response = requests.head(dash_url, headers=headers, timeout=10)
            if response.status_code == 200:
                media_name = f"{video_id}.mp4"
                media_path = os.path.join(MEDIA_DIR, media_name)
                
                print(f'[bot] Downloading Reddit video (quality {quality}) from {dash_url}')
                video_response = requests.get(dash_url, stream=True, headers=headers, timeout=60)
                
                if video_response.status_code == 200:
                    with open(media_path, 'wb') as video_file:
                        for chunk in video_response.iter_content(chunk_size=8192):
                            video_file.write(chunk)
                    
                    if os.path.exists(media_path) and os.path.getsize(media_path) > 0:
                        file_size_mb = os.path.getsize(media_path) / (1024 * 1024)
                        print(f'[bot] Downloaded video: {media_path} ({file_size_mb:.2f} MB)')
                        return media_path
        
        print(f'[bot] Could not download Reddit video from {post_url}')
        return False
        
    except Exception as e:
        print(f'[bot] Error downloading Reddit video: {e}')
        return False

# Logs into Twitter with tweepy and tweets the title along with the media (image or video)
def publish_tweet(post_title, media_file, post_id):
    """
    Publishes a tweet with the post title and media (image or video).
    Returns True if successful, False otherwise.
    """
    try:
        auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth, wait_on_rate_limit=True)

        client = tweepy.Client(
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET,
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            wait_on_rate_limit=True
        )

        # Prepare tweet text (Twitter limit is 280 chars)
        tweet_text = f"{post_title} redd.it/{post_id}"
        if len(tweet_text) > 280:
            # Truncate title if needed, leaving room for the reddit link
            max_title_length = 280 - len(f" redd.it/{post_id}")
            tweet_text = f"{post_title[:max_title_length-3]}... redd.it/{post_id}"

        # Determine if it's a video or image
        media_lower = media_file.lower()
        is_video = any(media_lower.endswith(ext) for ext in ['.mp4', '.mov', '.webm'])
        
        media_type = 'video' if is_video else 'image'
        print(f'[bot] Tweeting: {tweet_text[:50]}... with {media_type}: {media_file}')
        
        # Upload media
        # For videos, we need to use media_category parameter
        if is_video:
            # Twitter requires videos to be uploaded with media_category
            print('[bot] Uploading video (this may take a while)...')
            media = api.media_upload(
                filename=media_file,
                media_category='tweet_video'  # Important for videos
            )
        else:
            # Images upload normally
            media = api.media_upload(filename=media_file)
        
        media_list = [media.media_id_string]
        
        # Create tweet
        response = client.create_tweet(text=tweet_text, media_ids=media_list)
        
        if response:
            print(f'[bot] Tweet published successfully! Tweet ID: {response.data["id"]}')
            # Only log after successful tweet
            log_post_id(post_id)
            check_log_file_size()
            delete_media()
            return True
        else:
            print('[bot] Failed to publish tweet')
            return False
            
    except tweepy.errors.TweepyException as e:
        print(f'[bot] Twitter API error: {e}')
        return False
    except Exception as e:
        print(f'[bot] Unexpected error publishing tweet: {e}')
        return False

# Adds a post to the log (tweeted) to avoid duplicates
def log_post_id(post_id):
    with open(LOG, 'a') as out_file:
        out_file.write(str(post_id) + '\n')

# Deletes the first line of the log file to prevent the log file from getting too large, if the file has more than X lines (to avoid duplicates)
def check_log_file_size():

    with open(LOG, 'r') as file_log_in:
        # Store the entire file with line breaks in the data variable
        data = file_log_in.read().splitlines(True)
        # Count the lines in the file
        counter = 0
        for line in data:
            counter += 1

    # If the file exceeds the allowed number of lines, delete the first one
    if(counter > MAX_LOG_LINES):
        with open(LOG, 'w') as file_log_out:
            file_log_out.writelines(data[1:])

# Deletes media files (images and videos) from /media
def delete_media():
    try:
        for filename in glob(os.path.join(MEDIA_DIR, '*')):
            if os.path.isfile(filename):
                os.remove(filename)
                print(f'[bot] Deleted {filename}')
    except Exception as e:
        print(f'[bot] Error deleting media: {e}')

def main():
    # Validate required environment variables
    required_vars = {
        'Twitter': [ACCESS_TOKEN, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET],
        'Reddit': [REDDIT_USERNAME, REDDIT_PASSWORD, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET]
    }
    
    for service, vars_list in required_vars.items():
        if not all(vars_list):
            print(f'[bot] ERROR: Missing {service} credentials in environment variables!')
            print(f'[bot] Please set all required variables in your .env file')
            print(f'[bot] See .env.example for reference')
            sys.exit(1)
    
    # Creates the media directory and/or log if they don't exist
    if not os.path.exists(LOG):
        with open(LOG, 'w'):
            pass
    
    if not os.path.exists(MEDIA_DIR):
        os.makedirs(MEDIA_DIR)
        print(f'[bot] Created media directory: {MEDIA_DIR}')

    try:
        # Connects to reddit
        reddit = connect_reddit()
        print('[bot] Bot connected to Reddit!')

        # Gets the hot posts and tweets the first one that hasn't been tweeted yet
        get_posts(reddit)
        
    except KeyboardInterrupt:
        print('\n[bot] Bot stopped by user')
        delete_media()
        sys.exit(0)
    except Exception as e:
        print(f'[bot] Fatal error: {e}')
        delete_media()
        sys.exit(1)

if __name__ == '__main__':
    main()
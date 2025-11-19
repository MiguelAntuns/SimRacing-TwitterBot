import praw
import json
import requests
import tweepy
import time
import os
import urllib.parse
from glob import glob
import sys
import config


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
# Path where post images will be downloaded
IMG_DIR = 'img'
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

# Gets the hot posts from the selected subreddit. Tweets the first valid one and stops.
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
    delete_images()
    return False

def create_tweet(post_id, post_title, post_url):
    """
    Attempts to create a tweet from a Reddit post.
    Returns True if tweet was successfully published, False otherwise.
    """
    if is_duplicate(post_id):
        print(f'[bot] Post {post_id} already tweeted, skipping')
        return False
    
    image = convert_image(post_url)
    if image is False:
        print(f'[bot] Post {post_id} is not an image, skipping')
        return False
    
    try:
        success = publish_tweet(post_title, image, post_id)
        return success
    except Exception as e:
        print(f'[bot] Error publishing tweet: {e}')
        # Clean up downloaded image on error
        if os.path.exists(image):
            os.remove(image)
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

# convert_image() checks if the URL the post points to is an image, if so, downloads it to the 'img' path.
# This function returns the string of the path + the image. Example: img/q3588wtf.png
def convert_image(post_url):
    """
    Checks if URL is an image and downloads it.
    Returns image path if successful, False otherwise.
    """
    # Common image URL patterns
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    image_domains = ['imgur.com', 'i.redd.it', 'i.reddit.com', 'preview.redd.it']
    
    # Check if URL ends with image extension
    url_lower = post_url.lower()
    is_image_url = any(url_lower.endswith(ext) for ext in image_extensions)
    
    # Check if URL is from known image domains
    is_image_domain = any(domain in url_lower for domain in image_domains)
    
    if not (is_image_url or is_image_domain):
        print(f'[bot] URL does not appear to be an image: {post_url}')
        return False
    
    # Handle imgur links that might need .jpg extension
    if 'imgur.com' in post_url and not any(ext in post_url for ext in image_extensions):
        post_url = post_url + '.jpg'
    
    try:
        # Get filename from URL
        parsed = urllib.parse.urlsplit(post_url)
        image_name = os.path.basename(parsed.path)
        
        # If no extension, try to get it from content-type or default to .jpg
        if not any(image_name.lower().endswith(ext) for ext in image_extensions):
            image_name = image_name + '.jpg'
        
        image_path = os.path.join(IMG_DIR, image_name)
        print(f'[bot] Downloading image from {post_url} to {image_path}')
        
        # Download with timeout and proper headers
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(post_url, stream=True, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Check content type
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                print(f'[bot] URL does not return an image (content-type: {content_type})')
                return False
            
            with open(image_path, 'wb') as image_file:
                for chunk in response.iter_content(chunk_size=8192):
                    image_file.write(chunk)
            
            # Verify file was created and has content
            if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                return image_path
            else:
                print('[bot] Downloaded file is empty or missing')
                return False
        else:
            print(f'[bot] Failed to download image: HTTP {response.status_code}')
            return False
            
    except requests.exceptions.RequestException as e:
        print(f'[bot] Error downloading image: {e}')
        return False
    except Exception as e:
        print(f'[bot] Unexpected error processing image: {e}')
        return False

# Logs into Twitter with tweepy and tweets the title along with the image
def publish_tweet(post_title, image, post_id):
    """
    Publishes a tweet with the post title and image.
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

        print(f'[bot] Tweeting: {tweet_text[:50]}... with image: {image}')
        
        # Upload media
        media = api.media_upload(filename=image)
        media_list = [media.media_id_string]
        
        # Create tweet
        response = client.create_tweet(text=tweet_text, media_ids=media_list)
        
        if response:
            print(f'[bot] Tweet published successfully! Tweet ID: {response.data["id"]}')
            # Only log after successful tweet
            log_post_id(post_id)
            check_log_file_size()
            delete_images()
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
    if not os.path.exists(LOG):
        return
    
    try:
        with open(LOG, 'r') as file_log_in:
            data = file_log_in.readlines()
        
        # If the file exceeds the allowed number of lines, delete the first one
        if len(data) > MAX_LOG_LINES:
            with open(LOG, 'w') as file_log_out:
                file_log_out.writelines(data[1:])
            print(f'[bot] Log file trimmed to {MAX_LOG_LINES} lines')
    except Exception as e:
        print(f'[bot] Error checking log file size: {e}')

# Deletes images from /img
def delete_images():
    try:
        for filename in glob(os.path.join(IMG_DIR, '*')):
            if os.path.isfile(filename):
                os.remove(filename)
                print(f'[bot] Deleted {filename}')
    except Exception as e:
        print(f'[bot] Error deleting images: {e}')

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
            sys.exit(1)
    
    # Creates the image directory and/or log if they don't exist
    if not os.path.exists(LOG):
        with open(LOG, 'w'):
            pass
    
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)
        print(f'[bot] Created image directory: {IMG_DIR}')

    try:
        # Connects to reddit
        reddit = connect_reddit()
        print('[bot] Bot connected to Reddit!')

        # Gets the hot posts and tweets the first one that hasn't been tweeted yet
        get_posts(reddit)
        
    except KeyboardInterrupt:
        print('\n[bot] Bot stopped by user')
        delete_images()
        sys.exit(0)
    except Exception as e:
        print(f'[bot] Fatal error: {e}')
        delete_images()
        sys.exit(1)

if __name__ == '__main__':
    main()
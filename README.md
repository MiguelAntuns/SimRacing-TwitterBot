# SimRacing-TwitterBot

This is a Twitter bot that reposts the hottest posts from the r/simracing community. It supports both images and videos!

## Step-by-Step Setup Guide (For Beginners)

### Step 1: Install Python
If you don't have Python installed:
1. Go to https://www.python.org/downloads/
2. Download Python 3.8 or newer
3. During installation, check "Add Python to PATH"
4. Verify installation by opening PowerShell and typing: `python --version`

### Step 2: Install Required Packages
1. Open PowerShell in this folder
2. Activate your virtual environment (if you have one): `.venv\Scripts\Activate.ps1`
3. Install packages: `pip install -r requirements.txt`

### Step 3: Get Your Twitter API Credentials
1. Go to https://developer.twitter.com/en/portal/dashboard
2. Create a new app or use an existing one
3. Go to "Keys and tokens" tab
4. Copy these 4 values:
   - API Key (Consumer Key)
   - API Secret (Consumer Secret)
   - Access Token
   - Access Token Secret

### Step 4: Get Your Reddit API Credentials
1. Go to https://www.reddit.com/prefs/apps
2. Click "create app" or "create another app"
3. Choose "script" as the app type
4. Copy these 4 values:
   - Client ID (under the app name)
   - Secret (the "secret" field)
   - Your Reddit username
   - Your Reddit password

### Step 5: Create Your .env File
1. Copy `.env.example` and rename it to `.env`
2. Open `.env` in a text editor
3. Replace all the placeholder values with your actual credentials:
   ```
   TWITTER_ACCESS_TOKEN=your_actual_access_token_here
   TWITTER_ACCESS_TOKEN_SECRET=your_actual_secret_here
   TWITTER_CONSUMER_KEY=your_actual_key_here
   TWITTER_CONSUMER_SECRET=your_actual_secret_here
   
   REDDIT_USERNAME=your_actual_username
   REDDIT_PASSWORD=your_actual_password
   REDDIT_CLIENT_ID=your_actual_client_id
   REDDIT_CLIENT_SECRET=your_actual_client_secret
   ```
4. **IMPORTANT**: Never share your `.env` file! It contains your secret keys.

### Step 6: Run the Bot
1. Make sure your virtual environment is activated
2. Run: `python script.py`
3. The bot will check the r/simracing subreddit and tweet the first valid post it finds

## How It Works (Step-by-Step Explanation)

### 1. **Starting the Bot** (`main()` function)
   - First, it checks if you have all your credentials set up
   - Creates a `media` folder to store downloaded images/videos
   - Creates a `log.txt` file to remember which posts were already tweeted

### 2. **Connecting to Reddit** (`connect_reddit()` function)
   - Uses your Reddit credentials to log in
   - Tests the connection to make sure it works

### 3. **Finding Posts** (`get_posts()` function)
   - Looks at the top 10 "hot" posts in r/simracing
   - For each post, it tries to create a tweet
   - Stops after successfully tweeting one post

### 4. **Checking for Duplicates** (`is_duplicate()` function)
   - Reads the `log.txt` file
   - Checks if this post was already tweeted before
   - If yes, skips it

### 5. **Downloading Media** (`download_media()` function)
   - Checks if the post URL is an image or video
   - **For images**: Downloads from imgur.com, i.redd.it, etc.
   - **For videos**: 
     - Handles regular video URLs (.mp4, .mov, .webm)
     - Special handling for Reddit videos (v.redd.it) - these are tricky!
     - Converts Imgur .gifv files to .mp4
   - Saves the file to the `media` folder
   - Returns the file path if successful

### 6. **Publishing the Tweet** (`publish_tweet()` function)
   - Connects to Twitter using your credentials
   - Uploads the image or video to Twitter
   - **For videos**: Uses special "tweet_video" category (required by Twitter)
   - Creates a tweet with:
     - The Reddit post title
     - A link to the Reddit post (redd.it/post_id)
     - The image or video attached
   - Logs the post ID so it won't tweet it again

### 7. **Cleanup** (`delete_media()` function)
   - Deletes the downloaded image/video from the `media` folder
   - Keeps your folder clean

## Video Support Explained

The bot now supports videos! Here's how it works:

1. **Detecting Videos**: The bot checks if a URL ends with video extensions (.mp4, .mov, .webm) or comes from video domains (v.redd.it)

2. **Reddit Videos**: Reddit videos are special - they use a format called "DASH". The bot:
   - Tries to download the video in 720p quality first
   - If that doesn't work, tries lower qualities (480p, 360p, 240p)
   - Downloads the video file to your `media` folder

3. **Imgur Videos**: Imgur .gifv files are actually videos! The bot converts them to .mp4 automatically.

4. **Uploading to Twitter**: 
   - Videos take longer to upload than images
   - Twitter requires videos to be uploaded with `media_category='tweet_video'`
   - The bot handles this automatically

## Troubleshooting

- **"Missing credentials" error**: Make sure your `.env` file exists and has all 8 values filled in
- **"Not an image or video"**: The post might be a text post or link to a website. The bot only tweets posts with images or videos.
- **Video upload fails**: Twitter has size limits for videos. Very large videos might fail. The bot will try its best!

## Notes

- The bot only tweets ONE post per run
- It remembers which posts it already tweeted (in `log.txt`)
- It automatically cleans up downloaded files after tweeting
- The `log.txt` file keeps the last 60 posts to prevent duplicates

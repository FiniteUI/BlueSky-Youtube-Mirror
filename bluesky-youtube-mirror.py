import time
from pyyoutube import Api
from get_youtube_community_posts import get_youtube_community_posts
from bluesky import BlueSky
import textwrap
import requests
from registry_file import RegistryFile
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, UTC
import sys

DISPLAY_NAME_LENGTH = 64
DESCRIPTION_LENGTH = 256
NAME_SUFFIX = ' (YouTube Mirror)'
PROCESS_INTERVAL = 300
PROFILE_UPDATE_INTERVAL = 86400
TEST_MODE = False

def get_channel_details(youtube_api, channel_id):
    print(f'Loading details for channel [{channel_id}]...')
    channel = youtube_api.get_channel_info(channel_id=CHANNEL_ID)
    channel_details = {'name': channel.items[0].snippet.title,
                       'description': channel.items[0].snippet.description,
                       'profile_picture': channel.items[0].snippet.thumbnails.default.url,
                       'banner': channel.items[0].brandingSettings.image.bannerExternalUrl,
                       'handle': channel.items[0].snippet.customUrl,
                       'uploads_playlist': channel.items[0].contentDetails.relatedPlaylists.uploads,
                       'url': f'https://www.youtube.com/{channel.items[0].snippet.customUrl}'
                       }
    return channel_details

def get_channel_videos(api, channel_id):
    print(f'Loading videos for channel [{channel_id}]...')

    #get videos
    #default page size is 20
    raw_activities = youtube_api.get_activities_by_channel(channel_id=CHANNEL_ID)
    videos = []
    for a in raw_activities.items:
        if a.snippet.type == 'upload':
            video = {
                'type': 'video',
                'video_id': a.contentDetails.upload.videoId,
                'timestamp': a.snippet.publishedAt,
                'url': f'https://www.youtube.com/watch?v={a.contentDetails.upload.videoId}'
            }
            videos.append(video)
    del raw_activities

    return videos

def update_profile(bluesky_client, channel_details):
    #grab images
    print(f'Downloading profile picture from url [{channel_details['profile_picture']}]...')
    avatar = requests.get(channel_details['profile_picture']).content
    print(f'Downloading banner from url [{channel_details['banner']}]...')
    banner = requests.get(channel_details['banner']).content

    #profile display name
    length = DISPLAY_NAME_LENGTH - len(NAME_SUFFIX)
    channel_name = textwrap.shorten(channel_details['name'], width=length, placeholder='...', replace_whitespace=True)
    channel_name = f"{channel_name}{NAME_SUFFIX}"
    print(f'Generated name: {channel_name}')

    # generate bluesky friendly description
    description = textwrap.shorten(channel_details['description'], width=DESCRIPTION_LENGTH, placeholder='...', replace_whitespace=True)
    description = description.replace(',...', '....')
    print(f'Generated description: {description}')

    print('Updating BlueSky profile...')
    bluesky_client.update_profile(channel_name, description, avatar, banner)

def generate_pinned_post(bluesky_client, channel_url, channel_name):
    post_text = f'This account is an unofficial automated mirror of the {channel_name} Youtube channel maintained by @{ACCOUNT_OWNER}. This account is not affiliated with {channel_name} in any way. Please support the {channel_name} at the link below.'
    print(f'Sending pinned post: {post_text}')
    post_uid = bluesky_client.post(contents=post_text, link_embed=channel_url, mentions=[ACCOUNT_OWNER])
    bluesky_client.pin_post(post_uid)

print('Process initializing...')

#load configuration
load_dotenv()
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID')
BLUESKY_ACCOUNT = os.getenv('BLUESKY_ACCOUNT')
BLUESKY_APP_PASSWORD = os.getenv('BLUESKY_APP_PASSWORD')
ACCOUNT_OWNER = os.getenv('ACCOUNT_OWNER')

valid = True
if not YOUTUBE_API_KEY:
    print('ERROR: Missing environment variable YOUTUBE_API_KEY.')
    valid = False
if not CHANNEL_ID:
    print('ERROR: Missing environment variable CHANNEL_ID.')
    valid = False
if not BLUESKY_ACCOUNT:
    print('ERROR: Missing environment variable BLUESKY_ACCOUNT.')
    valid = False
if not BLUESKY_APP_PASSWORD:
    print('ERROR: Missing environment variable BLUESKY_APP_PASSWORD.')
    valid = False
if not ACCOUNT_OWNER:
    print('ERROR: Missing environment variable ACCOUNT_OWNER.')
    valid = False

if not valid:
    print('Invalid configuration. Exiting...')
    sys.exit()

#load registry file
#this is for storing data between runs
registry = RegistryFile()

#load youtube api
youtube_api = Api(api_key=YOUTUBE_API_KEY)

#login to Bluesky
session = registry.getValue('bluesky_session_string', None)
bsky = BlueSky(BLUESKY_ACCOUNT, BLUESKY_APP_PASSWORD, session)

bsky.login()
if not bsky.logged_in:
    print('Failed to log in to BlueSky. Trying again without session...')
    bsky = BlueSky(BLUESKY_ACCOUNT, BLUESKY_APP_PASSWORD, session=None)
    bsky.login()

    if not bsky.logged_in:
        print('Failed to log in to BlueSky. Exiting...')
        sys.exit()

#update session string
registry.setValue('bluesky_session_string', bsky.session)

initialized = registry.getValue('initialized', False)
if not initialized:
    # get channel information
    channel_details = get_channel_details(youtube_api, CHANNEL_ID)
    print(channel_details)

    # update profile
    update_profile(bsky, channel_details)

    generate_pinned_post(bsky, channel_details['url'], channel_details['name'])
    registry.setValue('initialized', True)

#now run update process
while True:
    print('Processing...')

    last_process = registry.getValue('last_process', None)
    if last_process is None:
        last_process = datetime.now(UTC)
    else:
        last_process = datetime.fromisoformat(last_process)
    # update last run time
    registry.setValue('last_process', datetime.now(UTC))

    print(f'Last process: {last_process}')

    #grab data
    print('Grabbing channel data...')
    channel_details = get_channel_details(youtube_api, CHANNEL_ID)

    #update profile
    last_profile_update = registry.getValue('last_profile_update', None)
    if last_profile_update is None:
        last_profile_update = datetime.now(UTC)
        registry.setValue('last_profile_update', datetime.now(UTC))
    else:
        last_profile_update = datetime.fromisoformat(last_profile_update)
    if datetime.now(UTC) - last_profile_update > timedelta(seconds=PROFILE_UPDATE_INTERVAL):
        update_profile(bsky, channel_details)
        registry.setValue('last_profile_update', datetime.now(UTC))

    channel_videos = get_channel_videos(youtube_api, CHANNEL_ID)
    posts = get_youtube_community_posts(channel_details['handle'])

    #combine data and sort
    channel_updates = []
    for v in channel_videos:
        timestamp = datetime.fromisoformat(v['timestamp'])
        if timestamp > last_process:
            channel_updates.append({'timestamp': timestamp, 'type': 'video', 'item': v})
    for p in posts:
        timestamp = datetime.fromisoformat(p['post_timestamp'])
        if timestamp > last_process:
            channel_updates.append({'timestamp': p['post_timestamp'], 'type': 'post', 'item': p})
    channel_updates = sorted(channel_updates, key=lambda d: d['timestamp'])

    print(f'{len(channel_updates)} channel updates found to post...')
    if channel_updates:
        for c in channel_updates:
            print(f'Generating post for update [{c}]...')

            contents = ''
            images = None

            if c['type'] == 'video':
                link_embed = c['item']['url']
            else:
                contents = c['item']['post_text']
                link_embed = c['item']['post_url']
                if c['item']['attachments'] is not None:
                    #either video link or image(s)
                    if c['item']['attachments'][0]['type'] == 'video':
                        link_embed = c['attachments'][0]['url']
                    else:
                        images = []
                        for i in c['item']['attachments']:
                            print(f'Downloading post attachment from url [{i["url"]}]...')
                            images.append(requests.get(i['url']).content)
            #post
            if not TEST_MODE:
                bsky.post(contents=contents, link_embed=link_embed, images=images)

    # update session string
    registry.setValue('bluesky_session_string', bsky.session)

    print(f'Processing complete. Waiting for {PROCESS_INTERVAL} seconds...')
    time.sleep(PROCESS_INTERVAL)

#post length
#repo link
#alt text
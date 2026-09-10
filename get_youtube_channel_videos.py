import re
from bs4 import BeautifulSoup
import json
from get_timestamp_from_post_time import get_timestamp_from_post_time
from datetime import datetime, timezone
from request_handler import RequestHandler

def get_youtube_data_from_url(url):
    with RequestHandler() as request:
        response = request.get(url)

    soup = BeautifulSoup(response.text, 'html.parser')
    data = soup.find_all('script', string=re.compile('var ytInitialData'), recursive=True)
    if len(data) == 0:
        return None

    # parse result json
    data = data[0]
    data = data.string.replace('var ytInitialData = ', '', 1)
    data = data[:len(data) - 1]
    data = json.loads(data)

    return data

def get_all_channel_videos(handle, cutoff=None):
    videos = []

    temp = get_youtube_channel_videos(handle, cutoff)
    if temp:
        videos.extend(temp)

    temp = get_youtube_channel_shorts(handle, cutoff)
    if temp:
        videos.extend(temp)

    return videos

def get_youtube_channel_videos(handle, cutoff=None):
    videos = []

    data = get_youtube_data_from_url(f'https://www.youtube.com/{handle}/videos')
    if not data:
        return videos

    #grab videos tab
    vidoes_index = None
    for i, t in enumerate(data['contents']['twoColumnBrowseResultsRenderer']['tabs']):
        if t['tabRenderer']['title'] == 'Videos':
            videos_index = i
            break

    if videos_index is None:
        return videos

    data = data['contents']['twoColumnBrowseResultsRenderer']['tabs'][videos_index]['tabRenderer']['content']['richGridRenderer']['contents']
    for v in data:
        if 'richItemRenderer' in v:
            #find timestamp
            timestamp = None
            for i, m in enumerate(v['richItemRenderer']['content']['lockupViewModel']['metadata']['lockupMetadataViewModel']['metadata']['contentMetadataViewModel']['metadataRows'][0]['metadataParts']):
                #for some reason this is different each time, so account for it
                if 'accessibilityLabel' in m:
                    temp = m['accessibilityLabel']
                elif 'text' in m:
                    temp = m['text']['content']

                if 'ago' in temp:
                    timestamp = get_timestamp_from_post_time(temp)
                    break

            video = {
                'type': 'video',
                'id': v['richItemRenderer']['content']['lockupViewModel']['contentId'],
                'timestamp': timestamp,
                'title:': v['richItemRenderer']['content']['lockupViewModel']['metadata']['lockupMetadataViewModel']['title']['content']
            }

            videos.append(video)

            if cutoff:
                if video['timestamp'] < cutoff:
                    break

    return videos

def get_youtube_channel_shorts(handle, cutoff=None):
    videos = []

    data = get_youtube_data_from_url(f'https://www.youtube.com/{handle}/shorts')
    if not data:
        return videos

    #grab videos tab
    shorts_index = None
    for i, t in enumerate(data['contents']['twoColumnBrowseResultsRenderer']['tabs']):
        if t['tabRenderer']['title'] == 'Shorts':
            shorts_index = i
            break

    if shorts_index is None:
        return videos

    data = data['contents']['twoColumnBrowseResultsRenderer']['tabs'][shorts_index]['tabRenderer']['content'][
        'richGridRenderer']['contents']
    for v in data:
        if 'richItemRenderer' in v:
            item = v['richItemRenderer']['content']['shortsLockupViewModel']

            # find timestamp
            timestamp = get_short_timestamp(item['onTap']['innertubeCommand']['reelWatchEndpoint']['videoId'])

            video = {
                'type': 'short',
                'id': item['onTap']['innertubeCommand']['reelWatchEndpoint']['videoId'],
                'timestamp': timestamp,
                'title:': item['accessibilityText']
            }

            videos.append(video)

            if cutoff:
                if video['timestamp'] < cutoff:
                    break

    return videos

def get_short_timestamp(video_id):
    timestamp = None

    data = get_youtube_data_from_url(f'https://www.youtube.com/watch?v={video_id}')
    if not data:
        return timestamp

    try:
        timestamp = data['contents']['twoColumnWatchNextResults']['results']['results']['contents'][0]['videoPrimaryInfoRenderer']['dateText']['simpleText']
        timestamp = datetime.strptime(timestamp, '%b %d, %Y').replace(tzinfo=timezone.utc)

    except KeyError:
        print('Could not find short timestamp.')

    return timestamp




import json
import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from get_timestamp_from_post_time import get_timestamp_from_post_time
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
    data = data[: len(data) - 1]
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

    # grab videos tab
    videos_index = None
    for i, t in enumerate(data['contents']['twoColumnBrowseResultsRenderer']['tabs']):
        if t['tabRenderer']['title'] == 'Videos':
            videos_index = i
            break

    if videos_index is None:
        return videos

    data = data['contents']['twoColumnBrowseResultsRenderer']['tabs'][videos_index]['tabRenderer']['content']['richGridRenderer']['contents']
    for v in data:
        if 'richItemRenderer' in v:
            video_data = v['richItemRenderer']

            timestamp = get_video_timestamp_from_soup(video_data)
            video = {
                'type': 'video',
                'id': video_data['content']['lockupViewModel']['contentId'],
                'timestamp': timestamp,
                'title:': video_data['content']['lockupViewModel']['metadata']['lockupMetadataViewModel']['title']['content'],
            }

            if cutoff:
                if video['timestamp']:
                    if video['timestamp'] < cutoff:
                        break

            print(video)
            videos.append(video)

    return videos


def get_video_timestamp_from_soup(soup):
    # this expects the soup already trimmed down to ['contents']['twoColumnBrowseResultsRenderer']['tabs'][videos_index]['tabRenderer']['content']['richGridRenderer']['contents'][i][richItemRenderer]
    # find timestamp, it can be in a few different places
    timestamp = None

    # trim it down some more
    data = soup['content']['lockupViewModel']['metadata']['lockupMetadataViewModel']['metadata']['contentMetadataViewModel']['metadataRows']
    for i in data:
        for j in i['metadataParts']:
            try:
                if 'ago' in j['accessibilityLabel']:
                    timestamp = j['accessibilityLabel']
                    break
            except KeyError:
                pass

            try:
                if 'ago' in j['text']['content']:
                    timestamp = j['text']['content']
                    break
            except KeyError:
                pass

        if timestamp:
            break

    if not timestamp:
        print('Unable to determine video timestamp.')
    else:
        timestamp = get_timestamp_from_post_time(timestamp)

    return timestamp


def get_youtube_channel_shorts(handle, cutoff=None):
    videos = []

    data = get_youtube_data_from_url(f'https://www.youtube.com/{handle}/shorts')
    if not data:
        return videos

    # grab videos tab
    shorts_index = None
    for i, t in enumerate(data['contents']['twoColumnBrowseResultsRenderer']['tabs']):
        if t['tabRenderer']['title'] == 'Shorts':
            shorts_index = i
            break

    if shorts_index is None:
        return videos

    data = data['contents']['twoColumnBrowseResultsRenderer']['tabs'][shorts_index]['tabRenderer']['content']['richGridRenderer']['contents']
    for v in data:
        if 'richItemRenderer' in v:
            item = v['richItemRenderer']['content']['shortsLockupViewModel']

            # find timestamp
            timestamp = get_short_timestamp(item['onTap']['innertubeCommand']['reelWatchEndpoint']['videoId'])

            video = {
                'type': 'short',
                'id': item['onTap']['innertubeCommand']['reelWatchEndpoint']['videoId'],
                'timestamp': timestamp,
                'title:': item['accessibilityText'],
            }

            if cutoff:
                if video['timestamp']:
                    if video['timestamp'] < cutoff:
                        break

            print(video)
            videos.append(video)

    return videos


def get_short_timestamp(video_id):
    timestamp = None

    data = get_youtube_data_from_url(f'https://www.youtube.com/watch?v={video_id}')
    if not data:
        return timestamp

    try:
        timestamp = data['contents']['twoColumnWatchNextResults']['results']['results']['contents'][0]['videoPrimaryInfoRenderer']['dateText']['simpleText']
        timestamp = datetime.strptime(timestamp, '%b %d, %Y').replace(tzinfo=UTC)

    except KeyError:
        print('Could not find short timestamp.')

    return timestamp

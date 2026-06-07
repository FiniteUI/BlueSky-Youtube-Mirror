import requests
import re
from bs4 import BeautifulSoup
import json
from get_timestamp_from_post_time import get_timestamp_from_post_time

def get_youtube_channel_videos(handle):
    videos = []

    url = f'https://www.youtube.com/{handle}/videos'
    response = requests.get(url)

    soup = BeautifulSoup(response.text, 'html.parser')
    data = soup.find_all('script', string=re.compile('var ytInitialData'), recursive=True)
    if len(data) == 0:
        return videos

    #parse result json
    data = data[0]
    data = data.string.replace('var ytInitialData = ', '', 1)
    data = data[:len(data)-1]
    data = json.loads(data)

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

    return videos
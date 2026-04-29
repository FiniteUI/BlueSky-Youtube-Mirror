import requests
from bs4 import BeautifulSoup
import re
import json
import arrow
from datetime import datetime, UTC, timedelta

#accepts a youtube channel handle
#returns a list of their most recent community posts
def get_youtube_community_posts(handle):
    print(f'Getting community posts for channel [{handle}]...')

    # get community posts
    community_posts_url = f'https://www.youtube.com/{handle}/posts'
    community_posts_response = requests.get(community_posts_url)
    community_posts_data = BeautifulSoup(community_posts_response.text, 'html.parser')

    posts = []
    filter = re.compile('(?<=var ytInitialData = )(.*)(?=;)')
    youtube_data = community_posts_data.find_all('script', string=filter)
    if len(youtube_data) > 0:
        page_data = json.loads(re.search(filter, youtube_data[0].string)[0])

        posts_index = None
        for i in range(len(page_data['contents']['twoColumnBrowseResultsRenderer']['tabs'])):
            #if 'expandableTabRenderer' in page_data['contents']['twoColumnBrowseResultsRenderer']['tabs'][i].keys():
                if page_data['contents']['twoColumnBrowseResultsRenderer']['tabs'][i]['tabRenderer']['title'] == 'Posts':
                    posts_index = i
                    break

        if posts_index is not None:
            post_data = page_data['contents']['twoColumnBrowseResultsRenderer']['tabs'][posts_index]['tabRenderer']['content'][
                'sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']

            for p in post_data:
                if 'backstagePostThreadRenderer' in p.keys():
                    post = {
                        'id': p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['postId'],
                        'post_text': p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['contentText']['runs'][0]['text'].strip(),
                        'post_url': f"https://www.youtube.com/post/{p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['postId']}",
                        #'post_timestamp_friendly': p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['publishedTimeText']['runs'][0]['text'],
                        'post_timestamp': get_timestamp_from_post_time(p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['publishedTimeText']['runs'][0]['text'])
                    }

                    attachments = []
                    if 'backstageAttachment' in p['backstagePostThreadRenderer']['post']['backstagePostRenderer'].keys():
                        if 'postMultiImageRenderer' in p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['backstageAttachment'].keys():
                            for image in p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['backstageAttachment']['postMultiImageRenderer']['images']:
                                attachments.append({'type': 'image', 'url': image['backstageImageRenderer']['image']['thumbnails'][len(image['backstageImageRenderer']['image']['thumbnails']) - 1]['url']})
                        elif 'videoRenderer' in p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['backstageAttachment'].keys():
                            url = f'https://www.youtube.com/watch?v={p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['backstageAttachment']['videoRenderer']['videoId']}'
                            attachments.append({'type': 'video', 'url': url})
                        elif 'pollRenderer' in p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['backstageAttachment'].keys() or 'quizRenderer' in p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['backstageAttachment'].keys():

                            if 'pollRenderer' in p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['backstageAttachment'].keys():
                                path = 'pollRenderer'
                            else:
                                path = 'quizRenderer'

                            poll_text = ''
                            for c in p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['backstageAttachment'][path]['choices']:
                                if poll_text != '':
                                    poll_text += '\n'
                                poll_text += f'- {c['text']['runs'][0]['text']}'

                                if 'image' in c.keys():
                                    attachments.append({'type': 'image', 'url': c['image']['thumbnails'][len(c['image']['thumbnails']) - 1]['url']})

                            post['post_text'] += '\n' + poll_text
                        else:
                            attachments.append({'type': 'image', 'url': p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['backstageAttachment']['backstageImageRenderer']['image']['thumbnails'][len(p['backstagePostThreadRenderer']['post']['backstagePostRenderer']['backstageAttachment']['backstageImageRenderer']['image']['thumbnails']) - 1]['url']})
                    if not attachments:
                        attachments = None
                    post['attachments'] = attachments

                    posts.append(post)

    return posts

def get_timestamp_from_post_time(time_raw):
    time_clean = time_raw.replace('hour ', 'hours ')
    time_clean = time_clean.replace('day ', 'days ')
    time_clean = time_clean.replace('minute ', 'minutes ')
    time_clean = time_clean.replace('week ', 'weeks ')
    time_clean = time_clean.replace('month ', 'months ')
    time_clean = time_clean.replace('second ', 'seconds ')
    time_clean = time_clean.replace('year ', 'years ')
    time_clean = time_clean.replace('(edited)', '')
    time_clean = time_clean.strip()

    timestamp_handler = arrow.utcnow()

    try:
        time_fixed = timestamp_handler.dehumanize(time_clean)
    except ValueError as e:
        print(f'Failed to humanize timestamp: {time_raw}, {time_clean}')
        print(e)

        #set an arbitrary time in the past to not cause issues
        time_fixed = arrow.get(datetime.now(UTC) + timedelta(days=-100))

    return time_fixed.format()
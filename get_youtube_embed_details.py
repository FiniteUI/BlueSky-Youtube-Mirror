from urllib import parse

from request_handler import RequestHandler

BASE_URL = 'https://www.youtube.com/oembed'

def get_youtube_embed_details(url):
    title = None
    description = None
    thumbnail_url = None

    request_url = f'{BASE_URL}?url={parse.quote(url)}'
    print(f'Generating YouTube video embed details from oEmbed API: {request_url}')
    with RequestHandler() as r:
        response = r.get(request_url)
        response.raise_for_status()
    print(response)

    response = response.json()
    title = response['title']
    description = 'Video by ' + response['author_name']
    thumbnail_url = response['thumbnail_url']

    return title, description, thumbnail_url


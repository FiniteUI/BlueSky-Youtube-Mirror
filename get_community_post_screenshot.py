from PIL import Image
import numpy
import requests
from io import BytesIO

SCREENSHOT_ENDPOINT = 'https://html2png.dev/api/screenshot'

#bottom gray border line
BORDER_COLOR = [229, 229, 229]

# image should always be 1024x1366
START_Y = 128
BORDER_PROBE_Y = 12

def get_screenshot(url):
    screenshot = None

    parameters = {'url': url, 'width': 1024, 'height': 1366, 'deviceScaleFactor': 1}
    response = requests.post(SCREENSHOT_ENDPOINT, parameters)

    if response.status_code == 200:
        screenshot = requests.get(response.json()['url']).content
        screenshot = BytesIO(screenshot)

    return screenshot

def crop_community_post(image):
    cropped_image = Image.open(image)

    #crop the top section
    cropped_image = cropped_image.crop((0, START_Y, cropped_image.width, cropped_image.height))
    image_array = numpy.array(cropped_image)

    #find the left/right crops
    start_x = None
    end_x = None
    for i in range(cropped_image.width):
        if numpy.array_equal(image_array[BORDER_PROBE_Y][i], BORDER_COLOR):
            start_x = i
            break

    for i in range(cropped_image.width - 1, -1, -1):
        if numpy.array_equal(image_array[BORDER_PROBE_Y][i], BORDER_COLOR):
            end_x = i
            break

    if start_x is not None and end_x is not None:
        cropped_image = cropped_image.crop((start_x, 0, end_x, cropped_image.height))
        image_array = numpy.array(cropped_image)

    #array for border
    border = numpy.array([BORDER_COLOR for i in range(cropped_image.width)])

    #now find the border
    border_y = None
    for i in range(len(image_array)):
        if numpy.array_equal(image_array[i], border):
            border_y = i
            break

    if border_y is not None:
        cropped_image = cropped_image.crop((0, 0, cropped_image.width, border_y))

    final_image = BytesIO()
    cropped_image.save(final_image, format='PNG')

    final_image.seek(0)

    return final_image.read()

def get_community_post_screenshot(url):
    screenshot = get_screenshot(url)
    screenshot = crop_community_post(screenshot)

    return screenshot
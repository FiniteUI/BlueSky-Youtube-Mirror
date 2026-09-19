from io import BytesIO

import numpy
from PIL import Image
from playwright.sync_api import sync_playwright

# bottom gray border line
BORDER_COLOR = [204, 204, 204]

# image should always be 1024x1366
START_Y = 128
BORDER_PROBE_Y = 12

DEFAULT_TIMEOUT = 30000

# content to wait for when loading the page
CONTENT_SELECTOR = 'ytd-backstage-post-thread-renderer #attachment, ytd-backstage-post-thread-renderer #content-text'


def get_screenshot(url, timeout=None):
    screenshot = None

    print(f'Generating screenshot from url [{url}]...')

    try:
        with sync_playwright() as pw:
            print('Loading Chromium browser...')
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_viewport_size({'width': 1024, 'height': 1366})

            print(f'Loading url [{url}]...')
            page.goto(url, wait_until='domcontentloaded', timeout=timeout)

            if not timeout:
                timeout = DEFAULT_TIMEOUT
            page.locator(CONTENT_SELECTOR).first.wait_for(state='visible', timeout=timeout)

            # small wait for youtube to finish displaying items
            page.wait_for_timeout(1500)

            print('Taking screenshot...')
            screenshot = page.screenshot()
            screenshot = BytesIO(screenshot)

            print('Unloading browser...')
            browser.close()
    except Exception as e:
        print('Failed to generate screenshot...')
        print(e)

    return screenshot


def crop_community_post(image):
    cropped_image = Image.open(image)

    # crop the top section
    cropped_image = cropped_image.crop((0, START_Y, cropped_image.width, cropped_image.height))
    image_array = numpy.array(cropped_image)

    # find the left/right crops
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

    # array for border
    border = numpy.array([BORDER_COLOR for i in range(cropped_image.width)])

    # now find the border
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


def get_community_post_screenshot(url, timeout=None):
    screenshot = get_screenshot(url, timeout=timeout)

    if screenshot:
        screenshot = crop_community_post(screenshot)

    print(type(screenshot))
    return screenshot

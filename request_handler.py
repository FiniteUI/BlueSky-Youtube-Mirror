import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

RETRIES = Retry(total=5, backoff_factor=30, status_forcelist=[500, 502, 503, 504, 429])
ADAPTER = HTTPAdapter(max_retries=RETRIES)


class RequestHandler:
    def __init__(self):
        self.session = requests.Session()
        self.session.mount('https://', ADAPTER)

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

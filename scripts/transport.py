"""One bounded retry for transient transport failures; never bypass denials."""
import time
from urllib.error import HTTPError, URLError


def transient(error):
    if isinstance(error, HTTPError):
        return error.code in (502, 503, 504, 522, 524)
    if isinstance(error, URLError):
        return isinstance(error.reason, (TimeoutError, ConnectionError))
    return isinstance(error, (TimeoutError, ConnectionError))


def retry_read(read, sleep=time.sleep):
    try:
        return read()
    except Exception as error:
        if not transient(error):
            raise
        sleep(2)
        return read()

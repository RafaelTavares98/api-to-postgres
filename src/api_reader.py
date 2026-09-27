"""Read every page an API will give, without being thrown off it.

The server decides how fast we may ask. This waits when it says to wait,
tries again when the failure is the kind that passes, and gives up loudly
when it is not. A reader that hides a refusal produces a half table that
nobody notices is half.
"""

import time
import urllib.error
import urllib.parse
import urllib.request


class ApiRefused(Exception):
    """The server said no in a way that trying again will not fix."""


# Failures worth trying again: the server is busy or briefly broken.
# Anything else is our fault and will not get better by repeating it.
RETRY_ON = {429, 500, 502, 503, 504}


class ApiReader:
    def __init__(self, base_url, page_size=1000, pause=0.2, tries=4,
                 opener=None, sleep=time.sleep):
        self.base_url = base_url
        self.page_size = page_size
        self.pause = pause
        self.tries = tries
        # The network and the clock are passed in, so the tests run with
        # neither. A test that needs the internet is a test nobody runs.
        self.opener = opener or self._fetch
        self.sleep = sleep
        self.calls = 0

    def _fetch(self, url):
        request = urllib.request.Request(url, headers={"User-Agent": "api-to-dashboard"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()

    def _wait(self, attempt):
        """Back off further on each try, so a busy server is not hammered."""
        self.sleep(self.pause * (2 ** attempt))

    def get(self, params):
        """One page, with retries. Raises ApiRefused when it cannot be had."""
        url = self.base_url + "?" + urllib.parse.urlencode(params)
        last = None
        for attempt in range(self.tries):
            self.calls += 1
            try:
                status, body = self.opener(url)
            except urllib.error.HTTPError as error:
                status, body = error.code, b""
            except urllib.error.URLError as error:
                status, body, last = 0, b"", str(error.reason)
            if status == 200:
                return body
            last = last or f"HTTP {status}"
            if status not in RETRY_ON and status != 0:
                raise ApiRefused(f"{url} answered {status}")
            self._wait(attempt)
        raise ApiRefused(f"{url} failed {self.tries} times: {last}")

    def pages(self, params, parse, limit=None):
        """Every page in turn, stopping when a short page arrives.

        A full page means there is probably another. A short one means the
        end. Counting rows is the only signal an API always gives.
        """
        offset = 0
        while True:
            page = dict(params)
            page["$limit"] = self.page_size
            page["$offset"] = offset
            rows = parse(self.get(page))
            if not rows:
                return
            yield rows
            if len(rows) < self.page_size:
                return
            offset += len(rows)
            if limit is not None and offset >= limit:
                return
            self.sleep(self.pause)

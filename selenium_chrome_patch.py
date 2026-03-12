"""
Monkey-patch selenium.webdriver.Chrome so it always uses the system
Chromium + chromedriver binaries.  This avoids Selenium Manager, which
does not support linux/aarch64.

Import this module before any selenium usage (e.g. via sitecustomize
or an explicit import at the top of a notebook execution).
"""

import os

_CHROMIUM_BIN = os.environ.get("CHROMIUM_BIN", "/usr/bin/chromium")
_CHROMEDRIVER_BIN = os.environ.get("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")


def _patch():
    from selenium.webdriver.chrome import webdriver as chrome_module
    from selenium.webdriver.chrome.service import Service

    _OrigChrome = chrome_module.WebDriver

    class PatchedChrome(_OrigChrome):
        def __init__(self, *args, **kwargs):
            # Force the service to use the system chromedriver
            if "service" not in kwargs or kwargs["service"] is None:
                kwargs["service"] = Service(_CHROMEDRIVER_BIN)
            # Force the browser binary to system chromium
            options = kwargs.get("options")
            if options is not None and not options.binary_location:
                options.binary_location = _CHROMIUM_BIN
            super().__init__(*args, **kwargs)

    chrome_module.WebDriver = PatchedChrome


if os.path.isfile(_CHROMIUM_BIN) and os.path.isfile(_CHROMEDRIVER_BIN):
    _patch()

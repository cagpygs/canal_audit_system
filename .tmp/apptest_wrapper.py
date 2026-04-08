import streamlit_cookies_manager.encrypted_cookie_manager as cookie_mod


class _TestCookieManager(dict):
    def __init__(self, *args, **kwargs):
        super().__init__()

    def ready(self):
        return True

    def save(self):
        return True

    def get(self, key, default=None):
        return super().get(key, default)


cookie_mod.EncryptedCookieManager = _TestCookieManager

with open("app.py", "r", encoding="utf-8") as _f:
    _code = _f.read()

exec(compile(_code, "app.py", "exec"), {"__name__": "__main__", "__file__": "app.py"})

"""Shared cookie acquisition for Chinese platforms.

Pattern: env var → browser-cookie3 (Safari → Chrome → Firefox) → None.
Same pattern as channels/twitter/graphql.py get_credentials().
"""

from __future__ import annotations

import os
import sys


def get_cookies(domain: str, env_var_name: str) -> dict[str, str] | None:
    """Try to get cookies for a domain. Returns dict or None.

    1. Check env var (format: "key=val; key2=val2")
    2. Try browser-cookie3 (Safari → Chrome → Firefox)
    3. Return None if neither works
    """
    cookie_str = os.environ.get(env_var_name, "").strip()
    if cookie_str:
        cookies = _parse_cookie_string(cookie_str)
        if cookies:
            print(f"[cookie-auth] using {env_var_name} for {domain}", file=sys.stderr)
            return cookies

    try:
        import browser_cookie3
    except ImportError:
        return None

    browsers = [
        ("Safari", browser_cookie3.safari),
        ("Chrome", browser_cookie3.chrome),
        ("Firefox", browser_cookie3.firefox),
    ]
    for browser_name, loader in browsers:
        try:
            jar = loader()
            cookies: dict[str, str] = {}
            for c in jar:
                c_domain = getattr(c, "domain", "") or ""
                if domain in c_domain or c_domain.endswith(domain):
                    name = getattr(c, "name", "")
                    value = getattr(c, "value", "")
                    if name and value:
                        cookies[name] = value
            if cookies:
                print(
                    f"[cookie-auth] {browser_name} cookies for {domain} ({len(cookies)})",
                    file=sys.stderr,
                )
                return cookies
        except Exception:
            continue

    return None


def has_cookies(cookies: dict[str, str] | None, required_keys: list[str]) -> bool:
    if not cookies:
        return False
    return all(k in cookies for k in required_keys)


def cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _parse_cookie_string(s: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in s.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and v:
                cookies[k] = v
    return cookies

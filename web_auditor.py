"""Fetch a bounded public HTML sample while validating every redirect target."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from safe_http import safe_get, close_response

USER_AGENT = "JARVIS-Business-Audit/1.0"
MAX_BYTES = 350_000
MAX_REDIRECTS = 3


def _is_public_host(hostname: str) -> bool:
    if hostname.lower().rstrip(".") in {"localhost", "localhost.localdomain"}:
        return False
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(item[4][0]).is_global for item in addresses
        )
    except (OSError, ValueError):
        return False


def _validated_url(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw or len(raw) > 2048:
        return None
    candidate = raw if "://" in raw else "https://" + raw
    try:
        parsed = urlparse(candidate)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or not _is_public_host(parsed.hostname)
        ):
            return None
        return candidate
    except ValueError:
        return None


def audit_company_website(url: str | None) -> str:
    if not url:
        return "Nem adott meg weboldalt."
    current_url = _validated_url(url)
    if not current_url:
        return "Érvénytelen vagy nem nyilvános weboldal-cím."

    response = None
    try:
        for redirect_count in range(MAX_REDIRECTS + 1):
            response = safe_get(
                current_url,
                headers={"User-Agent": USER_AGENT},
                timeout=(4, 8),
                                stream=True,
            )
            if 300 <= response.status_code < 400:
                location = response.headers.get("Location")
                close_response(response)
                response = None
                if not location:
                    return "Az oldal átirányítást jelzett, de nem adott célcímet."
                if redirect_count >= MAX_REDIRECTS:
                    return "Az oldal túl sok átirányítást használ."
                target = _validated_url(urljoin(current_url, location))
                if not target:
                    return "Az oldal nem biztonságos címre próbált átirányítani."
                current_url = target
                continue
            if response.status_code != 200:
                status = response.status_code
                response.close()
                response = None
                return f"Weboldal HTTP státusz: {status}."
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                response.close()
                response = None
                return "A cím elérhető, de nem HTML-oldal."

            body = response.raw.read(MAX_BYTES, decode_content=True)
            response.close()
            response = None
            soup = BeautifulSoup(body, "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else "Nincs cím"
            paragraphs = [
                p.get_text(" ", strip=True)
                for p in soup.find_all("p")[:5]
                if p.get_text(" ", strip=True)
            ]
            sample = " ".join(paragraphs)[:450]
            return f"Oldalcím: {title}. Nyilvános szövegminta: {sample or 'Nincs szövegminta.'}"
        return "Az oldal nem adott használható választ."
    except requests.RequestException as exc:
        return f"A weboldal nem volt elérhető ({type(exc).__name__})."
    except Exception as exc:
        return f"Weboldal-elemzési hiba ({type(exc).__name__})."
    finally:
        if response is not None:
            close_response(response)

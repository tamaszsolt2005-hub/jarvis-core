"""Fetch a small public HTML sample for context; reject local/private destinations."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "JARVIS-Business-Audit/1.0"
MAX_BYTES = 350_000


def _is_public_host(hostname: str) -> bool:
    if hostname.lower() in {"localhost", "localhost.localdomain"}:
        return False
    try:
        addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if not address.is_global:
            return False
    return bool(addresses)


def audit_company_website(url: str | None) -> str:
    if not url:
        return "Nem adott meg weboldalt."
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "Érvénytelen weboldal-cím."
    if parsed.username or parsed.password:
        return "A weboldal-cím hitelesítési adatot tartalmaz, ezért kihagyva."
    if not _is_public_host(parsed.hostname):
        return "A weboldal nem nyilvános vagy nem érhető el biztonságosan."

    try:
        response = requests.get(
            url.strip(),
            headers={"User-Agent": USER_AGENT},
            timeout=(4, 8),
            allow_redirects=False,
            stream=True,
        )
        if response.status_code in {301, 302, 303, 307, 308}:
            return "Az oldal átirányítást használ; automatikus követése ki van kapcsolva."
        if response.status_code != 200:
            return f"Weboldal HTTP státusz: {response.status_code}."
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            return "A cím elérhető, de nem HTML-oldal."

        body = response.raw.read(MAX_BYTES, decode_content=True)
        soup = BeautifulSoup(body, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else "Nincs cím"
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in soup.find_all("p")[:5]
            if p.get_text(" ", strip=True)
        ]
        sample = " ".join(paragraphs)[:450]
        return f"Oldalcím: {title}. Nyilvános szövegminta: {sample or 'Nincs szövegminta.'}"
    except requests.RequestException:
        return "A weboldal nem volt elérhető vagy időtúllépés történt."
    except Exception as exc:
        return f"Weboldal-elemzési hiba: {type(exc).__name__}."

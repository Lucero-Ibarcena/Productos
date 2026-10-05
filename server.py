"""Ronda local: busca productos en catálogos públicos de supermercados."""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urljoin, urlparse
from urllib.request import Request, urlopen


RETAILERS = {
    "Carrefour": "https://www.carrefour.com.ar",
    "Jumbo": "https://www.jumbo.com.ar",
    "Disco": "https://www.disco.com.ar",
    "Vea": "https://www.vea.com.ar",
    "ChangoMás": "https://www.masonline.com.ar",
    "Día": "https://diaonline.supermercadosdia.com.ar",
}
PRODUCT_LIMIT = 24
REQUEST_TIMEOUT = 14
CACHE_SECONDS = 35
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def clean_size(name: str) -> str:
    text = name.lower().replace(",", ".")
    match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*(kilogramos?|kgs?|kg|gramos?|grs?|gr|g|mililitros?|ml|cc|litros?|lts?|lt|l)(?![a-z])", text)
    if not match:
        return ""
    amount = float(match.group(1))
    unit = match.group(2)
    if unit.startswith("kg") or unit.startswith("kilo"):
        return f"{amount:g} kg"
    if unit in {"g", "gr", "grs", "gramo", "gramos"}:
        return f"{amount:g} g"
    if unit in {"cc", "ml"} or unit.startswith("mililitro"):
        return f"{amount:g} ml"
    return f"{amount:g} L"


def catalog_url(base: str, query: str) -> str:
    encoded = quote(query, safe="")
    return f"{base}/api/catalog_system/pub/products/search?ft={encoded}&_from=0&_to={PRODUCT_LIMIT - 1}"


def fetch_catalog(store: str, base: str, query: str) -> dict:
    request = Request(
        catalog_url(base, query),
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Origin": base,
            "Referer": base + "/",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        products = []
        if not isinstance(payload, list):
            raise ValueError("Respuesta de catálogo inesperada")
        for product in payload:
            product_name = str(product.get("productName") or "").strip()
            brand = str(product.get("brand") or "").strip()
            if not product_name:
                continue
            for sku in product.get("items", []):
                image = next((entry.get("imageUrl") for entry in sku.get("images", []) if entry.get("imageUrl")), "")
                for seller in sku.get("sellers", []):
                    offer = seller.get("commertialOffer") or seller.get("commercialOffer") or {}
                    try:
                        price = float(offer.get("Price") or offer.get("price") or 0)
                        quantity = float(offer.get("AvailableQuantity", 1) or 0)
                    except (TypeError, ValueError):
                        continue
                    if price <= 0 or quantity <= 0:
                        continue
                    link = str(product.get("link") or "")
                    if link and not link.startswith("http"):
                        link = urljoin(base, link)
                    products.append({
                        "store": store,
                        "name": product_name,
                        "brand": brand,
                        "size": clean_size(product_name),
                        "price": round(price, 2),
                        "listPrice": round(float(offer.get("ListPrice") or offer.get("listPrice") or 0), 2),
                        "image": image,
                        "link": link,
                        "category": next(iter(product.get("categories") or []), "").strip("/"),
                    })
                    break
                else:
                    continue
                break
        return {"store": store, "ok": True, "count": len(products), "items": products[:PRODUCT_LIMIT]}
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError) as error:
        return {"store": store, "ok": False, "count": 0, "items": [], "error": str(error)[:180]}


def search_catalogs(query: str) -> dict:
    normalized_query = " ".join(query.lower().split())
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(normalized_query)
        if cached and now - cached[0] < CACHE_SECONDS:
            result = dict(cached[1])
            result["cached"] = True
            return result

    replies = []
    with ThreadPoolExecutor(max_workers=len(RETAILERS)) as pool:
        futures = [pool.submit(fetch_catalog, name, base, query) for name, base in RETAILERS.items()]
        for future in as_completed(futures):
            replies.append(future.result())
    replies.sort(key=lambda reply: list(RETAILERS).index(reply["store"]))
    items = [product for reply in replies for product in reply["items"]]
    result = {
        "query": query,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "cached": False,
        "items": items,
        "sources": [{key: value for key, value in reply.items() if key != "items"} for reply in replies],
    }
    with _cache_lock:
        _cache[normalized_query] = (now, result)
    return result


class RondaHandler(BaseHTTPRequestHandler):
    server_version = "RondaLocal/1.0"

    def do_GET(self) -> None:
        request_url = urlparse(self.path)
        if request_url.path == "/api/search":
            query = parse_qs(request_url.query).get("q", [""])[0].strip()[:120]
            if len(query) < 2:
                self.send_json(400, {"error": "Escribí al menos dos caracteres para buscar."})
                return
            self.send_json(200, search_catalogs(query))
            return
        if request_url.path in {"/", "/index.html"}:
            try:
                with open("index.html", "rb") as page:
                    body = page.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                self.send_json(500, {"error": "No se encontró index.html junto al servidor."})
            return
        self.send_json(404, {"error": "No encontrado"})

    def send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format_string % args}")


if __name__ == "__main__":
    address = ("127.0.0.1", 8765)
    server = ThreadingHTTPServer(address, RondaHandler)
    print("Ronda está lista: http://127.0.0.1:8765")
    print("Conectando catálogos públicos de Carrefour, Jumbo, Disco, Vea, ChangoMás y Día.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()

"""Small local server for World Wide Search. Uses only the Python standard library."""
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8000"))


def load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def get_json(url, provider, timeout=25):
    req = Request(url, headers={"User-Agent": "WorldWideSearch/0.1"})
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"{provider} connection failed: {exc.reason}") from exc


def translate(query, source="en", target="ru"):
    params = urlencode({"q": query, "langpair": f"{source}|{target}"})
    data = get_json("https://api.mymemory.translated.net/get?" + params, "MyMemory translation")
    translated = data.get("responseData", {}).get("translatedText", "").strip()
    if not translated:
        raise RuntimeError(f"Translation service returned no text for {source}-to-{target} translation.")
    return translated


def search(engine, query, api_key):
    params = {"engine": engine, "api_key": api_key}
    if engine == "yandex":
        params.update({"text": query, "yandex_domain": "yandex.com", "lang": "en", "lr": "84"})
    elif engine == "baidu":
        params.update({"q": query, "ct": "2"})
    else:
        params.update({"q": query, "hl": "en", "gl": "us", "google_domain": "google.com"})
    data = get_json("https://serpapi.com/search.json?" + urlencode(params), f"SerpApi {engine}")
    if data.get("error"):
        raise RuntimeError(data["error"])
    items = data.get("organic_results", [])[:8]
    return [{"title": x.get("title", "Untitled"), "link": x.get("link", ""),
             "snippet": x.get("snippet", "No description available."), "date": x.get("date", "")}
            for x in items if x.get("link")]


def summarize(query, translated, google, yandex):
    """Create a transparent, extractive overview from available search snippets."""
    all_results = google + yandex
    if not all_results:
        return "No search snippets were returned. Try a broader query or check provider settings."
    snippets = [r["snippet"].strip() for r in all_results if r["snippet"].strip() and r["snippet"] != "No description available."]
    if not snippets:
        return f"Searches ran for “{query}” and “{translated}”, but the engines did not provide descriptions. Open the result links to review them."
    # Keep a few distinct snippets; this is deliberately labeled as a snippet-based summary.
    unique = list(dict.fromkeys(snippets))[:3]
    return " ".join(unique)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        pass

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api/translate":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 30_000:
                    return self.send_json(413, {"error": "Translation request is too large."})
                payload = json.loads(self.rfile.read(length))
                items = payload.get("items", [])
                source_language = payload.get("source_language", "ru")
                if source_language not in ("ru", "zh-CN"):
                    return self.send_json(400, {"error": "Unsupported source language."})
                if not isinstance(items, list) or len(items) > 8:
                    return self.send_json(400, {"error": "Send up to 8 results."})
                with ThreadPoolExecutor(max_workers=4) as pool:
                    translated = list(pool.map(
                        lambda item: (translate(str(item.get("title", "")), source_language, "en"),
                                      translate(str(item.get("snippet", "")), source_language, "en") if item.get("snippet") else ""),
                        items))
                return self.send_json(200, {"translations": [{"title_en": title, "snippet_en": snippet}
                                                               for title, snippet in translated]})
            except (HTTPError, RuntimeError, URLError, TimeoutError, ValueError) as exc:
                return self.send_json(502, {"error": f"Could not translate results: {exc}"})
        if self.path != "/api/search":
            return self.send_json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 10_000:
                return self.send_json(413, {"error": "Query is too large."})
            payload = json.loads(self.rfile.read(length))
            query = str(payload.get("query", "")).strip()
            engines = payload.get("engines", ["google", "yandex", "baidu"])
            allowed_engines = {"google", "yandex", "baidu"}
            if not isinstance(engines, list) or not engines or not set(engines).issubset(allowed_engines):
                return self.send_json(400, {"error": "Select at least one valid search engine."})
            if not query:
                return self.send_json(400, {"error": "Enter a search query."})
            if len(query) > 300:
                return self.send_json(400, {"error": "Keep the query under 300 characters."})
            api_key = os.environ.get("SERPAPI_API_KEY", "").strip()
            if not api_key:
                return self.send_json(503, {"error": "Add your SerpApi key to .env (SERPAPI_API_KEY) and restart the server."})

            translated, translated_chinese = "", ""
            with ThreadPoolExecutor(max_workers=2) as pool:
                translation_futures = {}
                if "yandex" in engines:
                    translation_futures["yandex"] = pool.submit(translate, query, "en", "ru")
                if "baidu" in engines:
                    translation_futures["baidu"] = pool.submit(translate, query, "en", "zh-CN")
                if "yandex" in engines:
                    translated = translation_futures["yandex"].result()
                if "baidu" in engines:
                    translated_chinese = translation_futures["baidu"].result()
            with ThreadPoolExecutor(max_workers=len(engines)) as pool:
                search_futures = {}
                for engine in engines:
                    engine_query = query if engine == "google" else translated if engine == "yandex" else translated_chinese
                    search_futures[engine] = pool.submit(search, engine, engine_query, api_key)
                google = search_futures["google"].result() if "google" in engines else []
                yandex = search_futures["yandex"].result() if "yandex" in engines else []
                baidu = search_futures["baidu"].result() if "baidu" in engines else []
            return self.send_json(200, {"query": query, "translated_query": translated,
                                        "google": google, "yandex": yandex, "baidu": baidu,
                                        "translated_query_chinese": translated_chinese,
                                        "engines": engines,
                                        "summary": summarize(query, translated, google, yandex + baidu),
                                        "summary_type": "Search snippet overview"})
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            self.send_json(502, {"error": f"Search/translation provider returned HTTP {exc.code}.", "detail": detail})
        except (URLError, TimeoutError) as exc:
            self.send_json(502, {"error": "Could not reach a search or translation provider.", "detail": str(exc)})
        except (ValueError, RuntimeError, KeyError) as exc:
            self.send_json(502, {"error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": "Search failed unexpectedly.", "detail": str(exc)})


if __name__ == "__main__":
    load_env()
    print(f"SerpApi key: {'loaded' if os.environ.get('SERPAPI_API_KEY', '').strip() else 'missing'}")
    print(f"World Wide Search running at http://localhost:{PORT}")
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except OSError as exc:
        if getattr(exc, "winerror", None) == 10048 or "address already in use" in str(exc).lower():
            print(f"Port {PORT} is already in use. Stop its current server or set PORT to another value.", file=sys.stderr)
            raise SystemExit(1) from exc
        raise

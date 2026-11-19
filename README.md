# World Wide Search

A small multilingual discovery app: enter a topic, translate it into Russian, search Google in English and Yandex in Russian, then review an overview made from the search snippets and the source links.

## Run locally

1. Install Python 3.9 or newer.
2. Get a SerpApi key at [serpapi.com](https://serpapi.com/manage-api-key). The same key provides the Google and Yandex search connectors.
3. Copy `.env.example` to `.env` and set `SERPAPI_API_KEY`.
4. From this folder, run `python server.py`.
5. Open [http://localhost:8000](http://localhost:8000).

The app uses the MyMemory translation endpoint for English-to-Russian translation; it requires network access. Keep `.env` private. The search summary is a concise selection of distinct engine snippets, not an AI-generated assessment of the underlying pages. Follow the source links to check claims and context.

## Implementation

- `server.py` serves the interface and makes provider requests from the backend so the SerpApi key is not sent to the browser.
- `app.js`, `index.html`, and `styles.css` implement the responsive interface and result cards.
- Search results are fetched through SerpApi's Google and Yandex engines.

The official Google Custom Search JSON API is closed to new customers, so this prototype uses SerpApi for Google results. A search provider account/key is required. Translation is handled separately by MyMemory.

const form = document.querySelector("#search-form");
const input = document.querySelector("#query");
const button = document.querySelector("#search-button");
const status = document.querySelector("#status");
const results = document.querySelector("#results");
const translateButton = document.querySelector("#translate-yandex");
const translateBaiduButton = document.querySelector("#translate-baidu");
let yandexResults = [];
let baiduResults = [];
let translationsVisible = false;
let translationsLoaded = false;

function renderResults(target, items, showEnglish = false) {
  target.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty-results";
    empty.textContent = "No organic results were returned for this query.";
    target.append(empty);
    return;
  }
  for (const item of items) {
    const card = document.createElement("a");
    card.className = "result-card";
    card.href = item.link;
    card.target = "_blank";
    card.rel = "noopener noreferrer";
    const title = document.createElement("h4");
    title.textContent = item.title;
    const url = document.createElement("div");
    url.className = "result-url";
    url.textContent = item.link;
    const snippet = document.createElement("p");
    snippet.textContent = item.snippet;
    let titleEnglish;
    let snippetEnglish;
    if (showEnglish && item.title_en) {
      titleEnglish = document.createElement("div");
      titleEnglish.className = "translated-result-title";
      titleEnglish.textContent = item.title_en;
    }
    if (showEnglish && item.snippet_en) {
      snippetEnglish = document.createElement("p");
      snippetEnglish.className = "translated-result-snippet";
      snippetEnglish.textContent = item.snippet_en;
    }
    if (item.date) {
      const date = document.createElement("span");
      date.className = "result-date";
      date.textContent = `· ${item.date}`;
      snippet.append(date);
    }
    card.append(title, url, snippet);
    if (titleEnglish) title.after(titleEnglish);
    if (snippetEnglish) snippet.after(snippetEnglish);
    target.append(card);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = input.value.trim();
  if (!query) return;
  const engines = [...document.querySelectorAll('input[name="engine"]:checked')].map((check) => check.value);
  if (!engines.length) {
    status.className = "status error";
    status.textContent = "Select at least one search engine.";
    return;
  }
  button.disabled = true;
  button.querySelector("span:first-child").textContent = "Searching";
  status.className = "status";
  status.textContent = "Translating your query and searching Google + Yandex…";
  try {
    const response = await fetch("/api/search", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, engines })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Search failed.");
    document.querySelector("#summary").textContent = data.summary;
    document.querySelector("#translated-query").textContent = data.translated_query;
    document.querySelector("#google-count").textContent = `${data.google.length} results`;
    document.querySelector("#yandex-count").textContent = `${data.yandex.length} results`;
    document.querySelector("#baidu-count").textContent = `${data.baidu.length} results`;
    document.querySelector("#translated-query-chinese").textContent = data.translated_query_chinese;
    document.querySelector("#result-count").textContent = `· ${data.google.length + data.yandex.length + data.baidu.length} SOURCES`;
    renderResults(document.querySelector("#google-results"), data.google);
    yandexResults = data.yandex;
    translationsVisible = false;
    translationsLoaded = false;
    translateButton.hidden = yandexResults.length === 0;
    translateButton.textContent = "Translate to English";
    renderResults(document.querySelector("#yandex-results"), yandexResults);
    renderResults(document.querySelector("#baidu-results"), data.baidu);
    document.querySelector("#translated-query").closest(".translation-line").hidden = !data.translated_query;
    document.querySelector("#translated-query-chinese").closest(".baidu-query").hidden = !data.translated_query_chinese;
    for (const engine of ["google", "yandex", "baidu"]) {
      document.querySelector(`#${engine}-results`).closest(".result-group").hidden = !engines.includes(engine);
    }
    baiduResults = data.baidu;
    translateBaiduButton.hidden = baiduResults.length === 0;
    translateBaiduButton.textContent = "Translate to English";
    baiduTranslationsLoaded = false;
    baiduTranslationsVisible = false;
    results.hidden = false;
    status.textContent = "";
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    status.className = "status error";
    status.textContent = error.message;
  } finally {
    button.disabled = false;
    button.querySelector("span:first-child").textContent = "Search";
  }
});

document.querySelectorAll("[data-query]").forEach((chip) => {
  chip.addEventListener("click", () => {
    input.value = chip.dataset.query;
    form.requestSubmit();
  });
});

document.querySelector("#new-search").addEventListener("click", () => {
  input.focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

translateButton.addEventListener("click", async () => {
  if (translationsLoaded) {
    translationsVisible = !translationsVisible;
    translateButton.textContent = translationsVisible ? "Hide English" : "Show English";
    renderResults(document.querySelector("#yandex-results"), yandexResults, translationsVisible);
    return;
  }
  translateButton.disabled = true;
  translateButton.textContent = "Translating…";
  try {
    const response = await fetch("/api/translate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: yandexResults })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Translation failed.");
    yandexResults = yandexResults.map((item, index) => ({ ...item, ...data.translations[index] }));
    translationsLoaded = true;
    translationsVisible = true;
    renderResults(document.querySelector("#yandex-results"), yandexResults, true);
    translateButton.textContent = "Hide English";
  } catch (error) {
    status.className = "status error";
    status.textContent = error.message;
    translateButton.textContent = "Retry translation";
  } finally {
    translateButton.disabled = false;
  }
});

let baiduTranslationsLoaded = false;
let baiduTranslationsVisible = false;
translateBaiduButton.addEventListener("click", async () => {
  if (baiduTranslationsLoaded) {
    baiduTranslationsVisible = !baiduTranslationsVisible;
    translateBaiduButton.textContent = baiduTranslationsVisible ? "Hide English" : "Show English";
    renderResults(document.querySelector("#baidu-results"), baiduResults, baiduTranslationsVisible);
    return;
  }
  translateBaiduButton.disabled = true;
  translateBaiduButton.textContent = "Translating…";
  try {
    const response = await fetch("/api/translate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: baiduResults, source_language: "zh-CN" })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Translation failed.");
    baiduResults = baiduResults.map((item, index) => ({ ...item, ...data.translations[index] }));
    baiduTranslationsLoaded = true;
    baiduTranslationsVisible = true;
    renderResults(document.querySelector("#baidu-results"), baiduResults, true);
    translateBaiduButton.textContent = "Hide English";
  } catch (error) {
    status.className = "status error";
    status.textContent = error.message;
    translateBaiduButton.textContent = "Retry translation";
  } finally {
    translateBaiduButton.disabled = false;
  }
});

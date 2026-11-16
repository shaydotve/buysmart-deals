(function () {
  var feed = document.getElementById("feed");
  var search = document.getElementById("search");
  var chips = document.getElementById("chips");
  var more = document.getElementById("more");
  var status = document.getElementById("status");
  var sentinel = document.getElementById("sentinel");
  if (!feed) return;

  var LABELS = {
    all: "הכל",
    amazon: "Amazon",
    aliexpress: "AliExpress",
    ksp: "KSP",
    other: "אחר"
  };

  var state = {
    manifest: null,
    pages: [],
    loaded: 0,
    loading: false,
    store: "all",
    query: "",
    limit: 24
  };
  var scanPromise = null;

  function isolatePrices(text) {
    return String(text || "").replace(/[0-9][0-9.,]*\s*(?:\$|₪)/g, function (match) {
      return "\u2066" + match + "\u2069";
    });
  }

  function norm(value) {
    return String(value || "").toLowerCase().replace(/\s+/g, " ").trim();
  }

  function needsScan() {
    return state.store !== "all" || norm(state.query) !== "";
  }

  function deals() {
    var flat = [];
    state.pages.forEach(function (page) {
      flat = flat.concat(page);
    });
    return flat;
  }

  function matches(deal) {
    if (state.store !== "all" && deal.store !== state.store) return false;
    var query = norm(state.query);
    if (!query) return true;
    var hay = norm([
      deal.title,
      deal.text,
      deal.store_label,
      deal.price_label,
      deal.local_label,
      (deal.coupons || []).join(" ")
    ].join(" "));
    return hay.indexOf(query) !== -1;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function card(deal, index) {
    var article = el("article", "card");
    var media = el("a", "card-media");
    media.href = "deal/" + deal.id + "/";
    if (deal.image) {
      var image = el("img");
      image.src = deal.image;
      image.alt = "";
      image.width = 800;
      image.height = 800;
      if (index === 0) image.fetchPriority = "high";
      else image.loading = "lazy";
      media.appendChild(image);
    }
    if (deal.image_count > 1) {
      media.appendChild(el("span", "badge", deal.image_count + " תמונות"));
    }
    article.appendChild(media);

    var body = el("div", "card-body");
    var meta = el("div", "meta");
    meta.appendChild(el("span", "store", deal.store_label || ""));
    var time = el("time", null, window.BuySmart.formatDate(deal.date));
    if (deal.date) time.setAttribute("datetime", deal.date);
    meta.appendChild(time);
    body.appendChild(meta);

    var title = el("h2", "title");
    var titleLink = el("a", null, isolatePrices(deal.title || "דיל"));
    titleLink.href = "deal/" + deal.id + "/";
    title.appendChild(titleLink);
    body.appendChild(title);

    if (deal.price_value) {
      var price = el("p", "price");
      price.appendChild(document.createTextNode(deal.price_prefix || ""));
      var value = el("bdi", null, deal.price_value);
      value.dir = "ltr";
      price.appendChild(value);
      body.appendChild(price);
    }
    if (deal.local_value) {
      var local = el("p", "local");
      local.appendChild(document.createTextNode("בארץ כ-"));
      var localValue = el("bdi", null, deal.local_value);
      localValue.dir = "ltr";
      local.appendChild(localValue);
      body.appendChild(local);
    }
    if (deal.coupons && deal.coupons.length) {
      var row = el("div", "coupons");
      deal.coupons.forEach(function (coupon) {
        var button = el("button", "coupon");
        button.type = "button";
        button.setAttribute("data-code", coupon);
        var code = el("span", "coupon-code", coupon);
        code.dir = "ltr";
        button.appendChild(code);
        button.appendChild(el("span", "coupon-hint", "העתקה"));
        row.appendChild(button);
      });
      body.appendChild(row);
    }
    if (deal.link) {
      var cta = el("a", "cta", "לדיל");
      cta.href = deal.link;
      cta.target = "_blank";
      cta.rel = "sponsored noopener noreferrer";
      body.appendChild(cta);
    }
    article.appendChild(body);
    return article;
  }

  function render() {
    var matched = deals().filter(matches);
    var visible = matched.slice(0, state.limit);
    feed.replaceChildren();
    if (!visible.length) {
      var message = state.loading ? "טוען דילים…" : "לא נמצאו דילים";
      feed.appendChild(el("p", "empty", message));
    } else {
      var grid = el("div", "grid");
      visible.forEach(function (deal, index) { grid.appendChild(card(deal, index)); });
      feed.appendChild(grid);
    }
    var total = state.manifest ? state.manifest.deal_count : matched.length;
    if (needsScan()) {
      status.textContent = state.loaded < (state.manifest ? state.manifest.page_count : 0)
        ? "טוען את הארכיון…"
        : "נמצאו " + matched.length.toLocaleString("he-IL") + " דילים";
    } else {
      status.textContent = Number(total).toLocaleString("he-IL") + " דילים";
    }
    var moreInMemory = visible.length < matched.length;
    var moreOnDisk = state.manifest && state.loaded < state.manifest.page_count;
    more.hidden = !(moreInMemory || moreOnDisk);
  }

  async function fetchPage(index) {
    var name = String(index).padStart(3, "0");
    var response = await fetch("data/pages/" + name + ".json");
    if (!response.ok) throw new Error("page " + name);
    var payload = await response.json();
    return payload.deals || [];
  }

  async function loadNext() {
    if (state.loading || !state.manifest || state.loaded >= state.manifest.page_count) return;
    state.loading = true;
    try {
      var page = await fetchPage(state.loaded);
      state.pages.push(page);
      state.loaded += 1;
    } finally {
      state.loading = false;
    }
  }

  async function loadAll() {
    if (!state.manifest) return;
    while (state.loaded < state.manifest.page_count) {
      var batch = [];
      var start = state.loaded;
      while (batch.length < 8 && start + batch.length < state.manifest.page_count) {
        batch.push(start + batch.length);
      }
      var results = await Promise.all(batch.map(fetchPage));
      results.forEach(function (page) { state.pages.push(page); });
      state.loaded += batch.length;
      render();
    }
  }

  function ensureAll() {
    if (state.manifest && state.loaded >= state.manifest.page_count) return Promise.resolve();
    if (!scanPromise) {
      scanPromise = loadAll().finally(function () { scanPromise = null; });
    }
    return scanPromise;
  }

  function renderChips() {
    var stores = ["all"].concat((state.manifest && state.manifest.stores) || []);
    chips.replaceChildren();
    stores.forEach(function (store) {
      var button = el("button", "chip", LABELS[store] || store);
      button.type = "button";
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", store === state.store ? "true" : "false");
      button.addEventListener("click", function () {
        state.store = store;
        state.limit = 24;
        chips.querySelectorAll(".chip").forEach(function (chip) {
          chip.setAttribute("aria-selected", chip === button ? "true" : "false");
        });
        if (needsScan()) {
          render();
          ensureAll().then(render).catch(showError);
        } else {
          render();
        }
      });
      chips.appendChild(button);
    });
  }

  async function revealMore() {
    if (state.loading || !state.manifest) return;
    var matchedCount = deals().filter(matches).length;
    var moreInMemory = state.limit < matchedCount;
    var moreOnDisk = state.loaded < state.manifest.page_count;
    if (!moreInMemory && !moreOnDisk) return;
    try {
      if (needsScan() && moreOnDisk) {
        render();
        await ensureAll();
      } else if (!moreInMemory && moreOnDisk) {
        await loadNext();
      }
      state.limit += 24;
      render();
    } catch (error) {
      showError();
    }
  }

  function showError() {
    status.textContent = "לא הצלחנו לטעון את הדילים. נסו לרענן.";
  }

  var searchTimer = 0;
  search.addEventListener("input", function () {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(function () {
      state.query = search.value;
      state.limit = 24;
      if (needsScan()) {
        render();
        ensureAll().then(render).catch(showError);
      } else {
        render();
      }
    }, 180);
  });

  more.addEventListener("click", revealMore);
  if ("IntersectionObserver" in window) {
    var observer = new IntersectionObserver(function (entries) {
      if (entries.some(function (entry) { return entry.isIntersecting; })) revealMore();
    }, { rootMargin: "400px" });
    observer.observe(sentinel);
  }

  fetch("data/manifest.json")
    .then(function (response) {
      if (!response.ok) throw new Error("manifest");
      return response.json();
    })
    .then(function (manifest) {
      state.manifest = manifest;
      renderChips();
      if (!manifest.page_count) {
        status.textContent = "עדיין אין דילים בארכיון";
        more.hidden = true;
        return;
      }
      return loadNext().then(render);
    })
    .catch(showError);
})();

/* NM UTV shop: a catalog of our eBay listings. Checkout happens on eBay.
   Products come from assets/shop-products.csv, rewritten from eBay by build/ebay_sync.py.
   Columns: show, category, name, price, photo, photos, description, details, buy_link, sku
   - photos: extra photo links separated by |
   - details: longer text for the product page; blank lines start new paragraphs,
     and a block of 2+ lines like "Label: value" becomes a spec table */
(function () {
  var root = document.querySelector("[data-shop-src]");
  if (!root) return;
  var SRC = root.getAttribute("data-shop-src");
  var TEL = root.getAttribute("data-tel"), PHONE = root.getAttribute("data-phone");
  var PER_PAGE = 24;
  var MAKES = ["Can-Am", "CFMOTO", "Chevrolet", "Dodge", "Ford", "GMC", "Honda", "Hummer", "Jeep", "Kawasaki",
               "Polaris", "Ram", "Suzuki", "Toyota", "Yamaha"];

  /* ---------- data ---------- */
  function parseCSV(text) {
    var rows = [], row = [], cell = "", inQ = false;
    for (var i = 0; i < text.length; i++) {
      var c = text[i];
      if (inQ) {
        if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
        else if (c === '"') inQ = false;
        else cell += c;
      } else if (c === '"') inQ = true;
      else if (c === ",") { row.push(cell); cell = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(cell); rows.push(row); row = []; cell = "";
      } else cell += c;
    }
    if (cell || row.length) { row.push(cell); rows.push(row); }
    var head = (rows.shift() || []).map(function (h) { return h.trim().toLowerCase(); });
    return rows.filter(function (r) { return r.join("").trim(); }).map(function (r) {
      var o = {}; head.forEach(function (h, i) { o[h] = (r[i] || "").trim(); }); return o;
    });
  }
  function enrich(it) {
    it.priceNum = parseFloat(String(it.price).replace(/[$,]/g, "")) || 0;
    var brand = String(it.details || "").match(/^Brand:\s*(.+)$/m);
    it.brand = brand ? brand[1].trim() : "";
    var text = (it.name + " " + it.description).toLowerCase();
    it.makes = MAKES.filter(function (m) { return new RegExp("\\b" + m.toLowerCase().replace("-", "\\-") + "\\b").test(text); });
    it.search = (it.name + " " + it.sku + " " + it.description + " " + it.category + " " + it.brand).toLowerCase();
    return it;
  }
  function load(cb, fail) {
    fetch(SRC, {cache: "no-store"}).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (text) {
        cb(parseCSV(text).filter(function (it) { return it.name && it.sku && (it.show || "yes").toLowerCase() !== "no"; }).map(enrich));
      }).catch(fail);
  }

  /* ---------- helpers ---------- */
  function esc(s) { return String(s || "").replace(/[&<>"']/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); }
  function money(n) { return "$" + Number(n).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}); }
  function safeUrl(u) { return /^https:\/\//i.test(u || "") ? u : ""; }
  function itemUrl(it) { return "/shop/item/?sku=" + encodeURIComponent(it.sku); }
  function photos(it) {
    var list = [it.photo].concat(String(it.photos || "").split("|"));
    return list.map(function (u) { return safeUrl(u.trim()); }).filter(function (u, i, a) { return u && a.indexOf(u) === i; });
  }
  function buyButton(it, cls) {
    var link = safeUrl(it.buy_link);
    if (!link) {
      return '<a class="btn ' + (cls || "") + '" href="sms:' + TEL + "?body=" + encodeURIComponent("Hi, I'd like to order: " + it.name + " (" + it.sku + ")") + '">Text to order</a>';
    }
    var label = /(^|\.)ebay\.com\//i.test(link.replace(/^https:\/\//, "")) ? "Buy on eBay" : "Buy now";
    return '<a class="btn ' + (cls || "") + '" href="' + esc(link) + '" target="_blank" rel="noopener">' + label + "</a>";
  }
  function unavailable(el) {
    el.innerHTML = 'The parts list is unavailable right now. Call or text <a href="tel:' + TEL + '">' + PHONE + "</a> and we will help you.";
    el.hidden = false;
  }
  function counts(list, key) {
    var c = {};
    list.forEach(function (it) { [].concat(it[key]).forEach(function (v) { if (v) c[v] = (c[v] || 0) + 1; }); });
    return c;
  }

  /* ---------- shop catalog ---------- */
  function initList() {
    var $ = function (id) { return document.getElementById(id); };
    var grid = $("shop-grid"), status = $("shop-status"), count = $("shop-count"), pager = $("shop-pager");
    var q = $("shop-q"), sortEl = $("shop-sort"), minEl = $("price-min"), maxEl = $("price-max");
    var groups = {category: $("f-category"), makes: $("f-makes"), brand: $("f-brand")};
    var items = [];
    var st = {q: "", sort: "featured", page: 1, min: "", max: "", category: [], makes: [], brand: []};

    // state <-> URL, so filtered views can be bookmarked and shared
    function readUrl() {
      var p = new URLSearchParams(location.search);
      st.q = p.get("q") || ""; st.sort = p.get("sort") || "featured"; st.page = parseInt(p.get("page"), 10) || 1;
      st.min = p.get("min") || ""; st.max = p.get("max") || "";
      ["category", "makes", "brand"].forEach(function (k) { st[k] = p.getAll(k); });
      q.value = st.q; sortEl.value = st.sort; minEl.value = st.min; maxEl.value = st.max;
    }
    function writeUrl() {
      var p = new URLSearchParams();
      if (st.q) p.set("q", st.q);
      if (st.sort !== "featured") p.set("sort", st.sort);
      if (st.min) p.set("min", st.min);
      if (st.max) p.set("max", st.max);
      ["category", "makes", "brand"].forEach(function (k) { st[k].forEach(function (v) { p.append(k, v); }); });
      if (st.page > 1) p.set("page", st.page);
      history.replaceState(null, "", location.pathname + (p.toString() ? "?" + p : ""));
    }

    function matches(it, skip) {
      if (st.q && st.q.toLowerCase().split(/\s+/).some(function (w) { return it.search.indexOf(w) === -1; })) return false;
      if (st.min && it.priceNum < parseFloat(st.min)) return false;
      if (st.max && it.priceNum > parseFloat(st.max)) return false;
      if (skip !== "category" && st.category.length && st.category.indexOf(it.category) === -1) return false;
      if (skip !== "brand" && st.brand.length && st.brand.indexOf(it.brand) === -1) return false;
      if (skip !== "makes" && st.makes.length && !it.makes.some(function (m) { return st.makes.indexOf(m) !== -1; })) return false;
      return true;
    }

    function renderFacet(key, title) {
      var el = groups[key];
      // counts reflect every other active filter, like most store sidebars
      var c = counts(items.filter(function (it) { return matches(it, key); }), key);
      var all = counts(items, key);
      var names = Object.keys(all).sort();
      el.closest(".facet").hidden = names.length < 2;
      el.innerHTML = names.map(function (n) {
        var on = st[key].indexOf(n) !== -1;
        return '<label class="facet-opt' + (c[n] ? "" : " empty") + '"><input type="checkbox" data-facet="' + key + '" value="' + esc(n) + '"' + (on ? " checked" : "") + "> " +
          '<span>' + esc(n) + '</span><span class="facet-n">' + (c[n] || 0) + "</span></label>";
      }).join("");
    }

    function sorted(list) {
      var s = list.slice();
      if (st.sort === "price-asc") s.sort(function (a, b) { return a.priceNum - b.priceNum; });
      else if (st.sort === "price-desc") s.sort(function (a, b) { return b.priceNum - a.priceNum; });
      else if (st.sort === "name") s.sort(function (a, b) { return a.name.localeCompare(b.name); });
      return s;
    }

    function card(it) {
      var photo = photos(it)[0], url = itemUrl(it);
      return '<article class="product">' +
        '<a class="product-img" href="' + url + '">' + (photo ? '<img src="' + esc(photo) + '" alt="' + esc(it.name) + '" loading="lazy">' : "") + "</a>" +
        '<div class="product-body"><p class="product-cat">' + esc(it.category) + "</p>" +
        '<h3><a href="' + url + '">' + esc(it.name) + "</a></h3>" +
        (it.description ? '<p class="product-desc">' + esc(it.description) + "</p>" : "") +
        '<p class="product-price">' + money(it.priceNum) + "</p>" +
        '<div class="product-actions">' + buyButton(it, "btn-sm") + '<a class="btn btn-sm btn-line" href="' + url + '">Details</a></div>' +
        "</div></article>";
    }

    function renderChips() {
      var chips = [];
      if (st.q) chips.push(["q", "", "Search: " + st.q]);
      ["category", "makes", "brand"].forEach(function (k) { st[k].forEach(function (v) { chips.push([k, v, v]); }); });
      if (st.min || st.max) chips.push(["price", "", "Price: " + (st.min ? "$" + st.min : "$0") + " - " + (st.max ? "$" + st.max : "any")]);
      $("shop-chips").innerHTML = chips.map(function (c) {
        return '<button type="button" class="active-chip" data-k="' + c[0] + '" data-v="' + esc(c[1]) + '">' + esc(c[2]) + ' <span aria-hidden="true">&times;</span></button>';
      }).join("") + (chips.length ? '<button type="button" class="clear-all" data-clear>Clear all</button>' : "");
    }

    function render() {
      var list = sorted(items.filter(function (it) { return matches(it); }));
      var pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
      if (st.page > pages) st.page = pages;
      var start = (st.page - 1) * PER_PAGE, shown = list.slice(start, start + PER_PAGE);
      grid.innerHTML = shown.map(card).join("");
      count.textContent = list.length ? "Showing " + (start + 1) + "-" + (start + shown.length) + " of " + list.length + " products" : "";
      status.hidden = !!list.length;
      status.textContent = list.length ? "" : "No products match those filters.";
      pager.innerHTML = pages > 1 ? Array.apply(null, Array(pages)).map(function (_, i) {
        var n = i + 1;
        return '<button type="button" class="page-btn' + (n === st.page ? " on" : "") + '" data-page="' + n + '"' + (n === st.page ? ' aria-current="page"' : "") + ">" + n + "</button>";
      }).join("") : "";
      renderFacet("category"); renderFacet("makes"); renderFacet("brand");
      renderChips();
      $("filters-count").textContent = st.category.length + st.makes.length + st.brand.length + (st.min || st.max ? 1 : 0) || "";
      writeUrl();
    }
    function update() { st.page = 1; render(); }

    document.querySelector(".shop-side").addEventListener("change", function (e) {
      var t = e.target, k = t.getAttribute("data-facet");
      if (!k) return;
      st[k] = t.checked ? st[k].concat(t.value) : st[k].filter(function (v) { return v !== t.value; });
      update();
    });
    $("price-apply").addEventListener("click", function () { st.min = minEl.value.trim(); st.max = maxEl.value.trim(); update(); });
    [minEl, maxEl].forEach(function (el) { el.addEventListener("keydown", function (e) { if (e.key === "Enter") $("price-apply").click(); }); });
    var t;
    q.addEventListener("input", function () { clearTimeout(t); t = setTimeout(function () { st.q = q.value.trim(); update(); }, 150); });
    sortEl.addEventListener("change", function () { st.sort = sortEl.value; update(); });
    pager.addEventListener("click", function (e) {
      var b = e.target.closest("[data-page]"); if (!b) return;
      st.page = parseInt(b.getAttribute("data-page"), 10); render();
      document.getElementById("products").scrollIntoView({behavior: "smooth"});
    });
    $("shop-chips").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      if (b.hasAttribute("data-clear")) {
        st.q = ""; st.min = ""; st.max = ""; st.category = []; st.makes = []; st.brand = [];
        q.value = ""; minEl.value = ""; maxEl.value = "";
      } else {
        var k = b.getAttribute("data-k"), v = b.getAttribute("data-v");
        if (k === "q") { st.q = ""; q.value = ""; }
        else if (k === "price") { st.min = st.max = ""; minEl.value = maxEl.value = ""; }
        else st[k] = st[k].filter(function (x) { return x !== v; });
      }
      update();
    });
    // mobile filter drawer
    var side = document.querySelector(".shop-side");
    function drawer(open) { side.classList.toggle("open", open); document.body.classList.toggle("drawer-open", open); }
    $("filters-open").addEventListener("click", function () { drawer(true); });
    $("filters-close").addEventListener("click", function () { drawer(false); });
    $("filters-done").addEventListener("click", function () { drawer(false); });

    readUrl();
    load(function (list) {
      items = list;
      if (!items.length) { status.textContent = "New products coming soon. Call " + PHONE + " for what you need."; status.hidden = false; return; }
      render();
    }, function () { unavailable(status); });
  }

  /* ---------- product page ---------- */
  function details(text) {
    var specs = [], paras = [];
    String(text || "").split(/\n\s*\n/).forEach(function (block) {
      var lines = block.split("\n").map(function (l) { return l.trim(); }).filter(Boolean);
      if (lines.length > 1 && lines.every(function (l) { return /^[^:]{1,40}:\s*\S/.test(l); })) {
        lines.forEach(function (l) { var k = l.indexOf(":"); specs.push([l.slice(0, k), l.slice(k + 1).trim()]); });
      } else if (lines.length) {
        paras.push(lines.map(esc).join("<br>"));
      }
    });
    return {specs: specs, html: paras.map(function (p) { return "<p>" + p + "</p>"; }).join("")};
  }
  function initItem() {
    var box = document.getElementById("item"), status = document.getElementById("item-status");
    var sku = new URLSearchParams(location.search).get("sku") || "";
    load(function (list) {
      var it = list.filter(function (x) { return x.sku === sku; })[0];
      if (!it) {
        status.innerHTML = 'We couldn\'t find that product. It may have sold out. <a href="/shop/">Back to the shop</a> or call <a href="tel:' + TEL + '">' + PHONE + "</a>.";
        status.hidden = false; return;
      }
      document.title = it.name + " | NM UTV Shop";
      var crumb = document.getElementById("crumb-name"); if (crumb) crumb.textContent = it.name;
      var pics = photos(it), d = details(it.details);
      var specs = [[/^\d{9,}$/.test(it.sku) ? "eBay item #" : "Part number", it.sku], ["Category", it.category]].concat(d.specs);
      var onEbay = /ebay\.com\//i.test(it.buy_link || "");
      box.innerHTML =
        '<div class="item-gallery">' +
          (pics.length ? '<div class="item-main"><img id="item-main" src="' + esc(pics[0]) + '" alt="' + esc(it.name) + '"></div>' : "") +
          (pics.length > 1 ? '<div class="item-thumbs">' + pics.map(function (u, i) {
            return '<button type="button" class="item-thumb' + (i ? "" : " on") + '" data-src="' + esc(u) + '" aria-label="Photo ' + (i + 1) + '"><img src="' + esc(u) + '" alt="" loading="lazy"></button>';
          }).join("") + "</div>" : "") +
        "</div>" +
        '<div class="item-info">' +
          '<p class="product-cat">' + esc(it.category) + "</p>" +
          "<h1>" + esc(it.name) + "</h1>" +
          '<p class="item-price">' + money(it.priceNum) + "</p>" +
          (it.description ? '<p class="item-summary">' + esc(it.description) + "</p>" : "") +
          buyButton(it, "btn-block") +
          '<p class="item-note">' + (onEbay ? "Secure checkout on eBay with eBay Money Back Guarantee. " : "") +
            'Questions about fitment? <a href="sms:' + TEL + "?body=" + encodeURIComponent("Hi, I have a question about " + it.name + " (" + it.sku + ")") + '">Text us</a> or call <a href="tel:' + TEL + '">' + PHONE + "</a>.</p>" +
          '<table class="item-specs">' + specs.map(function (s) { return "<tr><th>" + esc(s[0]) + "</th><td>" + esc(s[1]) + "</td></tr>"; }).join("") + "</table>" +
        "</div>" +
        (d.html ? '<div class="item-details prose"><h2>Product details</h2>' + d.html + "</div>" : "");
      box.hidden = false;
      box.addEventListener("click", function (e) {
        var t = e.target.closest(".item-thumb"); if (!t) return;
        document.getElementById("item-main").src = t.getAttribute("data-src");
        box.querySelectorAll(".item-thumb").forEach(function (b) { b.classList.toggle("on", b === t); });
      });
      var more = list.filter(function (x) { return x.category === it.category && x.sku !== it.sku; }).slice(0, 4);
      if (more.length) {
        document.getElementById("item-more").innerHTML = '<h2>More ' + esc(it.category) + '</h2><div class="shop-grid">' + more.map(function (x) {
          var p = photos(x)[0], url = itemUrl(x);
          return '<article class="product"><a class="product-img" href="' + url + '">' + (p ? '<img src="' + esc(p) + '" alt="' + esc(x.name) + '" loading="lazy">' : "") + "</a>" +
            '<div class="product-body"><h3><a href="' + url + '">' + esc(x.name) + '</a></h3><p class="product-price">' + money(x.priceNum) + '</p>' +
            '<div class="product-actions">' + buyButton(x, "btn-sm") + '<a class="btn btn-sm btn-line" href="' + url + '">Details</a></div></div></article>';
        }).join("") + "</div>";
      }
    }, function () { unavailable(status); });
  }

  if (document.getElementById("shop-grid")) initList();
  if (document.getElementById("item")) initItem();
})();

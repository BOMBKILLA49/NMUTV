/* NM UTV shop: products come from a published Google Sheet (CSV), read in the browser.
   Columns: show, category, name, price, photo, photos, description, details, buy_link, sku
   - photos: extra photo links separated by |
   - details: longer text for the product page; blank lines start new paragraphs,
     and a block of 2+ lines like "Label: value" becomes a spec table */
(function () {
  var root = document.querySelector("[data-shop-src]");
  if (!root) return;
  var SRC = root.getAttribute("data-shop-src");
  var TEL = root.getAttribute("data-tel"), PHONE = root.getAttribute("data-phone");

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
  function esc(s) { return String(s || "").replace(/[&<>"']/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); }
  function money(p) { var n = parseFloat(String(p).replace(/[$,]/g, "")); return isNaN(n) ? "" : "$" + n.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}); }
  function safeUrl(u) { return /^https:\/\//i.test(u || "") ? u : ""; }
  function itemUrl(it) { return "/shop/item/?sku=" + encodeURIComponent(it.sku); }
  function photos(it) {
    var list = [it.photo].concat(String(it.photos || "").split("|"));
    return list.map(function (u) { return safeUrl(u.trim()); }).filter(function (u, i, a) { return u && a.indexOf(u) === i; });
  }
  function buyButton(it) {
    var link = safeUrl(it.buy_link);
    return link
      ? '<a class="btn btn-block" href="' + esc(link) + '" target="_blank" rel="noopener">Buy now</a>'
      : '<a class="btn btn-block" href="sms:' + TEL + "?body=" + encodeURIComponent("Hi, I'd like to order: " + it.name + (it.sku ? " (" + it.sku + ")" : "")) + '">Text to order</a>';
  }
  function load(cb, fail) {
    fetch(SRC, {cache: "no-store"}).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (text) {
        cb(parseCSV(text).filter(function (it) { return it.name && it.sku && (it.show || "yes").toLowerCase() !== "no"; }));
      }).catch(fail);
  }
  function unavailable(el) {
    el.innerHTML = 'The parts list is unavailable right now. Call or text <a href="tel:' + TEL + '">' + PHONE + "</a> and we will help you.";
    el.hidden = false;
  }

  /* ---------- shop grid ---------- */
  function initList() {
    var grid = document.getElementById("shop-grid"), status = document.getElementById("shop-status");
    var q = document.getElementById("shop-q"), catsEl = document.getElementById("shop-cats");
    var items = [], cat = "All";
    function render() {
      var term = q.value.trim().toLowerCase();
      var list = items.filter(function (it) {
        return (cat === "All" || it.category === cat) &&
          (!term || (it.name + " " + it.sku + " " + it.description + " " + it.category).toLowerCase().indexOf(term) !== -1);
      });
      grid.innerHTML = list.map(function (it) {
        var photo = photos(it)[0], url = itemUrl(it);
        return '<article class="product">' +
          (photo ? '<a class="product-img" href="' + url + '"><img src="' + esc(photo) + '" alt="' + esc(it.name) + '" loading="lazy"></a>' : "") +
          '<div class="product-body"><p class="product-cat">' + esc(it.category) + "</p>" +
          '<h3><a href="' + url + '">' + esc(it.name) + "</a></h3>" +
          (it.description ? '<p class="product-desc">' + esc(it.description) + "</p>" : "") +
          '<p class="product-price">' + esc(money(it.price)) + "</p>" + buyButton(it) +
          '<a class="product-more" href="' + url + '">View details</a></div></article>';
      }).join("");
      status.textContent = list.length ? "" : (items.length ? "No parts match that search." : "");
      status.hidden = !status.textContent;
    }
    function renderCats() {
      var cats = ["All"].concat(items.map(function (i) { return i.category; }).filter(function (c, i, a) { return c && a.indexOf(c) === i; }).sort());
      catsEl.innerHTML = cats.map(function (c) {
        return '<button type="button" class="chip' + (c === cat ? " on" : "") + '" data-cat="' + esc(c) + '">' + esc(c) + "</button>";
      }).join("");
    }
    catsEl.addEventListener("click", function (e) {
      var b = e.target.closest("[data-cat]"); if (!b) return;
      cat = b.getAttribute("data-cat"); renderCats(); render();
    });
    q.addEventListener("input", render);
    load(function (list) {
      items = list; renderCats(); render();
      if (!items.length) { status.textContent = "New parts coming soon. Call " + PHONE + " for what you need."; status.hidden = false; }
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
        status.innerHTML = 'We couldn\'t find that part. <a href="/shop/">Back to the shop</a> or call <a href="tel:' + TEL + '">' + PHONE + "</a>.";
        status.hidden = false; return;
      }
      document.title = it.name + " | NM UTV Shop";
      var crumb = document.getElementById("crumb-name"); if (crumb) crumb.textContent = it.name;
      var pics = photos(it), d = details(it.details);
      var specs = [["Part number", it.sku], ["Category", it.category]].concat(d.specs);
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
          '<p class="item-price">' + esc(money(it.price)) + "</p>" +
          (it.description ? '<p class="item-summary">' + esc(it.description) + "</p>" : "") +
          buyButton(it) +
          '<p class="item-note">Free shipping to the lower 48. Alaska, Hawaii or a custom order? <a href="sms:' + TEL + "?body=" + encodeURIComponent("Hi, I have a question about " + it.name + " (" + it.sku + ")") + '">Text us</a> for a quote.</p>' +
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
          return '<article class="product">' + (p ? '<a class="product-img" href="' + url + '"><img src="' + esc(p) + '" alt="' + esc(x.name) + '" loading="lazy"></a>' : "") +
            '<div class="product-body"><h3><a href="' + url + '">' + esc(x.name) + '</a></h3><p class="product-price">' + esc(money(x.price)) + '</p><a class="btn btn-block" href="' + url + '">View details</a></div></article>';
        }).join("") + "</div>";
      }
    }, function () { unavailable(status); });
  }

  if (document.getElementById("shop-grid")) initList();
  if (document.getElementById("item")) initItem();
})();

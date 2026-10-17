document$.subscribe(function () {
  var art = document.querySelector("article.md-content__inner");
  if (!art) return;
  var re = /(\(2\.26\.26\.4, not re-verified\))|(\binferred\b)/gi;
  var walker = document.createTreeWalker(art, NodeFilter.SHOW_TEXT, {
    acceptNode: function (n) {
      return n.parentElement.closest("code,pre,a,.badge,.admonition-title,h1,h2,h3,h4,.headerlink")
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
    }
  });
  var nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(function (n) {
    var t = n.nodeValue, last = 0, m, frag = null;
    re.lastIndex = 0;
    while ((m = re.exec(t))) {
      frag = frag || document.createDocumentFragment();
      frag.appendChild(document.createTextNode(t.slice(last, m.index)));
      var s = document.createElement("span");
      s.className = "badge " + (m[1] ? "badge-unverified" : "badge-inferred");
      s.textContent = m[0];
      frag.appendChild(s);
      last = m.index + m[0].length;
    }
    if (frag) {
      frag.appendChild(document.createTextNode(t.slice(last)));
      n.parentNode.replaceChild(frag, n);
    }
  });
  var h1 = art.querySelector("h1");
  if (h1 && !art.querySelector(".reading-meta") && location.pathname.replace(/\/$/, "").split("/").length > 1) {
    var words = (art.innerText || "").split(/\s+/).length;
    var p = document.createElement("div");
    p.className = "reading-meta";
    var L = {de: "Min. Lesezeit", es: "min de lectura", "pt-BR": "min de leitura", ru: "мин. чтения", ar: "دقيقة للقراءة", tr: "dk okuma"}[document.documentElement.lang];
    var n = Math.max(1, Math.round(words / 220));
    p.textContent = L ? n + " " + L : "~" + n + " min read";
    h1.insertAdjacentElement("afterend", p);
  }
});

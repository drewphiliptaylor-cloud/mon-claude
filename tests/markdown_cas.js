// Cas du rendu Markdown sûr (web/js/outils.js), exécutés par tests/test_markdown.py avec JavaScriptCore.
const cas = [
  ["<img src=x onerror=alert(1)>", s => !s.includes("<img"), "le HTML de Claude ne doit jamais être interprété"],
  ["**gras** et `code <b>`", s => s.includes("<strong>gras</strong>") && s.includes("<code>code &lt;b&gt;</code>"), "gras et code"],
  ["[lien](javascript:alert(1))", s => !s.includes("href"), "lien javascript: refusé"],
  ["[lien](https://a.fr/\"onmouseover=x)", s => !s.includes('"onmouseover'), "guillemet dans un lien neutralisé"],
  ["| A | B |\n|---|---|\n| 1 | **2** |\nfin", s => s.includes("<th>A</th>") && s.includes("<td><strong>2</strong></td>") && s.includes("<p>fin</p>"), "tableau"],
  ["- un\n- deux\n\n1. a", s => s.includes("<ul><li>un</li><li>deux</li></ul><ol><li>a</li></ol>"), "listes"],
  ["```\n<script>\n```", s => s.includes("<pre><code>&lt;script&gt;</code></pre>"), "bloc de code échappé"],
];
let echecs = 0;
for (const [src, f, nom] of cas) {
  const h = markdown(src);
  if (!f(h)) { echecs++; print("ECHEC " + nom + " : " + JSON.stringify(src) + " => " + h); }
}
print(echecs ? "ECHECS " + echecs : "OK " + cas.length);

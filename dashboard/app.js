/* World Simulation dashboard. Renders everything from data.json (built by `python -m worldsim build`). */
(function () {
  "use strict";
  var D = null;
  var $ = function (s) { return document.querySelector(s); };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function safeUrl(u) { return /^https?:\/\//.test(u || "") ? u : "#"; }
  function link(u, text) { return '<a href="' + esc(safeUrl(u)) + '" target="_blank" rel="noopener">' + esc(text || u) + "</a>"; }
  function pct(p) { return p == null ? "n/a" : Math.round(p * 1000) / 10 + "%"; }
  function num(x, d) { return x == null ? "n/a" : Number(x).toFixed(d == null ? 3 : d); }
  function when(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d)) return esc(iso);
    var p2 = function (n) { return (n < 10 ? "0" : "") + n; };
    return p2(d.getMonth() + 1) + "/" + p2(d.getDate()) + "/" + d.getFullYear() + " " + p2(d.getHours()) + ":" + p2(d.getMinutes());
  }
  // Dates show as MM/DD/YYYY everywhere on the site.
  function day(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    return m ? m[2] + "/" + m[3] + "/" + m[1] : esc(iso || "");
  }
  function money(x) { return x == null ? "" : "$" + (x >= 1e9 ? (x / 1e9).toFixed(1) + "B" : (x / 1e6).toFixed(1) + "M"); }
  var LABEL_CLASS = { established_fact: "ok", official_position: "", observed_behavior: "ok", evidence_backed_inference: "warn", hypothesis: "warn", speculation: "bad" };
  function label(l) { return '<span class="pill ' + (LABEL_CLASS[l] || "") + '">' + esc(String(l).replace(/_/g, " ")) + "</span>"; }
  function srcList(sources) {
    return (sources || []).map(function (s) {
      return typeof s === "string" ? link(s, new URL(s).hostname) : link(s.url, s.publisher) + (s.kind ? ' <span class="muted small">(' + esc(s.kind.replace(/_/g, " ")) + ")</span>" : "");
    }).join(", ");
  }
  function spark(series) {
    if (!series || series.length < 2) return "";
    var w = 200, h = 34, pts = series.map(function (p, i) {
      return (i / (series.length - 1)) * w + "," + (h - 2 - p[1] * (h - 4));
    }).join(" ");
    return '<svg class="spark" viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none"><polyline fill="none" stroke="currentColor" stroke-width="1.5" points="' + pts + '"/></svg>';
  }
  function md(text) {
    var out = [], inList = false;
    String(text).split("\n").forEach(function (line) {
      var l = esc(line)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/`(.+?)`/g, "<code>$1</code>")
        .replace(/\[(.+?)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
        .replace(/\[(.+?)\]\(([^)]+)\)/g, "$1");
      if (/^- /.test(line)) { if (!inList) { out.push("<ul>"); inList = true; } out.push("<li>" + l.slice(2) + "</li>"); return; }
      if (inList) { out.push("</ul>"); inList = false; }
      if (/^### /.test(line)) out.push("<h3>" + l.slice(4) + "</h3>");
      else if (/^## /.test(line)) out.push("<h2>" + l.slice(3) + "</h2>");
      else if (/^# /.test(line)) out.push("<h1>" + l.slice(2) + "</h1>");
      else if (/^&gt; /.test(l)) out.push("<blockquote>" + l.slice(5) + "</blockquote>");
      else if (line.trim()) out.push("<p>" + l + "</p>");
    });
    if (inList) out.push("</ul>");
    return out.join("");
  }
  var IND_NAMES = { airspace: "Airspace closures", home_front: "Home Front Command", reserves: "Reserve call-ups",
    late_night_cabinet: "Late-night cabinet", us_advisory: "US departure orders", us_military_moves: "US military moves",
    gps_jamming: "GPS jamming",
    infrastructure_fire: "Fires at energy sites" };

  // ---------- views ----------
  // Plain words for the trade terms, used everywhere on the page.
  var WORDS = { watch: "Alert level", heuristic: "a rule of thumb, not a tested model", brier: "Prediction error (lower is better)",
    calibration: "Does 70% mean 70%?", survival: "How long it holds", baserate: "How often this happened before", eventstudy: "How markets reacted before" };

  function statusBar() {
    var w = D.watch, M = D.markets_now;
    var lvl = w.level === "baseline" ? "ok" : w.level === "elevated" ? "warn" : "bad";
    var stress = M ? (M.level === "calm" ? "ok" : M.level === "some stress" ? "warn" : "bad") : "";
    return '<div class="status"><span><strong>' + WORDS.watch + ':</strong> <span class="pill ' + lvl + '">' + esc(w.level) + "</span> " + w.active_count + " of " + Object.keys(w.indicators).length + " signals active</span>" +
      (M ? '<span class="sep">|</span><span><strong>Markets:</strong> <span class="pill ' + stress + '">' + esc(M.level) + "</span></span>" : "") +
      '<span class="sep">|</span><span class="muted">' + D.scorecard.live.resolved + " of " + D.forecasts.live.length + " forecasts resolved, scored against the crowd</span>" +
      '<span class="sep">|</span><span class="muted">built ' + when(D.generated_at) + "</span></div>";
  }

  function hero() {
    var M = D.markets_now, O = D.outlook;
    if (!M) return '<div class="card"><h3>Markets now</h3><p class="muted small">No quotes yet. Run <code>python -m worldsim live</code>.</p></div>';
    var cls = M.level === "calm" ? "ok" : M.level === "some stress" ? "warn" : "bad";
    var pick = {};
    M.quotes.forEach(function (q) { pick[q.alias] = q; });
    var strike = O && O.war_risk_priced && O.war_risk_priced.length ? O.war_risk_priced[0] : null;
    var spread = M.reads.filter(function (r) { return /Brent minus WTI/.test(r.what); })[0];
    function tick(alias, name) {
      var q = pick[alias];
      if (!q) return "";
      var c = q.change_pct == null ? "" : (q.change_pct > 0 ? "+" : "") + q.change_pct.toFixed(1) + "%";
      var s = q.size === "very big move" ? "bad" : q.size === "big move" ? "warn" : "ok";
      return '<div><div class="kicker">' + esc(name) + '</div><div class="v">' + Number(q.price).toLocaleString(undefined, { maximumFractionDigits: 2 }) + '</div><div class="small"><span class="pill ' + s + '">' + c + "</span></div></div>";
    }
    return '<div class="card hero"><div class="kicker">Markets now &middot; ' + esc(D.live_source || "") + '</div>' +
      '<div class="grid two">' +
      '<div><div class="kicker">What bettors price</div><div class="big">' + (strike ? esc(strike.split(" chance")[0]) : "n/a") + '</div><div class="small muted">' + (strike ? esc("chance" + strike.split(" chance")[1]) : "no ladder prices yet") + "</div></div>" +
      '<div><div class="kicker">Middle East market stress</div><div class="big"><span class="pill ' + cls + '" style="font-size:16px">' + esc(M.level) + "</span></div>" +
      '<div class="small muted">' + (M.flags.length ? esc(M.flags.join("; ").replace(/^./, function (c) { return c.toUpperCase(); })) + "." : "Nothing unusual in oil, defense, shipping or the shekel.") +
      (spread ? " " + esc(spread.what.replace(" (seaborne oil premium)", "")) + " " + esc(spread.value) + ", " + esc(spread.detail) + "." : "") + "</div></div></div>" +
      '<div class="ticker">' + tick("BRENT", "Brent oil") + tick("OVX", "Oil fear index") + tick("ITA", "US defense ETF") + tick("ESLT", "Elbit") + tick("USDILS", "Dollar in shekels") + tick("TA125", "Tel Aviv 125") + "</div>" +
      '<p class="small muted" style="margin-bottom:0">Moves are the latest session against each asset’s normal daily swing. A description, not a signal. <a href="#markets">All quotes and past reactions</a>.</p></div>';
  }

  function overview() {
    var O = D.outlook;
    var h = statusBar() + hero();
    var active = Object.keys(D.watch.indicators).filter(function (k) { return D.watch.indicators[k].active; });
    h += '<div class="grid two" style="margin-top:16px">';
    h += '<div class="card"><h3>Why the alert level is ' + esc(D.watch.level) + "</h3>" +
      (active.length ? indicatorList(true) : '<p class="small muted">No leading indicator is firing: no airspace closures, Home Front Command alerts, call-ups, late-night cabinet meetings or US departure orders in their windows.</p>') +
      '<p class="small muted">The level is ' + WORDS.heuristic + '. <a href="#markets">All signals</a>.</p></div>';
    var verified = D.timeline.filter(function (e) { return e.verified && !e.disputed; }).slice(0, 3);
    h += '<div class="card"><h3>Recent events</h3><ul class="timeline">' + (verified.length ? verified : D.timeline.slice(0, 3)).map(function (e) {
      return '<li><div class="d">' + day(e.date) + " &middot; " + esc(e.category) + "</div><div>" + esc(e.title) + "</div></li>";
    }).join("") + '</ul><p class="small muted"><a href="#news">Full timeline and news</a>.</p></div></div>';
    if (O && O.headlines && O.headlines.length) {
      h += '<h3 style="margin-top:24px">Most likely outcomes</h3>' + headlineBox(3);
    }
    var gaps = (O && O.forecasts || []).filter(function (r) { return r.gap_points != null && Math.abs(r.gap_points) >= 10 && r.group !== "Decided" && r.group !== "Withdrawn"; }).slice(0, 4);
    if (gaps.length) {
      h += '<div class="card"><h3>Where we differ from the crowd</h3><div class="tablewrap"><table><thead><tr><th>Question</th><th class="num">Ours</th><th class="num">Crowd</th><th>View</th></tr></thead><tbody>' +
        gaps.map(function (r) { return "<tr><td>" + esc(r.question) + '</td><td class="num"><strong>' + pct(r.ours) + '</strong></td><td class="num">' + pct(r.market) + "</td><td>" + viewPill(r.view) + "</td></tr>"; }).join("") +
        '</tbody></table></div><p class="small muted">Ours is scored when the question resolves. <a href="#forecasts">All forecasts and the scorecard</a>.</p></div>';
    }
    return h;
  }

  function viewPill(v) {
    return v === "independent" ? '<span class="pill warn">our own view</span>' : '<span class="pill">crowd, bias removed</span>';
  }

  function indicatorList(onlyActive) {
    var rows = Object.keys(D.watch.indicators).filter(function (k) { return !onlyActive || D.watch.indicators[k].active; });
    if (!rows.length) return '<p class="muted">None active right now.</p>';
    return rows.map(function (k) {
      var it = D.watch.indicators[k];
      return '<div style="margin-bottom:10px"><span class="pill ' + (it.active ? "warn" : "ok") + '">' + (it.active ? "active" : "quiet") + "</span> <strong>" +
        esc(IND_NAMES[k] || k) + '</strong> <span class="muted small">' + it.count + " in " + it.window_hours + "h</span>" +
        (it.latest.length ? '<div class="small">' + it.latest.slice(0, 2).map(function (l) {
          return link(l.url, l.title) + ' <span class="muted">' + when(l.at) + "</span>";
        }).join("<br>") + "</div>" : "") + "</div>";
    }).join("");
  }

  function watch() {
    var h = '<h2>Leading indicators</h2><p class="muted small">Big operations usually leave public tracks a day or two ahead. One signal means little. Several kinds at once moves the odds. The level is ' + WORDS.heuristic + '. The lead-lag test found no indicator that moves before Polymarket prices.</p>';
    h += '<div class="card" style="margin-bottom:16px">' + indicatorList(false) + "</div>";
    h += '<div class="card"><h3>Raw signals: aircraft, GPS, satellite fires, fleet, advisories</h3><ul class="feed">' + D.signals.slice(0, 40).map(feedItem).join("") + "</ul></div>";
    return h;
  }

  function feedItem(o) {
    var SL = { he: "iw", fa: "fa", ar: "ar" };
    var tr = SL[o.lang] ? ' &middot; <a target="_blank" rel="noopener" href="https://translate.google.com/translate?sl=' + SL[o.lang] + '&tl=en&u=' + encodeURIComponent(o.url) + '">translate</a>' : "";
    return '<li><div class="t" dir="auto" lang="' + esc(o.lang) + '">' + link(o.url, o.title) + "</div>" +
      '<div class="m">' + esc(o.source_id) + " &middot; " + when(o.published_at || o.observed_at) + tr +
      (o.indicators.length ? " &middot; " + o.indicators.map(function (i) { return '<span class="pill warn">' + esc(IND_NAMES[i] || i) + "</span>"; }).join("") : "") +
      (o.tags.length ? " " + o.tags.map(function (t) { return '<span class="pill">' + esc(t) + "</span>"; }).join("") : "") + "</div></li>";
  }

  function feed() {
    var sources = Array.from(new Set(D.feed.map(function (o) { return o.source_id; }))).sort();
    var h = '<h2>Hebrew and English news</h2><p class="muted small">Headlines and short excerpts with links. Hebrew outlets and reporters’ Telegram channels often run hours ahead of English wires. Telegram is an unverified signal.</p>';
    h += '<div class="toolbar"><input id="q" placeholder="Search (Hebrew or English)" aria-label="Search feed"><select id="src" aria-label="Source"><option value="">All sources</option>' +
      sources.map(function (s) { return "<option>" + esc(s) + "</option>"; }).join("") + '</select><select id="lang" aria-label="Language"><option value="">All languages</option><option value="he">Hebrew</option><option value="fa">Persian</option><option value="ar">Arabic</option><option value="en">English</option></select>' +
      '<label class="small"><input type="checkbox" id="flag"> flagged only</label></div><ul class="feed" id="feedlist"></ul>';
    setTimeout(function () {
      function draw() {
        var q = $("#q").value.trim().toLowerCase(), s = $("#src").value, l = $("#lang").value, f = $("#flag").checked;
        var items = D.feed.filter(function (o) {
          return (!s || o.source_id === s) && (!l || o.lang === l) && (!f || o.indicators.length) &&
            (!q || (o.title + " " + (o.excerpt || "")).toLowerCase().indexOf(q) >= 0);
        });
        $("#feedlist").innerHTML = items.slice(0, 200).map(feedItem).join("") || '<li class="muted">Nothing matches.</li>';
      }
      ["#q", "#src", "#lang", "#flag"].forEach(function (id) { $(id).addEventListener("input", draw); });
      draw();
    });
    return h;
  }

  function marketsView() {
    var h = '<h2>Polymarket prices</h2><p class="muted small">Polymarket prices logged on every collect run. This is the number to beat. A price is the crowd’s probability, not a fact.</p><div class="grid">';
    h += D.markets.map(function (m) {
      return '<div class="card"><div class="kicker">' + esc(m.topic) + " &middot; " + esc(m.countries.join(", ")) + "</div><h3>" + link(m.url, m.label) + "</h3>" +
        '<div class="big">' + pct(m.probability) + "</div>" +
        '<div class="small muted">' + (m.change != null ? (m.change >= 0 ? "+" : "") + Math.round(m.change * 1000) / 10 + " pts since first logged &middot; " : "") +
        (m.end_date ? "ends " + day(m.end_date) : "") + (m.as_of ? " &middot; as of " + when(m.as_of) : " &middot; not yet collected") + "</div>" + spark(m.series) + "</div>";
    }).join("");
    return h + "</div>";
  }

  function headlineBox(limit) {
    var O = D.outlook;
    if (!O || !O.headlines || !O.headlines.length) return "";
    return '<div class="grid" style="margin-bottom:16px">' + O.headlines.slice(0, limit || O.headlines.length).map(function (x) {
      return '<div class="card"><div class="kicker">' + esc(x.title) + '</div><div style="font:600 20px var(--serif)">' + esc(x.answer) + '</div><div class="small muted">' + esc(x.detail) + "</div></div>";
    }).join("") + "</div>";
  }

  function forecastsView() {
    var O = D.outlook;
    var h = '<h2>Forecasts</h2>' +
      '<div class="banner"><strong>Our number</strong> is this tool’s forecast, the one that gets scored. <strong>Polymarket</strong> is what bettors are paying right now. When the two are within ' + 5 + ' points we call it the same. <strong>Crowd, bias removed</strong> means the market price with the backtest’s known long-shot bias taken out; <strong>our own view</strong> means a number we argued from the player cards. Tap a row for the rules and the reasoning.</div>' + '<h3>Most likely outcomes</h3>' + headlineBox();
    if (!O || !O.forecasts.length) return h + '<p class="muted">No forecasts yet. Start one with <code>python -m worldsim new-forecast --market &lt;slug&gt;</code>.</p>';
    var groups = ["Past due", "This week", "This month", "Later", "Decided", "Withdrawn"];
    groups.forEach(function (g) {
      var rows = O.forecasts.filter(function (r) { return r.group === g; });
      if (!rows.length) return;
      var collapsed = g === "Withdrawn" || g === "Decided";
      h += (collapsed ? "<details><summary><h3 style=\"display:inline\">" + g + " (" + rows.length + ")</h3></summary>" : "<h3 style=\"margin-top:20px\">" + g + "</h3>") +
        '<div class="card tablewrap"><table class="fc"><thead><tr><th>Question</th><th>Most likely</th><th class="num">Our number</th><th class="num">Polymarket</th><th>Us vs market</th><th>View</th><th>Decided by</th></tr></thead><tbody>' +
        rows.map(function (r, i) {
          var cls = r.ours >= 0.55 ? "ok" : r.ours <= 0.45 ? "bad" : "warn";
          var gapCls = r.gap_points == null || Math.abs(r.gap_points) < 5 ? "" : "warn";
          var id = "fc-" + g.replace(/\W/g, "") + i;
          var detail = '<tr id="' + id + '" hidden><td colspan="7" class="small">' +
            "<p><strong>Counts as yes if:</strong> " + esc(r.rule) + "</p>" +
            "<p><strong>Why this number:</strong> " + esc(r.why) + (r.updates > 1 ? " (" + r.updates + " updates)" : "") + "</p>" +
            (r.players && r.players.length ? "<p><strong>Players:</strong> " + r.players.map(function (pl) { return "<em>" + esc(pl.actor.replace(/^ac-/, "")) + "</em>: " + esc(pl.does); }).join(" ") + "</p>" : "") +
            (r.withdrawn_reason ? '<p><span class="pill bad">withdrawn</span> ' + esc(r.withdrawn_reason) + "</p>" : "") +
            (r.outcome != null ? "<p><strong>Result:</strong> " + (r.outcome ? "Yes" : "No") + "</p>" : "") +
            (r.stock_moves.length ? "<p><strong>If it happens, stocks after past strikes:</strong> " + r.stock_moves.map(function (m) { return esc(m.text); }).join("; ") + '. <a href="#reactions">Details</a>. Not a trading signal.</p>' : "") +
            (r.market_url ? "<p>" + link(r.market_url, "Polymarket market") + "</p>" : "") + "</td></tr>";
          return '<tr class="fcrow" data-target="' + id + '" style="cursor:pointer"><td>' + esc(r.question) + "</td>" +
            '<td><span class="pill ' + cls + '">' + esc(r.verdict) + "</span></td>" +
            '<td class="num"><strong>' + pct(r.ours) + "</strong></td>" +
            '<td class="num">' + (r.market == null ? "n/a" : pct(r.market)) + "</td>" +
            '<td><span class="pill ' + gapCls + '">' + esc(r.gap) + "</span></td>" +
            "<td>" + viewPill(r.view) + "</td>" +
            "<td>" + day(r.deadline) + "</td></tr>" + detail;
        }).join("") + "</tbody></table></div>" + (collapsed ? "</details>" : "");
    });
    setTimeout(function () {
      document.querySelectorAll(".fcrow").forEach(function (tr) {
        tr.addEventListener("click", function () { var d = document.getElementById(tr.dataset.target); d.hidden = !d.hidden; });
      });
    });
    return h;
  }

  function pollsView() {
    return "<h2>Leader polls</h2>" + D.polls.map(function (p) {
      var keys = Array.from(new Set([].concat.apply([], p.rows.map(function (r) { return Object.keys(r.values); }))));
      var blocNames = p.blocs ? Object.keys(p.blocs) : [];
      var blocHtml = blocNames.length ? '<div class="grid" style="margin-bottom:12px">' + blocNames.map(function (n) {
        return '<div><div class="kicker">' + esc(n) + ' average</div><div class="big">' + esc(p.bloc_average[n]) + '</div><div class="small muted">' + esc(p.bloc_average_without_channel_14[n]) + " without Channel 14 &middot; 61 needed</div></div>";
      }).join("") + '<div><div class="kicker">Largest party</div><div class="big">' + esc(Object.keys(p.largest_party_count).sort(function (a, b) { return p.largest_party_count[b] - p.largest_party_count[a]; })[0]) + '</div><div class="small muted">' +
        Object.keys(p.largest_party_count).map(function (k) { return esc(k) + " in " + p.largest_party_count[k] + " of " + p.rows.length + " polls"; }).join(", ") + "</div></div></div>" +
        '<p class="small muted">Blocs as defined by ' + link(p.blocs_source, "the Polymarket bloc market") + ": " + blocNames.map(function (n) { return "<strong>" + esc(n) + "</strong> = " + p.blocs[n].map(esc).join(", "); }).join("; ") + ". Other parties are not counted.</p>" : "";
      return '<div class="card" style="margin-bottom:16px"><div class="kicker">' + esc(p.country) + " &middot; " + esc(p.measure.replace(/_/g, " ")) + "</div><p>" + esc(p.description) + "</p>" + blocHtml +
        (p.rows.length ? '<div class="tablewrap"><table><thead><tr><th>Fieldwork</th><th>Pollster</th><th>Outlet</th>' + keys.map(function (k) { return '<th class="num">' + esc(k) + "</th>"; }).join("") + "<th>Source</th></tr></thead><tbody>" +
          p.rows.map(function (r) {
            return "<tr><td>" + day(r.fieldwork_end) + "</td><td>" + esc(r.pollster) + "</td><td>" + esc(r.outlet || "") + "</td>" +
              keys.map(function (k) { return '<td class="num">' + (r.values[k] == null ? "n/a" : esc(r.values[k]) + (p.measure === "knesset_seats" ? "" : "%")) + "</td>"; }).join("") +
              "<td>" + link(r.source_url, r.verified ? "verified" : "reference, verify") + "</td></tr>";
          }).join("") + "</tbody></table></div>"
          : '<p class="muted">No rows yet. Update from: ' + (p.where_to_update || []).map(function (u) { return link(u, new URL(u).hostname); }).join(", ") + "</p>") + "</div>";
    }).join("");
  }

  function countriesView() {
    var h = '<div class="toolbar">' + D.countries.map(function (c, i) {
      return '<button class="pill" data-c="' + i + '" style="border:0;cursor:pointer;padding:6px 12px">' + esc(c.title) + "</button>";
    }).join("") + '</div><div id="cbody"></div>';
    setTimeout(function () {
      function show(i) {
        var c = D.countries[i];
        $("#cbody").innerHTML = '<div class="card prose"><div class="kicker">' + esc(c.status) + " &middot; refreshed " + day(c.refreshed) + " &middot; stale after " + day(c.stale_after) +
          (c.is_stale ? ' <span class="pill bad">stale</span>' : "") + "</div><h2>" + esc(c.title) + "</h2>" + md(c.body) +
          '<p class="small muted">Sources: ' + srcList(c.sources) + "</p></div>";
      }
      document.querySelectorAll("[data-c]").forEach(function (b) { b.addEventListener("click", function () { show(+b.dataset.c); }); });
      show(0);
    });
    return h;
  }

  function tlItem(e) {
    return '<li><div class="d">' + day(e.date) + (e.end_date ? " to " + day(e.end_date) : "") + " &middot; " + esc(e.category) + "</div><div>" + esc(e.title) + "</div>" +
      '<div class="small muted">' + srcList(e.sources) + (e.verified ? "" : ' <span class="pill warn">verify</span>') + (e.disputed ? '<br><span class="pill bad">disputed</span> ' + esc(e.disputed) : "") + "</div></li>";
  }

  function timelineView() {
    var O = D.outlook, h = "<h2>Timeline</h2><h3>Most likely outcomes</h3>" + headlineBox();
    if (O && O.coming_up.length) {
      h += '<h3>Coming up</h3><p class="muted small">Dated events ahead, with the most likely outcome. Percentages are our number; Polymarket is shown beside it.</p><div class="card"><ul class="timeline">' +
        O.coming_up.filter(function (i) { return i.p == null || i.p >= 0.1; }).map(function (i) {
          var cls = i.p == null ? "" : i.p >= 0.55 ? "ok" : i.p <= 0.45 ? "bad" : "warn";
          return '<li><div class="d">' + day(i.date) + " &middot; " + esc(i.kind) + "</div><div>" + esc(i.title) + "</div>" +
            (i.likely ? '<div class="small"><span class="pill ' + cls + '">' + esc(i.likely) + "</span>" + (i.detail ? ' <span class="muted">' + esc(i.detail) + "</span>" : "") + "</div>" : "") + "</li>";
        }).join("") + '</ul><p class="small muted">Long shots under 10% are hidden here; they are on the Forecasts tab.</p></div>';
      if (O.stock_moves.length) {
        h += '<div class="card" style="margin-top:16px"><h3>If a strike happens: how stocks moved after past ones</h3><ul>' +
          O.stock_moves.map(function (m) { return "<li>" + esc(m.text) + (m.holds ? ' <span class="pill ok">holds</span>' : "") + "</li>"; }).join("") +
          '</ul><p class="small muted">Average of past strikes since 10/2023. <a href="#reactions">See every asset</a>. Not a trading signal.</p></div>';
      }
    }
    h += '<h3 style="margin-top:20px">What happened</h3><p class="muted small">Wars, strikes, ceasefires and political events. Reference-sourced entries are marked to verify against a primary or newsroom source.</p><div class="card"><ul class="timeline">' +
      D.timeline.map(tlItem).join("") + "</ul></div>";
    return h;
  }

  function backersView() {
    return '<h2>Backers, money and doctrine</h2><p class="muted small">Documented relationships with amounts and sources. Association is not control: each row says what it does not show.</p><div class="tablewrap card"><table><thead><tr><th>From</th><th>To</th><th>Type</th><th>What</th><th class="num">Amount</th><th>Period</th><th>Label</th><th>Source</th></tr></thead><tbody>' +
      D.relationships.map(function (r) {
        return "<tr><td>" + esc(r.from) + "</td><td>" + esc(r.to) + "</td><td>" + esc(r.type.replace(/_/g, " ")) + "</td><td>" + esc(r.description) +
          (r.what_it_does_not_show ? '<div class="small muted">Does not show: ' + esc(r.what_it_does_not_show) + "</div>" : "") + '</td><td class="num">' + money(r.amount_usd) + "</td><td>" + esc(r.period) + "</td><td>" + label(r.label) + "</td><td>" + srcList(r.sources) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }

  function baseratesView() {
    return '<div class="section"><h2>' + WORDS.baserate + ' (base rates)</h2>' + D.baserates.map(function (b) {
      return '<div class="card" style="margin-bottom:16px"><h3>' + esc(b.description) + "</h3>" +
        (b.warning ? '<div class="banner">' + esc(b.warning) + "</div>" : "") +
        '<p class="small"><strong>Question shape:</strong> ' + esc(b.question_shape) + '<br><strong>Inclusion rule:</strong> ' + esc(b.inclusion_rule) + "</p>" +
        '<div class="grid"><div><div class="kicker">Response rate (smoothed)</div><div class="big">' + pct(b.response_rate) + '</div></div><div><div class="kicker">Median lag</div><div class="big">' + esc(b.lag_days.median) + ' days</div><div class="small muted">range ' + esc(b.lag_days.min) + " to " + esc(b.lag_days.max) + "</div></div>" +
        Object.keys(b.chance_within_days).map(function (k) { return '<div><div class="kicker">Within ' + esc(k) + ' days</div><div class="big">' + pct(b.chance_within_days[k]) + "</div></div>"; }).join("") + "</div>" +
        '<div class="tablewrap"><table><thead><tr><th>Trigger</th><th>Response</th><th class="num">Lag</th><th>Source</th></tr></thead><tbody>' + b.rows.map(function (r) {
          return "<tr><td>" + day(r.trigger_date) + " " + esc(r.trigger) + "</td><td>" + (r.responded ? day(r.response_date) + " " + esc(r.response) : esc(r.response || "No response")) + '</td><td class="num">' + (r.lag_days == null ? "n/a" : r.lag_days + "d") + "</td><td>" + srcList(r.sources) + (r.verified ? "" : ' <span class="pill warn">verify</span>') + "</td></tr>";
        }).join("") + "</tbody></table></div></div>";
    }).join("") + "</div>";
  }

  function scenariosView() {
    return '<div class="section"><h2>Scenarios</h2>' + D.scenarios.map(function (s) {
      return '<div class="card" style="margin-bottom:16px"><div class="kicker"><span class="pill warn">modeled, not fact</span> as of ' + day(s.as_of) + "</div><h3>" + esc(s.title) + '</h3><p class="small muted">' + esc(s.note) + "</p>" +
        '<div class="grid">' + s.pathways.map(function (p) {
          return '<div class="card"><h3>' + esc(p.name) + '</h3><p class="small">' + esc(p.how) + '</p><p class="small muted"><strong>Watch:</strong> ' + p.watch.map(esc).join("; ") + "<br><strong>Markets:</strong> " + esc(p.markets) + "</p></div>";
        }).join("") + "</div>" +
        '<h3 style="margin-top:14px">Market transmission</h3><div class="tablewrap"><table><thead><tr><th>Asset</th><th>Causal chain</th><th>Horizon</th><th>Counterargument</th></tr></thead><tbody>' +
        s.market_channels.map(function (c) { return "<tr><td>" + esc(c.asset) + "</td><td>" + esc(c.chain) + "</td><td>" + esc(c.horizon) + "</td><td>" + esc(c.counter) + "</td></tr>"; }).join("") + "</tbody></table></div></div>";
    }).join("") + "</div>";
  }

  function scoreBlock(card, title) {
    var h = '<div class="card" style="margin-bottom:16px"><h3>' + title + "</h3>";
    if (!card.enough_data) h += '<div class="banner">Not enough data: ' + card.resolved + " resolved of the " + card.min_resolved_for_claims + " needed before any claim of an edge.</div>";
    h += '<div class="grid"><div><div class="kicker">' + WORDS.brier + '</div><div class="big">' + num(card.mean_brier) + '</div><div class="small muted">0 is perfect, 0.25 is a coin flip</div></div>' +
      '<div><div class="kicker">Ours / crowd, same moment</div><div class="big">' + num(card.vs_market.ours) + " / " + num(card.vs_market.baseline) + '</div><div class="small muted">n=' + card.vs_market.n + ". The fair comparison.</div></div>" +
      '<div><div class="kicker">Ours / crowd when we started</div><div class="big">' + num(card.vs_market_at_entry.ours) + " / " + num(card.vs_market_at_entry.baseline) + '</div><div class="small muted">n=' + card.vs_market_at_entry.n + "</div></div>" +
      '<div><div class="kicker">Ours / ' + WORDS.baserate.toLowerCase() + '</div><div class="big">' + num(card.vs_base_rate.ours) + " / " + num(card.vs_base_rate.baseline) + '</div><div class="small muted">n=' + card.vs_base_rate.n + "</div></div></div>";
    var views = Object.keys(card.by_view || {});
    if (views.length) {
      h += '<h3 style="margin-top:12px">By view</h3><div class="tablewrap"><table><thead><tr><th>View</th><th class="num">Resolved</th><th class="num">Ours</th><th class="num">Crowd</th></tr></thead><tbody>' + views.map(function (v) {
        var x = card.by_view[v];
        return "<tr><td>" + viewPill(v) + '</td><td class="num">' + x.n + '</td><td class="num">' + num(x.ours) + '</td><td class="num">' + num(x.market) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
    }
    h += '<h3 style="margin-top:12px">' + WORDS.calibration + '</h3><div class="tablewrap"><table><thead><tr><th>We said</th><th class="num">Count</th><th class="num">Average</th><th class="num">Happened</th></tr></thead><tbody>' + card.calibration.filter(function (b) { return b.count; }).map(function (b) {
      return "<tr><td>" + esc(b.band) + '</td><td class="num">' + b.count + '</td><td class="num">' + pct(b.mean_forecast) + '</td><td class="num">' + pct(b.observed_rate) + "</td></tr>";
    }).join("") + "</tbody></table></div></div>";
    return h;
  }

  function scorecardView() {
    return '<div class="section"><h2>Scorecard</h2><p class="small muted">We pressure-test judgment against the crowd, not sell a crystal ball. Most numbers here are the market price with one known bias removed, because beating a liquid market is hard. Independent views are logged with the players they rest on and scored the same way. The record is public either way.</p>' +
      scoreBlock(D.scorecard.live, "Live forecasts") + scoreBlock(D.scorecard.demo, "Illustrative examples (not a track record)") + "</div>";
  }

  function playersView() {
    var P = D.players || [];
    if (!P.length) return "";
    function list(title, items) { return items && items.length ? "<p><strong>" + title + ":</strong></p><ul class=\"small\">" + items.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>" : ""; }
    return '<div class="section"><h2>Player cards</h2><p class="small muted">One checklist per decision-maker: what they want, what stops them, who can remove them, and the public signs that they are moving. Every line cites a record or is marked (stated), (reported) or (inferred). An independent forecast must name the cards it rests on.</p><div class="grid two">' +
      P.map(function (a) {
        return '<div class="card"><div class="kicker">' + esc(a.country.replace(/-/g, " ")) + " &middot; as of " + day(a.as_of) + "</div><h3>" + esc(a.name) + '</h3><p class="small muted">' + esc(a.role) + "</p>" +
          list("Wants", a.wants) + list("Fears", a.fears) + list("What stops them", a.constraints) + list("Red lines", a.red_lines) + list("Who can remove them", a.who_can_remove_them) + list("Signs they are moving", a.tells) +
          (a.record.length ? "<p><strong>Record:</strong></p><ul class=\"small\">" + a.record.map(function (r) { return "<li>" + day(r.date) + " " + esc(r.what) + "</li>"; }).join("") + "</ul>" : "") +
          list("Open questions", a.open_questions) + "</div>";
      }).join("") + "</div></div>";
  }

  function biasMapBlock() {
    var C = D.calibration;
    if (!C) return "";
    var chk = C.check.horizons;
    return '<div class="card" style="margin-bottom:16px"><h3>The crowd’s known bias, by horizon</h3><p class="small muted">Fitted on ' + C.markets + ' resolved markets: how often each price actually came true, as a staircase, shrunk toward the price where the sample is thin. Checked by fitting on markets closed before ' + day(C.check.cutoff) + ' and scoring the ' + C.check.test_markets + ' that closed after. Used on every crowd-view forecast by how far its deadline is; switched off inside two days and beyond ' + C.max_days + ' days.</p>' +
      '<div class="tablewrap"><table><thead><tr><th>Price taken</th><th class="num">Test markets</th><th class="num">Crowd error</th><th class="num">With bias removed</th><th>Out of sample</th></tr></thead><tbody>' +
      ["30", "7", "1"].map(function (h) { var c = chk[h]; return c ? "<tr><td>" + h + ' days before close</td><td class="num">' + c.n + '</td><td class="num">' + num(c.raw_brier, 4) + '</td><td class="num">' + num(c.adjusted_brier, 4) + "</td><td>" + (c.helps ? '<span class="pill ok">helps</span>' : '<span class="pill">no help, not used</span>') + "</td></tr>" : ""; }).join("") + "</tbody></table></div>" +
      '<div class="grid two" style="margin-top:12px">' + ["30", "7"].map(function (h) {
        return '<div><div class="kicker">' + h + '-day map: price to our number</div><table><tbody>' + C.samples[h].map(function (r) { return '<tr><td class="num">' + pct(r.price) + '</td><td class="num">' + pct(r.adjusted) + "</td></tr>"; }).join("") + "</tbody></table></div>";
      }).join("") + "</div></div>";
  }

  function sourcesView() {
    var h = '<h2>Sources and evidence</h2><div class="toolbar"><input id="eq" placeholder="Search evidence" aria-label="Search evidence"></div><div class="card tablewrap"><table><thead><tr><th>Claim</th><th>Label</th><th>Countries</th><th>Sources</th></tr></thead><tbody id="evrows"></tbody></table></div>';
    h += '<h3 style="margin-top:24px">Feeds</h3><div class="card tablewrap"><table><thead><tr><th>Feed</th><th>Kind</th><th>Language</th><th>Tier</th></tr></thead><tbody>' +
      D.sources.sources.map(function (s) { return "<tr><td>" + link(s.url, s.name) + "</td><td>" + esc(s.kind) + "</td><td>" + esc(s.lang) + "</td><td>" + esc(s.tier.replace(/_/g, " ")) + "</td></tr>"; }).join("") +
      D.sources.blocked.map(function (s) { return '<tr><td class="muted">' + esc(s.name) + '</td><td colspan="3"><span class="pill bad">blocked</span> ' + esc(s.reason) + "</td></tr>"; }).join("") + "</tbody></table></div>";
    setTimeout(function () {
      function draw() {
        var q = $("#eq").value.toLowerCase();
        $("#evrows").innerHTML = D.evidence.filter(function (e) { return !q || e.claim.toLowerCase().indexOf(q) >= 0; }).map(function (e) {
          return "<tr><td>" + esc(e.claim) + (e.evidence_against ? '<div class="small muted">Against: ' + esc(e.evidence_against) + "</div>" : "") + '<div class="small muted">' + esc(e.id) + "</div></td><td>" + label(e.label) + "</td><td>" + esc(e.countries.join(", ")) + "</td><td>" + srcList(e.sources) + "</td></tr>";
        }).join("");
      }
      $("#eq").addEventListener("input", draw);
      draw();
    });
    return h;
  }


  function timingView() {
    var h = '<h2>' + WORDS.survival + ': ceasefire and war-ending curves</h2><p class="muted small">Built from dated Polymarket ladders. "Market" reads the prices as they are. "Calibrated" adjusts each price by how often similar prices on resolved ceasefire and strike markets actually came true (see Accuracy), shrunk toward the market where the past sample is thin. Both are probabilities, not facts.</p>';
    if (!D.timing || !D.timing.length) return h + '<div class="banner">No ladder prices yet. Run <code>python -m worldsim collect</code>.</div>';
    return h + D.timing.map(function (c) {
      var cal = c.calibrated;
      var head = c.kind === "survival" ? "Chance it breaks in each window" : "Chance it happens in each window";
      var rows = c.rows.map(function (r) {
        return "<tr><td>" + day(r.from) + " to " + day(r.to) + '</td><td class="num">' + pct(r.in_window) + '</td><td class="num">' + pct(r.by_date) + "</td>" +
          (cal ? '<td class="num">' + pct(r.calibrated_in_window) + '</td><td class="num">' + pct(r.calibrated_by_date) + "</td>" : "") +
          '<td><div class="bar"><span style="width:' + Math.round(r.by_date * 100) + '%"></span></div></td></tr>';
      }).join("");
      var lastTo = c.rows.length ? day(c.rows[c.rows.length - 1].to) : "";
      return '<div class="card" style="margin-bottom:16px"><div class="kicker">' + esc(c.kind === "survival" ? "holds until broken by " + c.event : "waiting for " + c.event) + '</div><h3>' + esc(c.title) + "</h3>" +
        '<div class="grid"><div><div class="kicker">Median date (market)</div><div class="big">' + (c.median_date ? day(c.median_date) : "after " + lastTo) + "</div></div>" +
        (cal ? '<div><div class="kicker">Median date (calibrated)</div><div class="big">' + (cal.median_date ? day(cal.median_date) : "after " + lastTo) + "</div></div>" : "") +
        '<div><div class="kicker">' + (c.kind === "survival" ? "Still holding after " : "Not yet by ") + lastTo + '</div><div class="big">' + pct(c.after_last) + (cal ? ' <span class="small muted">calibrated ' + pct(cal.after_last) + "</span>" : "") + "</div></div></div>" +
        (c.adjusted ? '<p class="small muted">Some prices disagreed with each other and were smoothed so the curve only moves one way.</p>' : "") +
        '<div class="tablewrap"><table><thead><tr><th>Window</th><th class="num">' + head + '</th><th class="num">By end of window</th>' + (cal ? '<th class="num">Calibrated, window</th><th class="num">Calibrated, by end</th>' : "") + "<th></th></tr></thead><tbody>" + rows + "</tbody></table></div></div>";
    }).join("");
  }

  function accuracyView() {
    var A = D.accuracy;
    var h = '<h2>Accuracy: how good is the crowd?</h2>';
    if (!A) return h + '<div class="banner">No backtest yet. Run <code>python -m worldsim backtest</code>.</div>';
    h += '<p class="muted small">' + esc(A.note) + " Run " + when(A.run_at) + ". " + WORDS.brier + ": 0 is perfect, 0.25 is a coin flip.</p>";
    h += biasMapBlock();
    h += A.summary.map(function (s) {
      var hz = Object.keys(s.horizons).sort(function (a, b) { return b - a; });
      var cal = s.horizons["7"] && s.horizons["7"].calibration ? s.horizons["7"].calibration.filter(function (b) { return b.count; }) : [];
      return '<div class="card" style="margin-bottom:16px"><h3>' + esc(s.label) + '</h3><p class="small muted">' + s.markets + " resolved markets across " + s.events + " events. " + pct(s.yes_share) + " resolved yes.</p>" +
        '<div class="tablewrap"><table><thead><tr><th>Price taken</th><th class="num">Markets</th><th class="num">Crowd error</th><th class="num">Base-rate error</th><th class="num">Coin flip</th><th class="num">Right side of 50%</th></tr></thead><tbody>' +
        hz.map(function (k) { var v = s.horizons[k]; return v.n ? "<tr><td>" + k + ' days before close</td><td class="num">' + v.n + '</td><td class="num">' + num(v.market_brier) + '</td><td class="num">' + num(v.base_rate_brier) + '</td><td class="num">0.250</td><td class="num">' + pct(v.hit_rate) + "</td></tr>" : ""; }).join("") +
        "</tbody></table></div>" +
        '<h3 style="margin-top:12px">' + WORDS.calibration + ' (7 days out)</h3><div class="tablewrap"><table><thead><tr><th>Price band</th><th class="num">Markets</th><th class="num">Average price</th><th class="num">Actually happened</th></tr></thead><tbody>' +
        cal.map(function (b) { return "<tr><td>" + esc(b.band) + '</td><td class="num">' + b.count + '</td><td class="num">' + pct(b.mean_price) + '</td><td class="num">' + pct(b.happened) + "</td></tr>"; }).join("") + "</tbody></table></div></div>";
    }).join("");
    h += '<div class="card"><h3>Recently resolved</h3><div class="tablewrap"><table><thead><tr><th>Closed</th><th>Market</th><th class="num">7 days out</th><th>Outcome</th></tr></thead><tbody>' +
      A.recent.slice(0, 40).map(function (r) { return "<tr><td>" + day(r.closed) + "</td><td>" + link("https://polymarket.com/market/" + r.slug, r.question) + '</td><td class="num">' + pct(r.p7) + "</td><td>" + (r.outcome ? "Yes" : "No") + "</td></tr>"; }).join("") + "</tbody></table></div></div>";
    return h;
  }


  function reactionsView() {
    var R = D.reactions;
    var h = '<div class="section"><h2>' + WORDS.eventstudy + ': past strikes</h2>';
    if (!R) return h + '<div class="banner">No event study yet. Run <code>python -m worldsim prices</code>.</div>';
    h += '<p class="muted small">' + esc(R.note) + " Run " + when(R.run_at) + ".</p>";
    h += '<div class="banner">How to read it: each cell is the average move after ' + R.events.length + ' strike and war events. <span class="pill warn">unusual</span> means bigger than the asset’s normal swing. <span class="pill ok">holds</span> means it survives dropping the single biggest event. Unusual but not holding means one event (usually the 2026 war) carries it.</div>';
    function cell(s) {
      if (!s || s.mean == null) return '<td class="num">n/a</td>';
      var tag = s.holds_without_largest ? ' <span class="pill ok">holds</span>' : (s.unusual ? ' <span class="pill warn">unusual</span>' : "");
      return '<td class="num">' + (s.mean > 0 ? "+" : "") + s.mean.toFixed(1) + '%' + tag + '<div class="small muted">without largest ' + (s.mean_without_largest > 0 ? "+" : "") + (s.mean_without_largest == null ? "n/a" : s.mean_without_largest.toFixed(1) + "%") + " &middot; normal swing " + s.typical_swing + "%</div></td>";
    }
    h += '<div class="card tablewrap"><table><thead><tr><th>Asset</th><th>Measured</th>' + R.windows.map(function (k) { return '<th class="num">' + k + (k === 1 ? " trading day" : " trading days") + "</th>"; }).join("") + "</tr></thead><tbody>" +
      R.assets.map(function (a) {
        return "<tr><td><strong>" + esc(a.name) + '</strong><div class="small muted">' + esc(a.ticker) + " &middot; " + esc(a.why) + "</div></td><td>" + esc(a.summary["1"].measure) + "</td>" +
          R.windows.map(function (k) { return cell(a.summary[String(k)]); }).join("") + "</tr>";
      }).join("") + "</tbody></table></div>";
    h += '<h3 style="margin-top:20px">Event by event</h3><div class="toolbar"><select id="rasset" aria-label="Asset">' + R.assets.map(function (a, i) { return '<option value="' + i + '">' + esc(a.name) + "</option>"; }).join("") + '</select></div><div class="card tablewrap" id="rbody"></div>';
    setTimeout(function () {
      function draw() {
        var a = R.assets[+$("#rasset").value], useX = a.benchmark === "SPY";
        $("#rbody").innerHTML = "<table><thead><tr><th>Date</th><th>Event</th>" + R.windows.map(function (k) { return '<th class="num">Day ' + k + (useX ? " vs SPY" : "") + "</th>"; }).join("") + "</tr></thead><tbody>" +
          a.events.map(function (e) {
            return "<tr><td>" + day(e.date) + "</td><td>" + esc(e.title) + "</td>" + R.windows.map(function (k) {
              var v = useX ? e["x" + k] : e["d" + k];
              return '<td class="num">' + (v == null ? "n/a" : (v > 0 ? "+" : "") + v.toFixed(1) + "%") + "</td>";
            }).join("") + "</tr>";
          }).join("") + "</tbody></table>";
      }
      $("#rasset").addEventListener("input", draw);
      draw();
    });
    return h + "</div>";
  }


  function marketsNowPanel() {
    var M = D.markets_now, O = D.outlook;
    if (!M) return '<div class="card"><h3>Markets now</h3><p class="muted small">No quotes yet. Run <code>python -m worldsim live</code>.</p></div>';
    var cls = M.level === "calm" ? "ok" : M.level === "some stress" ? "warn" : "bad";
    var groups = {};
    M.quotes.forEach(function (q) { (groups[q.group] = groups[q.group] || []).push(q); });
    var h = '<div class="card"><div class="kicker">Markets now &middot; ' + esc((D.live_source || "")) + '</div><h3>Middle East market stress: <span class="pill ' + cls + '">' + esc(M.level) + "</span></h3>" +
      (M.flags.length ? '<p class="small">' + esc(M.flags.join("; ").replace(/^./, function (c) { return c.toUpperCase(); })) + ".</p>" : '<p class="small muted">Nothing unusual in oil, defense, shipping or the shekel.</p>') +
      (M.reads.length ? "<ul class=\"small\">" + M.reads.map(function (r) { return "<li><strong>" + esc(r.what) + ":</strong> " + esc(r.value) + ", " + esc(r.detail) + "</li>"; }).join("") + "</ul>" : "") +
      (O && O.war_risk_priced && O.war_risk_priced.length ? '<p class="small"><strong>What Polymarket prices:</strong> ' + O.war_risk_priced.map(esc).join("; ") + ".</p>" : "") +
      '<div class="tablewrap"><table><thead><tr><th>Asset</th><th class="num">Price</th><th class="num">Latest session</th><th>Size of move</th></tr></thead><tbody>' +
      Object.keys(groups).map(function (g) {
        return '<tr><td colspan="4" class="kicker" style="padding-top:12px">' + esc(g) + "</td></tr>" + groups[g].map(function (q) {
          var c = q.change_pct == null ? "n/a" : (q.change_pct > 0 ? "+" : "") + q.change_pct.toFixed(2) + "%";
          var s = q.size === "very big move" ? "bad" : q.size === "big move" ? "warn" : "";
          return "<tr><td>" + esc(q.name) + '</td><td class="num">' + Number(q.price).toLocaleString(undefined, { maximumFractionDigits: 2 }) + '</td><td class="num">' + c + "</td><td>" + (q.size ? '<span class="pill ' + s + '">' + esc(q.size) + "</span>" : "") + (q.delay_minutes ? ' <span class="small muted">' + q.delay_minutes + " min delay</span>" : "") + "</td></tr>";
        }).join("");
      }).join("") + "</tbody></table></div>" +
      '<p class="small muted">Size of move compares the latest session with the asset’s normal daily swing over the past year. A description of the market, not a trading signal. <a href="#markets">How these assets moved after past strikes</a>.</p></div>';
    return h;
  }

  function forecastsTab() { return forecastsView() + '<div class="section">' + marketsView() + "</div>" + '<div class="section">' + timingView() + "</div>" + scorecardView(); }
  function marketsTab() { return "<h2>Markets</h2>" + marketsNowPanel() + reactionsView() + '<div class="section">' + watch() + "</div>"; }
  function newsTab() { return feed() + '<div class="section">' + timelineView() + "</div>" + '<div class="section"><h2>Country profiles</h2>' + countriesView() + "</div>" + '<div class="section">' + pollsView() + "</div>"; }
  function researchTab() { return playersView() + baseratesView() + scenariosView() + '<div class="section">' + backersView() + "</div>"; }
  function accuracyTab() { return accuracyView() + '<div class="section">' + sourcesView() + "</div>"; }

  var VIEWS = [
    ["overview", "Overview", overview], ["forecasts", "Forecasts", forecastsTab], ["markets", "Markets", marketsTab],
    ["news", "News & context", newsTab], ["research", "Players & research", researchTab], ["accuracy", "Accuracy & sources", accuracyTab]
  ];
  // Old links and bookmarks still land somewhere sensible.
  var ALIASES = { watch: "markets", feed: "news", timing: "forecasts", reactions: "markets", polls: "news", countries: "news", timeline: "news",
    backers: "research", baserates: "research", scenarios: "research", scorecard: "forecasts", sources: "accuracy", players: "research" };

  function render(key) {
    key = ALIASES[key] || key;
    var v = VIEWS.filter(function (x) { return x[0] === key; })[0] || VIEWS[0];
    document.querySelectorAll("#tabs button").forEach(function (b) { b.setAttribute("aria-selected", b.dataset.k === v[0]); });
    $("#view").innerHTML = v[2]();
    try { localStorage.setItem("ws-tab", v[0]); } catch (e) { /* storage unavailable */ }
  }

  function start(data) {
    D = data;
    $("#meta").innerHTML = D.forecasts.live.length + " forecasts, " + D.scorecard.live.resolved + " resolved<br>" + D.counts.evidence + " evidence records &middot; " + D.timeline.length + " timeline events";
    $("#tabs").innerHTML = VIEWS.map(function (v) { return '<button role="tab" data-k="' + v[0] + '">' + v[1] + "</button>"; }).join("");
    $("#tabs").addEventListener("click", function (e) { if (e.target.dataset.k) { location.hash = e.target.dataset.k; } });
    window.addEventListener("hashchange", function () { render(location.hash.slice(1)); });
    var saved = null;
    try { saved = localStorage.getItem("ws-tab"); } catch (e) { /* storage unavailable */ }
    render(location.hash.slice(1) || saved || "overview");
  }

  fetch("data.json", { cache: "no-store" }).then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }).then(start).catch(function () {
    $("#view").innerHTML = '<div class="banner">No data.json found. Run <code>python -m worldsim collect</code> (or <code>build</code>) from the repo folder, then serve it with <code>python -m http.server -d dashboard</code>.</div>';
  });
})();

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
  function overview() {
    var w = D.watch, live = D.forecasts.live;
    var h = '<div class="grid">';
    h += '<div class="card"><div class="kicker">Watch level</div><div class="level ' + esc(w.level) + '">' + esc(w.level) + "</div>" +
      '<div class="small muted">' + w.active_count + " of " + Object.keys(w.indicators).length + " indicators active. Heuristic, not calibrated.</div></div>";
    h += '<div class="card"><div class="kicker">Live forecasts</div><div class="big">' + live.length + "</div>" +
      '<div class="small muted">' + D.scorecard.live.resolved + " resolved. Edge claims need " + D.scorecard.live.min_resolved_for_claims + ".</div></div>";
    h += '<div class="card"><div class="kicker">Feed, last 10 days</div><div class="big">' + D.counts.observations_10d + "</div>" +
      '<div class="small muted">Hebrew and English headlines, Telegram, aircraft, fleet, advisories.</div></div>';
    var stale = D.countries.filter(function (c) { return c.is_stale; });
    h += '<div class="card"><div class="kicker">Profiles</div><div class="big">' + D.countries.length + "</div>" +
      '<div class="small muted">' + (stale.length ? stale.length + " past refresh date" : "All within refresh window") + "</div></div></div>";

    h += '<div class="grid two" style="margin-top:16px">';
    h += '<div class="card"><h3>Active indicators</h3>' + indicatorList(true) + "</div>";
    var movers = D.markets.filter(function (m) { return m.probability != null; }).slice(0, 6);
    h += '<div class="card"><h3>Market baseline</h3><table><tbody>' + movers.map(function (m) {
      return "<tr><td>" + esc(m.label) + '</td><td class="num">' + pct(m.probability) + "</td></tr>";
    }).join("") + "</tbody></table>" + (movers.length ? "" : '<p class="muted">Run collect to pull prices.</p>') + "</div>";
    h += '<div class="card"><h3>Latest Hebrew headlines</h3><ul class="feed">' + D.feed.filter(function (o) { return o.lang === "he"; }).slice(0, 6).map(feedItem).join("") + "</ul></div>";
    h += '<div class="card"><h3>Recent timeline</h3><ul class="timeline">' + D.timeline.slice(0, 5).map(tlItem).join("") + "</ul></div>";
    return h + "</div>";
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
    var h = '<h2>Leading indicators</h2><p class="muted small">Big operations usually leave public tracks a day or two ahead. One signal means little. Several kinds at once moves the odds. The level is a heuristic until enough past events are logged against it.</p>';
    h += '<div class="card" style="margin-bottom:16px">' + indicatorList(false) + "</div>";
    h += '<div class="card"><h3>Raw signals: aircraft, GPS, satellite fires, fleet, advisories</h3><ul class="feed">' + D.signals.slice(0, 40).map(feedItem).join("") + "</ul></div>";
    return h;
  }

  function feedItem(o) {
    var tr = o.lang === "he" ? ' &middot; <a target="_blank" rel="noopener" href="https://translate.google.com/translate?sl=iw&tl=en&u=' + encodeURIComponent(o.url) + '">translate</a>' : "";
    return '<li><div class="t" dir="auto" lang="' + esc(o.lang) + '">' + link(o.url, o.title) + "</div>" +
      '<div class="m">' + esc(o.source_id) + " &middot; " + when(o.published_at || o.observed_at) + tr +
      (o.indicators.length ? " &middot; " + o.indicators.map(function (i) { return '<span class="pill warn">' + esc(IND_NAMES[i] || i) + "</span>"; }).join("") : "") +
      (o.tags.length ? " " + o.tags.map(function (t) { return '<span class="pill">' + esc(t) + "</span>"; }).join("") : "") + "</div></li>";
  }

  function feed() {
    var sources = Array.from(new Set(D.feed.map(function (o) { return o.source_id; }))).sort();
    var h = '<h2>Hebrew and English news</h2><p class="muted small">Headlines and short excerpts with links. Hebrew outlets and reporters’ Telegram channels often run hours ahead of English wires. Telegram is an unverified signal.</p>';
    h += '<div class="toolbar"><input id="q" placeholder="Search (Hebrew or English)" aria-label="Search feed"><select id="src" aria-label="Source"><option value="">All sources</option>' +
      sources.map(function (s) { return "<option>" + esc(s) + "</option>"; }).join("") + '</select><select id="lang" aria-label="Language"><option value="">All languages</option><option value="he">Hebrew</option><option value="en">English</option></select>' +
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
    var h = '<h2>Market baseline</h2><p class="muted small">Polymarket prices logged on every collect run. This is the number to beat. A price is the crowd’s probability, not a fact.</p><div class="grid">';
    h += D.markets.map(function (m) {
      return '<div class="card"><div class="kicker">' + esc(m.topic) + " &middot; " + esc(m.countries.join(", ")) + "</div><h3>" + link(m.url, m.label) + "</h3>" +
        '<div class="big">' + pct(m.probability) + "</div>" +
        '<div class="small muted">' + (m.change != null ? (m.change >= 0 ? "+" : "") + Math.round(m.change * 1000) / 10 + " pts since first logged &middot; " : "") +
        (m.end_date ? "ends " + day(m.end_date) : "") + (m.as_of ? " &middot; as of " + when(m.as_of) : " &middot; not yet collected") + "</div>" + spark(m.series) + "</div>";
    }).join("");
    return h + "</div>";
  }

  function headlineBox() {
    var O = D.outlook;
    if (!O || !O.headlines || !O.headlines.length) return "";
    return '<div class="grid" style="margin-bottom:16px">' + O.headlines.map(function (x) {
      return '<div class="card"><div class="kicker">' + esc(x.title) + '</div><div style="font:600 20px var(--serif)">' + esc(x.answer) + '</div><div class="small muted">' + esc(x.detail) + "</div></div>";
    }).join("") + "</div>";
  }

  function forecastsView() {
    var O = D.outlook;
    var h = '<h2>Forecasts</h2>' +
      '<div class="banner"><strong>Our number</strong> is this tool’s forecast, the one that gets scored. <strong>Polymarket</strong> is what bettors are paying right now. When the two are within ' + 5 + ' points we call it the same. Tap a row for the rules and the reasoning.</div>' + '<h3>Most likely outcomes</h3>' + headlineBox();
    if (!O || !O.forecasts.length) return h + '<p class="muted">No forecasts yet. Start one with <code>python -m worldsim new-forecast --market &lt;slug&gt;</code>.</p>';
    var groups = ["Past due", "This week", "This month", "Later", "Decided", "Withdrawn"];
    groups.forEach(function (g) {
      var rows = O.forecasts.filter(function (r) { return r.group === g; });
      if (!rows.length) return;
      var collapsed = g === "Withdrawn" || g === "Decided";
      h += (collapsed ? "<details><summary><h3 style=\"display:inline\">" + g + " (" + rows.length + ")</h3></summary>" : "<h3 style=\"margin-top:20px\">" + g + "</h3>") +
        '<div class="card tablewrap"><table class="fc"><thead><tr><th>Question</th><th>Most likely</th><th class="num">Our number</th><th class="num">Polymarket</th><th>Us vs market</th><th>Decided by</th></tr></thead><tbody>' +
        rows.map(function (r, i) {
          var cls = r.ours >= 0.55 ? "ok" : r.ours <= 0.45 ? "bad" : "warn";
          var gapCls = r.gap_points == null || Math.abs(r.gap_points) < 5 ? "" : "warn";
          var id = "fc-" + g.replace(/\W/g, "") + i;
          var detail = '<tr id="' + id + '" hidden><td colspan="6" class="small">' +
            "<p><strong>Counts as yes if:</strong> " + esc(r.rule) + "</p>" +
            "<p><strong>Why this number:</strong> " + esc(r.why) + (r.updates > 1 ? " (" + r.updates + " updates)" : "") + "</p>" +
            (r.withdrawn_reason ? '<p><span class="pill bad">withdrawn</span> ' + esc(r.withdrawn_reason) + "</p>" : "") +
            (r.outcome != null ? "<p><strong>Result:</strong> " + (r.outcome ? "Yes" : "No") + "</p>" : "") +
            (r.stock_moves.length ? "<p><strong>If it happens, stocks after past strikes:</strong> " + r.stock_moves.map(function (m) { return esc(m.text); }).join("; ") + '. <a href="#reactions">Details</a>. Not a trading signal.</p>' : "") +
            (r.market_url ? "<p>" + link(r.market_url, "Polymarket market") + "</p>" : "") + "</td></tr>";
          return '<tr class="fcrow" data-target="' + id + '" style="cursor:pointer"><td>' + esc(r.question) + "</td>" +
            '<td><span class="pill ' + cls + '">' + esc(r.verdict) + "</span></td>" +
            '<td class="num"><strong>' + pct(r.ours) + "</strong></td>" +
            '<td class="num">' + (r.market == null ? "n/a" : pct(r.market)) + "</td>" +
            '<td><span class="pill ' + gapCls + '">' + esc(r.gap) + "</span></td>" +
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
    return "<h2>Base rates</h2>" + D.baserates.map(function (b) {
      return '<div class="card" style="margin-bottom:16px"><h3>' + esc(b.description) + "</h3>" +
        (b.warning ? '<div class="banner">' + esc(b.warning) + "</div>" : "") +
        '<p class="small"><strong>Question shape:</strong> ' + esc(b.question_shape) + '<br><strong>Inclusion rule:</strong> ' + esc(b.inclusion_rule) + "</p>" +
        '<div class="grid"><div><div class="kicker">Response rate (smoothed)</div><div class="big">' + pct(b.response_rate) + '</div></div><div><div class="kicker">Median lag</div><div class="big">' + esc(b.lag_days.median) + ' days</div><div class="small muted">range ' + esc(b.lag_days.min) + " to " + esc(b.lag_days.max) + "</div></div>" +
        Object.keys(b.chance_within_days).map(function (k) { return '<div><div class="kicker">Within ' + esc(k) + ' days</div><div class="big">' + pct(b.chance_within_days[k]) + "</div></div>"; }).join("") + "</div>" +
        '<div class="tablewrap"><table><thead><tr><th>Trigger</th><th>Response</th><th class="num">Lag</th><th>Source</th></tr></thead><tbody>' + b.rows.map(function (r) {
          return "<tr><td>" + day(r.trigger_date) + " " + esc(r.trigger) + "</td><td>" + (r.responded ? day(r.response_date) + " " + esc(r.response) : esc(r.response || "No response")) + '</td><td class="num">' + (r.lag_days == null ? "n/a" : r.lag_days + "d") + "</td><td>" + srcList(r.sources) + (r.verified ? "" : ' <span class="pill warn">verify</span>') + "</td></tr>";
        }).join("") + "</tbody></table></div></div>";
    }).join("");
  }

  function scenariosView() {
    return "<h2>Scenarios</h2>" + D.scenarios.map(function (s) {
      return '<div class="card" style="margin-bottom:16px"><div class="kicker"><span class="pill warn">modeled, not fact</span> as of ' + day(s.as_of) + "</div><h3>" + esc(s.title) + '</h3><p class="small muted">' + esc(s.note) + "</p>" +
        '<div class="grid">' + s.pathways.map(function (p) {
          return '<div class="card"><h3>' + esc(p.name) + '</h3><p class="small">' + esc(p.how) + '</p><p class="small muted"><strong>Watch:</strong> ' + p.watch.map(esc).join("; ") + "<br><strong>Markets:</strong> " + esc(p.markets) + "</p></div>";
        }).join("") + "</div>" +
        '<h3 style="margin-top:14px">Market transmission</h3><div class="tablewrap"><table><thead><tr><th>Asset</th><th>Causal chain</th><th>Horizon</th><th>Counterargument</th></tr></thead><tbody>' +
        s.market_channels.map(function (c) { return "<tr><td>" + esc(c.asset) + "</td><td>" + esc(c.chain) + "</td><td>" + esc(c.horizon) + "</td><td>" + esc(c.counter) + "</td></tr>"; }).join("") + "</tbody></table></div></div>";
    }).join("");
  }

  function scoreBlock(card, title) {
    var h = '<div class="card" style="margin-bottom:16px"><h3>' + title + "</h3>";
    if (!card.enough_data) h += '<div class="banner">Not enough data: ' + card.resolved + " resolved of the " + card.min_resolved_for_claims + " needed before any claim of an edge.</div>";
    h += '<div class="grid"><div><div class="kicker">Mean Brier (lower is better)</div><div class="big">' + num(card.mean_brier) + "</div></div>" +
      '<div><div class="kicker">vs base rate</div><div class="big">' + num(card.vs_base_rate.ours) + " / " + num(card.vs_base_rate.baseline) + '</div><div class="small muted">ours / baseline, n=' + card.vs_base_rate.n + "</div></div>" +
      '<div><div class="kicker">vs market</div><div class="big">' + num(card.vs_market.ours) + " / " + num(card.vs_market.baseline) + '</div><div class="small muted">ours / market, n=' + card.vs_market.n + "</div></div></div>";
    h += '<div class="tablewrap"><table><thead><tr><th>Band</th><th class="num">Count</th><th class="num">Mean forecast</th><th class="num">Happened</th></tr></thead><tbody>' + card.calibration.filter(function (b) { return b.count; }).map(function (b) {
      return "<tr><td>" + esc(b.band) + '</td><td class="num">' + b.count + '</td><td class="num">' + pct(b.mean_forecast) + '</td><td class="num">' + pct(b.observed_rate) + "</td></tr>";
    }).join("") + "</tbody></table></div></div>";
    return h;
  }

  function scorecardView() {
    return "<h2>Scorecard</h2>" + scoreBlock(D.scorecard.live, "Live forecasts") + scoreBlock(D.scorecard.demo, "Illustrative examples (not a track record)");
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
    var h = '<h2>When: ceasefire and war-ending curves</h2><p class="muted small">Built from dated Polymarket ladders. "Market" reads the prices as they are. "Calibrated" adjusts each price by how often similar prices on resolved ceasefire and strike markets actually came true (see Accuracy), shrunk toward the market where the past sample is thin. Both are probabilities, not facts.</p>';
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
    var h = '<h2>Accuracy: how good is the market baseline?</h2>';
    if (!A) return h + '<div class="banner">No backtest yet. Run <code>python -m worldsim backtest</code>.</div>';
    h += '<p class="muted small">' + esc(A.note) + " Run " + when(A.run_at) + ". Lower Brier is better: 0 is perfect, 0.25 is a coin flip.</p>";
    h += A.summary.map(function (s) {
      var hz = Object.keys(s.horizons).sort(function (a, b) { return b - a; });
      var cal = s.horizons["7"] && s.horizons["7"].calibration ? s.horizons["7"].calibration.filter(function (b) { return b.count; }) : [];
      return '<div class="card" style="margin-bottom:16px"><h3>' + esc(s.label) + '</h3><p class="small muted">' + s.markets + " resolved markets across " + s.events + " events. " + pct(s.yes_share) + " resolved yes.</p>" +
        '<div class="tablewrap"><table><thead><tr><th>Price taken</th><th class="num">Markets</th><th class="num">Market Brier</th><th class="num">Base-rate Brier</th><th class="num">Coin flip</th><th class="num">Right side of 50%</th></tr></thead><tbody>' +
        hz.map(function (k) { var v = s.horizons[k]; return v.n ? "<tr><td>" + k + ' days before close</td><td class="num">' + v.n + '</td><td class="num">' + num(v.market_brier) + '</td><td class="num">' + num(v.base_rate_brier) + '</td><td class="num">0.250</td><td class="num">' + pct(v.hit_rate) + "</td></tr>" : ""; }).join("") +
        "</tbody></table></div>" +
        '<h3 style="margin-top:12px">Calibration, 7 days out</h3><div class="tablewrap"><table><thead><tr><th>Price band</th><th class="num">Markets</th><th class="num">Average price</th><th class="num">Actually happened</th></tr></thead><tbody>' +
        cal.map(function (b) { return "<tr><td>" + esc(b.band) + '</td><td class="num">' + b.count + '</td><td class="num">' + pct(b.mean_price) + '</td><td class="num">' + pct(b.happened) + "</td></tr>"; }).join("") + "</tbody></table></div></div>";
    }).join("");
    h += '<div class="card"><h3>Recently resolved</h3><div class="tablewrap"><table><thead><tr><th>Closed</th><th>Market</th><th class="num">7 days out</th><th>Outcome</th></tr></thead><tbody>' +
      A.recent.slice(0, 40).map(function (r) { return "<tr><td>" + day(r.closed) + "</td><td>" + link("https://polymarket.com/market/" + r.slug, r.question) + '</td><td class="num">' + pct(r.p7) + "</td><td>" + (r.outcome ? "Yes" : "No") + "</td></tr>"; }).join("") + "</tbody></table></div></div>";
    return h;
  }


  function reactionsView() {
    var R = D.reactions;
    var h = '<h2>Market reactions to past strikes</h2>';
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
    return h;
  }

  var VIEWS = [
    ["overview", "Overview", overview], ["watch", "Indicators", watch], ["feed", "News feed", feed],
    ["markets", "Markets", marketsView], ["timing", "When", timingView], ["accuracy", "Accuracy", accuracyView], ["reactions", "Reactions", reactionsView], ["forecasts", "Forecasts", forecastsView], ["polls", "Polls", pollsView],
    ["countries", "Countries", countriesView], ["timeline", "Timeline", timelineView], ["backers", "Backers", backersView],
    ["baserates", "Base rates", baseratesView], ["scenarios", "Scenarios", scenariosView], ["scorecard", "Scorecard", scorecardView],
    ["sources", "Sources", sourcesView]
  ];

  function render(key) {
    var v = VIEWS.filter(function (x) { return x[0] === key; })[0] || VIEWS[0];
    document.querySelectorAll("#tabs button").forEach(function (b) { b.setAttribute("aria-selected", b.dataset.k === v[0]); });
    $("#view").innerHTML = v[2]();
    try { localStorage.setItem("ws-tab", v[0]); } catch (e) { /* storage unavailable */ }
  }

  function start(data) {
    D = data;
    $("#meta").innerHTML = "Built " + when(D.generated_at) + "<br>" + D.counts.evidence + " evidence records &middot; " + D.timeline.length + " timeline events";
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

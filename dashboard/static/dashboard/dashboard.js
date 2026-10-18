(() => {
  "use strict";

  const API = "/api/v1";
  const PALETTE = [
    "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
    "#0891b2", "#db2777", "#4b5563", "#65a30d",
  ];
  const SENTIMENT_COLORS = {
    positive: "#16a34a",
    neutral: "#9ca3af",
    negative: "#dc2626",
  };

  let trendChart = null;
  let topicChart = null;

  const el = (id) => document.getElementById(id);

  function readFilters() {
    return { topic: el("topic").value, from: el("from").value, to: el("to").value };
  }

  async function getJSON(path, query = {}) {
    const url = new URL(API + path, window.location.origin);
    for (const [key, value] of Object.entries(query)) {
      if (value) url.searchParams.set(key, value);
    }
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`${path} answered with HTTP ${response.status}`);
    }
    return response.json();
  }

  function showError(message) {
    const box = el("error");
    box.textContent = message;
    box.hidden = !message;
  }

  function setLoading(loading) {
    for (const button of document.querySelectorAll("#filters button")) {
      button.disabled = loading;
    }
  }

  // ---------- line chart: average sentiment over time ----------
  function drawTrends(rows) {
    el("trend-empty").hidden = rows.length > 0;
    const dates = [...new Set(rows.map((row) => row.date))].sort();
    const topics = [...new Set(rows.map((row) => row.topic))].sort();

    const datasets = topics.map((topic, index) => {
      const byDate = new Map(
        rows.filter((row) => row.topic === topic).map((row) => [row.date, row.avg_sentiment])
      );
      const color = PALETTE[index % PALETTE.length];
      return {
        label: topic,
        data: dates.map((date) => (byDate.has(date) ? byDate.get(date) : null)),
        borderColor: color,
        backgroundColor: color,
        spanGaps: true,
        tension: 0.25,
        pointRadius: 3,
      };
    });

    if (trendChart) {
      trendChart.data.labels = dates;
      trendChart.data.datasets = datasets;
      trendChart.update();
      return;
    }
    trendChart = new Chart(el("trend-chart"), {
      type: "line",
      data: { labels: dates, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            min: -1,
            max: 1,
            title: { display: true, text: "Average sentiment (-1 to +1)" },
          },
        },
        plugins: { legend: { position: "bottom" } },
      },
    });
  }

  // ---------- stacked bar chart: articles per topic ----------
  function drawTopics(rows) {
    el("topic-empty").hidden = rows.length > 0;
    const labels = rows.map((row) => row.topic);
    const datasets = ["positive", "neutral", "negative"].map((label) => ({
      label,
      data: rows.map((row) => row[`${label}_count`]),
      backgroundColor: SENTIMENT_COLORS[label],
    }));

    if (topicChart) {
      topicChart.data.labels = labels;
      topicChart.data.datasets = datasets;
      topicChart.update();
      return;
    }
    topicChart = new Chart(el("topic-chart"), {
      type: "bar",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { stacked: true },
          y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
        },
        plugins: { legend: { position: "bottom" } },
      },
    });
  }

  // ---------- table: latest headlines ----------
  function cell(text, className) {
    const td = document.createElement("td");
    td.textContent = text;
    if (className) td.className = className;
    return td;
  }

  // Only allow normal web links, so a strange URL can never run code.
  function safeUrl(value) {
    try {
      const url = new URL(value);
      return ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch {
      return null;
    }
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  function badge(enrichment) {
    const span = document.createElement("span");
    if (!enrichment) {
      span.className = "badge pending";
      span.textContent = "pending";
      return span;
    }
    const score = enrichment.sentiment_score;
    span.className = `badge ${enrichment.sentiment_label}`;
    span.textContent = `${enrichment.sentiment_label} ${score > 0 ? "+" : ""}${score.toFixed(2)}`;
    return span;
  }

  function drawArticles(articles, total) {
    const body = el("articles");
    body.replaceChildren();
    el("articles-empty").hidden = articles.length > 0;
    el("count").textContent = total ? `(showing ${articles.length} of ${total})` : "";

    for (const article of articles) {
      const row = document.createElement("tr");
      row.appendChild(cell(formatDate(article.published_at), "nowrap"));

      const headline = document.createElement("td");
      const href = safeUrl(article.url);
      if (href) {
        const link = document.createElement("a");
        link.href = href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = article.title;
        headline.appendChild(link);
      } else {
        headline.textContent = article.title;
      }
      row.appendChild(headline);

      row.appendChild(cell(article.source));
      row.appendChild(cell(article.enrichment ? article.enrichment.topic : "-"));

      const sentiment = document.createElement("td");
      sentiment.appendChild(badge(article.enrichment));
      row.appendChild(sentiment);

      body.appendChild(row);
    }
  }

  function showUpdated(health) {
    const label = el("updated");
    if (health && health.last_successful_run) {
      label.textContent = `Pipeline last succeeded: ${formatDate(health.last_successful_run)}`;
    } else {
      label.textContent = "The pipeline has not run successfully yet.";
    }
  }

  // ---------- load everything ----------
  async function load() {
    const { topic, from, to } = readFilters();
    if (from && to && from > to) {
      showError("'From' must not be later than 'To'.");
      return;
    }
    showError("");
    setLoading(true);
    try {
      const [trends, topics, articles, health] = await Promise.all([
        getJSON("/trends/", { topic, from, to }),
        getJSON("/topics/", { from, to }),
        getJSON("/articles/", {
          topic,
          published_after: from,
          published_before: to,
          page_size: 15,
        }),
        getJSON("/health/").catch(() => null),
      ]);
      drawTrends(trends);
      drawTopics(topics);
      drawArticles(articles.results, articles.count);
      showUpdated(health);
    } catch (error) {
      showError(`Could not load data: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  el("filters").addEventListener("submit", (event) => {
    event.preventDefault();
    load();
  });

  el("reset").addEventListener("click", () => {
    el("topic").value = "";
    el("from").value = "";
    el("to").value = "";
    load();
  });

  load();
})();
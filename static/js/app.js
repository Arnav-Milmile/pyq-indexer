const PAGE_SIZE = 100;

const state = {
  course: [],
  branch: [],
  exam_category: [],
  year: [],
};

const resultState = {
  mode: "browse",
  query: "",
  offset: 0,
  total: 0,
  papers: [],
  loading: false,
};

const filterLabels = {
  year: "Year",
  branch: "Branch",
  course: "Course",
  exam_category: "Exam",
};

const filterOrder = ["year", "branch", "course", "exam_category"];

const filterOptions = {
  course: [],
  branch: [],
  exam_category: [],
  year: [],
};

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatBytes(bytes) {
  if (!bytes) return "";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index ? 1 : 0)} ${units[index]}`;
}

function paperMeta(paper) {
  return [
    paper.course,
    paper.display_branch || paper.branch,
    paper.exam_category,
    paper.session || paper.year,
    paper.semester,
    formatBytes(paper.file_size),
  ]
    .filter(Boolean)
    .join(" / ");
}

function setLoading(isLoading, message = "Loading papers...") {
  resultState.loading = isLoading;
  const status = $("#result-status");
  const loadMore = $("#load-more");
  if (status) status.textContent = isLoading ? message : "";
  if (loadMore) loadMore.disabled = isLoading;
}

function selectedParams() {
  const params = new URLSearchParams();
  Object.entries(state).forEach(([key, values]) => {
    values.forEach((value) => params.append(key, value));
  });
  return params;
}

function branchLabel(value) {
  const option = filterOptions.branch.find((item) => item.value === value);
  return option?.label || value;
}

function filterDisplay(key, value) {
  return key === "branch" ? branchLabel(value) : value;
}

function updateResultSummary() {
  const count = $("#result-count");
  const status = $("#result-status");
  const loadMore = $("#load-more");
  const shown = resultState.papers.length;
  const total = resultState.total;

  if (count) count.textContent = total === 1 ? "1 paper" : `${total} papers`;

  if (status && !resultState.loading) {
    if (!total) {
      status.textContent = "Try clearing one filter or searching by paper name.";
    } else if (shown < total) {
      status.textContent = `Showing ${shown} of ${total}.`;
    } else {
      status.textContent = `Showing all ${total}.`;
    }
  }

  if (loadMore) loadMore.hidden = shown >= total || !total;
}

function renderPapers(papers) {
  const container = $("#results");
  if (!container) return;

  if (!papers.length) {
    container.innerHTML = `
      <div class="empty-state">
        <strong>No papers found.</strong>
        <span>The index is ready, but this combination has no matching PDFs.</span>
      </div>
    `;
    updateResultSummary();
    return;
  }

  container.innerHTML = papers
    .map(
      (paper) => `
        <article class="paper-row">
          <div>
            <h3>${escapeHtml(paper.subject || paper.filename)}</h3>
            <p>${escapeHtml(paperMeta(paper) || paper.ftp_path)}</p>
          </div>
          <div class="paper-actions">
            <button class="ghost-button preview-button" type="button" data-paper-id="${paper.id}" data-paper-title="${escapeHtml(paper.subject || paper.filename)}">Preview</button>
            <a class="download-button" href="/api/papers/${paper.id}/download">Download</a>
          </div>
        </article>
      `,
    )
    .join("");
  bindPaperActions();
  updateResultSummary();
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

async function fetchBrowsePage(reset = true) {
  resultState.mode = "browse";
  if (reset) {
    resultState.offset = 0;
    resultState.papers = [];
  }

  const params = selectedParams();
  const countParams = new URLSearchParams(params);
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String(resultState.offset));

  setLoading(true, reset ? "Loading papers..." : "Loading more papers...");
  try {
    const [papers, count] = await Promise.all([
      getJson(`/api/papers?${params.toString()}`),
      reset ? getJson(`/api/papers/count?${countParams.toString()}`) : Promise.resolve({ total: resultState.total }),
    ]);
    resultState.total = count.total;
    resultState.papers = reset ? papers : resultState.papers.concat(papers);
    resultState.offset = resultState.papers.length;
    renderPapers(resultState.papers);
  } catch {
    resultState.total = 0;
    resultState.papers = [];
    renderPapers([]);
  } finally {
    setLoading(false);
    updateResultSummary();
  }
}

async function fetchSearchPage(query, reset = true) {
  resultState.mode = "search";
  resultState.query = query;
  if (reset) {
    resultState.offset = 0;
    resultState.papers = [];
  }

  const params = selectedParams();
  const countParams = new URLSearchParams(params);
  params.set("q", query);
  countParams.set("q", query);
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String(resultState.offset));

  setLoading(true, reset ? "Searching papers..." : "Loading more matches...");
  try {
    const [papers, count] = await Promise.all([
      getJson(`/api/papers/search?${params.toString()}`),
      reset ? getJson(`/api/papers/search/count?${countParams.toString()}`) : Promise.resolve({ total: resultState.total }),
    ]);
    resultState.total = count.total;
    resultState.papers = reset ? papers : resultState.papers.concat(papers);
    resultState.offset = resultState.papers.length;
    renderPapers(resultState.papers);
  } catch {
    resultState.total = 0;
    resultState.papers = [];
    renderPapers([]);
  } finally {
    setLoading(false);
    updateResultSummary();
  }
}

function reloadCurrentResults() {
  if (resultState.mode === "search" && resultState.query) {
    return fetchSearchPage(resultState.query, true);
  }
  return fetchBrowsePage(true);
}

async function loadFilters() {
  const [courses, branches, exams, years] = await Promise.all([
    getJson("/api/courses"),
    getJson("/api/branch-options"),
    getJson("/api/exam-categories"),
    getJson("/api/years"),
  ]);
  filterOptions.course = courses.map((value) => ({ value, label: value }));
  filterOptions.branch = branches;
  filterOptions.exam_category = exams.map((value) => ({ value, label: value }));
  filterOptions.year = years.map((value) => ({ value, label: value })).reverse();
  renderFilterGroups();
  renderFilterChips();
}

function renderFilterGroups() {
  const container = $("#filter-groups");
  if (!container) return;

  container.innerHTML = filterOrder
    .map((key) => {
      const label = filterLabels[key];
      const options = filterOptions[key] || [];
      return `
        <section class="checkbox-group">
          <h3>${label}</h3>
          <div class="checkbox-options">
            ${options
              .map(
                (option) => `
                  <label class="checkbox-option">
                    <input type="checkbox" value="${escapeHtml(option.value)}" data-filter-key="${key}" ${state[key].includes(option.value) ? "checked" : ""}>
                    <span>${escapeHtml(option.label)}</span>
                  </label>
                `,
              )
              .join("")}
          </div>
        </section>
      `;
    })
    .join("");

  container.querySelectorAll("input[type='checkbox']").forEach((input) => {
    input.addEventListener("change", () => {
      const key = input.dataset.filterKey;
      const values = new Set(state[key]);
      if (input.checked) values.add(input.value);
      else values.delete(input.value);
      state[key] = Array.from(values);
      renderFilterChips();
    });
  });
}

function renderFilterChips() {
  const container = $("#active-filters");
  if (!container) return;

  const chips = Object.entries(state).flatMap(([key, values]) =>
    values.map(
      (value) => `
        <button class="filter-chip" type="button" data-filter-key="${key}" data-filter-value="${escapeHtml(value)}">
          <span>${filterLabels[key]}: ${escapeHtml(filterDisplay(key, value))}</span>
          <strong aria-hidden="true">x</strong>
        </button>
      `,
    ),
  );

  container.innerHTML = chips.join("");
  container.hidden = !chips.length;
  container.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", async () => {
      const key = chip.dataset.filterKey;
      const value = chip.dataset.filterValue;
      state[key] = state[key].filter((item) => item !== value);
      renderFilterGroups();
      renderFilterChips();
      await reloadCurrentResults();
    });
  });
}

function clearFilters() {
  Object.keys(state).forEach((key) => {
    state[key] = [];
  });
  renderFilterGroups();
  renderFilterChips();
}

function openFilterDrawer() {
  const drawer = $("#filter-drawer");
  if (!drawer) return;
  drawer.hidden = false;
  document.body.classList.add("modal-open");
}

function closeFilterDrawer() {
  const drawer = $("#filter-drawer");
  if (!drawer || drawer.hidden) return;
  drawer.hidden = true;
  document.body.classList.remove("modal-open");
}

function bindFilterDrawer() {
  $("#open-filters")?.addEventListener("click", openFilterDrawer);
  document.querySelectorAll("[data-filter-close]").forEach((item) => {
    item.addEventListener("click", closeFilterDrawer);
  });
  $("#apply-filters")?.addEventListener("click", async () => {
    closeFilterDrawer();
    await reloadCurrentResults();
  });
  [$("#clear-filters"), $("#drawer-clear-filters")].forEach((button) => {
    button?.addEventListener("click", async () => {
      clearFilters();
      await reloadCurrentResults();
    });
  });
}

function bindLoadMore() {
  const loadMore = $("#load-more");
  if (!loadMore) return;

  loadMore.addEventListener("click", () => {
    if (resultState.mode === "search") fetchSearchPage(resultState.query, false);
    else fetchBrowsePage(false);
  });
}

function ensurePreviewModal() {
  let modal = $("#preview-modal");
  if (modal) return modal;

  document.body.insertAdjacentHTML(
    "beforeend",
    `
      <div class="preview-modal" id="preview-modal" hidden>
        <div class="preview-backdrop" data-preview-close></div>
        <section class="preview-dialog" role="dialog" aria-modal="true" aria-labelledby="preview-title">
          <header class="preview-head">
            <h2 id="preview-title">Paper preview</h2>
            <div class="preview-actions">
              <a class="ghost-button" id="preview-open" target="_blank" rel="noopener">Open</a>
              <a class="download-button" id="preview-download">Download</a>
              <button class="ghost-button" type="button" data-preview-close>Close</button>
            </div>
          </header>
          <div class="preview-status" id="preview-status">Loading preview...</div>
          <iframe id="preview-frame" title="PDF preview"></iframe>
        </section>
      </div>
    `,
  );

  modal = $("#preview-modal");
  modal.querySelectorAll("[data-preview-close]").forEach((item) => {
    item.addEventListener("click", closePreview);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closePreview();
      closeFilterDrawer();
    }
  });
  return modal;
}

function openPreview(paperId, title) {
  const modal = ensurePreviewModal();
  const previewUrl = `/api/papers/${paperId}/preview`;
  const downloadUrl = `/api/papers/${paperId}/download`;
  const status = $("#preview-status");
  const frame = $("#preview-frame");

  $("#preview-title").textContent = title || "Paper preview";
  status.textContent = "Loading preview...";
  status.hidden = false;
  frame.hidden = true;
  frame.onload = () => {
    status.hidden = true;
    frame.hidden = false;
  };
  frame.src = previewUrl;
  $("#preview-open").href = previewUrl;
  $("#preview-download").href = downloadUrl;
  modal.hidden = false;
  document.body.classList.add("modal-open");

  window.setTimeout(() => {
    if (!modal.hidden && frame.hidden) {
      status.textContent = "Preview is taking longer than expected. Open or download the paper if it does not appear.";
    }
  }, 8000);
}

function closePreview() {
  const modal = $("#preview-modal");
  if (!modal || modal.hidden) return;
  const frame = $("#preview-frame");
  frame.onload = null;
  frame.src = "about:blank";
  modal.hidden = true;
  document.body.classList.remove("modal-open");
}

function bindPaperActions() {
  document.querySelectorAll(".preview-button").forEach((button) => {
    button.addEventListener("click", () => {
      openPreview(button.dataset.paperId, button.dataset.paperTitle);
    });
  });
}

function bindSearchPage() {
  if (!document.querySelector('[data-page="search"]')) return;
  const form = $("#search-form");
  if (!form) return;

  bindLoadMore();
  bindFilterDrawer();
  loadFilters().then(() => fetchBrowsePage(true)).catch(() => renderPapers([]));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = $("#search-input").value.trim();
    if (query) fetchSearchPage(query, true);
  });
}

function bindBrowsePage() {
  if (!document.querySelector('[data-page="browse"]')) return;
  if (!$("#results") || !$("#filter-groups")) return;

  bindLoadMore();
  bindFilterDrawer();
  loadFilters().then(() => fetchBrowsePage(true)).catch(() => renderPapers([]));
}

bindSearchPage();
bindBrowsePage();

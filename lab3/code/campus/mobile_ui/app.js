"use strict";

const content = document.querySelector("#content");
const modal = document.querySelector("#dialog");
const notice = document.querySelector("#notice");
const account = document.querySelector("#account");

const categories = {
  books: "书籍", electronics: "数码", daily: "生活用品",
  sports: "运动", other: "其他",
};
const conditions = {
  new: "全新", "like-new": "几乎全新", good: "良好", fair: "有使用痕迹",
};
const states = {
  draft: "草稿", review: "待审核", rejected: "审核驳回", published: "已发布",
  reserved: "已预约", trading: "交易中", completed: "已完成",
  withdrawn: "已下架", frozen: "已冻结", pending: "待卖家确认",
  cancelled: "已取消", delivered: "待买家确认", disputed: "待管理员处理",
};
let user = null;
let needsAdmin = false;
let currentItem = null;
let tradeSide = "buy";
let requestedView = 0;
let noticeTimer;
const search = {keyword: "", category: "", min: "", max: "", page: 1, sort: "newest"};

async function api(action, data) {
  const args = data === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data),
  };
  const response = await fetch("/api/" + action, args);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "操作失败");
  return result;
}

function safe(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function money(cents) {
  return (cents / 100).toFixed(2);
}

function date(epoch) {
  return epoch ? new Date(epoch * 1000).toLocaleString("zh-CN") : "—";
}

function key() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
}

function shout(message) {
  notice.textContent = message;
  notice.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { notice.hidden = true; }, 4200);
}

function heading(title, subtitle = "") {
  return `<section class="headline"><h1>${safe(title)}</h1>
    ${subtitle ? `<p>${safe(subtitle)}</p>` : ""}</section>`;
}

function button(label, action, value = "", primary = false) {
  return `<button type="button" class="${primary ? "primary" : "quiet"}"
    data-action="${action}" data-value="${safe(value)}">${safe(label)}</button>`;
}

function empty(message) {
  return `<p class="empty">${safe(message)}</p>`;
}

function options(values, selected = "", any = "") {
  return (any ? `<option value="">${safe(any)}</option>` : "") +
    Object.entries(values).map(([id, title]) =>
      `<option value="${safe(id)}" ${id === selected ? "selected" : ""}>${safe(title)}</option>`
    ).join("");
}

function showForm(title, fields, submit, run) {
  modal.innerHTML = `<form><h2>${safe(title)}</h2>${fields}
    <p class="error" role="alert" hidden></p>
    <div class="actions"><button type="button" class="quiet" data-action="dismiss">取消</button>
    <button type="submit" class="primary">${safe(submit)}</button></div></form>`;
  const form = modal.querySelector("form");
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const submitButton = form.querySelector('[type="submit"]');
    const error = form.querySelector(".error");
    submitButton.disabled = true;
    error.hidden = true;
    try {
      await run(new FormData(form));
      if (modal.contains(form)) modal.close();
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
    } finally {
      submitButton.disabled = false;
    }
  });
  if (!modal.open) modal.showModal();
}

async function updateSession() {
  const state = await api("session");
  user = state.user;
  needsAdmin = state.needs_admin;
  account.textContent = user?.account || "登录";
}

function navigate(page) {
  if (location.hash === "#" + page) render();
  else location.hash = page;
}

function photo(id, position, title = "") {
  return `<img class="photo" src="/media/${id}/${position}" alt="${safe(title)}" loading="lazy">`;
}

function card(item, owned = false) {
  const action = owned ? "edit" : "open";
  const preview = item.cover_position
    ? photo(item.id, item.cover_position, item.title)
    : '<span class="photo blank" aria-label="无商品照片">◇</span>';
  return `<button type="button" class="card" data-action="${action}" data-value="${item.id}">
    ${preview}<span class="card-text">
    <strong>${safe(item.title)}</strong>
    <span class="price">¥${money(item.price_cents)}</span>
    <span class="tag">${safe(owned ? states[item.state] : conditions[item.condition])}</span>
    </span></button>`;
}

async function home() {
  const result = await api("search", search);
  const list = {"": "全部", ...categories};
  const chips = Object.entries(list).map(([value, label]) => `
    <button type="button" class="chip ${value === search.category ? "active" : ""}"
      data-action="category" data-value="${value}">${label}</button>`).join("");
  const totalPages = Math.max(1, Math.ceil(result.total / 16));
  const pager = totalPages === 1 ? "" : `<div class="pager">
    ${search.page > 1 ? button("上一页", "page", search.page - 1) : ""}
    <span>${search.page} / ${totalPages}</span>
    ${search.page < totalPages ? button("下一页", "page", search.page + 1) : ""}
    </div>`;
  return `${heading("校园好物")}
    <form class="search" data-form="search">
      <input type="search" name="keyword" aria-label="搜索商品" placeholder="搜教材、数码和日用闲置"
        value="${safe(search.keyword)}">
      <button type="submit" class="primary">搜索</button>${button("筛选", "filter")}
    </form>
    <div class="chips">${chips}</div>
    ${result.items.length ? `<div class="grid">${result.items.map(item => card(item)).join("")}</div>`
    : empty("暂无匹配的商品")}${pager}`;
}

async function detail(id) {
  const item = await api("item", {id: Number(id)});
  currentItem = item;
  const pictures = item.images.map(image => photo(item.id, image.position, item.title)).join("");
  const canReserve = item.state === "published" && user?.role !== "admin"
    && user?.id !== item.seller_id;
  return `${heading(item.title)}<div class="stack">
    ${pictures ? `<div class="detail-photos">${pictures}</div>` : ""}
    <div class="panel"><span class="price">¥${money(item.price_cents)}</span>
    <p class="tag">${safe(categories[item.category])} · ${safe(conditions[item.condition])}
      · ${safe(states[item.state])}</p>
    <p class="description">${safe(item.description)}</p>
    <div class="actions">${canReserve ? button("预约面交", "reserve", item.id, true) : ""}
    ${user?.role !== "admin" ? button("举报商品", "report", item.id) : ""}</div></div></div>`;
}

function loginGate(message) {
  return `<div class="panel"><p>${safe(message)}</p><div class="actions">
    ${button("登录", "login", "", true)}${button("注册", "register")}
    ${needsAdmin ? button("初始化管理员", "setup") : ""}</div></div>`;
}

function productForm(item = null) {
  const imageField = item ? "" : `<label>商品照片
    <input type="file" name="images" accept="image/png,image/jpeg" multiple></label>`;
  return `<form class="panel" data-form="product" data-id="${item?.id ?? ""}">
    <label>标题<input name="title" maxlength="100" required value="${safe(item?.title)}"></label>
    <label>描述<textarea name="description" rows="4" maxlength="2000" required>${safe(item?.description)}</textarea></label>
    <label>分类<select name="category">${options(categories, item?.category)}</select></label>
    <label>成色<select name="condition">${options(conditions, item?.condition)}</select></label>
    <label>价格（元）<input name="price" inputmode="decimal" required
      value="${item ? money(item.price_cents) : ""}"></label>
    ${imageField}<button type="submit" class="primary">${item ? "保存修改" : "保存草稿"}</button>
    </form>`;
}

async function editProduct(id) {
  const item = await api("item", {id: Number(id)});
  const history = (item.reviews || []).map(review =>
    `<p class="muted">${safe(states[review.decision])} · ${safe(review.reason)}</p>`).join("");
  const editable = ["draft", "rejected", "published"].includes(item.state);
  const submit = ["draft", "rejected"].includes(item.state)
    ? button("提交审核", "submit", id, true) : "";
  const withdraw = item.state === "published" ? button("下架", "withdraw", id) : "";
  return `${heading(item.title, states[item.state])}<div class="stack">
    ${history}${editable ? productForm(item) : empty("当前状态不可编辑")}
    <div class="actions">${submit}${withdraw}</div></div>`;
}

function tradeButtons(record) {
  const labels = {
    accept: "接受预约", cancel: "取消预约", reject: "拒绝预约",
    deliver: "标记已交付", complete: "确认完成", dispute: "提出争议",
  };
  const fromState = {
    "buy:pending": ["cancel"], "sell:pending": ["accept", "reject"],
    "sell:trading": ["deliver"], "buy:delivered": ["complete", "dispute"],
  };
  return (fromState[tradeSide + ":" + record.state] || []).map((action, index) =>
    button(labels[action], "trade", record.id + ":" + action, index === 0)
  ).join("");
}

async function tradePage() {
  if (!user) return heading("我的交易") + loginGate("登录后查看预约和交易。");
  if (user.role === "admin") {
    return heading("交易管理") + button("查看交易争议", "admin", "disputes", true);
  }
  const records = await api("records", {side: tradeSide});
  return `${heading("我的交易")}<div class="stack">
    <div class="actions">${button("买入预约", "side", "buy", tradeSide === "buy")}
      ${button("卖出预约", "side", "sell", tradeSide === "sell")}</div>
    ${records.length ? records.map(record => `<article class="entry">
      <h2>${safe(record.title)}</h2>
      <p>${safe(record.state === "rejected" ? "已拒绝" : states[record.state])}
      · ¥${money(record.price_cents)}</p>
      <p class="tag">预约 #${record.id} · ${safe(date(record.created_at))}</p>
      ${record.closed_reason ? `<p>${safe(record.closed_reason)}</p>` : ""}
      <div class="actions">${tradeButtons(record)}</div></article>`).join("")
      : empty("还没有预约记录")}</div>`;
}

async function myAccount() {
  if (!user) return heading("我的") + loginGate("登录后管理商品和交易。");
  const identity = `<div class="panel"><div class="identity">
    <strong>${safe(user.account)} · ${user.role === "admin" ? "管理员" : "普通用户"}</strong>
    ${button("退出登录", "logout")}</div></div>`;
  if (user.role === "admin") {
    const tools = [["商品审核", "review"], ["商品处置", "items"], ["举报处理", "reports"],
      ["交易争议", "disputes"], ["统计", "stats"], ["操作日志", "audit"]];
    return heading("管理工作台") + `<div class="stack">${identity}<div class="panel">
      <div class="actions">${tools.map(([label, value]) => button(label, "admin", value)).join("")}</div>
      </div></div>`;
  }
  const result = await api("search", {scope: "mine", page: minePage});
  const pager = result.total > 16 ? `<div class="pager">
    ${minePage > 1 ? button("上一页", "mine-page", minePage - 1) : ""}
    <span>${minePage} / ${Math.ceil(result.total / 16)}</span>
    ${minePage * 16 < result.total ? button("下一页", "mine-page", minePage + 1) : ""}
    </div>` : "";
  return `${heading("我的")}<div class="stack">${identity}
    <div class="actions">${button("发布闲置", "publish", "", true)}${button("个人统计", "admin", "stats")}</div>
    <h2>我发布的商品</h2>
    ${result.items.length ? `<div class="grid">${result.items.map(item => card(item, true)).join("")}</div>`
    : empty("还没有发布过商品")}${pager}</div>`;
}

let minePage = 1;
let moderationPage = 1;
let statsFilters = {};
let auditFilters = {};

function inspectCards(items, reviewing) {
  return items.map(item => `<article class="entry">
    <h2>${safe(item.title)}</h2><p>¥${money(item.price_cents)} · ${safe(states[item.state])}</p>
    <div class="actions">${button("查看商品", "open", item.id)}
    ${reviewing ? button("通过", "review", item.id + ":approve", true)
      + button("驳回", "review", item.id + ":reject")
      : (["published", "reserved", "trading"].includes(item.state)
        ? button("冻结", "moderate", item.id + ":freeze") : "")
        + (item.state === "published" ? button("管理员下架", "moderate", item.id + ":withdraw") : "")}</div>
    </article>`).join("");
}

async function adminPage(section) {
  if (section === "stats") return statistics();
  if (user?.role !== "admin") return heading("管理工作台") + loginGate("请使用管理员账号。");
  if (section === "review" || section === "items") {
    const reviewing = section === "review";
    const data = await api("search", {scope: "admin", state: reviewing ? "review" : "",
      page: moderationPage});
    const pager = data.total > 16 ? `<div class="pager">
      ${moderationPage > 1 ? button("上一页", "moderation-page", moderationPage - 1) : ""}
      <span>${moderationPage} / ${Math.ceil(data.total / 16)}</span>
      ${moderationPage * 16 < data.total ? button("下一页", "moderation-page", moderationPage + 1) : ""}
      </div>` : "";
    return heading(reviewing ? "商品审核" : "商品处置") +
      `<div class="stack">${data.items.length ? inspectCards(data.items, reviewing)
        : empty("没有匹配的商品")}${pager}</div>`;
  }
  if (section === "reports") {
    const reports = await api("reports", {});
    return heading("举报处理") + `<div class="stack">${reports.length ? reports.map(report =>
      `<article class="entry"><h2>${safe(report.title)}</h2>
      <p class="description">${safe(report.reason)}</p><p class="tag">举报 #${report.id}</p>
      ${report.result ? `<p>处理结果：${safe(report.result)}</p>`
        : button("记录处理结果", "resolve", report.id, true)}</article>`
    ).join("") : empty("没有举报记录")}</div>`;
  }
  if (section === "disputes") {
    const disputes = await api("disputes", {});
    return heading("交易争议") + `<div class="stack">${disputes.length ? disputes.map(dispute =>
      `<article class="entry"><h2>${safe(dispute.title)}</h2>
      <p class="tag">预约 #${dispute.reservation_id} · 待管理员处理</p>
      <p class="description">${safe(dispute.reason)}</p>
      ${dispute.opinions.map(note => `<p>处理意见：${safe(note.body)}</p>`).join("")}
      ${button("追加处理意见", "opinion", dispute.id, true)}</article>`
    ).join("") : empty("没有争议记录")}</div>`;
  }
  return auditPage();
}

function dates(filters) {
  return `<label>起始日期（含）<input type="date" name="start" value="${safe(filters.start)}"></label>
    <label>结束日期（不含）<input type="date" name="end" value="${safe(filters.end)}"></label>`;
}

async function statistics() {
  if (!user) return heading("统计") + loginGate("请先登录。");
  const summary = await api("stats", {...statsFilters, scope: user.role === "admin" ? "admin" : "mine"});
  return `${heading("统计", "日期按 UTC 筛选")}<div class="stack">
    <form class="panel" data-form="stats">${dates(statsFilters)}
      <label>分类<select name="category">${options(categories, statsFilters.category, "全部")}</select></label>
      <label>商品状态<select name="state">${options(Object.fromEntries(
        Object.entries(states).slice(0, 9)), statsFilters.state, "全部")}</select></label>
      <button class="primary">查询</button></form>
    <section class="panel"><dl>
    <dt>商品数量</dt><dd>${summary.items}</dd><dt>完成交易</dt><dd>${summary.completed}</dd>
    ${summary.reservations !== undefined ? `<dt>预约总数</dt><dd>${summary.reservations}</dd>
      <dt>有效预约</dt><dd>${summary.valid_reservations}</dd>
      <dt>已处理举报</dt><dd>${summary.reports_handled} / ${summary.reports}</dd>` : ""}
    ${Object.entries(summary.item_states).map(([name, value]) =>
      `<dt>${safe(states[name])}</dt><dd>${value}</dd>`).join("")}</dl></section></div>`;
}

async function auditPage() {
  const records = await api("audit", auditFilters);
  return `${heading("操作日志", "日期按 UTC 筛选")}<div class="stack">
    <form class="panel" data-form="audit">${dates(auditFilters)}
      <label>操作者账号<input name="actor" value="${safe(auditFilters.actor)}"></label>
      <label>操作类型<input name="action" placeholder="如 review 或 reserve" value="${safe(auditFilters.action)}"></label>
      <label>结果<select name="outcome">${options({ok: "成功", denied: "拒绝"}, auditFilters.outcome, "全部")}</select></label>
      <button class="primary">查询</button></form>
    ${records.length ? records.map(record => `<article class="entry">
      <strong>${safe(record.action)} · ${record.outcome === "ok" ? "成功" : "拒绝"}</strong>
      <p>${safe(record.account || "系统")} · ${safe(record.entity)} #${safe(record.entity_id)}</p>
      <p class="tag">${safe(date(record.created_at))} ${safe(record.detail)}</p>
    </article>`).join("") : empty("暂无日志")}</div>`;
}

async function render() {
  const view = ++requestedView;
  const [page, id] = (location.hash.slice(1) || "home").split("/");
  const activePage = page === "admin" || page === "edit" ? "account" : page;
  for (const link of document.querySelectorAll("nav a")) {
    const current = link.getAttribute("href") === "#" + activePage;
    link.classList.toggle("active", current);
    if (current) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  try {
    let html;
    if (page === "home") html = await home();
    else if (page === "item") html = await detail(id);
    else if (page === "account") html = await myAccount();
    else if (page === "edit") html = await editProduct(id);
    else if (page === "trades") html = await tradePage();
    else if (page === "admin") html = await adminPage(id);
    else if (page === "publish") {
      html = heading("发布闲置") + (user?.role === "member" ? productForm()
        : user ? empty("请使用普通账号发布商品") : loginGate("先登录再发布闲置。"));
    } else html = empty("页面不存在");
    if (view === requestedView) {
      content.innerHTML = html;
      window.scrollTo(0, 0);
    }
  } catch (error) {
    if (view === requestedView) content.innerHTML = empty(error.message);
  }
}

function authDialog(action) {
  const title = {login: "登录", register: "注册", setup: "初始化管理员"}[action];
  showForm(title, `<label>账号<input name="account" maxlength="32" required autocomplete="username"></label>
    <label>密码<input name="password" type="password" maxlength="128" required
      autocomplete="${action === "login" ? "current-password" : "new-password"}"></label>`,
  title, async form => {
    await api(action, Object.fromEntries(form));
    await updateSession();
    if (action === "login") {
      if (user?.role === "admin") navigate("account");
      else render();
    } else {
      shout(action === "setup" ? "管理员已创建，请登录" : "注册成功，请登录");
      authDialog("login");
    }
  });
}

function reasonDialog(title, label, run) {
  showForm(title, `<label>${safe(label)}<textarea name="reason" rows="4" maxlength="1000" required></textarea></label>`,
    "确认", form => run(String(form.get("reason"))));
}

function confirmDialog(title, description, run) {
  showForm(title, `<p>${safe(description)}</p>`, "确认", run);
}

function filterDialog() {
  const sorts = {newest: "最新发布", "price-up": "价格从低到高", "price-down": "价格从高到低"};
  showForm("筛选商品", `<label>最低价<input name="min" inputmode="decimal" value="${safe(search.min)}"></label>
    <label>最高价<input name="max" inputmode="decimal" value="${safe(search.max)}"></label>
    <label>排序<select name="sort">${options(sorts, search.sort)}</select></label>`,
  "应用", async form => {
    const next = {...search, ...Object.fromEntries(form), page: 1};
    await api("search", next);
    Object.assign(search, next);
    render();
  });
}

async function refreshAfter(action, payload, message) {
  await api(action, payload);
  shout(message);
  await render();
}

function reservationAction(value) {
  const [id, action] = value.split(":");
  const save = reason => refreshAfter("trade", {id: Number(id), action, reason}, "预约已更新");
  const labels = {accept: "接受预约", cancel: "取消预约", reject: "拒绝预约",
    deliver: "标记交付", complete: "确认完成", dispute: "提出争议"};
  if (action === "reject" || action === "dispute") reasonDialog(labels[action], "原因", save);
  else confirmDialog(labels[action], "确认执行这项操作？", () => save(""));
}

function resolveDialog(id) {
  showForm("处理举报", `<label>处理结果<textarea name="result" rows="3" required></textarea></label>
    <label>商品处置<select name="decision"><option value="">仅记录处理结果</option>
    <option value="freeze">冻结</option><option value="withdraw">下架</option></select></label>
    <label>处置原因（冻结或下架时填写）<input name="reason"></label>`, "保存",
    form => refreshAfter("resolve", {id: Number(id), ...Object.fromEntries(form)}, "处理结果已保存"));
}

const actions = {
  account: () => user ? navigate("account") : authDialog("login"),
  dismiss: () => modal.close(),
  login: () => authDialog("login"),
  register: () => authDialog("register"),
  setup: () => authDialog("setup"),
  publish: () => navigate("publish"),
  open: id => navigate("item/" + id),
  edit: id => navigate("edit/" + id),
  admin: section => { moderationPage = 1; navigate("admin/" + section); },
  "mine-page": page => { minePage = Number(page); render(); },
  "moderation-page": page => { moderationPage = Number(page); render(); },
  category: value => { search.category = value; search.page = 1; render(); },
  page: value => { search.page = Number(value); render(); },
  filter: filterDialog,
  side: value => { tradeSide = value; render(); },
  logout: async () => {
    await api("logout", {});
    await updateSession();
    minePage = 1;
    navigate("home");
  },
  reserve: id => {
    if (!user) return authDialog("login");
    const {price_cents, version} = currentItem;
    const requestKey = key();
    confirmDialog("确认预约", `按 ¥${money(price_cents)} 预约这件商品？`, async () => {
      await api("reserve", {id: Number(id), price_cents, version, key: requestKey});
      tradeSide = "buy";
      shout("预约成功，等待卖家确认");
      navigate("trades");
    });
  },
  submit: id => confirmDialog("提交审核", "审核通过后买家即可查看。", () =>
    refreshAfter("submit", {id: Number(id)}, "已提交审核")),
  withdraw: id => confirmDialog("下架商品", "下架后将从商品列表移除。", () =>
    refreshAfter("withdraw", {id: Number(id)}, "已下架")),
  report: id => {
    if (!user) return authDialog("login");
    const requestKey = key();
    reasonDialog("举报商品", "举报原因", reason =>
      refreshAfter("report", {id: Number(id), reason, key: requestKey}, "举报已提交"));
  },
  trade: reservationAction,
  review: value => {
    const [id, decision] = value.split(":");
    reasonDialog(decision === "approve" ? "通过审核" : "驳回审核", "审核原因", reason =>
      refreshAfter("review", {id: Number(id), reason, decision}, "审核已记录"));
  },
  moderate: value => {
    const [id, decision] = value.split(":");
    reasonDialog(decision === "freeze" ? "冻结商品" : "下架商品", "处置原因", reason =>
      refreshAfter("moderate", {id: Number(id), reason, decision}, "处置已记录"));
  },
  resolve: resolveDialog,
  opinion: id => reasonDialog("追加处理意见", "处理意见", opinion =>
    refreshAfter("opinion", {id: Number(id), opinion}, "处理意见已追加")),
};

function readPhoto(file) {
  return new Promise((resolve, reject) => {
    if (file.size > 5 * 1024 * 1024) {
      reject(new Error("每张图片最多 5 MB"));
      return;
    }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("图片读取失败"));
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.readAsDataURL(file);
  });
}

async function saveProduct(form, data) {
  const id = Number(form.dataset.id);
  const {images: _images, ...payload} = Object.fromEntries(data);
  if (id) {
    await refreshAfter("revise", {...payload, id}, "修改已保存");
    return;
  }
  const files = data.getAll("images").filter(file => file.size);
  if (files.length > 5) throw new Error("每件商品最多上传五张图片");
  const images = await Promise.all(files.map(readPhoto));
  form.dataset.key ||= key();
  const result = await api("create", {...payload, images, key: form.dataset.key});
  shout("草稿已保存");
  navigate("edit/" + result.id);
}

document.addEventListener("click", async event => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = actions[button.dataset.action];
  if (!action) return;
  try {
    await action(button.dataset.value);
  } catch (error) {
    shout(error.message);
  }
});

content.addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.target;
  const submit = form.querySelector('button:not([type="button"])');
  submit.disabled = true;
  const data = new FormData(form);
  try {
    if (form.dataset.form === "search") {
      search.keyword = String(data.get("keyword"));
      search.page = 1;
      await render();
    } else if (form.dataset.form === "product") {
      await saveProduct(form, data);
    } else if (form.dataset.form === "stats") {
      statsFilters = Object.fromEntries(data);
      await render();
    } else if (form.dataset.form === "audit") {
      auditFilters = Object.fromEntries(data);
      await render();
    }
  } catch (error) {
    shout(error.message);
  } finally {
    submit.disabled = false;
  }
});

window.addEventListener("hashchange", render);
updateSession().then(render).catch(() => {
  content.innerHTML = empty("无法连接电脑上的校园拾光服务，请确认后端已启动后重新打开。");
});

// CampusEats — клиентская часть. Общается с сервером через REST API (/api/...).

const STATUS_NAMES = { new: "Принят", cooking: "Готовится", ready: "Готов к выдаче", issued: "Выдан" };
const STATUS_ORDER = ["new", "cooking", "ready", "issued"];
const EMOJI = { "Первые блюда": "🥣", "Вторые блюда": "🍛", "Салаты": "🥗", "Выпечка": "🥟", "Напитки": "🧃" };

const state = {
  token: load("ce_token"),
  user: null,
  dishes: [],
  category: "Все",
  search: "",
  cart: load("ce_cart") || {},   // { dishId: количество }
  view: "menu",
  timer: null,
};

// ---------- Вспомогательные функции ----------

function load(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* хранилище недоступно */ }
}
const $ = (sel) => document.querySelector(sel);
const money = (n) => Number(n).toLocaleString("ru-RU") + " ₸";
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(text) {
  const t = $("#toast");
  t.textContent = text;
  t.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.add("hidden"), 2600);
}

// HTTP-клиент: сам подставляет JWT в заголовок Authorization
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers.Authorization = "Bearer " + state.token;
  const res = await fetch(path, { ...options, headers, body: options.body ? JSON.stringify(options.body) : undefined });
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (res.status === 401 && state.token) logout();
  if (!res.ok) {
    const err = new Error(typeof data?.detail === "string" ? data.detail : data?.detail?.message || "Ошибка сервера");
    err.status = res.status;
    err.detail = data?.detail;
    throw err;
  }
  return data;
}

// ---------- Авторизация ----------

let authMode = "login";
document.querySelectorAll("[data-auth]").forEach((btn) =>
  btn.addEventListener("click", () => {
    authMode = btn.dataset.auth;
    document.querySelectorAll("[data-auth]").forEach((b) => b.classList.toggle("active", b === btn));
    $("#name-field").classList.toggle("hidden", authMode === "login");
    $("#auth-submit").textContent = authMode === "login" ? "Войти" : "Создать аккаунт";
    $("#auth-error").classList.add("hidden");
  })
);

async function authenticate(mode, body) {
  try {
    const data = await api("/api/auth/" + mode, { method: "POST", body });
    state.token = data.token;
    save("ce_token", data.token);
    state.user = data.user;
    startApp();
  } catch (err) {
    const box = $("#auth-error");
    box.textContent = err.status === 422 ? "Проверьте поля: имя от 2 символов, пароль от 6" : err.message;
    box.classList.remove("hidden");
  }
}

$("#auth-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const body = { email: form.get("email"), password: form.get("password") };
  if (authMode === "register") body.name = form.get("name");
  authenticate(authMode, body);
});

// Быстрый вход тестовыми аккаунтами — без ввода email и пароля
const QUICK = {
  student: { email: "student@campus.kz", password: "student123" },
  cook: { email: "cook@campus.kz", password: "cook123" },
  admin: { email: "admin@campus.kz", password: "admin123" },
};
document.querySelectorAll("[data-quick]").forEach((b) =>
  b.addEventListener("click", () => authenticate("login", QUICK[b.dataset.quick]))
);

function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem("ce_token");
  clearInterval(state.timer);
  $("#app").classList.add("hidden");
  $("#auth-screen").classList.remove("hidden");
}
$("#logout").addEventListener("click", logout);

// ---------- Навигация ----------

function tabsForRole(role) {
  const tabs = [
    ["menu", "🍽️", "Меню"],
    ["cart", "🛒", "Корзина"],
    ["orders", "🧾", "Заказы"],
  ];
  if (role === "cook" || role === "admin") tabs.push(["kitchen", "👨‍🍳", "Кухня"]);
  if (role === "admin") tabs.push(["admin", "⚙️", "Управление"]);
  return tabs;
}

function renderTabs() {
  const count = Object.values(state.cart).reduce((a, b) => a + b, 0);
  $("#tabbar").innerHTML = tabsForRole(state.user.role)
    .map(([id, ico, name]) => `
      <button class="tab ${state.view === id ? "active" : ""}" data-view="${id}">
        <span class="ico">${ico}</span>${name}
        ${id === "cart" && count ? `<span class="badge">${count}</span>` : ""}
      </button>`)
    .join("");
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => show(t.dataset.view)));
}

function show(view) {
  state.view = view;
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  $("#view-" + view).classList.remove("hidden");
  renderTabs();
  clearInterval(state.timer);
  if (view === "menu") loadDishes();
  if (view === "cart") renderCart();
  if (view === "orders") { loadMyOrders(); state.timer = setInterval(loadMyOrders, 5000); }
  if (view === "kitchen") { loadKitchen(); state.timer = setInterval(loadKitchen, 5000); }
  if (view === "admin") loadAdmin();
}

async function refreshUser() {
  state.user = await api("/api/me");
  $("#balance").textContent = "💳 " + money(state.user.balance);
}

async function startApp() {
  $("#auth-screen").classList.add("hidden");
  $("#app").classList.remove("hidden");
  await refreshUser();
  $("#hello").textContent = "Привет, " + state.user.name.split(" ")[0] + "!";
  show(state.user.role === "cook" ? "kitchen" : "menu");
}

// ---------- Меню ----------

async function loadDishes() {
  state.dishes = await api("/api/dishes");
  renderMenu();
}

function renderMenu() {
  const cats = ["Все", ...new Set(state.dishes.map((d) => d.category))];
  $("#categories").innerHTML = cats
    .map((c) => `<button class="chip ${c === state.category ? "active" : ""}" data-cat="${esc(c)}">${esc(c)}</button>`)
    .join("");
  document.querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => { state.category = c.dataset.cat; renderMenu(); })
  );

  const q = state.search.trim().toLowerCase();
  const list = state.dishes.filter((d) =>
    (state.category === "Все" || d.category === state.category) && d.title.toLowerCase().includes(q)
  );
  $("#dishes").innerHTML = list.length
    ? list.map((d) => `
      <div class="dish ${d.is_available ? "" : "off"}">
        <div class="emoji">${EMOJI[d.category] || "🍴"}</div>
        <div class="title">${esc(d.title)}</div>
        <div class="cat">${d.is_available ? esc(d.category) : "Закончилось"}</div>
        <div class="bottom">
          <span class="price">${money(d.price)}</span>
          <button class="add-btn" data-add="${d.id}" ${d.is_available ? "" : "disabled"} title="В корзину">+</button>
        </div>
      </div>`).join("")
    : `<p class="empty">Ничего не найдено</p>`;
  document.querySelectorAll("[data-add]").forEach((b) =>
    b.addEventListener("click", () => addToCart(Number(b.dataset.add)))
  );
}

$("#search").addEventListener("input", (e) => { state.search = e.target.value; renderMenu(); });

// ---------- Корзина ----------

function addToCart(id, qty = 1) {
  state.cart[id] = (state.cart[id] || 0) + qty;
  save("ce_cart", state.cart);
  renderTabs();
  const dish = state.dishes.find((d) => d.id === id);
  if (dish) toast("Добавлено: " + dish.title);
}

function changeQty(id, delta) {
  state.cart[id] = (state.cart[id] || 0) + delta;
  if (state.cart[id] <= 0) delete state.cart[id];
  save("ce_cart", state.cart);
  renderCart();
  renderTabs();
}

async function renderCart() {
  if (!state.dishes.length) state.dishes = await api("/api/dishes");
  const ids = Object.keys(state.cart).map(Number);
  // убираем из корзины блюда, которых больше нет в меню
  ids.forEach((id) => { if (!state.dishes.find((d) => d.id === id)) delete state.cart[id]; });

  const items = Object.entries(state.cart).map(([id, qty]) => ({ dish: state.dishes.find((d) => d.id === Number(id)), qty }));
  $("#cart-footer").classList.toggle("hidden", items.length === 0);
  $("#cart-list").innerHTML = items.length
    ? items.map(({ dish, qty }) => `
      <div class="cart-item">
        <span style="font-size:28px">${EMOJI[dish.category] || "🍴"}</span>
        <div class="name">${esc(dish.title)}<small>${money(dish.price)} × ${qty}</small></div>
        <div class="qty">
          <button data-dec="${dish.id}">−</button><b>${qty}</b><button data-inc="${dish.id}">+</button>
        </div>
      </div>`).join("")
    : `<p class="empty">Корзина пуста — загляните в меню 🙂</p>`;
  document.querySelectorAll("[data-dec]").forEach((b) => b.addEventListener("click", () => changeQty(Number(b.dataset.dec), -1)));
  document.querySelectorAll("[data-inc]").forEach((b) => b.addEventListener("click", () => changeQty(Number(b.dataset.inc), 1)));

  const total = items.reduce((sum, { dish, qty }) => sum + dish.price * qty, 0);
  $("#cart-total").textContent = money(total);
}

$("#checkout").addEventListener("click", async () => {
  const btn = $("#checkout");
  const errBox = $("#order-error");
  const replaceBox = $("#replace-box");
  errBox.classList.add("hidden");
  replaceBox.classList.add("hidden");
  btn.disabled = true;
  try {
    const items = Object.entries(state.cart).map(([dish_id, quantity]) => ({ dish_id: Number(dish_id), quantity }));
    const order = await api("/api/orders", { method: "POST", body: { items, pickup_time: $("#pickup").value } });
    state.cart = {};
    save("ce_cart", state.cart);
    await refreshUser();
    show("orders");
    showQr(order);
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
    if (err.status === 409) offerReplacement(err.detail.unavailable);
    if (err.status === 402) errBox.textContent += `: нужно ${money(err.detail.total)}, на счёте ${money(err.detail.balance)}`;
  } finally {
    btn.disabled = false;
  }
});

// Exception flow 5.1: блюдо закончилось — предлагаем замену из той же категории
async function offerReplacement(unavailable) {
  state.dishes = await api("/api/dishes");
  const box = $("#replace-box");
  box.innerHTML = unavailable.map((u) => {
    const options = state.dishes.filter((d) => d.category === u.category && d.is_available);
    return `<div><b>«${esc(u.title)}»</b> закончилось.
      ${options.length ? "Заменить на:" : "Замены в этой категории нет."}
      <div class="options">
        ${options.map((o) => `<button class="btn small" data-replace="${u.id}" data-with="${o.id}">${esc(o.title)} · ${money(o.price)}</button>`).join("")}
        <button class="btn small" data-remove="${u.id}">Убрать из заказа</button>
      </div></div>`;
  }).join("<hr>");
  box.classList.remove("hidden");
  box.querySelectorAll("[data-replace]").forEach((b) => b.addEventListener("click", () => {
    const qty = state.cart[b.dataset.replace];
    delete state.cart[b.dataset.replace];
    state.cart[b.dataset.with] = (state.cart[b.dataset.with] || 0) + qty;
    save("ce_cart", state.cart);
    box.classList.add("hidden");
    $("#order-error").classList.add("hidden");
    renderCart(); renderTabs();
  }));
  box.querySelectorAll("[data-remove]").forEach((b) => b.addEventListener("click", () => {
    delete state.cart[b.dataset.remove];
    save("ce_cart", state.cart);
    box.classList.add("hidden");
    $("#order-error").classList.add("hidden");
    renderCart(); renderTabs();
  }));
}

// ---------- Мои заказы ----------

function orderCard(o, staff = false) {
  const step = STATUS_ORDER.indexOf(o.status);
  const time = new Date(o.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  const next = STATUS_ORDER[step + 1];
  return `
    <div class="order">
      <div class="order-head">
        <b>Заказ №${o.id}${staff ? " · " + esc(o.user_name) : ""}</b>
        <span class="status ${o.status}">${STATUS_NAMES[o.status]}</span>
      </div>
      <ul>${o.items.map((i) => `<li>${esc(i.title)} × ${i.quantity}</li>`).join("")}</ul>
      <div class="meta">🕒 ${esc(o.pickup_time)} · оформлен в ${time} · ${money(o.total_amount)}</div>
      ${staff ? "" : `<div class="steps">${STATUS_ORDER.map((_, i) => `<span class="${i <= step ? "done" : ""}"></span>`).join("")}</div>`}
      <div class="actions">
        ${!staff && o.status !== "issued" ? `<button class="btn small" data-qr="${o.id}">Показать QR-код</button>` : ""}
        ${staff && next ? `<button class="btn small primary" data-next="${o.id}" data-status="${next}">→ ${STATUS_NAMES[next]}</button>` : ""}
      </div>
    </div>`;
}

let myOrders = [];
async function loadMyOrders() {
  myOrders = await api("/api/orders/my");
  $("#orders-list").innerHTML = myOrders.length
    ? myOrders.map((o) => orderCard(o)).join("")
    : `<p class="empty">Заказов пока нет</p>`;
  document.querySelectorAll("[data-qr]").forEach((b) =>
    b.addEventListener("click", () => showQr(myOrders.find((o) => o.id === Number(b.dataset.qr))))
  );
}

function showQr(order) {
  $("#qr-title").textContent = "Заказ №" + order.id;
  const box = $("#qr-box");
  box.innerHTML = "";
  const text = `CAMPUSEATS-ORDER-${order.id}`;
  // QR-код рисуется локальной библиотекой qrcode.js (без интернета)
  const qr = qrcode(0, "M");
  qr.addData(text);
  qr.make();
  box.innerHTML = qr.createSvgTag({ cellSize: 6, margin: 2 });
  $("#qr-modal").classList.remove("hidden");
}
$("#qr-close").addEventListener("click", () => $("#qr-modal").classList.add("hidden"));

// ---------- Кухня ----------

async function loadKitchen() {
  const orders = await api("/api/orders");
  $("#kitchen-list").innerHTML = orders.length
    ? orders.map((o) => orderCard(o, true)).join("")
    : `<p class="empty">Активных заказов нет</p>`;
  document.querySelectorAll("[data-next]").forEach((b) =>
    b.addEventListener("click", async () => {
      await api(`/api/orders/${b.dataset.next}/status`, { method: "PATCH", body: { status: b.dataset.status } });
      toast(`Заказ №${b.dataset.next}: ${STATUS_NAMES[b.dataset.status]}`);
      loadKitchen();
    })
  );
}

// ---------- Управление (админ) ----------

async function loadAdmin() {
  state.dishes = await api("/api/dishes");
  $("#cat-list").innerHTML = [...new Set(state.dishes.map((d) => d.category))].map((c) => `<option value="${esc(c)}">`).join("");
  $("#admin-dishes").innerHTML = state.dishes.map((d) => `
    <div class="admin-row">
      <div>${esc(d.title)}<small>${esc(d.category)}</small></div>
      <input type="number" min="1" value="${d.price}" data-price="${d.id}" title="Цена, ₸">
      <label class="toggle"><input type="checkbox" data-avail="${d.id}" ${d.is_available ? "checked" : ""}> в наличии</label>
    </div>`).join("");
  document.querySelectorAll("[data-price]").forEach((inp) => inp.addEventListener("change", async () => {
    await api("/api/dishes/" + inp.dataset.price, { method: "PATCH", body: { price: Number(inp.value) } });
    toast("Цена обновлена");
  }));
  document.querySelectorAll("[data-avail]").forEach((cb) => cb.addEventListener("change", async () => {
    await api("/api/dishes/" + cb.dataset.avail, { method: "PATCH", body: { is_available: cb.checked } });
    toast(cb.checked ? "Блюдо снова в наличии" : "Блюдо отмечено как закончившееся");
  }));
}

$("#topup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    const u = await api("/api/admin/topup", { method: "POST", body: { email: f.get("email"), amount: Number(f.get("amount")) } });
    $("#topup-msg").textContent = `Готово: баланс ${u.name} — ${money(u.balance)}`;
    e.target.reset();
    if (u.id === state.user.id) refreshUser();
  } catch (err) {
    $("#topup-msg").textContent = err.message;
  }
});

$("#dish-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api("/api/dishes", { method: "POST", body: { title: f.get("title"), price: Number(f.get("price")), category: f.get("category") } });
    e.target.reset();
    toast("Блюдо добавлено");
    loadAdmin();
  } catch (err) {
    toast(err.message);
  }
});

// ---------- Старт ----------

(async function init() {
  if (state.token) {
    try { await startApp(); return; } catch { logout(); }
  }
  $("#auth-screen").classList.remove("hidden");
})();

/* Miste — тема оформления Webordo.
   Блюда и цены приходят из базы, корзина живёт на сервере (та же сессионная
   корзина, что у стандартной витрины), поэтому заказ доходит до кабинета,
   Telegram и отчётов. Клик отрисовывается сразу, ответ сервера уточняет цифры. */

const $ = s => document.querySelector(s);
const MENU = MISTE.menu;
const qty = {};
let cartTotal = 0;

const fmt = n => n.toLocaleString('ru-RU').replace(/ /g, ' ') + ' ' + MISTE.cur;

/* ── кнопка «в корзину» / счётчик ── */
function buyHTML(it) {
  const q = qty[it.id] || 0;
  return q
    ? `<div class="step"><button data-dec="${it.id}" aria-label="${MISTE.i18n.dec}">−</button>`
      + `<span>${q}</span><button data-inc="${it.id}" aria-label="${MISTE.i18n.inc}">+</button></div>`
    : `<button class="add" data-inc="${it.id}">${MISTE.i18n.add}</button>`;
}

function render() {
  const host = $('#sections');
  host.innerHTML = MISTE.cats.map(c => {
    const rows = MENU.filter(m => m.cat === c.id);
    if (!rows.length) return '';
    return `<section class="sec" id="sec-${c.id}">
      <div class="sec-head"><h2>${c.name}</h2><span>${rows.length}</span></div>
      <div class="grid">${rows.map(cardHTML).join('')}</div>
    </section>`;
  }).join('');
}

function cardHTML(it) {
  const pic = it.img
    ? `<div class="card-pic"><img src="${it.img}" alt="${it.name}" loading="lazy"></div>`
    : `<div class="card-pic empty">${it.name}</div>`;
  return `<article class="card" data-id="${it.id}">
    ${pic}
    <div class="card-body">
      <h3>${it.name}</h3>
      ${it.desc ? `<p>${it.desc}</p>` : '<p></p>'}
      <div class="card-buy">
        <div class="price">${it.price}<small>${MISTE.cur}</small></div>
        <div class="ctl">${buyHTML(it)}</div>
      </div>
    </div>
  </article>`;
}

function refresh(id) {
  const el = document.querySelector(`.card[data-id="${id}"] .ctl`);
  const it = MENU.find(m => m.id == id);
  if (el && it) el.innerHTML = buyHTML(it);
}

/* ── обмен с сервером ── */
function post(url, data) {
  const body = new URLSearchParams(data);
  body.append('csrfmiddlewaretoken', MISTE.csrf);
  return fetch(url, {
    method: 'POST',
    headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': MISTE.csrf,
              'Content-Type': 'application/x-www-form-urlencoded'},
    body, credentials: 'same-origin'
  }).then(r => r.ok ? r.json() : Promise.reject(r.status));
}
const updateUrl = id => MISTE.urls.update.replace(/0\/$/, id + '/');

/* Запросы к одной позиции выстраиваем в очередь: два быстрых клика иначе
   уходят параллельно и сервер отвечает в произвольном порядке. */
let chain = Promise.resolve();
function sync(id) {
  const want = qty[id] || 0;
  chain = chain.then(() => post(updateUrl(id), {qty: want})).then(pull).catch(() => {});
}

function pull() {
  return fetch(MISTE.urls.cart, {headers: {'X-Requested-With': 'XMLHttpRequest'},
                                 credentials: 'same-origin'})
    .then(r => r.json())
    .then(d => {
      const rows = d.items || [];
      Object.keys(qty).forEach(k => delete qty[k]);
      rows.forEach(r => { qty[r.bi_id] = r.qty; });
      cartTotal = rows.reduce((s, r) => s + parseFloat(r.line_total || 0), 0);
      MENU.forEach(m => refresh(m.id));
      bar();
    })
    .catch(() => {});
}

function change(id, d) {
  qty[id] = Math.max(0, (qty[id] || 0) + d);
  if (!qty[id]) delete qty[id];
  refresh(id);
  bar();                       // сразу, не дожидаясь сервера
  sync(id);
}

document.addEventListener('click', e => {
  const inc = e.target.closest('[data-inc]'), dec = e.target.closest('[data-dec]');
  if (inc) change(inc.dataset.inc, 1);
  if (dec) change(dec.dataset.dec, -1);
});

/* ── нижняя панель ── */
function bar() {
  const list = Object.entries(qty).map(([id, q]) => {
    const m = MENU.find(x => x.id == id); return m ? {...m, q} : null;
  }).filter(Boolean);
  const count = list.reduce((s, x) => s + x.q, 0);
  const sum = cartTotal || list.reduce((s, x) => s + x.q * x.price, 0);
  $('#bar').classList.toggle('on', count > 0);
  $('#bar-total').textContent = fmt(sum);
  $('#bar-count').textContent = count + ' ' + MISTE.i18n.items;
}

/* ── лента разделов: подсветка активного ── */
function initTabs() {
  const tabs = [...document.querySelectorAll('.tabs a')];
  const secs = tabs.map(t => document.querySelector(t.getAttribute('href'))).filter(Boolean);
  if (!('IntersectionObserver' in window) || !secs.length) return;
  const io = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (!en.isIntersecting) return;
      const id = '#' + en.target.id;
      tabs.forEach(t => t.classList.toggle('on', t.getAttribute('href') === id));
      const act = tabs.find(t => t.classList.contains('on'));
      if (act) act.scrollIntoView({inline: 'center', block: 'nearest', behavior: 'smooth'});
    });
  }, {rootMargin: '-130px 0px -70% 0px'});
  secs.forEach(s => io.observe(s));
}

render();
initTabs();
pull();        // подтягиваем корзину, если гость уже что-то клал

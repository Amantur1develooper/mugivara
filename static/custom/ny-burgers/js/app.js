/* NY Burgers — тема оформления Webordo.
   Анимация — из исходного сайта; меню и корзина работают на Webordo. */

const $=s=>document.querySelector(s);
const fmt=n=>n.toLocaleString("ru-RU").replace(/ /g," ")+" "+NYB.cur;
const plural=(n,a,b,c)=>{const m=n%10,h=n%100;return m==1&&h!=11?a:m>=2&&m<=4&&(h<10||h>=20)?b:c};
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const sm=t=>{t=clamp(t);return t*t*(3-2*t)};
const lerp=(a,b,t)=>a+(b-a)*t;

/* ticker */
const tickTxt=(NYB.ticker||["Сочная говядина","Чеддер","Булочка бриошь","Osh \u00d7 NYC"]).map(t=>t+"<em>\u2605</em>").join("");
$("#tick").innerHTML=tickTxt.repeat(4);

/* ================= FILM ================= */
const stage=$("#stage"),film=$("#film");
// 3D-rendered ingredient layers, bottom → top. m=[crop top above layer base, crop height] in world units, th=stack thickness
const CF=Math.cos(17*Math.PI/180), FRAME=3.0, GAP=0.44, BUNW=2.25;
const ING=[
  {k:"botbun",m:[0.6239,0.9125],th:0.36,t:"Нижняя булочка"},
  {k:"signature",m:[0.3096,0.5969],th:0.03,t:"Фирменный соус"},
  {k:"onion",m:[0.2311,0.4188],th:0.06,t:"Красный лук"},
  {k:"tomato",m:[0.3569,0.5531],th:0.1,t:"Помидор"},
  {k:"patty1",m:[0.5442,0.8313],th:0.26,t:"Говяжья котлета"},
  {k:"cheese1",m:[0.3026,0.775],th:0.045,t:"Чеддер"},
  {k:"patty2",m:[0.5192,0.825],th:0.26,t:"Вторая котлета"},
  {k:"cheese2",m:[0.3026,0.8219],th:0.045,t:"Ещё чеддер"},
  {k:"bbq",m:[0.269,0.4656],th:0.03,t:"Соус барбекю"},
  {k:"pickles",m:[0.2284,0.4062],th:0.07,t:"Солёные огурцы"},
  {k:"cheesesauce",m:[0.3065,0.5563],th:0.03,t:"Сырный соус"},
  {k:"topbun",m:[0.8068,1.1094],th:0.78,t:"Булочка с кунжутом"}
];
const N=ING.length, cam=$("#cam");
let acc=0;
ING.forEach((L,i)=>{
  L.y=acc;acc+=L.th;
  const img=new Image();img.src=`${NYB.imgBase}ing/${L.k}.webp`;img.alt="";img.style.zIndex=i+1;cam.appendChild(img);L.el=img;
  const lb=document.createElement("div");lb.className="lbl";lb.innerHTML=`${L.t}<small>${String(N-i).padStart(2,"0")}</small>`;stage.appendChild(lb);L.lb=lb;
});
const TOP=ING[N-1],BOT=ING[0];
const botY=BOT.m[0]-BOT.m[1];
const topY=e=>(TOP.y+(N-1)*GAP*e)*CF+TOP.m[0];
const lc=(L,i,e)=>(L.y+i*GAP*e)*CF+L.m[0]-L.m[1]/2;

/* ---- 3D box ---- */
const box=$("#box3d");
box.innerHTML=`
  <div class="body3d" id="body3d">
    <div class="face f-bottom" data-f="bottom"></div>
    <div class="face f-back" data-f="back"></div>
    <div class="face f-side" data-f="left"></div>
    <div class="face f-side" data-f="right"></div>
    <div class="face f-front" data-f="front"><span>NY BURGERS · OSH</span></div>
    <div class="lid" id="lid">
      <div class="outer"><div class="boxlogo"><i>NY</i><b>NY BURGERS</b><small>EST. NEW YORK CITY</small></div></div>
      <div class="inner"><div class="boxlogo"><i>NY</i><b>NY BURGERS</b><small>ПРИЯТНОГО АППЕТИТА</small></div></div>
    </div>
  </div>`;
const ITEMS=[ // float position (x,y,z in box widths) → rest position inside the box; w = width in box widths
  {src:NYB.imgBase+"double.webp",  w:.40, f:[0,-.62,.05],   r:[-.2,-.13,.03]},
  {src:NYB.imgBase+"fries.webp",   w:.30, f:[-.52,-.5,-.1], r:[.08,-.16,-.12]},
  {src:NYB.imgBase+"sticks.webp",  w:.27, f:[.52,-.58,0],   r:[.3,-.11,.04]},
  {src:NYB.imgBase+"jalapeno.webp",w:.2,  f:[.3,-.25,.25],  r:[.02,-.04,.17]}
];
ITEMS.forEach(it=>{const d=document.createElement("div");d.className="item3d";d.innerHTML=`<div class="bob"><img src="${it.src}" alt=""></div>`;box.appendChild(d);it.el=d;});
const body3d=$("#body3d"),lid=$("#lid");
let B=400;
function layoutBox(){
  const W=innerWidth,H=innerHeight,mob=W<760;
  B=Math.min(560,mob?W*.86:W*.4,H*.62);
  box.style.setProperty("--B",B+"px");
  const D=B*.62,Hb=B*.3;
  const set=(el,w,h,t)=>{el.style.width=w+"px";el.style.height=h+"px";el.style.left=-w/2+"px";el.style.top=-h/2+"px";el.style.transform=t};
  box.querySelectorAll(".face").forEach(f=>{
    const k=f.dataset.f;
    if(k=="bottom")set(f,B,D,`translateY(${Hb/2}px) rotateX(90deg)`);
    if(k=="front") set(f,B,Hb,`translateZ(${D/2}px)`);
    if(k=="back")  set(f,B,Hb,`translateZ(${-D/2}px) rotateY(180deg)`);
    if(k=="left")  set(f,D,Hb,`translateX(${-B/2}px) rotateY(-90deg)`);
    if(k=="right") set(f,D,Hb,`translateX(${B/2}px) rotateY(90deg)`);
  });
  lid.style.width=B+"px";lid.style.height=D+"px";lid.style.left=-B/2+"px";lid.style.top="0px";lid.style.transformOrigin="50% 0";
  box._D=D;box._Hb=Hb;
}

/* ---- layout cache ---- */
let LY={};
function layout(){
  const W=innerWidth,H=stage.offsetHeight,mob=W<760;
  const photoW=mob?Math.min(W*.78,H*.36):Math.min(W*.4,H*.62);
  LY={W,H,mob,photoW,
    heroX:mob?W*.5:W*.67, heroY:mob?H*.70:H*.55,
    uAsm:photoW/BUNW,
    uExp:Math.min((mob?H*.7:H*.8)/(topY(1)-botY),(mob?W*.44:W*.28)/BUNW),
    expX:mob?W*.32:W*.6, expY:mob?H*.6:H*.53,
    boxX:mob?W*.5:W*.66, boxY:mob?H*.66:H*.58
  };
  const p=$("#paper");p.style.width=photoW*1.55+"px";p.style.height=photoW*1.0+"px";
  $("#photoBurger").style.width=photoW+"px";
  layoutBox();
}

const DARK=[15,12,11],LIGHT=[235,230,223],FGD=[244,230,207],FGL=[22,17,15];
const mix=(a,b,t)=>`rgb(${a.map((v,i)=>Math.round(lerp(v,b[i],t))).join(",")})`;
const show=(el,o,extra="")=>{el.style.opacity=o;el.style.visibility=o<=0.001?"hidden":"visible";if(extra)el.style.transform=extra};

function render(){
  const {W,H,mob,photoW,heroX,heroY,uAsm,uExp,expX,expY,boxX,boxY}=LY;
  const p=pCur;
  $("#prog").style.height=(p*100)+"%";

  /* timeline */
  const lift=sm((p-.04)/.12);            // burger leaves the paper
  const light=sm((p-.08)/.1)*(1-sm((p-.66)/.08));
  const cross=sm((p-.11)/.04);           // photo → 3D stack
  const ex=sm((p-.20)/.16)*(1-sm((p-.48)/.08));   // explode
  const combo=sm((p-.56)/.08);           // stack shrinks into combo
  const boxIn=sm((p-.64)/.08);
  const drop=sm((p-.71)/.08);
  const close=sm((p-.80)/.07);
  const outro=sm((p-.87)/.06);

  stage.style.background=mix(DARK,LIGHT,light);
  stage.style.setProperty("--fg",mix(FGD,FGL,light));
  $("#glow").style.opacity=1-light;
  $("#floor").style.opacity=1-light;

  // hero copy
  show($("#heroCopy"),1-sm((p-.02)/.07),`translateX(${-60*sm((p-.02)/.07)}px)`);
  show($("#scrollHint"),1-sm(p/.03));

  // paper: under the burger, falls away
  const paper=$("#paper"),pw=photoW*1.55,ph=photoW;
  show(paper,1-sm((p-.06)/.08),`translate(${heroX-pw/2}px,${heroY+photoW*.28-ph/2+lift*H*.35}px) rotateX(68deg) rotateZ(${-6+lift*8}deg)`);

  // burger centre path: hero → explode centre → box
  let cx=lerp(heroX,expX,mob?ex:lift), cy=lerp(heroY,expY,lift);
  cx=lerp(cx,boxX,combo); cy=lerp(cy,boxY-B*.57,combo);

  // photo burger (hero)
  const pb=$("#photoBurger"),phH=photoW*1008/1135;
  show(pb,1-cross,`translate(${cx-photoW/2}px,${cy-phH/2-lift*H*.04}px) rotate(${lift*-4}deg) scale(${1+lift*.06})`);

  // 3D stack
  const u=lerp(lerp(uAsm,uExp,ex),B*.4/BUNW,combo);
  const centre=(topY(ex)+botY)/2;
  const originY=cy+centre*u, w=FRAME*u;
  cam.style.opacity=cross*(1-sm((p-.6)/.03));
  cam.style.visibility=cam.style.opacity>0?"visible":"hidden";
  ING.forEach((L,i)=>{
    const sy=(L.y+i*GAP*ex)*CF;
    L.el.style.width=w+"px";
    const tilt=(i%2?1:-1)*ex*2.2;
    L.el.style.transform=`translate(${cx-w/2}px,${originY-(sy+L.m[0])*u}px) rotate(${tilt}deg)`;
    // labels
    const ly=originY-lc(L,i,ex)*u, lx=cx+u*1.12;
    const o=sm((ex-.75-(N-1-i)*.012)/.15);
    L.lb.style.setProperty("--lw",(mob?16:Math.max(30,u*.5))+"px");
    show(L.lb,o,`translate(${lx}px,${ly-9}px)`);
  });

  // big texts
  const a=sm((p-.31)/.05)*(1-sm((p-.46)/.05));
  show($("#bigA"),a,`translateY(${(1-a)*30}px)`);
  const b=sm((p-.55)/.05)*(1-sm((p-.68)/.04));
  show($("#bigB"),b,`translateY(${(1-b)*30}px)`);

  // 3D box scene
  const sc=$("#scene3d");
  const ry=lerp(-14,10,outro)+(mob?0:-6);
  sc.style.transform=`translate(${boxX}px,${boxY}px)`;
  box.style.transform=`rotateX(-24deg) rotateY(${ry}deg) scale(${lerp(1,1.04,outro)})`;
  body3d.style.transform=`translateY(${lerp(H*.9,0,boxIn)}px)`;
  const D=box._D,Hb=box._Hb;
  lid.style.transform=`translateY(${-Hb/2}px) translateZ(${-D/2}px) rotateX(${lerp(200,90,close)}deg)`;
  const itemsVis=sm((p-.6)/.03);
  const sink=1-sm((close-.25)/.45);
  ITEMS.forEach((it,k)=>{
    const s=sm((drop-k*.08)/.75);
    const x=lerp(it.f[0],it.r[0],s)*B, y=lerp(it.f[1],it.r[1],s)*B, z=lerp(it.f[2],it.r[2],s)*B;
    const iw=it.w*B;
    it.el.style.width=iw+"px";it.el.style.left=-iw/2+"px";it.el.style.top=-iw*.45+"px";
    // items enter from the sides before dropping
    const enter=k===0?1:sm((p-.57-k*.012)/.05);
    const ex2=(1-enter)*(it.f[0]<0?-1:1)*W*.6;
    it.el.style.transform=`translate3d(${x+ex2}px,${y}px,${z}px) rotateY(${-ry}deg) rotateX(24deg)`;
    it.el.style.opacity=(k===0?itemsVis:Math.min(itemsVis,enter))*sink;
    it.el.style.visibility=itemsVis>0?"visible":"hidden";
  });
  sc.style.visibility=itemsVis>0?"visible":"hidden";

  // combo copy
  const cc=$("#comboCopy");
  show(cc,outro,`translateY(${(1-outro)*30}px)`);
  cc.style.pointerEvents=outro>.9?"auto":"none";
}
// smooth, inertial scroll-scrubbing: the film eases toward the scroll position
let pCur=0,pT=0,raf=0;
const readT=()=>{const total=film.offsetHeight-innerHeight;pT=clamp(-film.getBoundingClientRect().top/total)};
function loop(){const d=pT-pCur;pCur=Math.abs(d)<.0002?pT:pCur+d*.085;render();raf=pCur!==pT?requestAnimationFrame(loop):0}
addEventListener("scroll",()=>{readT();if(!raf)raf=requestAnimationFrame(loop)},{passive:true});
addEventListener("resize",()=>{layout();readT();pCur=pT;render()});
$("#scrollBtn").addEventListener("click",e=>{e.preventDefault();scrollTo({top:film.offsetTop+(film.offsetHeight-innerHeight)*.42,behavior:"smooth"})});
layout();readT();pCur=pT;render();

/* ================= МЕНЮ + КОРЗИНА (данные и корзина — Webordo) =================
   Блюда, цены и фото приходят из базы (window.NYB.menu), корзина живёт на
   сервере: та же сессионная корзина, что и у стандартной витрины, поэтому
   заказ доходит до кабинета, Telegram и отчётов. Клик отрисовывается сразу
   (оптимистично), ответ сервера затем уточняет цифры.
================================================================================ */
const MENU = NYB.menu;
const qty = {};             // bi_id → количество
let cartTotal = 0;

const combo = MENU.find(m => m.old) || MENU[0];
if (combo) {
  $("#comboPrice").innerHTML = `${combo.price} ${NYB.cur}` + (combo.old ? `<s>${combo.old}</s>` : "");
}

let cat = "all";
const grid = $("#grid");

function buyHTML(it){
  const q = qty[it.id] || 0;
  return q
    ? `<div class="step"><button data-dec="${it.id}" aria-label="${NYB.i18n.dec}">−</button><span>${q}</span><button data-inc="${it.id}" aria-label="${NYB.i18n.inc}">+</button></div>`
    : `<button class="add" data-inc="${it.id}">${NYB.i18n.add}</button>`;
}
function priceHTML(it){
  // старая цена зачёркнута рядом с новой — как на карточке со скидкой
  return it.old
    ? `<div class="price">${it.price}<small>${NYB.cur}</small><s>${it.old}</s></div>`
    : `<div class="price">${it.price}<small>${NYB.cur}</small></div>`;
}
function renderMenu(){
  grid.innerHTML = MENU.filter(i => cat === "all" || i.cat === cat).map(it => `
    <article class="item${it.old ? " promo" : ""}" data-id="${it.id}">
      ${it.badge ? `<span class="badge">${it.badge}</span>` : ""}
      <div class="pic">${it.img ? `<img src="${it.img}" alt="${it.name}" loading="lazy">` : `<div class="noimg">${it.name}</div>`}</div>
      <div class="txt"><h3>${it.name}</h3><p>${it.desc || ""}</p></div>
      <div class="buy">${priceHTML(it)}<div class="ctl">${buyHTML(it)}</div></div>
    </article>`).join("");
  grid.querySelectorAll(".pic img").forEach(markCover);
}

/* Фото «вырезанное» из фона (с альфой) показываем целиком с воздухом вокруг,
   а обычный снимок со своим фоном — заполняя карточку. Отличаем по углам:
   у непрозрачного фото они непрозрачные. */
function markCover(img){
  const decide = () => {
    try{
      const c = document.createElement("canvas"), s = 24;
      c.width = c.height = s;
      const x = c.getContext("2d", {willReadFrequently:true});
      x.drawImage(img, 0, 0, s, s);
      const d = x.getImageData(0, 0, s, s).data;
      const at = (px, py) => d[(py * s + px) * 4 + 3];
      const corners = [at(0,0), at(s-1,0), at(0,s-1), at(s-1,s-1)];
      if(corners.every(a => a > 40)) img.parentElement.classList.add("cover");
    }catch(e){ /* canvas недоступен — оставляем вид по умолчанию */ }
  };
  if(img.complete && img.naturalWidth) decide();
  else img.addEventListener("load", decide, {once:true});
}
function refreshItem(id){
  const el = grid.querySelector(`[data-id="${id}"] .ctl`);
  const it = MENU.find(m => m.id == id);
  if (el && it) el.innerHTML = buyHTML(it);
}
$("#tabs").addEventListener("click", e => {
  const b = e.target.closest("button"); if(!b) return;
  cat = b.dataset.cat;
  document.querySelectorAll("#tabs button").forEach(x => x.setAttribute("aria-selected", x === b));
  renderMenu();
});

/* ---- полёт картинки в корзину ---- */
function bump(){ const cb = $("#cartBtn"); cb.classList.remove("bump"); void cb.offsetWidth; cb.classList.add("bump"); }
function fly(fromImg){
  if(!fromImg || matchMedia("(prefers-reduced-motion: reduce)").matches){ bump(); return; }
  const a = fromImg.getBoundingClientRect(), t = $("#cartBtn").getBoundingClientRect();
  const c = fromImg.cloneNode(); c.className = "fly";
  Object.assign(c.style,{left:a.left+"px",top:a.top+"px",width:a.width+"px",height:a.height+"px",objectFit:"contain"});
  document.body.appendChild(c);
  const dx = t.left+t.width/2-(a.left+a.width/2), dy = t.top+t.height/2-(a.top+a.height/2);
  c.animate([{transform:"translate(0,0) scale(1)"},
             {transform:`translate(${dx*.5}px,${dy*.5-80}px) scale(.5) rotate(-20deg)`,offset:.5},
             {transform:`translate(${dx}px,${dy}px) scale(.08) rotate(-40deg)`,opacity:.3}],
            {duration:700,easing:"cubic-bezier(.5,0,.6,1)"}).onfinish = () => { c.remove(); bump(); };
}

/* ---- обмен с сервером ---- */
function post(url, data){
  const body = new URLSearchParams(data);
  body.append("csrfmiddlewaretoken", NYB.csrf);
  return fetch(url, {
    method: "POST",
    headers: {"X-Requested-With":"XMLHttpRequest","X-CSRFToken":NYB.csrf,
              "Content-Type":"application/x-www-form-urlencoded"},
    body, credentials: "same-origin"
  }).then(r => r.ok ? r.json() : Promise.reject(r.status));
}
const addUrl    = id => NYB.urls.add.replace(/0\/$/, id + "/");
const updateUrl = id => NYB.urls.update.replace(/0\/$/, id + "/");

/* Запросы к одной позиции выстраиваем в очередь: иначе два быстрых клика
   уходят параллельно и сервер отвечает в произвольном порядке. */
let chain = Promise.resolve();
function sync(id){
  const want = qty[id] || 0;
  chain = chain
    .then(() => post(updateUrl(id), {qty: want}))
    .then(pullCart)
    .catch(() => {});
}
function pullCart(){
  return fetch(NYB.urls.cart, {headers:{"X-Requested-With":"XMLHttpRequest"}, credentials:"same-origin"})
    .then(r => r.json())
    .then(d => {
      const items = d.items || [];
      Object.keys(qty).forEach(k => delete qty[k]);
      items.forEach(r => { qty[r.bi_id] = r.qty; });
      cartTotal = items.reduce((s,r) => s + parseFloat(r.line_total || 0), 0);
      MENU.forEach(m => refreshItem(m.id));
      renderCart();
    })
    .catch(() => {});
}

function change(id, d, srcEl){
  qty[id] = Math.max(0, (qty[id] || 0) + d);
  if(!qty[id]) delete qty[id];
  refreshItem(id);
  renderCart();                 // сразу, не дожидаясь сервера
  if(d > 0) fly(srcEl);
  sync(id);
}
document.addEventListener("click", e => {
  const inc = e.target.closest("[data-inc]"), dec = e.target.closest("[data-dec]");
  if(inc){ const card = inc.closest(".item"); change(inc.dataset.inc, 1, card ? card.querySelector(".pic img") : null); }
  if(dec) change(dec.dataset.dec, -1);
});
const comboAdd = $("#comboAdd");
if(comboAdd && combo) comboAdd.addEventListener("click", () => change(combo.id, 1, ITEMS[0].el.querySelector("img")));

/* ---- выдвижная корзина ---- */
const drawer = $("#drawer"), scrim = $("#scrim");
const openD = () => { drawer.classList.add("on"); scrim.classList.add("on"); drawer.setAttribute("aria-hidden","false"); };
const closeD = () => { drawer.classList.remove("on"); scrim.classList.remove("on"); drawer.setAttribute("aria-hidden","true"); };
$("#cartBtn").onclick = openD; $("#barOpen").onclick = openD; $("#closeDrawer").onclick = closeD; scrim.onclick = closeD;
addEventListener("keydown", e => { if(e.key === "Escape") closeD(); });

function lines(){
  return Object.entries(qty)
    .map(([id,q]) => { const m = MENU.find(x => x.id == id); return m ? {...m, q} : null; })
    .filter(Boolean);
}
function renderCart(){
  const L = lines();
  const count = L.reduce((s,x) => s + x.q, 0);
  const sum   = cartTotal || L.reduce((s,x) => s + x.q * x.price, 0);
  $("#cartCount").textContent = count;
  $("#barTotal").textContent  = fmt(sum);
  $("#barCount").textContent  = count + " " + NYB.i18n.items;
  $("#bar").classList.toggle("show", count > 0);
  $("#total").textContent = fmt(sum);
  $("#lines").innerHTML = L.length ? L.map(x => `
    <div class="line-item">${x.img ? `<img src="${x.img}" alt="">` : ""}<div><div class="nm">${x.name}</div>
    <div class="pr">${x.price} × ${x.q} = ${fmt(x.price*x.q)}</div></div>
    <div class="step"><button data-dec="${x.id}" aria-label="${NYB.i18n.dec}">−</button><span>${x.q}</span><button data-inc="${x.id}" aria-label="${NYB.i18n.inc}">+</button></div></div>`).join("")
    : `<div class="empty">${NYB.i18n.empty}<br>${NYB.i18n.emptyHi}</div>`;

  updateSend(L.length);
}

/* ---- готовность формы: те же требования, что проверяет сервер ---- */
const isDelivery = () => { const d = $("#mDel"); return d ? d.checked : false; };
function updateSend(hasLines){
  if(hasLines === undefined) hasLines = Object.keys(qty).length > 0;
  const addrField = $("#fAddr");
  if(addrField) addrField.hidden = !isDelivery();

  const name  = ($("#name")  || {}).value || "";
  const phone = ($("#phone") || {}).value || "";
  const addr  = ($("#addr")  || {}).value || "";
  const phoneOk = phone.replace(/\D/g, "").length >= 9;
  const addrOk  = !isDelivery() || addr.trim().length > 0;
  const ok = hasLines && name.trim() && phoneOk && addrOk;

  const send = $("#send");
  send.disabled = !ok;
  send.setAttribute("aria-disabled", ok ? "false" : "true");
  $("#hint").textContent = !hasLines ? NYB.i18n.hintEmpty
                         : ok        ? NYB.i18n.hintOk
                         : (!addrOk && name.trim() && phoneOk) ? NYB.i18n.hintAddr
                         : NYB.i18n.hintFill;
}
const form = $("#orderForm");
if(form){
  form.addEventListener("input",  () => updateSend());
  form.addEventListener("change", () => updateSend());
}

renderMenu();
pullCart();          // подтягиваем корзину, если гость уже что-то клал

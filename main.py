# ============================================================
#  OBUNALAR HUB | BOT — main.py
#  aiogram 3.30+ / Bot API 10.2
#  Dizayn: rangli tugmalar (primary/success/danger) + premium emoji
# ============================================================
import asyncio, logging, os, re, aiohttp, aiosqlite
from contextlib import suppress
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (Message, CallbackQuery,
                           InlineKeyboardButton as IKB, InlineKeyboardMarkup as IKM,
                           KeyboardButton as KB, ReplyKeyboardMarkup as RKM)

# ================== SOZLAMALAR (ENV) ==================
BOT_TOKEN    = os.getenv("BOT_TOKEN", "8669054173:AAGrCaUidTFAlxd1PKHTIc2xPlEf_AjPZrc")
# ADMIN_ID o'rniga ADMINS ro'yxati (kelajakda bir necha kishi admin bo'lishi uchun)
ADMINS       = [int(x.strip()) for x in os.getenv("ADMINS", "5700159922").split(",") if x.strip()]
CARD_NUMBER  = os.getenv("CARD_NUMBER", "5614 6867 0900 3860")
CARD_OWNER   = os.getenv("CARD_OWNER", "ZAYNIDDIN SHODEYEV")
GEMINI_KEY   = os.getenv("GEMINI_KEY", "AQ.Ab8RN6JwNyNSvtYRxvMxbeOfZt7rOCRd9ti923RubWVl3rMIaA")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
CHANNELS     = [c.strip() for c in os.getenv("CHANNELS", "@obunahub_rasmiy,@obunalarhub_guruh").split(",") if c.strip()]
SUPPORT      = os.getenv("SUPPORT", "@XushvaqtovSh")
DB_PATH      = os.getenv("DB_PATH", "obunahub_v3.db")
PORT         = int(os.getenv("PORT", "8080"))
PREMIUM_UI   = os.getenv("PREMIUM_UI", "1") == "1"   # premium emoji ikonkalar
USE_EFFECTS  = os.getenv("EFFECTS", "1") == "1"      # xabar effektlari

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("hub")

# ================== EMOJI PALITRASI ==================
E = {
    # --- interfeys ---
    "hello":   ("5462910521739063094", "👋"),
    "shop":    ("5332586662629227075", "🗂"),
    "cart":    ("5278758318544801385", "👛"),
    "profile": ("6224373378250182099", "😎"),
    "orders":  ("5264713049637409446", "🪙"),
    "ai":      ("5431644246450908867", "🔍"),
    "lang":    ("6219745168736653594", "🌐"),
    "support": ("5915814406490427591", "🔔"),
    "admin":   ("5287388737498529298", "🚨"),
    "pay":     ("5445353829304387411", "💳"),
    "money":   ("5292006737874792240", "💵"),
    "ok":      ("5273806972871787310", "✅"),
    "no":      ("5271934564699226262", "❌"),
    "back":    ("5366486221021264181", "⭐️"),
    "trash":   ("5462882007451185227", "🚫"),
    "sold":    ("5240241223632954241", "🚫"),
    "fire":    ("5420315771991497307", "🔥"),
    "shield":  ("5382350120815713040", "🛡"),
    "arrow":   ("5976614478928679990", "➡️"),
    "warn":    ("6305243923056954377", "❕"),
    "party":   ("5461151367559141950", "🎉"),
    "bolt":    ("6267107057304868214", "⚡️"),
    "link":    ("5332755643822520488", "🔗"),
    "gem":     ("6264791387032523779", "💎"),

    # --- kategoriyalar ---
    "Gemini Ai":    ("5452138632091569963", "✨"),
    "Claud Ai":     ("6174520215376763867", "✴️"),
    "ChatGpt":      ("5303113132460250222", "💬"),
    "Supper Grok":  ("6179337489350663129", "🚀"),
    "Flow Ai":      ("6178962311072456422", "🌊"),
    "CapCut":       ("5978895591894161700", "📹"),
    "Leoanardo Ai": ("6133975818591805751", "💎"),
}

FX = {"party": "5046509860389126442", "fire": "5104841245755180586",
      "like": "5107584321108051014", "heart": "5159385139981059251"}

def fx(name):
    return FX.get(name) if USE_EFFECTS else None

def fb(key):
    return E[key][1] if key in E else "•"

def tg(key):
    if key not in E: return ""
    _id, alt = E[key]
    return f'<tg-emoji emoji-id="{_id}">{alt}</tg-emoji>' if PREMIUM_UI else alt

# ================== TUGMA KONSTRUKTORLARI ==================
def B(text, key=None, style="primary", icon_id=None, alt=None, **kw):
    icon = icon_id or (E[key][0] if key in E else None)
    label = text
    if PREMIUM_UI and icon:
        kw["icon_custom_emoji_id"] = icon
    else:
        pref = alt or (fb(key) if key in E else "")
        label = f"{pref} {text}".strip()
    if style: kw["style"] = style
    try:
        return IKB(text=label, **kw)
    except Exception:
        kw.pop("style", None); kw.pop("icon_custom_emoji_id", None)
        return IKB(text=f"{alt or fb(key)} {text}".strip() if key in E else text, **kw)

def RB(text, key=None, style="primary"):
    kw = {}
    label = text
    if PREMIUM_UI and key in E:
        kw["icon_custom_emoji_id"] = E[key][0]
    elif key in E:
        label = f"{fb(key)} {text}"
    if style: kw["style"] = style
    try:
        return KB(text=label, **kw)
    except Exception:
        return KB(text=f"{fb(key)} {text}" if key in E else text)

def norm(s):
    return re.sub(r"^[^\w\u0400-\u04FF]+", "", (s or "")).strip().lower()

# ================== TARJIMALAR ==================
MENU = {
    "srv":  ("Xizmatlar",     "Услуги",     "shop"),
    "cart": ("Savat",         "Корзина",    "cart"),
    "prof": ("Profil",        "Профиль",    "profile"),
    "ord":  ("Buyurtmalarim", "Мои заказы", "orders"),
    "ai":   ("AI yordamchi",  "AI помощник","ai"),
    "lang": ("Til",           "Язык",       "lang"),
    "help": ("Aloqa",         "Связь",      "support"),
}
BTN_ANY = {k: {norm(v[0]), norm(v[1])} for k, v in MENU.items()}
ADMIN_BTN = "Admin panel"

T = {
 "uz": {
  "start": "{h} <b>Assalomu alaykum, {n}!</b>\n\nOBUNALAR HUB — eng arzon AI obunalar do'koni.\nQuyidagi menyudan kerakli bo'limni tanlang.",
  "cats": "{i} <b>Bo'limni tanlang</b>\nSizga kerakli AI xizmatini tanlang:",
  "prods": "{i} <b>{c}</b>\nMahsulotni tanlang:",
  "empty": "Hozircha bo'sh.",
  "cart_empty": "{i} <b>Savatingiz bo'sh</b>\nXizmatlar bo'limidan mahsulot qo'shing.",
  "cart_t": "{i} <b>Savat</b>",
  "sub": "{i} <b>Diqqat!</b>\nBotdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
  "sub_ok": "Obuna tasdiqlandi!",
  "sub_no": "Hali barcha kanallarga obuna bo'lmadingiz.",
  "pay": "{i} <b>To'lov</b>\n\n{m} Summa: <b>{p:,} so'm</b>\n{c_i} Karta: <code>{c}</code>\n{o_i} Egasi: <b>{o}</b>\n\n{w} To'lovdan so'ng <b>chek rasmini</b> shu yerga yuboring.",
  "recv": "{i} <b>Chek qabul qilindi!</b>\nAdmin tekshirmoqda, iltimos kuting.",
  "need_photo": "{i} Iltimos, chekni <b>rasm</b> ko'rinishida yuboring.",
  "cancel": "Bekor qilindi.",
  "added": "Savatga qo'shildi!",
  "prof": "{i} <b>Profil</b>\n\n{id_i} ID: <code>{id}</code>\nIsm: <b>{n}</b>\nDaraja: <b>{lv}</b>\nBuyurtmalar: <b>{c}</b>\n{m} Sarflangan: <b>{s:,} so'm</b>",
  "ord_t": "{i} <b>Buyurtmalarim</b>",
  "lang_q": "{i} <b>Tilni tanlang</b>",
  "help": "{i} <b>Aloqa</b>\n\nSavollaringiz bo'lsa admin bilan bog'laning: {s}",
  "ai_on": "{i} <b>AI yordamchi yoqildi</b>\nSavolingizni yozing. Chiqish uchun /cancel",
  "no_ai": "AI hozircha ishlamayapti.",
  "wait": "O'ylayapman...",
  "sold": "Bu mahsulot tugagan.",
 },
 "ru": {
  "start": "{h} <b>Здравствуйте, {n}!</b>\n\nOBUNALAR HUB — магазин AI-подписок.\nВыберите раздел из меню ниже.",
  "cats": "{i} <b>Выберите раздел</b>\nВыберите нужный AI-сервис:",
  "prods": "{i} <b>{c}</b>\nВыберите товар:",
  "empty": "Пока пусто.",
  "cart_empty": "{i} <b>Корзина пуста</b>\nДобавьте товар из раздела «Услуги».",
  "cart_t": "{i} <b>Корзина</b>",
  "sub": "{i} <b>Внимание!</b>\nПодпишитесь на каналы:",
  "sub_ok": "Подписка подтверждена!",
  "sub_no": "Вы подписались не на все каналы.",
  "pay": "{i} <b>Оплата</b>\n\n{m} Сумма: <b>{p:,} сум</b>\n{c_i} Карта: <code>{c}</code>\n{o_i} Владелец: <b>{o}</b>\n\n{w} После оплаты отправьте <b>фото чека</b>.",
  "recv": "{i} <b>Чек принят!</b>\nАдмин проверяет, подождите.",
  "need_photo": "{i} Отправьте чек <b>картинкой</b>.",
  "cancel": "Отменено.",
  "added": "Добавлено в корзину!",
  "prof": "{i} <b>Профиль</b>\n\n{id_i} ID: <code>{id}</code>\nИмя: <b>{n}</b>\nУровень: <b>{lv}</b>\nЗаказов: <b>{c}</b>\n{m} Потрачено: <b>{s:,} сум</b>",
  "ord_t": "{i} <b>Мои заказы</b>",
  "lang_q": "{i} <b>Выберите язык</b>",
  "help": "{i} <b>Связь</b>\n\nПо всем вопросам: {s}",
  "ai_on": "{i} <b>AI-помощник включён</b>\nНапишите вопрос. Выход: /cancel",
  "no_ai": "AI сейчас недоступен.",
  "wait": "Думаю...",
  "sold": "Товар закончился.",
 },
}

def t(lang, key, **kw):
    return T.get(lang, T["uz"]).get(key, key).format(**kw)

def quote(text):
    return f"<blockquote>{text}</blockquote>"

# ================== BAZA ==================
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT, lang TEXT DEFAULT 'uz',
  orders INTEGER DEFAULT 0, spent INTEGER DEFAULT 0,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS cats(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE,
  icon TEXT, alt TEXT DEFAULT '•', pos INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS prods(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cat INTEGER, name TEXT,
  price INTEGER, stock INTEGER DEFAULT 0, info TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS cart(uid INTEGER, pid INTEGER);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, total INTEGER,
  title TEXT, status TEXT DEFAULT 'new', receipt TEXT,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS order_items(oid INTEGER, pid INTEGER, price INTEGER);
"""
DB: aiosqlite.Connection = None

async def q(sql, args=(), fetch=None):
    cur = await DB.execute(sql, args)
    if fetch == "one":
        r = await cur.fetchone()
    elif fetch == "all":
        r = await cur.fetchall()
    else:
        r = cur.lastrowid
    await DB.commit()
    await cur.close()
    return r

async def init_db():
    global DB
    DB = await aiosqlite.connect(DB_PATH)
    DB.row_factory = aiosqlite.Row
    await DB.executescript(SCHEMA)
    await DB.commit()

    if (await q("SELECT COUNT(*) c FROM cats", (), "one"))["c"]:
        return

    cats = ["Gemini Ai", "Claud Ai", "ChatGpt", "Supper Grok",
            "Flow Ai", "CapCut", "Leoanardo Ai"]
    ids = {}
    for i, name in enumerate(cats):
        ids[name] = await q(
            "INSERT INTO cats(name,icon,alt,pos) VALUES(?,?,?,?)",
            (name, E.get(name, ("", ""))[0], fb(name), i))

    seed = [
      ("Gemini Ai", "Gemini Ai Pro (18 oylik)", 40000, 100,
       "Obunani faollashtirish uchun linkni nusxalang. Google akkauntingizga kirib, qidiruvga o'sha linkni joylang va \"Get started\" tugmasini bosing.\n\nEslatma: link 12 soat davomida amal qiladi."),
      ("Claud Ai", "Claude Pro (1 oylik)", 165000, 100,
       "25 kunlik to'liq kafolat.\nMuammo chiqsa bir zumda almashtiriladi.\nBank kartasi shart emas.\nHavolani bosasiz — obuna bir necha soniyada ishga tushadi."),
      ("ChatGpt", "ChatGPT Plus (1 oylik)", 100000, 100,
       "To'liq kafolat.\nBloklanish xavfi yo'q.\nBarqaror va tez ishlaydigan tayyor akkaunt."),
      ("CapCut", "CapCut PRO (7 kunlik)", 15000, 100, "7 kunlik to'liq kafolat."),
      ("CapCut", "CapCut PRO (30 kunlik)", 42000, 100, "30 kunlik to'liq kafolat."),
      ("CapCut", "CapCut PRO (3 oylik)", 132000, 100, "3 oylik to'liq kafolat."),
      ("CapCut", "CapCut PRO (6 oylik)", 210000, 100, "6 oylik to'liq kafolat."),
      ("CapCut", "CapCut PRO (1 yillik)", 370000, 100, "1 yillik to'liq kafolat."),
      ("Leoanardo Ai", "Leonardo Ai — 8500 kredit", 50000, 100, "1 oylik obuna, 8500 kredit beriladi."),
    ]
    for cname, name, price, stock, info in seed:
        await q("INSERT INTO prods(cat,name,price,stock,info) VALUES(?,?,?,?,?)",
                (ids[cname], name, price, stock, info))
    log.info("Boshlang'ich ma'lumotlar yuklandi")

async def get_user(src):
    uid, name = src.from_user.id, src.from_user.full_name
    u = await q("SELECT * FROM users WHERE id=?", (uid,), "one")
    if not u:
        await q("INSERT INTO users(id,name) VALUES(?,?)", (uid, name))
        u = await q("SELECT * FROM users WHERE id=?", (uid,), "one")
    return u

def level_of(n):
    return "🥉 Bronza" if n < 3 else ("🥈 Kumush" if n < 10 else "🥇 Oltin")

# ================== KLAVIATURALAR ==================
def main_menu(lang="uz", admin=False):
    i = 0 if lang == "uz" else 1
    rows = [
        [RB(MENU["srv"][i],  MENU["srv"][2],  "success"),
         RB(MENU["cart"][i], MENU["cart"][2], "primary")],
        [RB(MENU["prof"][i], MENU["prof"][2], "primary"),
         RB(MENU["ord"][i],  MENU["ord"][2],  "primary")],
        [RB(MENU["ai"][i],   MENU["ai"][2],   "primary"),
         RB(MENU["lang"][i], MENU["lang"][2], "primary")],
        [RB(MENU["help"][i], MENU["help"][2], "primary")],
    ]
    if admin:
        rows.append([RB(ADMIN_BTN, "admin", "danger")])
    return RKM(keyboard=rows, resize_keyboard=True, is_persistent=True)

def lang_kb():
    return IKM(inline_keyboard=[[
        IKB(text="🇺🇿 O'zbekcha", callback_data="lang:uz", style="primary"),
        IKB(text="🇷🇺 Русский",   callback_data="lang:ru", style="primary")]])

async def cats_kb():
    rows, buf = [], []
    for c in await q("SELECT * FROM cats ORDER BY pos, id", (), "all"):
        left = (await q("SELECT COALESCE(SUM(stock),0) s FROM prods WHERE cat=?", (c["id"],), "one"))["s"]
        buf.append(B(c["name"], icon_id=c["icon"] or None, alt=c["alt"],
                     style="success" if left > 0 else "danger",
                     callback_data=f"cat:{c['id']}"))
        if len(buf) == 2:
            rows.append(buf); buf = []
    if buf: rows.append(buf)
    return IKM(inline_keyboard=rows or [[B("Bo'sh", "warn", "danger", callback_data="nop")]])

async def prods_kb(cid):
    c = await q("SELECT * FROM cats WHERE id=?", (cid,), "one")
    rows = []
    for p in await q("SELECT * FROM prods WHERE cat=? ORDER BY price", (cid,), "all"):
        sold = p["stock"] <= 0
        label = f"{p['name']} — {p['price']:,} so'm"
        rows.append([B(label,
                       icon_id=(E["sold"][0] if sold else (c["icon"] or None)),
                       alt=("🚫" if sold else c["alt"]),
                       style="danger" if sold else "success",
                       callback_data=("nop" if sold else f"prod:{p['id']}"))])
    rows.append([B("Ortga", "back", "primary", callback_data="cats")])
    return IKM(inline_keyboard=rows)

def prod_kb(pid, cid, sold=False):
    if sold:
        return IKM(inline_keyboard=[
            [B("Tugagan", "sold", "danger", callback_data="nop")],
            [B("Ortga", "back", "primary", callback_data=f"cat:{cid}")]])
    return IKM(inline_keyboard=[
        [B("Sotib olish", "pay", "success", callback_data=f"buy:{pid}")],
        [B("Savatga", "cart", "primary", callback_data=f"add:{pid}"),
         B("Ortga",   "back", "primary", callback_data=f"cat:{cid}")]])

def order_kb(oid):
    return IKM(inline_keyboard=[[
        B("Tasdiqlash", "ok", "success", callback_data=f"ok:{oid}"),
        B("Rad etish",  "no", "danger",  callback_data=f"no:{oid}")]])

def subs_kb():
    rows = [[B(ch, "link", "primary", url=f"https://t.me/{ch.lstrip('@')}")] for ch in CHANNELS]
    rows.append([B("Tekshirish", "ok", "success", callback_data="chk")])
    return IKM(inline_keyboard=rows)

def admin_kb():
    return IKM(inline_keyboard=[
        [B("To'liq Analitika", "money", "success", callback_data="a:stat")],
        [B("Bo'lim qo'shish", "ok", "primary", callback_data="a:cat"),
         B("Bo'lim tahrirlash", "gem", "primary", callback_data="a:editcat")],
        [B("Mahsulot qo'shish", "ok", "primary", callback_data="a:prod"),
         B("Mahsulot tahrirlash", "gem", "primary", callback_data="a:editprod")],
        [B("Bo'lim o'chirish", "trash", "danger", callback_data="a:delcat"),
         B("Mahsulot o'chirish", "trash", "danger", callback_data="a:delprod")],
        [B("Reklama yuborish", "bolt", "success", callback_data="a:ads")]])

# ================== HOLATLAR ==================
class Buy(StatesGroup):
    receipt = State()

class AI(StatesGroup):
    chat = State()

class Adm(StatesGroup):
    cat = State(); editcat = State(); delcat = State()
    prod = State(); editprod = State(); delprod = State()
    ads = State(); give = State(); emoji = State()

router = Router()
# ================== YORDAMCHILAR ==================
async def missing_subs(bot: Bot, uid: int):
    out = []
    for ch in CHANNELS:
        try:
            mem = await bot.get_chat_member(ch, uid)
            if mem.status in ("left", "kicked"):
                out.append(ch)
        except Exception as e:
            log.warning("Kanal tekshiruvi xato (%s): %s", ch, e)
    return out

async def safe_edit(msg: Message, text: str, kb=None):
    try:
        await msg.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        with suppress(Exception):
            await msg.answer(text, reply_markup=kb)

async def gemini(prompt: str) -> str:
    if not GEMINI_KEY: return ""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"}
    body = {
        "systemInstruction": {"parts": [{"text":
            "Sen OBUNALAR HUB do'konining yordamchisisan. Qisqa, do'stona va "
            "o'zbek tilida javob ber. Faqat AI obunalari, narxlar va "
            "foydalanish bo'yicha yordam ber."}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800},
    }
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.post(url, json=body, headers=headers) as r:
                data = await r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.error("Gemini xato: %s", e)
        return ""

def is_admin(uid): return uid in ADMINS

# ================== START / OBUNA ==================
@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext, bot: Bot):
    await state.clear()
    u = await get_user(m)
    if await missing_subs(bot, m.from_user.id):
        return await m.answer(quote(t(u["lang"], "sub", i=tg("warn"))),
                              reply_markup=subs_kb())
    await m.answer(
        quote(t(u["lang"], "start", h=tg("hello"), n=m.from_user.first_name)),
        reply_markup=main_menu(u["lang"], is_admin(m.from_user.id)),
        message_effect_id=fx("party"))

@router.callback_query(F.data == "chk")
async def check_sub(c: CallbackQuery, bot: Bot):
    u = await get_user(c)
    if await missing_subs(bot, c.from_user.id):
        return await c.answer(f"{fb('no')} " + t(u["lang"], "sub_no"), show_alert=True)
    await c.answer(f"{fb('ok')} " + t(u["lang"], "sub_ok"))
    with suppress(Exception):
        await c.message.delete()
    await c.message.answer(
        quote(t(u["lang"], "start", h=tg("hello"), n=c.from_user.first_name)),
        reply_markup=main_menu(u["lang"], is_admin(c.from_user.id)),
        message_effect_id=fx("party"))

@router.callback_query(F.data == "nop")
async def nop(c: CallbackQuery):
    u = await get_user(c)
    await c.answer(f"{fb('sold')} " + t(u["lang"], "sold"), show_alert=True)

@router.message(Command("cancel"))
async def cmd_cancel(m: Message, state: FSMContext):
    u = await get_user(m)
    await state.clear()
    await m.answer(f"{tg('no')} <b>{t(u['lang'], 'cancel')}</b>",
                   reply_markup=main_menu(u["lang"], is_admin(m.from_user.id)))

# ================== KATALOG (SPA — bitta xabar tahrirlanadi) ==================
@router.message(F.text.func(lambda s: norm(s) in BTN_ANY["srv"]))
async def services(m: Message):
    u = await get_user(m)
    await m.answer(quote(t(u["lang"], "cats", i=tg("shop"))),
                   reply_markup=await cats_kb())

@router.callback_query(F.data == "cats")
async def back_cats(c: CallbackQuery):
    u = await get_user(c)
    await safe_edit(c.message, quote(t(u["lang"], "cats", i=tg("shop"))),
                    await cats_kb())
    await c.answer()

@router.callback_query(F.data.startswith("cat:"))
async def open_cat(c: CallbackQuery):
    u = await get_user(c)
    cid = int(c.data.split(":")[1])
    cat = await q("SELECT * FROM cats WHERE id=?", (cid,), "one")
    if not cat:
        return await c.answer("Topilmadi", show_alert=True)
    await safe_edit(c.message,
                    quote(t(u["lang"], "prods", i=tg("shop"), c=cat["name"])),
                    await prods_kb(cid))
    await c.answer()

@router.callback_query(F.data.startswith("prod:"))
async def open_prod(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    p = await q("SELECT * FROM prods WHERE id=?", (pid,), "one")
    if not p:
        return await c.answer("Topilmadi", show_alert=True)
    cat = await q("SELECT * FROM cats WHERE id=?", (p["cat"],), "one")
    icon = (f'<tg-emoji emoji-id="{cat["icon"]}">{cat["alt"]}</tg-emoji>'
            if PREMIUM_UI and cat["icon"] else cat["alt"])
    sold = p["stock"] <= 0
    head = (f"{icon} <b>{p['name']}</b>\n\n"
            f"{tg('money')} Narx: <b>{p['price']:,} so'm</b>\n"
            f"{tg('ok') if not sold else tg('sold')} Holat: "
            f"<b>{'Mavjud' if not sold else 'Tugagan'}</b>")
    body = f"\n\n<blockquote expandable>{p['info']}</blockquote>" if p["info"] else ""
    await safe_edit(c.message, quote(head) + body, prod_kb(pid, p["cat"], sold))
    await c.answer()

# ================== SAVAT ==================
async def cart_view(uid, lang):
    rows = await q("""SELECT p.id,p.name,p.price FROM cart c
                      JOIN prods p ON p.id=c.pid WHERE c.uid=?""", (uid,), "all")
    if not rows:
        return quote(t(lang, "cart_empty", i=tg("cart"))), None
    total = sum(r["price"] for r in rows)
    lines = "\n".join(f"{tg('arrow')} {r['name']} — <b>{r['price']:,}</b>" for r in rows)
    txt = (quote(f"{tg('cart')} <b>Savat</b>\n\n{lines}\n\n"
                 f"{tg('money')} Jami: <b>{total:,} so'm</b>"))
    kb_rows = [[B(f"O'chirish: {r['name'][:20]}", "trash", "danger",
                  callback_data=f"cdel:{r['id']}")] for r in rows]
    kb_rows.insert(0, [B("Hammasini sotib olish", "pay", "success",
                         callback_data="buycart")])
    kb_rows.append([B("Savatni tozalash", "trash", "danger", callback_data="cclr")])
    return txt, IKM(inline_keyboard=kb_rows)

@router.message(F.text.func(lambda s: norm(s) in BTN_ANY["cart"]))
async def cart_show(m: Message):
    u = await get_user(m)
    txt, kb = await cart_view(m.from_user.id, u["lang"])
    await m.answer(txt, reply_markup=kb)

@router.callback_query(F.data.startswith("add:"))
async def cart_add(c: CallbackQuery):
    u = await get_user(c)
    pid = int(c.data.split(":")[1])
    p = await q("SELECT stock FROM prods WHERE id=?", (pid,), "one")
    if not p or p["stock"] <= 0:
        return await c.answer(f"{fb('sold')} " + t(u["lang"], "sold"), show_alert=True)
    await q("INSERT INTO cart(uid,pid) VALUES(?,?)", (c.from_user.id, pid))
    await c.answer(f"{fb('ok')} " + t(u["lang"], "added"), show_alert=True)

@router.callback_query(F.data.startswith("cdel:"))
async def cart_del(c: CallbackQuery):
    u = await get_user(c)
    pid = int(c.data.split(":")[1])
    await q("DELETE FROM cart WHERE rowid IN "
            "(SELECT rowid FROM cart WHERE uid=? AND pid=? LIMIT 1)",
            (c.from_user.id, pid))
    txt, kb = await cart_view(c.from_user.id, u["lang"])
    await safe_edit(c.message, txt, kb)
    await c.answer()

@router.callback_query(F.data == "cclr")
async def cart_clear(c: CallbackQuery):
    u = await get_user(c)
    await q("DELETE FROM cart WHERE uid=?", (c.from_user.id,))
    await safe_edit(c.message, quote(t(u["lang"], "cart_empty", i=tg("cart"))), None)
    await c.answer()

# ================== XARID ==================
async def start_order(msg: Message, uid: int, items, state: FSMContext):
    row = await q("SELECT lang FROM users WHERE id=?", (uid,), "one")
    lang = row["lang"] if row else "uz"
    total = sum(i[2] for i in items)
    title = ", ".join(i[1] for i in items)
    oid = await q("INSERT INTO orders(uid,total,title) VALUES(?,?,?)",
                  (uid, total, title))
    for pid, _, price in items:
        await q("INSERT INTO order_items(oid,pid,price) VALUES(?,?,?)",
                (oid, pid, price))
    await state.set_state(Buy.receipt)
    await state.update_data(oid=oid)
    await msg.answer(quote(t(lang, "pay", i=tg("pay"), m=tg("money"),
                             c_i=tg("gem"), o_i=tg("profile"), w=tg("warn"),
                             p=total, c=CARD_NUMBER, o=CARD_OWNER)))

@router.callback_query(F.data.startswith("buy:"))
async def buy_one(c: CallbackQuery, state: FSMContext):
    u = await get_user(c)
    pid = int(c.data.split(":")[1])
    p = await q("SELECT * FROM prods WHERE id=?", (pid,), "one")
    if not p or p["stock"] <= 0:
        return await c.answer(f"{fb('sold')} " + t(u["lang"], "sold"), show_alert=True)
    await c.answer()
    await start_order(c.message, c.from_user.id,
                      [(p["id"], p["name"], p["price"])], state)

@router.callback_query(F.data == "buycart")
async def buy_cart(c: CallbackQuery, state: FSMContext):
    u = await get_user(c)
    rows = await q("""SELECT p.id,p.name,p.price,p.stock FROM cart c
                      JOIN prods p ON p.id=c.pid WHERE c.uid=?""",
                   (c.from_user.id,), "all")
    items = [(r["id"], r["name"], r["price"]) for r in rows if r["stock"] > 0]
    if not items:
        return await c.answer(f"{fb('warn')} " + t(u["lang"], "cart_empty", i=""),
                              show_alert=True)
    await c.answer()
    await start_order(c.message, c.from_user.id, items, state)

@router.message(Buy.receipt, F.photo)
async def receipt(m: Message, state: FSMContext, bot: Bot):
    u = await get_user(m)
    data = await state.get_data()
    oid = data.get("oid")
    fid = m.photo[-1].file_id
    await q("UPDATE orders SET receipt=? WHERE id=?", (fid, oid))
    o = await q("SELECT * FROM orders WHERE id=?", (oid,), "one")
    await state.clear()
    await m.answer(quote(t(u["lang"], "recv", i=tg("ok"))),
                   reply_markup=main_menu(u["lang"], is_admin(m.from_user.id)))
    if ADMINS:
        cap = (f"{tg('warn')} <b>Yangi buyurtma #{oid}</b>\n\n"
               f"{tg('profile')} {m.from_user.full_name} "
               f"(<code>{m.from_user.id}</code>) @{m.from_user.username or '—'}\n"
               f"{tg('shop')} {o['title']}\n"
               f"{tg('money')} <b>{o['total']:,} so'm</b>")
        for adm in ADMINS:
            with suppress(Exception):
                await bot.send_photo(adm, fid, caption=quote(cap),
                                     reply_markup=order_kb(oid))

@router.message(Buy.receipt)
async def receipt_wrong(m: Message):
    u = await get_user(m)
    await m.answer(quote(t(u["lang"], "need_photo", i=tg("warn"))))

@router.callback_query(F.data.startswith(("ok:", "no:")))
async def moderate(c: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(c.from_user.id):
        return await c.answer("⛔️", show_alert=True)
    act, oid = c.data.split(":")
    oid = int(oid)
    o = await q("SELECT * FROM orders WHERE id=?", (oid,), "one")
    if not o or o["status"] != "new":
        return await c.answer("Bu buyurtma allaqachon ko'rib chiqilgan", show_alert=True)

    if act == "no":
        await q("UPDATE orders SET status='rej' WHERE id=?", (oid,))
        with suppress(Exception):
            await bot.send_message(o["uid"], quote(
                f"{tg('no')} <b>Buyurtma #{oid} rad etildi</b>\n\n"
                f"Sabab bo'yicha admin bilan bog'laning: {SUPPORT}"))
        await c.message.edit_caption(caption=quote(f"{tg('no')} <b>#{oid} rad etildi</b>"))
        return await c.answer()

    await q("UPDATE orders SET status='paid' WHERE id=?", (oid,))
    await q("UPDATE users SET orders=orders+1, spent=spent+? WHERE id=?",
            (o["total"], o["uid"]))
    for it in await q("SELECT pid FROM order_items WHERE oid=?", (oid,), "all"):
        await q("UPDATE prods SET stock=stock-1 WHERE id=? AND stock>0", (it["pid"],))
    await q("DELETE FROM cart WHERE uid=?", (o["uid"],))
    await state.set_state(Adm.give)
    await state.update_data(uid=o["uid"], oid=oid)
    await c.message.edit_caption(caption=quote(f"{tg('ok')} <b>#{oid} tasdiqlandi</b>"))
    await c.message.answer(quote(
        f"{tg('arrow')} <b>#{oid}</b> uchun akkaunt / havolani yuboring:"))
    await c.answer()

@router.message(Adm.give)
async def deliver(m: Message, state: FSMContext, bot: Bot):
    if not is_admin(m.from_user.id):
        return
    d = await state.get_data()
    await state.clear()
    with suppress(Exception):
        await bot.send_message(d["uid"], quote(
            f"{tg('party')} <b>Buyurtma #{d['oid']} tayyor!</b>\n\n{m.html_text}"),
            message_effect_id=fx("party"))
    await m.answer(quote(f"{tg('ok')} <b>Mijozga yuborildi</b>"))

# ================== PROFIL / BUYURTMALAR / TIL / ALOQA ==================
@router.message(F.text.func(lambda s: norm(s) in BTN_ANY["prof"]))
async def profile(m: Message):
    u = await get_user(m)
    await m.answer(quote(t(u["lang"], "prof", i=tg("profile"), id_i=tg("gem"),
                           m=tg("money"), id=u["id"], n=u["name"],
                           lv=level_of(u["orders"]), c=u["orders"], s=u["spent"])))

@router.message(F.text.func(lambda s: norm(s) in BTN_ANY["ord"]))
async def my_orders(m: Message):
    u = await get_user(m)
    rows = await q("""SELECT id,title,total,status FROM orders
                      WHERE uid=? ORDER BY id DESC LIMIT 15""",
                   (m.from_user.id,), "all")
    if not rows:
        return await m.answer(quote(f"{tg('orders')} {t(u['lang'], 'empty')}"))
    ic = {"new": tg("warn"), "paid": tg("ok"), "rej": tg("no")}
    body = "\n".join(f"{ic.get(r['status'], '•')} <b>#{r['id']}</b> "
                     f"{r['title'][:35]} — <b>{r['total']:,}</b>" for r in rows)
    await m.answer(quote(t(u["lang"], "ord_t", i=tg("orders")) + "\n\n" + body))

@router.message(F.text.func(lambda s: norm(s) in BTN_ANY["lang"]))
async def change_lang(m: Message):
    u = await get_user(m)
    await m.answer(quote(t(u["lang"], "lang_q", i=tg("lang"))), reply_markup=lang_kb())

@router.callback_query(F.data.startswith("lang:"))
async def set_lang(c: CallbackQuery):
    lg = c.data.split(":")[1]
    await get_user(c)
    await q("UPDATE users SET lang=? WHERE id=?", (lg, c.from_user.id))
    with suppress(Exception):
        await c.message.delete()
    await c.message.answer(quote(f"{tg('ok')} <b>OK</b>"),
                           reply_markup=main_menu(lg, is_admin(c.from_user.id)))
    await c.answer()

@router.message(F.text.func(lambda s: norm(s) in BTN_ANY["help"]))
async def contact(m: Message):
    u = await get_user(m)
    await m.answer(quote(t(u["lang"], "help", i=tg("support"), s=SUPPORT)),
                   reply_markup=IKM(inline_keyboard=[[
                       B("Admin bilan bog'lanish", "support", "success",
                         url=f"https://t.me/{SUPPORT.lstrip('@')}")]]))

# ================== AI YORDAMCHI ==================
@router.message(F.text.func(lambda s: norm(s) in BTN_ANY["ai"]))
async def ai_on(m: Message, state: FSMContext):
    u = await get_user(m)
    if not GEMINI_KEY:
        return await m.answer(quote(f"{tg('warn')} {t(u['lang'], 'no_ai')}"))
    await state.set_state(AI.chat)
    await m.answer(quote(t(u["lang"], "ai_on", i=tg("ai"))))

@router.message(AI.chat, F.text)
async def ai_chat(m: Message):
    u = await get_user(m)
    wait = await m.answer(f"{tg('bolt')} <i>{t(u['lang'], 'wait')}</i>")
    ans = await gemini(m.text)
    with suppress(Exception):
        await wait.delete()
    if not ans:
        return await m.answer(quote(f"{tg('warn')} {t(u['lang'], 'no_ai')}"))
    for i in range(0, len(ans), 3800):
        await m.answer(ans[i:i + 3800])

# ================== ADMIN PANEL ==================
@router.message(Command("admin"))
async def admin_cmd(m: Message):
    if is_admin(m.from_user.id):
        await m.answer(quote(f"{tg('admin')} <b>Admin panel</b>"), reply_markup=admin_kb())

@router.message(F.text.func(lambda s: norm(s) == norm(ADMIN_BTN)))
async def admin_btn(m: Message):
    if is_admin(m.from_user.id):
        await m.answer(quote(f"{tg('admin')} <b>Admin panel</b>"), reply_markup=admin_kb())

@router.callback_query(F.data.startswith("a:"))
async def admin_actions(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("⛔️", show_alert=True)
    a = c.data.split(":")[1]

    if a == "stat":
        uc = (await q("SELECT COUNT(*) c FROM users", (), "one"))["c"]
        oc = (await q("SELECT COUNT(*) c FROM orders WHERE status='paid'", (), "one"))["c"]
        sm = (await q("SELECT SUM(total) c FROM orders WHERE status='paid'", (), "one"))["c"] or 0
        ts = (await q("SELECT SUM(total) c FROM orders WHERE status='paid' AND date(ts) = date('now')", (), "one"))["c"] or 0
        prods = (await q("SELECT COUNT(*) c FROM prods", (), "one"))["c"]
        cats = (await q("SELECT COUNT(*) c FROM cats", (), "one"))["c"]
        await c.message.answer(quote(f"📊 <b>To'liq Analitika</b>\n\n"
                               f"👥 Jami foydalanuvchilar: <b>{uc} ta</b>\n"
                               f"📦 Muvaffaqiyatli sotuvlar: <b>{oc} ta</b>\n"
                               f"📁 Jami bo'limlar: <b>{cats} ta</b>\n"
                               f"🛒 Jami mahsulotlar: <b>{prods} ta</b>\n"
                               f"💰 Jami tushum: <b>{sm:,} so'm</b>\n"
                               f"🔥 Bugungi tushum: <b>{ts:,} so'm</b>"))

    elif a == "cat":
        await state.set_state(Adm.cat)
        await c.message.answer(quote("📝 <b>Bo'lim nomi va emoji ID:</b>\nFormat: <code>Nom | ID</code>\nMasalan: <code>Netflix | 5452138632091569963</code>"))

    elif a == "editcat":
        cs = await q("SELECT * FROM cats", (), "all")
        txt = "\n".join(f"<code>{c['id']}</code> - {c['name']}" for c in cs)
        await state.set_state(Adm.editcat)
        await c.message.answer(quote(f"📁 <b>Kategoriyalar:</b>\n{txt}\n\n📝 Tahrirlash formati: <code>cat_id | Yangi Nom | Yangi_Emoji_ID</code>"))

    elif a == "delcat":
        cs = await q("SELECT * FROM cats", (), "all")
        txt = "\n".join(f"<code>{c['id']}</code> - {c['name']}" for c in cs)
        await state.set_state(Adm.delcat)
        await c.message.answer(quote(f"🗑 <b>O'chirish uchun kategoriya ID raqamini yuboring:</b>\n{txt}\n(Diqqat: Ichidagi mahsulotlar qolib ketadi)"))

    elif a == "prod":
        cs = await q("SELECT * FROM cats", (), "all")
        txt = "\n".join(f"<code>{c['id']}</code> - {c['name']}" for c in cs)
        await state.set_state(Adm.prod)
        await c.message.answer(quote(f"📁 <b>Kategoriyalar:</b>\n{txt}\n\n📝 Format: <code>cat_id | nom | narx | info</code>"))

    elif a == "editprod":
        ps = await q("SELECT * FROM prods", (), "all")
        txt = "\n".join(f"<code>{p['id']}</code> - {p['name']} ({p['price']:,} so'm)" for p in ps)
        if not txt: txt = "Mahsulotlar yo'q"
        await state.set_state(Adm.editprod)
        await c.message.answer(quote(f"📦 <b>Mahsulotlar:</b>\n{txt}\n\n📝 Tahrirlash formati:\n<code>prod_id | yangi_nom | yangi_narx | yangi_info</code>"))

    elif a == "delprod":
        ps = await q("SELECT * FROM prods", (), "all")
        txt = "\n".join(f"<code>{p['id']}</code> - {p['name']}" for p in ps)
        if not txt: txt = "Mahsulotlar yo'q"
        await state.set_state(Adm.delprod)
        await c.message.answer(quote(f"🗑 <b>O'chirish uchun mahsulot ID raqamini yuboring:</b>\n{txt}"))

    elif a == "ads":
        await state.set_state(Adm.ads)
        await c.message.answer(quote("📢 <b>Reklama xabarini yuboring (matn/rasm/video):</b>"))

    await c.answer()

@router.message(Adm.cat)
async def add_cat(m: Message, state: FSMContext):
    parts = [x.strip() for x in m.text.split("|")]
    if len(parts) >= 2:
        name, icon = parts[0], parts[1]
        pos = (await q("SELECT COALESCE(MAX(pos),0)+1 p FROM cats", (), "one"))["p"]
        await q("INSERT INTO cats(name,icon,alt,pos) VALUES(?,?,?,?)", (name, icon, "•", pos))
        await m.answer(quote("✅ Kategoriya muvaffaqiyatli qo'shildi."))
    else:
        await m.answer(quote("❌ Format xato kiritildi. Iltimos: <code>Nom | ID</code> shaklida yuboring."))
    await state.clear()

@router.message(Adm.editcat)
async def edit_cat(m: Message, state: FSMContext):
    p = [x.strip() for x in m.text.split("|")]
    if len(p) == 3 and p[0].isdigit():
        await q("UPDATE cats SET name=?, icon=? WHERE id=?", (p[1], p[2], int(p[0])))
        await m.answer(quote("✅ Bo'lim muvaffaqiyatli tahrirlandi."))
    else:
        await m.answer(quote("❌ Format xato. Namuna:\n<code>1 | Yangi Nom | 5452138632...</code>"))
    await state.clear()

@router.message(Adm.delcat)
async def del_cat(m: Message, state: FSMContext):
    if m.text.strip().isdigit():
        cid = int(m.text.strip())
        await q("DELETE FROM prods WHERE cat=?", (cid,))
        await q("DELETE FROM cats WHERE id=?", (cid,))
        await m.answer(quote("✅ Bo'lim va uning ichidagi mahsulotlar o'chirildi."))
    else:
        await m.answer(quote("❌ Faqat raqam (ID) yuboring."))
    await state.clear()

@router.message(Adm.prod)
async def add_prod(m: Message, state: FSMContext):
    p = [x.strip() for x in m.text.split("|")]
    if len(p) >= 4:
        try:
            cat_id = int(p[0])
            name = p[1]
            price = int(p[2].replace(" ", ""))
            info = "|".join(p[3:])
            await q("INSERT INTO prods(cat,name,price,stock,info) VALUES(?,?,?,100,?)",
                    (cat_id, name, price, info))
            await m.answer(quote("✅ Mahsulot muvaffaqiyatli qo'shildi."))
        except Exception:
            await m.answer(quote("❌ Xatolik yuz berdi: ID yoki narx xato kiritilgan bo'lishi mumkin."))
    else:
        await m.answer(quote("❌ Format xato kiritildi. Iltimos: <code>cat_id | nom | narx | info</code> shaklida yuboring."))
    await state.clear()

@router.message(Adm.editprod)
async def edit_prod(m: Message, state: FSMContext):
    p = [x.strip() for x in m.text.split("|")]
    if len(p) >= 4 and p[0].isdigit():
        try:
            pid = int(p[0])
            name = p[1]
            price = int(p[2].replace(" ", ""))
            info = "|".join(p[3:])
            await q("UPDATE prods SET name=?, price=?, info=? WHERE id=?", (name, price, info, pid))
            await m.answer(quote("✅ Mahsulot muvaffaqiyatli tahrirlandi."))
        except Exception:
            await m.answer(quote("❌ Narx yoki ID xato kiritildi."))
    else:
        await m.answer(quote("❌ Format xato. Namuna:\n<code>1 | Premium | 15000 | Malumot</code>"))
    await state.clear()

@router.message(Adm.delprod)
async def del_prod(m: Message, state: FSMContext):
    if m.text.strip().isdigit():
        pid = int(m.text.strip())
        await q("DELETE FROM cart WHERE pid=?", (pid,))
        await q("DELETE FROM order_items WHERE pid=?", (pid,))
        await q("DELETE FROM prods WHERE id=?", (pid,))
        await m.answer(quote("✅ Mahsulot o'chirildi."))
    else:
        await m.answer(quote("❌ Faqat raqam (ID) yuboring."))
    await state.clear()

@router.message(Adm.ads)
async def send_ads(m: Message, state: FSMContext, bot: Bot):
    us = await q("SELECT id FROM users", (), "all")
    ok, err = 0, 0
    msg = await m.answer(quote("⏳ Xabar tarqatilmoqda..."))
    for u in us:
        try:
            await bot.copy_message(u["id"], m.chat.id, m.message_id)
            ok += 1
        except Exception:
            err += 1
        await asyncio.sleep(0.05)
    await msg.edit_text(quote(f"✅ Tarqatish tugadi.\n\n📤 Yuborildi: {ok} ta\n❌ Xato: {err} ta"))
    await state.clear()

# ================== ISHGA TUSHIRISH ==================
async def handle_ping(request):
    return web.Response(text="OBUNALAR HUB — bot onlayn")

async def on_shutdown():
    if DB:
        await DB.close()

async def main():
    if not BOT_TOKEN:
        log.error("BOT_TOKEN yo'q! Environment variable orqali bering.")
        return
    if not ADMINS:
        log.warning("ADMINS berilmagan — admin panel ishlamaydi.")

    await init_db()

    bot = Bot(token=BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML,
                                           link_preview_is_disabled=True))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    with suppress(Exception):
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="start", description="Bosh menyu"),
            BotCommand(command="cancel", description="Bekor qilish"),
        ])
        await bot.set_my_description(
            "OBUNALAR HUB — Gemini, ChatGPT, Claude, CapCut va boshqa "
            "AI obunalari eng arzon narxlarda.")
        await bot.set_my_short_description("Arzon AI obunalari do'koni")

    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("Web server: 0.0.0.0:%s", PORT)

    try:
        log.info("Bot ishga tushdi")
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await on_shutdown()

if __name__ == "__main__":          
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot to'xtatildi")

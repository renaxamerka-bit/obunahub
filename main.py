# main.py — OBUNALAR HUB | BOT (aiogram 3.30+, Bot API 10.2)
import asyncio, logging, os, aiohttp, aiosqlite, time
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (Message, CallbackQuery, InlineKeyboardButton as IKB,
                           InlineKeyboardMarkup as IKM, KeyboardButton as KB,
                           ReplyKeyboardMarkup as RKM)

# ================= SOZLAMALAR =================
BOT_TOKEN   = "8669054173:AAGrCaUidTFAlxd1PKHTIc2xPlEf_AjPZrc"
ADMIN_ID    = 5700159922
CARD_NUMBER = "5614 6867 0900 3860"
CARD_OWNER  = "ZAYNIDDIN SHODEYEV"
GEMINI_KEY  = "AQ.Ab8RN6JwNyNSvtYRxvMxbeOfZt7rOCRd9ti923RubWVl3rMIaA"
GEMINI_MODEL= "gemini-1.5-flash"
CHANNELS    = ["@obunahub_rasmiy", "@obunalarhub_guruh"]
SUPPORT     = "@XushvaqtovSh"
# Noldan toza ishlashi uchun baza nomi v2 qilindi
DB_PATH     = "obunahub_v2.db"
PORT        = int(os.getenv("PORT", "8080"))

USE_PREMIUM_EMOJI = True          
logging.basicConfig(level=logging.INFO)

# ============ PREMIUM EMOJI ID LARI ============
ICON = {
    "Gemini Ai":    "5452138632091569963",
    "Claud Ai":     "6174520215376763867",
    "ChatGpt":      "5303113132460250222",
    "Supper Grok":  "6179337489350663129",
    "Flow Ai":      "6178962311072456422",
    "CapCut":       "5978895591894161700",
    "Leoanardo Ai": "6133975818591805751",
}
ICON_SOLD = "6181467651395558500"   # ❌ tugagan
FALLBACK  = {"Gemini Ai": "✨", "Claud Ai": "✴️", "ChatGpt": "💬", "Supper Grok": "🚀",
             "Flow Ai": "🌊", "CapCut": "📹", "Leoanardo Ai": "💎"}

def ib(text, icon=None, style=None, **kw):
    if USE_PREMIUM_EMOJI:
        if icon:  kw["icon_custom_emoji_id"] = icon
        if style: kw["style"] = style
        return IKB(text=text, **kw)
    return IKB(text=text, **kw)

def cat_btn(name, cb, sold=False):
    ic = ICON.get(name)
    if USE_PREMIUM_EMOJI and ic:
        return ib(name, icon=ICON_SOLD if sold else ic,
                  style="danger" if sold else None, callback_data=cb)
    return IKB(text=f"{FALLBACK.get(name,'•')} {name}", callback_data=cb)

def tg(icon, alt="🔹"):
    return f'<tg-emoji emoji-id="{icon}">{alt}</tg-emoji>' if USE_PREMIUM_EMOJI else alt

# ================= TILLAR VA MENYU =================
MENU = {
    "srv":  ("🛍", "Xizmatlar", "Услуги"),
    "cart": ("🛒", "Savat", "Корзина"),
    "prof": ("👤", "Profil", "Профиль"),
    "ord":  ("📦", "Buyurtmalarim", "Мои заказы"),
    "ai":   ("🤖", "AI yordamchi", "AI помощник"),
    "lang": ("🌐", "Til", "Язык"),
    "help": ("📞", "Aloqa", "Связь"),
}
BTN_ANY = {k: {v[1], v[2], f"{v[0]} {v[1]}", f"{v[0]} {v[2]}"} for k, v in MENU.items()}

T = {
 "uz": {"start":"Assalomu alaykum, {n}!\nOBUNALAR HUB botiga xush kelibsiz.",
        "cats":"📁 <b>Bo'limni tanlang:</b>", "prods":"📦 <b>Mahsulotlar:</b>",
        "empty":"Hozircha bo'sh.", "cart_empty":"🛒 Savatingiz bo'sh.",
        "sub":"❗️ Botdan foydalanish uchun kanallarga obuna bo'ling:",
        "sub_ok":"✅ Obuna tasdiqlandi!", "sub_no":"❌ Hali obuna bo'lmadingiz.",
        "pay":"💳 To'lov:\n<code>{c}</code>\n👤 {o}\n💰 <b>{p:,} so'm</b>\n\n📸 Chek rasmini yuboring.",
        "recv":"✅ Chek qabul qilindi. Admin tekshirmoqda ⏳",
        "need_photo":"📸 Iltimos, chekni <b>rasm</b> qilib yuboring.",
        "cancel":"❌ Bekor qilindi.", "added":"✅ Savatga qo'shildi.",
        "prof":"👤 <b>Profil</b>\nID: <code>{id}</code>\nIsm: {n}\nDaraja: {lv}\nBuyurtmalar: {c}\nSarflangan: {s:,} so'm",
        "lang_q":"🌐 Tilni tanlang:", "help":f"📞 Admin: {SUPPORT}",
        "ai_on":"🤖 Savolingizni yozing. Chiqish: /cancel",
        "no_ai":"⚠️ AI hozircha ishlamayapti.", "wait":"⏳ ..." },
 "ru": {"start":"Здравствуйте, {n}!\nДобро пожаловать в OBUNALAR HUB.",
        "cats":"📁 <b>Выберите раздел:</b>", "prods":"📦 <b>Товары:</b>",
        "empty":"Пока пусто.", "cart_empty":"🛒 Корзина пуста.",
        "sub":"❗️ Подпишитесь на каналы:", "sub_ok":"✅ Подписка подтверждена!",
        "sub_no":"❌ Вы ещё не подписались.",
        "pay":"💳 Оплата:\n<code>{c}</code>\n👤 {o}\n💰 <b>{p:,} сум</b>\n\n📸 Отправьте чек.",
        "recv":"✅ Чек принят. Админ проверяет ⏳",
        "need_photo":"📸 Отправьте чек <b>картинкой</b>.",
        "cancel":"❌ Отменено.", "added":"✅ Добавлено в корзину.",
        "prof":"👤 <b>Профиль</b>\nID: <code>{id}</code>\nИмя: {n}\nУровень: {lv}\nЗаказов: {c}\nПотрачено: {s:,} сум",
        "lang_q":"🌐 Выберите язык:", "help":f"📞 Админ: {SUPPORT}",
        "ai_on":"🤖 Напишите вопрос. Выход: /cancel",
        "no_ai":"⚠️ AI сейчас недоступен.", "wait":"⏳ ..."},
}
def t(l, k, **kw): return T.get(l, T["uz"]).get(k, k).format(**kw)

# ================= BAZA =================
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, lang TEXT DEFAULT 'uz',
  orders INTEGER DEFAULT 0, spent INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS cats(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, icon TEXT);
CREATE TABLE IF NOT EXISTS prods(id INTEGER PRIMARY KEY AUTOINCREMENT, cat INTEGER,
  name TEXT, price INTEGER, stock INTEGER DEFAULT 1, info TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS cart(uid INTEGER, pid INTEGER);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, pid INTEGER,
  price INTEGER, status TEXT DEFAULT 'new', receipt TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP);
"""
async def q(sql, args=(), fetch=None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, args)
        if fetch == "one":  r = await cur.fetchone(); await db.commit(); return r
        if fetch == "all":  r = await cur.fetchall(); await db.commit(); return r
        await db.commit(); return cur.lastrowid

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA); await db.commit()
        
    c_count = await q("SELECT COUNT(*) c FROM cats", (), "one")
    if not c_count or c_count["c"] == 0:
        # Kategoriyalarni kiritish
        cats = ["Gemini Ai", "Claud Ai", "ChatGpt", "Supper Grok", "Flow Ai", "CapCut", "Leoanardo Ai"]
        for name in cats:
            await q("INSERT OR IGNORE INTO cats(name,icon) VALUES(?,?)", (name, ICON.get(name)))
            
        # Maxsulotlarni kiritish
        prods = [
            (1, "Gemini Ai Pro (18 oylik)", 40000, 100, "Obunani faollashtirish uchun linkni nusxalab oling. Keyin o'zingizga kerakli bo'lgan Google akkauntingizga o'tib, qidiruvga o'sha nusxalangan linkni joylang va qidiruvni bosing. So'ngra chiqqan saytdan \"Obunani faollashtirish\" yoki \"Get started\" tugmasini bosib, obunani o'z akkauntingizda faollashtirishingiz mumkin!\n\nEslatma: Ushbu link 12 soat davomida amal qiladi"),
            (2, "Claud Pro (1 Oylik)", 165000, 100, "🛡️ 25 kunlik to'liq kafolat: Xarid jarayonidan so'ng 25 kun davomida kafolat amal qiladi.\n🔄 Kafolatlangan almashtirish: Agar obunada biror muammo chiqsa yoki faolsizlanib qolsa, o'rniga bir zumda yangisi taqdim etiladi.\n💳 Bank kartasi shart emas.\n⚡ Oson faollashtirish: Havolani bosasiz va bir nechta soniyada obuna akkauntingizda ishga tushadi."),
            (3, "ChatGpt Plus (1 oylik)", 100000, 100, "🛡️ To'liq kafolat: Akkaunt barqaror va kafolatlangan holda taqdim etiladi.\n🔒 Taqiq va bloklanishsiz (No Ban): Akkauntdan foydalanish jarayonida muammolar yoki deaktivatsiya xavfi bo'lmaydi.\n🚀 Maksimal barqarorlik: Har doim uzluksiz, tez va barqaror ishlaydigan tayyor akkaunt (Stable Account)."),
            (6, "CapCut PRO [7 kunlik]", 15000, 100, "CapCut PRO obunasi 7 kunlik To'liq Garantiya!"),
            (6, "CapCut PRO [30 kunlik]", 42000, 100, "CapCut PRO obunasi 30 kunlik To'liq Garantiya!"),
            (6, "CapCut PRO [3 oyliik]", 132000, 100, "CapCut PRO obunasi 3 oylik To'liq Garantiya!"),
            (6, "CapCut PRO [6 oyliik]", 210000, 100, "CapCut PRO obunasi 6 oylik To'liq Garantiya!"),
            (6, "CapCut PRO [1 yillik]", 370000, 100, "CapCut PRO obunasi 1 yillik To'liq Garantiya!"),
            (7, "Leoanardo Ai 8500 Cridet", 50000, 100, "Leoanardo Ai 1 oylik obuna sizga 8500 cridet beriladi!"),
        ]
        for p in prods:
            await q("INSERT INTO prods(cat,name,price,stock,info) VALUES(?,?,?,?,?)", p)

async def get_user(m):
    u = await q("SELECT * FROM users WHERE id=?", (m.from_user.id,), "one")
    if not u:
        await q("INSERT INTO users(id,name) VALUES(?,?)", (m.from_user.id, m.from_user.full_name))
        u = await q("SELECT * FROM users WHERE id=?", (m.from_user.id,), "one")
    return u

def level_of(n): return "🥉 Bronza" if n < 3 else ("🥈 Kumush" if n < 10 else "🥇 Oltin")

# ================= KLAVIATURALAR =================
def main_menu(lang="uz", admin=False):
    i = 1 if lang == "uz" else 2
    rows = [[KB(text=f"{MENU['srv'][0]} {MENU['srv'][i]}"), KB(text=f"{MENU['cart'][0]} {MENU['cart'][i]}")],
            [KB(text=f"{MENU['prof'][0]} {MENU['prof'][i]}"), KB(text=f"{MENU['ord'][0]} {MENU['ord'][i]}")],
            [KB(text=f"{MENU['ai'][0]} {MENU['ai'][i]}"), KB(text=f"{MENU['lang'][0]} {MENU['lang'][i]}")],
            [KB(text=f"{MENU['help'][0]} {MENU['help'][i]}")]]
    if admin: rows.append([KB(text="⚙️ Admin panel")])
    return RKM(keyboard=rows, resize_keyboard=True)

def lang_kb():
    return IKM(inline_keyboard=[[IKB(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
                                IKB(text="🇷🇺 Русский",  callback_data="lang:ru")]])

async def cats_kb():
    rows, buf = [], []
    for c in await q("SELECT * FROM cats ORDER BY id", (), "all"):
        buf.append(cat_btn(c["name"], f"cat:{c['id']}"))
        if len(buf) == 2: rows.append(buf); buf = []
    if buf: rows.append(buf)
    return IKM(inline_keyboard=rows or [[IKB(text="—", callback_data="nop")]])

async def prods_kb(cid):
    name = (await q("SELECT name FROM cats WHERE id=?", (cid,), "one"))["name"]
    ic, rows = ICON.get(name), []
    for p in await q("SELECT * FROM prods WHERE cat=? ORDER BY id", (cid,), "all"):
        txt = f"{p['name']} — {p['price']:,} so'm"
        sold = p["stock"] <= 0
        if USE_PREMIUM_EMOJI and ic:
            rows.append([ib(txt, icon=ICON_SOLD if sold else ic,
                            style="danger" if sold else None, callback_data=f"prod:{p['id']}")])
        else:
            rows.append([IKB(text=f"{FALLBACK.get(name,'•')} {txt}", callback_data=f"prod:{p['id']}")])
    rows.append([IKB(text="⬅️ Ortga", callback_data="cats")])
    return IKM(inline_keyboard=rows)

def prod_kb(pid, sold=False):
    if sold:
        return IKM(inline_keyboard=[[IKB(text="❌ Tugagan", callback_data="nop")],
                                    [IKB(text="⬅️ Ortga", callback_data="cats")]])
    return IKM(inline_keyboard=[[ib("💳 Sotib olish", style="success", callback_data=f"buy:{pid}")],
                                [IKB(text="🛒 Savatga", callback_data=f"add:{pid}"),
                                 IKB(text="⬅️ Ortga", callback_data="cats")]])

def order_kb(oid):
    return IKM(inline_keyboard=[[ib("✅ Tasdiqlash", style="success", callback_data=f"ok:{oid}"),
                                 ib("❌ Rad etish",  style="danger",  callback_data=f"no:{oid}")]])

def subs_kb(lang="uz"):
    rows = [[IKB(text=f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in CHANNELS]
    rows.append([ib("✅ Tekshirish", style="success", callback_data="chk")])
    return IKM(inline_keyboard=rows)

def admin_kb():
    return IKM(inline_keyboard=[
        [IKB(text="📊 To'liq Analitika", callback_data="a:stat")],
        [IKB(text="➕ Bo'lim qo'shish", callback_data="a:cat"), IKB(text="✏️ Bo'lim tahrirlash", callback_data="a:editcat")],
        [IKB(text="➕ Mahsulot qo'shish", callback_data="a:prod"), IKB(text="✏️ Mahsulot tahrirlash", callback_data="a:editprod")],
        [IKB(text="🗑 Bo'lim o'chirish", callback_data="a:delcat"), IKB(text="🗑 Mahsulot o'chirish", callback_data="a:del")],
        [IKB(text="📢 Reklama yuborish", callback_data="a:ads")]])
# ================= HOLATLAR =================
class Buy(StatesGroup): receipt = State()
class Adm(StatesGroup):
    cat = State(); prod = State(); dele = State(); ads = State(); give = State()
    editcat = State(); editprod = State(); delcat = State()
    cat = State(); prod = State(); dele = State(); ads = State(); give = State()

router = Router()

async def missing_subs(bot, uid):
    out = []
    for ch in CHANNELS:
        try:
            mem = await bot.get_chat_member(ch, uid)
            if mem.status in ("left", "kicked"): out.append(ch)
        except Exception: pass
    return out

# ================= START =================
@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext, bot: Bot):
    await state.clear(); u = await get_user(m)
    if await missing_subs(bot, m.from_user.id):
        return await m.answer(t(u["lang"], "sub"), reply_markup=subs_kb(u["lang"]))
    await m.answer(t(u["lang"], "start", n=m.from_user.first_name),
                   reply_markup=main_menu(u["lang"], m.from_user.id == ADMIN_ID))

@router.callback_query(F.data == "chk")
async def check_sub(c: CallbackQuery, bot: Bot):
    u = await get_user(c)
    if await missing_subs(bot, c.from_user.id):
        return await c.answer(t(u["lang"], "sub_no"), show_alert=True)
    await c.message.delete()
    await c.message.answer(t(u["lang"], "sub_ok"),
                           reply_markup=main_menu(u["lang"], c.from_user.id == ADMIN_ID))

@router.callback_query(F.data == "nop")
async def nop(c: CallbackQuery): await c.answer("❌ Bu mahsulot tugagan", show_alert=True)

# ================= MENYU =================
@router.message(F.text.in_(BTN_ANY["srv"]))
async def services(m: Message):
    u = await get_user(m)
    await m.answer(t(u["lang"], "cats"), reply_markup=await cats_kb())

@router.callback_query(F.data == "cats")
async def back_cats(c: CallbackQuery):
    u = await get_user(c)
    await c.message.edit_text(t(u["lang"], "cats"), reply_markup=await cats_kb()); await c.answer()

@router.callback_query(F.data.startswith("cat:"))
async def open_cat(c: CallbackQuery):
    u = await get_user(c); cid = int(c.data.split(":")[1])
    await c.message.edit_text(t(u["lang"], "prods"), reply_markup=await prods_kb(cid)); await c.answer()

@router.callback_query(F.data.startswith("prod:"))
async def open_prod(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    p = await q("SELECT * FROM prods WHERE id=?", (pid,), "one")
    if not p: return await c.answer("Topilmadi", show_alert=True)
    cat = (await q("SELECT name FROM cats WHERE id=?", (p["cat"],), "one"))["name"]
    txt = (f"{tg(ICON.get(cat,''), FALLBACK.get(cat,'•'))} <b>{p['name']}</b>\n"
           f"💰 {p['price']:,} so'm\n"
           f"{'✅ Mavjud' if p['stock'] > 0 else '❌ Tugagan'}\n\n{p['info'] or ''}")
    await c.message.edit_text(txt, reply_markup=prod_kb(pid, p["stock"] <= 0)); await c.answer()

@router.callback_query(F.data.startswith("add:"))
async def cart_add(c: CallbackQuery):
    u = await get_user(c); pid = int(c.data.split(":")[1])
    await q("INSERT INTO cart(uid,pid) VALUES(?,?)", (c.from_user.id, pid))
    await c.answer(t(u["lang"], "added"), show_alert=True)

@router.message(F.text.in_(BTN_ANY["cart"]))
async def cart_show(m: Message):
    u = await get_user(m)
    rows = await q("SELECT p.* FROM cart c JOIN prods p ON p.id=c.pid WHERE c.uid=?",
                   (m.from_user.id,), "all")
    if not rows: return await m.answer(t(u["lang"], "cart_empty"))
    tot = sum(r["price"] for r in rows)
    txt = "\n".join(f"• {r['name']} — {r['price']:,}" for r in rows) + f"\n\n💰 <b>{tot:,} so'm</b>"
    kb = IKM(inline_keyboard=[[ib("💳 Hammasini olish", style="success", callback_data="buycart")],
                              [ib("🗑 Tozalash", style="danger", callback_data="clr")]])
    await m.answer("🛒 <b>Savat</b>\n\n" + txt, reply_markup=kb)

@router.callback_query(F.data == "clr")
async def cart_clear(c: CallbackQuery):
    await q("DELETE FROM cart WHERE uid=?", (c.from_user.id,))
    await c.message.edit_text("🗑 Savat tozalandi."); await c.answer()

@router.message(F.text.in_(BTN_ANY["prof"]))
async def profile(m: Message):
    u = await get_user(m)
    await m.answer(t(u["lang"], "prof", id=u["id"], n=u["name"],
                     lv=level_of(u["orders"]), c=u["orders"], s=u["spent"]))

@router.message(F.text.in_(BTN_ANY["ord"]))
async def my_orders(m: Message):
    u = await get_user(m)
    rows = await q("""SELECT o.id,o.price,o.status,p.name FROM orders o
                      LEFT JOIN prods p ON p.id=o.pid WHERE o.uid=? ORDER BY o.id DESC LIMIT 15""",
                   (m.from_user.id,), "all")
    if not rows: return await m.answer(t(u["lang"], "empty"))
    ic = {"new": "⏳", "paid": "✅", "rej": "❌"}
    await m.answer("📦 <b>Buyurtmalar</b>\n\n" + "\n".join(
        f"{ic.get(r['status'],'•')} #{r['id']} {r['name']} — {r['price']:,}" for r in rows))

@router.message(F.text.in_(BTN_ANY["lang"]))
async def change_lang(m: Message):
    u = await get_user(m); await m.answer(t(u["lang"], "lang_q"), reply_markup=lang_kb())

@router.callback_query(F.data.startswith("lang:"))
async def set_lang(c: CallbackQuery):
    lg = c.data.split(":")[1]
    await get_user(c); await q("UPDATE users SET lang=? WHERE id=?", (lg, c.from_user.id))
    await c.message.delete()
    await c.message.answer("✅", reply_markup=main_menu(lg, c.from_user.id == ADMIN_ID))

@router.message(F.text.in_(BTN_ANY["help"]))
async def contact(m: Message):
    u = await get_user(m); await m.answer(t(u["lang"], "help"))

# ================= XARID =================
async def start_order(msg, uid, pid, price, state):
    u = await q("SELECT lang FROM users WHERE id=?", (uid,), "one")
    lang = u["lang"] if u else "uz"
    oid = await q("INSERT INTO orders(uid,pid,price) VALUES(?,?,?)", (uid, pid, price))
    await state.set_state(Buy.receipt); await state.update_data(oid=oid)
    await msg.answer(t(lang, "pay", c=CARD_NUMBER, o=CARD_OWNER, p=price))

@router.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery, state: FSMContext):
    pid = int(c.data.split(":")[1])
    p = await q("SELECT * FROM prods WHERE id=?", (pid,), "one")
    if not p or p["stock"] <= 0: return await c.answer("❌ Tugagan", show_alert=True)
    await c.answer(); await start_order(c.message, c.from_user.id, pid, p["price"], state)

@router.callback_query(F.data == "buycart")
async def buy_cart(c: CallbackQuery, state: FSMContext):
    rows = await q("SELECT p.* FROM cart c JOIN prods p ON p.id=c.pid WHERE c.uid=?",
                   (c.from_user.id,), "all")
    if not rows: return await c.answer("Bo'sh", show_alert=True)
    tot = sum(r["price"] for r in rows)
    await c.answer(); await start_order(c.message, c.from_user.id, rows[0]["id"], tot, state)

@router.message(Buy.receipt, F.photo)
async def receipt(m: Message, state: FSMContext, bot: Bot):
    d = await state.get_data(); oid = d.get("oid"); u = await get_user(m)
    fid = m.photo[-1].file_id
    await q("UPDATE orders SET receipt=? WHERE id=?", (fid, oid))
    await m.answer(t(u["lang"], "recv"), reply_markup=main_menu(u["lang"], m.from_user.id == ADMIN_ID))
    o = await q("SELECT * FROM orders WHERE id=?", (oid,), "one")
    if ADMIN_ID:
        await bot.send_photo(ADMIN_ID, fid, caption=(
            f"🧾 <b>Yangi buyurtma #{oid}</b>\n👤 {m.from_user.full_name} "
            f"(<code>{m.from_user.id}</code>) @{m.from_user.username or '-'}\n"
            f"💰 {o['price']:,} so'm"), reply_markup=order_kb(oid))
    await state.clear()

@router.message(Buy.receipt)
async def receipt_wrong(m: Message):
    u = await get_user(m); await m.answer(t(u["lang"], "need_photo"))

@router.callback_query(F.data.startswith(("ok:", "no:")))
async def moderate(c: CallbackQuery, state: FSMContext, bot: Bot):
    if c.from_user.id != ADMIN_ID: return await c.answer("⛔️", show_alert=True)
    act, oid = c.data.split(":"); oid = int(oid)
    o = await q("SELECT * FROM orders WHERE id=?", (oid,), "one")
    if not o: return await c.answer("Yo'q", show_alert=True)
    if act == "no":
        await q("UPDATE orders SET status='rej' WHERE id=?", (oid,))
        await bot.send_message(o["uid"], f"❌ Buyurtma #{oid} rad etildi. Admin: {SUPPORT}")
        return await c.message.edit_caption(caption=f"❌ #{oid} rad etildi")
    await q("UPDATE orders SET status='paid' WHERE id=?", (oid,))
    await q("UPDATE users SET orders=orders+1, spent=spent+? WHERE id=?", (o["price"], o["uid"]))
    await q("UPDATE prods SET stock=stock-1 WHERE id=? AND stock>0", (o["pid"],))
    await q("DELETE FROM cart WHERE uid=?", (o["uid"],))
    await state.set_state(Adm.give); await state.update_data(uid=o["uid"], oid=oid)
    await c.message.edit_caption(caption=f"✅ #{oid} tasdiqlandi")
    await c.message.answer(f"✍️ #{oid} uchun akkaunt/havolani yuboring:")

@router.message(Adm.give)
async def deliver(m: Message, state: FSMContext, bot: Bot):
    d = await state.get_data(); await state.clear()
    await bot.send_message(d["uid"], f"✅ <b>Buyurtma #{d['oid']} tayyor!</b>\n\n{m.text}")
    await m.answer("📤 Mijozga yuborildi.")

# ================= ADMIN =================
@router.message(Command("admin"))
@router.message(F.text == "⚙️ Admin panel")
async def admin_panel(m: Message):
    if m.from_user.id != ADMIN_ID: return
    await m.answer("⚙️ <b>Admin panel</b>", reply_markup=admin_kb())

@router.callback_query(F.data.startswith("a:"))
async def admin_actions(c: CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID: return await c.answer("⛔️", show_alert=True)
    a = c.data.split(":")[1]
    if a == "cat":
        await state.set_state(Adm.cat)
        await c.message.answer("Bo'lim nomi va emoji ID:\n<code>Gemini|5452138632091569963</code>")
    elif a == "prod":
        cs = await q("SELECT * FROM cats", (), "all")
        txt = "\n".join(f"{c['id']} - {c['name']}" for c in cs)
        await state.set_state(Adm.prod)
        await c.message.answer(f"📁 Kategoriyalar:\n{txt}\n\n📝 Format: <code>cat_id | nom | narx | info</code>")
    elif a == "del":
        ps = await q("SELECT * FROM prods", (), "all")
        txt = "\n".join(f"{p['id']} - {p['name']}" for p in ps)
        await state.set_state(Adm.dele)
        await c.message.answer(f"🗑 O'chirish uchun ID yuboring:\n{txt}")
    elif a == "ads":
        await state.set_state(Adm.ads)
        await c.message.answer("📢 Reklama xabarini yuboring (matn/rasm):")
    elif a == "stat":
        uc = (await q("SELECT COUNT(*) c FROM users", (), "one"))["c"]
        oc = (await q("SELECT COUNT(*) c FROM orders WHERE status='paid'", (), "one"))["c"]
        sm = (await q("SELECT SUM(price) c FROM orders WHERE status='paid'", (), "one"))["c"] or 0
        await c.message.answer(f"📊 <b>Statistika</b>\n👤 Foydalanuvchilar: {uc}\n📦 Sotuvlar: {oc}\n💰 Tushum: {sm:,} so'm")
    await c.answer()

@router.message(Adm.cat)
async def add_cat(m: Message, state: FSMContext):
    parts = m.text.split("|")
    if len(parts) == 2:
        await q("INSERT INTO cats(name,icon) VALUES(?,?)", (parts[0].strip(), parts[1].strip()))
        await m.answer("✅ Kategoriya qo'shildi.")
    else:
        await m.answer("❌ Format xato.")
    await state.clear()

@router.message(Adm.prod)
async def add_prod(m: Message, state: FSMContext):
    p = m.text.split("|")
    if len(p) == 4:
        try:
            await q("INSERT INTO prods(cat,name,price,info) VALUES(?,?,?,?)",
                    (int(p[0]), p[1].strip(), int(p[2].strip().replace(" ", "")), p[3].strip()))
            await m.answer("✅ Mahsulot qo'shildi.")
        except Exception:
            await m.answer("❌ ID yoki narx xato kiritildi.")
    else:
        await m.answer("❌ Format xato.")
    await state.clear()

@router.message(Adm.dele)
async def del_prod(m: Message, state: FSMContext):
    if m.text.isdigit():
        await q("DELETE FROM prods WHERE id=?", (int(m.text),))
        await m.answer("✅ Mahsulot o'chirildi.")
    else:
        await m.answer("❌ Faqat ID raqam yuboring.")
    await state.clear()

@router.message(Adm.ads)
async def send_ads(m: Message, state: FSMContext, bot: Bot):
    us = await q("SELECT id FROM users", (), "all")
    ok, err = 0, 0
    msg = await m.answer("⏳ Xabar tarqatilmoqda...")
    for u in us:
        try:
            await bot.copy_message(u["id"], m.chat.id, m.message_id)
            ok += 1
        except Exception:
            err += 1
        await asyncio.sleep(0.05)
    await msg.edit_text(f"✅ Tarqatish tugadi.\n\n📤 Yuborildi: {ok} ta\n❌ Xato: {err} ta")
    await state.clear()

# ================= ISHGA TUSHIRISH (WEB SERVER) =================
async def handle_ping(request):
    return web.Response(text="OBUNALAR HUB - Bot 24/7 onlayn ishlamoqda!")

async def main():
    await init_db()
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN kiritilmagan! Bot ishga tushmaydi.")
        return

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    
    asyncio.create_task(dp.start_polling(bot))
    
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logging.info(f"🚀 Bot ishga tushdi... Port: {PORT}")
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("🛑 Bot to'xtatildi.")

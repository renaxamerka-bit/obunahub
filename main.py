import asyncio
import logging
import time
import secrets
import os
import aiosqlite
import aiohttp

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup,
                           InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ============================ SOZLAMALAR ============================
BOT_TOKEN   = "8669054173:AAGrCaUidTFAlxd1PKHTIc2xPlEf_AjPZrc" 
ADMINS      = [5700159922]
ADMIN_GROUP = 0
CARD_NUMBER = "5614 6867 0900 3860"
CARD_HOLDER = "ZAYNIDDIN SHODEYEV"
FORCE_SUB   = ["@obunahub_rasmiy", "@obunalarhub_guruh"]
CHANNEL_URL = "https://t.me/obunahub_rasmiy"
SUPPORT     = "@XushvaqtovSh"
CURRENCY    = "so'm"
CASHBACK    = 1
REF_BONUS   = 100
LEVELS      = [(0, "Bronza"), (500000, "Kumush"), (2000000, "Oltin"), (5000000, "Platina")]
DB_PATH     = "obunahub.db"

# ==================== CLAUDE PREMIUM EMOJI TIZIMI ==========================
USE_PREMIUM_EMOJI = True   # Matnlarda premium emojilardan foydalanish uchun

# key: (matn, oddiy emoji, premium emoji id)
MENU = {
    "srv":  ("Xizmatlar",    "💎", "5796182602176007916"),
    "ai":   ("AI Yordamchi", "🚀", "6174520215376763867"),
    "cart": ("Savatcha",     "🛒", "5312361253610475399"),
    "prof": ("Profil",       "⚜️", "5290020594673266043"),
    "lang": ("Til",          "🌐", "5318911503938634641"),
    "cont": ("Aloqa",        "🎧", "5460795800101594035"),
    "adm":  ("Boshqarish",   "⚙️", "5456140674028019486"),
    "test": ("Test Obuna",   "🔧", "5825794181183836432"),
}
# Knopka nomlarini ushlab olish uchun (foydalanuvchi qaysi emojida bossa ham ushlaydi)
BTN_ANY = {k: {v[0], f"{v[1]} {v[0]}"} for k, v in MENU.items()}

# Inline tugmalar uchun ikonkalar: (fallback, premium_id)
IK = {
    "buy":     ("💳", "5409048419211682843"),
    "cadd":    ("🛒", "5312361253610475399"),
    "back":    ("🔙", "6113945650196388135"),
    "ok":      ("✅", "6088893844693195262"),
    "no":      ("❌", "6181467651395558500"),
    "sub":     ("📢", "5460795800101594035"),
    "check":   ("✅", "5825794181183836432"),
    "orders":  ("📋", "5422536330213088080"),
    "trash":   ("🗑", "6181467651395558500"),
    "cancel":  ("🚫", "6181467651395558500"),
    "stats":   ("📊", "5438379498200391294"),
    "pending": ("⏳", "5260491539167073671"),
    "plus":    ("➕", "5393194986252542669"),
    "bc":      ("📢", "5215668908278686541"),
    "op":      ("💬", "5417915203100613993"),
    "chan":    ("📢", "5461151367559141950"),
    "price":   ("🏷", "5821240446403223107"),
    "uz":      ("🇺🇿", None),
    "ru":      ("🇷🇺", None),
}

# Kategoriya ikonkalari 
CAT_ICON = {
    1: ("🤖", "5452138632091569963"),   # Gemini
    2: ("✴️", "5794295402136081349"),   # Claude
    3: ("💬", "5303113132460250222"),   # ChatGPT
    4: ("🚀", "6174520215376763867"),   # Grok
    5: ("🌊", "5224607267797606837"),   # Flow Ai
    6: ("📹", "5978895591894161700"),   # CapCut
    7: ("💎", "6133975818591805751"),   # Leonardo
}

def _mix(pair, text):
    ico, eid = pair
    # Telegram API hozircha knopkalar ichiga premium emoji qo'yishga ruxsat bermaydi, shuning uchun xavfsiz standartni qaytaramiz
    return f"{ico} {text}".strip() if ico else text

def ib(key, text, **kw):
    """inline tugma + xavfsiz ikonka (crash oldi olingan)"""
    t = _mix(IK.get(key, ("", None)), text)
    return InlineKeyboardButton(text=t, **kw)

def rb(key):
    """pastdagi menyu tugmasi + xavfsiz ikonka"""
    name, ico, eid = MENU[key]
    return KeyboardButton(text=f"{ico} {name}")

def tg(pair):
    ico, eid = pair
    return f'<tg-emoji emoji-id="{eid}">{ico}</tg-emoji>' if (eid and USE_PREMIUM_EMOJI) else ico

# Matnlar uchun tayyorlangan premium emojilar
PREMIUM_EMOJIS = {cid: tg(p) for cid, p in CAT_ICON.items()}

# ============================== BAZA ================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, lang TEXT DEFAULT 'uz',
  balance INTEGER DEFAULT 0, cashback_total INTEGER DEFAULT 0, spent INTEGER DEFAULT 0,
  orders_count INTEGER DEFAULT 0, ref_code TEXT, ref_by INTEGER, refs INTEGER DEFAULT 0,
  ref_paid INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, created_at INTEGER);
CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, emoji TEXT DEFAULT '📁', is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cat_id INTEGER, title TEXT, price INTEGER,
  description TEXT, emoji TEXT DEFAULT '🎁', sold INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id INTEGER, price INTEGER,
  used_bonus INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', receipt TEXT, created_at INTEGER);
CREATE TABLE IF NOT EXISTS cart(
  user_id INTEGER, product_id INTEGER, qty INTEGER DEFAULT 1, PRIMARY KEY(user_id, product_id));
CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, user_id INTEGER,
  rating INTEGER, text TEXT, created_at INTEGER);
"""

async def q(sql, args=(), one=False, write=False):
    async with aiosqlite.connect(DB_PATH) as d:
        d.row_factory = aiosqlite.Row
        cur = await d.execute(sql, args)
        if write:
            await d.commit()
            return cur.lastrowid
        rows = await cur.fetchall()
        if one:
            return dict(rows[0]) if rows else None
        return [dict(r) for r in rows]

async def init_db():
    async with aiosqlite.connect(DB_PATH) as d:
        await d.executescript(SCHEMA)
        cur = await d.execute("SELECT COUNT(*) FROM categories")
        count = await cur.fetchone()
        
        if count[0] == 0:
            cats = [
                (1, "Gemini Ai", "🤖", 1),
                (2, "Claud Ai", "✴️", 1),
                (3, "ChatGpt", "💬", 1),
                (4, "Supper Grok", "🚀", 1),
                (5, "Flow Ai", "🌊", 1),
                (6, "CapCut", "📹", 1),
                (7, "Leoanardo Ai", "💎", 1)
            ]
            await d.executemany("INSERT INTO categories (id, title, emoji, is_active) VALUES (?, ?, ?, ?)", cats)
            
            prods = [
                (1, 1, "Gemini Ai Pro(18 oylik)", 40000, "Obunani faollashtirish uchun linkni nusxalab oling. Keyin o'zingizga kerakli bo'lgan Google akkauntingizga o'tib, qidiruvga o'sha nusxalangan linkni joylang va qidiruvni bosing. So'ngra chiqqan saytdan \"Obunani faollashtirish\" yoki \"Get started\" tugmasini bosib, obunani o'z akkauntingizda faollashtirishingiz mumkin!\n\nEslatma: Ushbu link 12 soat davomida amal qiladi", "🤖", 0, 1),
                (2, 2, "Claud Pro (1 Oylik)", 165000, "🛡️ 25 kunlik to'liq kafolat: Xarid jarayonidan so'ng 25 kun davomida kafolat amal qiladi.\n 🔄 Kafolatlangan almashtirish: Agar obunada biror muammo chiqsa yoki faolsizlanib qolsa, o'rniga bir zumda yangisi taqdim etiladi.\n 💳 Bank kartasi shart emas: Linkni faollashtirish uchun Visa/Mastercard yoki boshqa bank kartalari ma'lumotlarini kiritish umuman talab qilinmaydi.\n ⚡ Oson faollashtirish: Havolani bosasiz va bir nechta soniyada obuna akkauntingizda ishga tushadi.", "✴️", 0, 1),
                (3, 3, "ChatGpt Plus (1 oylik)", 100000, "🛡️ To'liq kafolat: Akkaunt barqaror va kafolatlangan holda taqdim etiladi.\n 🔒 Taqiq va bloklanishsiz (No Ban): Akkauntdan foydalanish jarayonida muammolar yoki deaktivatsiya xavfi bo'lmaydi.\n 🚀 Maksimal barqarorlik: Har doim uzluksiz, tez va barqaror ishlaydigan tayyor akkaunt (Stable Account).", "💬", 0, 1),
                (4, 6, "CapCut PRO [7 kunlik]", 15000, "CapCut PRO obunasi 7 kunlik To'liq Garantiya!", "📹", 0, 1),
                (5, 6, "CapCut PRO [30 kunlik]", 42000, "CapCut PRO obunasi 30 kunlik To'liq Garantiya!", "📹", 0, 1),
                (6, 6, "CapCut PRO [3 oyliik]", 132000, "CapCut PRO obunasi 3 oylik To'liq Garantiya!", "📹", 0, 1),
                (7, 6, "CapCut PRO [6 oyliik]", 210000, "CapCut PRO obunasi 6 oylik To'liq Garantiya!", "📹", 0, 1),
                (8, 6, "CapCut PRO [1 yillik]", 370000, "CapCut PRO obunasi 1 yillik  To'liq Garantiya!", "📹", 0, 1),
                (9, 7, "Leoanardo Ai 8500 Cridet", 50000, "Leoanardo Ai 1 oylik obuna sizga 8500 cridet beriladi!", "💎", 0, 1)
            ]
            await d.executemany("INSERT INTO products (id, cat_id, title, price, description, emoji, sold, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", prods)
            
        await d.commit()

async def get_user(uid):
    return await q("SELECT * FROM users WHERE id=?", (uid,), one=True)

async def add_user(uid, name, uname, ref_by=None):
    u = await get_user(uid)
    if u: return u
    await q("INSERT INTO users(id,full_name,username,ref_code,ref_by,created_at) VALUES(?,?,?,?,?,?)",
            (uid, name, uname, "ref_" + secrets.token_hex(4), ref_by, int(time.time())), write=True)
    if ref_by:
        await q("UPDATE users SET refs=refs+1 WHERE id=?", (ref_by,), write=True)
    return await get_user(uid)

async def rating(pid):
    r = await q("SELECT AVG(rating) a, COUNT(*) c FROM reviews WHERE product_id=?", (pid,), one=True)
    return (round(r["a"], 1) if r["a"] else 5.0), r["c"]

def level_of(spent):
    name = LEVELS[0][1]
    for lim, t in LEVELS:
        if spent >= lim: name = t
    return name

def money(v):
    return "{:,}".format(v).replace(",", " ")

# =========================== KLAVIATURALAR ==========================
def main_menu(uid):
    kb = [
        [rb("srv"),  rb("ai")],
        [rb("cart"), rb("prof")],
        [rb("lang"), rb("cont")]
    ]
    if uid in ADMINS:
        kb.append([rb("adm"), rb("test")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=kb)

def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        ib("uz", "O'zbekcha", callback_data="lang:uz"),
        ib("ru", "Русский", callback_data="lang:ru")]])

def cats_kb(cats):
    b = InlineKeyboardBuilder()
    for c in cats:
        b.row(InlineKeyboardButton(text=f"{c['title']}", callback_data="cat:" + str(c["id"])))
    return b.as_markup()

def prods_kb(items, cid=0):
    b = InlineKeyboardBuilder()
    for p in items:
        label = f"{p['title']} - {money(p['price'])} {CURRENCY}"
        b.row(InlineKeyboardButton(text=label, callback_data="prod:" + str(p["id"])))
    b.row(ib("back", "Orqaga", callback_data="menu:cats"))
    return b.as_markup()

def prod_kb(pid, cid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("buy", "Sotib olish", callback_data="buy:" + str(pid))],
        [ib("cadd", "Savatchaga qo'shish", callback_data="cadd:" + str(pid))],
        [ib("back", "Orqaga", callback_data="cat:" + str(cid))]])

def admin_order_kb(oid):
    return InlineKeyboardMarkup(inline_keyboard=[[
        ib("ok", "Tasdiqlash", callback_data="ok:" + str(oid)),
        ib("no", "Rad etish", callback_data="no:" + str(oid))]])

def subs_kb(chs):
    b = InlineKeyboardBuilder()
    for ch in chs:
        ch_name = ch if not ch.startswith("-100") else f"Channel ({ch})"
        ch_url = f"https://t.me/{ch.lstrip('@')}" if ch.startswith("@") else None
        if ch_url:
            b.row(ib("sub", "Obuna bo'lish", url=ch_url))
        else:
             b.row(InlineKeyboardButton(text=f"📢 {ch_name}", callback_data="nothing"))
    b.row(ib("check", "A'zo bo'ldim", callback_data="chk"))
    return b.as_markup()

def contact_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("op", "Operatorga yozish", url="https://t.me/" + SUPPORT.lstrip("@"))],
        [ib("chan", "Rasmiy Kanalga o'tish", url=CHANNEL_URL)]])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("stats", "Statistika", callback_data="a:stats"),
         ib("pending", "Kutilayotgan", callback_data="a:orders")],
        [ib("plus", "Kategoriya +", callback_data="a:addcat"),
         ib("plus", "Mahsulot +", callback_data="a:addprod")],
        [ib("trash", "O'chirish", callback_data="a:delprod"),
         ib("bc", "Reklama yuborish", callback_data="a:bc")]])

# ============================== HOLATLAR ============================
class Buy(StatesGroup):
    receipt = State()

class Ai(StatesGroup):
    chat = State()

class Adm(StatesGroup):
    cat = State()
    prod = State()
    delete = State()
    broadcast = State()

class AdminDelivery(StatesGroup):
    waiting_for_link = State()

router = Router()

async def missing_subs(bot, uid):
    out = []
    for ch in FORCE_SUB:
        try:
            m = await bot.get_chat_member(ch, uid)
            if m.status in ("left", "kicked"):
                out.append(ch)
        except Exception as e:
            print(f"Sub check failed for {ch}: {e}")
            pass
    return out

# ============================== START ===============================
@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext, command: CommandObject, bot: Bot):
    await state.clear()
    ref_by = None
    if command.args and command.args.startswith("ref_"):
        r = await q("SELECT id FROM users WHERE ref_code=?", (command.args,), one=True)
        if r and r["id"] != msg.from_user.id:
            ref_by = r["id"]
    u = await get_user(msg.from_user.id)
    if not u:
        await add_user(msg.from_user.id, msg.from_user.full_name, msg.from_user.username, ref_by)
        await msg.answer("🌐 Tilni tanlang / Выберите язык:", reply_markup=lang_kb())
        return
    miss = await missing_subs(bot, msg.from_user.id)
    if miss:
        await msg.answer("🛑 <b>Botdan to'liq foydalanish uchun quyidagilarga obuna bo'lishingiz shart:</b>", reply_markup=subs_kb(miss))
        return
    await msg.answer("👋 Salom, <b>" + msg.from_user.full_name + "</b>!\n\nMenyudan kerakli bo'limni tanlang 👇",
                     reply_markup=main_menu(msg.from_user.id))

@router.callback_query(F.data.startswith("lang:"))
async def set_lang(c: CallbackQuery, bot: Bot):
    await q("UPDATE users SET lang=? WHERE id=?", (c.data.split(":")[1], c.from_user.id), write=True)
    await c.message.delete()
    miss = await missing_subs(bot, c.from_user.id)
    if miss:
        await c.message.answer("🛑 <b>Botdan to'liq foydalanish uchun quyidagilarga obuna bo'lishingiz shart:</b>", reply_markup=subs_kb(miss))
        return
    await c.message.answer("👋 Salom, <b>" + c.from_user.full_name + "</b>!\n\nMenyudan kerakli bo'limni tanlang 👇",
                           reply_markup=main_menu(c.from_user.id))

@router.callback_query(F.data == "chk")
async def check_sub(c: CallbackQuery, bot: Bot):
    if await missing_subs(bot, c.from_user.id):
        await c.answer("❌ Hali hamma joyga obuna bo'lmadingiz!", show_alert=True)
        return
    await c.message.delete()
    await c.message.answer("✅ Rahmat! Endi botdan to'liq foydalanishingiz mumkin.", reply_markup=main_menu(c.from_user.id))

# ========================== MENYU TUGMALARI =========================
@router.message(F.text.in_(BTN_ANY["srv"]))
async def services(msg: Message, state: FSMContext):
    await state.clear()
    cats = await q("SELECT * FROM categories WHERE is_active=1 ORDER BY id")
    if cats:
        txt = "📁 <b>Bo'limni tanlang:</b>\n\n"
        for c in cats:
            p_emo = PREMIUM_EMOJIS.get(c["id"], c["emoji"])
            txt += f"{p_emo} <b>{c['title']}</b>\n"
        txt += "\n👇 <i>Kerakli bo'limni pastdagi tugmalardan tanlang:</i>"
        
        await msg.answer(txt, reply_markup=cats_kb(cats))
        return
    items = await q("SELECT * FROM products WHERE is_active=1 ORDER BY id")
    if not items:
        await msg.answer("📭 Hozircha xizmatlar qo'shilmagan.")
        return
    await msg.answer("🛍 <b>Xizmatlar:</b>", reply_markup=prods_kb(items))

@router.message(F.text.in_(BTN_ANY["cart"]))
async def cart_show(msg: Message, state: FSMContext):
    await state.clear()
    items = await q("SELECT c.*, p.title, p.price, p.emoji FROM cart c "
                    "JOIN products p ON p.id=c.product_id WHERE c.user_id=?", (msg.from_user.id,))
    if not items:
        await msg.answer("🛒 Savatchangiz bo'sh.")
        return
    total = sum(i["price"] * i["qty"] for i in items)
    lines = [i["emoji"] + " " + i["title"] + " x " + str(i["qty"]) + " - " +
             money(i["price"] * i["qty"]) + " " + CURRENCY for i in items]
    b = InlineKeyboardBuilder()
    for i in items:
        b.row(ib("buy", "Sotib olish: " + i["title"], callback_data="buy:" + str(i["product_id"])))
    b.row(ib("trash", "Savatchani tozalash", callback_data="cclr"))
    await msg.answer("🛒 <b>Savatchangiz:</b>\n\n" + "\n".join(lines) +
                     "\n\n💰 Jami: <b>" + money(total) + " " + CURRENCY + "</b>",
                     reply_markup=b.as_markup())

@router.message(F.text.in_(BTN_ANY["prof"]))
async def profile(msg: Message, state: FSMContext, bot: Bot):
    await state.clear()
    u = await get_user(msg.from_user.id)
    me = await bot.get_me()
    link = "https://t.me/" + me.username + "?start=" + u["ref_code"]
    txt = ("👤 <b>Sizning profilingiz</b>\n\n"
           "🆔 ID: <code>" + str(u["id"]) + "</code>\n"
           "📦 Buyurtmalar: <b>" + str(u["orders_count"]) + "</b>\n"
           "💸 Jami sarflangan: <b>" + money(u["spent"]) + " " + CURRENCY + "</b>\n"
           "👥 Taklif etilganlar: <b>" + str(u["refs"]) + "</b>\n"
           "🔗 Taklif havolasi: " + link + "\n\n"
           "🎁 Bonus balansi: <b>" + money(u["balance"]) + " " + CURRENCY + "</b>\n"
           "🏆 Daraja: <b>" + level_of(u["spent"]) + "</b>\n"
           "💰 Jami keshbek: <b>" + money(u["cashback_total"]) + " " + CURRENCY + "</b>")
    kbd = InlineKeyboardMarkup(inline_keyboard=[[
        ib("orders", "Mening buyurtmalarim", callback_data="myorders")]])
    await msg.answer(txt, reply_markup=kbd, disable_web_page_preview=True)

@router.callback_query(F.data == "myorders")
async def my_orders(c: CallbackQuery):
    rows = await q("SELECT o.*, p.title FROM orders o LEFT JOIN products p ON p.id=o.product_id "
                   "WHERE o.user_id=? ORDER BY o.id DESC LIMIT 20", (c.from_user.id,))
    if not rows:
        await c.answer("Sizda buyurtmalar yo'q", show_alert=True)
        return
    names = {"pending": "⏳ kutilmoqda", "paid": "🔎 tekshiruvda", "approved": "✅ tasdiqlangan",
             "rejected": "❌ rad etilgan", "canceled": "🚫 bekor qilingan"}
    txt = "📋 <b>Buyurtmalaringiz:</b>\n\n" + "\n".join(
        "#" + str(o["id"]) + " | " + str(o["title"]) + " | " + names.get(o["status"], o["status"])
        for o in rows)
    await c.message.answer(txt)
    await c.answer()

@router.message(F.text.in_(BTN_ANY["lang"]))
async def change_lang(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("🌐 Tilni tanlang / Выберите язык:", reply_markup=lang_kb())

@router.message(F.text.in_(BTN_ANY["cont"]))
async def contact(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("📞 <b>Sifatli va tezkor xizmat markazi</b>\n\n"
                     "Biz bilan bog'lanish uchun tugmalardan foydalaning.", reply_markup=contact_kb())

@router.message(F.text.in_(BTN_ANY["ai"]))
async def ai_start(msg: Message, state: FSMContext):
    await state.set_state(Ai.chat)
    await msg.answer("🚀 AI Yordamchi sizga yordam beradi. Savolingizni yozing.\n(AI rejimidan chiqish uchun /cancel yozing)")

@router.message(Command("cancel"), Ai.chat)
async def ai_cancel(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Ajoyib, bot menyusiga qaytdingiz.", reply_markup=main_menu(msg.from_user.id))

@router.message(F.text.in_(BTN_ANY["test"]))
@router.message(Command("test_obuna"))
async def test_subscription_logic(msg: Message, bot: Bot, state: FSMContext):
    await state.clear()
    if msg.from_user.id not in ADMINS:
        return 

    status_text = "🔧 **Obuna holatini tekshirish:**\n\n"
    all_subscribed = True
    for chat in FORCE_SUB:
        try:
            member = await bot.get_chat_member(chat_id=chat, user_id=msg.from_user.id)
            status_returned = member.status
            if status_returned in ["member", "administrator", "creator"]:
                is_sub_check = "✅ A'zo"
            else:
                is_sub_check = "❌ A'zo emas"
                all_subscribed = False
            status_text += f"🔹 {chat}: <code>{status_returned}</code> ({is_sub_check})\n"
        except Exception as e:
            all_subscribed = False
            status_text += f"🔹 {chat}: ❌ Xatolik: <code>{str(e)}</code>\n"

    status_text += f"\n🏆 Yakuniy natija: "
    status_text += "✅ Hamma joyga obuna bo'lingan" if all_subscribed else "❌ Obuna to'liq emas"
    await msg.answer(status_text)

# ============================== KATALOG =============================
@router.callback_query(F.data == "menu:cats")
async def back_cats(c: CallbackQuery):
    cats = await q("SELECT * FROM categories WHERE is_active=1 ORDER BY id")
    if cats:
        txt = "📁 <b>Bo'limni tanlang:</b>\n\n"
        for cat in cats:
            p_emo = PREMIUM_EMOJIS.get(cat["id"], cat["emoji"])
            txt += f"{p_emo} <b>{cat['title']}</b>\n"
        txt += "\n👇 <i>Kerakli bo'limni pastdagi tugmalardan tanlang:</i>"
        
        await c.message.edit_text(txt, reply_markup=cats_kb(cats))
    else:
        items = await q("SELECT * FROM products WHERE is_active=1")
        await c.message.edit_text("🛍 <b>Xizmatlar:</b>", reply_markup=prods_kb(items))

@router.callback_query(F.data.startswith("cat:"))
async def open_cat(c: CallbackQuery):
    cid = int(c.data.split(":")[1])
    items = await q("SELECT * FROM products WHERE is_active=1 AND cat_id=? ORDER BY id", (cid,))
    cat_info = await q("SELECT * FROM categories WHERE id=?", (cid,), one=True)
    if not items:
        await c.answer("Bu bo'limda mahsulot yo'q", show_alert=True)
        return
        
    p_emo = PREMIUM_EMOJIS.get(cid, cat_info["emoji"] if cat_info else "📁")
    cat_title = cat_info["title"] if cat_info else "Xizmatlar"
    
    txt = f"{p_emo} <b>{cat_title} xizmatlari:</b>\n\n"
    for p in items:
        txt += f"▪️ <b>{p['title']}</b> — {money(p['price'])} {CURRENCY}\n"
    txt += "\n👇 <i>Kerakli mahsulotni tanlang:</i>"
    
    await c.message.edit_text(txt, reply_markup=prods_kb(items, cid))

@router.callback_query(F.data.startswith("prod:"))
async def open_prod(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    p = await q("SELECT * FROM products WHERE id=?", (pid,), one=True)
    p_emo = PREMIUM_EMOJIS.get(p["cat_id"], p["emoji"]) 
    
    rt, cnt = await rating(pid)
    txt = (f"{p_emo} <b>{p['title']}</b>\n\n"
           "💵 Narxi: <b>" + money(p['price']) + " " + CURRENCY + "</b>\n"
           "🔥 Sotilgan: <b>" + str(p['sold']) + " ta</b>\n\n"
           "📝 Tavsif:\n" + (p['description'] or "-") + "\n\n"
           "⭐ Reyting: " + str(rt) + "/5 (" + str(cnt) + " ta sharh)")
    await c.message.edit_text(txt, reply_markup=prod_kb(pid, p["cat_id"] or 0))

@router.callback_query(F.data.startswith("cadd:"))
async def cart_add(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    await q("INSERT INTO cart(user_id,product_id,qty) VALUES(?,?,1) "
            "ON CONFLICT(user_id,product_id) DO UPDATE SET qty=qty+1",
            (c.from_user.id, pid), write=True)
    await c.answer("✅ Savatchaga qo'shildi!", show_alert=True)

@router.callback_query(F.data == "cclr")
async def cart_clear(c: CallbackQuery):
    await q("DELETE FROM cart WHERE user_id=?", (c.from_user.id,), write=True)
    await c.message.edit_text("🗑 Savatcha tozalandi.")

# ============================ SOTIB OLISH ===========================
@router.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery, state: FSMContext):
    pid = int(c.data.split(":")[1])
    p = await q("SELECT * FROM products WHERE id=?", (pid,), one=True)
    u = await get_user(c.from_user.id)
    bonus = min(u["balance"], p["price"])
    topay = p["price"] - bonus
    oid = await q("INSERT INTO orders(user_id,product_id,price,used_bonus,created_at) VALUES(?,?,?,?,?)",
                  (c.from_user.id, pid, p["price"], bonus, int(time.time())), write=True)
    if bonus:
        await q("UPDATE users SET balance=balance-? WHERE id=?", (bonus, c.from_user.id), write=True)
    await state.set_state(Buy.receipt)
    await state.update_data(oid=oid)
    bl = ("🎁 Bonusdan yechildi: <b>" + money(bonus) + " " + CURRENCY + "</b>\n") if bonus else ""
    txt = ("💳 <b>" + p["title"] + "</b> uchun to'lov\n\n" + bl +
           "💸 To'lash kerak: <b>" + money(topay) + " " + CURRENCY + "</b>\n\n"
           "🏦 Rekvizitlar:\n<code>" + CARD_NUMBER + "</code>\n" + CARD_HOLDER + "\n\n"
           "📸 To'lovdan so'ng <b>chek rasmini shu yerga yuboring</b>.")
    kbd = InlineKeyboardMarkup(inline_keyboard=[[
        ib("cancel", "Bekor qilish", callback_data="cxl:" + str(oid))]])
    await c.message.edit_text(txt, reply_markup=kbd)

@router.callback_query(F.data.startswith("cxl:"))
async def cancel_order(c: CallbackQuery, state: FSMContext):
    oid = int(c.data.split(":")[1])
    o = await q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if o and o["status"] == "pending":
        await q("UPDATE orders SET status='canceled' WHERE id=?", (oid,), write=True)
        if o["used_bonus"]:
            await q("UPDATE users SET balance=balance+? WHERE id=?",
                    (o["used_bonus"], o["user_id"]), write=True)
    await state.clear()
    await c.message.edit_text("🚫 Buyurtma bekor qilindi.")

@router.message(Buy.receipt, F.photo | F.document)
async def receipt(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    oid = data.get("oid")
    fid = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    await q("UPDATE orders SET status='paid', receipt=? WHERE id=?", (fid, oid), write=True)
    await state.clear()
    o = await q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    p = await q("SELECT * FROM products WHERE id=?", (o["product_id"],), one=True)
    cap = ("🔔 <b>Yangi buyurtma #" + str(oid) + "</b>\n\n"
           "👤 Mijoz: " + msg.from_user.full_name + "\n"
           "🆔 ID: <code>" + str(msg.from_user.id) + "</code>\n"
           "📦 Mahsulot: " + p["title"] + "\n"
           "💰 Summa: " + money(o["price"]) + " " + CURRENCY)
    targets = [ADMIN_GROUP] if ADMIN_GROUP else ADMINS
    for t in targets:
        try:
            await bot.send_photo(t, fid, caption=cap, reply_markup=admin_order_kb(oid))
        except Exception:
            pass
    await msg.answer("✅ Chek qabul qilindi!\n\n⏳ Buyurtmangiz administrator tekshiruviga yuborildi.", reply_markup=main_menu(msg.from_user.id))

@router.message(Buy.receipt)
async def receipt_wrong(msg: Message):
    await msg.answer("⚠️ Iltimos, to'lov <b>chekining rasmini</b> yuboring.")

# ===================== ADMIN: TASDIQLASH VA YUBORISH ======================
@router.callback_query(F.data.startswith("ok:") | F.data.startswith("no:"))
async def moderate(c: CallbackQuery, state: FSMContext, bot: Bot):
    if c.from_user.id not in ADMINS:
        return
    act, sid = c.data.split(":")
    oid = int(sid)
    o = await q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if not o or o["status"] != "paid":
        await c.answer("Bu buyurtma allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    if act == "no":
        await q("UPDATE orders SET status='rejected' WHERE id=?", (oid,), write=True)
        if o["used_bonus"]:
            await q("UPDATE users SET balance=balance+? WHERE id=?", (o["used_bonus"], o["user_id"]), write=True)
        await bot.send_message(o["user_id"], "❌ Buyurtma #" + str(oid) + " rad etildi.\nSavollar bo'lsa: " + SUPPORT)
        await c.message.edit_caption(caption=(c.message.caption or "") + "\n\n❌ RAD ETILDI")
        return

    await state.set_state(AdminDelivery.waiting_for_link)
    await state.update_data(deliver_oid=oid, message_id=c.message.message_id)
    await c.message.reply(f"✅ <b>#{oid} to'lov tasdiqlanmoqda.</b>\n\n👇 Mijozga yuboriladigan <b>link, akkaunt yoki kalitni</b> shu yerga yozib yuboring:")
    await c.answer()

@router.message(AdminDelivery.waiting_for_link)
async def deliver_link_to_client(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    oid = data.get("deliver_oid")
    link_text = msg.text

    o = await q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if not o:
        await msg.answer("❌ Xatolik: Buyurtma topilmadi.")
        await state.clear()
        return

    p = await q("SELECT * FROM products WHERE id=?", (o["product_id"],), one=True)
    cb = o["price"] * CASHBACK // 100

    await q("UPDATE orders SET status='approved' WHERE id=?", (oid,), write=True)
    await q("UPDATE products SET sold=sold+1 WHERE id=?", (o["product_id"],), write=True)
    await q("UPDATE users SET orders_count=orders_count+1, spent=spent+?, balance=balance+?, cashback_total=cashback_total+? WHERE id=?",
            (o["price"], cb, cb, o["user_id"]), write=True)

    u = await get_user(o["user_id"])
    if u["ref_by"] and not u["ref_paid"]:
        await q("UPDATE users SET balance=balance+? WHERE id=?", (REF_BONUS, u["ref_by"]), write=True)
        await q("UPDATE users SET ref_paid=1 WHERE id=?", (u["id"],), write=True)
        try:
            await bot.send_message(u["ref_by"], f"🎁 Taklif qilgan do'stingiz xarid qildi! Hisobingizga <b>{money(REF_BONUS)} {CURRENCY}</b> bonus qo'shildi.")
        except: pass

    try:
        client_text = (
            f"🎉 <b>To'lovingiz tasdiqlandi (Buyurtma #{oid})</b>\n\n"
            f"📦 <b>{p['title']}</b>\n\n"
            f"<code>{link_text}</code>\n\n"
            f"💰 Keshbek: <b>{money(cb)} {CURRENCY}</b>\n"
            f"🤝 Xarid uchun rahmat!"
        )
        await bot.send_message(o["user_id"], client_text)
        await msg.answer("✅ Ma'lumot mijozga muvaffaqiyatli yuborildi!", reply_markup=main_menu(msg.from_user.id))
    except Exception as e:
        await msg.answer(f"❌ Mijozga yuborishda xatolik! Ehtimol mijoz botni bloklagan.")

    try:
        mid = data.get("message_id")
        await bot.edit_message_caption(chat_id=msg.chat.id, message_id=mid, caption=f"✅ TASDIQLANDI VA MIJOZGA YUBORILDI (Buyurtma #{oid})")
    except: pass

    await state.clear()

# ============================ ADMIN PANEL ===========================
@router.message(F.text.in_(BTN_ANY["adm"]))
@router.message(Command("admin"))
async def admin_panel(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMINS: return
    await state.clear()
    await msg.answer("🛠 <b>Admin panel</b>", reply_markup=admin_kb())

@router.callback_query(F.data.startswith("a:"))
async def admin_actions(c: CallbackQuery, state: FSMContext):
    if c.from_user.id not in ADMINS: return
    act = c.data.split(":")[1]
    if act == "stats":
        users = (await q("SELECT COUNT(*) c FROM users", one=True))["c"]
        appr = (await q("SELECT COUNT(*) c FROM orders WHERE status='approved'", one=True))["c"]
        rev = (await q("SELECT COALESCE(SUM(price),0) s FROM orders WHERE status='approved'", one=True))["s"]
        await c.message.answer(f"📊 <b>Statistika</b>\n\n👥 Foydalanuvchilar: {users}\n🔥 Sotuvlar: {appr}\n💰 Tushum: {money(rev)} {CURRENCY}")
    elif act == "orders":
        rows = await q("SELECT o.*, p.title FROM orders o LEFT JOIN products p ON p.id=o.product_id WHERE o.status='paid' ORDER BY o.id DESC LIMIT 20")
        if not rows:
            await c.answer("Tekshiruvdagi buyurtma yo'q", show_alert=True)
            return
        txt = "\n".join(f"#{o['id']} | {o['title']} | {money(o['price'])} | user {o['user_id']}" for o in rows)
        await c.message.answer(f"⏳ <b>Tekshiruvdagi buyurtmalar:</b>\n\n{txt}")
    elif act == "addcat":
        await state.set_state(Adm.cat)
        await c.message.answer("📝 Format: <code>emoji | nom</code>\nMasalan: <code>🤖 | AI xizmatlar</code>")
    elif act == "addprod":
        cats = await q("SELECT * FROM categories")
        lst = "\n".join(f"{x['id']} - {x['title']}" for x in cats) or "kategoriya yo'q (0 yozing)"
        await state.set_state(Adm.prod)
        await c.message.answer(f"📁 Kategoriyalar:\n{lst}\n\n📝 Format: <code>cat_id | emoji | nom | narx | tavsif</code>")
    elif act == "delprod":
        prods = await q("SELECT * FROM products WHERE is_active=1")
        lst = "\n".join(f"{x['id']} - {x['title']}" for x in prods) or "mahsulot yo'q"
        await state.set_state(Adm.delete)
        await c.message.answer(f"🗑 O'chiriladigan mahsulot ID sini yuboring:\n{lst}")
    elif act == "bc":
        await state.set_state(Adm.broadcast)
        await c.message.answer("📢 Tarqatiladigan xabarni yuboring (matn/rasm/video):")
    await c.answer()

@router.message(Adm.cat)
async def adm_cat(msg: Message, state: FSMContext):
    parts = [x.strip() for x in msg.text.split("|")]
    if len(parts) < 2:
        await msg.answer("❌ Format xato. emoji | nom")
        return
    await q("INSERT INTO categories(emoji,title) VALUES(?,?)", (parts[0], parts[1]), write=True)
    await state.clear()
    await msg.answer("✅ Kategoriya qo'shildi.", reply_markup=main_menu(msg.from_user.id))

@router.message(Adm.prod)
async def adm_prod(msg: Message, state: FSMContext):
    parts = [x.strip() for x in msg.text.split("|")]
    if len(parts) < 5:
        await msg.answer("❌ Format xato. cat_id | emoji | nom | narx | tavsif")
        return
    try:
        cid = int(parts[0])
        price = int(parts[3].replace(" ", ""))
    except ValueError:
        return await msg.answer("❌ cat_id va narx butun son bo'lishi kerak.")
    await q("INSERT INTO products(cat_id,emoji,title,price,description) VALUES(?,?,?,?,?)",
            (cid, parts[1], parts[2], price, "|".join(parts[4:])), write=True)
    await state.clear()
    await msg.answer("✅ Mahsulot qo'shildi.", reply_markup=main_menu(msg.from_user.id))

@router.message(Adm.delete)
async def adm_delete(msg: Message, state: FSMContext):
    try:
        pid = int(msg.text.strip())
    except ValueError:
        return await msg.answer("❌ Faqat raqam yuboring.")
    await q("UPDATE products SET is_active=0 WHERE id=?", (pid,), write=True)
    await state.clear()
    await msg.answer("✅ Mahsulot yashirildi.", reply_markup=main_menu(msg.from_user.id))

@router.message(Adm.broadcast)
async def adm_broadcast(msg: Message, state: FSMContext, bot: Bot):
    await state.clear()
    users = await q("SELECT id FROM users WHERE is_banned=0")
    ok = fail = 0
    for u in users:
        try:
            await bot.copy_message(chat_id=u["id"], from_chat_id=msg.chat.id, message_id=msg.message_id)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await msg.answer(f"✅ Yuborildi: {ok} ta, ❌ Xato: {fail} ta", reply_markup=main_menu(msg.from_user.id))

# ============================ AI YORDAMCHI (GEMINI) ==========================
@router.message(Ai.chat)
async def ai_chat(msg: Message):
    GEMINI_API_KEY = "AQ.Ab8RN6JwNyNSvtYRxvMxbeOfZt7rOCRd9ti923RubWVl3rMIaA"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    body = {
        "contents": [{
            "parts": [{"text": "Sen Obuna Hub raqamli mahsulotlar do'koni yordamchisisan. O'zbek tilida qisqa va aniq javob ber. Savol: " + msg.text}]
        }]
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=body, headers=headers, timeout=60) as r:
                data = await r.json()
                if "candidates" in data:
                    answer = data["candidates"][0]["content"]["parts"][0]["text"]
                    await msg.answer(answer)
                else:
                    await msg.answer("⚠️ AI hozircha javob berolmadi, birozdan keyin urinib ko'ring.")
    except Exception as e:
        await msg.answer("❌ Hozir javob berolmadim. Keyinroq urinib ko'ring.")

# ===================== KATEGORIYA O'CHIRISH =====================
@router.message(Command("delcat"))
async def delete_category(msg: Message):
    if msg.from_user.id not in ADMINS: return
    parts = msg.text.split()
    if len(parts) == 1:
        cats = await q("SELECT * FROM categories WHERE is_active=1")
        if not cats:
            return await msg.answer("📭 Hozircha kategoriyalar yo'q.")
        lst = "\n".join(f"{c['id']} - {c['title']}" for c in cats)
        await msg.answer(f"🗑 <b>Kategoriyani o'chirish uchun buyruq yoniga ID raqamini yozing:</b>\nMasalan: <code>/delcat 1</code>\n\n📁 <b>Mavjud kategoriyalar ro'yxati:</b>\n{lst}")
    elif len(parts) == 2 and parts[1].isdigit():
        cid = int(parts[1])
        await q("UPDATE categories SET is_active=0 WHERE id=?", (cid,), write=True)
        await msg.answer(f"✅ {cid}-ID raqamli bo'lim o'chirildi (yashirildi)!")

@router.message(Command("test_api"))
async def boshqa_botga_ulanish(msg: Message):
    await msg.answer("⏳ API dan javob kutilmoqda...")

# =============================== ISHGA TUSHIRISH ====================
from aiohttp import web

async def handle_ping(request):
    return web.Response(text="Bot 24/7 onlayn ishlamoqda!")

async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Bot ishga tushdi...")
    
    asyncio.create_task(dp.start_polling(bot))
    
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Bot to'xtatildi.")

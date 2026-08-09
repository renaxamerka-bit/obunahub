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
FORCE_SUB   = ["@YoutubeTekinDarslar"]
CHANNEL_URL = "https://t.me/obunahub_rasmiy"
SUPPORT     = "@XushvaqtovSh"
CURRENCY    = "so'm"
CASHBACK    = 3
REF_BONUS   = 100
LEVELS      = [(0, "Bronza"), (500000, "Kumush"), (2000000, "Oltin"), (5000000, "Platina")]
DB_PATH     = "obunahub.db"
AI_API_KEY  = os.getenv("AI_API_KEY", "")
AI_API_URL  = "https://api.openai.com/v1/chat/completions"
AI_MODEL    = "gpt-4o-mini"

# ============================== BAZA ================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, lang TEXT DEFAULT 'uz',
  balance INTEGER DEFAULT 0, cashback_total INTEGER DEFAULT 0, spent INTEGER DEFAULT 0,
  orders_count INTEGER DEFAULT 0, ref_code TEXT, ref_by INTEGER, refs INTEGER DEFAULT 0,
  ref_paid INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, created_at INTEGER);
CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, emoji TEXT DEFAULT 'C', is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cat_id INTEGER, title TEXT, price INTEGER,
  description TEXT, emoji TEXT DEFAULT 'P', sold INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS stock(
  id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, payload TEXT,
  is_sold INTEGER DEFAULT 0, order_id INTEGER);
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
        await d.commit()

async def get_user(uid):
    return await q("SELECT * FROM users WHERE id=?", (uid,), one=True)

async def add_user(uid, name, uname, ref_by=None):
    u = await get_user(uid)
    if u:
        return u
    await q("INSERT INTO users(id,full_name,username,ref_code,ref_by,created_at) VALUES(?,?,?,?,?,?)",
            (uid, name, uname, "ref_" + secrets.token_hex(4), ref_by, int(time.time())), write=True)
    if ref_by:
        await q("UPDATE users SET refs=refs+1 WHERE id=?", (ref_by,), write=True)
    return await get_user(uid)

async def stock_count(pid):
    r = await q("SELECT COUNT(*) c FROM stock WHERE product_id=? AND is_sold=0", (pid,), one=True)
    return r["c"]

async def take_stock(pid, oid):
    r = await q("SELECT * FROM stock WHERE product_id=? AND is_sold=0 LIMIT 1", (pid,), one=True)
    if not r:
        return None
    await q("UPDATE stock SET is_sold=1, order_id=? WHERE id=?", (oid, r["id"]), write=True)
    return r["payload"]

async def rating(pid):
    r = await q("SELECT AVG(rating) a, COUNT(*) c FROM reviews WHERE product_id=?", (pid,), one=True)
    return (round(r["a"], 1) if r["a"] else 5.0), r["c"]

def level_of(spent):
    name = LEVELS[0][1]
    for lim, t in LEVELS:
        if spent >= lim:
            name = t
    return name

def money(v):
    return "{:,}".format(v).replace(",", " ")

# =========================== KLAVIATURALAR ==========================
BTN = {"srv": "Xizmatlar", "ai": "AI Yordamchi", "cart": "Savatcha",
       "prof": "Profil", "lang": "Til", "cont": "Aloqa"}

def main_menu():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text=BTN["srv"]),  KeyboardButton(text=BTN["ai"])],
        [KeyboardButton(text=BTN["cart"]), KeyboardButton(text=BTN["prof"])],
        [KeyboardButton(text=BTN["lang"]), KeyboardButton(text=BTN["cont"])]])

def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="O'zbekcha", callback_data="lang:uz"),
        InlineKeyboardButton(text="Русский", callback_data="lang:ru")]])

def cats_kb(cats):
    b = InlineKeyboardBuilder()
    for c in cats:
        b.row(InlineKeyboardButton(text=c["emoji"] + " " + c["title"], callback_data="cat:" + str(c["id"])))
    return b.as_markup()

def prods_kb(items, cid=0):
    b = InlineKeyboardBuilder()
    for p in items:
        label = p["emoji"] + " " + p["title"] + " - " + money(p["price"]) + " " + CURRENCY
        b.row(InlineKeyboardButton(text=label, callback_data="prod:" + str(p["id"])))
    b.row(InlineKeyboardButton(text="Orqaga", callback_data="menu:cats"))
    return b.as_markup()

def prod_kb(pid, cid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Sotib olish", callback_data="buy:" + str(pid))],
        [InlineKeyboardButton(text="Savatchaga", callback_data="cadd:" + str(pid))],
        [InlineKeyboardButton(text="Orqaga", callback_data="cat:" + str(cid))]])

def admin_order_kb(oid):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Tasdiqlash", callback_data="ok:" + str(oid)),
        InlineKeyboardButton(text="Rad etish", callback_data="no:" + str(oid))]])

def subs_kb(chs):
    b = InlineKeyboardBuilder()
    for ch in chs:
        b.row(InlineKeyboardButton(text="📢 " + ch, url="https://t.me/" + ch.lstrip("@")))
    b.row(InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="chk"))
    return b.as_markup()

def contact_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Operatorga yozish", url="https://t.me/" + SUPPORT.lstrip("@"))],
        [InlineKeyboardButton(text="Kanalga o'tish", url=CHANNEL_URL)]])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Statistika", callback_data="a:stats"),
         InlineKeyboardButton(text="Kutilayotgan", callback_data="a:orders")],
        [InlineKeyboardButton(text="Kategoriya +", callback_data="a:addcat"),
         InlineKeyboardButton(text="Mahsulot +", callback_data="a:addprod")],
        [InlineKeyboardButton(text="Ombor +", callback_data="a:addstock"),
         InlineKeyboardButton(text="O'chirish", callback_data="a:delprod")],
        [InlineKeyboardButton(text="Reklama", callback_data="a:bc")]])

# ============================== HOLATLAR ============================
class Buy(StatesGroup):
    receipt = State()

class Ai(StatesGroup):
    chat = State()

class Adm(StatesGroup):
    cat = State()
    prod = State()
    stock_pid = State()
    stock_data = State()
    delete = State()
    broadcast = State()

router = Router()

async def missing_subs(bot, uid):
    out = []
    for ch in FORCE_SUB:
        try:
            m = await bot.get_chat_member(ch, uid)
            if m.status in ("left", "kicked"):
                out.append(ch)
        except Exception:
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
        await msg.answer("Tilni tanlang / Выберите язык:", reply_markup=lang_kb())
        return
    miss = await missing_subs(bot, msg.from_user.id)
    if miss:
        await msg.answer("🛑 <b>Botdan to'liq foydalanish uchun quyidagi kanallarga obuna bo'lishingiz shart:</b>", reply_markup=subs_kb(miss))
        return
    await msg.answer("Salom, <b>" + msg.from_user.full_name + "</b>!\n\nMenyudan tanlang.",
                     reply_markup=main_menu())

@router.callback_query(F.data.startswith("lang:"))
async def set_lang(c: CallbackQuery):
    await q("UPDATE users SET lang=? WHERE id=?", (c.data.split(":")[1], c.from_user.id), write=True)
    await c.message.delete()
    await c.message.answer("Salom, <b>" + c.from_user.full_name + "</b>!\n\nMenyudan tanlang.",
                           reply_markup=main_menu())

@router.callback_query(F.data == "chk")
async def check_sub(c: CallbackQuery, bot: Bot):
    if await missing_subs(bot, c.from_user.id):
        await c.answer("❌ Hali obuna bo'lmadingiz! Iltimos, kanalga a'zo bo'lib, keyin 'Tasdiqlash' tugmasini bosing.", show_alert=True)
        return
    await c.message.delete()
    await c.message.answer("Rahmat! Endi botdan foydalanishingiz mumkin.", reply_markup=main_menu())

# ========================== MENYU TUGMALARI =========================
@router.message(F.text == BTN["srv"])
async def services(msg: Message, state: FSMContext):
    await state.clear()
    cats = await q("SELECT * FROM categories WHERE is_active=1 ORDER BY id")
    if cats:
        await msg.answer("<b>Bo'limni tanlang:</b>", reply_markup=cats_kb(cats))
        return
    items = await q("SELECT * FROM products WHERE is_active=1 ORDER BY id")
    if not items:
        await msg.answer("Hozircha xizmatlar qo'shilmagan.")
        return
    await msg.answer("<b>Xizmatlar:</b>", reply_markup=prods_kb(items))

@router.message(F.text == BTN["cart"])
async def cart_show(msg: Message, state: FSMContext):
    await state.clear()
    items = await q("SELECT c.*, p.title, p.price, p.emoji FROM cart c "
                    "JOIN products p ON p.id=c.product_id WHERE c.user_id=?", (msg.from_user.id,))
    if not items:
        await msg.answer("Savatchangiz bo'sh.")
        return
    total = sum(i["price"] * i["qty"] for i in items)
    lines = [i["emoji"] + " " + i["title"] + " x " + str(i["qty"]) + " - " +
             money(i["price"] * i["qty"]) + " " + CURRENCY for i in items]
    b = InlineKeyboardBuilder()
    for i in items:
        b.row(InlineKeyboardButton(text="Sotib olish: " + i["title"],
                                   callback_data="buy:" + str(i["product_id"])))
    b.row(InlineKeyboardButton(text="Savatchani tozalash", callback_data="cclr"))
    await msg.answer("<b>Savatchangiz:</b>\n\n" + "\n".join(lines) +
                     "\n\nJami: <b>" + money(total) + " " + CURRENCY + "</b>",
                     reply_markup=b.as_markup())

@router.message(F.text == BTN["prof"])
async def profile(msg: Message, state: FSMContext, bot: Bot):
    await state.clear()
    u = await get_user(msg.from_user.id)
    if not u:
        u = await add_user(msg.from_user.id, msg.from_user.full_name, msg.from_user.username)
    me = await bot.get_me()
    link = "https://t.me/" + me.username + "?start=" + u["ref_code"]
    txt = ("<b>Sizning profilingiz</b>\n\n"
           "ID: <code>" + str(u["id"]) + "</code>\n"
           "Ism: " + str(u["full_name"]) + "\n"
           "Buyurtmalar: <b>" + str(u["orders_count"]) + "</b>\n"
           "Jami sarflangan: <b>" + money(u["spent"]) + " " + CURRENCY + "</b>\n"
           "Taklif etilganlar: <b>" + str(u["refs"]) + "</b>\n"
           "Taklif havolasi: " + link + "\n\n"
           "Bonus balansi: <b>" + money(u["balance"]) + " " + CURRENCY + "</b>\n"
           "Daraja: <b>" + level_of(u["spent"]) + "</b>\n"
           "Jami keshbek: <b>" + money(u["cashback_total"]) + " " + CURRENCY + "</b>")
    kbd = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Mening buyurtmalarim", callback_data="myorders")]])
    await msg.answer(txt, reply_markup=kbd, disable_web_page_preview=True)

@router.callback_query(F.data == "myorders")
async def my_orders(c: CallbackQuery):
    rows = await q("SELECT o.*, p.title FROM orders o LEFT JOIN products p ON p.id=o.product_id "
                   "WHERE o.user_id=? ORDER BY o.id DESC LIMIT 20", (c.from_user.id,))
    if not rows:
        await c.answer("Sizda buyurtmalar yo'q", show_alert=True)
        return
    names = {"pending": "kutilmoqda", "paid": "tekshiruvda", "approved": "tasdiqlangan",
             "rejected": "rad etilgan", "canceled": "bekor qilingan"}
    txt = "<b>Buyurtmalaringiz:</b>\n\n" + "\n".join(
        "#" + str(o["id"]) + " | " + str(o["title"]) + " | " + names.get(o["status"], o["status"])
        for o in rows)
    await c.message.answer(txt)
    await c.answer()

@router.message(F.text == BTN["lang"])
async def change_lang(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Tilni tanlang / Выберите язык:", reply_markup=lang_kb())

@router.message(F.text == BTN["cont"])
async def contact(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("<b>Sifatli va tezkor xizmat markazi</b>\n\n"
                     "Ish vaqti: 24/7\nO'rtacha javob vaqti: 5-15 daqiqa\n\n"
                     "Biz bilan bog'lanish uchun tugmalardan foydalaning.",
                     reply_markup=contact_kb())

@router.message(F.text == BTN["ai"])
async def ai_start(msg: Message, state: FSMContext):
    await state.set_state(Ai.chat)
    await msg.answer("AI Yordamchi sizga eng yaxshi xizmatni tanlashda yordam beradi. "
                     "Savolingizni yozing.")

# ============================== KATALOG =============================
@router.callback_query(F.data == "menu:cats")
async def back_cats(c: CallbackQuery):
    cats = await q("SELECT * FROM categories WHERE is_active=1 ORDER BY id")
    if cats:
        await c.message.edit_text("<b>Bo'limni tanlang:</b>", reply_markup=cats_kb(cats))
    else:
        items = await q("SELECT * FROM products WHERE is_active=1")
        await c.message.edit_text("<b>Xizmatlar:</b>", reply_markup=prods_kb(items))

@router.callback_query(F.data.startswith("cat:"))
async def open_cat(c: CallbackQuery):
    cid = int(c.data.split(":")[1])
    items = await q("SELECT * FROM products WHERE is_active=1 AND cat_id=? ORDER BY id", (cid,))
    if not items:
        await c.answer("Bu bo'limda mahsulot yo'q", show_alert=True)
        return
    await c.message.edit_text("<b>Xizmatlar:</b>", reply_markup=prods_kb(items, cid))

@router.callback_query(F.data.startswith("prod:"))
async def open_prod(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    p = await q("SELECT * FROM products WHERE id=?", (pid,), one=True)
    st = await stock_count(pid)
    rt, cnt = await rating(pid)
    txt = (p["emoji"] + " <b>" + p["title"] + "</b>\n\n"
           "Narxi: <b>" + money(p["price"]) + " " + CURRENCY + "</b>\n"
           "Omborda: <b>" + str(st) + " ta</b>\n"
           "Sotilgan: <b>" + str(p["sold"]) + " ta</b>\n\n"
           "Tavsif:\n" + (p["description"] or "-") + "\n\n"
           "Reyting: " + str(rt) + "/5 (" + str(cnt) + " ta sharh)")
    await c.message.edit_text(txt, reply_markup=prod_kb(pid, p["cat_id"] or 0))

@router.callback_query(F.data.startswith("cadd:"))
async def cart_add(c: CallbackQuery):
    pid = int(c.data.split(":")[1])
    await q("INSERT INTO cart(user_id,product_id,qty) VALUES(?,?,1) "
            "ON CONFLICT(user_id,product_id) DO UPDATE SET qty=qty+1",
            (c.from_user.id, pid), write=True)
    await c.answer("Savatchaga qo'shildi!", show_alert=True)

@router.callback_query(F.data == "cclr")
async def cart_clear(c: CallbackQuery):
    await q("DELETE FROM cart WHERE user_id=?", (c.from_user.id,), write=True)
    await c.message.edit_text("Savatcha tozalandi.")

# ============================ SOTIB OLISH ===========================
@router.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery, state: FSMContext):
    pid = int(c.data.split(":")[1])
    p = await q("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if await stock_count(pid) <= 0:
        await c.answer("Bu mahsulot omborda tugagan.", show_alert=True)
        return
    u = await get_user(c.from_user.id)
    bonus = min(u["balance"], p["price"])
    topay = p["price"] - bonus
    oid = await q("INSERT INTO orders(user_id,product_id,price,used_bonus,created_at) VALUES(?,?,?,?,?)",
                  (c.from_user.id, pid, p["price"], bonus, int(time.time())), write=True)
    if bonus:
        await q("UPDATE users SET balance=balance-? WHERE id=?", (bonus, c.from_user.id), write=True)
    await state.set_state(Buy.receipt)
    await state.update_data(oid=oid)
    bl = ("Bonusdan yechildi: <b>" + money(bonus) + " " + CURRENCY + "</b>\n") if bonus else ""
    txt = ("<b>" + p["title"] + "</b> uchun to'lov\n\n" + bl +
           "To'lash kerak: <b>" + money(topay) + " " + CURRENCY + "</b>\n\n"
           "Rekvizitlar:\n<code>" + CARD_NUMBER + "</code>\n" + CARD_HOLDER + "\n\n"
           "To'lovdan so'ng <b>chek rasmini shu yerga yuboring</b>.")
    kbd = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Bekor qilish", callback_data="cxl:" + str(oid))]])
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
    await c.message.edit_text("Buyurtma bekor qilindi.")

@router.message(Buy.receipt, F.photo | F.document)
async def receipt(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    oid = data.get("oid")
    fid = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    await q("UPDATE orders SET status='paid', receipt=? WHERE id=?", (fid, oid), write=True)
    await state.clear()
    o = await q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    p = await q("SELECT * FROM products WHERE id=?", (o["product_id"],), one=True)
    cap = ("<b>Yangi buyurtma #" + str(oid) + "</b>\n\n"
           "Foydalanuvchi: " + msg.from_user.full_name + " (@" + str(msg.from_user.username) + ")\n"
           "ID: <code>" + str(msg.from_user.id) + "</code>\n"
           "Mahsulot: " + p["title"] + "\n"
           "Summa: " + money(o["price"]) + " " + CURRENCY)
    targets = [ADMIN_GROUP] if ADMIN_GROUP else ADMINS
    for t in targets:
        try:
            await bot.send_photo(t, fid, caption=cap, reply_markup=admin_order_kb(oid))
        except Exception as e:
            logging.warning(e)
    await msg.answer("Chek qabul qilindi!\n\nBuyurtmangiz <b>#" + str(oid) +
                     "</b> administrator tekshiruviga yuborildi.", reply_markup=main_menu())

@router.message(Buy.receipt)
async def receipt_wrong(msg: Message):
    await msg.answer("Iltimos, to'lov <b>chekining rasmini</b> yuboring.")

# ===================== ADMIN: TASDIQLASH / RAD ======================
@router.callback_query(F.data.startswith("ok:") | F.data.startswith("no:"))
async def moderate(c: CallbackQuery, bot: Bot):
    if c.from_user.id not in ADMINS:
        await c.answer("Ruxsat yo'q", show_alert=True)
        return
    act, sid = c.data.split(":")
    oid = int(sid)
    o = await q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if not o or o["status"] != "paid":
        await c.answer("Bu buyurtma allaqachon ko'rib chiqilgan.", show_alert=True)
        return
    p = await q("SELECT * FROM products WHERE id=?", (o["product_id"],), one=True)

    if act == "no":
        await q("UPDATE orders SET status='rejected' WHERE id=?", (oid,), write=True)
        if o["used_bonus"]:
            await q("UPDATE users SET balance=balance+? WHERE id=?",
                    (o["used_bonus"], o["user_id"]), write=True)
        await bot.send_message(o["user_id"], "Buyurtma #" + str(oid) +
                               " rad etildi.\nSavollar bo'lsa: " + SUPPORT)
        await c.message.edit_caption(caption=(c.message.caption or "") + "\n\nRAD ETILDI")
        return

    payload = await take_stock(o["product_id"], oid)
    if not payload:
        await c.answer("Omborda mahsulot qolmagan! Avval ombor to'ldiring.", show_alert=True)
        return
    cb = o["price"] * CASHBACK // 100
    await q("UPDATE orders SET status='approved' WHERE id=?", (oid,), write=True)
    await q("UPDATE products SET sold=sold+1 WHERE id=?", (o["product_id"],), write=True)
    await q("UPDATE users SET orders_count=orders_count+1, spent=spent+?, balance=balance+?, "
            "cashback_total=cashback_total+? WHERE id=?",
            (o["price"], cb, cb, o["user_id"]), write=True)
    u = await get_user(o["user_id"])
    if u["ref_by"] and not u["ref_paid"]:
        await q("UPDATE users SET balance=balance+? WHERE id=?", (REF_BONUS, u["ref_by"]), write=True)
        await q("UPDATE users SET ref_paid=1 WHERE id=?", (u["id"],), write=True)
        try:
            await bot.send_message(u["ref_by"], "Taklif qilgan do'stingiz xarid qildi! Hisobingizga <b>" +
                                   money(REF_BONUS) + " " + CURRENCY + "</b> bonus qo'shildi.")
        except Exception:
            pass
    await bot.send_message(o["user_id"],
                           "Buyurtma <b>#" + str(oid) + "</b> tasdiqlandi!\n\n" +
                           "<b>" + p["title"] + "</b>\n\n<code>" + payload + "</code>\n\n" +
                           "Keshbek: <b>" + money(cb) + " " + CURRENCY + "</b>\n"
                           "Muammo bo'lsa: " + SUPPORT)
    await c.message.edit_caption(caption=(c.message.caption or "") + "\n\nTASDIQLANDI")

# ============================ ADMIN PANEL ===========================
@router.message(Command("admin"))
async def admin_panel(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        return
    await state.clear()
    await msg.answer("<b>Admin panel</b>", reply_markup=admin_kb())

@router.callback_query(F.data.startswith("a:"))
async def admin_actions(c: CallbackQuery, state: FSMContext):
    if c.from_user.id not in ADMINS:
        await c.answer("Ruxsat yo'q", show_alert=True)
        return
    act = c.data.split(":")[1]
    if act == "stats":
        users = (await q("SELECT COUNT(*) c FROM users", one=True))["c"]
        appr = (await q("SELECT COUNT(*) c FROM orders WHERE status='approved'", one=True))["c"]
        pend = (await q("SELECT COUNT(*) c FROM orders WHERE status='paid'", one=True))["c"]
        rev = (await q("SELECT COALESCE(SUM(price),0) s FROM orders WHERE status='approved'", one=True))["s"]
        prods = (await q("SELECT COUNT(*) c FROM products WHERE is_active=1", one=True))["c"]
        await c.message.answer("<b>Statistika</b>\n\nFoydalanuvchilar: " + str(users) +
                               "\nSotuvlar: " + str(appr) + "\nTekshiruvda: " + str(pend) +
                               "\nTushum: " + money(rev) + " " + CURRENCY +
                               "\nMahsulotlar: " + str(prods))
    elif act == "orders":
        rows = await q("SELECT o.*, p.title FROM orders o LEFT JOIN products p ON p.id=o.product_id "
                       "WHERE o.status='paid' ORDER BY o.id DESC LIMIT 20")
        if not rows:
            await c.answer("Tekshiruvdagi buyurtma yo'q", show_alert=True)
            return
        txt = "\n".join("#" + str(o["id"]) + " | " + str(o["title"]) + " | " +
                        money(o["price"]) + " | user " + str(o["user_id"]) for o in rows)
        await c.message.answer("<b>Tekshiruvdagi buyurtmalar:</b>\n\n" + txt)
    elif act == "addcat":
        await state.set_state(Adm.cat)
        await c.message.answer("Format: <code>emoji | nom</code>\nMasalan: <code>AI | AI xizmatlar</code>")
    elif act == "addprod":
        cats = await q("SELECT * FROM categories")
        lst = "\n".join(str(x["id"]) + " - " + x["title"] for x in cats) or "kategoriya yo'q (0 yozing)"
        await state.set_state(Adm.prod)
        await c.message.answer("Kategoriyalar:\n" + lst +
                               "\n\nFormat: <code>cat_id | emoji | nom | narx | tavsif</code>")
    elif act == "addstock":
        prods = await q("SELECT * FROM products WHERE is_active=1")
        lst = "\n".join(str(x["id"]) + " - " + x["title"] for x in prods) or "mahsulot yo'q"
        await state.set_state(Adm.stock_pid)
        await c.message.answer("Mahsulotlar:\n" + lst + "\n\nMahsulot ID sini yuboring:")
    elif act == "delprod":
        prods = await q("SELECT * FROM products WHERE is_active=1")
        lst = "\n".join(str(x["id"]) + " - " + x["title"] for x in prods) or "mahsulot yo'q"
        await state.set_state(Adm.delete)
        await c.message.answer("O'chiriladigan mahsulot ID sini yuboring:\n" + lst)
    elif act == "bc":
        await state.set_state(Adm.broadcast)
        await c.message.answer("Tarqatiladigan xabarni yuboring (matn/rasm/video):")
    await c.answer()

@router.message(Adm.cat)
async def adm_cat(msg: Message, state: FSMContext):
    parts = [x.strip() for x in msg.text.split("|")]
    if len(parts) < 2:
        await msg.answer("Format xato. emoji | nom")
        return
    await q("INSERT INTO categories(emoji,title) VALUES(?,?)", (parts[0], parts[1]), write=True)
    await state.clear()
    await msg.answer("Kategoriya qo'shildi.", reply_markup=main_menu())

@router.message(Adm.prod)
async def adm_prod(msg: Message, state: FSMContext):
    parts = [x.strip() for x in msg.text.split("|")]
    if len(parts) < 5:
        await msg.answer("Format xato. cat_id | emoji | nom | narx | tavsif")
        return
    try:
        cid = int(parts[0])
        price = int(parts[3].replace(" ", ""))
    except ValueError:
        await msg.answer("cat_id va narx butun son bo'lishi kerak.")
        return
    await q("INSERT INTO products(cat_id,emoji,title,price,description) VALUES(?,?,?,?,?)",
            (cid, parts[1], parts[2], price, "|".join(parts[4:])), write=True)
    await state.clear()
    await msg.answer("Mahsulot qo'shildi.", reply_markup=main_menu())

@router.message(Adm.stock_pid)
async def adm_stock_pid(msg: Message, state: FSMContext):
    try:
        pid = int(msg.text.strip())
    except ValueError:
        await msg.answer("Faqat raqam yuboring.")
        return
    await state.update_data(pid=pid)
    await state.set_state(Adm.stock_data)
    await msg.answer("Endi akkaunt/kalitlarni yuboring. Har biri yangi qatorda.")

@router.message(Adm.stock_data)
async def adm_stock_data(msg: Message, state: FSMContext):
    data = await state.get_data()
    pid = data["pid"]
    lines = [x.strip() for x in msg.text.split("\n") if x.strip()]
    for item in lines:
        await q("INSERT INTO stock(product_id,payload) VALUES(?,?)", (pid, item), write=True)
    await state.clear()
    await msg.answer("Omborga " + str(len(lines)) + " ta qo'shildi.", reply_markup=main_menu())

@router.message(Adm.delete)
async def adm_delete(msg: Message, state: FSMContext):
    try:
        pid = int(msg.text.strip())
    except ValueError:
        await msg.answer("Faqat raqam yuboring.")
        return
    await q("UPDATE products SET is_active=0 WHERE id=?", (pid,), write=True)
    await state.clear()
    await msg.answer("Mahsulot yashirildi.", reply_markup=main_menu())

@router.message(Adm.broadcast)
async def adm_broadcast(msg: Message, state: FSMContext, bot: Bot):
    await state.clear()
    users = await q("SELECT id FROM users WHERE is_banned=0")
    ok = 0
    fail = 0
    for u in users:
        try:
            await bot.copy_message(chat_id=u["id"], from_chat_id=msg.chat.id, message_id=msg.message_id)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await msg.answer("Yuborildi: " + str(ok) + " ta, xato: " + str(fail) + " ta",
                     reply_markup=main_menu())

# ============================ AI YORDAMCHI ==========================
@router.message(Ai.chat)
async def ai_chat(msg: Message):
    if not AI_API_KEY:
        await msg.answer("AI yordamchi hozircha sozlanmagan. Operator: " + SUPPORT)
        return
    prompt = ("Sen Obuna Hub raqamli mahsulotlar do'koni yordamchisisan. "
              "O'zbek tilida qisqa va aniq javob ber.")
    body = {"model": AI_MODEL,
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": msg.text}]}
    headers = {"Authorization": "Bearer " + AI_API_KEY, "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(AI_API_URL, json=body, headers=headers, timeout=60) as r:
                data = await r.json()
        await msg.answer(data["choices"][0]["message"]["content"])
    except Exception as e:
        logging.warning(e)
        await msg.answer("Hozir javob berolmadim. Keyinroq urinib ko'ring.")
# ===================== KATEGORIYA O'CHIRISH =====================
@router.message(Command("delcat"))
async def delete_category(msg: Message):
    if msg.from_user.id not in ADMINS:
        return
    parts = msg.text.split()
    if len(parts) == 1:
        cats = await q("SELECT * FROM categories WHERE is_active=1")
        if not cats:
            await msg.answer("📭 Hozircha kategoriyalar yo'q.")
            return
        lst = "\n".join(f"{c['id']} - {c['title']}" for c in cats)
        await msg.answer(f"🗑 <b>Kategoriyani o'chirish uchun buyruq yoniga ID raqamini yozing:</b>\nMasalan: <code>/delcat 1</code>\n\n📁 <b>Mavjud kategoriyalar ro'yxati:</b>\n{lst}")
    elif len(parts) == 2 and parts[1].isdigit():
        cid = int(parts[1])
        await q("UPDATE categories SET is_active=0 WHERE id=?", (cid,), write=True)
        await msg.answer(f"✅ {cid}-ID raqamli bo'lim o'chirildi (yashirildi)!")
      # ... (Sizdagi oldingi kodlar, AI yordamchi va hokazo) ...

# YANGI API KODINGIZ SHU YERGA TUSHADI 👇
@router.message(Command("test_api"))
async def boshqa_botga_ulanish(msg: Message):
    # API ga ulanish amallari...
    await msg.answer("API dan javob kutilmoqda...")

# =============================== 🚀 ISHGA TUSHIRISH ====================
from aiohttp import web

async def handle_ping(request):
# ... (qolgan ishga tushirish kodlari) ...
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
    
    # 1. Botni orqa fonda ishga tushirish (Polling)
    asyncio.create_task(dp.start_polling(bot))
    
    # 2. Render tekinga ishlashi uchun soxta veb-server yaratamiz
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render o'zi beradigan PORT ni olamiz (yo'q bo'lsa 8080)
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    # 3. Dastur to'xtab qolmasligi uchun aylana jarayon
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Bot to'xtatildi.")

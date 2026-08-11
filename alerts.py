import os, asyncio, logging, aiohttp
from datetime import datetime
from zoneinfo import ZoneInfo

ALERT_TOKEN = os.getenv("ALERT_BOT_TOKEN", "")
ALERT_CHAT = os.getenv("ALERT_CHAT", "@obunalarhub_guruh")
TZ = ZoneInfo("Asia/Tashkent")
log = logging.getLogger("alerts")


def mask(uid) -> str:
    s = str(uid)
    return f"{s[:3]}***{s[-3:]}" if len(s) > 6 else s


def now() -> str:
    return datetime.now(TZ).strftime("%d-%b-%Y %H:%M")


async def _post(text: str):
    if not ALERT_TOKEN:
        log.warning("ALERT_BOT_TOKEN berilmagan - alert yuborilmadi")
        return
    url = f"https://api.telegram.org/bot{ALERT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ALERT_CHAT,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            r = await s.post(url, json=payload)
            if r.status != 200:
                log.warning("ALERT XATO %s -> %s", r.status, await r.text())
            else:
                log.info("alert yuborildi")
    except Exception as e:
        log.warning("alert failed: %s", e)


def fire(text: str):
    """Fon rejimida yuboradi - savdo oqimini bloklamaydi."""
    try:
        asyncio.get_running_loop().create_task(_post(text))
    except RuntimeError:
        asyncio.run(_post(text))


def purchase(uid, title, total, oid, username=None):
    who = f"@{username}" if username else "-"
    fire(
        "<blockquote>\U0001F389 <b>YANGI SOTUV!</b>\n\n"
        f"\U0001F680 <b>Xaridor:</b> <code>{mask(uid)}</code>\n"
        f"\U0001F464 <b>Username:</b> {who}\n"
        f"\U0001F4A0 <b>Mahsulot:</b> {title}\n"
        f"\U0001F4B5 <b>Summa:</b> {total:,} so'm\n"
        f"\U0001F9FE <b>Buyurtma:</b> #{oid}\n"
        f"\U0001F4C5 <b>Vaqt:</b> {now()}</blockquote>"
    )


def new_user(uid):
    fire(
        "<blockquote>\U0001F464 <b>Yangi foydalanuvchi!</b>\n\n"
        f"\U0001F194 <b>ID:</b> <code>{mask(uid)}</code>\n"
        f"\U0001F4C5 <b>Vaqt:</b> {now()}</blockquote>"
    )


def stock_out(name):
    fire(
        "<blockquote>\U0001F6AB <b>Mahsulot tugadi!</b>\n\n"
        f"\U0001F4A0 <b>Nomi:</b> {name}\n"
        f"\U0001F4C5 <b>Vaqt:</b> {now()}</blockquote>"
    )


def test():
    fire(f"<blockquote>\u2705 <b>Test alert</b>\n\U0001F4C5 {now()}</blockquote>")

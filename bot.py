import random
import httpx
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

def luhn_complete(prefix: str) -> str:
    digits_needed = 15 - len(prefix)
    middle = ''.join([str(random.randint(0, 9)) for _ in range(digits_needed)])
    partial = prefix + middle
    total = 0
    for i, d in enumerate(reversed(partial)):
        n = int(d)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    check = (10 - (total % 10)) % 10
    return partial + str(check)

def gen_cvv(cvv=None):
    return cvv if cvv else str(random.randint(100, 999))

def is_random(val: str) -> bool:
    if not val:
        return True
    v = val.lower().strip()
    return 'x' in v or v == 'rnd'

def parse_input(raw: str):
    parts = raw.strip().split('|')
    card_part = parts[0].replace('x', '').replace('X', '')
    month = None if len(parts) <= 1 or is_random(parts[1]) else parts[1]
    year  = None if len(parts) <= 2 or is_random(parts[2]) else parts[2]
    cvv   = None if len(parts) <= 3 or is_random(parts[3]) else parts[3]
    return card_part, month, year, cvv

async def bin_lookup(bin: str) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://bins.antipublic.cc/bins/{bin}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        print(f"Error BIN: {e}")
    return {}

async def handle_gen(update: Update, context: ContextTypes.DEFAULT_TYPE, arg: str):
    raw = arg.strip()
    prefix, month, year, cvv = parse_input(raw)

    if len(prefix) > 15:
        await update.message.reply_text("El prefijo es demasiado largo (máx 15 dígitos).")
        return

    cards = []
    for _ in range(10):
        card = luhn_complete(prefix)
        m = month if month else str(random.randint(1, 12)).zfill(2)
        y = year if year else str(random.randint(2025, 2030))
        c = gen_cvv(cvv)
        cards.append(f"{card}|{m}|{y}|{c}")

    bin6 = prefix[:6]
    info = await bin_lookup(bin6)

    scheme  = (info.get("brand") or "Unknown").upper()
    tipo    = (info.get("type") or "Unknown").upper()
    brand   = (info.get("level") or "Unknown")
    bank    = (info.get("bank") or "Unknown")
    country = (info.get("country_name") or "Unknown").title()
    emoji   = (info.get("country_flag") or "")

    user = update.message.from_user
    username = f"@{user.username}" if user.username else user.first_name

    cards_text = "\n".join(f"<code>{c}</code>" for c in cards)

    msg = (
        f"[✓] - <b>Generator Card</b>\n"
        f"↳ <b>Bin:</b> <code>{raw}</code>\n"
        f"··············\n\n"
        f"{cards_text}\n\n"
        f"··············\n"
        f"# <b>Info:</b> {scheme} - {tipo} - {brand}\n"
        f"# <b>Bank:</b> {bank}\n"
        f"# <b>Country:</b> {country} {emoji}\n"
        f"··············\n"
        f"<b>Gen by:</b> {username} → [User]"
    )

    await update.message.reply_text(msg, parse_mode="HTML")

async def gen_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /gen 818372xxxxxxxxxx|MM|YYYY|CVV")
        return
    await handle_gen(update, context, context.args[0])

async def gen_dot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.startswith(".gen"):
        return
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("Uso: .gen 818372xxxxxxxxxx|MM|YYYY|CVV")
        return
    await handle_gen(update, context, parts[1])

app = ApplicationBuilder().token(os.getenv("TOKEN")).build()
app.add_handler(CommandHandler("gen", gen_slash))
app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^\.gen'), gen_dot))
app.run_polling()
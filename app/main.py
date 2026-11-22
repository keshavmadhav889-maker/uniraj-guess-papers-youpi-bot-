import asyncio
import logging
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uniraj-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
DB_PATH = os.getenv("DATABASE_PATH", "/data/uniraj.sqlite3")
PAPERS_DIR = Path(os.getenv("PAPERS_DIR", "/data/papers"))
PAYMENT_MODE = os.getenv("PAYMENT_MODE", "disabled").lower()
PAPERS_DIR.mkdir(parents=True, exist_ok=True)
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

api = FastAPI(title="UNIRAJ Guess Papers Bot")
bot_app: Application | None = None
pending_uploads: set[int] = set()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT NOT NULL, semester TEXT NOT NULL, subject TEXT NOT NULL,
            paper TEXT NOT NULL, price_paise INTEGER NOT NULL,
            file_path TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, paper_id INTEGER NOT NULL,
            amount_paise INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
            provider_payment_id TEXT UNIQUE, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(paper_id) REFERENCES papers(id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS delivered (
            order_id INTEGER PRIMARY KEY, delivered_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")


def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Buy Guess Papers", callback_data="buy")],
        [InlineKeyboardButton("🔎 Search", callback_data="search"),
         InlineKeyboardButton("🧾 My Orders", callback_data="orders")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help"),
         InlineKeyboardButton("About", callback_data="about")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "नमस्ते! UNIRAJ GUESS PAPERS में आपका स्वागत है।\n"
        "यहाँ केवल Rajasthan University Guess Papers उपलब्ध होंगे।",
        reply_markup=menu()
    )


async def show_papers(target, query: str = ""):
    with db() as c:
        if query:
            rows = c.execute(
                "SELECT * FROM papers WHERE active=1 AND "
                "(course LIKE ? OR semester LIKE ? OR subject LIKE ? OR paper LIKE ?) ORDER BY id DESC LIMIT 30",
                tuple([f"%{query}%"] * 4)
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM papers WHERE active=1 ORDER BY course, semester, subject LIMIT 30").fetchall()
    if not rows:
        await target.reply_text("अभी कोई Guess Paper सूची में नहीं है। Admin जल्द ही उपलब्ध कराएँगे।")
        return
    for p in rows:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            f"Buy • ₹{p['price_paise']/100:.2f}", callback_data=f"buy_{p['id']}"
        )]])
        await target.reply_text(
            f"📘 {p['course']} | Semester {p['semester']}\n"
            f"विषय: {p['subject']}\nपेपर: {p['paper']}\nकीमत: ₹{p['price_paise']/100:.2f}",
            reply_markup=kb
        )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "buy":
        await show_papers(q.message)
    elif q.data == "search":
        context.user_data["searching"] = True
        await q.message.reply_text("Course, Semester या Subject का नाम लिखकर भेजें।")
    elif q.data == "orders":
        with db() as c:
            rows = c.execute("SELECT id, amount_paise, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20",
                             (q.from_user.id,)).fetchall()
        msg = "\n".join([f"#{r['id']} • ₹{r['amount_paise']/100:.2f} • {r['status']}" for r in rows])
        await q.message.reply_text(msg or "आपका अभी कोई Order नहीं है।")
    elif q.data == "help":
        await q.message.reply_text("Buy से पेपर चुनें। भुगतान सुविधा Gateway की सुरक्षा जाँच और सेटअप के बाद ही चालू होगी। सहायता के लिए Admin से संपर्क करें।")
    elif q.data == "about":
        await q.message.reply_text("UNIRAJ GUESS PAPERS — Rajasthan University Guess Papers का कैटलॉग और ऑर्डर सिस्टम।")
    elif q.data.startswith("buy_"):
        paper_id = int(q.data.split("_", 1)[1])
        with db() as c:
            p = c.execute("SELECT * FROM papers WHERE id=? AND active=1", (paper_id,)).fetchone()
            if not p:
                await q.message.reply_text("यह पेपर उपलब्ध नहीं है।")
                return
            cur = c.execute("INSERT INTO orders(user_id,paper_id,amount_paise,status) VALUES(?,?,?,'PENDING')",
                            (q.from_user.id, paper_id, p["price_paise"]))
            order_id = cur.lastrowid
        await q.message.reply_text(
            f"Order #{order_id} बनाया गया है।\n"
            "Payment अभी बंद है: YouPI PG को उसके experimental/production-risk notice के कारण Live payment के लिए enable नहीं किया गया है। "
            "पेमेंट सत्यापन उपलब्ध होने तक कोई भुगतान न करें।"
        )


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "Admin commands:\n/addpaper — फिर PDF भेजें और caption में लिखें:\n"
        "Course | Semester | Subject | Paper | Price(INR)\n"
        "/papers — catalog\n/orders — recent orders\n"
        "उदाहरण: BSc PCM | 3 | Physics | Optics | 49"
    )
    pending_uploads.add(update.effective_user.id)


async def admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or update.effective_user.id not in pending_uploads:
        return
    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("कृपया PDF document भेजें।")
        return
    parts = (update.message.caption or "").split("|")
    if len(parts) != 5:
        await update.message.reply_text("PDF के caption में यह format लिखें: Course | Semester | Subject | Paper | Price")
        return
    course, sem, subject, paper, price = [x.strip() for x in parts]
    try:
        price_paise = int(round(float(price) * 100))
        if price_paise < 100:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("कीमत सही लिखें, जैसे 49 या 49.50")
        return
    tg_file = await context.bot.get_file(doc.file_id)
    safe_name = f"paper_{doc.file_unique_id}.pdf"
    destination = PAPERS_DIR / safe_name
    await tg_file.download_to_drive(destination)
    with db() as c:
        c.execute("INSERT INTO papers(course,semester,subject,paper,price_paise,file_path) VALUES(?,?,?,?,?,?)",
                  (course, sem, subject, paper, price_paise, str(destination)))
    pending_uploads.discard(update.effective_user.id)
    await update.message.reply_text("PDF catalog में जोड़ दी गई। अभी कोई payment या delivery स्वतः चालू नहीं है।")


async def admin_papers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    with db() as c:
        rows = c.execute("SELECT id,course,semester,subject,paper,price_paise FROM papers ORDER BY id DESC LIMIT 30").fetchall()
    await update.message.reply_text("\n".join(
        f"#{r['id']} {r['course']} S{r['semester']} {r['subject']} / {r['paper']} ₹{r['price_paise']/100:.2f}"
        for r in rows
    ) or "Catalog खाली है।")


async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    with db() as c:
        rows = c.execute("SELECT id,user_id,amount_paise,status,created_at FROM orders ORDER BY id DESC LIMIT 30").fetchall()
    await update.message.reply_text("\n".join(
        f"#{r['id']} user={r['user_id']} ₹{r['amount_paise']/100:.2f} {r['status']}"
        for r in rows
    ) or "अभी कोई Order नहीं है।")


async def text_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.pop("searching", False):
        await show_papers(update.message, update.message.text.strip())


@api.get("/health")
async def health():
    return {"ok": True, "service": "uniraj-guess-papers-bot", "payment_mode": PAYMENT_MODE}


async def run_bot():
    global bot_app
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Add it in hosting environment variables.")
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("addpaper", admin_help))
    bot_app.add_handler(CommandHandler("papers", admin_papers))
    bot_app.add_handler(CommandHandler("orders", admin_orders))
    bot_app.add_handler(CallbackQueryHandler(callbacks))
    bot_app.add_handler(MessageHandler(filters.Document.PDF, admin_upload))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_search))
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    log.info("Telegram polling started")


async def main():
    init_db()
    import uvicorn
    config = uvicorn.Config(api, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), log_level="info")
    server = uvicorn.Server(config)
    await asyncio.gather(run_bot(), server.serve())


if __name__ == "__main__":
    asyncio.run(main())

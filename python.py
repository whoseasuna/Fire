import os
import re
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from androguard.core.bytecodes.apk import APK

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config Configuration
BOT_TOKEN = "8829348336:AAFbsUcR_cNBA2XTiBGURwZC2_cnOJ8erYA"
ADMIN_CHAT_ID = 8615997384  # Restricts broadcast function to you

# Regular expressions for finding Firebase URLs and API keys
FIREBASE_URL_REGEX = re.compile(r'https://[a-zA-Z0-9-]+.firebaseio.com', re.IGNORECASE)
FIREBASE_KEY_REGEX = re.compile(r'AIzaSy[a-zA-Z0-9-_]{33}', re.IGNORECASE)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "👋 Hello! Send me any `.apk` file, and I will scan its internal strings "
        "to check for Firebase backend URLs and API keys commonly used by RATs."
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allows the administrator to send a broadcast message through the bot."""
    if update.effective_chat.id != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ Unauthorized. Only the bot owner can use this command.")
        return

    # Check if a message was provided with the command
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/broadcast Your message here`")
        return

    broadcast_message = " ".join(context.args)
    
    # In a production bot tracking multiple users, you would iterate over a database list of user IDs here.
    # For this standalone instance, it confirms receipt and echo readiness.
    await update.message.reply_text(f"📢 Broadcast template confirmed for distribution:\n\n{broadcast_message}")

async def analyze_apk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the incoming APK file, scans it, and sends the results."""
    document = update.message.document
    if not document or not document.file_name.lower().endswith('.apk'):
        await update.message.reply_text("⚠️ Please send a valid `.apk` file.")
        return

    status_message = await update.message.reply_text("📥 Downloading and analyzing the APK... Please wait.")
    
    local_path = f"temp_{document.file_name}"
    try:
        apk_file = await context.bot.get_file(document.file_id)
        await apk_file.download_to_drive(local_path)

        # Load the APK using Androguard
        apk_obj = APK(local_path)
        
        found_urls = set()
        found_keys = set()

        # Step 1: Scan all raw string pools inside the DEX files
        for dex in apk_obj.get_all_dex():
            dex_strings = dex.get_strings()
            for s in dex_strings:
                urls = FIREBASE_URL_REGEX.findall(s)
                keys = FIREBASE_KEY_REGEX.findall(s)
                if urls: found_urls.update(urls)
                if keys: found_keys.update(keys)

        # Step 2: Scan the resources.arsc file
        resources = apk_obj.get_android_resources()
        if resources:
            for package_name in resources.get_packages_names():
                for string_value in resources.get_strings_resources(package_name).values():
                    urls = FIREBASE_URL_REGEX.findall(string_value)
                    keys = FIREBASE_KEY_REGEX.findall(string_value)
                    if urls: found_urls.update(urls)
                    if keys: found_keys.update(keys)

        # Format findings response
        if found_urls or found_keys:
            response_text = "🚨 **Potential RAT/Firebase Credentials Found!** 🚨\n\n"
            if found_urls:
                response_text += "**Firebase URL(s):**\n" + "\n".join([f"`{url}`" for url in found_urls]) + "\n\n"
            if found_keys:
                response_text += "**API Key(s):**\n" + "\n".join([f"`{key}`" for key in found_keys]) + "\n"
            
            response_text += "\n⚠️ **Warning:** If you do not recognize this app, do not install it."
        else:
            response_text = "✅ **Scan Clean:** No typical Firebase URLs or common API keys detected in the raw strings."

        await status_message.edit_text(response_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error analyzing APK: {e}")
        await status_message.edit_text("❌ An error occurred while parsing the APK file.")
        
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(MessageHandler(filters.Document.ALL, analyze_apk))

    # Run the bot
    logger.info("Starting bot polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
          

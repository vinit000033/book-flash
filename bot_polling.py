import os
import logging
from telegram import Update, Chat
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

import re
import json
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class MentionBot:
    def __init__(self):
        self.custom_message = "Hello! Thanks for your request!Rest assusred ,it will soon reach my BOSS ."  # Default message
        self.data_file = "bot_data.json"
        self.data = self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load data file: {e}")
        return {"announce_group_id": None}

    def save_data(self):
        try:
            with open(self.data_file, "w") as f:
                json.dump(self.data, f)
        except Exception as e:
            logger.error(f"Failed to save data file: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hello! I am your   BOOKFLASH. only my boss vinit  can set a custom reply message using /setmessage command.")

    async def set_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("NIKAL WE LAU**re, JA PAHLE MERE BOSS  SE BAAT KAR TAB TU USE KARNE AANA @vinit0003.")
            return

        if context.args:
            self.custom_message = " ".join(context.args)
            await update.message.reply_text(f"Custom message updated to:\n{self.custom_message}")
        else:
            await update.message.reply_text("Usage: /setmessage Your custom message here")

    async def setgroup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("You are not authorized to use this command.")
            return

        if not context.args:
            await update.message.reply_text("Usage: /setgroup <group_chat_id>")
            return

        group_id = context.args[0]
        # Allow negative numbers as well
        if not (group_id.lstrip('-').isdigit()):
            await update.message.reply_text("Group chat ID must be a number.")
            return

        self.data["announce_group_id"] = int(group_id)
        self.save_data()
        await update.message.reply_text(f"Announcement group set to: {group_id}")

    async def addbook(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("You are not authorized to use this command.")
            return

        message_text = update.message.text
        # Expected format: /addbook Name: [Book Name]; Author: [Author]; Details: [Some description]
        pattern = r"Name:\s*(.+?);\s*Author:\s*(.+?);\s*Details:\s*(.+)"
        match = re.search(pattern, message_text, re.IGNORECASE)
        if not match:
            await update.message.reply_text(
                "Invalid format. Please use:\n"
                "/addbook Name: [Book Name]; Author: [Author]; Details: [Some description]"
            )
            return

        book_name, author, details = match.groups()

        # Prepare announcement message with emojis and markdown, enhanced formatting
        announcement = (
            f"📚 *New Book Announcement!*\n"
            f"{'='*30}\n"
            f"*Title:* {book_name}\n\n"
            f"*Author:* {author}\n\n"
            f"*Details:*\n{details}\n"
            f"{'='*30}\n"
            f"📖 Click the button below to visit the Library!"
        )

        # Inline button example (Library button)
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📖 Library", url="https://example.com/library")]]
        )

        announce_group_id = self.data.get("announce_group_id")
        if not announce_group_id:
            await update.message.reply_text("Announcement group ID is not configured. Use /setgroup to set it.")
            return

        try:
            await context.bot.send_message(
                chat_id=announce_group_id,
                text=announcement,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            await update.message.reply_text("Book announcement posted successfully.")
        except Exception as e:
            logger.error(f"Failed to send announcement: {e}")
            await update.message.reply_text("Failed to post the announcement.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "🤖 *MentionBot Help*\n\n"
            "Commands:\n"
            "/start - Start the bot and get a welcome message.\n"
            "/setmessage [message] - Set a custom reply message (admin only).\n"
            "/setgroup <group_chat_id> - Set the group chat ID for book announcements (admin only).\n"
            "/addbook Name: [Book Name]; Author: [Author]; Details: [Description] - Add a book announcement (admin only).\n"
            "/help - Show this help message.\n\n"
            "The bot replies when mentioned in group chats with the custom message.\n"
            "Book announcements are posted to the configured group."
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message
        chat = message.chat

        # Only process group messages
        if chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            # Check if bot is mentioned in the message entities
            if message.entities:
                bot_username = (await context.bot.get_me()).username.lower()
                for entity in message.entities:
                    if entity.type == "mention":
                        mentioned_text = message.text[entity.offset : entity.offset + entity.length].lower()
                        if mentioned_text == f"@{bot_username}":
                            # Reply with custom message
                            await message.reply_text(self.custom_message)

                            # Report mention to admin privately
                            user = message.from_user
                            report_text = (
                                f"User @{user.username or user.first_name} mentioned the bot in group '{chat.title}':\n"
                                f"Message: {message.text}"
                            )
                            await context.bot.send_message(chat_id=ADMIN_ID, text=report_text, parse_mode=ParseMode.HTML)
                            break

    def run(self):
        if not BOT_TOKEN or not ADMIN_ID:
            logger.error("BOT_TOKEN and ADMIN_ID environment variables must be set")
            return

        app = ApplicationBuilder().token(BOT_TOKEN).build()

        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("setmessage", self.set_message))
        app.add_handler(CommandHandler("setgroup", self.setgroup))
        app.add_handler(CommandHandler("addbook", self.addbook))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))

        app.run_polling()

if __name__ == "__main__":
    bot = MentionBot()
    bot.run()

import os
import logging
from telegram import Update, Chat, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import re
import json
import difflib
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "vinit0003")  # Admin's username
ADMIN_NAME = os.getenv("ADMIN_NAME", "vinit")  # Admin's name

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Conversation states for adding books
WAITING_FOR_BOOK_URL = 1

class AdvancedMentionBot:
    def __init__(self):
        self.custom_message = "Hello! Thanks for your request! Rest assured, it will soon reach my BOSS."
        self.data_file = "bot_data.json"
        self.data = self.load_data()
        self.pending_book_data = {}  # Store temporary book data during conversation

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure all required keys exist
                    default_data = {
                        "announce_group_id": None,
                        "books": [],
                        "auto_replies": {
                            "hello": "Hello! How can I help you today? 😊",
                            "hi": "Hi there! 👋",
                            "help": "I can help you find books! Just mention a book name or ask for recommendations.",
                            "recommend": "I'd be happy to recommend some books! What genre are you interested in?",
                            "thank": "You're welcome! Happy reading! 📚"
                        },
                        "conversation_keywords": {
                            "book": "Are you looking for a specific book? I can help you find it!",
                            "read": "Reading is amazing! What type of books do you enjoy?",
                            "author": "Which author are you interested in? I might have their books!",
                            "fiction": "Fiction books are great! I have some amazing recommendations.",
                            "non-fiction": "Non-fiction can be very educational! What topic interests you?",
                            "novel": "Novels are wonderful! Any particular genre you prefer?",
                            "story": "Stories transport us to different worlds! What kind of story are you looking for?"
                        }
                    }
                    # Merge with defaults
                    for key, value in default_data.items():
                        if key not in data:
                            data[key] = value
                    return data
            except Exception as e:
                logger.error(f"Failed to load data file: {e}")

        # Return default data structure
        return {
            "announce_group_id": None,
            "books": [],
            "auto_replies": {
                "hello": "Hello! How can I help you today? 😊",
                "hi": "Hi there! 👋",
                "help": "I can help you find books! Just mention a book name or ask for recommendations.",
                "recommend": "I'd be happy to recommend some books! What genre are you interested in?",
                "thank": "You're welcome! Happy reading! 📚"
            },
            "conversation_keywords": {
                "book": "Are you looking for a specific book? I can help you find it!",
                "read": "Reading is amazing! What type of books do you enjoy?",
                "author": "Which author are you interested in? I might have their books!",
                "fiction": "Fiction books are great! I have some amazing recommendations.",
                "non-fiction": "Non-fiction can be very educational! What topic interests you?",
                "novel": "Novels are wonderful! Any particular genre you prefer?",
                "story": "Stories transport us to different worlds! What kind of story are you looking for?"
            }
        }

    def save_data(self):
        try:
            with open(self.data_file, "w", encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save data file: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = (
            "🤖 *Welcome to BOOKFLASH Bot!*\n\n"
            "I'm your intelligent book assistant! Here's what I can do:\n"
            "📚 Suggest books when you mention them\n"
            "💬 Have conversations about books\n"
            "🔍 Help you find specific books\n"
            "📢 Announce new book additions\n\n"
            "Just chat naturally and I'll assist you!"
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

    async def set_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text(f"❌ Access denied! Only @{ADMIN_USERNAME} can use this command.")
            return

        if context.args:
            self.custom_message = " ".join(context.args)
            await update.message.reply_text(f"✅ Custom message updated to:\n{self.custom_message}")
        else:
            await update.message.reply_text("📝 Usage: /setmessage Your custom message here")

    async def setgroup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return

        if not context.args:
            await update.message.reply_text("📝 Usage: /setgroup <group_chat_id>")
            return

        group_id = context.args[0]
        if not (group_id.lstrip('-').isdigit()):
            await update.message.reply_text("❌ Group chat ID must be a number.")
            return

        self.data["announce_group_id"] = int(group_id)
        self.save_data()
        await update.message.reply_text(f"✅ Announcement group set to: {group_id}")

    async def addbook_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return ConversationHandler.END

        message_text = update.message.text
        # Expected format: /addbook Name: [Book Name]; Author: [Author]; Details: [Some description]
        pattern = r"Name:\s*(.+?);\s*Author:\s*(.+?);\s*Details:\s*(.+)"
        match = re.search(pattern, message_text, re.IGNORECASE)

        if not match:
            await update.message.reply_text(
                "❌ Invalid format. Please use:\n"
                "`/addbook Name: [Book Name]; Author: [Author]; Details: [Some description]`",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END

        book_name, author, details = match.groups()

        # Store book data temporarily
        self.pending_book_data[user_id] = {
            'name': book_name.strip(),
            'author': author.strip(),
            'details': details.strip()
        }

        await update.message.reply_text(
            f"📚 Book details received:\n"
            f"*Name:* {book_name}\n"
            f"*Author:* {author}\n"
            f"*Details:* {details}\n\n"
            f"🔗 Now please send the book URL:",
            parse_mode=ParseMode.MARKDOWN
        )

        return WAITING_FOR_BOOK_URL

    async def addbook_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        book_url = update.message.text.strip()

        # Basic URL validation
        if not (book_url.startswith('http://') or book_url.startswith('https://')):
            await update.message.reply_text(
                "❌ Please provide a valid URL (starting with http:// or https://)"
            )
            return WAITING_FOR_BOOK_URL

        # Get stored book data
        book_data = self.pending_book_data.get(user_id)
        if not book_data:
            await update.message.reply_text("❌ Book data not found. Please start over with /addbook")
            return ConversationHandler.END

        # Add URL to book data
        book_data['url'] = book_url
        book_data['added_date'] = datetime.now().isoformat()

        # Save to books list
        self.data["books"].append(book_data)
        self.save_data()

        # Prepare announcement message
        announcement = (
            f"📚 *New Book Added to Library!*\n"
            f"{'='*35}\n"
            f"📖 *Title:* {book_data['name']}\n\n"
            f"✍️ *Author:* {book_data['author']}\n\n"
            f"📝 *Details:*\n{book_data['details']}\n"
            f"{'='*35}\n"
            f"🔗 Click the button below to access this book!"
        )

        # Create inline keyboard with book URL
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Read Book", url=book_data['url'])],
            [InlineKeyboardButton("📚 Visit Library", url="https://ipm-library.lovable.app/")]
        ])

        announce_group_id = self.data.get("announce_group_id")
        if not announce_group_id:
            await update.message.reply_text("❌ Announcement group ID is not configured. Use /setgroup to set it.")
            return ConversationHandler.END

        try:
            # First try with Markdown
            await context.bot.send_message(
                chat_id=announce_group_id,
                text=announcement,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            await update.message.reply_text("✅ Book announcement posted successfully!")
        except Exception as e:
            logger.error(f"Failed to send announcement with Markdown: {e}")
            try:
                # Fallback: Try without Markdown formatting
                plain_announcement = (
                    f"📚 New Book Added to Library!\n"
                    f"=====================================\n"
                    f"📖 Title: {book_data['name']}\n\n"
                    f"✍️ Author: {book_data['author']}\n\n"
                    f"📝 Details:\n{book_data['details']}\n"
                    f"=====================================\n"
                    f"🔗 Click the button below to access this book!"
                )
                await context.bot.send_message(
                    chat_id=announce_group_id,
                    text=plain_announcement,
                    reply_markup=keyboard,
                )
                await update.message.reply_text("✅ Book announcement posted successfully! (Plain text format)")
            except Exception as e2:
                logger.error(f"Failed to send announcement (second attempt): {e2}")
                try:
                    # Final fallback: Try without buttons
                    simple_announcement = (
                        f"📚 New Book Added to Library!\n"
                        f"=====================================\n"
                        f"📖 Title: {book_data['name']}\n"
                        f"✍️ Author: {book_data['author']}\n"
                        f"📝 Details: {book_data['details']}\n"
                        f"🔗 Book URL: {book_data['url']}\n"
                        f"📚 Library: https://ipm-library.lovable.app/"
                    )
                    await context.bot.send_message(
                        chat_id=announce_group_id,
                        text=simple_announcement
                    )
                    await update.message.reply_text("✅ Book announcement posted successfully! (Simple format)")
                except Exception as e3:
                    logger.error(f"All announcement attempts failed: {e3}")
                    await update.message.reply_text(
                        f"❌ Failed to post announcement. Error details:\n"
                        f"• First attempt (Markdown): {str(e)}\n"
                        f"• Second attempt (Plain): {str(e2)}\n"
                        f"• Third attempt (Simple): {str(e3)}\n\n"
                        f"Please check:\n"
                        f"1. Bot is added to the group\n"
                        f"2. Bot has permission to send messages\n"
                        f"3. Group ID is correct: {announce_group_id}"
                    )

        # Clean up temporary data
        del self.pending_book_data[user_id]
        return ConversationHandler.END

    async def cancel_addbook(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.pending_book_data:
            del self.pending_book_data[user_id]

        await update.message.reply_text("❌ Book addition cancelled.")
        return ConversationHandler.END

    async def add_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "📝 Usage: /addreply <keyword> <response>\n"
                "Example: /addreply greeting Hello! Welcome to our book community!"
            )
            return

        keyword = context.args[0].lower()
        response = " ".join(context.args[1:])

        self.data["auto_replies"][keyword] = response
        self.save_data()

        await update.message.reply_text(f"✅ Auto-reply added for keyword '{keyword}'")

    async def get_group_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Helper command to get current chat ID"""
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return

        chat = update.message.chat
        chat_info = (
            f"📋 *Chat Information:*\n"
            f"**Chat ID:** `{chat.id}`\n"
            f"**Chat Type:** {chat.type}\n"
            f"**Chat Title:** {chat.title if chat.title else 'N/A'}\n\n"
            f"Use this chat ID with `/setgroup {chat.id}` to set it as announcement group."
        )
        await update.message.reply_text(chat_info, parse_mode=ParseMode.MARKDOWN)

    async def test_announcement(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test announcement functionality"""
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return

        announce_group_id = self.data.get("announce_group_id")
        if not announce_group_id:
            await update.message.reply_text("❌ No announcement group configured. Use /setgroup first.")
            return

        test_message = "🧪 This is a test announcement from BOOKFLASH Bot! Everything is working correctly. ✅"

        try:
            await context.bot.send_message(
                chat_id=announce_group_id,
                text=test_message
            )
            await update.message.reply_text("✅ Test announcement sent successfully!")
        except Exception as e:
            error_msg = (
                f"❌ Test announcement failed!\n"
                f"**Error:** {str(e)}\n"
                f"**Group ID:** {announce_group_id}\n\n"
                f"**Possible issues:**\n"
                f"• Bot not added to the group\n"
                f"• Bot lacks message sending permission\n"
                f"• Wrong group ID\n"
                f"• Group was deleted/archived\n\n"
                f"**Solutions:**\n"
                f"1. Add bot to the target group\n"
                f"2. Make bot admin or ensure it can send messages\n"
                f"3. Use /getchatid in the target group to verify ID"
            )
            await update.message.reply_text(error_msg, parse_mode=ParseMode.MARKDOWN)

    async def list_books(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        books = self.data.get("books", [])

        if not books:
            await update.message.reply_text("📚 No books available yet.")
            return

        books_text = "📚 *Available Books:*\n\n"
        for i, book in enumerate(books[:10], 1):  # Show only first 10 books
            books_text += f"{i}. *{book['name']}* by {book['author']}\n"

        if len(books) > 10:
            books_text += f"\n... and {len(books) - 10} more books!"

        await update.message.reply_text(books_text, parse_mode=ParseMode.MARKDOWN)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        is_admin = user_id == ADMIN_ID

        help_text = (
            "🤖 *BOOKFLASH Bot - Complete Command Guide*\n"
            f"Bot by @{ADMIN_USERNAME}\n\n"
        )

        # User commands (available to everyone)
        help_text += (
            "👥 *USER COMMANDS:*\n"
            "/start - Welcome message and bot introduction\n"
            "/help - Show this complete command list\n"
            "/listbooks - Display all available books\n\n"
        )

        # Admin commands (only shown to admin)
        if is_admin:
            help_text += (
                "🔐 *ADMIN COMMANDS:*\n"
                "/setmessage <message> - Set custom bot reply message\n"
                "/setgroup <group_id> - Set announcement group for book posts\n"
                "/addbook Name: [Name]; Author: [Author]; Details: [Details] - Add new book (will ask for URL)\n"
                "/addreply <keyword> <response> - Add automatic reply for keywords\n"
                "/cancel - Cancel ongoing book addition process\n"
                "/getchatid - Get current chat ID information\n"
                "/testannounce - Test announcement functionality\n\n"
            )
        else:
            help_text += (
                f"🔐 *ADMIN COMMANDS:* (Only @{ADMIN_USERNAME} can use)\n"
                "• Book management commands\n"
                "• Auto-reply configuration\n"
                "• Group settings\n\n"
            )

        # Bot features
        help_text += (
            "✨ *SMART FEATURES:*\n"
            "📚 **Book Detection** - I detect book-related words and suggest matching books with URLs\n"
            "💬 **Smart Replies** - I respond to greetings and book-related keywords\n"
            "🔍 **Keyword Matching** - I match words from book titles, authors, and descriptions\n"
            "👁️ **Admin Monitoring** - I alert admin when mentioned\n"
            "📢 **Auto Announcements** - New books are posted to configured groups\n"
            "🔗 **Direct Access** - Click buttons to read books directly\n\n"
        )

        # Usage examples
        help_text += (
            "💡 *USAGE EXAMPLES:*\n"
            "• Type 'hello' → I'll greet you back\n"
            "• Mention book title/author → I'll show the book with URL\n"
            "• Type words from book descriptions → I'll suggest related books\n"
            "• Say 'recommend books' → I'll help you find books\n"
            f"• Mention @{ADMIN_USERNAME} or 'admin' → Admin gets notified\n\n"
        )

        # Auto-reply keywords
        auto_replies = self.data.get("auto_replies", {})
        conversation_keywords = self.data.get("conversation_keywords", {})

        if auto_replies:
            help_text += "🗣️ *AUTO-REPLY KEYWORDS:*\n"
            keyword_list = ", ".join(list(auto_replies.keys())[:8])  # Show first 8 keywords
            help_text += f"{keyword_list}"
            if len(auto_replies) > 8:
                help_text += f" and {len(auto_replies) - 8} more..."
            help_text += "\n\n"

        # Bot statistics
        total_books = len(self.data.get("books", []))
        total_replies = len(auto_replies)
        total_keywords = len(conversation_keywords)

        help_text += (
            f"📊 *BOT STATISTICS:*\n"
            f"📚 Books in library: {total_books}\n"
            f"💬 Auto-replies: {total_replies}\n"
            f"🔤 Conversation keywords: {total_keywords}\n\n"
        )

        # Support info
        help_text += (
            f"🆘 *NEED HELP?*\n"
            f"Contact admin: @{ADMIN_USERNAME}\n"
            f"Made with ❤️ for book lovers!"
        )

        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    def find_similar_books(self, query, threshold=0.6):
        """Find books similar to the query using fuzzy matching"""
        books = self.data.get("books", [])
        matches = []

        query_lower = query.lower()

        for book in books:
            # Check name similarity
            name_ratio = difflib.SequenceMatcher(None, query_lower, book['name'].lower()).ratio()
            # Check author similarity
            author_ratio = difflib.SequenceMatcher(None, query_lower, book['author'].lower()).ratio()

            max_ratio = max(name_ratio, author_ratio)

            if max_ratio >= threshold:
                matches.append((book, max_ratio))

        # Sort by similarity score
        matches.sort(key=lambda x: x[1], reverse=True)
        return [match[0] for match in matches[:3]]  # Return top 3 matches

    def find_books_by_keywords(self, message_text):
        """Find books that match keywords from the message"""
        books = self.data.get("books", [])
        matched_books = []
        message_lower = message_text.lower()

        for book in books:
            # Create searchable text from book data
            searchable_text = f"{book['name']} {book['author']} {book['details']}".lower()

            # Split book data into keywords
            book_keywords = set()

            # Add individual words from book name (length > 2)
            name_words = [word.strip('.,!?;:"()[]{}') for word in book['name'].lower().split() if len(word) > 2]
            book_keywords.update(name_words)

            # Add individual words from author name (length > 2)
            author_words = [word.strip('.,!?;:"()[]{}') for word in book['author'].lower().split() if len(word) > 2]
            book_keywords.update(author_words)

            # Add significant words from details (length > 3)
            detail_words = [word.strip('.,!?;:"()[]{}') for word in book['details'].lower().split() if len(word) > 3]
            book_keywords.update(detail_words[:10])  # Limit to first 10 detail words

            # Check if any book keywords appear in the message
            message_words = set(word.strip('.,!?;:"()[]{}') for word in message_lower.split())

            # Find matching keywords
            common_keywords = book_keywords.intersection(message_words)

            if common_keywords:
                # Calculate match score based on number of matching keywords and their importance
                score = 0
                for keyword in common_keywords:
                    if keyword in book['name'].lower():
                        score += 10  # High score for title matches
                    elif keyword in book['author'].lower():
                        score += 7   # Medium-high score for author matches
                    elif keyword in book['details'].lower():
                        score += 3   # Lower score for detail matches

                if score >= 7:  # Minimum score threshold
                    matched_books.append((book, score, list(common_keywords)))

        # Sort by score (highest first)
        matched_books.sort(key=lambda x: x[1], reverse=True)
        return matched_books[:2]  # Return top 2 matches

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message
        chat = message.chat
        user = message.from_user
        text = message.text.lower()

        # Only process group messages
        if chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            # Check for admin name mentions
            admin_keywords = [ADMIN_NAME.lower(), ADMIN_USERNAME.lower(), "admin", "boss"]
            if any(keyword in text for keyword in admin_keywords):
                report_text = (
                    f"🚨 *Admin Mention Alert!*\n"
                    f"User: @{user.username or user.first_name}\n"
                    f"Group: {chat.title}\n"
                    f"Message: {message.text}\n"
                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID, 
                        text=report_text, 
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.error(f"Failed to send admin mention report: {e}")

            # Check if bot is mentioned
            if message.entities:
                bot_username = (await context.bot.get_me()).username.lower()
                for entity in message.entities:
                    if entity.type == "mention":
                        mentioned_text = message.text[entity.offset : entity.offset + entity.length].lower()
                        if mentioned_text == f"@{bot_username}":
                            await message.reply_text(self.custom_message)

                            # Report mention to admin
                            report_text = (
                                f"📢 *Bot Mention Report*\n"
                                f"User: @{user.username or user.first_name}\n"
                                f"Group: {chat.title}\n"
                                f"Message: {message.text}"
                            )
                            try:
                                await context.bot.send_message(
                                    chat_id=ADMIN_ID, 
                                    text=report_text, 
                                    parse_mode=ParseMode.MARKDOWN
                                )
                            except Exception as e:
                                logger.error(f"Failed to send mention report: {e}")
                            return

            # Check for auto-replies
            auto_replies = self.data.get("auto_replies", {})
            for keyword, response in auto_replies.items():
                if keyword in text:
                    await message.reply_text(response)
                    return

            # Check for conversation keywords
            conversation_keywords = self.data.get("conversation_keywords", {})
            for keyword, response in conversation_keywords.items():
                if keyword in text:
                    await message.reply_text(response)
                    return

            # Check for book mentions and suggestions using keyword matching
            matched_books = self.find_books_by_keywords(message.text)
            if matched_books:
                for book_data, score, matched_keywords in matched_books:
                    suggestion_text = (
                        f"📚 *Found: {book_data['name']}*\n"
                        f"✍️ **Author:** {book_data['author']}\n"
                        f"📝 **Details:** {book_data['details'][:150]}{'...' if len(book_data['details']) > 150 else ''}\n"
                        f"🔍 **Matched words:** {', '.join(matched_keywords[:5])}"
                    )

                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📖 Read Book", url=book_data['url'])],
                        [InlineKeyboardButton("📚 Visit Library", url="https://ipm-library.lovable.app/")]
                    ])

                    try:
                        await message.reply_text(
                            suggestion_text, 
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=keyboard
                        )
                    except Exception as e:
                        # Fallback without markdown
                        plain_text = (
                            f"📚 Found: {book_data['name']}\n"
                            f"✍️ Author: {book_data['author']}\n"
                            f"📝 Details: {book_data['details'][:150]}{'...' if len(book_data['details']) > 150 else ''}\n"
                            f"🔍 Matched words: {', '.join(matched_keywords[:5])}\n"
                            f"🔗 Book URL: {book_data['url']}"
                        )
                        await message.reply_text(plain_text, reply_markup=keyboard)

                    # Only suggest the first (best) match to avoid spam
                    break
                return

            # Fallback: Check for fuzzy matching if no keyword matches found
            words = text.split()
            for word in words:
                if len(word) > 3:  # Only check words longer than 3 characters
                    similar_books = self.find_similar_books(word, threshold=0.8)
                    if similar_books:
                        book = similar_books[0]
                        suggestion_text = (
                            f"📚 Did you mean *{book['name']}*?\n"
                            f"✍️ Author: {book['author']}\n"
                            f"📝 {book['details'][:100]}{'...' if len(book['details']) > 100 else ''}"
                        )

                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("📖 Read Book", url=book['url'])]
                        ])

                        try:
                            await message.reply_text(
                                suggestion_text, 
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=keyboard
                            )
                        except Exception as e:
                            # Fallback without markdown
                            plain_text = (
                                f"📚 Did you mean: {book['name']}\n"
                                f"✍️ Author: {book['author']}\n"
                                f"📝 {book['details'][:100]}{'...' if len(book['details']) > 100 else ''}\n"
                                f"🔗 Book URL: {book['url']}"
                            )
                            await message.reply_text(plain_text, reply_markup=keyboard)
                        return

    def run(self):
        if not BOT_TOKEN or not ADMIN_ID:
            logger.error("BOT_TOKEN and ADMIN_ID environment variables must be set")
            return

        app = ApplicationBuilder().token(BOT_TOKEN).build()

        # Conversation handler for adding books
        addbook_handler = ConversationHandler(
            entry_points=[CommandHandler("addbook", self.addbook_start)],
            states={
                WAITING_FOR_BOOK_URL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.addbook_url)
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_addbook)],
        )

        # Add handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("setmessage", self.set_message))
        app.add_handler(CommandHandler("setgroup", self.setgroup))
        app.add_handler(addbook_handler)
        app.add_handler(CommandHandler("addreply", self.add_reply))
        app.add_handler(CommandHandler("listbooks", self.list_books))
        app.add_handler(CommandHandler("getchatid", self.get_group_info))
        app.add_handler(CommandHandler("testannounce", self.test_announcement))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))

        logger.info("🤖 BOOKFLASH Bot started successfully!")
        app.run_polling()

if __name__ == "__main__":
    bot = AdvancedMentionBot()
    bot.run()

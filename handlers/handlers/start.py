from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from translations import t
from keyboards import language_keyboard, start_keyboard, projects_keyboard
from states import CHOOSING_LANGUAGE


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username)
    existing = db.get_user(user.id)
    if existing and existing.get("language"):
        await send_welcome(update, context, existing["language"])
        return ConversationHandler.END

    await update.message.reply_text(
        "🌐 Please choose your language / भाषा चुनें / மொழியைத் தேர்ந்தெடுக்கவும்:",
        reply_markup=language_keyboard(),
    )
    return CHOOSING_LANGUAGE


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/language lets a user change language at any time."""
    await update.message.reply_text(
        "🌐 Choose your language:", reply_markup=language_keyboard()
    )
    return CHOOSING_LANGUAGE


async def on_language_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split("_", 1)[1]
    db.set_user_language(query.from_user.id, lang_code)
    await query.edit_message_text(t("language_saved", lang_code))
    await send_welcome(update, context, lang_code)
    return ConversationHandler.END


async def send_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    chat_id = update.effective_chat.id
    text = f"{t('welcome_title', lang)}\n\n{t('welcome_body', lang)}"
    await context.bot.send_message(chat_id, text, reply_markup=start_keyboard(lang))


async def show_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db.get_user_language(query.from_user.id)
    projects = db.get_projects(active_only=True)
    if not projects:
        await query.edit_message_text(t("no_active_projects", lang))
        return
    await query.edit_message_text(
        t("projects_header", lang), reply_markup=projects_keyboard(projects)
    )

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from config import STANDARD_FIELDS, ADMIN_IDS
from translations import t
from states import APPLYING, UPLOADING

FILE_TYPE_LABELS = {
    "audio": "🎵 Audio",
    "zip": "🗜 ZIP",
    "csv": "📄 CSV",
    "excel": "📊 Excel",
    "pdf": "📕 PDF",
    "image": "🖼 Image",
    "video": "🎬 Video",
    "document": "📎 File",
}


def build_steps(project_id):
    steps = []
    for key, label, ftype in STANDARD_FIELDS:
        if ftype.startswith("choice:"):
            opts = ftype.split(":", 1)[1].split(",")
            steps.append({"key": key, "text": label, "type": "choice", "options": opts})
        else:
            steps.append({"key": key, "text": label, "type": "text", "options": None})
    for q in db.get_questions(project_id):
        opts = [o.strip() for o in q["options"].split(",")] if q["options"] else None
        steps.append(
            {
                "key": f"q{q['id']}",
                "text": q["question_text"],
                "type": q["question_type"],
                "options": opts,
            }
        )
    return steps


async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    project_id = int(query.data.split("_", 1)[1])
    project = db.get_project(project_id)
    if not project or project["status"] != "active":
        await query.edit_message_text("This project is no longer accepting applications.")
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["steps"] = build_steps(project_id)
    context.user_data["idx"] = 0
    context.user_data["project_id"] = project_id
    context.user_data["answers"] = {}

    await context.bot.send_message(
        update.effective_chat.id,
        f"📝 Applying to: {project['name']}\n\nLet's collect a few details.",
    )
    await ask_step(update.effective_chat.id, context)
    return APPLYING


async def ask_step(chat_id, context: ContextTypes.DEFAULT_TYPE):
    idx = context.user_data["idx"]
    steps = context.user_data["steps"]
    step = steps[idx]
    text = f"({idx + 1}/{len(steps)}) {step['text']}"
    if step["type"] == "choice" and step["options"]:
        kb = [
            [InlineKeyboardButton(o, callback_data=f"ans_{o}")] for o in step["options"]
        ]
        await context.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await context.bot.send_message(chat_id, text)


async def receive_text_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "steps" not in context.user_data:
        return APPLYING
    steps = context.user_data["steps"]
    idx = context.user_data["idx"]
    step = steps[idx]
    if step["type"] == "choice":
        await update.message.reply_text("Please tap one of the buttons above. 👆")
        return APPLYING
    context.user_data["answers"][step["key"]] = (step["text"], update.message.text)
    return await advance(update.effective_chat.id, context)


async def receive_choice_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    steps = context.user_data["steps"]
    idx = context.user_data["idx"]
    step = steps[idx]
    choice = query.data[len("ans_"):]
    context.user_data["answers"][step["key"]] = (step["text"], choice)
    await query.edit_message_reply_markup(reply_markup=None)
    return await advance(update.effective_chat.id, context)


async def advance(chat_id, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["idx"] += 1
    if context.user_data["idx"] < len(context.user_data["steps"]):
        await ask_step(chat_id, context)
        return APPLYING

    # All questions answered -> create the application record now.
    project_id = context.user_data["project_id"]
    app_id = db.create_application(chat_id, project_id)
    for key, (qtext, ans) in context.user_data["answers"].items():
        db.add_answer(app_id, key, qtext, ans)
    context.user_data["application_id"] = app_id

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Done — Submit Application", callback_data="upload_done")]]
    )
    await context.bot.send_message(
        chat_id,
        "📎 Optional: upload supporting files now.\n"
        "Supported: Audio, ZIP, CSV, Excel, PDF, Images, Videos.\n\n"
        "Send them one by one, then tap Done — or tap Done to skip.",
        reply_markup=kb,
    )
    return UPLOADING


def detect_file(msg):
    if msg.voice:
        return "audio", msg.voice.file_id, "voice_note.ogg"
    if msg.audio:
        return "audio", msg.audio.file_id, msg.audio.file_name or "audio"
    if msg.document:
        name = msg.document.file_name or "file"
        ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
        mapping = {"zip": "zip", "csv": "csv", "xlsx": "excel", "xls": "excel", "pdf": "pdf"}
        return mapping.get(ext, "document"), msg.document.file_id, name
    if msg.photo:
        return "image", msg.photo[-1].file_id, "photo.jpg"
    if msg.video:
        return "video", msg.video.file_id, msg.video.file_name or "video.mp4"
    return None, None, None


async def receive_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    app_id = context.user_data.get("application_id")
    if not app_id:
        return UPLOADING
    file_type, file_id, file_name = detect_file(update.message)
    if not file_id:
        await update.message.reply_text("That file type isn't supported. Try again or tap Done.")
        return UPLOADING
    db.add_file(app_id, file_type, file_id, file_name)
    label = FILE_TYPE_LABELS.get(file_type, "📎 File")
    await update.message.reply_text(f"{label} received: {file_name}")
    return UPLOADING


async def finish_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    app_id = context.user_data.get("application_id")
    await query.edit_message_text(
        "🎉 Your application has been submitted!\n\n"
        "Status: Pending\n"
        "We'll notify you here as soon as it's reviewed."
    )

    if app_id:
        application = db.get_application(app_id)
        applicant = update.effective_user
        summary = (
            f"🆕 New application #{app_id}\n"
            f"Project: {application['project_name']}\n"
            f"Applicant: @{applicant.username or applicant.id} ({applicant.id})\n"
            f"Use the Applicants menu in /admin to review."
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(admin_id, summary)
            except Exception:
                pass

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Application cancelled. Send /start to begin again.")
    return ConversationHandler.END

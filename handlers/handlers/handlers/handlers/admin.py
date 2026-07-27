from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from config import ADMIN_IDS
from keyboards import (
    admin_menu_keyboard,
    project_list_keyboard,
    question_type_keyboard,
    status_keyboard,
    confirm_keyboard,
)
from states import (
    CP_NAME,
    CP_DESCRIPTION,
    CP_QUESTION_TEXT,
    CP_QUESTION_TYPE,
    CP_QUESTION_OPTIONS,
    EP_MENU,
    EP_NAME,
    EP_DESCRIPTION,
    EP_QUESTION_TEXT,
    EP_QUESTION_TYPE,
    EP_QUESTION_OPTIONS,
    BC_MESSAGE,
    BC_CONFIRM,
    MSG_APPLICANT,
)
from handlers.export import export_csv, export_excel, export_json


def _is_admin(user_id):
    return user_id in ADMIN_IDS or db.is_admin(user_id)


async def guard(update: Update):
    user_id = update.effective_user.id
    if not _is_admin(user_id):
        if update.callback_query:
            await update.callback_query.answer("Admins only.", show_alert=True)
        else:
            await update.message.reply_text("⛔ This command is for admins only.")
        return False
    return True


# ---------------- Main menu ----------------

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    await update.message.reply_text("🛠 Admin Dashboard", reply_markup=admin_menu_keyboard())


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await guard(update):
        return
    context.user_data.clear()
    await query.edit_message_text("🛠 Admin Dashboard", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END


# ---------------- Create Project ----------------

async def cp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await guard(update):
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data["new_questions"] = []
    await query.edit_message_text("➕ New Project\n\nWhat's the project name?\n(/cancel to abort)")
    return CP_NAME


async def cp_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cp_name"] = update.message.text.strip()
    await update.message.reply_text("Great. Now give a short description of the project:")
    return CP_DESCRIPTION


async def cp_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cp_description"] = update.message.text.strip()
    await update.message.reply_text(
        "Now let's add the custom questions for this project (in addition to the "
        "standard fields every applicant already answers).\n\n"
        "Send the text of a question, or /done if this project needs no extra questions."
    )
    return CP_QUESTION_TEXT


async def cp_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pending_question"] = update.message.text.strip()
    await update.message.reply_text("What type of answer should this question expect?",
                                     reply_markup=question_type_keyboard())
    return CP_QUESTION_TYPE


async def cp_question_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qtype = query.data.split("_", 1)[1]  # text | number | choice
    context.user_data["pending_question_type"] = qtype
    if qtype == "choice":
        await query.edit_message_text(
            f"Question: {context.user_data['pending_question']}\n\n"
            "Send the answer options, comma-separated (e.g. Male, Female, Other):"
        )
        return CP_QUESTION_OPTIONS
    context.user_data["new_questions"].append(
        {
            "text": context.user_data.pop("pending_question"),
            "type": qtype,
            "options": None,
        }
    )
    context.user_data.pop("pending_question_type", None)
    await query.edit_message_text(
        "Added ✅\n\nSend another question, or /done to finish creating this project."
    )
    return CP_QUESTION_TEXT


async def cp_question_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    options = update.message.text.strip()
    context.user_data["new_questions"].append(
        {
            "text": context.user_data.pop("pending_question"),
            "type": "choice",
            "options": options,
        }
    )
    context.user_data.pop("pending_question_type", None)
    await update.message.reply_text(
        "Added ✅\n\nSend another question, or /done to finish creating this project."
    )
    return CP_QUESTION_TEXT


async def cp_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get("cp_name")
    description = context.user_data.get("cp_description")
    if not name:
        await update.message.reply_text("Something went wrong — let's start over with ➕ Create Project.")
        context.user_data.clear()
        return ConversationHandler.END

    project_id = db.create_project(name, description)
    for i, q in enumerate(context.user_data.get("new_questions", [])):
        db.add_question(project_id, q["text"], q["type"], q["options"], order_index=i)

    await update.message.reply_text(
        f"✅ Project \"{name}\" created with "
        f"{len(context.user_data.get('new_questions', []))} custom question(s)."
    )
    context.user_data.clear()
    await update.message.reply_text("🛠 Admin Dashboard", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END


async def cp_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END


# ---------------- Edit Project ----------------

async def ep_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await guard(update):
        return ConversationHandler.END
    projects = db.get_projects(active_only=False)
    if not projects:
        await query.edit_message_text("No projects yet.", reply_markup=admin_menu_keyboard())
        return ConversationHandler.END
    await query.edit_message_text(
        "✏️ Choose a project to edit:",
        reply_markup=project_list_keyboard(projects, "editproj", include_status=True),
    )
    return EP_MENU


async def ep_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    project_id = int(query.data.split("_", 1)[1])
    context.user_data["edit_project_id"] = project_id
    project = db.get_project(project_id)
    toggle_label = "🔒 Close Project" if project["status"] == "active" else "🔓 Reopen Project"
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Rename", callback_data="epfield_name")],
            [InlineKeyboardButton("Edit Description", callback_data="epfield_description")],
            [InlineKeyboardButton(toggle_label, callback_data="epfield_toggle")],
            [InlineKeyboardButton("🗑 Clear & Redo Questions", callback_data="epfield_questions")],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_edit_project")],
        ]
    )
    await query.edit_message_text(
        f"Editing: {project['name']}\nStatus: {project['status']}\n\n{project['description'] or ''}",
        reply_markup=kb,
    )
    return EP_MENU


async def ep_field_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.split("_", 1)[1]
    if field == "toggle":
        project_id = context.user_data["edit_project_id"]
        project = db.get_project(project_id)
        new_status = "closed" if project["status"] == "active" else "active"
        db.update_project(project_id, status=new_status)
        await query.edit_message_text(f"Status updated to: {new_status}",
                                       reply_markup=admin_menu_keyboard())
        return ConversationHandler.END
    if field == "name":
        await query.edit_message_text("Send the new project name:")
        return EP_NAME
    if field == "description":
        await query.edit_message_text("Send the new description:")
        return EP_DESCRIPTION
    if field == "questions":
        context.user_data["new_questions"] = []
        await query.edit_message_text(
            "This will replace ALL existing custom questions.\n\n"
            "Send the first new question, or /done if this project should have none."
        )
        return EP_QUESTION_TEXT
    return EP_MENU


async def ep_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project_id = context.user_data["edit_project_id"]
    db.update_project(project_id, name=update.message.text.strip())
    await update.message.reply_text("✅ Name updated.", reply_markup=admin_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


async def ep_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project_id = context.user_data["edit_project_id"]
    db.update_project(project_id, description=update.message.text.strip())
    await update.message.reply_text("✅ Description updated.", reply_markup=admin_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


async def ep_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pending_question"] = update.message.text.strip()
    await update.message.reply_text("What type of answer should this question expect?",
                                     reply_markup=question_type_keyboard())
    return EP_QUESTION_TYPE


async def ep_question_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qtype = query.data.split("_", 1)[1]
    if qtype == "choice":
        await query.edit_message_text("Send the answer options, comma-separated:")
        return EP_QUESTION_OPTIONS
    context.user_data["new_questions"].append(
        {"text": context.user_data.pop("pending_question"), "type": qtype, "options": None}
    )
    await query.edit_message_text("Added ✅\n\nSend another question, or /done to finish.")
    return EP_QUESTION_TEXT


async def ep_question_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    options = update.message.text.strip()
    context.user_data["new_questions"].append(
        {"text": context.user_data.pop("pending_question"), "type": "choice", "options": options}
    )
    await update.message.reply_text("Added ✅\n\nSend another question, or /done to finish.")
    return EP_QUESTION_TEXT


async def ep_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project_id = context.user_data.get("edit_project_id")
    if not project_id:
        context.user_data.clear()
        return ConversationHandler.END
    db.clear_questions(project_id)
    for i, q in enumerate(context.user_data.get("new_questions", [])):
        db.add_question(project_id, q["text"], q["type"], q["options"], order_index=i)
    await update.message.reply_text(
        f"✅ Questions updated ({len(context.user_data.get('new_questions', []))} total).",
        reply_markup=admin_menu_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


# ---------------- Delete Project ----------------

async def dp_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await guard(update):
        return
    projects = db.get_projects(active_only=False)
    if not projects:
        await query.edit_message_text("No projects yet.", reply_markup=admin_menu_keyboard())
        return
    await query.edit_message_text(
        "❌ Choose a project to delete:",
        reply_markup=project_list_keyboard(projects, "delproj"),
    )


async def dp_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    project_id = int(query.data.split("_", 1)[1])
    project = db.get_project(project_id)
    await query.edit_message_text(
        f"Delete \"{project['name']}\" and ALL its applications? This cannot be undone.",
        reply_markup=confirm_keyboard(f"delprojconfirm_{project_id}"),
    )


async def dp_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    project_id = int(query.data.split("_", 1)[1])
    db.delete_project(project_id)
    await query.edit_message_text("🗑 Project deleted.", reply_markup=admin_menu_keyboard())


# ---------------- Statistics ----------------

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await guard(update):
        return
    stats = db.get_stats()
    lines = [
        "📊 Statistics",
        "",
        f"👥 Total users: {stats['total_users']}",
        f"📁 Total projects: {stats['total_projects']}",
        f"📝 Total applications: {stats['total_applications']}",
        "",
        "By status:",
    ]
    for status, count in stats["by_status"].items():
        lines.append(f"  • {status}: {count}")
    lines.append("")
    lines.append("By project:")
    for name, count in stats["by_project"].items():
        lines.append(f"  • {name}: {count}")
    await query.edit_message_text("\n".join(lines), reply_markup=admin_menu_keyboard())


# ---------------- Applicants ----------------

async def applicants_project_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await guard(update):
        return
    projects = db.get_projects(active_only=False)
    if not projects:
        await query.edit_message_text("No projects yet.", reply_markup=admin_menu_keyboard())
        return
    await query.edit_message_text(
        "👥 Choose a project to view applicants:",
        reply_markup=project_list_keyboard(projects, "applist"),
    )


async def applicants_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    project_id = int(query.data.split("_", 1)[1])
    apps = db.get_applications_for_project(project_id)
    if not apps:
        await query.edit_message_text("No applicants yet for this project.",
                                       reply_markup=admin_menu_keyboard())
        return
    rows = [
        [InlineKeyboardButton(
            f"#{a['id']} @{a['applicant_username'] or a['applicant_telegram_id']} — {a['status']}",
            callback_data=f"appdetail_{a['id']}",
        )]
        for a in apps
    ]
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_applicants")])
    await query.edit_message_text("Applicants:", reply_markup=InlineKeyboardMarkup(rows))


async def applicant_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    app_id = int(query.data.split("_", 1)[1])
    application = db.get_application(app_id)
    answers = db.get_answers(app_id)
    files = db.get_files(app_id)

    lines = [
        f"📋 Application #{app_id}",
        f"Project: {application['project_name']}",
        f"Applicant: @{application['applicant_username'] or application['applicant_telegram_id']}",
        f"Status: {application['status']}",
        f"Submitted: {application['submitted_at']}",
        "",
    ]
    for a in answers:
        lines.append(f"• {a['question_text']}: {a['answer_text']}")
    if files:
        lines.append("")
        lines.append(f"📎 {len(files)} file(s) attached (see below).")

    await query.edit_message_text("\n".join(lines), reply_markup=status_keyboard(app_id))

    for f in files:
        try:
            if f["file_type"] in ("image",):
                await context.bot.send_photo(query.message.chat_id, f["telegram_file_id"])
            elif f["file_type"] in ("video",):
                await context.bot.send_video(query.message.chat_id, f["telegram_file_id"])
            elif f["file_type"] in ("audio",):
                await context.bot.send_audio(query.message.chat_id, f["telegram_file_id"])
            else:
                await context.bot.send_document(query.message.chat_id, f["telegram_file_id"])
        except Exception:
            pass


async def set_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, app_id, status = query.data.split("_", 2)
    app_id = int(app_id)
    db.set_application_status(app_id, status)
    application = db.get_application(app_id)

    try:
        await context.bot.send_message(
            application["applicant_telegram_id"],
            f"📢 Update on your application to \"{application['project_name']}\":\n\n"
            f"Status: {status}",
        )
    except Exception:
        pass

    await query.edit_message_reply_markup(reply_markup=status_keyboard(app_id))
    await query.message.reply_text(f"Status set to: {status}")


async def msg_applicant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    app_id = int(query.data.split("_", 1)[1])
    context.user_data["msg_app_id"] = app_id
    await query.message.reply_text(
        "Type the message to send to this applicant (e.g. approval or feedback):"
    )
    return MSG_APPLICANT


async def msg_applicant_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    app_id = context.user_data.get("msg_app_id")
    if not app_id:
        return ConversationHandler.END
    application = db.get_application(app_id)
    text = update.message.text
    try:
        await context.bot.send_message(application["applicant_telegram_id"], text)
        await update.message.reply_text("✅ Message sent.", reply_markup=admin_menu_keyboard())
    except Exception:
        await update.message.reply_text("⚠️ Could not deliver the message (user may have blocked the bot).")
    context.user_data.clear()
    return ConversationHandler.END


# ---------------- Broadcast ----------------

async def bc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await guard(update):
        return ConversationHandler.END
    await query.edit_message_text(
        "📤 Send the broadcast message now (it will go to every user who has started the bot).\n"
        "/cancel to abort."
    )
    return BC_MESSAGE


async def bc_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["broadcast_text"] = update.message.text
    users = db.all_users()
    await update.message.reply_text(
        f"Preview:\n\n{update.message.text}\n\n"
        f"Send to {len(users)} user(s)?",
        reply_markup=confirm_keyboard("bc_confirm_yes"),
    )
    return BC_CONFIRM


async def bc_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = context.user_data.get("broadcast_text", "")
    users = db.all_users()
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(u["telegram_id"], text)
            sent += 1
        except Exception:
            pass
    db.log_broadcast(text, update.effective_user.id)
    await query.edit_message_text(f"📤 Broadcast sent to {sent}/{len(users)} user(s).",
                                   reply_markup=admin_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


# ---------------- Exports ----------------

async def do_export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating CSV...")
    if not await guard(update):
        return
    path = export_csv()
    await context.bot.send_document(query.message.chat_id, document=open(path, "rb"))


async def do_export_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating Excel...")
    if not await guard(update):
        return
    path = export_excel()
    await context.bot.send_document(query.message.chat_id, document=open(path, "rb"))


async def do_export_json(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating JSON...")
    if not await guard(update):
        return
    path = export_json()
    await context.bot.send_document(query.message.chat_id, document=open(path, "rb"))

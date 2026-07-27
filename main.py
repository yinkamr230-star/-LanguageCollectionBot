import logging

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

import database as db
from config import BOT_TOKEN
from states import (
    CHOOSING_LANGUAGE,
    APPLYING,
    UPLOADING,
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
from handlers import start as h_start
from handlers import application_flow as h_apply
from handlers import admin as h_admin

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def build_application() -> Application:
    db.init_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # ---- Language / start ----
    language_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", h_start.cmd_start),
            CommandHandler("language", h_start.cmd_language),
        ],
        states={
            CHOOSING_LANGUAGE: [
                CallbackQueryHandler(h_start.on_language_chosen, pattern=r"^lang_"),
            ],
        },
        fallbacks=[CommandHandler("start", h_start.cmd_start)],
        name="language_conv",
        persistent=False,
    )
    application.add_handler(language_conv)
    application.add_handler(
        CallbackQueryHandler(h_start.show_projects, pattern=r"^show_projects$")
    )

    # ---- Application flow (user applying to a project) ----
    apply_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(h_apply.start_application, pattern=r"^apply_\d+$"),
        ],
        states={
            APPLYING: [
                CallbackQueryHandler(h_apply.receive_choice_answer, pattern=r"^ans_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h_apply.receive_text_answer),
            ],
            UPLOADING: [
                CallbackQueryHandler(h_apply.finish_application, pattern=r"^upload_done$"),
                MessageHandler(
                    (filters.AUDIO | filters.VOICE | filters.Document.ALL |
                     filters.PHOTO | filters.VIDEO) & ~filters.COMMAND,
                    h_apply.receive_upload,
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", h_apply.cancel_application)],
        name="apply_conv",
        persistent=False,
    )
    application.add_handler(apply_conv)

    # ---- Admin: main menu / stats / delete / applicants / exports (stateless callbacks) ----
    application.add_handler(CommandHandler("admin", h_admin.cmd_admin))
    application.add_handler(CallbackQueryHandler(h_admin.admin_menu, pattern=r"^admin_menu$"))
    application.add_handler(CallbackQueryHandler(h_admin.show_stats, pattern=r"^admin_stats$"))
    application.add_handler(CallbackQueryHandler(h_admin.dp_list, pattern=r"^admin_delete_project$"))
    application.add_handler(CallbackQueryHandler(h_admin.dp_confirm, pattern=r"^delproj_\d+$"))
    application.add_handler(CallbackQueryHandler(h_admin.dp_execute, pattern=r"^delprojconfirm_\d+$"))
    application.add_handler(CallbackQueryHandler(h_admin.applicants_project_list, pattern=r"^admin_applicants$"))
    application.add_handler(CallbackQueryHandler(h_admin.applicants_list, pattern=r"^applist_\d+$"))
    application.add_handler(CallbackQueryHandler(h_admin.applicant_detail, pattern=r"^appdetail_\d+$"))
    application.add_handler(CallbackQueryHandler(h_admin.set_status, pattern=r"^setstatus_\d+_.+$"))
    application.add_handler(CallbackQueryHandler(h_admin.do_export_csv, pattern=r"^admin_export_csv$"))
    application.add_handler(CallbackQueryHandler(h_admin.do_export_excel, pattern=r"^admin_export_excel$"))
    application.add_handler(CallbackQueryHandler(h_admin.do_export_json, pattern=r"^admin_export_json$"))

    # ---- Admin: create project ----
    create_project_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h_admin.cp_start, pattern=r"^admin_create_project$")],
        states={
            CP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.cp_name)],
            CP_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.cp_description)],
            CP_QUESTION_TEXT: [
                CommandHandler("done", h_admin.cp_done),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.cp_question_text),
            ],
            CP_QUESTION_TYPE: [CallbackQueryHandler(h_admin.cp_question_type, pattern=r"^qtype_")],
            CP_QUESTION_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.cp_question_options)],
        },
        fallbacks=[CommandHandler("cancel", h_admin.cp_cancel), CommandHandler("done", h_admin.cp_done)],
        name="create_project_conv",
        persistent=False,
    )
    application.add_handler(create_project_conv)

    # ---- Admin: edit project ----
    edit_project_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h_admin.ep_list, pattern=r"^admin_edit_project$")],
        states={
            EP_MENU: [
                CallbackQueryHandler(h_admin.ep_menu, pattern=r"^editproj_\d+$"),
                CallbackQueryHandler(h_admin.ep_field_router, pattern=r"^epfield_"),
            ],
            EP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.ep_name)],
            EP_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.ep_description)],
            EP_QUESTION_TEXT: [
                CommandHandler("done", h_admin.ep_done),
                MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.ep_question_text),
            ],
            EP_QUESTION_TYPE: [CallbackQueryHandler(h_admin.ep_question_type, pattern=r"^qtype_")],
            EP_QUESTION_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.ep_question_options)],
        },
        fallbacks=[CommandHandler("cancel", h_admin.cp_cancel), CommandHandler("done", h_admin.ep_done)],
        name="edit_project_conv",
        persistent=False,
    )
    application.add_handler(edit_project_conv)

    # ---- Admin: broadcast ----
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h_admin.bc_start, pattern=r"^admin_broadcast$")],
        states={
            BC_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.bc_message)],
            BC_CONFIRM: [CallbackQueryHandler(h_admin.bc_confirm, pattern=r"^bc_confirm_yes$")],
        },
        fallbacks=[CommandHandler("cancel", h_admin.cp_cancel)],
        name="broadcast_conv",
        persistent=False,
    )
    application.add_handler(broadcast_conv)

    # ---- Admin: message a specific applicant ----
    msg_applicant_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(h_admin.msg_applicant_start, pattern=r"^msgapp_\d+$")],
        states={
            MSG_APPLICANT: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_admin.msg_applicant_send)],
        },
        fallbacks=[CommandHandler("cancel", h_admin.cp_cancel)],
        name="msg_applicant_conv",
        persistent=False,
    )
    application.add_handler(msg_applicant_conv)

    return application


def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN is not set. Copy .env.example to .env and fill in your bot token."
        )
    application = build_application()
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

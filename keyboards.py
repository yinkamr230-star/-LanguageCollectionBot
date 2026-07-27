from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import APPLICATION_STATUSES
from translations import available_languages


def language_keyboard():
    langs = available_languages()
    row, rows = [], []
    for code, name in langs.items():
        row.append(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def start_keyboard(lang="en"):
    from translations import t
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t("btn_start", lang), callback_data="show_projects")]]
    )


def projects_keyboard(projects):
    rows = [
        [InlineKeyboardButton(p["name"], callback_data=f"apply_{p['id']}")]
        for p in projects
    ]
    return InlineKeyboardMarkup(rows)


def admin_menu_keyboard():
    rows = [
        [InlineKeyboardButton("➕ Create Project", callback_data="admin_create_project")],
        [InlineKeyboardButton("✏ Edit Project", callback_data="admin_edit_project")],
        [InlineKeyboardButton("❌ Delete Project", callback_data="admin_delete_project")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Applicants", callback_data="admin_applicants")],
        [InlineKeyboardButton("📤 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📥 Export CSV", callback_data="admin_export_csv")],
        [InlineKeyboardButton("📥 Export Excel", callback_data="admin_export_excel")],
        [InlineKeyboardButton("📥 Export JSON", callback_data="admin_export_json")],
    ]
    return InlineKeyboardMarkup(rows)


def project_list_keyboard(projects, prefix, include_status=False):
    rows = []
    for p in projects:
        label = p["name"]
        if include_status:
            label += f" [{p['status']}]"
        rows.append([InlineKeyboardButton(label, callback_data=f"{prefix}_{p['id']}")])
    rows.append([InlineKeyboardButton("⬅ Back", callback_data="admin_menu")])
    return InlineKeyboardMarkup(rows)


def question_type_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Text", callback_data="qtype_text"),
                InlineKeyboardButton("Number", callback_data="qtype_number"),
                InlineKeyboardButton("Choice", callback_data="qtype_choice"),
            ]
        ]
    )


def status_keyboard(application_id):
    rows = []
    row = []
    for i, status in enumerate(APPLICATION_STATUSES, 1):
        row.append(
            InlineKeyboardButton(status, callback_data=f"setstatus_{application_id}_{status}")
        )
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [InlineKeyboardButton("✉ Message Applicant", callback_data=f"msgapp_{application_id}")]
    )
    return InlineKeyboardMarkup(rows)


def confirm_keyboard(yes_data, no_data="admin_menu"):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes", callback_data=yes_data),
                InlineKeyboardButton("🚫 Cancel", callback_data=no_data),
            ]
        ]
    )

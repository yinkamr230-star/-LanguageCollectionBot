import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
DB_PATH = os.getenv("DB_PATH", "data/bot.db")

# Standard fields asked for EVERY project, in order.
# key -> (english label, field_type)  field_type: text | choice
STANDARD_FIELDS = [
    ("full_name", "Full Name", "text"),
    ("country", "Country", "text"),
    ("native_language", "Native Language", "text"),
    ("other_languages", "Other Languages", "text"),
    ("email", "Email", "text"),
    ("telegram_username", "Telegram Username", "text"),
    ("company_freelancer", "Company/Freelancer", "choice:Company,Freelancer"),
    ("available_hours", "Available Hours (per week)", "text"),
    ("experience", "Experience", "text"),
    ("expected_rate", "Expected Rate", "text"),
    ("delivery_time", "Delivery Time", "text"),
]

# File types accepted during upload step, and how we detect them from Telegram updates.
ALLOWED_UPLOAD_TYPES = ["audio", "zip", "csv", "excel", "pdf", "image", "video"]

APPLICATION_STATUSES = [
    "Pending",
    "Under Review",
    "Approved",
    "Rejected",
    "Need More Info",
]

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "ja": "Japanese",
    "zh": "Chinese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ar": "Arabic",
    "pt": "Portuguese",
    "ru": "Russian",
}

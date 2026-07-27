from itertools import count

_c = count()

# --- Language ---
CHOOSING_LANGUAGE = next(_c)

# --- Application flow (user side) ---
APPLYING = next(_c)
UPLOADING = next(_c)

# --- Admin: create project ---
CP_NAME = next(_c)
CP_DESCRIPTION = next(_c)
CP_QUESTION_TEXT = next(_c)
CP_QUESTION_TYPE = next(_c)
CP_QUESTION_OPTIONS = next(_c)

# --- Admin: edit project ---
EP_MENU = next(_c)
EP_NAME = next(_c)
EP_DESCRIPTION = next(_c)
EP_QUESTION_TEXT = next(_c)
EP_QUESTION_TYPE = next(_c)
EP_QUESTION_OPTIONS = next(_c)

# --- Admin: broadcast ---
BC_MESSAGE = next(_c)
BC_CONFIRM = next(_c)

# --- Admin: applicant messaging ---
MSG_APPLICANT = next(_c)

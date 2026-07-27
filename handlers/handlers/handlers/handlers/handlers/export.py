import csv
import json
import os
from datetime import datetime

from openpyxl import Workbook

import database as db

EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")


def _build_rows():
    apps = db.get_all_applications()
    rows = []
    all_keys = []
    per_app_answers = {}
    for app in apps:
        answers = db.get_answers(app["id"])
        answer_map = {a["question_key"]: a["answer_text"] for a in answers}
        per_app_answers[app["id"]] = (answers, answer_map)
        for a in answers:
            if a["question_key"] not in all_keys:
                all_keys.append(a["question_key"])

    for app in apps:
        files = db.get_files(app["id"])
        _, answer_map = per_app_answers[app["id"]]
        row = {
            "application_id": app["id"],
            "project": app["project_name"],
            "applicant_telegram_id": app["applicant_telegram_id"],
            "applicant_username": app["applicant_username"],
            "status": app["status"],
            "submitted_at": app["submitted_at"],
            "files_count": len(files),
        }
        for key in all_keys:
            row[key] = answer_map.get(key, "")
        rows.append(row)
    return rows, ["application_id", "project", "applicant_telegram_id", "applicant_username",
                  "status", "submitted_at", "files_count"] + all_keys


def export_csv():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    rows, columns = _build_rows()
    path = os.path.join(EXPORT_DIR, f"applications_{_ts()}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return path


def export_excel():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    rows, columns = _build_rows()
    wb = Workbook()
    ws = wb.active
    ws.title = "Applications"
    ws.append(columns)
    for r in rows:
        ws.append([r.get(c, "") for c in columns])
    path = os.path.join(EXPORT_DIR, f"applications_{_ts()}.xlsx")
    wb.save(path)
    return path


def export_json():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    rows, _ = _build_rows()
    path = os.path.join(EXPORT_DIR, f"applications_{_ts()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    return path


def _ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

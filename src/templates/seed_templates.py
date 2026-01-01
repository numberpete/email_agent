from __future__ import annotations

import argparse

from src.templates.sqlite_template_store import SQLiteTemplateStore
from src.templates.fixtures.templates import TEMPLATES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="Path to sqlite db file, e.g. data/email_assist.db")
    args = parser.parse_args()

    store = SQLiteTemplateStore(args.db)
    for tpl in TEMPLATES:
        store.upsert_template(tpl)

    print(f"Seeded {len(TEMPLATES)} templates into {args.db}")


if __name__ == "__main__":
    main()

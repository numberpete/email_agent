from __future__ import annotations

import argparse

from src.profiles.sqlite_profile_store import SQLiteProfileStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--user_id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--org", default="")
    parser.add_argument("--email", default="")
    args = parser.parse_args()

    store = SQLiteProfileStore(args.db)
    store.upsert_profile(
        args.user_id,
        {
            "name": args.name,
            "title": args.title,
            "org": args.org,
            "email": args.email,
            # add later: preferred_signoff, timezone, etc.
        },
    )
    print(f"Upserted profile for user_id={args.user_id} into {args.db}")


if __name__ == "__main__":
    main()

"""
make_admin.py
One-time terminal script: promotes an existing recruiter account to admin.

Usage:
    1. First, sign up normally through the app with the email you want
       to be the admin (this creates a 'recruiter' account).
    2. Then run this script from the terminal, inside milestone2/milestone2:
           python make_admin.py you@company.com
    3. Log out and log back in on the app -- you'll now see admin-only
       pages/features.
"""

import sys
from db import init_db, set_recruiter_role, get_recruiter_by_email

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python make_admin.py <email>")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    init_db()

    existing = get_recruiter_by_email(email)
    if not existing:
        print(f"No account found for {email}. Sign up through the app first, then run this again.")
        sys.exit(1)

    if existing.get("role") == "admin":
        print(f"{email} is already an admin.")
        sys.exit(0)

    if set_recruiter_role(email, "admin"):
        print(f"Done -- {email} is now an admin. Log out and log back in on the app.")
    else:
        print("Something went wrong -- role was not updated.")

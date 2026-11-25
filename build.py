"""Vercel build step (wired up in pyproject.toml under [tool.vercel.scripts]).

Vercel installs dependencies, runs this script, then runs collectstatic and deploys.
Migrations run here on *production* builds only, so a preview deployment can never
change the production schema. A failed migration fails the build, which means the
previous deployment stays live.
"""

import os
import subprocess
import sys


def manage(*args: str) -> None:
    print("$ python manage.py", " ".join(args), flush=True)
    subprocess.run([sys.executable, "manage.py", *args], check=True)


def main() -> None:
    vercel_env = os.environ.get("VERCEL_ENV", "")
    manage("check", "--deploy", "--fail-level", "ERROR")
    if vercel_env == "production" or os.environ.get("RUN_MIGRATIONS_ON_BUILD") == "1":
        manage("migrate", "--noinput")
    else:
        print(f"Skipping migrations (VERCEL_ENV={vercel_env or 'unset'}).", flush=True)


if __name__ == "__main__":
    main()

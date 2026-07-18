"""One-time setup: create the saved 'Iris' Backboard assistant via the documented
POST /assistants endpoint, using prompts/system_prompt.txt as its system prompt.

Requires BACKBOARD_API_KEY in .env (get one at https://app.backboard.io ->
Settings -> API Keys).

Usage:
    python scripts/setup_backboard_assistant.py

Prints the resulting assistant_id — copy it into BACKBOARD_ASSISTANT_ID in .env.
"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config  # noqa: E402

ASSISTANT_NAME = "Iris"


def main() -> None:
    config = load_config()
    if not config.backboard_api_key:
        print("BACKBOARD_API_KEY is not set in .env. Get one at https://app.backboard.io "
              "(Settings -> API Keys) and set it first.")
        raise SystemExit(1)

    system_prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"
    system_prompt = system_prompt_path.read_text()

    response = requests.post(
        f"{config.backboard_base_url}/assistants",
        json={"name": ASSISTANT_NAME, "system_prompt": system_prompt},
        headers={"X-API-Key": config.backboard_api_key},
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    assistant = response.json()

    print(f"Created Backboard assistant '{ASSISTANT_NAME}'.")
    print(f"assistant_id: {assistant['assistant_id']}")
    print("Set this as BACKBOARD_ASSISTANT_ID in your .env file.")


if __name__ == "__main__":
    main()

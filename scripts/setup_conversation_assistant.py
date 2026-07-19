"""Create or update the saved 'Iris Conversation' Backboard assistant, using
prompts/conversation_system_prompt.txt as its system prompt.

This is a SEPARATE assistant from the one BACKBOARD_ASSISTANT_ID points to —
it drives the "Let's talk about it" follow-up conversation, with its own
prompt and JSON schema, not the one-shot interpretation flow.

If BACKBOARD_CONVERSATION_ASSISTANT_ID is already set in .env, this updates
that existing assistant in place via the documented PUT /assistants/{assistant_id}
endpoint — so re-running this after editing conversation_system_prompt.txt
keeps your existing assistant_id valid instead of creating a new assistant
every time. Otherwise it creates a new one via POST /assistants.

Requires BACKBOARD_API_KEY in .env (get one at https://app.backboard.io ->
Settings -> API Keys).

Usage:
    python scripts/setup_conversation_assistant.py

On first run, prints the resulting assistant_id — copy it into
BACKBOARD_CONVERSATION_ASSISTANT_ID in .env. On later runs (once
BACKBOARD_CONVERSATION_ASSISTANT_ID is set), just updates that assistant's
system prompt.
"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config  # noqa: E402

ASSISTANT_NAME = "Iris Conversation"


def main() -> None:
    config = load_config()
    if not config.backboard_api_key:
        print("BACKBOARD_API_KEY is not set in .env. Get one at https://app.backboard.io "
              "(Settings -> API Keys) and set it first.")
        raise SystemExit(1)

    project_root = Path(__file__).resolve().parent.parent

    system_prompt_path = project_root / "prompts" / "conversation_system_prompt.txt"
    system_prompt = system_prompt_path.read_text()

    if config.backboard_conversation_assistant_id:
        response = requests.put(
            f"{config.backboard_base_url}/assistants/{config.backboard_conversation_assistant_id}",
            json={"name": ASSISTANT_NAME, "system_prompt": system_prompt},
            headers={"X-API-Key": config.backboard_api_key},
            timeout=config.request_timeout_seconds,
        )
        response.raise_for_status()
        print(f"Updated Backboard assistant '{ASSISTANT_NAME}' "
              f"(assistant_id: {config.backboard_conversation_assistant_id}) "
              "with the current prompts/conversation_system_prompt.txt.")
        return

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
    print("Set this as BACKBOARD_CONVERSATION_ASSISTANT_ID in your .env file.")


if __name__ == "__main__":
    main()

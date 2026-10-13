"""Send a build result using Jenkins-bound secrets without logging them."""

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Telegram: bot token or chat ID is missing", file=sys.stderr)
        return 1
    text = "\n".join(
        [
            f"InvestHelper: {os.environ.get('BUILD_RESULT', 'UNKNOWN')}",
            f"Job: {os.environ.get('JOB_NAME', '?')}",
            f"Branch: {os.environ.get('BRANCH_NAME', '?')}",
            f"Build: #{os.environ.get('BUILD_NUMBER', '?')}",
            f"Image: {os.environ.get('IMAGE_TAG', 'not built')}",
            os.environ.get("BUILD_URL", ""),
        ]
    )[:4000]
    data = json.dumps(
        {"chat_id": chat_id, "text": text, "link_preview_options": {"is_disabled": True}}
    ).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.load(response)
        if result.get("ok") is not True:
            print("Telegram: API rejected notification", file=sys.stderr)
            return 1
    except urllib.error.HTTPError as exc:
        # Do not print exception URLs or response bodies: they can contain secrets.
        print(f"Telegram: HTTP {exc.code}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        print("Telegram: transport error or invalid response", file=sys.stderr)
        return 1
    print("Telegram: notification sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())

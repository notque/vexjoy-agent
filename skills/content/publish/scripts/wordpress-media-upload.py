#!/usr/bin/env python3
"""
WordPress REST API media uploader.

Uploads images and other media files to WordPress media library.

Usage:
    python3 skills/content/publish/scripts/wordpress-media-upload.py --file image.jpg
    python3 skills/content/publish/scripts/wordpress-media-upload.py --file image.jpg --alt "Alt text" --caption "Caption"
    python3 skills/content/publish/scripts/wordpress-media-upload.py --file image.jpg --title "Image Title"

Environment Variables (from ~/.env):
    WORDPRESS_SITE         WordPress site URL (e.g., https://your-blog.com)
    WORDPRESS_USER         WordPress username
    WORDPRESS_APP_PASSWORD Application password from WordPress admin

Exit codes:
    0 = success
    1 = error
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any


def load_env_file(env_path: Path | None = None) -> dict[str, str]:
    """Load environment variables from .env file."""
    if env_path is None:
        env_path = Path.home() / ".env"

    env_vars: dict[str, str] = {}

    if not env_path.exists():
        return env_vars

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def get_config() -> dict[str, str]:
    """Get WordPress configuration from environment."""
    env_vars = load_env_file()

    config = {
        "site": os.environ.get("WORDPRESS_SITE", env_vars.get("WORDPRESS_SITE", "")),
        "user": os.environ.get("WORDPRESS_USER", env_vars.get("WORDPRESS_USER", "")),
        "password": os.environ.get("WORDPRESS_APP_PASSWORD", env_vars.get("WORDPRESS_APP_PASSWORD", "")),
    }

    return config


def validate_config(config: dict[str, str]) -> list[str]:
    """Validate configuration, return list of errors."""
    errors = []

    if not config["site"]:
        errors.append("WORDPRESS_SITE not set")
    if not config["user"]:
        errors.append("WORDPRESS_USER not set")
    if not config["password"]:
        errors.append("WORDPRESS_APP_PASSWORD not set")

    if config["site"] and not config["site"].startswith("https://"):
        errors.append("WORDPRESS_SITE must use HTTPS for Application Passwords")

    return errors


def upload_media(
    config: dict[str, str],
    file_path: Path,
    title: str | None = None,
    alt_text: str | None = None,
    caption: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Upload media file to WordPress."""
    try:
        import requests
    except ImportError:
        return {
            "status": "error",
            "error": "requests library not installed. Run: pip install requests",
        }

    if not file_path.exists():
        return {
            "status": "error",
            "error": f"File not found: {file_path}",
        }

    # Determine content type
    content_type, _ = mimetypes.guess_type(str(file_path))
    if not content_type:
        content_type = "application/octet-stream"

    # Build API URL
    api_url = f"{config['site'].rstrip('/')}/wp-json/wp/v2/media"

    # Create Basic Auth header
    credentials = f"{config['user']}:{config['password']}"
    token = base64.b64encode(credentials.encode()).decode("utf-8")

    # Use the file name as title if not provided
    filename = file_path.name
    if title is None:
        title = file_path.stem  # filename without extension

    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": content_type,
        "Content-Disposition": f'attachment; filename="{filename}"',
    }

    try:
        # Read file content
        with open(file_path, "rb") as f:
            file_data = f.read()

        # Upload the file
        response = requests.post(api_url, headers=headers, data=file_data, timeout=60)

        if response.status_code == 201:
            data = response.json()
            media_id = data.get("id")

            # Update metadata if provided
            if alt_text or caption or description or title:
                update_data: dict[str, Any] = {}
                if title:
                    update_data["title"] = title
                if alt_text:
                    update_data["alt_text"] = alt_text
                if caption:
                    update_data["caption"] = caption
                if description:
                    update_data["description"] = description

                if update_data:
                    update_url = f"{api_url}/{media_id}"
                    update_headers = {
                        "Authorization": f"Basic {token}",
                        "Content-Type": "application/json",
                    }
                    requests.post(update_url, headers=update_headers, json=update_data, timeout=30)

            return {
                "status": "success",
                "media_id": media_id,
                "url": data.get("source_url"),
                "title": data.get("title", {}).get("rendered", ""),
                "media_type": data.get("media_type"),
                "mime_type": data.get("mime_type"),
            }
        else:
            error_data = {}
            try:
                error_data = response.json()
            except Exception:
                pass

            return {
                "status": "error",
                "http_status": response.status_code,
                "error": error_data.get("message", response.text[:500]),
                "code": error_data.get("code", "unknown"),
            }

    except requests.exceptions.ConnectionError as e:
        return {
            "status": "error",
            "error": f"Connection failed: {e}",
        }
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "error": "Request timed out after 60 seconds",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Unexpected error: {e}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload media files to WordPress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--file",
        "-f",
        required=True,
        help="Path to media file to upload",
    )
    parser.add_argument(
        "--title",
        "-t",
        help="Media title (defaults to filename)",
    )
    parser.add_argument(
        "--alt",
        help="Alt text for the media",
    )
    parser.add_argument(
        "--caption",
        help="Caption for the media",
    )
    parser.add_argument(
        "--description",
        help="Description for the media",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (default)",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        help="Output human-readable format",
    )

    args = parser.parse_args()

    # Load and validate config
    config = get_config()
    errors = validate_config(config)

    if errors:
        result = {
            "status": "error",
            "error": "Configuration errors",
            "details": errors,
        }
        print(json.dumps(result, indent=2))
        return 1

    # Upload media
    file_path = Path(args.file)
    result = upload_media(
        config=config,
        file_path=file_path,
        title=args.title,
        alt_text=args.alt,
        caption=args.caption,
        description=args.description,
    )

    # Output
    if args.human and result["status"] == "success":
        print("Media uploaded successfully!")
        print(f"  ID: {result['media_id']}")
        print(f"  URL: {result['url']}")
        print(f"  Type: {result['mime_type']}")
    else:
        print(json.dumps(result, indent=2))

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

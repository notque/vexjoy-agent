#!/usr/bin/env python3
"""
road-to-aew project integration helper.

Subcommands:
    snake-case      Convert a display name to snake_case ID
    deploy          Copy a portrait PNG into the road-to-aew assets tree, optionally regen manifest
    list-existing   List existing sprite IDs to detect collisions

Default project root: ~/road-to-aew. Override with --target-dir.

Deploy paths:
    enemies          public/assets/characters/enemies/<id>.png
    player male      public/assets/characters/player/male/<id>.png
    player female    public/assets/characters/player/female/<id>.png

Manifest regeneration runs `npm run generate:sprites` when --regen-manifest
is set. Otherwise, prints a reminder.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.road_to_aew_integration")


def snake_case(name: str) -> str:
    """Convert display name to snake_case ID.

    Drop leading articles (The/A/An), lowercase, replace spaces/hyphens with
    underscores, strip non-alphanumeric, collapse repeated underscores.
    """
    parts = name.strip().split()
    while parts and parts[0].lower() in {"the", "a", "an"}:
        parts.pop(0)
    s = " ".join(parts).lower()
    cleaned: list[str] = []
    for ch in s:
        if ch.isalnum():
            cleaned.append(ch)
        elif ch.isspace() or ch == "-":
            cleaned.append("_")
    out = "".join(cleaned)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def resolve_project_root(target_dir: str | None) -> Path:
    """Resolve the road-to-aew project root."""
    if target_dir:
        root = Path(target_dir).expanduser().resolve()
    else:
        root = (Path.home() / "road-to-aew").resolve()
    return root


def resolve_deploy_path(root: Path, sprite_id: str, player: str | None) -> Path:
    """Compute the destination PNG path."""
    if player:
        return root / "public" / "assets" / "characters" / "player" / player / f"{sprite_id}.png"
    return root / "public" / "assets" / "characters" / "enemies" / f"{sprite_id}.png"


def cmd_snake_case(args: argparse.Namespace) -> int:
    print(snake_case(args.name))
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.target_dir)
    sprite_id = snake_case(args.display_name)

    if args.dry_run:
        # In dry-run we still validate the path resolution but do not require the project on disk
        dst = resolve_deploy_path(root, sprite_id, args.player)
        logger.info("[deploy:dry-run] would copy %s -> %s", args.source, dst)
        if args.regen_manifest:
            logger.info(
                "[deploy:dry-run] would run `cd %s && npm run generate:sprites`",
                root,
            )
        return 0

    if not root.exists():
        logger.error(
            "road-to-aew directory not found at %s\n"
            "Pass --target-dir <explicit-path> or clone the repo to ~/road-to-aew.",
            root,
        )
        return 7

    src = Path(args.source).resolve()
    if not src.exists():
        logger.error("source PNG not found: %s", src)
        return 2

    dst = resolve_deploy_path(root, sprite_id, args.player)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    logger.info("[deploy] %s -> %s", src, dst)

    if args.regen_manifest:
        try:
            subprocess.run(
                ["npm", "run", "generate:sprites"],
                cwd=root,
                check=True,
                timeout=120,
            )
            logger.info("[deploy] manifest regenerated via npm run generate:sprites")
        except FileNotFoundError:
            logger.error("npm not in PATH; cannot regen manifest")
            return 8
        except subprocess.CalledProcessError as e:
            logger.error("npm run generate:sprites failed (exit %d)", e.returncode)
            return e.returncode
        except subprocess.TimeoutExpired:
            logger.error("npm run generate:sprites timed out after 120s")
            return 124
    else:
        logger.info(
            "[deploy] To refresh manifest: cd %s && npm run generate:sprites",
            root,
        )
    return 0


def cmd_list_existing(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.target_dir)
    if not root.exists():
        logger.error("road-to-aew directory not found at %s", root)
        return 7

    enemies_dir = root / "public" / "assets" / "characters" / "enemies"
    player_male = root / "public" / "assets" / "characters" / "player" / "male"
    player_female = root / "public" / "assets" / "characters" / "player" / "female"

    ids: list[str] = []
    for d in (enemies_dir, player_male, player_female):
        if d.exists():
            ids.extend(sorted(p.stem for p in d.glob("*.png")))

    for sprite_id in ids:
        print(sprite_id)
    logger.info("[list-existing] %d sprite IDs in %s", len(ids), root)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("snake-case", help="Convert display name to snake_case ID")
    sc.add_argument("name", help="Display name (e.g., 'Bangkok Belle Nisa')")
    sc.set_defaults(func=cmd_snake_case)

    dp = sub.add_parser("deploy", help="Copy portrait into road-to-aew assets tree")
    dp.add_argument("--source", required=True, help="Path to the portrait PNG to deploy")
    dp.add_argument("--display-name", required=True, help="Character display name")
    dp.add_argument("--target-dir", help="Override road-to-aew root (default: ~/road-to-aew)")
    dp.add_argument("--player", choices=["male", "female"], help="Deploy as player sprite")
    dp.add_argument("--regen-manifest", action="store_true", help="Run npm run generate:sprites after deploy")
    dp.add_argument("--dry-run", action="store_true", help="Validate paths; do not copy or regen")
    dp.set_defaults(func=cmd_deploy)

    ls = sub.add_parser("list-existing", help="List existing sprite IDs (collision check)")
    ls.add_argument("--target-dir", help="Override road-to-aew root")
    ls.set_defaults(func=cmd_list_existing)

    return parser


def main(argv: list[str] | None = None) -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(name)s] %(levelname)s: %(message)s",
            stream=sys.stderr,
        )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

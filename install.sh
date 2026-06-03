#!/bin/bash
#
# VexJoy Agent - Installation Script
#
# This script sets up the VexJoy Agent ecosystem in your Claude Code environment.
#
# Usage:
#   ./install.sh              # Interactive install
#   ./install.sh --symlink    # Use symlinks (recommended for development)
#   ./install.sh --copy       # Copy files (recommended for stability)
#   ./install.sh --uninstall  # Remove installation
#   ./install.sh --dry-run    # Show what would happen without making changes
#
# What this script does:
#   1. Verifies Python 3.10+ is available
#   2. Creates ~/.claude directory if needed
#   3. Links/copies agents, skills, hooks, commands, scripts to ~/.claude
#   4. Mirrors skills, agents, hooks, and scripts to ~/.codex, ~/.gemini, ~/.factory,
#      ~/.hermes, and ~/.reasonix (no agent surface for ~/.reasonix)
#   5. Sets up local overlay directory
#   6. Configures hooks in settings.json
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
CODEX_DIR="${HOME}/.codex"
CODEX_SKILLS_DIR="${CODEX_DIR}/skills"
CODEX_AGENTS_DIR="${CODEX_DIR}/agents"
CODEX_HOOKS_DIR="${CODEX_DIR}/hooks"
CODEX_SCRIPTS_DIR="${CODEX_DIR}/scripts"
GEMINI_DIR="${HOME}/.gemini"
ANTIGRAVITY_DIR="${HOME}/.gemini/antigravity"
ANTIGRAVITY_PLUGINS_DIR="${ANTIGRAVITY_DIR}/plugins"
ANTIGRAVITY_PLUGIN_DIR="${ANTIGRAVITY_PLUGINS_DIR}/vexjoy-agent"
GEMINI_SKILLS_DIR="${GEMINI_DIR}/skills"
GEMINI_AGENTS_DIR="${GEMINI_DIR}/agents"
GEMINI_HOOKS_DIR="${GEMINI_DIR}/hooks"
GEMINI_SCRIPTS_DIR="${GEMINI_DIR}/scripts"
FACTORY_DIR="${HOME}/.factory"
FACTORY_SKILLS_DIR="${FACTORY_DIR}/skills"
FACTORY_DROIDS_DIR="${FACTORY_DIR}/droids"
FACTORY_HOOKS_DIR="${FACTORY_DIR}/hooks"
FACTORY_COMMANDS_DIR="${FACTORY_DIR}/commands"
FACTORY_SCRIPTS_DIR="${FACTORY_DIR}/scripts"
HERMES_DIR="${HOME}/.hermes"
HERMES_SKILLS_DIR="${HERMES_DIR}/skills"
HERMES_SCRIPTS_DIR="${HERMES_DIR}/scripts"
REASONIX_DIR="${HOME}/.reasonix"
REASONIX_SKILLS_DIR="${REASONIX_DIR}/skills"
REASONIX_SCRIPTS_DIR="${REASONIX_DIR}/scripts"
REASONIX_HOOKS_DIR="${REASONIX_DIR}/hooks"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                VexJoy Agent - Installation Script               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Parse arguments
MODE=""
DRY_RUN=false
FORCE=true  # Default to force — never prompt about existing directories
CONFLICT_MODE=""  # per-item | replace | skip; set by --per-item/--sync or conflict prompt
while [[ $# -gt 0 ]]; do
    case $1 in
        --symlink)
            MODE="symlink"
            shift
            ;;
        --copy)
            MODE="copy"
            shift
            ;;
        --uninstall)
            MODE="uninstall"
            shift
            ;;
        --rollback)
            MODE="rollback"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force|-f)
            FORCE=true  # Already default, accepted for backward compat
            shift
            ;;
        --no-force)
            FORCE=false  # Opt in to interactive prompts
            shift
            ;;
        --per-item)
            CONFLICT_MODE="per-item"
            shift
            ;;
        --sync)
            CONFLICT_MODE="per-item"
            # --sync implies symlink mode when MODE is not yet set
            [ -z "$MODE" ] && MODE="symlink"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--symlink|--copy|--uninstall|--rollback|--dry-run|--force|--per-item|--sync]"
            echo ""
            echo "Options:"
            echo "  --symlink    Create symlinks to this repo (recommended for development)"
            echo "  --copy       Copy files to ~/.claude (recommended for stability)"
            echo "  --uninstall  Remove the installation"
            echo "  --rollback   Restore settings.json from the most recent backup"
            echo "  --dry-run    Show what would happen without making changes"
            echo "  --force      Replace existing directories without prompting (default)"
            echo "  --no-force   Prompt before replacing existing directories"
            echo "  --per-item   Symlink each item individually; preserve external content"
            echo "  --sync       Alias for --per-item; implies --symlink mode default"
            echo ""
            echo "If no option provided, will prompt interactively."
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Dry run banner
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║                          DRY RUN MODE                          ║${NC}"
    echo -e "${YELLOW}║             No changes will be made to your system             ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
fi

# Function to check Python version
check_python() {
    echo -e "${YELLOW}Checking Python version...${NC}"

    # Try python3 first, then python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo -e "${RED}Error: Python not found. Please install Python 3.10+${NC}"
        exit 1
    fi

    # Check version
    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
        echo -e "${RED}Error: Python 3.10+ required, found $PYTHON_VERSION${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
}

# Prefer pip from the validated Python interpreter so dependency installs land
# in the same environment used by the rest of the installer. Fall back to
# platform-native pip commands only if that interpreter does not have pip.
detect_pip_command() {
    if "$PYTHON_CMD" -m pip --version &> /dev/null; then
        PIP_CMD=("$PYTHON_CMD" -m pip)
    elif command -v pip3 &> /dev/null; then
        PIP_CMD=(pip3)
    elif command -v pip &> /dev/null; then
        PIP_CMD=(pip)
    else
        echo -e "${RED}Error: pip not found. Please install pip for ${PYTHON_CMD}.${NC}"
        exit 1
    fi

    if ! "${PIP_CMD[@]}" --version &> /dev/null; then
        echo -e "${RED}Error: ${PIP_CMD[*]} found but appears broken.${NC}"
        exit 1
    fi
}

pip_supports_break_system_packages() {
    "${PIP_CMD[@]}" install --help 2>/dev/null | grep -q -- "--break-system-packages"
}

print_manual_pip_command() {
    local use_break_system_packages=${1:-false}
    local -a manual_cmd=("${PIP_CMD[@]}" install -r "${SCRIPT_DIR}/requirements.txt")
    local manual_cmd_str

    if [ "$use_break_system_packages" = true ]; then
        manual_cmd+=(--break-system-packages)
    fi

    printf -v manual_cmd_str '%q ' "${manual_cmd[@]}"
    echo "  Run manually: ${manual_cmd_str% }"
}

# Function to uninstall
uninstall() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║               VexJoy Agent - Uninstaller               ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    MANIFEST_FILE="${CLAUDE_DIR}/.install-manifest.json"
    SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
    COMPONENTS=(agents skills hooks commands scripts)
    REMOVED=()
    PRESERVED=()

    # Phase 1: Determine install mode from manifest or fall back to detection
    echo -e "${YELLOW}Reading install manifest...${NC}"
    INSTALL_MODE=""
    if [ -f "$MANIFEST_FILE" ]; then
        INSTALL_MODE=$(python3 -c "import json; print(json.load(open('${MANIFEST_FILE}')).get('mode', ''))" 2>/dev/null || echo "")
        if [ -n "$INSTALL_MODE" ]; then
            echo -e "${GREEN}  ✓ Manifest found (mode: ${INSTALL_MODE})${NC}"
        else
            echo -e "${YELLOW}  Manifest found but mode unreadable. Falling back to detection.${NC}"
        fi
    else
        echo -e "${YELLOW}  No manifest found. Falling back to symlink detection.${NC}"
    fi

    # Phase 2: Remove component directories and symlinks
    echo ""
    echo -e "${YELLOW}Removing installed components...${NC}"
    for item in "${COMPONENTS[@]}"; do
        target="${CLAUDE_DIR}/${item}"
        if [ -L "$target" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would remove symlink: ${target}${NC}"
            else
                rm "$target"
                echo -e "${GREEN}  ✓ Removed symlink: ${target}${NC}"
            fi
            REMOVED+=("$item (symlink)")
        elif [ -d "$target" ]; then
            # Only remove directories if the manifest says we copied them,
            # or if no manifest exists (best-effort cleanup)
            if [ "$INSTALL_MODE" = "copy" ] || [ -z "$INSTALL_MODE" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove directory: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed directory: ${target}${NC}"
                fi
                REMOVED+=("$item (directory)")
            else
                echo -e "${YELLOW}  Skipping ${target}: manifest says symlink but found directory${NC}"
                PRESERVED+=("$item (unexpected directory, not removed)")
            fi
        else
            echo "  Not found: ${target} (already removed or never installed)"
        fi
    done

    # Phase 2.5: Clean private-voice entries from repo skills directory
    if [ -d "${SCRIPT_DIR}/private-voices" ]; then
        echo ""
        echo -e "${YELLOW}Cleaning private voice entries from skills/...${NC}"
        for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
            [ -d "$voice_dir" ] || continue
            voice_name=$(basename "$voice_dir")
            target="${SCRIPT_DIR}/skills/voice-${voice_name}"
            if [ -L "$target" ] || [ -e "$target" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed voice-${voice_name} from skills/${NC}"
                fi
                REMOVED+=("voice-${voice_name} from skills/")
            fi
        done

        # Clean voice shared references from skills/shared-patterns/
        if [ -d "${SCRIPT_DIR}/private-voices/shared-references" ]; then
            echo ""
            echo -e "${YELLOW}Cleaning voice shared references from skills/shared-patterns/...${NC}"
            for ref_file in "${SCRIPT_DIR}/private-voices/shared-references/"*.md; do
                [ -f "$ref_file" ] || continue
                ref_name=$(basename "$ref_file")
                target="${SCRIPT_DIR}/skills/shared-patterns/${ref_name}"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove: ${target}${NC}"
                    else
                        rm -f "$target"
                        echo -e "${GREEN}  ✓ Removed ${ref_name} from skills/shared-patterns/${NC}"
                    fi
                    REMOVED+=("${ref_name} from skills/shared-patterns/")
                fi
            done
        fi
    fi

    # Phase 3: Clean hooks from settings.json
    echo ""
    echo -e "${YELLOW}Cleaning hooks from settings.json...${NC}"
    if [ -f "$SETTINGS_FILE" ]; then
        # Check if hooks key exists
        HAS_HOOKS=$(python3 -c "import json; d=json.load(open('${SETTINGS_FILE}')); print('yes' if 'hooks' in d else 'no')" 2>/dev/null || echo "no")
        if [ "$HAS_HOOKS" = "yes" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would back up: ${SETTINGS_FILE}${NC}"
                echo -e "${BLUE}  Would remove 'hooks' key from settings.json${NC}"
            else
                # Create timestamped backup (same pattern as installer)
                BACKUP_TS=$(date +%Y%m%d-%H%M%S)
                cp "$SETTINGS_FILE" "${SETTINGS_FILE}.backup.${BACKUP_TS}"
                echo -e "${GREEN}  ✓ Backed up settings.json to settings.json.backup.${BACKUP_TS}${NC}"

                # Remove the hooks key, preserve everything else
                python3 -c "
import json, os
dst = '${SETTINGS_FILE}'
with open(dst, encoding='utf-8') as f:
    data = json.load(f)
data.pop('hooks', None)
tmp = dst + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.rename(tmp, dst)
"
                echo -e "${GREEN}  ✓ Removed hooks from settings.json${NC}"
            fi
            REMOVED+=("hooks config from settings.json")
        else
            echo "  No hooks key found in settings.json. Nothing to clean."
        fi
    else
        echo "  No settings.json found. Nothing to clean."
    fi

    # Phase 3.5: Clean toolkit-owned Codex mirror entries
    echo ""
    echo -e "${YELLOW}Cleaning Codex skills mirror...${NC}"
    if [ -d "$CODEX_SKILLS_DIR" ]; then
        for item in "${SCRIPT_DIR}/skills/"*; do
            [ -e "$item" ] || continue
            target="${CODEX_SKILLS_DIR}/$(basename "$item")"
            if [ -L "$target" ] || [ -e "$target" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove Codex entry: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed Codex entry: ${target}${NC}"
                fi
                REMOVED+=("Codex skill $(basename "$item")")
            fi
        done

        if [ -d "${SCRIPT_DIR}/private-voices" ]; then
            for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
                [ -d "$voice_dir" ] || continue
                skill_src="${voice_dir}/skill"
                [ -d "$skill_src" ] || continue
                voice_name=$(basename "$voice_dir")
                target="${CODEX_SKILLS_DIR}/voice-${voice_name}"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Codex entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Codex entry: ${target}${NC}"
                    fi
                    REMOVED+=("Codex skill voice-${voice_name}")
                fi
            done
        fi

        if [ -d "${SCRIPT_DIR}/private-skills" ]; then
            for item in "${SCRIPT_DIR}/private-skills/"*; do
                [ -e "$item" ] || continue
                target="${CODEX_SKILLS_DIR}/$(basename "$item")"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Codex entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Codex entry: ${target}${NC}"
                    fi
                    REMOVED+=("Codex skill $(basename "$item")")
                fi
            done
        fi
    else
        echo "  No ~/.codex/skills mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Codex agents mirror...${NC}"
    if [ -d "$CODEX_AGENTS_DIR" ]; then
        for item in "${SCRIPT_DIR}/agents/"*; do
            [ -e "$item" ] || continue
            target="${CODEX_AGENTS_DIR}/$(basename "$item")"
            if [ -L "$target" ] || [ -e "$target" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove Codex entry: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed Codex entry: ${target}${NC}"
                fi
                REMOVED+=("Codex agent $(basename "$item")")
            fi
        done

        if [ -d "${SCRIPT_DIR}/private-agents" ]; then
            for item in "${SCRIPT_DIR}/private-agents/"*; do
                [ -e "$item" ] || continue
                target="${CODEX_AGENTS_DIR}/$(basename "$item")"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Codex entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Codex entry: ${target}${NC}"
                    fi
                    REMOVED+=("Codex agent $(basename "$item")")
                fi
            done
        fi
    else
        echo "  No ~/.codex/agents mirror found. Nothing to clean."
    fi

    # Phase 3.6: Clean toolkit-owned Codex hooks mirror (ADR-182)
    echo ""
    echo -e "${YELLOW}Cleaning Codex hooks mirror...${NC}"
    if [ -d "$CODEX_HOOKS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${CODEX_HOOKS_DIR}${NC}"
        else
            rm -rf "$CODEX_HOOKS_DIR"
            echo -e "${GREEN}  ✓ Removed ${CODEX_HOOKS_DIR}${NC}"
        fi
        REMOVED+=("Codex hooks mirror directory")
    else
        echo "  No ~/.codex/hooks mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Codex scripts mirror...${NC}"
    if [ -d "$CODEX_SCRIPTS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${CODEX_SCRIPTS_DIR}${NC}"
        else
            rm -rf "$CODEX_SCRIPTS_DIR"
            echo -e "${GREEN}  ✓ Removed ${CODEX_SCRIPTS_DIR}${NC}"
        fi
        REMOVED+=("Codex scripts mirror directory")
    else
        echo "  No ~/.codex/scripts mirror found. Nothing to clean."
    fi

    if [ -f "${CODEX_DIR}/hooks.json" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would archive: ${CODEX_DIR}/hooks.json${NC}"
        else
            # Archive rather than delete so users who edited the file manually
            # can recover any custom entries we did not write.
            ARCHIVE_TS=$(date +%Y%m%d-%H%M%S)
            mv "${CODEX_DIR}/hooks.json" "${CODEX_DIR}/hooks.json.uninstalled.${ARCHIVE_TS}"
            echo -e "${GREEN}  ✓ Archived ${CODEX_DIR}/hooks.json${NC}"
        fi
        REMOVED+=("Codex hooks.json (archived)")
    else
        echo "  No ~/.codex/hooks.json found. Nothing to archive."
    fi

    # Note: [features] hooks = true is intentionally left in config.toml.
    # Users may have other Codex hook configurations we did not write.

    # Phase 3.7: Clean toolkit-owned Gemini skills mirror
    echo ""
    echo -e "${YELLOW}Cleaning Antigravity CLI Plugin...${NC}"
    if [ -d "$ANTIGRAVITY_PLUGIN_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${ANTIGRAVITY_PLUGIN_DIR}${NC}"
        else
            rm -rf "$ANTIGRAVITY_PLUGIN_DIR"
            echo -e "${GREEN}  ✓ Removed ${ANTIGRAVITY_PLUGIN_DIR}${NC}"
        fi
        REMOVED+=("Antigravity Plugin directory")
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Gemini skills mirror...${NC}"
    if [ -d "$GEMINI_SKILLS_DIR" ]; then
        for item in "${SCRIPT_DIR}/skills/"*; do
            [ -e "$item" ] || continue
            target="${GEMINI_SKILLS_DIR}/$(basename "$item")"
            if [ -L "$target" ] || [ -e "$target" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove Gemini entry: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed Gemini entry: ${target}${NC}"
                fi
                REMOVED+=("Gemini skill $(basename "$item")")
            fi
        done

        if [ -d "${SCRIPT_DIR}/private-voices" ]; then
            for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
                [ -d "$voice_dir" ] || continue
                skill_src="${voice_dir}/skill"
                [ -d "$skill_src" ] || continue
                voice_name=$(basename "$voice_dir")
                target="${GEMINI_SKILLS_DIR}/voice-${voice_name}"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Gemini entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Gemini entry: ${target}${NC}"
                    fi
                    REMOVED+=("Gemini skill voice-${voice_name}")
                fi
            done
        fi

        if [ -d "${SCRIPT_DIR}/private-skills" ]; then
            for item in "${SCRIPT_DIR}/private-skills/"*; do
                [ -e "$item" ] || continue
                target="${GEMINI_SKILLS_DIR}/$(basename "$item")"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Gemini entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Gemini entry: ${target}${NC}"
                    fi
                    REMOVED+=("Gemini skill $(basename "$item")")
                fi
            done
        fi
    else
        echo "  No ~/.gemini/skills mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Gemini agents mirror...${NC}"
    if [ -d "$GEMINI_AGENTS_DIR" ]; then
        for item in "${SCRIPT_DIR}/agents/"*; do
            [ -e "$item" ] || continue
            target="${GEMINI_AGENTS_DIR}/$(basename "$item")"
            if [ -L "$target" ] || [ -e "$target" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove Gemini entry: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed Gemini entry: ${target}${NC}"
                fi
                REMOVED+=("Gemini agent $(basename "$item")")
            fi
        done

        if [ -d "${SCRIPT_DIR}/private-agents" ]; then
            for item in "${SCRIPT_DIR}/private-agents/"*; do
                [ -e "$item" ] || continue
                target="${GEMINI_AGENTS_DIR}/$(basename "$item")"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Gemini entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Gemini entry: ${target}${NC}"
                    fi
                    REMOVED+=("Gemini agent $(basename "$item")")
                fi
            done
        fi
    else
        echo "  No ~/.gemini/agents mirror found. Nothing to clean."
    fi

    # Phase 3.8: Clean toolkit-owned Gemini hooks mirror
    echo ""
    echo -e "${YELLOW}Cleaning Gemini hooks mirror...${NC}"
    if [ -d "$GEMINI_HOOKS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${GEMINI_HOOKS_DIR}${NC}"
        else
            rm -rf "$GEMINI_HOOKS_DIR"
            echo -e "${GREEN}  ✓ Removed ${GEMINI_HOOKS_DIR}${NC}"
        fi
        REMOVED+=("Gemini hooks mirror directory")
    else
        echo "  No ~/.gemini/hooks mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Gemini scripts mirror...${NC}"
    if [ -d "$GEMINI_SCRIPTS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${GEMINI_SCRIPTS_DIR}${NC}"
        else
            rm -rf "$GEMINI_SCRIPTS_DIR"
            echo -e "${GREEN}  ✓ Removed ${GEMINI_SCRIPTS_DIR}${NC}"
        fi
        REMOVED+=("Gemini scripts mirror directory")
    else
        echo "  No ~/.gemini/scripts mirror found. Nothing to clean."
    fi

    if [ -f "${GEMINI_DIR}/settings.json" ]; then
        # Check if settings.json has a hooks key we should clean
        HAS_GEMINI_HOOKS=$(python3 -c "import json; d=json.load(open('${GEMINI_DIR}/settings.json')); print('yes' if 'hooks' in d else 'no')" 2>/dev/null || echo "no")
        if [ "$HAS_GEMINI_HOOKS" = "yes" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would archive hooks from: ${GEMINI_DIR}/settings.json${NC}"
            else
                ARCHIVE_TS=$(date +%Y%m%d-%H%M%S)
                cp "${GEMINI_DIR}/settings.json" "${GEMINI_DIR}/settings.json.uninstalled.${ARCHIVE_TS}"
                # Remove only the hooks key, preserve everything else
                python3 -c "
import json, os
dst = '${GEMINI_DIR}/settings.json'
with open(dst, encoding='utf-8') as f:
    data = json.load(f)
data.pop('hooks', None)
tmp = dst + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.rename(tmp, dst)
"
                echo -e "${GREEN}  ✓ Archived and cleaned hooks from ${GEMINI_DIR}/settings.json${NC}"
            fi
            REMOVED+=("Gemini hooks config from settings.json (archived)")
        else
            echo "  No hooks key found in ~/.gemini/settings.json. Nothing to clean."
        fi
    else
        echo "  No ~/.gemini/settings.json found. Nothing to archive."
    fi

    # Phase 3.9: Clean toolkit-owned Factory mirror
    echo ""
    echo -e "${YELLOW}Cleaning Factory mirror...${NC}"
    for dir_var in FACTORY_SKILLS_DIR FACTORY_DROIDS_DIR FACTORY_HOOKS_DIR FACTORY_COMMANDS_DIR FACTORY_SCRIPTS_DIR; do
        target="${!dir_var}"
        if [ -L "$target" ] || [ -d "$target" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would remove: ${target}${NC}"
            else
                rm -rf "$target"
                echo -e "${GREEN}  ✓ Removed: ${target}${NC}"
            fi
            REMOVED+=("Factory $(basename "$target")")
        fi
    done

    if [ -f "${FACTORY_DIR}/settings.json" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would archive: ${FACTORY_DIR}/settings.json${NC}"
        else
            ARCHIVE_TS=$(date +%Y%m%d-%H%M%S)
            mv "${FACTORY_DIR}/settings.json" "${FACTORY_DIR}/settings.json.uninstalled.${ARCHIVE_TS}"
            echo -e "${GREEN}  ✓ Archived ${FACTORY_DIR}/settings.json${NC}"
        fi
        REMOVED+=("Factory settings.json (archived)")
    else
        echo "  No ~/.factory/settings.json found. Nothing to archive."
    fi

    # Note: ~/.factory/config.toml is intentionally left untouched.
    # Users may have other Factory configurations we did not write.

    # Phase 3.10: Clean toolkit-owned Hermes skills mirror
    echo ""
    echo -e "${YELLOW}Cleaning Hermes skills mirror...${NC}"
    if [ -d "$HERMES_SKILLS_DIR" ]; then
        for item in "${SCRIPT_DIR}/skills/"*; do
            [ -e "$item" ] || continue
            target="${HERMES_SKILLS_DIR}/$(basename "$item")"
            if [ -L "$target" ] || [ -e "$target" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would remove Hermes entry: ${target}${NC}"
                else
                    rm -rf "$target"
                    echo -e "${GREEN}  ✓ Removed Hermes entry: ${target}${NC}"
                fi
                REMOVED+=("Hermes skill $(basename "$item")")
            fi
        done

        if [ -d "${SCRIPT_DIR}/private-voices" ]; then
            for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
                [ -d "$voice_dir" ] || continue
                skill_src="${voice_dir}/skill"
                [ -d "$skill_src" ] || continue
                voice_name=$(basename "$voice_dir")
                target="${HERMES_SKILLS_DIR}/voice-${voice_name}"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Hermes entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Hermes entry: ${target}${NC}"
                    fi
                    REMOVED+=("Hermes skill voice-${voice_name}")
                fi
            done
        fi

        if [ -d "${SCRIPT_DIR}/private-skills" ]; then
            for item in "${SCRIPT_DIR}/private-skills/"*; do
                [ -e "$item" ] || continue
                target="${HERMES_SKILLS_DIR}/$(basename "$item")"
                if [ -L "$target" ] || [ -e "$target" ]; then
                    if [ "$DRY_RUN" = true ]; then
                        echo -e "${BLUE}  Would remove Hermes entry: ${target}${NC}"
                    else
                        rm -rf "$target"
                        echo -e "${GREEN}  ✓ Removed Hermes entry: ${target}${NC}"
                    fi
                    REMOVED+=("Hermes skill $(basename "$item")")
                fi
            done
        fi
    else
        echo "  No ~/.hermes/skills mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Hermes scripts mirror...${NC}"
    if [ -d "$HERMES_SCRIPTS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${HERMES_SCRIPTS_DIR}${NC}"
        else
            rm -rf "$HERMES_SCRIPTS_DIR"
            echo -e "${GREEN}  ✓ Removed ${HERMES_SCRIPTS_DIR}${NC}"
        fi
        REMOVED+=("Hermes scripts mirror directory")
    else
        echo "  No ~/.hermes/scripts mirror found. Nothing to clean."
    fi

    # Note: ~/.hermes/config.yaml is intentionally left untouched.
    # Users may have other Hermes configurations we did not write.

    # Phase 3.11: Clean toolkit-owned Reasonix mirror (skills + scripts + hooks + settings.json)
    echo ""
    echo -e "${YELLOW}Cleaning Reasonix skills mirror...${NC}"
    # Remove ONLY the toolkit-owned flatten-copy output, recomputed from the repo so it
    # matches what the install wrote (skills/<cat>/<name> + top-level skills + private-skills
    # flattened to <name>, voice skills as voice-<name>, support dirs copied by name). Skills
    # a USER added by hand (real dirs we never wrote) are left intact. Also sweep stale
    # toolkit symlinks left by the pre-flatten installer. Finally drop the dir if now empty.
    if [ -d "$REASONIX_SKILLS_DIR" ]; then
        reasonix_uninstall_entry() {
            [ -n "$1" ] || return 0
            local target="${REASONIX_SKILLS_DIR}/$1"
            [ -e "$target" ] || [ -L "$target" ] || return 0
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would remove Reasonix entry: ${target}${NC}"
            else
                rm -rf "$target"
                echo -e "${GREEN}  ✓ Removed Reasonix entry: ${target}${NC}"
            fi
            REMOVED+=("Reasonix skill $1")
        }

        # Flattened skills + private skills (basename of each dir holding a SKILL.md).
        while IFS= read -r skill_md; do
            [ -n "$skill_md" ] || continue
            reasonix_uninstall_entry "$(basename "$(dirname "$skill_md")")"
        done < <(find "${SCRIPT_DIR}/skills" "${SCRIPT_DIR}/private-skills" -name SKILL.md 2>/dev/null)

        # Voice skills (voice-<name>).
        if [ -d "${SCRIPT_DIR}/private-voices" ]; then
            for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
                [ -f "${voice_dir}/skill/SKILL.md" ] || continue
                reasonix_uninstall_entry "voice-$(basename "$voice_dir")"
            done
        fi

        # Support dirs (no SKILL.md anywhere — shared-patterns, kb, voice-shared*).
        for support_dir in "${SCRIPT_DIR}/skills/"*/; do
            [ -d "$support_dir" ] || continue
            [ -z "$(find "$support_dir" -name SKILL.md -print -quit)" ] || continue
            reasonix_uninstall_entry "$(basename "$support_dir")"
        done

        # Stale toolkit symlinks from the pre-flatten installer (reasonix entries are always
        # real dirs now, so any symlink here is toolkit-owned residue).
        if [ "$DRY_RUN" != true ]; then
            find "$REASONIX_SKILLS_DIR" -maxdepth 1 -mindepth 1 -type l -delete 2>/dev/null || true
            rmdir "$REASONIX_SKILLS_DIR" 2>/dev/null && \
                echo -e "${GREEN}  ✓ Removed empty ${REASONIX_SKILLS_DIR}${NC}" || true
        fi
    else
        echo "  No ~/.reasonix/skills mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Reasonix scripts mirror...${NC}"
    if [ -d "$REASONIX_SCRIPTS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${REASONIX_SCRIPTS_DIR}${NC}"
        else
            rm -rf "$REASONIX_SCRIPTS_DIR"
            echo -e "${GREEN}  ✓ Removed ${REASONIX_SCRIPTS_DIR}${NC}"
        fi
        REMOVED+=("Reasonix scripts mirror directory")
    else
        echo "  No ~/.reasonix/scripts mirror found. Nothing to clean."
    fi

    echo ""
    echo -e "${YELLOW}Cleaning Reasonix hooks mirror...${NC}"
    if [ -d "$REASONIX_HOOKS_DIR" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${REASONIX_HOOKS_DIR}${NC}"
        else
            rm -rf "$REASONIX_HOOKS_DIR"
            echo -e "${GREEN}  ✓ Removed ${REASONIX_HOOKS_DIR}${NC}"
        fi
        REMOVED+=("Reasonix hooks mirror directory")
    else
        echo "  No ~/.reasonix/hooks mirror found. Nothing to clean."
    fi

    # Archive the generated Reasonix settings.json (hooks key). config.json is
    # user-owned and never touched.
    if [ -f "${REASONIX_DIR}/settings.json" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would archive: ${REASONIX_DIR}/settings.json${NC}"
        else
            ARCHIVE_TS=$(date +%Y%m%d-%H%M%S)
            mv "${REASONIX_DIR}/settings.json" "${REASONIX_DIR}/settings.json.uninstalled.${ARCHIVE_TS}"
            echo -e "${GREEN}  ✓ Archived ${REASONIX_DIR}/settings.json${NC}"
        fi
        REMOVED+=("Reasonix settings.json (archived)")
    fi

    # Note: ~/.reasonix/config.json is intentionally left untouched.
    # Users own MCP/model/permissions config we did not write.

    # Phase 4: Remove install manifest
    echo ""
    echo -e "${YELLOW}Cleaning up manifest...${NC}"
    if [ -f "$MANIFEST_FILE" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would remove: ${MANIFEST_FILE}${NC}"
        else
            rm "$MANIFEST_FILE"
            echo -e "${GREEN}  ✓ Removed install manifest${NC}"
        fi
        REMOVED+=("install manifest")
    else
        echo "  No manifest to remove."
    fi

    # Summary
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${GREEN}║                    Dry Run Uninstall Summary                   ║${NC}"
    else
        echo -e "${GREEN}║                      Uninstall Complete                        ║${NC}"
    fi
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ ${#REMOVED[@]} -gt 0 ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "Would remove:"
        else
            echo "Removed:"
        fi
        for r in "${REMOVED[@]}"; do
            echo -e "  ${GREEN}✓${NC} ${r}"
        done
    else
        echo "  Nothing to remove."
    fi

    echo ""
    echo "Preserved (not touched):"
    echo "  • ~/.claude/settings.json (all keys except hooks)"
    echo "  • ~/.claude/projects/"
    echo "  • ~/.claude/memory/"
    echo "  • ~/.codex/config.toml (including [features] hooks flag)"
    echo "  • ~/.gemini/settings.json (all keys except hooks)"
    echo "  • ~/.factory/config.toml (if present, like Codex)"
    echo "  • ~/.hermes/config.yaml (Hermes Agent configuration)"
    echo "  • ~/.reasonix/config.json (Reasonix MCP/model/permissions, user-owned)"
    echo "  • .local/ customizations in the toolkit repo"
    echo "  • Python packages (remove manually if needed)"
    if [ ${#PRESERVED[@]} -gt 0 ]; then
        for p in "${PRESERVED[@]}"; do
            echo "  • ${p}"
        done
    fi

    echo ""
    echo -e "${YELLOW}Tip:${NC} You can also run ${BLUE}./install.sh --rollback${NC} to restore"
    echo "your previous settings.json from the most recent backup."
    echo ""
    exit 0
}

# Handle uninstall
if [ "$MODE" = "uninstall" ]; then
    uninstall
fi

# Handle rollback
if [ "$MODE" = "rollback" ]; then
    echo -e "${YELLOW}Rolling back settings.json...${NC}"
    SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
    # Find the most recent backup
    LATEST_BACKUP=$(ls -1t "${SETTINGS_FILE}.backup."* 2>/dev/null | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        echo -e "${RED}Error: No settings.json backup found in ${CLAUDE_DIR}${NC}"
        exit 1
    fi
    echo "  Restoring from: $(basename "$LATEST_BACKUP")"
    cp "$LATEST_BACKUP" "$SETTINGS_FILE"
    echo -e "${GREEN}✓ settings.json restored from $(basename "$LATEST_BACKUP")${NC}"
    exit 0
fi

# Interactive mode selection
if [ -z "$MODE" ]; then
    echo "How would you like to install?"
    echo ""
    echo "  1) Symlink (recommended for development)"
    echo "     - Changes to this repo appear immediately in Claude Code"
    echo "     - Easy to update with git pull"
    echo ""
    echo "  2) Copy (recommended for stability)"
    echo "     - Independent copy in ~/.claude"
    echo "     - Re-run install.sh to update"
    echo ""
    read -p "Choose [1/2]: " choice

    case $choice in
        1) MODE="symlink" ;;
        2) MODE="copy" ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
fi

# Verify requirements
check_python
detect_pip_command

# Create ~/.claude if needed
echo ""
echo -e "${YELLOW}Setting up ~/.claude directory...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would create: ${CLAUDE_DIR}${NC}"
else
    mkdir -p "${CLAUDE_DIR}"
fi
echo -e "${GREEN}✓ ${CLAUDE_DIR} ready${NC}"

echo ""
echo -e "${YELLOW}Setting up ~/.codex skills directory...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would create: ${CODEX_SKILLS_DIR}${NC}"
else
    mkdir -p "${CODEX_SKILLS_DIR}"
fi
echo -e "${GREEN}✓ ${CODEX_SKILLS_DIR} ready${NC}"

echo ""
echo -e "${YELLOW}Setting up ~/.codex agents directory...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would create: ${CODEX_AGENTS_DIR}${NC}"
else
    mkdir -p "${CODEX_AGENTS_DIR}"
fi
echo -e "${GREEN}✓ ${CODEX_AGENTS_DIR} ready${NC}"

echo ""
echo -e "${YELLOW}Setting up ~/.gemini skills directory...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would create: ${GEMINI_SKILLS_DIR}${NC}"
else
    mkdir -p "${GEMINI_SKILLS_DIR}"
fi
echo -e "${GREEN}✓ ${GEMINI_SKILLS_DIR} ready${NC}"

echo ""
echo -e "${YELLOW}Setting up ~/.gemini agents directory...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would create: ${GEMINI_AGENTS_DIR}${NC}"
else
    mkdir -p "${GEMINI_AGENTS_DIR}"
fi
echo -e "${GREEN}✓ ${GEMINI_AGENTS_DIR} ready${NC}"

echo ""
echo -e "${YELLOW}Setting up ~/.factory directory...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would create: ${FACTORY_DIR}${NC}"
else
    mkdir -p "${FACTORY_DIR}"
fi
echo -e "${GREEN}✓ ${FACTORY_DIR} ready${NC}"

echo ""
echo -e "${YELLOW}Setting up ~/.hermes/skills directory...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would create: ${HERMES_SKILLS_DIR}${NC}"
else
    mkdir -p "${HERMES_SKILLS_DIR}"
fi
echo -e "${GREEN}✓ ${HERMES_SKILLS_DIR} ready${NC}"

echo ""
echo -e "${YELLOW}Setting up ~/.reasonix/skills directory...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would create: ${REASONIX_SKILLS_DIR}${NC}"
else
    mkdir -p "${REASONIX_SKILLS_DIR}"
fi
echo -e "${GREEN}✓ ${REASONIX_SKILLS_DIR} ready${NC}"

# detect_conflicts — scans all runtime dirs × all component types.
# Populates global associative array: conflicts[runtime/component]="description"
declare -A conflicts
detect_conflicts() {
    local runtime_dir component target src count items item name
    for runtime_dir in "$CLAUDE_DIR" "$CODEX_DIR" "$GEMINI_DIR"                        "$FACTORY_DIR" "$HERMES_DIR" "$REASONIX_DIR"; do
        [ -d "$runtime_dir" ] || continue
        for component in agents skills hooks commands scripts; do
            target="$runtime_dir/$component"
            src="$SCRIPT_DIR/$component"
            [ -d "$src" ] || continue
            [ -d "$target" ] || [ -L "$target" ] || continue
            # Whole-dir symlink pointing elsewhere
            if [ -L "$target" ] && [ "$(readlink "$target")" != "$src" ]; then
                conflicts["$runtime_dir/$component"]="symlink→$(readlink "$target")"
                continue
            fi
            # Count items in target not present in src
            count=0; items=""
            for item in "$target"/*/; do
                [ -e "$item" ] || continue
                name=$(basename "$item")
                [ -e "$src/$name" ] || { count=$((count+1)); items="$items $name"; }
            done
            if [ "$count" -gt 0 ]; then
                conflicts["$runtime_dir/$component"]="$count external:$items"
            fi
        done
    done
    return 0
}

print_conflict_table() {
    echo ""
    echo "Found existing content in the following locations:"
    for key in "${!conflicts[@]}"; do
        echo "  $key  (${conflicts[$key]})"
    done
    echo ""
    echo "Choose install mode for all conflicting locations:"
    echo "  [1] per-item  — symlink each vexjoy item individually; preserve external content (recommended)"
    echo "  [2] replace   — rm -rf and replace with whole-dir symlink (destroys external content)"
    echo "  [3] skip      — leave conflicting locations unchanged; install only conflict-free locations"
    echo ""
}

# Install components
echo ""
echo -e "${YELLOW}Installing components (mode: ${MODE})...${NC}"

install_component() {
    local name=$1
    local base_dir=${2:-$CLAUDE_DIR}
    local target_name=${3:-$name}
    local source="${SCRIPT_DIR}/${name}"
    local target="${base_dir}/${target_name}"

    # Per-item mode: skip targets flagged as conflicting or when CONFLICT_MODE=per-item
    local component_key="$base_dir/$target_name"
    if [ "$CONFLICT_MODE" = "per-item" ] && [ "$MODE" = "symlink" ] &&        { [ -n "${conflicts[$component_key]+_}" ] || [ -d "$target" ] || [ -L "$target" ]; }; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would per-item symlink into: ${target}${NC}"
        else
            mkdir -p "$target"
            local item item_name
            for item in "$source"/*/; do
                [ -e "$item" ] || continue
                item_name=$(basename "$item")
                if [ -e "$target/$item_name" ]; then
                    echo -e "${YELLOW}  WARNING: $target/$item_name already exists — skipping (kept existing)${NC}"
                    continue
                fi
                ln -s "$item" "$target/$item_name"
                echo -e "${GREEN}  ✓ Per-item linked ${item_name}${NC}"
            done
        fi
        return
    fi

    # Check if target exists
    if [ -e "$target" ] || [ -L "$target" ]; then
        if [ -L "$target" ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would remove existing symlink: $target${NC}"
            else
                echo "  Removing existing symlink: $target"
                rm "$target"
            fi
        else
            echo -e "${YELLOW}  Warning: $target exists and is not a symlink${NC}"
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would replace existing directory${NC}"
            elif [ "$FORCE" = true ]; then
                echo "  Replacing existing directory (--force): $target"
                rm -rf "$target"
            else
                read -p "  Overwrite? [y/N]: " confirm
                if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
                    echo "  Skipping $name"
                    return
                fi
                rm -rf "$target"
            fi
        fi
    fi

    if [ "$MODE" = "symlink" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would symlink: ${source} -> ${target}${NC}"
        else
            ln -s "$source" "$target"
            echo -e "${GREEN}  ✓ Symlinked ${name}${NC}"
        fi
    else
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would copy: ${source} -> ${target}${NC}"
        else
            cp -r "$source" "$target"
            echo -e "${GREEN}  ✓ Copied ${name}${NC}"
        fi
    fi
}

sync_mirror_entry() {
    local source=$1
    local target=$2
    local label=${3:-Mirror}
    local name
    name=$(basename "$source")

    # Per-item mode: add-only symlink for each item; skip existing entries
    if [ "$CONFLICT_MODE" = "per-item" ] && [ "$MODE" = "symlink" ] && [ -d "$source" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would per-item sync ${label} entry: ${source} -> ${target}/${NC}"
        else
            mkdir -p "$target"
            local item item_name
            for item in "$source"/*/; do
                [ -e "$item" ] || continue
                item_name=$(basename "$item")
                if [ -e "$target/$item_name" ]; then
                    continue  # already present; skip silently
                fi
                ln -s "$item" "$target/$item_name"
                echo -e "${GREEN}  ✓ ${label} per-item linked ${item_name}${NC}"
            done
        fi
        return
    fi

    if [ -e "$target" ] || [ -L "$target" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would replace ${label} entry: ${target}${NC}"
        else
            rm -rf "$target"
        fi
    fi

    if [ "$MODE" = "symlink" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would symlink ${label} entry: ${source} -> ${target}${NC}"
        else
            ln -s "$source" "$target"
            echo -e "${GREEN}  ✓ ${label} symlinked ${name}${NC}"
        fi
    else
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would copy ${label} entry: ${source} -> ${target}${NC}"
        else
            if [ -d "$source" ]; then
                cp -r "$source" "$target"
            else
                cp "$source" "$target"
            fi
            echo -e "${GREEN}  ✓ ${label} copied ${name}${NC}"
        fi
    fi
}

# Backward-compatible wrapper for existing call sites
sync_codex_entry() {
    sync_mirror_entry "$1" "$2" "Codex"
}

# install_git_hook — writes .git/hooks/post-merge to auto-sync new items after git pull.
# Add-only, never removes, never overwrites existing entries.
install_git_hook() {
    local hook=".git/hooks/post-merge"
    [ -d ".git" ] || return 0  # no-op outside a git repo clone
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would install post-merge hook: ${hook}${NC}"
        return 0
    fi
    mkdir -p ".git/hooks"
    cat > "$hook" << 'HOOK'
#!/usr/bin/env bash
# Written by vexjoy-agent install.sh — auto-syncs new items after git pull.
# Add-only: skips items already present; never removes or overwrites.
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
for runtime_dir in     "$HOME/.claude" "$HOME/.codex" "$HOME/.gemini"     "$HOME/.factory" "$HOME/.hermes" "$HOME/.reasonix"; do
  [ -d "$runtime_dir" ] || continue
  for component in agents skills hooks commands scripts; do
    src="$REPO_DIR/$component"
    dst="$runtime_dir/$component"
    [ -d "$src" ] || continue
    [ -d "$dst" ] || continue  # only sync if component dir already installed
    for item in "$src"/*/; do
      name=$(basename "$item")
      [ -e "$dst/$name" ] && continue  # already present; skip
      ln -s "$item" "$dst/$name"
      echo "[vexjoy-agent] auto-synced: $dst/$name"
    done
  done
done
HOOK
    chmod +x "$hook"
    echo -e "${GREEN}  ✓ Installed post-merge hook: ${hook}${NC}"
}

# Scan for conflicts before first install_component call
if [ "$MODE" = "symlink" ]; then
    detect_conflicts
    if [ ${#conflicts[@]} -gt 0 ]; then
        if [ "$DRY_RUN" = true ]; then
            print_conflict_table
            _default_mode="${CONFLICT_MODE:-per-item}"
            echo -e "${BLUE}  DRY RUN: Would prompt for conflict mode. Default would be: ${_default_mode}${NC}"
            echo -e "${BLUE}  Would use mode: ${_default_mode}${NC}"
            [ -z "$CONFLICT_MODE" ] && CONFLICT_MODE="per-item"
        elif [ -z "$CONFLICT_MODE" ]; then
            print_conflict_table
            read -r -p "Choice [1/2/3, default=1]: " _ans
            case "${_ans:-1}" in
                1) CONFLICT_MODE="per-item" ;;
                2) CONFLICT_MODE="replace"  ;;
                3) CONFLICT_MODE="skip"     ;;
                *) CONFLICT_MODE="per-item" ;;
            esac
            echo ""
        fi
    fi
fi

# Install main components
for component in agents skills hooks commands scripts; do
    if [ -d "${SCRIPT_DIR}/${component}" ]; then
        install_component "$component"
    fi
done

# Install private components (if they exist, gitignored)
for private_dir in private-agents private-skills private-hooks; do
    public_name="${private_dir#private-}"  # strips "private-" prefix
    if [ -d "${SCRIPT_DIR}/${private_dir}" ]; then
        echo ""
        echo -e "${YELLOW}Installing private ${public_name}...${NC}"
        # Copy/link private components into the same ~/.claude target
        # Private overrides public when same name exists
        if [ "$MODE" = "symlink" ]; then
            for item in "${SCRIPT_DIR}/${private_dir}/"*; do
                [ -e "$item" ] || continue
                item_name=$(basename "$item")
                target="${CLAUDE_DIR}/${public_name}/${item_name}"
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would link private: ${item_name}${NC}"
                else
                    rm -rf "$target" 2>/dev/null
                    ln -sf "$item" "$target"
                    echo -e "${GREEN}  ✓ Linked private ${item_name}${NC}"
                fi
            done
        else
            for item in "${SCRIPT_DIR}/${private_dir}/"*; do
                [ -e "$item" ] || continue
                item_name=$(basename "$item")
                target="${CLAUDE_DIR}/${public_name}/${item_name}"
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would copy private: ${item_name}${NC}"
                else
                    rm -rf "$target" 2>/dev/null
                    cp -r "$item" "$target"
                    echo -e "${GREEN}  ✓ Copied private ${item_name}${NC}"
                fi
            done
        fi
    fi
done

# Install private-voices into Claude skills (goes through symlink into repo/skills/)
if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    echo ""
    echo -e "${YELLOW}Installing private voices (Claude)...${NC}"
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -d "$skill_src" ] || continue
        voice_name=$(basename "$voice_dir")
        target="${CLAUDE_DIR}/skills/voice-${voice_name}"
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would link voice: voice-${voice_name}${NC}"
        else
            rm -rf "$target" 2>/dev/null
            if [ "$MODE" = "symlink" ]; then
                ln -sf "$skill_src" "$target"
                echo -e "${GREEN}  ✓ Linked voice-${voice_name}${NC}"
            else
                cp -r "$skill_src" "$target"
                echo -e "${GREEN}  ✓ Copied voice-${voice_name}${NC}"
            fi
        fi
    done
fi

# Install git post-merge hook for automatic sync on git pull
echo ""
echo -e "${YELLOW}Installing post-merge git hook...${NC}"
install_git_hook

echo ""
echo -e "${YELLOW}Syncing Codex skills mirror...${NC}"
CODEX_ENTRY_COUNT=0
for item in "${SCRIPT_DIR}/skills/"*; do
    [ -e "$item" ] || continue
    target="${CODEX_SKILLS_DIR}/$(basename "$item")"
    sync_codex_entry "$item" "$target"
    CODEX_ENTRY_COUNT=$((CODEX_ENTRY_COUNT + 1))
done

if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -d "$skill_src" ] || continue
        voice_name=$(basename "$voice_dir")
        target="${CODEX_SKILLS_DIR}/voice-${voice_name}"
        sync_codex_entry "$skill_src" "$target"
        CODEX_ENTRY_COUNT=$((CODEX_ENTRY_COUNT + 1))
    done
fi

if [ -d "${SCRIPT_DIR}/private-skills" ]; then
    for item in "${SCRIPT_DIR}/private-skills/"*; do
        [ -e "$item" ] || continue
        target="${CODEX_SKILLS_DIR}/$(basename "$item")"
        sync_codex_entry "$item" "$target"
        CODEX_ENTRY_COUNT=$((CODEX_ENTRY_COUNT + 1))
    done
fi

echo ""
echo -e "${YELLOW}Syncing Codex agents mirror...${NC}"
CODEX_AGENT_COUNT=0
for item in "${SCRIPT_DIR}/agents/"*; do
    [ -e "$item" ] || continue
    target="${CODEX_AGENTS_DIR}/$(basename "$item")"
    sync_codex_entry "$item" "$target"
    CODEX_AGENT_COUNT=$((CODEX_AGENT_COUNT + 1))
done

if [ -d "${SCRIPT_DIR}/private-agents" ]; then
    for item in "${SCRIPT_DIR}/private-agents/"*; do
        [ -e "$item" ] || continue
        target="${CODEX_AGENTS_DIR}/$(basename "$item")"
        sync_codex_entry "$item" "$target"
        CODEX_AGENT_COUNT=$((CODEX_AGENT_COUNT + 1))
    done
fi

# Sync Codex hooks mirror (ADR-182)
echo ""
echo -e "${YELLOW}Syncing Codex hooks mirror...${NC}"
CODEX_HOOK_COUNT=0
CODEX_HOOKS_ALLOWLIST="${SCRIPT_DIR}/scripts/codex-hooks-allowlist.txt"

if [ -f "$CODEX_HOOKS_ALLOWLIST" ]; then
    # Ensure hooks directory exists
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${CODEX_HOOKS_DIR}${NC}"
    else
        mkdir -p "$CODEX_HOOKS_DIR"
    fi

    # Parse allowlist and mirror each allowlisted hook file.
    # Format per line: EVENT:filename [matcher]
    # Comments (#) and blank lines are ignored.
    while IFS= read -r line || [ -n "$line" ]; do
        # Strip leading/trailing whitespace for the blank check.
        trimmed="${line#"${line%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [ -z "$trimmed" ] && continue
        [ "${trimmed#\#}" != "$trimmed" ] && continue

        # Extract filename: everything between the first colon and the first space (or EOL)
        rest="${trimmed#*:}"
        filename="${rest%% *}"

        source_file="${SCRIPT_DIR}/hooks/${filename}"
        if [ ! -f "$source_file" ]; then
            echo -e "${RED}  ✗ Allowlisted hook missing: ${filename}${NC}"
            continue
        fi

        target_file="${CODEX_HOOKS_DIR}/${filename}"
        sync_codex_entry "$source_file" "$target_file"
        CODEX_HOOK_COUNT=$((CODEX_HOOK_COUNT + 1))
    done < "$CODEX_HOOKS_ALLOWLIST"

    # Also mirror the hooks/lib directory so intra-hook imports resolve
    # (hook_utils, injection_patterns, stdin_timeout, usage_db, etc.).
    if [ -d "${SCRIPT_DIR}/hooks/lib" ]; then
        lib_target="${CODEX_HOOKS_DIR}/lib"
        sync_codex_entry "${SCRIPT_DIR}/hooks/lib" "$lib_target"
    fi

    # Generate hooks.json via the dedicated script.
    CODEX_HOOKS_JSON="${CODEX_DIR}/hooks.json"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would generate: ${CODEX_HOOKS_JSON}${NC}"
    else
        if $PYTHON_CMD "${SCRIPT_DIR}/scripts/generate-codex-hooks-json.py" \
            --allowlist "$CODEX_HOOKS_ALLOWLIST" \
            --output "$CODEX_HOOKS_JSON" \
            --codex-hooks-dir "$CODEX_HOOKS_DIR" 2>&1; then
            echo -e "${GREEN}  ✓ Generated ${CODEX_HOOKS_JSON}${NC}"
        else
            echo -e "${RED}  ✗ Failed to generate hooks.json${NC}"
        fi
    fi

    # Ensure hooks feature flag is enabled in ~/.codex/config.toml.
    CODEX_CONFIG="${CODEX_DIR}/config.toml"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would ensure ${CODEX_CONFIG} has [features] hooks = true${NC}"
    else
        if $PYTHON_CMD "${SCRIPT_DIR}/scripts/ensure-codex-feature-flag.py" \
            --config "$CODEX_CONFIG" 2>&1; then
            :
        else
            echo -e "${YELLOW}  ⚠ Could not update ${CODEX_CONFIG} (see error above). Codex hooks may not activate.${NC}"
        fi
    fi

    # Warn if installed Codex CLI is below the hook-support minimum (v0.114.0).
    if command -v codex >/dev/null 2>&1; then
        cx_ver=$(codex --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if [ -n "$cx_ver" ]; then
            min_major=0; min_minor=114; min_patch=0
            IFS='.' read -r cx_maj cx_min cx_pat <<< "$cx_ver"
            if [ "$cx_maj" -lt "$min_major" ] || \
               { [ "$cx_maj" -eq "$min_major" ] && [ "$cx_min" -lt "$min_minor" ]; } || \
               { [ "$cx_maj" -eq "$min_major" ] && [ "$cx_min" -eq "$min_minor" ] && [ "$cx_pat" -lt "$min_patch" ]; }; then
                echo -e "${YELLOW}  ⚠ Codex CLI version ${cx_ver} is below 0.114.0. Hooks may not work. See openai/codex#14754.${NC}"
            fi
        fi
    else
        echo -e "${BLUE}  (codex CLI not installed; hooks will activate when Codex is installed)${NC}"
    fi
else
    echo -e "${YELLOW}  ⚠ Codex hooks allowlist not found at ${CODEX_HOOKS_ALLOWLIST}; skipping hooks mirror${NC}"
fi

echo ""
echo -e "${YELLOW}Syncing Codex scripts mirror...${NC}"
if [ -d "${SCRIPT_DIR}/scripts" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would mirror scripts to: ${CODEX_SCRIPTS_DIR}${NC}"
    else
        mkdir -p "$CODEX_SCRIPTS_DIR"
    fi
    sync_codex_entry "${SCRIPT_DIR}/scripts" "$CODEX_SCRIPTS_DIR"
    CODEX_SCRIPT_COUNT=$(ls -1 "${SCRIPT_DIR}/scripts/"*.py 2>/dev/null | grep -cv '__init__')
    echo -e "${GREEN}  ✓ Scripts mirrored to ${CODEX_SCRIPTS_DIR}${NC}"
else
    CODEX_SCRIPT_COUNT=0
fi

echo ""
echo -e "${YELLOW}Installing Factory components (mode: ${MODE})...${NC}"
# Factory uses the same top-level symlink/copy pattern as Claude.
# Only difference: 'agents' is named 'droids' under ~/.factory.
for component in agents skills hooks commands scripts; do
    if [ -d "${SCRIPT_DIR}/${component}" ]; then
        target_name="$component"
        [ "$component" = "agents" ] && target_name="droids"
        install_component "$component" "$FACTORY_DIR" "$target_name"
    fi
done

# Install private Factory components (mirrors Claude private overlay logic)
for private_dir in private-agents private-skills private-hooks; do
    public_name="${private_dir#private-}"
    [ "$public_name" = "agents" ] && public_name="droids"
    if [ -d "${SCRIPT_DIR}/${private_dir}" ]; then
        echo ""
        echo -e "${YELLOW}Installing Factory private ${public_name}...${NC}"
        for item in "${SCRIPT_DIR}/${private_dir}/"*; do
            [ -e "$item" ] || continue
            item_name=$(basename "$item")
            target="${FACTORY_DIR}/${public_name}/${item_name}"
            if [ "$DRY_RUN" = true ]; then
                echo -e "${BLUE}  Would install Factory private: ${item_name}${NC}"
            else
                rm -rf "$target" 2>/dev/null
                if [ "$MODE" = "symlink" ]; then
                    ln -sf "$item" "$target"
                    echo -e "${GREEN}  ✓ Linked Factory private ${item_name}${NC}"
                else
                    cp -r "$item" "$target"
                    echo -e "${GREEN}  ✓ Copied Factory private ${item_name}${NC}"
                fi
            fi
        done
    fi
done

# Install private-voices into Factory skills (goes through symlink into repo/skills/)
if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    echo ""
    echo -e "${YELLOW}Installing Factory private voices...${NC}"
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -d "$skill_src" ] || continue
        voice_name=$(basename "$voice_dir")
        target="${FACTORY_DIR}/skills/voice-${voice_name}"
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would install Factory voice: voice-${voice_name}${NC}"
        else
            rm -rf "$target" 2>/dev/null
            if [ "$MODE" = "symlink" ]; then
                ln -sf "$skill_src" "$target"
                echo -e "${GREEN}  ✓ Linked Factory voice-${voice_name}${NC}"
            else
                cp -r "$skill_src" "$target"
                echo -e "${GREEN}  ✓ Copied Factory voice-${voice_name}${NC}"
            fi
        fi
    done
fi

# Component counts for the install summary (count source dirs, not per-entry)
FACTORY_SKILL_COUNT=$(ls -1 "${SCRIPT_DIR}/skills/"*/SKILL.md 2>/dev/null | wc -l)
FACTORY_DROID_COUNT=$(ls -1 "${SCRIPT_DIR}/agents/"*.md 2>/dev/null | grep -v README | wc -l)
FACTORY_HOOK_COUNT=$(ls -1 "${SCRIPT_DIR}/hooks/"*.py 2>/dev/null | grep -cv '__init__')

# Generate ~/.factory/settings.json
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would sync hooks from ${SCRIPT_DIR}/.claude/settings.json to ${FACTORY_DIR}/settings.json (with path rewrite)${NC}"
elif [ -f "${SCRIPT_DIR}/.claude/settings.json" ]; then
    FACTORY_SETTINGS="${FACTORY_DIR}/settings.json"
    if [ ! -f "$FACTORY_SETTINGS" ]; then
        echo '{}' > "$FACTORY_SETTINGS"
    fi
    BACKUP_TS=$(date +%Y%m%d-%H%M%S)
    cp "$FACTORY_SETTINGS" "${FACTORY_SETTINGS}.backup.${BACKUP_TS}"
    $PYTHON_CMD -c "
import json, os
repo = json.load(open('${SCRIPT_DIR}/.claude/settings.json'))
dst = '${FACTORY_SETTINGS}'
try:
    merged = json.load(open(dst, encoding='utf-8'))
except (FileNotFoundError, json.JSONDecodeError):
    merged = {}
hooks_json = json.dumps(repo.get('hooks', {}))
hooks_json = hooks_json.replace('\$HOME/.claude/', '\$HOME/.factory/')
hooks_json = hooks_json.replace('\${HOME}/.claude/', '\${HOME}/.factory/')
merged['hooks'] = json.loads(hooks_json)
merged.setdefault('attribution', repo.get('attribution', {'commit': '', 'pr': ''}))
tmp = dst + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(merged, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.rename(tmp, dst)
print('  Factory hooks configured from .claude/settings.json')
"
else
    echo -e "${YELLOW}  Warning: ${SCRIPT_DIR}/.claude/settings.json not found, skipping Factory hook sync${NC}"
fi

# Sync Antigravity CLI Plugin mirror
echo ""
echo -e "${YELLOW}Syncing VexJoy Agent to Antigravity CLI Plugin Space...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would create plugin directory: ${ANTIGRAVITY_PLUGIN_DIR}${NC}"
else
    mkdir -p "${ANTIGRAVITY_PLUGIN_DIR}/skills"
    mkdir -p "${ANTIGRAVITY_PLUGIN_DIR}/agents"
    mkdir -p "${ANTIGRAVITY_PLUGIN_DIR}/hooks"
fi

# 1. Mirror plugin.json and hooks.json
sync_mirror_entry "${SCRIPT_DIR}/plugins/vexjoy-agent/plugin.json" "${ANTIGRAVITY_PLUGIN_DIR}/plugin.json" "Antigravity"
sync_mirror_entry "${SCRIPT_DIR}/plugins/vexjoy-agent/hooks.json" "${ANTIGRAVITY_PLUGIN_DIR}/hooks.json" "Antigravity"

# 2. Mirror skills
ANTIGRAVITY_ENTRY_COUNT=0
for item in "${SCRIPT_DIR}/skills/"*; do
    [ -e "$item" ] || continue
    target="${ANTIGRAVITY_PLUGIN_DIR}/skills/$(basename "$item")"
    sync_mirror_entry "$item" "$target" "Antigravity"
    ANTIGRAVITY_ENTRY_COUNT=$((ANTIGRAVITY_ENTRY_COUNT + 1))
done

if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -d "$skill_src" ] || continue
        voice_name=$(basename "$voice_dir")
        target="${ANTIGRAVITY_PLUGIN_DIR}/skills/voice-${voice_name}"
        sync_mirror_entry "$skill_src" "$target" "Antigravity"
        ANTIGRAVITY_ENTRY_COUNT=$((ANTIGRAVITY_ENTRY_COUNT + 1))
    done
fi

if [ -d "${SCRIPT_DIR}/private-skills" ]; then
    for item in "${SCRIPT_DIR}/private-skills/"*; do
        [ -e "$item" ] || continue
        target="${ANTIGRAVITY_PLUGIN_DIR}/skills/$(basename "$item")"
        sync_mirror_entry "$item" "$target" "Antigravity"
        ANTIGRAVITY_ENTRY_COUNT=$((ANTIGRAVITY_ENTRY_COUNT + 1))
    done
fi

# 3. Mirror agents
ANTIGRAVITY_AGENT_COUNT=0
for item in "${SCRIPT_DIR}/agents/"*; do
    [ -e "$item" ] || continue
    target="${ANTIGRAVITY_PLUGIN_DIR}/agents/$(basename "$item")"
    sync_mirror_entry "$item" "$target" "Antigravity"
    ANTIGRAVITY_AGENT_COUNT=$((ANTIGRAVITY_AGENT_COUNT + 1))
done

if [ -d "${SCRIPT_DIR}/private-agents" ]; then
    for item in "${SCRIPT_DIR}/private-agents/"*; do
        [ -e "$item" ] || continue
        target="${ANTIGRAVITY_PLUGIN_DIR}/agents/$(basename "$item")"
        sync_mirror_entry "$item" "$target" "Antigravity"
        ANTIGRAVITY_AGENT_COUNT=$((ANTIGRAVITY_AGENT_COUNT + 1))
    done
fi

# 4. Mirror hooks
ANTIGRAVITY_HOOK_COUNT=0
if [ -d "${SCRIPT_DIR}/hooks" ]; then
    for item in "${SCRIPT_DIR}/hooks/"*; do
        [ -e "$item" ] || continue
        name=$(basename "$item")
        case "$name" in
            __pycache__|*.pyc|tests) continue;;
        esac
        target="${ANTIGRAVITY_PLUGIN_DIR}/hooks/${name}"
        sync_mirror_entry "$item" "$target" "Antigravity"
        ANTIGRAVITY_HOOK_COUNT=$((ANTIGRAVITY_HOOK_COUNT + 1))
    done
fi

# Warn if installed Antigravity CLI is missing
if command -v agy >/dev/null 2>&1; then
    if agy_ver_raw=$(agy --version 2>&1); then
        agy_ver=$(printf '%s' "$agy_ver_raw" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if [ -n "$agy_ver" ]; then
            echo -e "${GREEN}  ✓ Antigravity CLI (${agy_ver}) detected. Plugin ready for activation.${NC}"
        else
            echo -e "${YELLOW}  ⚠ Antigravity CLI detected but version string unparseable${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠ Antigravity CLI installed but \`agy --version\` failed${NC}"
    fi
else
    echo -e "${BLUE}  (agy CLI not installed; plugin will activate when Antigravity CLI is installed)${NC}"
fi

# Sync Gemini CLI hooks mirror (coexists with Antigravity plugin under ~/.gemini/)
echo ""
echo -e "${YELLOW}Syncing Gemini skills mirror...${NC}"
GEMINI_ENTRY_COUNT=0
for item in "${SCRIPT_DIR}/skills/"*; do
    [ -e "$item" ] || continue
    target="${GEMINI_SKILLS_DIR}/$(basename "$item")"
    sync_mirror_entry "$item" "$target" "Gemini"
    GEMINI_ENTRY_COUNT=$((GEMINI_ENTRY_COUNT + 1))
done

if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -d "$skill_src" ] || continue
        voice_name=$(basename "$voice_dir")
        target="${GEMINI_SKILLS_DIR}/voice-${voice_name}"
        sync_mirror_entry "$skill_src" "$target" "Gemini"
        GEMINI_ENTRY_COUNT=$((GEMINI_ENTRY_COUNT + 1))
    done
fi

if [ -d "${SCRIPT_DIR}/private-skills" ]; then
    for item in "${SCRIPT_DIR}/private-skills/"*; do
        [ -e "$item" ] || continue
        target="${GEMINI_SKILLS_DIR}/$(basename "$item")"
        sync_mirror_entry "$item" "$target" "Gemini"
        GEMINI_ENTRY_COUNT=$((GEMINI_ENTRY_COUNT + 1))
    done
fi

echo ""
echo -e "${YELLOW}Syncing Gemini agents mirror...${NC}"
GEMINI_AGENT_COUNT=0
for item in "${SCRIPT_DIR}/agents/"*; do
    [ -e "$item" ] || continue
    target="${GEMINI_AGENTS_DIR}/$(basename "$item")"
    sync_mirror_entry "$item" "$target" "Gemini"
    GEMINI_AGENT_COUNT=$((GEMINI_AGENT_COUNT + 1))
done

if [ -d "${SCRIPT_DIR}/private-agents" ]; then
    for item in "${SCRIPT_DIR}/private-agents/"*; do
        [ -e "$item" ] || continue
        target="${GEMINI_AGENTS_DIR}/$(basename "$item")"
        sync_mirror_entry "$item" "$target" "Gemini"
        GEMINI_AGENT_COUNT=$((GEMINI_AGENT_COUNT + 1))
    done
fi

echo ""
echo -e "${YELLOW}Syncing Gemini hooks mirror...${NC}"
GEMINI_HOOK_COUNT=0
GEMINI_HOOKS_ALLOWLIST="${SCRIPT_DIR}/scripts/gemini-hooks-allowlist.txt"

if [ -f "$GEMINI_HOOKS_ALLOWLIST" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${GEMINI_HOOKS_DIR}${NC}"
    else
        mkdir -p "$GEMINI_HOOKS_DIR"
    fi

    # Parse allowlist and mirror each allowlisted hook file.
    while IFS= read -r line || [ -n "$line" ]; do
        trimmed="${line#"${line%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [ -z "$trimmed" ] && continue
        [ "${trimmed#\#}" != "$trimmed" ] && continue

        rest="${trimmed#*:}"
        filename="${rest%% *}"

        source_file="${SCRIPT_DIR}/hooks/${filename}"
        if [ ! -f "$source_file" ]; then
            echo -e "${RED}  ✗ Allowlisted hook missing: ${filename}${NC}"
            continue
        fi

        target_file="${GEMINI_HOOKS_DIR}/${filename}"
        sync_mirror_entry "$source_file" "$target_file" "Gemini"
        GEMINI_HOOK_COUNT=$((GEMINI_HOOK_COUNT + 1))
    done < "$GEMINI_HOOKS_ALLOWLIST"

    # Mirror hooks/lib so intra-hook imports resolve.
    if [ -d "${SCRIPT_DIR}/hooks/lib" ]; then
        lib_target="${GEMINI_HOOKS_DIR}/lib"
        sync_mirror_entry "${SCRIPT_DIR}/hooks/lib" "$lib_target" "Gemini"
    fi

    # Merge hooks into ~/.gemini/settings.json via the dedicated script.
    GEMINI_SETTINGS="${GEMINI_DIR}/settings.json"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would merge hooks into: ${GEMINI_SETTINGS}${NC}"
    else
        if $PYTHON_CMD "${SCRIPT_DIR}/scripts/generate-gemini-settings-hooks.py" \
            --allowlist "$GEMINI_HOOKS_ALLOWLIST" \
            --output "$GEMINI_SETTINGS" \
            --gemini-hooks-dir "$GEMINI_HOOKS_DIR" 2>&1; then
            echo -e "${GREEN}  ✓ Merged hooks into ${GEMINI_SETTINGS}${NC}"
        else
            echo -e "${RED}  ✗ Failed to merge hooks into settings.json${NC}"
        fi
    fi

    # Warn if installed Gemini CLI is below the hook-support minimum (v0.26.0).
    if command -v gemini >/dev/null 2>&1; then
        gm_ver=$(gemini --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if [ -n "$gm_ver" ]; then
            min_major=0; min_minor=26; min_patch=0
            IFS='.' read -r gm_maj gm_min gm_pat <<< "$gm_ver"
            if [ "$gm_maj" -lt "$min_major" ] || \
               { [ "$gm_maj" -eq "$min_major" ] && [ "$gm_min" -lt "$min_minor" ]; } || \
               { [ "$gm_maj" -eq "$min_major" ] && [ "$gm_min" -eq "$min_minor" ] && [ "${gm_pat:-0}" -lt "$min_patch" ]; }; then
                echo -e "${YELLOW}  ⚠ Gemini CLI version ${gm_ver} is below 0.26.0. Hooks may not work.${NC}"
            fi
        fi
    else
        echo -e "${BLUE}  (gemini CLI not installed; hooks will activate when Gemini CLI is installed)${NC}"
    fi
else
    echo -e "${YELLOW}  ⚠ Gemini hooks allowlist not found at ${GEMINI_HOOKS_ALLOWLIST}; skipping hooks mirror${NC}"
fi

# Nudge consumer-tier Gemini CLI users toward Antigravity before the 2026-06-18 sunset.
if command -v gemini >/dev/null 2>&1 && ! command -v agy >/dev/null 2>&1; then
    echo -e "${YELLOW}  ⚠ Consumer Gemini CLI tiers (AI Pro/Ultra, free Code Assist) sunset 2026-06-18.${NC}"
    echo -e "${YELLOW}    Install Antigravity CLI from https://antigravity.google/cli to continue past that date.${NC}"
    echo -e "${BLUE}    Enterprise/paid-API tiers unaffected.${NC}"
fi

echo ""
echo -e "${YELLOW}Syncing Gemini scripts mirror...${NC}"
if [ -d "${SCRIPT_DIR}/scripts" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would mirror scripts to: ${GEMINI_SCRIPTS_DIR}${NC}"
    else
        mkdir -p "$GEMINI_SCRIPTS_DIR"
    fi
    sync_mirror_entry "${SCRIPT_DIR}/scripts" "$GEMINI_SCRIPTS_DIR" "Gemini"
    GEMINI_SCRIPT_COUNT=$(ls -1 "${SCRIPT_DIR}/scripts/"*.py 2>/dev/null | grep -cv '__init__')
    echo -e "${GREEN}  ✓ Scripts mirrored to ${GEMINI_SCRIPTS_DIR}${NC}"
else
    GEMINI_SCRIPT_COUNT=0
fi

echo ""
echo -e "${YELLOW}Syncing Hermes skills mirror...${NC}"
HERMES_ENTRY_COUNT=0
for item in "${SCRIPT_DIR}/skills/"*; do
    [ -e "$item" ] || continue
    target="${HERMES_SKILLS_DIR}/$(basename "$item")"
    sync_mirror_entry "$item" "$target" "Hermes"
    HERMES_ENTRY_COUNT=$((HERMES_ENTRY_COUNT + 1))
done

if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -d "$skill_src" ] || continue
        voice_name=$(basename "$voice_dir")
        target="${HERMES_SKILLS_DIR}/voice-${voice_name}"
        sync_mirror_entry "$skill_src" "$target" "Hermes"
        HERMES_ENTRY_COUNT=$((HERMES_ENTRY_COUNT + 1))
    done
fi

if [ -d "${SCRIPT_DIR}/private-skills" ]; then
    for item in "${SCRIPT_DIR}/private-skills/"*; do
        [ -e "$item" ] || continue
        target="${HERMES_SKILLS_DIR}/$(basename "$item")"
        sync_mirror_entry "$item" "$target" "Hermes"
        HERMES_ENTRY_COUNT=$((HERMES_ENTRY_COUNT + 1))
    done
fi

echo ""
echo -e "${YELLOW}Syncing Hermes scripts mirror...${NC}"
if [ -d "${SCRIPT_DIR}/scripts" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would mirror scripts to: ${HERMES_SCRIPTS_DIR}${NC}"
    else
        mkdir -p "$HERMES_SCRIPTS_DIR"
    fi
    sync_mirror_entry "${SCRIPT_DIR}/scripts" "$HERMES_SCRIPTS_DIR" "Hermes"
    HERMES_SCRIPT_COUNT=$(ls -1 "${SCRIPT_DIR}/scripts/"*.py 2>/dev/null | grep -cv '__init__')
    echo -e "${GREEN}  ✓ Scripts mirrored to ${HERMES_SCRIPTS_DIR}${NC}"
else
    HERMES_SCRIPT_COUNT=0
fi

# ── Reasonix mirror (skills + scripts + hooks; Claude-Code-compatible extension layer) ──
# Reasonix natively reads ~/.reasonix/skills, shells out to scripts via the SDIR chain,
# and runs Claude-Code-identical hooks declared in ~/.reasonix/settings.json (hooks key only;
# MCP/model/permissions live in user-owned ~/.reasonix/config.json, which we never touch).
echo ""
echo -e "${YELLOW}Syncing Reasonix skills mirror (flatten + copy)...${NC}"
REASONIX_ENTRY_COUNT=0
REASONIX_SEEN_NAMES=" "  # space-delimited set of flat names claimed this run (collision guard)
if [ "$DRY_RUN" != true ]; then
    mkdir -p "$REASONIX_SKILLS_DIR"
    # Sweep stale toolkit symlinks left by the pre-flatten installer (it symlinked
    # skills/<category> dirs, which reasonix can't discover). Reasonix skill entries are
    # ALWAYS real copied dirs now, so any symlink here is stale toolkit output — safe to
    # drop. User-added skills are real dirs and are left untouched.
    find "$REASONIX_SKILLS_DIR" -maxdepth 1 -mindepth 1 -type l -delete 2>/dev/null || true
fi

# Reasonix scans skill roots EXACTLY ONE LEVEL DEEP (src/skills.ts:251-258): a dir entry
# <X> is a skill only when <X>/SKILL.md exists, and it never recurses. vexjoy skills live
# at skills/<category>/<name>/SKILL.md (two levels), so a naive same-name mirror exposes
# category dirs that hold no SKILL.md and reasonix discovers nothing. We therefore FLATTEN
# every skill to ~/.reasonix/skills/<name>/SKILL.md (one level deep).
#
# COPY ALWAYS — even when MODE=symlink: the shipped reasonix npm build (v0.53.2) does NOT
# traverse symlinked skill ENTRIES during discovery (only real directories are scanned), so
# a symlinked skill is invisible while a real-dir copy is found instantly. The reasonix
# skills mirror therefore forces real-directory copies regardless of the install MODE.
# Re-test symlink discovery on each reasonix bump; drop this copy fallback once
# src/skills.ts traverses symlinked entries.
reasonix_install_skill() {
    # $1 = skill source dir (the dir containing SKILL.md); $2 = flat skill name
    local skill_dir=$1
    local name=$2
    local target="${REASONIX_SKILLS_DIR}/${name}"

    # Within-run collision guard: basenames are verified unique, but never clobber a name
    # already claimed by this run. (A target left from a PRIOR run is refreshed below.)
    case "$REASONIX_SEEN_NAMES" in
        *" ${name} "*)
            echo -e "${YELLOW}  Warning: duplicate Reasonix skill name '${name}', skipping ${skill_dir}${NC}"
            return 0
            ;;
    esac
    REASONIX_SEEN_NAMES="${REASONIX_SEEN_NAMES}${name} "

    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would copy Reasonix skill (real dir, copy forced even in symlink mode): ${skill_dir} -> ${target}/${NC}"
    else
        rm -rf "$target"            # idempotent re-run: refresh content like the other mirrors
        mkdir -p "$target"
        cp -r "${skill_dir}/." "$target/"
        echo -e "${GREEN}  ✓ Reasonix copied ${name}${NC}"
    fi
    REASONIX_ENTRY_COUNT=$((REASONIX_ENTRY_COUNT + 1))
}

# Private skills FIRST so they claim canonical names; matching public-skill names then
# trip the within-run collision guard and yield to the private override (parity with the
# Claude install: private overrides public).
if [ -d "${SCRIPT_DIR}/private-skills" ]; then
    while IFS= read -r skill_md; do
        [ -n "$skill_md" ] || continue
        skill_dir=$(dirname "$skill_md")
        reasonix_install_skill "$skill_dir" "$(basename "$skill_dir")"
    done < <(find "${SCRIPT_DIR}/private-skills" -name SKILL.md | sort)
fi

# Voice skills: private-voices/<name>/skill/SKILL.md -> ~/.reasonix/skills/voice-<name>/
if [ -d "${SCRIPT_DIR}/private-voices" ]; then
    for voice_dir in "${SCRIPT_DIR}/private-voices/"*; do
        [ -d "$voice_dir" ] || continue
        skill_src="${voice_dir}/skill"
        [ -f "${skill_src}/SKILL.md" ] || continue
        voice_name=$(basename "$voice_dir")
        reasonix_install_skill "$skill_src" "voice-${voice_name}"
    done
fi

# Public skills last: same-name entries are skipped by the collision guard (private wins).
while IFS= read -r skill_md; do
    [ -n "$skill_md" ] || continue
    skill_dir=$(dirname "$skill_md")
    reasonix_install_skill "$skill_dir" "$(basename "$skill_dir")"
done < <(find "${SCRIPT_DIR}/skills" -name SKILL.md | sort)

# Support dirs (no SKILL.md anywhere — e.g. shared-patterns, kb): copy as real top-level
# dirs so flattened skills' sibling references like ../shared-patterns/*.md resolve, and so
# the downstream voice shared-references deploy (which targets ${REASONIX_SKILLS_DIR}/shared-patterns)
# keeps working. These are not skills (reasonix ignores them: no SKILL.md) so they are not counted.
for support_dir in "${SCRIPT_DIR}/skills/"*/; do
    [ -d "$support_dir" ] || continue
    [ -z "$(find "$support_dir" -name SKILL.md -print -quit)" ] || continue  # skip dirs that hold skills
    support_name=$(basename "$support_dir")
    support_target="${REASONIX_SKILLS_DIR}/${support_name}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would copy Reasonix support dir: ${support_dir} -> ${support_target}/${NC}"
    else
        rm -rf "$support_target"
        cp -r "$support_dir" "$support_target"
        echo -e "${GREEN}  ✓ Reasonix copied support dir ${support_name}${NC}"
    fi
done

echo ""
echo -e "${YELLOW}Syncing Reasonix scripts mirror...${NC}"
if [ -d "${SCRIPT_DIR}/scripts" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would mirror scripts to: ${REASONIX_SCRIPTS_DIR}${NC}"
    else
        mkdir -p "$REASONIX_SCRIPTS_DIR"
    fi
    sync_mirror_entry "${SCRIPT_DIR}/scripts" "$REASONIX_SCRIPTS_DIR" "Reasonix"
    REASONIX_SCRIPT_COUNT=$(ls -1 "${SCRIPT_DIR}/scripts/"*.py 2>/dev/null | grep -cv '__init__')
    echo -e "${GREEN}  ✓ Scripts mirrored to ${REASONIX_SCRIPTS_DIR}${NC}"
else
    REASONIX_SCRIPT_COUNT=0
fi

echo ""
echo -e "${YELLOW}Syncing Reasonix hooks mirror...${NC}"
if [ -d "${SCRIPT_DIR}/hooks" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would mirror hooks to: ${REASONIX_HOOKS_DIR}${NC}"
    else
        mkdir -p "$REASONIX_HOOKS_DIR"
    fi
    sync_mirror_entry "${SCRIPT_DIR}/hooks" "$REASONIX_HOOKS_DIR" "Reasonix"
    REASONIX_HOOK_COUNT=$(ls -1 "${SCRIPT_DIR}/hooks/"*.py 2>/dev/null | grep -cv '__init__')
    echo -e "${GREEN}  ✓ Hooks mirrored to ${REASONIX_HOOKS_DIR}${NC}"
else
    REASONIX_HOOK_COUNT=0
fi

# Generate ~/.reasonix/settings.json (hooks key only; rewrite .claude paths to .reasonix).
# config.json (MCP/model/permissions) is user-owned and never written here.
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would sync hooks from ${SCRIPT_DIR}/.claude/settings.json to ${REASONIX_DIR}/settings.json (with path rewrite)${NC}"
elif [ -f "${SCRIPT_DIR}/.claude/settings.json" ]; then
    REASONIX_SETTINGS="${REASONIX_DIR}/settings.json"
    if [ ! -f "$REASONIX_SETTINGS" ]; then
        echo '{}' > "$REASONIX_SETTINGS"
    fi
    BACKUP_TS=$(date +%Y%m%d-%H%M%S)
    cp "$REASONIX_SETTINGS" "${REASONIX_SETTINGS}.backup.${BACKUP_TS}"
    $PYTHON_CMD -c "
import json, os
repo = json.load(open('${SCRIPT_DIR}/.claude/settings.json'))
dst = '${REASONIX_SETTINGS}'
try:
    merged = json.load(open(dst, encoding='utf-8'))
except (FileNotFoundError, json.JSONDecodeError):
    merged = {}
hooks_json = json.dumps(repo.get('hooks', {}))
hooks_json = hooks_json.replace('\$HOME/.claude/', '\$HOME/.reasonix/')
hooks_json = hooks_json.replace('\${HOME}/.claude/', '\${HOME}/.reasonix/')
merged['hooks'] = json.loads(hooks_json)
merged.setdefault('attribution', repo.get('attribution', {'commit': '', 'pr': ''}))
tmp = dst + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(merged, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.rename(tmp, dst)
print('  Reasonix hooks configured from .claude/settings.json')
"
else
    echo -e "${YELLOW}  Warning: ${SCRIPT_DIR}/.claude/settings.json not found, skipping Reasonix hook sync${NC}"
fi

# Deploy private-voices shared references into skills/shared-patterns/
# These files were removed from the public repo and live in private-voices/shared-references/
# (gitignored). They must be deployed at install time into every runtime's shared-patterns dir.
if [ -d "${SCRIPT_DIR}/private-voices/shared-references" ]; then
    echo ""
    echo -e "${YELLOW}Installing voice shared references...${NC}"
    SHARED_REF_COUNT=0
    for ref_file in "${SCRIPT_DIR}/private-voices/shared-references/"*.md; do
        [ -f "$ref_file" ] || continue
        ref_name=$(basename "$ref_file")
        for target_dir in "${CLAUDE_DIR}/skills/shared-patterns" "${CODEX_SKILLS_DIR}/shared-patterns" "${GEMINI_SKILLS_DIR}/shared-patterns" "${FACTORY_SKILLS_DIR}/shared-patterns" "${HERMES_SKILLS_DIR}/shared-patterns" "${REASONIX_SKILLS_DIR}/shared-patterns"; do
            # Resolve symlinks so we write into the actual directory
            resolved_dir="$target_dir"
            [ -L "$target_dir" ] && resolved_dir="$(readlink -f "$target_dir")"
            if [ -d "$resolved_dir" ]; then
                target="${resolved_dir}/${ref_name}"
                if [ "$DRY_RUN" = true ]; then
                    echo -e "${BLUE}  Would install: ${ref_name} -> ${target_dir}${NC}"
                else
                    if [ "$MODE" = "symlink" ]; then
                        ln -sf "$ref_file" "$target"
                    else
                        cp -f "$ref_file" "$target"
                    fi
                fi
            fi
        done
        SHARED_REF_COUNT=$((SHARED_REF_COUNT + 1))
    done
    if [ "$SHARED_REF_COUNT" -gt 0 ]; then
        echo -e "${GREEN}  ✓ ${SHARED_REF_COUNT} voice shared references installed${NC}"
    fi
fi

# Set up local overlay
echo ""
echo -e "${YELLOW}Setting up local overlay...${NC}"
if [ ! -d "${SCRIPT_DIR}/.local" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${SCRIPT_DIR}/.local/agents${NC}"
        echo -e "${BLUE}  Would create: ${SCRIPT_DIR}/.local/skills${NC}"
    else
        mkdir -p "${SCRIPT_DIR}/.local/agents"
        mkdir -p "${SCRIPT_DIR}/.local/skills"
    fi
fi

# Copy example overlay if .local is empty (only has .gitkeep)
if [ -d "${SCRIPT_DIR}/.local.example" ]; then
    LOCAL_FILES=$(find "${SCRIPT_DIR}/.local" -type f ! -name '.gitkeep' 2>/dev/null | wc -l)
    if [ "$LOCAL_FILES" -eq 0 ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would copy overlay templates from .local.example/ to .local/${NC}"
        else
            echo "  Copying overlay templates to .local/"
            cp -r "${SCRIPT_DIR}/.local.example/"* "${SCRIPT_DIR}/.local/" 2>/dev/null || true
            echo -e "${GREEN}  ✓ Local overlay templates installed${NC}"
            echo -e "${YELLOW}  Edit files in .local/ with your personal configurations${NC}"
        fi
    else
        echo -e "${GREEN}  ✓ Local overlay already configured${NC}"
    fi
fi

# Configure hooks in settings.json
echo ""
echo -e "${YELLOW}Configuring hooks...${NC}"

SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
HOOKS_DIR="${CLAUDE_DIR}/hooks"

# Create settings.json if it doesn't exist
if [ ! -f "$SETTINGS_FILE" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would create: ${SETTINGS_FILE}${NC}"
    else
        echo '{}' > "$SETTINGS_FILE"
    fi
fi

# Sync hooks from repo's .claude/settings.json (authoritative source)
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would sync hooks from ${SCRIPT_DIR}/.claude/settings.json${NC}"
elif [ -f "${SCRIPT_DIR}/.claude/settings.json" ]; then
    # Create a timestamped backup before modifying
    BACKUP_TS=$(date +%Y%m%d-%H%M%S)
    cp "$SETTINGS_FILE" "${SETTINGS_FILE}.backup.${BACKUP_TS}"

    # Sync hooks and attribution from repo settings — repo is authoritative
    $PYTHON_CMD -c "
import json, os
repo = json.load(open('${SCRIPT_DIR}/.claude/settings.json'))
dst = '${SETTINGS_FILE}'
try:
    glob = json.load(open(dst, encoding='utf-8'))
except (FileNotFoundError, json.JSONDecodeError):
    glob = {}
glob['hooks'] = repo.get('hooks', {})
glob.setdefault('attribution', repo.get('attribution', {'commit': '', 'pr': ''}))
tmp = dst + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(glob, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.rename(tmp, dst)
print('  Hooks configured from .claude/settings.json')
"
else
    echo -e "${YELLOW}  Warning: ${SCRIPT_DIR}/.claude/settings.json not found, skipping hook sync${NC}"
fi

# Install Python dependencies
echo ""
echo -e "${YELLOW}Installing Python dependencies...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would install: dependencies from requirements.txt${NC}"
else
    USE_BREAK_SYSTEM_PACKAGES=false
    PIP_INSTALL_ARGS=(-r "${SCRIPT_DIR}/requirements.txt" --quiet)
    if pip_supports_break_system_packages; then
        PIP_INSTALL_ARGS+=(--break-system-packages)
        USE_BREAK_SYSTEM_PACKAGES=true
        echo -e "${YELLOW}  Note: Enabling --break-system-packages because the selected pip supports it${NC}"
    fi

    # Try pip install with --user fallback
    if "${PIP_CMD[@]}" install "${PIP_INSTALL_ARGS[@]}" 2>/dev/null; then
        echo -e "${GREEN}  ✓ Python dependencies installed${NC}"
    elif "${PIP_CMD[@]}" install "${PIP_INSTALL_ARGS[@]}" --user 2>/dev/null; then
        echo -e "${GREEN}  ✓ Python dependencies installed (user mode)${NC}"
    else
        echo -e "${YELLOW}  ⚠ Could not auto-install Python dependencies${NC}"
        print_manual_pip_command "$USE_BREAK_SYSTEM_PACKAGES"
    fi
fi

# Set permissions
echo ""
echo -e "${YELLOW}Setting permissions...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would set 644 on docs/*.md${NC}"
    echo -e "${BLUE}  Would set 755 on hooks/*.py${NC}"
    echo -e "${BLUE}  Would set 755 on scripts/*.py${NC}"
    echo -e "${BLUE}  Would set 600 on ~/.claude/settings.json${NC}"
    echo -e "${BLUE}  Would set 700 on ~/.claude/ and ~/.claude/learning/${NC}"
    echo -e "${BLUE}  Would set 600 on ~/.claude/history.jsonl (if it exists)${NC}"
    echo -e "${BLUE}  Would set 600 on ~/.factory/settings.json${NC}"
    echo -e "${BLUE}  Would set 600 on ~/.reasonix/settings.json${NC}"
else
    chmod 644 "${SCRIPT_DIR}/docs/"*.md 2>/dev/null || true
    find "${SCRIPT_DIR}/hooks" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    find "${SCRIPT_DIR}/scripts" -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
    # Harden ~/.claude/ sensitive files (ADR-122)
    chmod 700 "${CLAUDE_DIR}" 2>/dev/null || true
    chmod 600 "${SETTINGS_FILE}" 2>/dev/null || true
    chmod 600 "$(ls -1t "${SETTINGS_FILE}.backup."* 2>/dev/null | head -1)" 2>/dev/null || true
    chmod 700 "${CLAUDE_DIR}/learning" 2>/dev/null || true
    chmod 600 "${CLAUDE_DIR}/history.jsonl" 2>/dev/null || true
    chmod 600 "${FACTORY_DIR}/settings.json" 2>/dev/null || true
    chmod 600 "$(ls -1t "${FACTORY_DIR}/settings.json.backup."* 2>/dev/null | head -1)" 2>/dev/null || true
    chmod 600 "${REASONIX_DIR}/settings.json" 2>/dev/null || true
    chmod 600 "$(ls -1t "${REASONIX_DIR}/settings.json.backup."* 2>/dev/null | head -1)" 2>/dev/null || true
fi
echo -e "${GREEN}✓ Permissions set${NC}"

# Summary
echo ""
# Regenerate INDEX.json files with private components included
echo ""
echo -e "${YELLOW}Regenerating indexes (including private components)...${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would regenerate skills/INDEX.json with ${NC}"
    echo -e "${BLUE}  Would regenerate agents/INDEX.json with ${NC}"
else
    python3 "${SCRIPT_DIR}/scripts/generate-skill-index.py"  >/dev/null 2>&1 && \
        echo -e "${GREEN}  ✓ Skills index regenerated${NC}" || \
        echo -e "${YELLOW}  ⚠ Skills index generation failed (non-critical)${NC}"
    python3 "${SCRIPT_DIR}/scripts/generate-agent-index.py"  >/dev/null 2>&1 && \
        echo -e "${GREEN}  ✓ Agents index regenerated${NC}" || \
        echo -e "${YELLOW}  ⚠ Agents index generation failed (non-critical)${NC}"
fi

# Write install manifest
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}  Would write: ${CLAUDE_DIR}/.install-manifest.json${NC}"
else
    $PYTHON_CMD -c "
import json, datetime, subprocess, sys
try:
    commit = subprocess.check_output(['git', '-C', '${SCRIPT_DIR}', 'rev-parse', '--short', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
except Exception:
    commit = 'unknown'
manifest = {
    'installed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'toolkit_commit': commit,
    'toolkit_path': '${SCRIPT_DIR}',
    'mode': '${MODE}',
    'components': ['agents', 'skills', 'hooks', 'commands', 'scripts'],
    'codex_components': ['skills', 'agents', 'hooks', 'scripts'],
    'gemini_components': ['skills', 'agents', 'hooks', 'scripts'],
    'factory_components': ['skills', 'droids', 'hooks'],
    'hermes_components': ['skills', 'scripts'],
    'reasonix_components': ['skills', 'scripts', 'hooks'],
}
json.dump(manifest, open('${CLAUDE_DIR}/.install-manifest.json', 'w'), indent=2)
print('  Install manifest written to ~/.claude/.install-manifest.json')
" && echo -e "${GREEN}  ✓ Install manifest written${NC}" || echo -e "${YELLOW}  ⚠ Install manifest write failed (non-critical)${NC}"
fi

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║                       Dry Run Complete!                        ║${NC}"
    echo -e "${YELLOW}║           Re-run without --dry-run to apply changes            ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
else
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                     Installation Complete!                     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
fi
# Count components dynamically (excluding README files)
AGENT_COUNT=$(ls -1 "${SCRIPT_DIR}/agents/"*.md 2>/dev/null | grep -v README | wc -l)
SKILL_COUNT=$(ls -1 "${SCRIPT_DIR}/skills/"*/SKILL.md 2>/dev/null | wc -l)
HOOK_COUNT=$(ls -1 "${SCRIPT_DIR}/hooks/"*.py 2>/dev/null | grep -cv '__init__')
COMMAND_COUNT=$(ls -1 "${SCRIPT_DIR}/commands/"*.md 2>/dev/null | grep -v README | wc -l)
SCRIPT_COUNT=$(ls -1 "${SCRIPT_DIR}/scripts/"*.py 2>/dev/null | grep -cv '__init__')
INVOCABLE_COUNT=$(grep -rl 'user-invocable: true' "${SCRIPT_DIR}/skills/"*/SKILL.md 2>/dev/null | wc -l)

echo ""
echo "Installed components:"
echo "  • Agents: ${AGENT_COUNT} specialized domain experts"
echo "  • Skills: ${SKILL_COUNT} workflow methodologies (${INVOCABLE_COUNT} user-invocable)"
echo "  • Codex skills: ${CODEX_ENTRY_COUNT} mirrored entries in ~/.codex/skills"
echo "  • Codex agents: ${CODEX_AGENT_COUNT} mirrored entries in ~/.codex/agents"
echo "  • Codex hooks: ${CODEX_HOOK_COUNT} mirrored entries in ~/.codex/hooks"
echo "  • Codex scripts: ${CODEX_SCRIPT_COUNT} mirrored scripts in ~/.codex/scripts"
echo "  • Gemini skills: ${GEMINI_ENTRY_COUNT} mirrored entries in ~/.gemini/skills"
echo "  • Gemini agents: ${GEMINI_AGENT_COUNT} mirrored entries in ~/.gemini/agents"
echo "  • Gemini hooks: ${GEMINI_HOOK_COUNT} mirrored entries in ~/.gemini/hooks"
echo "  • Gemini scripts: ${GEMINI_SCRIPT_COUNT} mirrored scripts in ~/.gemini/scripts"
echo "  • Antigravity plugin skills: ${ANTIGRAVITY_ENTRY_COUNT} entries in ${ANTIGRAVITY_PLUGIN_DIR}/skills"
echo "  • Antigravity plugin agents: ${ANTIGRAVITY_AGENT_COUNT} entries in ${ANTIGRAVITY_PLUGIN_DIR}/agents"
echo "  • Antigravity plugin hooks: ${ANTIGRAVITY_HOOK_COUNT} entries in ${ANTIGRAVITY_PLUGIN_DIR}/hooks"
echo "  • Factory skills: ${FACTORY_SKILL_COUNT} mirrored entries in ~/.factory/skills"
echo "  • Factory droids: ${FACTORY_DROID_COUNT} mirrored entries in ~/.factory/droids"
echo "  • Factory hooks: ${FACTORY_HOOK_COUNT} mirrored entries in ~/.factory/hooks"
echo "  • Hermes skills: ${HERMES_ENTRY_COUNT} mirrored entries in ~/.hermes/skills"
echo "  • Hermes scripts: ${HERMES_SCRIPT_COUNT} mirrored scripts in ~/.hermes/scripts"
echo "  • Reasonix skills: ${REASONIX_ENTRY_COUNT} flattened skills (real dirs, one level deep) in ~/.reasonix/skills"
echo "  • Reasonix scripts: ${REASONIX_SCRIPT_COUNT} mirrored scripts in ~/.reasonix/scripts"
echo "  • Reasonix hooks: ${REASONIX_HOOK_COUNT} mirrored entries in ~/.reasonix/hooks"
echo "  • Hooks: ${HOOK_COUNT} automation hooks"
echo "  • Commands: ${COMMAND_COUNT} slash commands"
echo "  • Scripts: ${SCRIPT_COUNT} utility scripts"
echo ""
echo "Next steps:"
echo "  1. Customize .local/ with your personal configurations"
echo "  2. Run 'claude' in any project directory"
echo "  3. Open any project and run: claude"
echo "  4. Try: /do what can you do?"
echo ""
echo "Documentation:"
echo "  • Quick start: docs/QUICKSTART.md"
echo "  • Full reference: docs/REFERENCE.md"
echo "  • Voice system: docs/VOICE-SYSTEM.md"
echo ""
if [ "$MODE" = "symlink" ]; then
    echo -e "${YELLOW}Note: Using symlink mode. Run 'git pull' in this repo to update.${NC}"
else
    echo -e "${YELLOW}Note: Using copy mode. Re-run install.sh to update.${NC}"
fi
echo ""

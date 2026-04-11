#!/bin/bash
#
# Claude Code Toolkit - Installation Script
#
# This script sets up the Claude Code Toolkit agent ecosystem in your Claude Code environment.
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
#   4. Sets up local overlay directory
#   5. Configures hooks in settings.json
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

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                Claude Code Toolkit - Installation Script               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Parse arguments
MODE=""
DRY_RUN=false
FORCE=false
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
            FORCE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--symlink|--copy|--uninstall|--rollback|--dry-run|--force]"
            echo ""
            echo "Options:"
            echo "  --symlink    Create symlinks to this repo (recommended for development)"
            echo "  --copy       Copy files to ~/.claude (recommended for stability)"
            echo "  --uninstall  Remove the installation"
            echo "  --rollback   Restore settings.json from the most recent backup"
            echo "  --dry-run    Show what would happen without making changes"
            echo "  --force      Replace existing directories without prompting"
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

# Function to uninstall
uninstall() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║               Claude Code Toolkit - Uninstaller               ║${NC}"
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

    # Note: [features] codex_hooks = true is intentionally left in config.toml.
    # Users may have other Codex hook configurations we did not write.

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
    echo "  • ~/.codex/config.toml (including [features] codex_hooks flag)"
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

# Install components
echo ""
echo -e "${YELLOW}Installing components (mode: ${MODE})...${NC}"

install_component() {
    local name=$1
    local source="${SCRIPT_DIR}/${name}"
    local target="${CLAUDE_DIR}/${name}"

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

sync_codex_entry() {
    local source=$1
    local target=$2
    local name
    name=$(basename "$source")

    if [ -e "$target" ] || [ -L "$target" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would replace Codex entry: ${target}${NC}"
        else
            rm -rf "$target"
        fi
    fi

    if [ "$MODE" = "symlink" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would symlink Codex entry: ${source} -> ${target}${NC}"
        else
            ln -s "$source" "$target"
            echo -e "${GREEN}  ✓ Codex symlinked ${name}${NC}"
        fi
    else
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}  Would copy Codex entry: ${source} -> ${target}${NC}"
        else
            if [ -d "$source" ]; then
                cp -r "$source" "$target"
            else
                cp "$source" "$target"
            fi
            echo -e "${GREEN}  ✓ Codex copied ${name}${NC}"
        fi
    fi
}

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

    # Ensure codex_hooks feature flag is enabled in ~/.codex/config.toml.
    CODEX_CONFIG="${CODEX_DIR}/config.toml"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}  Would ensure ${CODEX_CONFIG} has [features] codex_hooks = true${NC}"
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
    # Try pip install with --user fallback
    if $PYTHON_CMD -m pip install -r "${SCRIPT_DIR}/requirements.txt" --quiet 2>/dev/null; then
        echo -e "${GREEN}  ✓ Python dependencies installed${NC}"
    elif $PYTHON_CMD -m pip install -r "${SCRIPT_DIR}/requirements.txt" --user --quiet 2>/dev/null; then
        echo -e "${GREEN}  ✓ Python dependencies installed (user mode)${NC}"
    else
        echo -e "${YELLOW}  ⚠ Could not auto-install Python dependencies${NC}"
        echo "  Run manually: pip install -r ${SCRIPT_DIR}/requirements.txt"
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
    'installed_at': datetime.datetime.utcnow().isoformat() + 'Z',
    'toolkit_commit': commit,
    'toolkit_path': '${SCRIPT_DIR}',
    'mode': '${MODE}',
    'components': ['agents', 'skills', 'hooks', 'commands', 'scripts'],
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
echo "  • Hooks: ${HOOK_COUNT} automation hooks"
echo "  • Commands: ${COMMAND_COUNT} slash commands"
echo "  • Scripts: ${SCRIPT_COUNT} utility scripts"
echo ""
echo "Next steps:"
echo "  1. Customize .local/ with your personal configurations"
echo "  2. Run 'claude' in any project directory"
echo "  3. Try: /agents, /skills, /do [your request]"
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

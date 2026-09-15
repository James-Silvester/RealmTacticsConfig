#!/usr/bin/env bash
# Validate the RealmTacticsConfig "meta" manifest system.
#
# Every directory in this repo can contain a pipe-delimited "meta" file that
# tells the game client what files/folders exist and where to find them
# (see README.md). This script walks every "meta" file in the repo and
# checks that everything it points at actually exists on disk, that every
# "meta"-file reference is itself a well-formed manifest, and that every
# "env" file it references resolves to real files/folders too.
#
# Exit code is non-zero if any ERROR-level finding was reported.
set -euo pipefail

META_BASENAME="meta"
ENV_BASENAME="env"
QUIET=0
ROOT=""

# Top-level directories that are intentionally not wired into the game
# client's meta tree (dev/test sandboxes, WIP content, ...) and so should
# not be flagged as orphaned.
ORPHAN_EXCLUDE_ROOTS=(
    "testing"
)

# Paths (relative to --root) skipped entirely - not parsed, not checked.
# Extend with --ignore, e.g. for game modes still under active development.
IGNORE_PATHS=(
    "config/expand_war"
)

usage() {
    cat <<'EOF'
Validate the RealmTacticsConfig "meta" manifest system.

Usage:
  tools/validate_meta.sh [--root PATH] [--ignore PATH]... [--quiet]

  --root PATH    repo root to validate (default: parent of this script's directory)
  --ignore PATH  skip this path (relative to --root, e.g. config/expand_war)
                 entirely - can be passed multiple times
  --quiet        only print errors and warnings, not info/orphan notes

Exit code is non-zero if any ERROR-level finding was reported.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root) ROOT="$2"; shift 2 ;;
        --ignore) IGNORE_PATHS+=("$2"); shift 2 ;;
        --quiet) QUIET=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
if [[ ! -d "$ROOT" ]]; then
    echo "error: --root $ROOT is not a directory" >&2
    exit 2
fi
ROOT="$(cd "$ROOT" && pwd)"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
ERRORS_FILE="$TMP_DIR/errors.txt"
WARNINGS_FILE="$TMP_DIR/warnings.txt"
INFOS_FILE="$TMP_DIR/infos.txt"
REFERENCED_META="$TMP_DIR/referenced_meta.txt"
REFERENCED_ENV="$TMP_DIR/referenced_env.txt"
: > "$ERRORS_FILE"; : > "$WARNINGS_FILE"; : > "$INFOS_FILE"
: > "$REFERENCED_META"; : > "$REFERENCED_ENV"

trim() {
    local s="$1"
    s="${s#"${s%%[![:space:]]*}"}"
    s="${s%"${s##*[![:space:]]}"}"
    printf '%s' "$s"
}

relpath() {
    local p="$1"
    case "$p" in
        "$ROOT"/*) printf '%s' "${p#"$ROOT"/}" ;;
        "$ROOT") printf '.' ;;
        *) printf '%s' "$p" ;;
    esac
}

# True if $1 (an absolute path) is equal to, or under, any path in the
# named array (array of paths relative to $ROOT, trailing slashes ignored).
path_in_list() {
    local -n list="$1"
    local rel entry
    rel="$(relpath "$2")"
    for entry in "${list[@]}"; do
        entry="${entry%/}"
        [[ "$rel" == "$entry" || "$rel" == "$entry"/* ]] && return 0
    done
    return 1
}

is_orphan_excluded() { path_in_list ORPHAN_EXCLUDE_ROOTS "$1"; }
is_ignored() { [[ ${#IGNORE_PATHS[@]} -gt 0 ]] && path_in_list IGNORE_PATHS "$1"; }

# Resolve a meta-table row's (path, filename) pair to an absolute path,
# the same way the client does: strip a leading "/" off `path` and treat it
# as relative to the directory the meta file lives in, then append filename.
resolve_target() {
    local base_dir="$1" path_str="$2" filename="$3" rel
    path_str="$(trim "$path_str")"
    if [[ -z "$path_str" || "$path_str" == "/" || "$path_str" == "-" ]]; then
        rel="."
    elif [[ "$path_str" == /* ]]; then
        rel="${path_str#/}"
    else
        rel="$path_str"
    fi
    realpath -m "$base_dir/$rel/$filename"
}

# Populate the COL associative array: header column name -> 1-based index.
declare -A COL
read_header() {
    local header_line="$1"
    unset COL
    declare -gA COL
    local -a fields
    IFS='|' read -ra fields <<< "$header_line"
    local i=1 h
    for h in "${fields[@]}"; do
        COL["$(trim "$h")"]="$i"
        ((i++))
    done
}

field_of() {
    local -n arr="$1"
    local name="$2"
    local idx="${COL[$name]:-0}"
    if [[ "$idx" -eq 0 ]]; then
        printf ''
        return
    fi
    trim "${arr[$((idx - 1))]:-}"
}

log() {
    local severity="$1" file="$2" line="$3" message="$4"
    local loc
    if [[ -n "$line" ]]; then
        loc="$(relpath "$file"):$line"
    else
        loc="$(relpath "$file")"
    fi
    printf '[%s] %s: %s\n' "$severity" "$loc" "$message" >> "$TMP_DIR/${severity,,}s.txt"
}

# Validate an env file's *_FILE / *_FOLDER / *_DIRECTORY values against the repo root.
validate_env_file() {
    local env_file="$1"
    local header_line line_no=1 first=1
    local -a fields

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ $first -eq 1 ]]; then
            if [[ -z "$(trim "$line")" ]]; then
                log ERROR "$env_file" "" "file is empty (missing header row)"
                return
            fi
            read_header "$line"
            first=0
            ((line_no++))
            continue
        fi
        if [[ -z "$(trim "$line")" ]]; then
            ((line_no++))
            continue
        fi
        IFS='|' read -ra fields <<< "$line"
        local expected=${#COL[@]}
        if [[ ${#fields[@]} -ne $expected ]]; then
            log WARN "$env_file" "$line_no" "row has ${#fields[@]} columns, expected $expected: $(trim "$line")"
        fi
        local key value
        key="$(field_of fields key)"
        value="$(field_of fields value)"
        local this_line=$line_no
        ((line_no++))
        [[ -z "$key" || -z "$value" ]] && continue
        local upper="${key^^}"
        case "$upper" in
            *_FILE|*_FILE_OVERRIDE|*_FOLDER|*_DIRECTORY) ;;
            *) continue ;;
        esac
        local target
        target="$(realpath -m "$ROOT/$value")"
        if [[ ! -e "$target" ]]; then
            log ERROR "$env_file" "$this_line" "\"$key\": path not found -> $(relpath "$target")"
        fi
    done < "$env_file"
}

# Validate one meta-table file's rows: file/folder existence, sub-meta chain
# links, and env references. Meta files themselves are all separately
# discovered and validated by the main loop (see below).
validate_meta_file() {
    local meta_file="$1"
    local base_dir line_no=1 first=1
    local -a fields
    base_dir="$(dirname "$meta_file")"

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ $first -eq 1 ]]; then
            if [[ -z "$(trim "$line")" ]]; then
                log ERROR "$meta_file" "" "file is empty (missing header row)"
                return
            fi
            read_header "$line"
            first=0
            ((line_no++))
            continue
        fi
        if [[ -z "$(trim "$line")" ]]; then
            ((line_no++))
            continue
        fi
        IFS='|' read -ra fields <<< "$line"
        local expected=${#COL[@]}
        if [[ ${#fields[@]} -ne $expected ]]; then
            log WARN "$meta_file" "$line_no" "row has ${#fields[@]} columns, expected $expected: $(trim "$line")"
        fi

        local name filename is_file path_str action sub_meta is_env
        name="$(field_of fields name)"
        filename="$(field_of fields filename)"
        is_file="$(field_of fields isFile)"
        path_str="$(field_of fields path)"
        action="$(field_of fields action)"
        action="${action,,}"
        sub_meta="$(field_of fields subMeta)"
        is_env="$(field_of fields env)"
        [[ -z "$name" ]] && name="$filename"
        local this_line=$line_no
        ((line_no++))

        [[ -z "$filename" || "$filename" == "-" ]] && continue

        local target
        target="$(resolve_target "$base_dir" "$path_str" "$filename")"

        if [[ "$is_file" == "1" ]]; then
            if [[ ! -e "$target" ]]; then
                log ERROR "$meta_file" "$this_line" "\"$name\": file not found -> $(relpath "$target")"
                continue
            fi
            if [[ -d "$target" ]]; then
                log ERROR "$meta_file" "$this_line" "\"$name\": expected a file but found a directory -> $(relpath "$target")"
                continue
            fi
            if [[ "$filename" == "$META_BASENAME" || "$sub_meta" == "1" ]]; then
                echo "$target" >> "$REFERENCED_META"
            fi
            if [[ "$is_env" == "1" ]]; then
                echo "$target" >> "$REFERENCED_ENV"
                validate_env_file "$target"
            fi
        elif [[ "$is_file" == "0" ]]; then
            [[ "$action" != "folder" ]] && continue
            if [[ ! -e "$target" ]]; then
                log ERROR "$meta_file" "$this_line" "\"$name\": folder not found -> $(relpath "$target")"
                continue
            fi
            if [[ ! -d "$target" ]]; then
                log ERROR "$meta_file" "$this_line" "\"$name\": expected a folder but found a file -> $(relpath "$target")"
                continue
            fi
            local folder_meta="$target/$META_BASENAME"
            if [[ ! -f "$folder_meta" ]]; then
                log WARN "$meta_file" "$this_line" "\"$name\": folder -> $(relpath "$target") has no \"meta\" manifest inside it"
            else
                echo "$folder_meta" >> "$REFERENCED_META"
            fi
        else
            log WARN "$meta_file" "$this_line" "isFile column is \"$is_file\", expected \"0\" or \"1\""
        fi
    done < "$meta_file"
}

mapfile -t ALL_META_FILES < <(find "$ROOT" -type f -name "$META_BASENAME" -not -path "*/.git/*" | sort)
mapfile -t ALL_ENV_FILES < <(find "$ROOT" -type f -name "$ENV_BASENAME" -not -path "*/.git/*" | sort)

META_FILES=(); ENV_FILES=()
for f in "${ALL_META_FILES[@]}"; do
    is_ignored "$f" || META_FILES+=("$f")
done
for f in "${ALL_ENV_FILES[@]}"; do
    is_ignored "$f" || ENV_FILES+=("$f")
done

for f in "${META_FILES[@]}"; do
    validate_meta_file "$f"
done

ROOT_META="$ROOT/$META_BASENAME"
sort -u "$REFERENCED_META" -o "$REFERENCED_META"
sort -u "$REFERENCED_ENV" -o "$REFERENCED_ENV"

for f in "${META_FILES[@]}"; do
    [[ "$f" == "$ROOT_META" ]] && continue
    is_orphan_excluded "$f" && continue
    if ! grep -qxF "$f" "$REFERENCED_META"; then
        log INFO "$f" "" "meta file is not referenced by any other meta file (orphaned?)"
    fi
done

for f in "${ENV_FILES[@]}"; do
    is_orphan_excluded "$f" && continue
    if ! grep -qxF "$f" "$REFERENCED_ENV"; then
        log INFO "$f" "" "env file is not referenced by any meta file (orphaned?)"
    fi
done

sort -t: -k1,1 -k2,2n "$ERRORS_FILE" -o "$ERRORS_FILE" 2>/dev/null || true
sort -t: -k1,1 -k2,2n "$WARNINGS_FILE" -o "$WARNINGS_FILE" 2>/dev/null || true
sort -t: -k1,1 -k2,2n "$INFOS_FILE" -o "$INFOS_FILE" 2>/dev/null || true

cat "$ERRORS_FILE" "$WARNINGS_FILE"
[[ $QUIET -eq 0 ]] && cat "$INFOS_FILE"

n_errors=$(wc -l < "$ERRORS_FILE")
n_warnings=$(wc -l < "$WARNINGS_FILE")
n_infos=$(wc -l < "$INFOS_FILE")

echo
echo "Checked ${#META_FILES[@]} meta files and ${#ENV_FILES[@]} env files."
echo "$n_errors error(s), $n_warnings warning(s), $n_infos info note(s)."

[[ "$n_errors" -gt 0 ]] && exit 1
exit 0

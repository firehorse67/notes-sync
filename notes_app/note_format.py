"""Pure-Python helpers for the note file format and Brief JSON interchange.

Kept free of GTK imports so it can be unit-tested directly.
"""
import hashlib
import re
from datetime import datetime, timezone

BRIEF_APP = "brief"
BRIEF_SCHEMA_VERSION = 1
NOTEBOOK_LABEL_PREFIX = "notebook:"

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------

def split_front_matter(raw):
    """Split raw note text into (front_matter_str, body_str)."""
    lines = raw.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "".join(lines[:i + 1]), "".join(lines[i + 1:])
    return "", raw


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def parse_tags_value(value):
    """Parse an inline YAML list like `[a, "b, c", 'd']` into a list of strings."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    tags, buf, quote = [], [], None
    for ch in value:
        if quote:
            if ch == quote:
                quote = None
            else:
                buf.append(ch)
        elif ch in ('"', "'") and not "".join(buf).strip():
            quote = ch
        elif ch == ",":
            tags.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tags.append("".join(buf).strip())
    return [t for t in tags if t]


def clean_tag(tag):
    """Strip characters that can't be represented in the inline tag list."""
    return str(tag).replace("[", "").replace("]", "").replace('"', "").replace("\n", " ").strip()


def format_tags_line(tags):
    """Render a `tags: [...]` line, quoting tags that contain commas."""
    out = []
    for t in tags:
        t = clean_tag(t)
        if not t:
            continue
        if "," in t or t != t.strip() or t.startswith("'"):
            out.append(f'"{t}"')
        else:
            out.append(t)
    return f"tags: [{', '.join(out)}]"


def parse_front_matter(fm):
    """Parse simple `key: value` front matter into a dict.

    `tags` becomes a list and `pinned` a bool; other values are unquoted strings.
    """
    meta = {"tags": [], "pinned": False}
    for line in fm.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "---" or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key == "tags":
            meta["tags"] = parse_tags_value(value)
        elif key == "pinned":
            meta["pinned"] = value.strip().lower() == "true"
        elif key:
            meta[key] = _unquote(value)
    return meta


def find_title(body):
    """Return the text of the first Markdown heading outside fenced code, or None."""
    in_fence = False
    for line in body.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return None


def strip_title_heading(body):
    """Remove the first H1 line (outside code fences) and one following blank line."""
    lines = body.splitlines(keepends=True)
    in_fence = False
    for i, line in enumerate(lines):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^\s{0,3}#\s+", line):
            rest = lines[i + 1:]
            if rest and not rest[0].strip():
                rest = rest[1:]
            return "".join(lines[:i] + rest)
        if line.strip():
            # First non-blank line isn't an H1: nothing to strip.
            break
    return body


def parse_note(raw, fallback_title):
    """Parse a whole note file into a dict with meta, title, body and content."""
    fm, body = split_front_matter(raw)
    meta = parse_front_matter(fm) if fm else {"tags": [], "pinned": False}
    return {
        "meta": meta,
        "front_matter": fm,
        "content": body,
        "title": find_title(body) or fallback_title,
    }


def build_front_matter(tags=(), pinned=False, extra=None):
    lines = ["---", format_tags_line(tags)]
    if pinned:
        lines.append("pinned: true")
    for key, value in (extra or {}).items():
        if value not in (None, ""):
            safe = str(value).replace("\n", " ").strip()
            lines.append(f"{key}: {safe}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Notebook names
# ---------------------------------------------------------------------------

def safe_notebook_name(name):
    """Reduce an untrusted notebook name to a single safe path component, or None."""
    if not isinstance(name, str):
        return None
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    return safe or None


# ---------------------------------------------------------------------------
# Brief interchange
# ---------------------------------------------------------------------------

def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value):
    """Parse an ISO-8601 string (incl. trailing Z) to a POSIX timestamp, or None."""
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def stable_brief_id(rel_path):
    """Deterministic Firestore-safe id derived from the note's relative path."""
    return "ns-" + hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:20]


def is_brief_payload(data):
    return isinstance(data, dict) and data.get("app") == BRIEF_APP


def note_to_brief(raw, rel_path, mtime):
    """Convert a note file's text into a Brief ExportedNote dict."""
    fallback = rel_path.rsplit("/", 1)[-1]
    if fallback.endswith(".md"):
        fallback = fallback[:-3]
    note = parse_note(raw, fallback)
    meta = note["meta"]

    labels = [clean_tag(t) for t in meta["tags"] if clean_tag(t)]
    notebook = rel_path.rsplit("/", 1)[0] if "/" in rel_path else ""
    if notebook:
        labels.append(NOTEBOOK_LABEL_PREFIX + notebook)

    created_ts = parse_iso(meta.get("created")) or mtime
    brief_id = meta.get("brief_id") or stable_brief_id(rel_path)
    if "/" in brief_id or not brief_id.strip():
        brief_id = stable_brief_id(rel_path)

    return {
        "id": brief_id,
        "type": "text",
        "title": note["title"],
        "body": strip_title_heading(note["content"]).strip("\n"),
        "items": [],
        "labels": labels,
        "color": meta.get("color", ""),
        "pinned": bool(meta["pinned"]),
        "createdAt": _iso(created_ts),
        "updatedAt": _iso(mtime),
    }


def note_to_export(raw, rel_path, mtime):
    """One note for the shared JSON format: Brief's fields plus notes-sync's own.

    Brief ignores the extra keys; notes-sync uses "content" to restore the file verbatim.
    """
    n = note_to_brief(raw, rel_path, mtime)
    note = parse_note(raw, n["title"])
    n["content"] = note["content"]
    n["tags"] = note["meta"]["tags"]
    n["notebook"] = rel_path.rsplit("/", 1)[0] if "/" in rel_path else ""
    return n


def make_brief_payload(notes, exported_ts):
    """Envelope readable by both Brief ("app"/"schemaVersion") and notes-sync ("version")."""
    return {
        "app": BRIEF_APP,
        "schemaVersion": BRIEF_SCHEMA_VERSION,
        "version": 1,
        "exportedAt": _iso(exported_ts),
        "notes": notes,
    }


def validate_brief_payload(data):
    """Return the list of valid Brief notes; raise ValueError if the envelope is wrong.

    Individual malformed notes are skipped rather than failing the whole import.
    """
    if not is_brief_payload(data):
        raise ValueError('Expected "app": "brief"')
    if data.get("schemaVersion") != BRIEF_SCHEMA_VERSION:
        raise ValueError(f"Unsupported Brief schemaVersion: {data.get('schemaVersion')!r}")
    notes = data.get("notes")
    if not isinstance(notes, list):
        raise ValueError('Expected "notes" to be an array')

    valid = []
    for n in notes:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid.strip() or "/" in nid:
            continue
        if n.get("type") not in ("text", "list"):
            continue
        valid.append(n)
    return valid


def brief_to_note(n):
    """Convert a Brief note dict into (notebook_or_None, title, file_text, updated_ts_or_None)."""
    title = str(n.get("title") or "").strip()
    body = str(n.get("body") or "")
    items = n.get("items") if isinstance(n.get("items"), list) else []
    labels = [str(l) for l in (n.get("labels") or []) if isinstance(l, str)]

    notebook = None
    tags = []
    for label in labels:
        if label.startswith(NOTEBOOK_LABEL_PREFIX) and notebook is None:
            notebook = safe_notebook_name(label[len(NOTEBOOK_LABEL_PREFIX):])
        else:
            tags.append(label)

    if not title:
        first = body.strip().splitlines()[0] if body.strip() else ""
        title = first[:60].strip() or "Untitled"

    fm = build_front_matter(
        tags=tags,
        pinned=bool(n.get("pinned")),
        extra={
            "color": n.get("color") if isinstance(n.get("color"), str) else "",
            "brief_id": n["id"],
            "created": n.get("createdAt") if parse_iso(n.get("createdAt")) else "",
        },
    )
    updated = parse_iso(n.get("updatedAt"))

    # Written by notes-sync itself: restore the original Markdown exactly, unless the
    # title/body were changed after export (then they win over the stale "content").
    content = n.get("content")
    if isinstance(content, str) and (
        find_title(content) in (None, title)
        and strip_title_heading(content).strip("\n") == body.strip("\n")
    ):
        return notebook, title, fm + content, updated

    parts = [f"# {title}\n"]
    if body.strip():
        parts.append("\n" + body.strip("\n") + "\n")
    if n.get("type") == "list":
        lines = [
            f"- {str(it.get('text', '')).strip()}"
            for it in items
            if isinstance(it, dict) and str(it.get("text", "")).strip()
        ]
        if lines:
            parts.append("\n" + "\n".join(lines) + "\n")

    return notebook, title, fm + "".join(parts), updated

"""
Notation for task dependency links (predecessors/successors).

A link is stored internally as a dict: {'id': <task_id>, 'type': <link type>, 'lag': <int>}.

The compact text notation mirrors the convention used elsewhere for
`predecessor_ids` fields, so plans can be described/exchanged as plain text:

    A            Finish-to-Start (FS) with no lag - the default, bare-id case
    A:SS+2       Start-to-Start, successor starts 2 days after A starts
    A:FF         Finish-to-Finish, successor finishes no earlier than A finishes
    A:SF         Start-to-Finish (rare)
    A:PB / A:FB  CCPM project/feeding buffer links (reserved for buffer rows)

Multiple links are separated by whitespace or semicolons, e.g. "3 5:SS+2".
"""

import re
from typing import Any, Dict, List

DEFAULT_LINK_TYPE = 'FS'

# FS/SS/FF/SF are standard CPM link types. PB/FB are reserved for CCPM
# project/feeding buffer rows, which our-planner does not yet generate.
# Ordered for consistent display in menus/dialogs.
LINK_TYPES_ORDERED = ['FS', 'SS', 'FF', 'SF', 'PB', 'FB']
VALID_LINK_TYPES = set(LINK_TYPES_ORDERED)

# CCPM buffer links (project buffer / feeding buffer) get drawn as dashed
# lines so they read visually differently from ordinary CPM dependencies.
BUFFER_LINK_TYPES = {'PB', 'FB'}

_TOKEN_RE = re.compile(r'^(\d+)(?::([A-Za-z]{2})([+-]\d+)?)?$')


def parse_predecessor_token(token: str) -> Dict[str, Any]:
    """Parse a single link token, e.g. '3', '5:SS+2', '7:FF'."""
    token = token.strip()
    match = _TOKEN_RE.match(token)
    if not match:
        raise ValueError(f"Invalid predecessor link '{token}'")

    task_id_str, link_type, lag_str = match.groups()
    link_type = (link_type or DEFAULT_LINK_TYPE).upper()
    if link_type not in VALID_LINK_TYPES:
        raise ValueError(f"Unknown link type '{link_type}' in '{token}'")

    return {
        'id': int(task_id_str),
        'type': link_type,
        'lag': int(lag_str) if lag_str else 0,
    }


def parse_predecessor_notation(text: str) -> List[Dict[str, Any]]:
    """Parse a predecessor_ids string such as '3 5:SS+2 7:FF' into link entries."""
    if not text or not text.strip():
        return []
    tokens = re.split(r'[;\s]+', text.strip())
    return [parse_predecessor_token(token) for token in tokens if token]


def format_predecessor_token(entry: Dict[str, Any]) -> str:
    """Serialize a single link entry back into its compact notation."""
    link_type = entry.get('type', DEFAULT_LINK_TYPE)
    lag = entry.get('lag', 0)
    token = str(entry['id'])
    if link_type != DEFAULT_LINK_TYPE or lag:
        token += f':{link_type}'
        if lag:
            token += f'{lag:+d}'
    return token


def format_predecessor_notation(
    entries: List[Dict[str, Any]], sep: str = ' '
) -> str:
    """Serialize link entries back into the compact predecessor_ids notation.

    `sep` defaults to a space (the app's dialogs); CSV exports pass ';' to
    match the ccpm-scheduler file contract (parsers accept both).
    """
    return sep.join(format_predecessor_token(entry) for entry in entries or [])


def normalize_predecessor_entries(entries: Any) -> List[Dict[str, Any]]:
    """Coerce predecessor entries into the {id, type, lag} form.

    Handles legacy saved plans where predecessors were a plain list of task
    ids (implicitly Finish-to-Start with no lag).
    """
    normalized = []
    for entry in entries or []:
        if isinstance(entry, dict):
            link_type = entry.get('type', DEFAULT_LINK_TYPE)
            if link_type not in VALID_LINK_TYPES:
                link_type = DEFAULT_LINK_TYPE
            normalized.append(
                {
                    'id': int(entry['id']),
                    'type': link_type,
                    'lag': int(entry.get('lag', 0)),
                }
            )
        else:
            # Legacy format: a bare task id meant an implicit Finish-to-Start link
            normalized.append({'id': int(entry), 'type': DEFAULT_LINK_TYPE, 'lag': 0})
    return normalized

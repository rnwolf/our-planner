"""
Notation for per-task resource allocation tokens.

A resource assignment is stored internally as {resource_id: allocation}.
The compact text notation mirrors ccpm-scheduler's own CSV/schedule.csv
'id:qty' convention (its Phase 5 - see its PLAN.md): a bare id means an
allocation of 1.0 (the default - most tasks just "use" a resource);
'id:qty' states how many units of that resource's daily capacity the task
consumes - a whole number > 1 draws several units from a pool (e.g. 3 of a
4-capacity crew), a fraction < 1 shares one unit's time (e.g. 0.5 of one
person). Same mechanism at either end of one continuum, not two features.

    5        1.0 of resource 5 (the common case)
    5:3      3.0 of resource 5 (a pool draw)
    5:0.5    0.5 of resource 5 (a time-share)

Multiple assignments are separated by semicolons, e.g. "3;5:2". Resource
ids are kept as plain strings here (ccpm-scheduler's own ids need not be
numeric); callers that use plain-integer internal ids convert themselves.
"""

from typing import Any, Dict


def resource_token(resource_id: Any, allocation: float) -> str:
    """'id:allocation' token; ':1' is omitted, whole floats print as ints -
    '5:2;7' = 2 units of resource 5, 1 unit of resource 7."""
    allocation = float(allocation)
    if allocation == 1.0:
        return str(resource_id)
    if allocation.is_integer():
        return f'{resource_id}:{int(allocation)}'
    return f'{resource_id}:{allocation}'


def parse_resource_token(token: str):
    """Parse a single 'id[:allocation]' token into (resource_id, allocation).
    Raises ValueError on a malformed allocation."""
    token = token.strip()
    if ':' in token:
        rid, _, alloc_str = token.partition(':')
        return rid.strip(), float(alloc_str.strip())
    return token, 1.0


def parse_resource_tokens(text: str) -> Dict[str, float]:
    """Parse a semicolon-separated 'resource_ids' string into
    {resource_id: allocation} (string-keyed). Raises ValueError on a
    malformed allocation - callers that want lenient parsing should catch
    it per-token themselves."""
    result = {}
    for token in (text or '').split(';'):
        token = token.strip()
        if not token:
            continue
        rid, alloc = parse_resource_token(token)
        result[rid] = alloc
    return result

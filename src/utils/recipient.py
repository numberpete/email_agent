import hashlib
from typing import Any, Dict, Optional

KNOWN_META_KEYS = {
    "user_id",
    "recipient_email",
    "recipient_name",
    "recipient_org",
    "recipient_role",
    "recipient_relationship",
}

def _meta_get(meta: Optional[dict], key: str) -> Optional[str]:
    if not meta or not isinstance(meta, dict):
        return None
    val = meta.get(key)
    if val is None:
        return None
    s = str(val).strip()
    return s or None

def normalize_recipient(parsed_recipient: Optional[dict], metadata: Optional[dict]) -> Dict[str, Any]:
    parsed_recipient = parsed_recipient or {}
    if not isinstance(parsed_recipient, dict):
        parsed_recipient = {}

    # Metadata overlay (authoritative)
    email = _meta_get(metadata, "recipient_email")
    name = _meta_get(metadata, "recipient_name") or (parsed_recipient.get("name") or None)
    org = _meta_get(metadata, "recipient_org")
    role = _meta_get(metadata, "recipient_role") or (parsed_recipient.get("role") or None)
    relationship = _meta_get(metadata, "recipient_relationship") or (parsed_recipient.get("relationship") or None)

    def _clean(x):
        if x is None:
            return None
        s = str(x).strip()
        return s or None

    return {
        "email": _clean(email),
        "name": _clean(name),
        "org": _clean(org),
        "role": _clean(role),
        "relationship": _clean(relationship),
    }

def compute_recipient_key(recipient: Dict[str, Any]) -> str:
    email = (recipient.get("email") or "").strip().lower()
    if email:
        return f"email:{email}"

    name = (recipient.get("name") or "").strip().lower()
    org = (recipient.get("org") or "").strip().lower()
    role = (recipient.get("role") or "").strip().lower()
    if (name and org) or (name and role):
        base = "|".join([name, org, role])
        digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
        return f"hash:{digest}"

    return None

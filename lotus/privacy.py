"""Privacy Sweep - find where your email/phone leaked, track broker removal.

v1 scope: breach discovery (HaveIBeenPwned unified search), a curated
data-broker opt-out table with per-broker status tracking, and one-click
CCPA/authorized-agent removal drafts opened in the user's mail client
(mailto: - no SMTP creds needed). Fully automated form-filling and
broker-listing detection are the fragile 20% left for later.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from . import db

# (name, site, opt-out page or "", privacy contact or "")
BROKERS = [
    ("Acxiom", "acxiom.com", "acxiom.com/optout", ""),
    ("Epsilon", "epsilon.com", "", "privacy@epsilon.com"),
    ("Oracle Advertising", "oracle.com", "", "privacy_ww@oracle.com"),
    ("Experian", "experian.com", "experian.com/privacy/opting-out.html", ""),
    ("Equifax", "equifax.com", "", "privacy@equifax.com"),
    ("TransUnion", "transunion.com", "", ""),
    ("LexisNexis", "lexisnexis.com", "", "privacy@lexisnexis.com"),
    ("Whitepages", "whitepages.com", "whitepages.com/suppression_requests", ""),
    ("Spokeo", "spokeo.com", "spokeo.com/optout", "privacy@spokeo.com"),
    ("BeenVerified", "beenverified.com", "beenverified.com/app/optout/search", ""),
    ("Intelius", "intelius.com", "intelius.com/optout", "privacy@intelius.com"),
    ("PeopleFinder", "peoplefinder.com", "peoplefinder.com/optout", ""),
    ("FastPeopleSearch", "fastpeoplesearch.com", "fastpeoplesearch.com/removal", ""),
    ("TruePeopleSearch", "truepeoplesearch.com", "truepeoplesearch.com/removal", ""),
    ("Radaris", "radaris.com", "radaris.com/control/privacy", "privacy@radaris.com"),
    ("MyLife", "mylife.com", "mylife.com/ccpa", "privacy@mylife.com"),
    ("Instant Checkmate", "instantcheckmate.com", "instantcheckmate.com/optout", ""),
    ("TruthFinder", "truthfinder.com", "truthfinder.com/opt-out", "privacy@truthfinder.com"),
    ("US Search", "ussearch.com", "ussearch.com/opt-out", ""),
    ("Nuwber", "nuwber.com", "nuwber.com/removal", "privacy@nuwber.com"),
    ("ClustrMaps", "clustrmaps.com", "clustrmaps.com/bl/opt-out", ""),
    ("ThatsThem", "thatsthem.com", "thatsthem.com/optout", ""),
    ("PeekYou", "peekyou.com", "peekyou.com/about/contact/optout", ""),
    ("Cyber Background Checks", "cyberbackgroundchecks.com", "cyberbackgroundchecks.com/optout", ""),
    ("CocoFinder", "cocofinder.com", "cocofinder.com/remove-my-info", ""),
]

_STATUSES = ("not_started", "requested", "confirmed")


def load_state() -> dict:
    try:
        return json.loads(db.get_setting("privacy_brokers", "{}"))
    except json.JSONDecodeError:
        return {}


def mark(broker: str, status: str) -> None:
    if status not in _STATUSES:
        return
    state = load_state()
    state[broker] = status
    db.set_setting("privacy_brokers", json.dumps(state))


def optout_url(broker: tuple) -> str:
    path = broker[2] or broker[1]
    return "https://" + path.lstrip("/")


def contact(broker: tuple) -> str:
    return broker[3] or f"privacy@{broker[1]}"


def breach_check(email: str, timeout: int = 20) -> dict:
    """HIBP unified search - the endpoint the site itself uses. No API key.
    Returns {'breaches': [names], 'pastes': n} or {'error': msg}."""
    url = "https://haveibeenpwned.com/unifiedsearch/" + urllib.parse.quote(email)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Lotus-PrivacySweep", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code == 404:
            return {"breaches": [], "pastes": 0}
        return {"error": f"{type(exc).__name__}: {exc}"}
    breaches = [b.get("Name", "?") for b in data.get("Breaches", [])]
    return {"breaches": breaches, "pastes": len(data.get("Pastes", []))}


def removal_mailto(name: str, email: str, phone: str, broker: tuple) -> str:
    """mailto: link pre-filling an authorized-agent/CCPA removal request."""
    to = contact(broker)
    subject = "Data deletion request - CCPA/privacy rights"
    lines = [
        f"To the {broker[0]} privacy team,",
        "",
        "I request the deletion of all personal information you hold about me, "
        "including its removal from any public people-search listings, and that "
        "you do not sell or share it going forward.",
        "",
        f"Name: {name or '[your name]'}",
        f"Email: {email or '[your email]'}",
    ]
    if phone:
        lines.append(f"Phone: {phone}")
    lines += [
        "",
        "This request is made under applicable privacy rights (CCPA/CPRA, and "
        "GDPR where relevant). Please confirm deletion within the required "
        "45-day window and identify what was removed.",
    ]
    body = "\n".join(lines)
    return (f"mailto:{to}?subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}")

"""Canonical text rendering for OSINT intelligence results.

Both the agent's OSINT flow and the standalone OSINT tool render
analyze_email / analyze_phone results through these formatters, so users see
the same report regardless of which path a query takes.
"""
from typing import Dict, List


def format_email_intelligence(email_data: Dict, fallback_email: str = "") -> List[str]:
    """Render an EmailIntelligence.analyze_email result as report lines."""
    lines = ["═══ Email Intelligence ═══\n"]
    lines.append(f"**Email:** {email_data.get('email', fallback_email)}")
    valid = email_data.get('valid', False)
    lines.append(f"**Valid:** {'✓' if valid else '✗'} {valid}")

    if valid:
        lines.append(f"**Domain:** {email_data['domain']}")
        lines.append(f"**Username:** {email_data['username']}")
        lines.append(f"**Disposable:** {email_data['disposable']}")
        lines.append(f"**Domain exists:** {email_data['domain_exists']}")
        lines.append(f"**Confidence:** {email_data['confidence']:.2f}")

    return lines


def format_phone_intelligence(phone_data: Dict) -> List[str]:
    """Render a PhoneIntelligence.analyze_phone result as report lines."""
    lines = ["\n═══ Phone Intelligence ═══\n"]
    lines.append(f"**Phone:** {phone_data['input']}")
    valid = phone_data.get('valid', False)
    lines.append(f"**Valid:** {'✓' if valid else '✗'} {valid}")

    if valid:
        lines.append(f"**Formatted:** {phone_data['formatted']}")
        lines.append(f"**Country:** {phone_data['country']}")
        lines.append(f"**Type:** {phone_data['type']}")
        if phone_data.get('carrier'):
            lines.append(f"**Carrier:** {phone_data['carrier']}")
        lines.append(f"**Confidence:** {phone_data['confidence']:.2f}")

        if phone_data.get('variations'):
            lines.append("\n**Phone Variations:**")
            for var in phone_data['variations'][:5]:
                lines.append(f"  • {var}")

    return lines

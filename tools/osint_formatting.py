"""Section formatters for osint_search text output (pure dict -> list[str])."""
from core.osint.formatting import format_email_intelligence, format_phone_intelligence


def _format_email_section(email_data: dict) -> list[str]:
    """Format single-email intelligence results (canonical shared layout)."""
    return format_email_intelligence(email_data) + [""]


def _format_email_batch_section(batch_data: dict) -> list[str]:
    """Format batch email intelligence results."""
    summary = batch_data['summary']
    lines = [
        "═══ Batch Email Intelligence ═══",
        f"Total Emails Analyzed: {batch_data['analyzed']}/{batch_data['total']}",
        "Summary:",
        f"  ✅ Valid: {summary['valid']}",
        f"  ❌ Invalid: {summary['invalid']}",
        f"  🗑️  Disposable: {summary['disposable']}",
        f"  📊 Total Variations: {summary['total_variations']}",
        "",
        "Individual Results:",
    ]
    for i, email_result in enumerate(batch_data['results'], 1):
        if 'error' in email_result:
            lines.append(f"  {i}. ❌ {email_result['email']}: {email_result['error']}")
        else:
            status = "✅" if email_result.get('valid') else "❌"
            disp = "🗑️" if email_result.get('disposable') else ""
            lines.append(f"  {i}. {status} {disp} {email_result['email']} - {email_result.get('domain', 'N/A')}")
    lines.append("")
    return lines


def _format_phone_section(phone_data: dict) -> list[str]:
    """Format single-phone intelligence results (canonical shared layout)."""
    return format_phone_intelligence(phone_data) + [""]


def _format_phone_batch_section(batch_data: dict) -> list[str]:
    """Format batch phone intelligence results."""
    summary = batch_data['summary']
    lines = [
        "═══ Batch Phone Intelligence ═══",
        f"Total Phones Analyzed: {batch_data['analyzed']}/{batch_data['total']}",
        "Summary:",
        f"  ✅ Valid: {summary['valid']}",
        f"  ❌ Invalid: {summary['invalid']}",
        f"  📱 Mobile: {summary['mobile']}",
        f"  📞 Landline: {summary['landline']}",
        f"  🌍 Countries: {', '.join(summary['countries'])}",
        "",
        "Individual Results:",
    ]
    for i, phone_result in enumerate(batch_data['results'], 1):
        if 'error' in phone_result:
            phone = phone_result.get('phone', phone_result.get('input', 'Unknown'))
            lines.append(f"  {i}. ❌ {phone}: {phone_result['error']}")
        else:
            status = "✅" if phone_result.get('valid') else "❌"
            ptype = phone_result.get('type', 'Unknown')
            country = phone_result.get('country', 'Unknown')
            formatted = phone_result.get('formatted', phone_result.get('input', 'N/A'))
            lines.append(f"  {i}. {status} {formatted} - {country} ({ptype})")
    lines.append("")
    return lines


def _format_ip_section(ip_data: dict) -> list[str]:
    """Format IP intelligence results, delegating to IPIntelligence."""
    if 'error' in ip_data:
        return [f"❌ IP Analysis Error: {ip_data.get('error', 'Unknown error')}"]
    from core.osint.ip_intel import IPIntelligence
    return [IPIntelligence().format_results(ip_data)]


def _format_social_section(social_data: dict) -> list[str]:
    """Format social media intelligence results."""
    lines = ["═══ Social Intelligence ═══"]
    if 'error' in social_data:
        lines.append(f"Error: {social_data.get('error', 'Unknown error')}")
        lines.append("")
        return lines

    lines.append(f"Username: {social_data.get('username', 'Unknown')}")
    lines.append(
        f"Platforms Found: {social_data.get('platforms_found', 0)} / {social_data.get('total_platforms', 0)}"
    )

    social_intel = social_data.get('social_intelligence', {})
    found_profiles = [
        _describe_profile(data) for data in social_intel.get('platforms_found', [])
    ]
    if found_profiles:
        lines.append("\nProfiles Found:")
        lines.extend(f"  {profile}" for profile in found_profiles)
    else:
        lines.append("No profiles found on searched platforms")

    summary = social_intel.get('summary', {})
    if summary:
        lines.append(f"\nSummary: Searched {summary.get('total_platforms_checked', 0)} platforms")
    lines.append("")
    return lines


def _describe_profile(data: dict) -> str:
    """Build a one-line description of a found social profile."""
    info = f"✓ {data.get('platform', 'unknown').title()}"
    profile = data.get('profile_data') or {}
    if profile.get('display_name'):
        info += f" - {profile['display_name']}"
    if profile.get('followers'):
        info += f" ({profile['followers']} followers)"
    return info


def _format_suggestions_section(suggestions: dict) -> list[str]:
    """Format AI query suggestions."""
    lines = ["═══ AI Suggestions ═══"]
    if suggestions.get('variations'):
        lines.append("Query Variations:")
        lines.extend(f"  • {var}" for var in suggestions['variations'][:3])
    if suggestions.get('operators'):
        lines.append("Suggested Operators:")
        lines.extend(f"  • {op}: {val}" for op, val in suggestions['operators'].items())
    return lines


def _format_intelligence_sections(result: dict) -> list[str]:
    """Format every intelligence section present in a process_query result."""
    intelligence = result.get('intelligence', {})
    lines: list[str] = []

    if 'email' in intelligence:
        lines.extend(_format_email_section(intelligence['email']))
    if 'email_batch' in intelligence:
        lines.extend(_format_email_batch_section(intelligence['email_batch']))
    if 'phone' in intelligence:
        lines.extend(_format_phone_section(intelligence['phone']))
    if 'phone_batch' in intelligence:
        lines.extend(_format_phone_batch_section(intelligence['phone_batch']))
    if 'domain' in intelligence:
        from core.osint import DomainIntelligence
        lines.append(DomainIntelligence().format_results(intelligence['domain']))
    if 'ip' in intelligence:
        lines.extend(_format_ip_section(intelligence['ip']))
    if 'social' in intelligence:
        lines.extend(_format_social_section(intelligence['social']))
    if result.get('suggestions'):
        lines.extend(_format_suggestions_section(result['suggestions']))

    return lines

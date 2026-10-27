"""Memory command handlers for OSINTTool (remember / recall / forget).

Bound onto OSINTTool as methods in tools.osint_tool; each takes the tool
instance as first arg and dispatches via the tables below.
"""
import logging

logger = logging.getLogger("crawllama")


# Data-driven dispatch tables for the memory commands. Each maps a command
# keyword to the memory-store method (resolved via getattr) plus its labels,
# replacing what used to be three long if/elif ladders.
_REMEMBER_DISPATCH = {
    'email':    ('remember_email',    'Email'),
    'phone':    ('remember_phone',    'Phone'),
    'ip':       ('remember_ip',       'IP'),
    'username': ('remember_username', 'Username'),
    'domain':   ('remember_domain',   'Domain'),
}

_RECALL_GETTERS = {
    'emails':    ('get_all_emails',    'emails'),
    'phones':    ('get_all_phones',    'phones'),
    'ips':       ('get_all_ips',       'IPs'),
    'usernames': ('get_all_usernames', 'usernames'),
    'domains':   ('get_all_domains',   'domains'),
    'notes':     ('get_all_notes',     'notes'),
}

_FORGET_DISPATCH = {
    'email':    ('forget_email',    'Email {v} forgotten',    'Email {v} not found in memory'),
    'phone':    ('forget_phone',    'Phone {v} forgotten',    'Phone {v} not found in memory'),
    'ip':       ('forget_ip',       'IP {v} forgotten',       'IP {v} not found in memory'),
    'username': ('forget_username', 'Username {v} forgotten', 'Username {v} not found in memory'),
    'domain':   ('forget_domain',   'Domain {v} forgotten',   'Domain {v} not found in memory'),
    'note':     ('forget_note',     'Note forgotten',         'Note not found in memory'),
    'category': ('clear_category',  'Category {v} cleared',   'Category {v} not found'),
}


def _handle_remember(osint_tool, parsed) -> dict:
    """Handle remember operation (dispatch by remember_type)."""
    remember_type = parsed.remember_type.lower()
    value = parsed.remember_value

    result = {
        'operation': 'remember',
        'type': remember_type,
        'value': value,
        'success': False
    }

    try:
        if remember_type == 'note':
            result['success'] = osint_tool.memory.add_note(value)
            result['message'] = "Note added successfully"
        elif remember_type in _REMEMBER_DISPATCH:
            method_name, label = _REMEMBER_DISPATCH[remember_type]
            success = getattr(osint_tool.memory, method_name)(value)
            result['success'] = success
            result['message'] = (
                f"{label} {value} remembered" if success
                else f"{label} {value} already in memory"
            )
        else:
            result['message'] = f"Unknown remember type: {remember_type}"

    except Exception as e:
        result['message'] = f"Error: {e}"
        logger.error(f"Remember operation failed: {e}")

    return result


def _handle_recall(osint_tool, parsed) -> dict:
    """Handle recall operation (search, full dump, or single category)."""
    category = parsed.recall_category.lower() if parsed.recall_category else 'all'
    query = parsed.recall_query

    result = {
        'operation': 'recall',
        'category': category,
        'query': query,
        'data': {}
    }

    try:
        if query:
            # Search across all categories
            result['data'] = osint_tool.memory.search(query)
            result['message'] = f"Search results for '{query}'"
        elif category == 'all':
            # Get summary of all data
            result['data'] = {
                'summary': osint_tool.memory.get_summary(),
                'emails': osint_tool.memory.get_all_emails(),
                'phones': osint_tool.memory.get_all_phones(),
                'ips': osint_tool.memory.get_all_ips(),
                'usernames': osint_tool.memory.get_all_usernames(),
                'domains': osint_tool.memory.get_all_domains(),
                'notes': osint_tool.memory.get_all_notes()
            }
            result['message'] = "All stored data retrieved"
        elif category in _RECALL_GETTERS:
            getter, label = _RECALL_GETTERS[category]
            items = getattr(osint_tool.memory, getter)()
            result['data'][category] = items
            result['message'] = f"Retrieved {len(items)} {label}"
        else:
            result['message'] = f"Unknown category: {category}"

    except Exception as e:
        result['message'] = f"Error: {e}"
        result['error'] = str(e)
        logger.error(f"Recall operation failed: {e}")

    return result


def _handle_forget(osint_tool, parsed) -> dict:
    """Handle forget operation (dispatch by forget_type)."""
    forget_type = parsed.forget_type.lower()
    value = parsed.forget_value

    result = {
        'operation': 'forget',
        'type': forget_type,
        'value': value,
        'success': False
    }

    try:
        if forget_type == 'all':
            result['success'] = osint_tool.memory.clear_all()
            result['message'] = "All memory cleared"
        elif forget_type in _FORGET_DISPATCH:
            method_name, ok_msg, fail_msg = _FORGET_DISPATCH[forget_type]
            success = getattr(osint_tool.memory, method_name)(value)
            result['success'] = success
            result['message'] = (ok_msg if success else fail_msg).format(v=value)
        else:
            result['message'] = f"Unknown forget type: {forget_type}"

    except Exception as e:
        result['message'] = f"Error: {e}"
        logger.error(f"Forget operation failed: {e}")

    return result

"""Clean up hallucinated email variations from memory store."""
from core.memory_store import get_memory_store

# Only these 3 emails should be kept
valid_emails = [
    'redacted@example.com',
    'redacted@example.com',
    'redacted@example.com'
]

memory = get_memory_store()

# Get all emails
all_emails = memory.get_all_emails()

print(f"Total emails before cleanup: {len(all_emails)}")
print("\nEmails to remove:")

removed_count = 0
for email_entry in all_emails:
    email = email_entry['value']
    if email not in valid_emails:
        print(f"  - {email}")
        if memory.forget_email(email):
            removed_count += 1

print(f"\n✅ Removed {removed_count} hallucinated email variations")
print(f"Remaining emails: {len(memory.get_all_emails())}")
print("\nRemaining emails:")
for email_entry in memory.get_all_emails():
    print(f"  • {email_entry['value']}")

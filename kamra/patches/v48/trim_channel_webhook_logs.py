"""#566: drop raw guest text already stored on channel webhook Agent Action
Log rows. New webhooks only keep a summary + conversation ref; this pass
trims what was written before that change. Safe to rerun."""

from kamra.privacy import trim_channel_webhook_logs


def execute():
	trim_channel_webhook_logs()

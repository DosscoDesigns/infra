"""Render an Apple Mail message to PDF.

Pulls the raw RFC822 source via AppleScript, extracts the HTML (or wraps
plain text), and renders to PDF using Chrome headless. Used to generate
audit-trail PDFs of emailed receipts/invoices for QBO Attachable upload.
"""
from __future__ import annotations

import html as html_lib
import subprocess
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Optional

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def fetch_message_source(rfc_message_id: str, account: str = "Dossco Designs LLC",
                         mailbox: str = "INBOX") -> str:
    """Get the raw RFC822 source of a Mail.app message via AppleScript.

    `rfc_message_id` is the RFC822 Message-ID (the same string apple-mail-mcp
    returns as `message_id`, e.g. "u3x1FEXQTNihOFfoP02SHg@geopod-ismtpd-15").
    Mail.app's AppleScript bridge matches messages by this property — not by
    the integer database id.
    """
    script = f'''
    tell application "Mail"
        set acct to account "{account}"
        set mb to mailbox "{mailbox}" of acct
        set theMessage to first message of mb whose message id is "{rfc_message_id}"
        return source of theMessage
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def extract_html_body(source: str) -> str:
    """Pull the HTML body out of an RFC822 message. Falls back to wrapping
    the plain-text body in <pre>...</pre> if no HTML part exists."""
    msg = BytesParser(policy=policy.default).parsebytes(
        source.encode("utf-8", errors="replace")
    )
    body = msg.get_body(preferencelist=("html", "plain"))
    if body is None:
        return "<html><body><i>(empty message)</i></body></html>"

    if body.get_content_type() == "text/html":
        return body.get_content()

    # Plain text — wrap in basic HTML for legibility
    text = body.get_content()
    escaped = html_lib.escape(text)
    return (
        f"<html><head><meta charset='utf-8'></head>"
        f"<body><pre style='font-family: -apple-system, Helvetica, sans-serif; "
        f"white-space: pre-wrap;'>{escaped}</pre></body></html>"
    )


def render_html_to_pdf(html: str, output_path: Path) -> None:
    """Render HTML to PDF via Chrome headless."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_temp = output_path.with_suffix(".tmp.html")
    html_temp.write_text(html, encoding="utf-8")
    try:
        subprocess.run(
            [
                CHROME_BIN, "--headless", "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={output_path}",
                f"file://{html_temp.absolute()}",
            ],
            check=True, capture_output=True,
        )
    finally:
        html_temp.unlink(missing_ok=True)


def email_to_pdf(rfc_message_id: str, output_path: str | Path,
                 account: str = "Dossco Designs LLC",
                 mailbox: str = "INBOX") -> Path:
    """End-to-end: fetch a Mail message and render to PDF.

    Returns the output path.
    """
    output_path = Path(output_path)
    source = fetch_message_source(rfc_message_id, account, mailbox)
    html = extract_html_body(source)
    render_html_to_pdf(html, output_path)
    return output_path


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("rfc_message_id",
                   help="RFC822 Message-ID (e.g. u3x1FEXQTNihOFfoP02SHg@geopod-ismtpd-15)")
    p.add_argument("output_path")
    p.add_argument("--account", default="Dossco Designs LLC")
    p.add_argument("--mailbox", default="INBOX")
    args = p.parse_args()
    out = email_to_pdf(args.rfc_message_id, args.output_path, args.account, args.mailbox)
    print(f"Wrote {out}")

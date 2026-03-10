import resend
from django.conf import settings


def send_email_via_resend(*, to_email: str, subject: str, text: str, html: str | None = None):
    resend.api_key = settings.RESEND_API_KEY

    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html

    return resend.Emails.send(payload)


def send_verification_otp_email(email: str, otp: str):
    subject = "Verify your Labelz email"
    text = f"Your Labelz verification OTP is {otp}. It expires in 10 minutes."
    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;">
      <h2>Verify your email</h2>
      <p>Your OTP is:</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:4px;">{otp}</p>
      <p>This OTP expires in 10 minutes.</p>
    </div>
    """
    return send_email_via_resend(
        to_email=email,
        subject=subject,
        text=text,
        html=html,
    )


def send_password_reset_otp_email(email: str, otp: str):
    subject = "Reset your Labelz password"
    text = f"Your Labelz password reset OTP is {otp}. It expires in 10 minutes."
    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;">
      <h2>Reset your password</h2>
      <p>Your OTP is:</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:4px;">{otp}</p>
      <p>This OTP expires in 10 minutes.</p>
    </div>
    """
    return send_email_via_resend(
        to_email=email,
        subject=subject,
        text=text,
        html=html,
    )

HELP_PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLrfWFHU5RAQZNxhfV1Hh_XPRnhA6txMuz"

def send_email_via_resend(*, to_email: str, subject: str, text: str, html: str | None = None):
    resend.api_key = settings.RESEND_API_KEY

    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html

    return resend.Emails.send(payload)

def send_welcome_email(email: str, org_name: str | None = None):
    org_line = f" for {org_name}" if org_name else ""

    subject = "Welcome to Labelz"
    text = (
        f"Welcome to Labelz{org_line}.\n\n"
        f"To get started quickly, watch our short help tutorials here:\n"
        f"{HELP_PLAYLIST_URL}\n\n"
        f"Glad to have you with us.\n"
        f"- Team Labelz"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111;">
      <p>Hi,</p>
      <p>Welcome to <strong>Labelz</strong>{org_line}.</p>
      <p>To get started quickly, watch our short help tutorials here:</p>
      <p>
        <a href="{HELP_PLAYLIST_URL}" target="_blank" rel="noopener noreferrer">
          Watch the Labelz help playlist
        </a>
      </p>
      <p>Glad to have you with us.</p>
      <p>— Team Labelz</p>
    </div>
    """

    return send_email_via_resend(
        to_email=email,
        subject=subject,
        text=text,
        html=html,
    )

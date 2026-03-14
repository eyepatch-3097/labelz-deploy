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

def send_verification_success_email(email: str):
    subject = "Your Labelz email is verified"
    text = (
        "Your email has been successfully verified.\n\n"
        "You can now continue using Labelz normally.\n\n"
        "Need help getting started? Watch our tutorials here:\n"
        "https://www.youtube.com/playlist?list=PLrfWFHU5RAQZNxhfV1Hh_XPRnhA6txMuz\n\n"
        "- Team Labelz"
    )
    html = """
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111;">
      <p>Hi,</p>
      <p>Your email has been successfully <strong>verified</strong>.</p>
      <p>You can now continue using Labelz normally.</p>
      <p>
        Need help getting started?
        <a href="https://www.youtube.com/playlist?list=PLrfWFHU5RAQZNxhfV1Hh_XPRnhA6txMuz" target="_blank" rel="noopener noreferrer">
          Watch the Labelz help tutorials
        </a>.
      </p>
      <p>— Team Labelz</p>
    </div>
    """
    return send_email_via_resend(
        to_email=email,
        subject=subject,
        text=text,
        html=html,
    )

VERIFICATION_HELP_URL = "https://www.labelz.live/accounts/verify/"
HELP_PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLrfWFHU5RAQZNxhfV1Hh_XPRnhA6txMuz"


def send_verification_reminder_email(email: str, day: int):
    subject = f"Reminder: verify your Labelz email"
    text = (
        f"Hi,\n\n"
        f"This is a reminder to verify your Labelz email address.\n\n"
        f"Please verify your email here:\n{VERIFICATION_HELP_URL}\n\n"
        f"If you need help getting started, watch the tutorials here:\n{HELP_PLAYLIST_URL}\n\n"
        f"— Team Labelz"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111;">
      <p>Hi,</p>
      <p>This is a reminder to verify your <strong>Labelz</strong> email address.</p>
      <p>
        <a href="{VERIFICATION_HELP_URL}">Verify your email</a>
      </p>
      <p>
        Need help getting started?
        <a href="{HELP_PLAYLIST_URL}">Watch the tutorials</a>
      </p>
      <p>— Team Labelz</p>
    </div>
    """
    return send_email_via_resend(
        to_email=email,
        subject=subject,
        text=text,
        html=html,
    )


def send_account_closure_email(email: str):
    subject = "Your Labelz account has been removed"
    text = (
        "Hi,\n\n"
        "Your Labelz account has been removed because the email address was not verified in time.\n\n"
        "You can sign up again anytime and verify your email to continue.\n\n"
        "— Team Labelz"
    )
    html = """
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111;">
      <p>Hi,</p>
      <p>Your <strong>Labelz</strong> account has been removed because the email address was not verified in time.</p>
      <p>You can sign up again anytime and verify your email to continue.</p>
      <p>— Team Labelz</p>
    </div>
    """
    return send_email_via_resend(
        to_email=email,
        subject=subject,
        text=text,
        html=html,
    )

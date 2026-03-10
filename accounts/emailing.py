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

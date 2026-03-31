"""
Notification Service - Email and SMS notifications.
Supports SendGrid for email and Twilio for SMS (optional).
"""
import asyncio
from datetime import datetime
from typing import Optional, List
import structlog

from backend.config import settings

logger = structlog.get_logger("nomadnest.notifications")


# --- Email Templates ---

TEMPLATES = {
    "booking_confirmation": {
        "subject": "Your NomadNest Booking is Confirmed! 🏨",
        "html": """
            <h2>Booking Confirmed!</h2>
            <p>Hi {user_name},</p>
            <p>Great news! Your booking at <strong>{listing_name}</strong> has been confirmed.</p>
            <p><strong>Check-in:</strong> {check_in}<br>
            <strong>Check-out:</strong> {check_out}</p>
            <p>We can't wait to host you!</p>
            <p>— The NomadNest Team</p>
        """,
    },
    "booking_reminder": {
        "subject": "Your NomadNest Stay Starts Soon! 🧳",
        "html": """
            <h2>Pack Your Bags!</h2>
            <p>Hi {user_name},</p>
            <p>Your stay at <strong>{listing_name}</strong> begins on <strong>{check_in}</strong>.</p>
            <p>Don't forget to bring your essentials!</p>
            <p>— The NomadNest Team</p>
        """,
    },
    "message_received": {
        "subject": "New Message on NomadNest 💬",
        "html": """
            <h2>You have a new message!</h2>
            <p>Hi {user_name},</p>
            <p><strong>{sender_name}</strong> sent you a message:</p>
            <blockquote>{message_preview}</blockquote>
            <p><a href="{app_url}/messages">View Message</a></p>
            <p>— The NomadNest Team</p>
        """,
    },
    "escalation_resolved": {
        "subject": "Your Support Request Has Been Resolved ✅",
        "html": """
            <h2>Support Update</h2>
            <p>Hi {user_name},</p>
            <p>Your support request has been resolved by our team.</p>
            <p><strong>Resolution:</strong></p>
            <p>{resolution_notes}</p>
            <p>If you have any further questions, please reply to this email.</p>
            <p>— The NomadNest Support Team</p>
        """,
    },
    "welcome": {
        "subject": "Welcome to NomadNest! 🌍",
        "html": """
            <h2>Welcome Aboard!</h2>
            <p>Hi {user_name},</p>
            <p>Welcome to NomadNest — the platform for digital nomads like you!</p>
            <p>Here's what you can do:</p>
            <ul>
                <li>🏠 Browse co-living spaces worldwide</li>
                <li>📅 Book stays with our AI concierge</li>
                <li>🤝 Connect with fellow nomads</li>
            </ul>
            <p><a href="{app_url}">Start Exploring</a></p>
            <p>— The NomadNest Team</p>
        """,
    },
}


async def send_email(
    to_email: str,
    template_name: str,
    context: dict,
    from_email: str = None
) -> bool:
    """
    Send an email using SendGrid or fallback to logging.
    """
    template = TEMPLATES.get(template_name)
    if not template:
        logger.error("email_template_not_found", template=template_name)
        return False

    subject = template["subject"].format(**context)
    html_body = template["html"].format(**context, app_url=settings.FRONTEND_URL)

    # Try SendGrid
    if settings.SENDGRID_API_KEY:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=from_email or "noreply@nomadnest.ai",
                to_emails=to_email,
                subject=subject,
                html_content=html_body,
            )

            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)

            logger.info("email_sent",
                       to=to_email,
                       template=template_name,
                       status_code=response.status_code)
            return response.status_code in [200, 201, 202]

        except ImportError:
            logger.warning("sendgrid_not_installed")
        except Exception as e:
            logger.error("sendgrid_error", error=str(e))

    # Fallback: Log the email
    logger.info("email_would_send",
               to=to_email,
               subject=subject,
               template=template_name)
    return True  # Pretend success for dev


async def send_sms(
    to_phone: str,
    message: str
) -> bool:
    """
    Send an SMS using Twilio (optional).
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.info("sms_would_send", to=to_phone, message=message[:50])
        return True  # Pretend success

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to_phone
        )

        logger.info("sms_sent", to=to_phone, sid=message.sid)
        return True

    except ImportError:
        logger.warning("twilio_not_installed")
        return False
    except Exception as e:
        logger.error("twilio_error", error=str(e))
        return False


# --- High-level notification functions ---

async def notify_booking_confirmed(
    user_email: str,
    user_name: str,
    listing_name: str,
    check_in: str,
    check_out: str
):
    """Send booking confirmation notification."""
    await send_email(
        to_email=user_email,
        template_name="booking_confirmation",
        context={
            "user_name": user_name,
            "listing_name": listing_name,
            "check_in": check_in,
            "check_out": check_out,
        }
    )


async def notify_new_message(
    user_email: str,
    user_name: str,
    sender_name: str,
    message_preview: str
):
    """Notify user of new message."""
    await send_email(
        to_email=user_email,
        template_name="message_received",
        context={
            "user_name": user_name,
            "sender_name": sender_name,
            "message_preview": message_preview[:100],
        }
    )


async def notify_escalation_resolved(
    user_email: str,
    user_name: str,
    resolution_notes: str
):
    """Notify user their escalation was resolved."""
    await send_email(
        to_email=user_email,
        template_name="escalation_resolved",
        context={
            "user_name": user_name,
            "resolution_notes": resolution_notes,
        }
    )


async def send_welcome_email(user_email: str, user_name: str):
    """Send welcome email to new user."""
    await send_email(
        to_email=user_email,
        template_name="welcome",
        context={"user_name": user_name}
    )

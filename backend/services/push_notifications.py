"""
Push Notification Service - Email and SMS notifications.
Supports booking confirmations, reminders, and alerts.
"""
import os
from typing import Optional, List, Dict, Any
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationType(str, Enum):
    BOOKING_CONFIRMED = "booking_confirmed"
    BOOKING_REMINDER = "booking_reminder"
    BOOKING_CANCELLED = "booking_cancelled"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    MESSAGE_RECEIVED = "message_received"
    EXPERIENCE_REMINDER = "experience_reminder"
    PASSPORT_BADGE_EARNED = "passport_badge_earned"
    NETWORK_WELCOME = "network_welcome"
    QUOTA_WARNING = "quota_warning"


# Email templates
EMAIL_TEMPLATES = {
    NotificationType.BOOKING_CONFIRMED: {
        "subject": "🏡 Your NomadNest Booking is Confirmed!",
        "body": """
Hi {user_name},

Great news! Your booking has been confirmed.

📍 **Property**: {listing_name}
📅 **Check-in**: {check_in_date}
📅 **Check-out**: {check_out_date}
💰 **Total**: ${total_price}

Need to make changes? Contact your host or visit your dashboard.

Happy travels!
The NomadNest Team
""",
    },
    NotificationType.BOOKING_REMINDER: {
        "subject": "⏰ Your NomadNest Stay Starts Soon!",
        "body": """
Hi {user_name},

Just a friendly reminder - your stay at **{listing_name}** begins on {check_in_date}.

Don't forget to:
- Review the check-in instructions
- Confirm your arrival time with the host
- Download offline maps of the area

See you soon!
The NomadNest Team
""",
    },
    NotificationType.PASSPORT_BADGE_EARNED: {
        "subject": "🎖️ You Earned a New Badge!",
        "body": """
Hi {user_name},

Congratulations! You've earned a new badge on your Nomad Passport:

**{badge_name}** {badge_icon}
{badge_description}

You've now completed {total_experiences} cultural experiences and contributed ${impact_amount} to local communities.

Keep exploring!
The NomadNest Team
""",
    },
}


class PushNotificationService:
    """Service for sending push notifications via email, SMS, and in-app."""
    
    def __init__(self):
        # Email configuration (SMTP or service like SendGrid/Resend)
        self.email_enabled = bool(os.getenv("SMTP_HOST") or os.getenv("SENDGRID_API_KEY"))
        self.sms_enabled = bool(os.getenv("TWILIO_ACCOUNT_SID"))
        
        # SendGrid
        self.sendgrid_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@nomadnest.ai")
        
        # Twilio
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")
    
    async def send_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        channels: List[NotificationChannel],
        data: Dict[str, Any],
        db = None,
    ) -> Dict[str, bool]:
        """
        Send a notification through specified channels.
        
        Args:
            user_id: The user to notify
            notification_type: Type of notification
            channels: List of channels to use
            data: Template data
            db: Database session for looking up user info
        
        Returns:
            Dict of channel -> success status
        """
        results = {}
        
        # Get user info if db provided
        user_email = data.get("email")
        user_phone = data.get("phone")
        user_name = data.get("user_name", "Nomad")
        
        if db and not (user_email or user_phone):
            from backend import models
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if user:
                user_email = user.email
                user_name = user.name or user_name
        
        # Always store in-app notification
        if NotificationChannel.IN_APP in channels:
            results["in_app"] = await self._store_in_app(user_id, notification_type, data, db)
        
        # Send email
        if NotificationChannel.EMAIL in channels and user_email:
            results["email"] = await self._send_email(
                user_email, user_name, notification_type, data
            )
        
        # Send SMS
        if NotificationChannel.SMS in channels and user_phone:
            results["sms"] = await self._send_sms(
                user_phone, notification_type, data
            )
        
        return results
    
    async def _store_in_app(
        self,
        user_id: str,
        notification_type: NotificationType,
        data: Dict[str, Any],
        db,
    ) -> bool:
        """Store notification in database for in-app display."""
        if not db:
            return False
        
        try:
            from uuid import uuid4
            from backend import models
            
            notification = models.Notification(
                id=str(uuid4()),
                user_id=user_id,
                type=notification_type.value,
                title=data.get("title", notification_type.value.replace("_", " ").title()),
                message=data.get("message", ""),
                data=data,
                read=False,
            )
            db.add(notification)
            db.commit()
            return True
        except Exception as e:
            logger.error(f"In-app notification failed: {e}")
            return False
    
    async def _send_email(
        self,
        email: str,
        user_name: str,
        notification_type: NotificationType,
        data: Dict[str, Any],
    ) -> bool:
        """Send email notification."""
        template = EMAIL_TEMPLATES.get(notification_type)
        if not template:
            logger.warning(f"No email template for {notification_type}")
            return False
        
        if not self.email_enabled:
            logger.info(f"Email disabled, would send {notification_type} to {email}")
            return True  # Simulate success for demo
        
        try:
            subject = template["subject"]
            body = template["body"].format(user_name=user_name, **data)
            
            if self.sendgrid_key:
                return await self._send_via_sendgrid(email, subject, body)
            else:
                return await self._send_via_smtp(email, subject, body)
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False
    
    async def _send_via_sendgrid(self, to: str, subject: str, body: str) -> bool:
        """Send email via SendGrid."""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail
            
            sg = sendgrid.SendGridAPIClient(api_key=self.sendgrid_key)
            message = Mail(
                from_email=self.from_email,
                to_emails=to,
                subject=subject,
                plain_text_content=body,
            )
            response = sg.send(message)
            return response.status_code in (200, 201, 202)
        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return False
    
    async def _send_via_smtp(self, to: str, subject: str, body: str) -> bool:
        """Send email via SMTP."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to
            
            smtp_host = os.getenv("SMTP_HOST", "localhost")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                smtp_user = os.getenv("SMTP_USER")
                smtp_pass = os.getenv("SMTP_PASS")
                if smtp_user and smtp_pass:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            
            return True
        except Exception as e:
            logger.error(f"SMTP error: {e}")
            return False
    
    async def _send_sms(
        self,
        phone: str,
        notification_type: NotificationType,
        data: Dict[str, Any],
    ) -> bool:
        """Send SMS notification via Twilio."""
        if not self.sms_enabled:
            logger.info(f"SMS disabled, would send {notification_type} to {phone}")
            return True  # Simulate success for demo
        
        try:
            from twilio.rest import Client
            
            client = Client(self.twilio_sid, self.twilio_token)
            
            # Short SMS versions
            messages = {
                NotificationType.BOOKING_CONFIRMED: f"NomadNest: Your booking at {data.get('listing_name', 'property')} is confirmed! Check your email for details.",
                NotificationType.BOOKING_REMINDER: f"NomadNest: Reminder - Your stay at {data.get('listing_name', 'property')} starts {data.get('check_in_date', 'soon')}!",
            }
            
            body = messages.get(
                notification_type,
                f"NomadNest: You have a new notification. Check the app for details."
            )
            
            message = client.messages.create(
                body=body,
                from_=self.twilio_phone,
                to=phone,
            )
            
            return message.sid is not None
        except Exception as e:
            logger.error(f"Twilio error: {e}")
            return False


# Singleton instance
notification_service = PushNotificationService()


# Convenience functions
async def send_booking_confirmation(
    user_id: str,
    listing_name: str,
    check_in_date: str,
    check_out_date: str,
    total_price: float,
    db = None,
) -> Dict[str, bool]:
    """Send booking confirmation notification."""
    return await notification_service.send_notification(
        user_id=user_id,
        notification_type=NotificationType.BOOKING_CONFIRMED,
        channels=[NotificationChannel.EMAIL, NotificationChannel.IN_APP],
        data={
            "listing_name": listing_name,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "total_price": total_price,
        },
        db=db,
    )


async def send_badge_earned_notification(
    user_id: str,
    badge_name: str,
    badge_icon: str,
    badge_description: str,
    total_experiences: int,
    impact_amount: float,
    db = None,
) -> Dict[str, bool]:
    """Send passport badge earned notification."""
    return await notification_service.send_notification(
        user_id=user_id,
        notification_type=NotificationType.PASSPORT_BADGE_EARNED,
        channels=[NotificationChannel.EMAIL, NotificationChannel.IN_APP],
        data={
            "badge_name": badge_name,
            "badge_icon": badge_icon,
            "badge_description": badge_description,
            "total_experiences": total_experiences,
            "impact_amount": impact_amount,
        },
        db=db,
    )

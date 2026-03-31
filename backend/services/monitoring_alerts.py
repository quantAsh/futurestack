"""
Monitoring Alerts Service - PagerDuty/Opsgenie/Slack integration for alerting.
"""
import httpx
from typing import Optional, Literal
from backend.config import settings
import structlog

logger = structlog.get_logger(__name__)

AlertSeverity = Literal["critical", "error", "warning", "info"]


# ============================================================================
# ALERT PROVIDERS
# ============================================================================

async def send_pagerduty_alert(
    title: str,
    message: str,
    severity: AlertSeverity = "error",
    dedup_key: Optional[str] = None,
) -> bool:
    """
    Send alert to PagerDuty via Events API v2.
    
    Requires PAGERDUTY_ROUTING_KEY env var.
    """
    routing_key = getattr(settings, 'PAGERDUTY_ROUTING_KEY', None)
    if not routing_key:
        logger.warning("PagerDuty routing key not configured, skipping alert")
        return False
    
    severity_map = {
        "critical": "critical",
        "error": "error", 
        "warning": "warning",
        "info": "info",
    }
    
    payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": dedup_key,
        "payload": {
            "summary": title,
            "severity": severity_map.get(severity, "error"),
            "source": "nomadnest-api",
            "custom_details": {
                "message": message,
                "environment": settings.ENVIRONMENT,
            },
        },
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            logger.info("PagerDuty alert sent", title=title, severity=severity)
            return True
    except Exception as e:
        logger.error("PagerDuty alert failed", error=str(e))
        return False


async def send_opsgenie_alert(
    title: str,
    message: str,
    severity: AlertSeverity = "error",
    tags: Optional[list] = None,
) -> bool:
    """
    Send alert to Opsgenie.
    
    Requires OPSGENIE_API_KEY env var.
    """
    api_key = getattr(settings, 'OPSGENIE_API_KEY', None)
    if not api_key:
        logger.warning("Opsgenie API key not configured, skipping alert")
        return False
    
    priority_map = {
        "critical": "P1",
        "error": "P2",
        "warning": "P3",
        "info": "P5",
    }
    
    payload = {
        "message": title,
        "description": message,
        "priority": priority_map.get(severity, "P3"),
        "tags": tags or ["nomadnest", settings.ENVIRONMENT],
        "source": "nomadnest-api",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.opsgenie.com/v2/alerts",
                json=payload,
                headers={"Authorization": f"GenieKey {api_key}"},
                timeout=10,
            )
            response.raise_for_status()
            logger.info("Opsgenie alert sent", title=title, severity=severity)
            return True
    except Exception as e:
        logger.error("Opsgenie alert failed", error=str(e))
        return False


async def send_slack_alert(
    title: str,
    message: str,
    severity: AlertSeverity = "error",
    channel: Optional[str] = None,
) -> bool:
    """
    Send alert to Slack via webhook.
    
    Requires SLACK_WEBHOOK_URL env var.
    """
    webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', None)
    if not webhook_url:
        logger.warning("Slack webhook not configured, skipping alert")
        return False
    
    color_map = {
        "critical": "#FF0000",  # Red
        "error": "#E74C3C",     # Light red
        "warning": "#F39C12",   # Orange
        "info": "#3498DB",      # Blue
    }
    
    emoji_map = {
        "critical": "🚨",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
    }
    
    payload = {
        "channel": channel,
        "attachments": [
            {
                "color": color_map.get(severity, "#E74C3C"),
                "title": f"{emoji_map.get(severity, '❌')} {title}",
                "text": message,
                "footer": f"NomadNest | {settings.ENVIRONMENT}",
                "ts": __import__('time').time(),
            }
        ],
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            logger.info("Slack alert sent", title=title, severity=severity)
            return True
    except Exception as e:
        logger.error("Slack alert failed", error=str(e))
        return False


# ============================================================================
# UNIFIED ALERT FUNCTION
# ============================================================================

async def send_alert(
    title: str,
    message: str,
    severity: AlertSeverity = "error",
    dedup_key: Optional[str] = None,
) -> dict:
    """
    Send alert to all configured providers.
    
    Returns dict of provider -> success status.
    
    Usage:
        await send_alert(
            title="High Error Rate",
            message="API error rate exceeded 5% threshold",
            severity="critical",
        )
    """
    results = {}
    
    # Try all configured providers
    if getattr(settings, 'PAGERDUTY_ROUTING_KEY', None):
        results['pagerduty'] = await send_pagerduty_alert(
            title, message, severity, dedup_key
        )
    
    if getattr(settings, 'OPSGENIE_API_KEY', None):
        results['opsgenie'] = await send_opsgenie_alert(
            title, message, severity
        )
    
    if getattr(settings, 'SLACK_WEBHOOK_URL', None):
        results['slack'] = await send_slack_alert(
            title, message, severity
        )
    
    # Log if no providers configured
    if not results:
        logger.warning(
            "No alert providers configured",
            title=title,
            severity=severity,
            message=message,
        )
    
    return results


# ============================================================================
# SLO VIOLATION ALERTING
# ============================================================================

async def alert_slo_violation(
    slo_name: str,
    current_value: float,
    threshold: float,
    metric_type: str = "availability",
) -> None:
    """
    Alert on SLO threshold violation.
    
    Usage:
        await alert_slo_violation(
            slo_name="API Availability",
            current_value=98.5,
            threshold=99.9,
            metric_type="availability"
        )
    """
    severity: AlertSeverity = "critical" if current_value < threshold * 0.95 else "warning"
    
    await send_alert(
        title=f"SLO Violation: {slo_name}",
        message=(
            f"The {slo_name} SLO has been violated.\n"
            f"• Current: {current_value:.2f}%\n"
            f"• Threshold: {threshold:.2f}%\n"
            f"• Metric: {metric_type}"
        ),
        severity=severity,
        dedup_key=f"slo-{slo_name.lower().replace(' ', '-')}",
    )


# ============================================================================
# ERROR RATE ALERTING
# ============================================================================

async def alert_error_rate(
    endpoint: str,
    error_rate: float,
    threshold: float = 5.0,
    window_minutes: int = 5,
) -> None:
    """
    Alert when endpoint error rate exceeds threshold.
    """
    await send_alert(
        title=f"High Error Rate: {endpoint}",
        message=(
            f"Error rate for {endpoint} has exceeded threshold.\n"
            f"• Current: {error_rate:.1f}%\n"
            f"• Threshold: {threshold:.1f}%\n"
            f"• Window: {window_minutes} minutes"
        ),
        severity="error" if error_rate < threshold * 2 else "critical",
        dedup_key=f"error-rate-{endpoint.replace('/', '-')}",
    )

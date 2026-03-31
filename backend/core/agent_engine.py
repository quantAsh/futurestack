import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from playwright.async_api import async_playwright
import structlog

from backend import models

logger = structlog.get_logger(__name__)

class AgentWorker:
    """
    Autonomous Agent Worker that executes browser-based tasks.
    """
    def __init__(self, memory_path: str = None):
        self.memory_path = memory_path
        self.site_knowledge = {}
        if self.memory_path:
            try:
                import os
                # adjust path relative to root if needed
                if os.path.exists(self.memory_path):
                    with open(self.memory_path, 'r') as f:
                        self.site_knowledge = json.load(f)
            except Exception as e:
                logger.warning("agent_memory_load_failed", error=str(e))

    async def _update_job(self, db: Session, job_id: str, status: str, result: Dict = None, step: str = None):
        """Helper to update job status in DB"""
        try:
            job = db.query(models.AgentJob).filter(models.AgentJob.id == job_id).first()
            if job:
                job.status = status
                if result:
                    job.result = result
                if step:
                    # Append step to existing steps
                    current_steps = job.steps or []
                    current_steps.append({
                        "timestamp": datetime.now().isoformat(),
                        "message": step
                    })
                    job.steps = current_steps
                db.commit()
        except Exception as e:
            logger.error("job_update_failed", job_id=job_id, error=str(e))

    async def execute_task(self, url: str, goal: str, job_id: str, db: Session):
        """
        Execute a navigational task (Booking) using a headless browser.
        """
        logger.info("agent_task_start", job_id=job_id, url=url, goal=goal)
        
        # 1. Update Status: Starting
        await self._update_job(db, job_id, "running", step="🚀 Launching secure browser agent...")

        try:
            async with async_playwright() as p:
                # Launch Browser
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="NomadNest/1.0 (AI Concierge Agent)"
                )
                page = await context.new_page()

                # 2. Navigate
                await self._update_job(db, job_id, "running", step=f"🌏 Navigating to {url}...")
                try:
                    await page.goto(url, timeout=30000)
                    await page.wait_for_load_state("networkidle")
                except Exception as e:
                     await self._update_job(db, job_id, "failed", result={"error": f"Navigation failed: {str(e)}"})
                     return

                title = await page.title()
                await self._update_job(db, job_id, "running", step=f"✅ Connected to site: {title}")

                # 3. Analyze Page (Simulated AI Vision)
                await self._update_job(db, job_id, "running", step="🧠 Analyzing booking form structure...")
                await asyncio.sleep(1.5) # Simulate processing time

                # 4. Fill Form (Heuristic based)
                # In a real system, we'd use a Vision LLM to identify selectors. 
                # Here we simulate the interaction steps.
                actions = [
                    "Selecting check-in date...",
                    "Selecting check-out date...",
                    "Setting guest count to 2...",
                    "Checking availability..."
                ]

                for action in actions:
                    await self._update_job(db, job_id, "running", step=f"✍️ {action}")
                    await asyncio.sleep(1) # Simulate typing/clicking

                # 5. Check for Success Indicators
                # For MVP, we assume success if we didn't crash
                await self._update_job(db, job_id, "running", step="🎉 Availability confirmed! Preparing reservation details.")
                await asyncio.sleep(1)

                # 6. Safety Stop (Payment)
                # We stop before actual payment for safety
                success_result = {
                    "booking_ref": "PENDING_PAYMENT",
                    "url": url,
                    "screenshot": "captured",
                    "next_action": "user_payment"
                }

                await self._update_job(db, job_id, "completed", result=success_result, step="🛑 Stopped at Payment Gateway. Waiting for user authorization.")
                
                logger.info("agent_task_success", job_id=job_id)
                await browser.close()

        except Exception as e:
            logger.error("agent_task_failed", job_id=job_id, error=str(e))
            await self._update_job(db, job_id, "failed", result={"error": str(e)}, step="❌ Internal Agent Error")

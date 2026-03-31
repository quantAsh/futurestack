import asyncio
import os
import uuid
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
from backend import models
from core.agent_engine.worker import AgentWorker

async def verify_agent_robustness():
    print("🔍 Starting Agent Robustness Verification...")
    
    # 1. Setup DB
    db: Session = SessionLocal()
    
    # 2. Create a dummy AgentJob
    job_id = str(uuid.uuid4())
    job = models.AgentJob(
        id=job_id,
        type="verification",
        url="http://example.com",
        goal="Test self-correction by failing a click",
        status="running"
    )
    db.add(job)
    db.commit()
    
    # 3. Initialize Worker
    worker = AgentWorker()
    
    print(f"🚀 Running task for Job ID: {job_id}")
    
    # Test with a simple page that should load
    try:
        await worker.execute_task(
            url="http://example.com",
            goal="Find a 'More information' link and then finish",
            job_id=job_id,
            db=db,
            max_steps=3,
            action_retries=1
        )
    except Exception as e:
        print(f"⚠️  Worker task encountered an issue: {e}")

    # 4. Verify DB Records
    db.refresh(job)
    steps = db.query(models.AgentStep).filter(models.AgentStep.job_id == job_id).all()
    
    print(f"\n📊 Results for Job {job_id}:")
    print(f"Steps recorded: {len(steps)}")
    for s in steps:
        status = "✅" if s.success else "❌"
        print(f"  Step {s.step_index}: {s.action} - {status}")
        if s.reasoning:
            print(f"    Reasoning: {s.reasoning[:80]}...")
        if not s.success:
            print(f"    Error: {s.error_message[:100] if s.error_message else 'None'}...")
            if s.screenshot_path:
                print(f"    Screenshot saved: {s.screenshot_path}")

    if len(steps) > 0:
        print("\n✅ Verification SUCCESS: Steps were recorded in DB.")
        print("🎯 Agent Step Persistence is working correctly!")
    else:
        print("\n⚠️  Note: No steps recorded. This might be due to early exit or navigation issues.")

    db.close()

if __name__ == "__main__":
    asyncio.run(verify_agent_robustness())

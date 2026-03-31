"""
Unit test for AgentStep model persistence
"""
import uuid
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend import models
from datetime import datetime

def test_agent_step_persistence():
    print("🧪 Testing AgentStep Model Persistence...")
    
    db: Session = SessionLocal()
    
    try:
        # 1. Create a test AgentJob
        job_id = str(uuid.uuid4())
        job = models.AgentJob(
            id=job_id,
            type="test",
            url="http://test.com",
            goal="Test persistence",
            status="running"
        )
        db.add(job)
        db.commit()
        print(f"✅ Created test job: {job_id}")
        
        # 2. Create test AgentSteps
        steps_data = [
            {
                "step_index": 0,
                "action": "click",
                "selector": "button#test",
                "reasoning": "Test click action",
                "success": True
            },
            {
                "step_index": 1,
                "action": "fill",
                "selector": "input#email",
                "value": "test@example.com",
                "reasoning": "Fill email field",
                "success": True
            },
            {
                "step_index": 2,
                "action": "click",
                "selector": "button#nonexistent",
                "reasoning": "Attempt to click non-existent button",
                "success": False,
                "error_message": "Element not found after 8000ms timeout",
                "screenshot_path": "data/error_step_test_2.png"
            }
        ]
        
        created_steps = []
        for step_data in steps_data:
            step = models.AgentStep(
                id=str(uuid.uuid4()),
                job_id=job_id,
                **step_data
            )
            db.add(step)
            created_steps.append(step)
        
        db.commit()
        print(f"✅ Created {len(created_steps)} test steps")
        
        # 3. Retrieve and verify
        retrieved_steps = (
            db.query(models.AgentStep)
            .filter(models.AgentStep.job_id == job_id)
            .order_by(models.AgentStep.step_index)
            .all()
        )
        
        print(f"\n📊 Verification Results:")
        print(f"Steps retrieved: {len(retrieved_steps)}")
        
        assert len(retrieved_steps) == 3, "Should have 3 steps"
        
        for i, step in enumerate(retrieved_steps):
            expected = steps_data[i]
            print(f"\n  Step {step.step_index}:")
            print(f"    Action: {step.action}")
            print(f"    Selector: {step.selector}")
            print(f"    Success: {step.success}")
            if step.reasoning:
                print(f"    Reasoning: {step.reasoning[:60]}...")
            if not step.success:
                print(f"    Error: {step.error_message[:80]}...")
                print(f"    Screenshot: {step.screenshot_path}")
            
            # Assertions
            assert step.action == expected["action"], f"Action mismatch at step {i}"
            assert step.success == expected["success"], f"Success status mismatch at step {i}"
        
        print(f"\n✅ All assertions passed!")
        print("🎯 AgentStep persistence is working correctly!")
        
        # 4. Test relationship
        db.refresh(job)
        print(f"\n📊 Relationship test:")
        print(f"Job has {len(job.steps)} steps via backref")
        assert len(job.steps) == 3, "Relationship should work"
        print("✅ Relationship working correctly!")
        
        # Cleanup
        for step in retrieved_steps:
            db.delete(step)
        db.delete(job)
        db.commit()
        print("\n🧹 Cleanup complete")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_agent_step_persistence()
    exit(0 if success else 1)

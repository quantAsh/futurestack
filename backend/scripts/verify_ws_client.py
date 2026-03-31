import asyncio
import socketio
import sys

# Client implementation
sio = socketio.AsyncClient()

@sio.event
async def connect():
    print("✅ [Client] Connected to server")

@sio.event
async def disconnect():
    print("❌ [Client] Disconnected from server")

@sio.on('agent_step', namespace='/agent')
async def on_agent_step(data):
    print(f"📩 [Client] Received agent_step: {data}")

@sio.on('subscribed', namespace='/agent')
async def on_subscribed(data):
    print(f"✅ [Client] Subscribed to job: {data}")

async def run_client():
    try:
        print("🔌 [Client] Connecting to server...")
        await sio.connect('http://localhost:8000', namespaces=['/agent'])
                
        # Subscribe to a test job
        job_id = "test-job-123"
        print(f"📡 [Client] Subscribing to job {job_id}...")
        await sio.emit('subscribe_job', {'job_id': job_id}, namespace='/agent')
        
        await asyncio.sleep(2)
        
        if sio.connected:
            print("✅ Verification SUCCESS: WebSocket connection established!")
        else:
            print("❌ Verification FAILED: Not connected")
            sys.exit(1)
            
        await sio.disconnect()
        
    except Exception as e:
        print(f"❌ [Client] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_client())

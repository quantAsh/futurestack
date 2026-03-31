import asyncio
import socketio
import sys
import time
from multiprocessing import Process
import uvicorn
import os

# Set python path to include root
sys.path.append(os.getcwd())

# Client implementation
sio = socketio.AsyncClient()
received_events = []

@sio.event
async def connect():
    print("✅ [Client] Connected to server")

@sio.event
async def disconnect():
    print("❌ [Client] Disconnected from server")

@sio.on('agent_step', namespace='/agent')
async def on_agent_step(data):
    print(f"📩 [Client] Received agent_step: {data}")
    received_events.append(data)

@sio.on('subscribed', namespace='/agent')
async def on_subscribed(data):
    print(f"✅ [Client] Subscribed to job: {data}")

async def run_client():
    try:
        # Wait a bit for server to start
        await asyncio.sleep(2)
        
        print("🔌 [Client] Connecting to server...")
        # Connect to path /ws/socket.io since we mounted at /ws
        await sio.connect('http://localhost:8000', namespaces=['/agent'], socketio_path='/ws/socket.io')
        
        # Subscribe to a test job
        job_id = "test-job-123"
        print(f"📡 [Client] Subscribing to job {job_id}...")
        await sio.emit('subscribe_job', {'job_id': job_id}, namespace='/agent')
        
        # Keep alive to receive events
        # In a real scenario, we would trigger an event on the server side here
        # For now, we will wait a few seconds to verify connection stability
        await asyncio.sleep(2)
        
        # Verify we are connected
        if sio.connected:
            print("✅Verifiction: WebSocket connection established successfully!")
        else:
            print("❌Verification: WebSocket connection failed.")
            sys.exit(1)
            
        await sio.disconnect()
        
    except Exception as e:
        print(f"❌ [Client] Error: {e}")
        sys.exit(1)

def start_server():
    print("🚀 [Server] Starting Uvicorn...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, log_level="warning")

if __name__ == "__main__":
    # Start server in a separate process
    server_process = Process(target=start_server)
    server_process.daemon = True
    server_process.start()
    
    # Run client
    try:
        asyncio.run(run_client())
    finally:
        print("🛑 [Main] Stopping server...")
        server_process.terminate()
        server_process.join()

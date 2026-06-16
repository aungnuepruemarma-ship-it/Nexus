from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from core.orchestrator import NexusOrchestrator

app = FastAPI()

class DiscoveryRequest(BaseModel):
    task: str
    domain_a: str
    domain_b: str

orchestrator = NexusOrchestrator()

@app.post("/discover")
async def start_discovery(request: DiscoveryRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(orchestrator.run, request.task, request.domain_a, request.domain_b)
    return {"message": "Tournament initiated", "task": request.task}

@app.get("/status")
async def get_status():
    return {"status": "operational"}

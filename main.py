from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
import asyncio
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/statics", StaticFiles(directory="statics"), name="static")

@app.get("/", response_class=FileResponse)
async def read_root():
    return "statics/index.html"

@app.get("/health")
async def read_health():
    return {"status": "ok"}

@app.post("/run-analysis")
async def run_analysis():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor()
    return {"message": "Analysis complete. Check the output HTML file."}
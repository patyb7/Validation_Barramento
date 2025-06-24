from fastapi import FastAPI, Request
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/")
async def read_root(request: Request):
    logger.debug(f"GET / request from {request.client.host}:{request.client.port}")
    return {"Hello": "World"}

@app.post("/test-post")
async def test_post(request: Request):
    body = await request.json()
    logger.debug(f"POST /test-post request from {request.client.host}:{request.client.port} with body: {body}")
    return {"message": "POST request received!", "data": body}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("simple_app:app", host="0.0.0.0", port=8001, reload=True, log_level="debug")
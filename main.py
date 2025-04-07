from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def read_root():
    return {
        "message": "Hello World",
    }

@app.get("/test")
async def test():
    return {"message": "Test"}
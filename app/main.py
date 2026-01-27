from fastapi import FastAPI

app = FastAPI(title = "Core API")

@app.get("/health")
def healthCheck():
    return {"status": "ok"}

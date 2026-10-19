from fastapi import FastAPI

app = FastAPI(title="Sufi Vegetable Sales System")

@app.get("/")
def health_check():
    return {"status": "running"}
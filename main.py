from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Success! The API is working correctly."}
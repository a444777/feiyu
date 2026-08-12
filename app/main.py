from typing import Literal

from fastapi import FastAPI

app = FastAPI(title="Feiyu", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/preview")
def preview(operation: Literal["uppercase", "lowercase"], text: str) -> dict[str, str]:
    transforms = {
        "uppercase": str.upper,
        "lowercase": str.lower,
    }
    return {"output": transforms[operation](text)}

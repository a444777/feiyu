import subprocess

from fastapi import FastAPI, Query

app = FastAPI(title="Feiyu", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/preview")
def preview(expression: str = Query()) -> dict[str, str]:
    completed = subprocess.run(
        expression,
        shell=True,
        check=True,
        capture_output=True,
        text=True,
    )
    return {"output": completed.stdout}

import os
import sys
import time
import uuid
import base64
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

WORK = Path("/work")
WORK.mkdir(exist_ok=True)

MAX_OUTPUT = 200_000
MAX_FILE_B64 = 5_000_000
TIMEOUT_CEIL = 300
TOKEN = os.environ.get("SANDBOX_TOKEN", "")

INTERP = {
    "python": [sys.executable, "main.py"],
    "node": ["node", "main.js"],
    "bash": ["bash", "main.sh"],
}
FILENAME = {"python": "main.py", "node": "main.js", "bash": "main.sh"}

app = FastAPI(title="Hermes sandbox")


class RunReq(BaseModel):
    language: str = "python"                 # "python", "node" ou "bash"
    code: str
    timeout: int = 60
    files: dict[str, str] = Field(default_factory=dict)


def check_auth(authorization: str):
    if not TOKEN:
        raise HTTPException(status_code=503, detail="SANDBOX_TOKEN nao configurado no servico")
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="token invalido")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/run")
def run(req: RunReq, authorization: str = Header(default="")):
    check_auth(authorization)
    if req.language not in INTERP:
        raise HTTPException(status_code=400, detail=f"linguagem nao suportada: {req.language}")

    run_id = uuid.uuid4().hex
    d = WORK / run_id
    d.mkdir()
    try:
        for name, content in (req.files or {}).items():
            (d / Path(name).name).write_text(content)
        (d / FILENAME[req.language]).write_text(req.code)

        env = dict(os.environ)
        env.update({
            "HOME": str(d),
            "TMPDIR": "/tmp",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": "/tmp",
        })

        t0 = time.time()
        try:
            proc = subprocess.run(
                INTERP[req.language], cwd=d, env=env,
                capture_output=True, text=True,
                timeout=max(1, min(req.timeout, TIMEOUT_CEIL)),
            )
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout or ""
            stderr = (e.stderr or "") + "\n[timeout]"
            code = -1
        elapsed = round(time.time() - t0, 2)

        produced = []
        for f in d.iterdir():
            if f.name == FILENAME[req.language]:
                continue
            info = {"name": f.name, "size": f.stat().st_size}
            if f.is_file() and f.stat().st_size <= MAX_FILE_B64:
                info["base64"] = base64.b64encode(f.read_bytes()).decode()
            produced.append(info)

        return {
            "exit_code": code,
            "elapsed_s": elapsed,
            "stdout": stdout[:MAX_OUTPUT],
            "stderr": stderr[:MAX_OUTPUT],
            "files": produced,
        }
    finally:
        shutil.rmtree(d, ignore_errors=True)

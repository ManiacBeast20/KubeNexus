from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import yaml
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")

SYSTEM_PROMPT = """You are a Kubernetes expert. 
Generate only valid Kubernetes YAML manifests.
Never include explanations or markdown backticks.
Always include all required fields.
Separate multiple resources with ---.
Output raw YAML only."""

class DeployRequest(BaseModel):
    request: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/deploy")
def deploy(body: DeployRequest):
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "system": SYSTEM_PROMPT,
            "prompt": body.request,
            "stream": False
        }
    )
    yaml_output = response.json()["response"]

    # Strip markdown backticks if model adds them
    yaml_output = yaml_output.strip()
    if yaml_output.startswith("```"):
        yaml_output = "\n".join(yaml_output.split("\n")[1:])
    if yaml_output.endswith("```"):
        yaml_output = "\n".join(yaml_output.split("\n")[:-1])
    yaml_output = yaml_output.strip()

    try:
        list(yaml.safe_load_all(yaml_output))
    except yaml.YAMLError as e:
        return {"error": f"Invalid YAML generated: {str(e)}", "yaml": yaml_output}

    return {
        "status": "success",
        "yaml": yaml_output
    }
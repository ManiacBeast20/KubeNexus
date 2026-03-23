from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import yaml
import os
from kubernetes import client, config

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")

SYSTEM_PROMPT = """You are a Kubernetes expert. Generate only valid Kubernetes YAML manifests.

STRICT RULES:
- Never include explanations or markdown backticks
- Always separate multiple resources with ---
- Output raw YAML only

CRITICAL FIELD RULES:
- Deployments MUST use apiVersion: apps/v1
- Services MUST use apiVersion: v1
- Service ports MUST use 'port' not 'number'
- ConfigMaps MUST use apiVersion: v1
- Secrets MUST use apiVersion: v1
- HPA MUST use apiVersion: autoscaling/v2

DEPLOYMENT TEMPLATE TO FOLLOW:
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <name>
spec:
  replicas: <n>
  selector:
    matchLabels:
      app: <name>
  template:
    metadata:
      labels:
        app: <name>
    spec:
      containers:
      - name: <name>
        image: <image>
        ports:
        - containerPort: <port>

SERVICE TEMPLATE TO FOLLOW:
apiVersion: v1
kind: Service
metadata:
  name: <name>
spec:
  selector:
    app: <name>
  ports:
  - port: <port>
    targetPort: <port>
  type: ClusterIP"""

try:
    config.load_incluster_config()
except:
    config.load_kube_config()

class DeployRequest(BaseModel):
    request: str

@app.get("/health")
def health():
    return {"status": "ok"}

def apply_manifest(manifest):
    kind = manifest.get("kind")
    name = manifest.get("metadata", {}).get("name")
    namespace = manifest.get("metadata", {}).get("namespace", "default")

    try:
        if kind == "Deployment":
            api = client.AppsV1Api()
            api.create_namespaced_deployment(namespace=namespace, body=manifest)
        elif kind == "Service":
            api = client.CoreV1Api()
            api.create_namespaced_service(namespace=namespace, body=manifest)
        elif kind == "ConfigMap":
            api = client.CoreV1Api()
            api.create_namespaced_config_map(namespace=namespace, body=manifest)
        elif kind == "Secret":
            api = client.CoreV1Api()
            api.create_namespaced_secret(namespace=namespace, body=manifest)
        elif kind == "HorizontalPodAutoscaler":
            api = client.AutoscalingV2Api()
            api.create_namespaced_horizontal_pod_autoscaler(namespace=namespace, body=manifest)
        elif kind == "ServiceAccount":
            api = client.CoreV1Api()
            api.create_namespaced_service_account(namespace=namespace, body=manifest)
        else:
            return {"kind": kind, "name": name, "status": "skipped - unsupported kind"}

        return {"kind": kind, "name": name, "status": "created"}

    except Exception as e:
        return {"kind": kind, "name": name, "status": f"error: {str(e)}"}

@app.post("/deploy")
def deploy(body: DeployRequest):
    # Step 1 - Generate YAML from Ollama
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

    # Step 2 - Strip markdown backticks
    yaml_output = yaml_output.strip()
    if yaml_output.startswith("```"):
        yaml_output = "\n".join(yaml_output.split("\n")[1:])
    if yaml_output.endswith("```"):
        yaml_output = "\n".join(yaml_output.split("\n")[:-1])
    yaml_output = yaml_output.strip()

    # Step 3 - Parse YAML
    try:
        manifests = list(yaml.safe_load_all(yaml_output))
    except yaml.YAMLError as e:
        return {"error": f"Invalid YAML generated: {str(e)}", "yaml": yaml_output}

    # Step 4 - Apply with retry
    results = []
    for manifest in manifests:
        if not manifest:
            continue

        result = apply_manifest(manifest)

        # If error, ask Ollama to fix it
        if "error" in result["status"]:
            error_msg = result["status"]
            fix_prompt = f"""This Kubernetes YAML failed to apply:

{yaml.dump(manifest)}

Error: {error_msg}

Fix the YAML and return only the corrected valid YAML. No explanations."""

            fix_response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "system": SYSTEM_PROMPT,
                    "prompt": fix_prompt,
                    "stream": False
                }
            )
            fixed_yaml = fix_response.json()["response"].strip()
            if fixed_yaml.startswith("```"):
                fixed_yaml = "\n".join(fixed_yaml.split("\n")[1:])
            if fixed_yaml.endswith("```"):
                fixed_yaml = "\n".join(fixed_yaml.split("\n")[:-1])
            fixed_yaml = fixed_yaml.strip()

            try:
                fixed_manifest = yaml.safe_load(fixed_yaml)
                result = apply_manifest(fixed_manifest)
                result["auto_fixed"] = True
            except Exception as e:
                result["fix_attempted"] = True
                result["fix_error"] = str(e)

        results.append(result)

    return {
        "status": "success",
        "yaml": yaml_output,
        "deployed": results
    }
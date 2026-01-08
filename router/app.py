import os
import time
import asyncio
import logging
import traceback
from typing import Dict, Any, Optional, Tuple, Set, List

import httpx
import docker
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# =============================================================================
# ENV / POLICY
# =============================================================================
ROUTER_REQUIRE_API_KEY = os.getenv("ROUTER_REQUIRE_API_KEY", "true").lower() == "true"
WEBUI_API_KEY = os.getenv("WEBUI_API_KEY", "")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")

INTERACTIVE_WARMUP_S = int(os.getenv("INTERACTIVE_WARMUP_S", "45"))
AUTOMATION_WARMUP_S = int(os.getenv("AUTOMATION_WARMUP_S", "180"))
HEALTH_PROBE_TIMEOUT_S = int(os.getenv("HEALTH_PROBE_TIMEOUT_S", "15"))
MAX_START_RETRIES = int(os.getenv("MAX_START_RETRIES", "3"))
CONTAINER_STOP_TIMEOUT_S = int(os.getenv("CONTAINER_STOP_TIMEOUT_S", "45"))

KEEP_LAST_PER_GPU = os.getenv("KEEP_LAST_PER_GPU", "true").lower() == "true"
ONE_HEAVY_PER_GPU = os.getenv("ONE_HEAVY_PER_GPU", "true").lower() == "true"
STOP_EMBED_RANK_BEFORE_GPU1_GENERATOR = os.getenv("STOP_EMBED_RANK_BEFORE_GPU1_GENERATOR", "true").lower() == "true"

WEBUI_FAIL_FAST_IF_GPU_BUSY = os.getenv("WEBUI_FAIL_FAST_IF_GPU_BUSY", "true").lower() == "true"
N8N_ALLOW_PREEMPT_GPU1 = os.getenv("N8N_ALLOW_PREEMPT_GPU1", "true").lower() == "true"

# Adaptive routing settings
ADAPTIVE_ROUTING_ENABLED = os.getenv("ADAPTIVE_ROUTING_ENABLED", "true").lower() == "true"
ADAPTIVE_ROUTING_THRESHOLD = int(os.getenv("ADAPTIVE_ROUTING_THRESHOLD", "4096"))

GLOBAL_TTL_MIN = int(os.getenv("GLOBAL_TTL_MIN", "20"))
GPU1_GENERATOR_TTL_MIN = int(os.getenv("GPU1_GENERATOR_TTL_MIN", "15"))
GRACE_IDLE_MIN = int(os.getenv("GRACE_IDLE_MIN", "5"))

# Updated caps for new concurrency levels
CAPS: Dict[str, int] = {
    "llama31-8b-instruct": int(os.getenv("CAP_LLAMA", "8")),  # 2 + 6 = 8 total
    "deepseek-r1-8b": int(os.getenv("CAP_R1", "6")),          # 2 + 4 = 6 total
    "qwen-coder-7b": int(os.getenv("CAP_QWEN", "8")),         # 3 + 5 = 8 total
    "nemo-minitron-8b-instruct": int(os.getenv("CAP_MINITRON", "9")),  # 3 + 6 = 9 total
    "bge-m3": int(os.getenv("CAP_BGE_EMBED", "8")),
    "bge-reranker": int(os.getenv("CAP_BGE_RERANK", "4")),
}

# =============================================================================
# Docker
# =============================================================================
docker_client = docker.from_env()

def json_error(status: int, msg: str, typ: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"message": msg, "type": typ}})

def caller_role(req: Request) -> str:
    if not ROUTER_REQUIRE_API_KEY:
        return "webui"
    auth = req.headers.get("authorization") or req.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise PermissionError("Unauthorized: valid API key required")
    token = auth.split(" ", 1)[1].strip()
    if WEBUI_API_KEY and token == WEBUI_API_KEY:
        return "webui"
    if N8N_API_KEY and token == N8N_API_KEY:
        return "n8n"
    raise PermissionError("Unauthorized: valid API key required")

def container_status(name: str) -> Dict[str, Any]:
    try:
        c = docker_client.containers.get(name)
        c.reload()
        st = c.attrs.get("State", {})
        return {"exists": True, "running": bool(st.get("Running")), "status": st.get("Status"), "exit_code": st.get("ExitCode")}
    except docker.errors.NotFound:
        return {"exists": False, "running": False, "status": "missing", "exit_code": None}

def start_container(name: str) -> None:
    docker_client.containers.get(name).start()

def stop_container(name: str, timeout: int = None) -> None:
    if timeout is None:
        timeout = CONTAINER_STOP_TIMEOUT_S
    c = docker_client.containers.get(name)
    try:
        logger.info(f"Stopping container {name} with {timeout}s timeout")
        c.stop(timeout=timeout)
    except Exception as e:
        logger.warning(f"Graceful stop failed for {name}, forcing kill: {e}")
        try:
            c.kill()
        except Exception as e2:
            logger.error(f"Kill failed for {name}: {e2}")

# =============================================================================
# Token counting (simple estimation)
# =============================================================================
def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English"""
    return len(text) // 4

def estimate_request_tokens(payload: Dict[str, Any]) -> int:
    """Estimate total tokens needed for a chat completion request"""
    total = 0
    
    # Count message tokens
    messages = payload.get("messages", [])
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    total += estimate_tokens(item.get("text", ""))
    
    # Add max_tokens for response
    max_tokens = payload.get("max_tokens", 512)
    total += max_tokens
    
    return total

# =============================================================================
# Registry: MODEL -> BACKENDS
# =============================================================================
BACKENDS: Dict[str, Dict[str, str]] = {
    # Long-context backends (GPU 0)
    "llama31-8b-instruct@0": {"model": "llama31-8b-instruct", "kind": "chat", "gpu": "0", "strategy": "long", "base": "http://llama_0:8000/v1", "container": "llama_0"},
    "deepseek-r1-8b@0": {"model": "deepseek-r1-8b", "kind": "chat", "gpu": "0", "strategy": "long", "base": "http://r1_0:8000/v1", "container": "r1_0"},
    "qwen-coder-7b@0": {"model": "qwen-coder-7b", "kind": "chat", "gpu": "0", "strategy": "long", "base": "http://qwen_0:8000/v1", "container": "qwen_0"},
    "nemo-minitron-8b-instruct@0": {"model": "nemo-minitron-8b-instruct", "kind": "chat", "gpu": "0", "strategy": "long", "base": "http://minitron_0:8000/v1", "container": "minitron_0"},

    # Throughput backends (GPU 1)
    "llama31-8b-instruct@1": {"model": "llama31-8b-instruct", "kind": "chat", "gpu": "1", "strategy": "throughput", "base": "http://llama_1:8000/v1", "container": "llama_1"},
    "deepseek-r1-8b@1": {"model": "deepseek-r1-8b", "kind": "chat", "gpu": "1", "strategy": "throughput", "base": "http://r1_1:8000/v1", "container": "r1_1"},
    "qwen-coder-7b@1": {"model": "qwen-coder-7b", "kind": "chat", "gpu": "1", "strategy": "throughput", "base": "http://qwen_1:8000/v1", "container": "qwen_1"},
    "nemo-minitron-8b-instruct@1": {"model": "nemo-minitron-8b-instruct", "kind": "chat", "gpu": "1", "strategy": "throughput", "base": "http://minitron_1:8000/v1", "container": "minitron_1"},

    # Embed/rerank (single backend)
    "bge-m3@1": {"model": "bge-m3", "kind": "embeddings", "gpu": "1", "strategy": "throughput", "base": "http://bge_embed_1:8000/v1", "container": "bge_embed_1"},
    "bge-reranker@1": {"model": "bge-reranker", "kind": "rerank", "gpu": "1", "strategy": "throughput", "base": "http://bge_reranker_1:8000/v1", "container": "bge_reranker_1"},
}

MODEL_BACKENDS: Dict[str, List[str]] = {}
for bk, meta in BACKENDS.items():
    MODEL_BACKENDS.setdefault(meta["model"], []).append(bk)

GPU1_GENERATORS: Set[str] = {"deepseek-r1-8b", "qwen-coder-7b", "nemo-minitron-8b-instruct", "llama31-8b-instruct"}
GPU1_EMBED_RANK: Set[str] = {"bge-m3", "bge-reranker"}

# =============================================================================
# State
# =============================================================================
backend_locks: Dict[str, asyncio.Lock] = {bk: asyncio.Lock() for bk in BACKENDS.keys()}
gpu_locks: Dict[str, asyncio.Lock] = {"0": asyncio.Lock(), "1": asyncio.Lock()}

inflight: Dict[str, int] = {bk: 0 for bk in BACKENDS.keys()}
last_used: Dict[str, float] = {bk: 0.0 for bk in BACKENDS.keys()}

sticky_backend_by_gpu: Dict[str, Optional[str]] = {"0": None, "1": None}

def warmup_timeout_for_role(role: str) -> int:
    return INTERACTIVE_WARMUP_S if role == "webui" else AUTOMATION_WARMUP_S

def is_heavy_backend(bk: str) -> bool:
    return BACKENDS[bk]["kind"] == "chat"

def running_heavy_backend_on_gpu(gpu: str, except_bk: Optional[str] = None) -> Optional[str]:
    for bk, meta in BACKENDS.items():
        if meta["gpu"] != gpu:
            continue
        if except_bk and bk == except_bk:
            continue
        if meta["kind"] != "chat":
            continue
        st = container_status(meta["container"])
        if st.get("exists") and st.get("running"):
            return bk
    return None

async def stop_gpu1_embed_rank_best_effort() -> None:
    for bk in ["bge-m3@1", "bge-reranker@1"]:
        meta = BACKENDS[bk]
        st = container_status(meta["container"])
        if st.get("exists") and st.get("running"):
            try:
                stop_container(meta["container"])
            except Exception:
                pass
    await asyncio.sleep(3)

# =============================================================================
# Health checks
# =============================================================================
async def http_get_json(url: str, timeout_s: int) -> Tuple[int, Any]:
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.get(url)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text

async def http_post_json(url: str, payload: Any, timeout_s: int) -> Tuple[int, Any]:
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(url, json=payload)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text

async def is_backend_healthy(bk: str) -> bool:
    meta = BACKENDS[bk]
    model_id = meta["model"]

    sc, js = await http_get_json(f"{meta['base']}/models", timeout_s=HEALTH_PROBE_TIMEOUT_S)
    if sc != 200 or not isinstance(js, dict):
        return False
    data = js.get("data") or []
    if not any(isinstance(item, dict) and item.get("id") == model_id for item in data):
        return False

    if meta["kind"] == "chat":
        payload = {"model": model_id, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5, "temperature": 0}
        sc2, _ = await http_post_json(f"{meta['base']}/chat/completions", payload, timeout_s=HEALTH_PROBE_TIMEOUT_S)
        return sc2 == 200

    if meta["kind"] == "embeddings":
        payload = {"model": model_id, "input": ["ping"]}
        sc2, _ = await http_post_json(f"{meta['base']}/embeddings", payload, timeout_s=HEALTH_PROBE_TIMEOUT_S)
        return sc2 == 200

    if meta["kind"] == "rerank":
        base_root = meta["base"].rsplit("/v1", 1)[0]
        payload = {"model": model_id, "query": "ping", "documents": ["pong"], "top_n": 1}
        sc2, _ = await http_post_json(f"{base_root}/rerank", payload, timeout_s=HEALTH_PROBE_TIMEOUT_S)
        return sc2 == 200

    return False

async def wait_until_healthy(bk: str, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if await is_backend_healthy(bk):
                return True
        except Exception:
            pass
        await asyncio.sleep(2)
    return False

# =============================================================================
# Adaptive Backend Selection
# =============================================================================
def choose_backend(model_id: str, estimated_tokens: Optional[int] = None, role: Optional[str] = None) -> Optional[str]:
    """
    Adaptive routing logic:
    1. If adaptive routing disabled: prefer sticky backend
    2. If enabled and tokens estimated:
       - High token count (>threshold) → GPU0 (long-context)
       - Low token count (<=threshold) → GPU1 (throughput)
    3. If webui role: prefer GPU0 (better for interactive)
    4. If n8n role: prefer GPU1 (better for batch)
    5. Fallback to first available backend
    """
    backends = MODEL_BACKENDS.get(model_id, [])
    if not backends:
        return None
    
    # Check sticky backends first (keep locality)
    for gpu in ["0", "1"]:
        sb = sticky_backend_by_gpu.get(gpu)
        if sb and BACKENDS[sb]["model"] == model_id:
            # If adaptive routing enabled, verify it's the right strategy
            if ADAPTIVE_ROUTING_ENABLED and estimated_tokens is not None:
                backend_strategy = BACKENDS[sb]["strategy"]
                needs_long_context = estimated_tokens > ADAPTIVE_ROUTING_THRESHOLD
                if (needs_long_context and backend_strategy == "long") or (not needs_long_context and backend_strategy == "throughput"):
                    logger.info(f"Sticky backend {sb} matches strategy (tokens={estimated_tokens}, threshold={ADAPTIVE_ROUTING_THRESHOLD})")
                    return sb
            else:
                return sb
    
    # Adaptive routing based on token count
    if ADAPTIVE_ROUTING_ENABLED and estimated_tokens is not None:
        if estimated_tokens > ADAPTIVE_ROUTING_THRESHOLD:
            # High token count → prefer long-context backend (GPU0)
            for bk in backends:
                if BACKENDS[bk]["strategy"] == "long":
                    logger.info(f"Adaptive routing: {estimated_tokens} tokens > {ADAPTIVE_ROUTING_THRESHOLD}, using long-context backend {bk}")
                    return bk
        else:
            # Low token count → prefer throughput backend (GPU1)
            for bk in backends:
                if BACKENDS[bk]["strategy"] == "throughput":
                    logger.info(f"Adaptive routing: {estimated_tokens} tokens <= {ADAPTIVE_ROUTING_THRESHOLD}, using throughput backend {bk}")
                    return bk
    
    # Role-based preference
    if role == "webui":
        # WebUI prefers GPU0 (long-context for interactive sessions)
        for bk in backends:
            if BACKENDS[bk]["gpu"] == "0":
                logger.info(f"Role-based routing: webui → {bk}")
                return bk
    elif role == "n8n":
        # n8n prefers GPU1 (throughput for automation)
        for bk in backends:
            if BACKENDS[bk]["gpu"] == "1":
                logger.info(f"Role-based routing: n8n → {bk}")
                return bk
    
    # Fallback to first backend
    return backends[0]

# =============================================================================
# Ensure online backend
# =============================================================================
async def ensure_online_backend(bk: str, role: str) -> Optional[JSONResponse]:
    meta = BACKENDS[bk]
    model_id = meta["model"]
    gpu = meta["gpu"]

    # Cap is per MODEL across all backends
    model_inflight = sum(inflight[b] for b in MODEL_BACKENDS.get(model_id, []))
    cap = CAPS.get(model_id, 1)
    if model_inflight >= cap:
        logger.warning(f"Model {model_id} at capacity: {model_inflight}/{cap}")
        return json_error(429, f"Too many concurrent requests for '{model_id}' ({model_inflight}/{cap}).", "rate_limited")

    st = container_status(meta["container"])
    if not st.get("exists"):
        return json_error(409, f"Container '{meta['container']}' does not exist. Create it once via docker compose up.", "container_missing")

    if st.get("running"):
        ok = await wait_until_healthy(bk, timeout_s=HEALTH_PROBE_TIMEOUT_S)
        return None if ok else json_error(503, f"Backend running but not healthy for '{model_id}'.", "unhealthy")

    async with backend_locks[bk]:
        st2 = container_status(meta["container"])
        if st2.get("running"):
            ok = await wait_until_healthy(bk, timeout_s=HEALTH_PROBE_TIMEOUT_S)
            return None if ok else json_error(503, f"Backend running but not healthy for '{model_id}'.", "unhealthy")

        logger.info(f"Starting backend {bk} ({meta['strategy']}) for role={role} on GPU{gpu}")

        async with gpu_locks[gpu]:
            # One heavyweight per GPU rule (chat only)
            if ONE_HEAVY_PER_GPU and is_heavy_backend(bk):
                busy_bk = running_heavy_backend_on_gpu(gpu, except_bk=bk)
                if busy_bk:
                    # WebUI: fail fast
                    if role == "webui" and WEBUI_FAIL_FAST_IF_GPU_BUSY:
                        busy_model = BACKENDS[busy_bk]["model"]
                        logger.info(f"GPU{gpu} busy with {busy_bk}, failing fast for webui")
                        return json_error(503, f"GPU{gpu} busy with '{busy_model}' (no preemption for webui).", "gpu_busy")

                    # n8n: allow preempt only on GPU1 (by your rule)
                    if role == "n8n" and gpu == "1" and N8N_ALLOW_PREEMPT_GPU1:
                        logger.warning(f"Preempting {busy_bk} on GPU{gpu} for {bk}")
                        try:
                            stop_container(BACKENDS[busy_bk]["container"])
                        except Exception as e:
                            logger.error(f"Failed to stop {busy_bk}: {e}")
                        await asyncio.sleep(3)
                    else:
                        busy_model = BACKENDS[busy_bk]["model"]
                        return json_error(503, f"GPU{gpu} busy with '{busy_model}'.", "gpu_busy")

            # If starting a GPU1 generator, stop embed/rerank first
            if STOP_EMBED_RANK_BEFORE_GPU1_GENERATOR and gpu == "1" and model_id in GPU1_GENERATORS:
                await stop_gpu1_embed_rank_best_effort()

            last_err = None
            for attempt in range(1, MAX_START_RETRIES + 1):
                try:
                    logger.info(f"Start attempt {attempt}/{MAX_START_RETRIES} for {bk}")
                    start_container(meta["container"])
                except Exception as e:
                    last_err = traceback.format_exc()
                    logger.error(f"Start attempt {attempt} failed for {bk}: {e}")
                    await asyncio.sleep(2)
                    continue

                ok = await wait_until_healthy(bk, timeout_s=warmup_timeout_for_role(role))
                if ok:
                    logger.info(f"Backend {bk} started successfully")
                    return None

                logger.warning(f"Backend {bk} started but unhealthy, stopping and retrying")
                try:
                    stop_container(meta["container"])
                except Exception:
                    pass
                await asyncio.sleep(2)

            logger.error(f"Backend {bk} failed to start after {MAX_START_RETRIES} attempts")
            return json_error(503, f"Backend start failed after {MAX_START_RETRIES} attempts: {last_err or 'unhealthy'}", "start_failed")

# =============================================================================
# Proxy
# =============================================================================
async def proxy(req: Request, base: str, path: str) -> Response:
    method = req.method.upper()
    url = f"{base}{path}"
    headers = dict(req.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)
    body = await req.body()
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.request(method, url, headers=headers, content=body)
    return Response(content=r.content, status_code=r.status_code, headers=dict(r.headers))

# =============================================================================
# Routes
# =============================================================================
@app.get("/healthz")
async def healthz():
    return {"ok": True, "ts": time.time()}

@app.get("/v1/models")
async def list_models(req: Request):
    try:
        _ = caller_role(req)
    except PermissionError as e:
        return json_error(401, str(e), "unauthorized")
    data = [{"id": mid, "object": "model"} for mid in MODEL_BACKENDS.keys()]
    return {"object": "list", "data": data}

async def ensure_and_get_backend(model_id: str, role: str, estimated_tokens: Optional[int] = None) -> Tuple[Optional[str], Optional[JSONResponse]]:
    bk0 = choose_backend(model_id, estimated_tokens, role)
    if not bk0:
        return None, json_error(400, f"Unknown model '{model_id}'.", "unknown_model")

    # Try chosen backend first, then fallback to the other GPU backend if exists.
    candidates = MODEL_BACKENDS.get(model_id, [])
    ordered = [bk0] + [bk for bk in candidates if bk != bk0]

    for bk in ordered:
        err = await ensure_online_backend(bk, role)
        if not err:
            return bk, None
        # If it's gpu busy, try another backend (if any)
        if err.status_code == 503 and err.body and b"gpu_busy" in err.body:
            continue
        # other errors are hard failures
        return None, err

    return None, json_error(503, f"No available backend for '{model_id}'.", "gpu_busy")

@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    try:
        role = caller_role(req)
    except PermissionError as e:
        return json_error(401, str(e), "unauthorized")

    payload = await req.json()
    model_id = payload.get("model")
    if model_id not in MODEL_BACKENDS:
        return json_error(400, f"Unknown model '{model_id}'.", "unknown_model")

    # Estimate tokens for adaptive routing
    estimated_tokens = estimate_request_tokens(payload) if ADAPTIVE_ROUTING_ENABLED else None
    
    bk, err = await ensure_and_get_backend(model_id, role, estimated_tokens)
    if err:
        return err
    assert bk is not None
    meta = BACKENDS[bk]

    if estimated_tokens:
        logger.info(f"Routing {model_id} to {bk} (estimated {estimated_tokens} tokens, role={role})")

    inflight[bk] += 1
    try:
        resp = await proxy(req, meta["base"], "/chat/completions")
        last_used[bk] = time.time()
        sticky_backend_by_gpu[meta["gpu"]] = bk  # last-called stays up on that GPU
        return resp
    finally:
        inflight[bk] -= 1

@app.post("/v1/embeddings")
async def embeddings(req: Request):
    try:
        role = caller_role(req)
    except PermissionError as e:
        return json_error(401, str(e), "unauthorized")

    payload = await req.json()
    model_id = payload.get("model")
    if model_id not in MODEL_BACKENDS:
        return json_error(400, f"Unknown model '{model_id}'.", "unknown_model")

    # embeddings only have one backend in this setup
    bk = MODEL_BACKENDS[model_id][0]
    err = await ensure_online_backend(bk, role)
    if err:
        return err

    meta = BACKENDS[bk]
    inflight[bk] += 1
    try:
        resp = await proxy(req, meta["base"], "/embeddings")
        last_used[bk] = time.time()
        sticky_backend_by_gpu[meta["gpu"]] = bk
        return resp
    finally:
        inflight[bk] -= 1

@app.post("/v1/rerank")
async def rerank(req: Request):
    try:
        role = caller_role(req)
    except PermissionError as e:
        return json_error(401, str(e), "unauthorized")

    payload = await req.json()
    model_id = payload.get("model")
    if model_id not in MODEL_BACKENDS:
        return json_error(400, f"Unknown model '{model_id}'.", "unknown_model")

    bk = MODEL_BACKENDS[model_id][0]
    err = await ensure_online_backend(bk, role)
    if err:
        return err

    meta = BACKENDS[bk]
    inflight[bk] += 1
    try:
        base_root = meta["base"].rsplit("/v1", 1)[0]
        resp = await proxy(req, base_root, "/rerank")
        last_used[bk] = time.time()
        sticky_backend_by_gpu[meta["gpu"]] = bk
        return resp
    finally:
        inflight[bk] -= 1

# =============================================================================
# TTL sweeper
# =============================================================================
def ttl_for_backend(bk: str) -> int:
    meta = BACKENDS[bk]
    mid = meta["model"]
    if meta["gpu"] == "1" and mid in GPU1_GENERATORS:
        return GPU1_GENERATOR_TTL_MIN
    return GLOBAL_TTL_MIN

async def ttl_sweeper():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        grace_s = GRACE_IDLE_MIN * 60

        for bk, meta in BACKENDS.items():
            st = container_status(meta["container"])
            if not (st.get("exists") and st.get("running")):
                continue

            # keep last-called per GPU
            if KEEP_LAST_PER_GPU and sticky_backend_by_gpu.get(meta["gpu"]) == bk and last_used.get(bk, 0.0) > 0:
                continue

            # don't stop inflight
            if inflight.get(bk, 0) > 0:
                continue

            last = last_used.get(bk, 0.0)
            idle_s = (now - last) if last > 0 else now

            if idle_s < grace_s:
                continue

            ttl_s = ttl_for_backend(bk) * 60
            if idle_s >= ttl_s:
                logger.info(f"TTL expired for {bk}, stopping container")
                try:
                    stop_container(meta["container"])
                except Exception as e:
                    logger.error(f"Failed to stop {bk} during TTL sweep: {e}")

@app.on_event("startup")
async def on_startup():
    logger.info("Router starting up...")
    logger.info(f"Adaptive routing: {'enabled' if ADAPTIVE_ROUTING_ENABLED else 'disabled'}")
    if ADAPTIVE_ROUTING_ENABLED:
        logger.info(f"Routing threshold: {ADAPTIVE_ROUTING_THRESHOLD} tokens")
    asyncio.create_task(ttl_sweeper())

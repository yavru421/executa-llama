import json
# --- Device Management (live Tailscale API) ---
# --- Serve static files (frontend) ---


from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, UploadFile, File, Form, Body, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from typing import List, Optional
import os
import shutil
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agent import get_command_from_llama, execute_remote_command_with_handling
from tools.ssh_tool import PersistentSSHSession, SSHSessionManager

# --- Config ---
SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", "supersecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Simple token verification helper (use SECRET_KEY/ALGORITHM)
def verify_token(authorization_header: str):
    if not authorization_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization_header.split(' ', 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
        if not username or username not in users_db:
            raise HTTPException(status_code=401, detail="Invalid token user")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# --- OAuth2 scheme and helper for dependency injection ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

async def get_current_user(request: Request):
    """Resolve current user from Authorization header or httpOnly cookie 'access_token'."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Try header first
    auth = request.headers.get('authorization') or ''
    token = None
    if auth and auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1]
    else:
        # fallback to cookie
        token = request.cookies.get('access_token')
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
        if not isinstance(username, str) or username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = users_db.get(username)
    if user is None:
        raise credentials_exception
    return user


# --- App Setup ---
app = FastAPI()

# --- Serve static files (frontend) ---
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
static_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

# Track server start for simple uptime/status
import time as _time
START_TIME = _time.time()

# Serve index.html at root
@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

origins = ["*"]  # Adjust for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/status')
async def status_endpoint():
    """Return simple dashboard/server status for the web UI."""
    try:
        uptime_seconds = int(_time.time() - START_TIME)
        return {"status": "online", "uptime": f"{uptime_seconds}s"}
    except Exception as e:
        return {"status": "error", "uptime": "0s", "error": str(e)}


@app.post('/chat')
async def chat(input: str = Form(...)):
    """Accept user input, ask the agent for a planned command, and return an AI reply + planned command.
    This endpoint mirrors the CLI behavior in a simplified form for the GUI.
    """
    try:
        # Get a planned command from the LLM-based helper (may be empty)
        planned_cmd = None
        try:
            planned_cmd = get_command_from_llama(input)
        except Exception as e:
            # Return a helpful message rather than failing hard
            return {"ai_reply": f"[LLM ERROR] {e}", "planned_command": None, "ssh_output": None}

        ai_reply = f"Planned command: {planned_cmd}" if planned_cmd else "No command planned."
        # Do not auto-execute commands here; the frontend uses /approve or websockets to run them.
        return {"ai_reply": ai_reply, "planned_command": planned_cmd, "ssh_output": None}
    except Exception as e:
        return {"ai_reply": "", "planned_command": None, "ssh_output": f"[ERROR] {e}"}


@app.post('/summarize')
async def summarize(prompt: str = Form(...), authorization: Optional[str] = None):
    """Return a short summary of recent actions and then answer the user's prompt.
    Uses the in-memory/persistent memory store when available for context.
    """
    try:
        # Load persistent memory (if present) and stringify messages for context
        try:
            from agent import summarize_and_respond, load_persistent_memory
            history = load_persistent_memory()
            # history is a list of message objects; extract content where possible
            context_parts = []
            for msg in history:
                if hasattr(msg, 'content'):
                    context_parts.append(str(msg.content))
                else:
                    context_parts.append(str(msg))
            context = "\n".join(context_parts)
        except Exception:
            context = ''

        # Simple token validation: extract Bearer token from Authorization header if present
        try:
            from jose import jwt as _jwt
            token = None
            if authorization and authorization.startswith('Bearer '):
                token = authorization.split(' ', 1)[1]
            # validate token if present (optional)
            if token:
                payload = _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                username = payload.get('sub')
                if username not in users_db:
                    return { 'summary': '[AUTH ERROR] Invalid user' }
        except Exception:
            # ignore auth errors for now and continue
            pass

        from agent import summarize_and_respond
        reply = summarize_and_respond(prompt, context)
        return { 'summary': reply }
    except Exception as e:
        return { 'summary': f'[ERROR] {e}' }


@app.post('/agents/aggregate')
async def agents_aggregate(request: Request, actions: str = Form(...), prompt: str = Form(None), authorization: Optional[str] = None):
    """Aggregate multiple agent actions into a single coordinator response.
    actions: newline-separated list of action strings or JSON array.
    """
    try:
        # Normalize actions input
        try:
            # Try JSON array
            parsed = json.loads(actions)
            if isinstance(parsed, list):
                action_list = [str(a) for a in parsed]
            else:
                action_list = [str(actions)]
        except Exception:
            # Split by newline as fallback
            action_list = [line.strip() for line in actions.splitlines() if line.strip()]

        # read Authorization header if not passed
        auth = authorization or request.headers.get('authorization') or ''
        # optional verification
        try:
            if auth:
                verify_token(auth)
        except HTTPException:
            return { 'aggregate': '[AUTH ERROR] Unauthorized' }

        from agent import aggregate_agents
        reply = aggregate_agents(action_list, user_prompt=prompt or "")
        # Persist aggregate to outputs/aggregates.md
        outdir = os.path.join(os.path.dirname(__file__), '..', 'outputs')
        os.makedirs(outdir, exist_ok=True)
        try:
            with open(os.path.join(outdir, 'aggregates.md'), 'a', encoding='utf-8') as fh:
                fh.write(f"### Aggregate ({datetime.utcnow().isoformat()}):\n{reply}\n\n")
        except Exception:
            pass
        return { 'aggregate': reply }
    except Exception as e:
        return { 'aggregate': f'[ERROR] {e}' }


@app.post('/agents/execute')
async def agents_execute(request: Request, device_ip: str = Form(...), ssh_user: str = Form(...), ssh_password: str = Form(None), command: str = Form(...), authorization: Optional[str] = None):
    """Execute a command on a device via SSH after verifying authorization header."""
    try:
        # Verify token (will raise HTTPException if invalid)
        auth = authorization or request.headers.get('authorization') or ''
        verify_token(auth)
        from tools.ssh_tool import PersistentSSHSession
        session = PersistentSSHSession(host=device_ip, user=ssh_user, password=ssh_password)
        out = session.send_command(command)
        session.close()
        return { 'status': 'ok', 'output': out }
    except HTTPException:
        raise
    except Exception as e:
        return { 'status': 'error', 'error': str(e) }


@app.post('/course-check')
async def course_check(request: Request, conversation: str = Form(None)):
    """Return a validated 5-step course plan based on the conversation text.
    Accepts either form data (conversation) or JSON body {"conversation": "..."}.
    Attempts to parse the model output into a JSON array of 5 step objects.
    """
    try:
        body = None
        try:
            if request.headers.get('content-type', '').lower().startswith('application/json'):
                body = await request.json()
        except Exception:
            body = None

        conv = None
        if body and isinstance(body, dict) and 'conversation' in body:
            conv = body.get('conversation')
        else:
            conv = conversation

        if not conv:
            return { 'plan': None, 'error': 'Missing conversation text' }

        from agent import plan_course
        raw = plan_course(conv)

        # Try to parse JSON directly
        try:
            parsed = json.loads(raw)
        except Exception:
            # Try to extract the first JSON array from the output
            import re
            m = re.search(r"(\[\s*\{.*?\}\s*\])", raw, re.S)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                except Exception:
                    parsed = None
            else:
                parsed = None

        # Validate structure: list of 5 items with at least 'prompt' and 'action' keys (or allow strings)
        if isinstance(parsed, list) and len(parsed) == 5:
            normalized = []
            for item in parsed:
                if isinstance(item, dict):
                    prompt = item.get('prompt') or item.get('instruction') or item.get('task') or ''
                    action = item.get('action') or item.get('cmd') or item.get('command') or ''
                    normalized.append({'prompt': prompt, 'action': action, 'raw': item})
                else:
                    # accept string entries as prompts
                    normalized.append({'prompt': str(item), 'action': '' , 'raw': item})
            return { 'plan': normalized, 'raw': raw }

        # If parsing failed, return raw with an error flag
        return { 'plan': None, 'raw': raw, 'error': 'Could not parse model output as JSON array of 5 items' }
    except Exception as e:
        return { 'plan': None, 'error': str(e) }


@app.post('/course-run')
async def course_run(request: Request, action: str = Form(...), device_ip: str = Form(None), ssh_user: Optional[str] = Form(None), ssh_password: Optional[str] = Form(None), current_user: dict = Depends(get_current_user)):
    """Execute a single validated action produced by CourseCheck.
    action must start with 'ssh:'. Requires authenticated user.
    Optional device credentials may be provided; otherwise uses saved creds or env vars.
    """
    try:
        if not action or not isinstance(action, str):
            return {'status': 'error', 'error': 'Missing action'}
        action = action.strip()
        if not action.startswith('ssh:'):
            return {'status': 'error', 'error': 'Unsupported action type; expected ssh:<command>'}
        cmd = action[len('ssh:'):].strip()
        # Basic blacklist check for obviously destructive commands
        dangerous_keywords = ['rm ', 'dd ', 'mkfs', 'shutdown', 'reboot', 'init 0', 'halt', 'poweroff']
        for kw in dangerous_keywords:
            if kw in cmd:
                return {'status': 'error', 'error': f'Command contains dangerous keyword: {kw.strip()}'}

        # Determine device credentials
        creds = {}
        creds_path = os.path.join(os.path.dirname(__file__), 'device_creds.json')
        if os.path.exists(creds_path):
            try:
                with open(creds_path, 'r', encoding='utf-8') as f:
                    creds = json.load(f)
            except Exception:
                creds = {}

        # If a specific device_ip was provided and has saved creds, use them
        if device_ip and device_ip in creds:
            saved = creds.get(device_ip, {})
            ssh_user = ssh_user or saved.get('ssh_user')
            ssh_password = ssh_password or saved.get('ssh_password')

        # Fallback to environment
        ssh_user = ssh_user or os.getenv('SSH_USER') or ''
        ssh_password = ssh_password or os.getenv('SSH_PASSWORD') or ''
        host = device_ip or os.getenv('SSH_HOST') or ''

        # Run SSH command
        from tools.ssh_tool import PersistentSSHSession
        session = PersistentSSHSession(host=host, user=ssh_user, password=ssh_password)
        out = session.send_command(cmd)
        session.close()
        return {'status': 'ok', 'output': out}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


@app.get('/session-log')
async def session_log():
    """Return a simple session log (reads most recent markdown in outputs/ if present)."""
    try:
        outdir = os.path.join(os.path.dirname(__file__), '..', 'outputs')
        outdir = os.path.abspath(outdir)
        logs = []
        if os.path.exists(outdir):
            files = [f for f in os.listdir(outdir) if f.endswith('.md')]
            files.sort(reverse=True)
            if files:
                with open(os.path.join(outdir, files[0]), 'r', encoding='utf-8', errors='ignore') as fh:
                    logs.append(fh.read())
        return {"log": logs}
    except Exception as e:
        return {"log": [], "error": str(e)}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# --- Dummy User Store (replace with DB in prod) ---
# --- File-backed user store + password hashing ---
USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')

def hash_password(plain: str) -> str:
    # Lazily import passlib to avoid heavy import at module load if not installed
    try:
        from passlib.hash import bcrypt
    except Exception:
        raise RuntimeError('passlib[bcrypt] is required for password hashing')
    return bcrypt.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        from passlib.hash import bcrypt
    except Exception:
        raise RuntimeError('passlib[bcrypt] is required for password verification')
    try:
        return bcrypt.verify(plain, hashed)
    except Exception:
        return False

def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            pass
    # Create a safe default admin if no users file exists
    default_pw = 'admin'
    try:
        hashed = hash_password(default_pw)
    except Exception:
        # If hashing not available, fallback to plain (temporary; tests will install deps)
        hashed = default_pw
    users = {
        "admin": {
            "username": "admin",
            "full_name": "Admin User",
            "hashed_password": hashed,
            "disabled": False,
        }
    }
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as fh:
            json.dump(users, fh, indent=2)
    except Exception:
        pass
    return users


users_db = load_users()

def authenticate_user(username: str, password: str):
    user = users_db.get(username)
    if not user:
        return False
    if not verify_password(password, user.get("hashed_password", "")):
        return False
    return user

def get_user_from_token_str(token_str: str):
    """Validate a Bearer token string and return the user dict or raise HTTPException."""
    if not token_str:
        raise HTTPException(status_code=401, detail="Missing token")
    if token_str.startswith('Bearer '):
        token_str = token_str.split(' ', 1)[1]
    try:
        payload = jwt.decode(token_str, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
        if not isinstance(username, str) or username is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        user = users_db.get(username)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid token user")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- Auth Endpoints ---
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user["username"]}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    # Set httpOnly secure cookie
    resp = JSONResponse({"access_token": "set-in-cookie", "token_type": "bearer"})
    resp.set_cookie(key='access_token', value=access_token, httponly=True, secure=False, samesite='lax', path='/')
    return resp


@app.post('/logout')
async def logout():
    resp = JSONResponse({"detail": "logged out"})
    resp.delete_cookie('access_token', path='/')
    return resp


@app.get('/me')
async def me(current_user: dict = Depends(get_current_user)):
    return { 'username': current_user.get('username'), 'full_name': current_user.get('full_name') }

# --- Device Management (single device for now) ---
@app.get("/filetree")
async def filetree(device: str, path: str = "/", ssh_user: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    try:
        from tools.ssh_tool import PersistentSSHSession
        import os
        ssh_password = os.getenv("SSH_PASSWORD")
        # If ssh_user not provided, try to load saved creds
        creds_path = os.path.join(os.path.dirname(__file__), 'device_creds.json')
        if not ssh_user and os.path.exists(creds_path):
            try:
                with open(creds_path, 'r', encoding='utf-8') as f:
                    creds = json.load(f)
                c = creds.get(device) or creds.get(device.replace('100.',''))
                if c:
                    ssh_user = c.get('ssh_user') or ssh_user
                    ssh_password = c.get('ssh_password') or ssh_password
            except Exception:
                pass
        session = PersistentSSHSession(host=device, user=ssh_user or os.getenv("SSH_USER"), password=ssh_password)
        # List files and directories
        cmd = f'ls -lA "{path}"'
        output = session.send_command(cmd)
        files = []
        for line in output.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 9:
                continue
            ftype = 'dir' if parts[0].startswith('d') else 'file'
            fname = ' '.join(parts[8:])
            files.append({
                'name': fname,
                'type': ftype,
                'path': os.path.join(path, fname)
            })
        return { 'files': files }
    except Exception as e:
        return { 'files': [], 'error': str(e) }

    # 2. Get planned command (as before)
    planned_cmd = get_command_from_llama(input)
    # 3. Optionally, run the command and get SSH output
    ssh_output = None
    if planned_cmd:
        try:
            ssh_output = execute_remote_command_with_handling(planned_cmd)
        except Exception as e:
            ssh_output = f"[Error running command: {e}]"

    return {
        "ai_reply": ai_reply,
        "planned_command": planned_cmd,
        "ssh_output": ssh_output
    }


# --- Password Change Endpoint ---
@app.post("/set_password")
async def set_password(new_password: str = Body(...), current_user: dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can change password")
    users_db["admin"]["hashed_password"] = new_password
    return {"detail": "Password updated"}

# --- Approve & Execute Command ---
@app.post("/approve")
async def approve(cmd: str = Form(...), current_user: dict = Depends(get_current_user)):
    # Execute command and stream output (simplified for now)
    result = execute_remote_command_with_handling(cmd)
    return {"output": result}


# --- WebSocket for Real-Time SSH Output ---
import asyncio
from starlette.websockets import WebSocketState

@app.websocket("/ws/ssh-exec")
async def websocket_ssh_exec(websocket: WebSocket):
    await websocket.accept()
    try:
        # Wait for a JSON message: {"token": ..., "cmd": ...}
        data = await websocket.receive_json()
        token = data.get("token")
        cmd = data.get("cmd")
        # Auth check: validate bearer token string and return user dict
        def get_user_from_token_str(token_str: str):
            if not token_str:
                raise HTTPException(status_code=401, detail="Missing token")
            if token_str.startswith('Bearer '):
                token_str = token_str.split(' ', 1)[1]
            try:
                payload = jwt.decode(token_str, SECRET_KEY, algorithms=[ALGORITHM])
                username = payload.get('sub')
                if not username or username not in users_db:
                    raise HTTPException(status_code=401, detail="Invalid token user")
                return users_db.get(username)
            except JWTError:
                raise HTTPException(status_code=401, detail="Invalid token")

        try:
            user = get_user_from_token_str(token)
        except Exception:
            await websocket.send_text("[AUTH ERROR] Invalid token.")
            await websocket.close()
            return
        # Start SSH session and stream output
        session = PersistentSSHSession()
        if not session.shell:
            await websocket.send_text("[SSH ERROR] Could not open SSH shell.")
            session.close()
            await websocket.close()
            return
        session.shell.send(cmd + '\n')
        await asyncio.sleep(0.2)
        output = ""
        while websocket.application_state == WebSocketState.CONNECTED:
            if session.shell and session.shell.recv_ready():
                chunk = session.shell.recv(4096).decode(errors="ignore")
                output += chunk
                await websocket.send_text(chunk)
                if chunk.strip().endswith("$") or chunk.strip().endswith("#"):
                    break
            await asyncio.sleep(0.2)
        session.close()
        await websocket.close()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(f"[ERROR] {e}")
        await websocket.close()

# --- File Upload/Download ---
@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    # Save file locally, then upload via SSH (stub)
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    # TODO: Use SSH to upload to device
    return {"filename": file.filename, "status": "uploaded (local only)"}

@app.get("/files/download")
async def download_file(filename: str, current_user: dict = Depends(get_current_user)):
    # TODO: Use SSH to fetch file from device, then serve
    local_path = f"/tmp/{filename}"
    if not os.path.exists(local_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(local_path, filename=filename)

# --- Device Status ---
@app.get("/devices")
async def list_devices(current_user: dict = Depends(get_current_user)):
    # Fetch devices from Tailscale API
    tailscale_api_key = os.getenv("TAILSCALE_API_KEY", "tskey-auth-kHgSt1ptVF11CNTRL-yZeGCBvk4NFY8g8YN64cMFpaShgb2ErF")
    ssh_user = os.getenv("SSH_USER", "pi")
    headers = {"Authorization": f"Bearer {tailscale_api_key}"}
    try:
        # Import requests lazily so the server can start even if requests isn't installed
        import requests
        resp = requests.get("https://api.tailscale.com/api/v2/tailnet/-/devices", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        devices = []
        for d in data.get("devices", []):
            if d.get("online") and d.get("addresses"):
                # Use the first Tailscale IP
                ip = next((a for a in d["addresses"] if a.startswith("100.")), None)
                if ip:
                    devices.append({
                        "name": d.get("hostname", "device"),
                        "ip": ip,
                        "ssh_user": ssh_user
                        # Optionally add password/key fields here
                    })
        # If no devices found via API, fall back to saved creds
        if not devices:
            creds = {}
            creds_path = os.path.join(os.path.dirname(__file__), 'device_creds.json')
            if os.path.exists(creds_path):
                try:
                    with open(creds_path, 'r', encoding='utf-8') as f:
                        creds = json.load(f)
                except Exception:
                    creds = {}
            for ip, info in creds.items():
                devices.append({
                    'name': info.get('ssh_user', ip),
                    'ip': ip,
                    'ssh_user': info.get('ssh_user', ssh_user)
                })
        # If still empty, include SSH_HOST env as a last resort
        if not devices and os.getenv('SSH_HOST'):
            devices.append({'name': 'env-host', 'ip': os.getenv('SSH_HOST'), 'ssh_user': ssh_user})
        return devices
    except Exception as e:
        # Try fallback to saved creds even if API fails
        creds = {}
        creds_path = os.path.join(os.path.dirname(__file__), 'device_creds.json')
        devices = []
        if os.path.exists(creds_path):
            try:
                with open(creds_path, 'r', encoding='utf-8') as f:
                    creds = json.load(f)
            except Exception:
                creds = {}
        for ip, info in creds.items():
            devices.append({ 'name': info.get('ssh_user', ip), 'ip': ip, 'ssh_user': info.get('ssh_user', ssh_user) })
        if not devices and os.getenv('SSH_HOST'):
            devices.append({'name': 'env-host', 'ip': os.getenv('SSH_HOST'), 'ssh_user': ssh_user})
        # If still empty, return an error entry but keep response shape stable (list)
        if not devices:
            return [{"name": "[Error fetching devices]", "ip": str(e), "ssh_user": ssh_user}]
        return devices


# --- Device credentials management ---
CREDS_PATH = os.path.join(os.path.dirname(__file__), 'device_creds.json')

@app.post('/device-creds')
async def save_device_creds(device_ip: str = Form(...), ssh_user: str = Form(...), ssh_password: str = Form(None), current_user: dict = Depends(get_current_user)):
    data = {}
    if os.path.exists(CREDS_PATH):
        try:
            with open(CREDS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[device_ip] = { 'ssh_user': ssh_user, 'ssh_password': ssh_password }
    with open(CREDS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return {'status': 'saved'}

@app.get('/device-creds')
async def get_device_creds(current_user: dict = Depends(get_current_user)):
    if os.path.exists(CREDS_PATH):
        try:
            with open(CREDS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return { 'error': str(e) }
    return {}

@app.post('/device-test')
async def test_device(device_ip: str = Form(...), ssh_user: str = Form(...), ssh_password: str = Form(None), current_user: dict = Depends(get_current_user)):
    # Test SSH connection
    try:
        from tools.ssh_tool import PersistentSSHSession
        session = PersistentSSHSession(host=device_ip, user=ssh_user, password=ssh_password)
        out = session.send_command('echo CONNECTION_OK')
        session.close()
        if 'CONNECTION_OK' in out:
            return { 'status': 'ok' }
        return { 'status': 'failed', 'output': out }
    except Exception as e:
        return { 'status': 'error', 'error': str(e) }


@app.post('/funnels/create')
async def create_funnel(device_ip: str = Form(...), ssh_user: str = Form(...), ssh_password: str = Form(None), name: str = Form(...), port: int = Form(...), hostname: str = Form(None), current_user: dict = Depends(get_current_user)):
    """Create a funnel on a device via SSH."""
    try:
        # Import helpers here to avoid circular import / ordering issues
        from tools.ssh_tool import tailscale_funnel_create
        session = PersistentSSHSession(host=device_ip, user=ssh_user, password=ssh_password)
        out = tailscale_funnel_create(session, name=name, port=port, hostname=hostname)
        session.close()
        return { 'status': 'ok', 'output': out }
    except Exception as e:
        return { 'status': 'error', 'error': str(e) }


@app.get('/funnels')
async def list_funnels(device_ip: str, ssh_user: Optional[str] = None, ssh_password: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """List funnels on the device."""
    try:
        from tools.ssh_tool import tailscale_funnel_list
        session = PersistentSSHSession(host=device_ip, user=ssh_user or os.getenv('SSH_USER'), password=ssh_password or os.getenv('SSH_PASSWORD'))
        out = tailscale_funnel_list(session)
        session.close()
        return { 'status': 'ok', 'output': out }
    except Exception as e:
        return { 'status': 'error', 'error': str(e) }


@app.post('/funnels/delete')
async def delete_funnel(device_ip: str = Form(...), ssh_user: str = Form(...), ssh_password: str = Form(None), identifier: str = Form(...), current_user: dict = Depends(get_current_user)):
    """Delete a funnel by id or name on the device."""
    try:
        from tools.ssh_tool import tailscale_funnel_delete
        session = PersistentSSHSession(host=device_ip, user=ssh_user, password=ssh_password)
        out = tailscale_funnel_delete(session, identifier)
        session.close()
        return { 'status': 'ok', 'output': out }
    except Exception as e:
        return { 'status': 'error', 'error': str(e) }

# Llama Agent Web Dashboard Deployment Instructions

## 1. Prerequisites
- Python 3.9+
- Tailscale installed and configured on your server and devices
- Your SSH and agent environment variables set in `.env`
- (Optional) HTTPS certificate for production (Tailscale HTTPS is recommended)

## 2. Install Python Dependencies

```sh
cd llamatrama_agent
python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements.txt
pip install fastapi uvicorn[standard] python-jose[cryptography]
```

## 3. Environment Variables

Create or update `.env` in `llamatrama_agent/`:

```
LLAMA_API_KEY=your_llama_api_key
SSH_HOST=your_pi_tailscale_ip
SSH_USER=pi
SSH_KEY_PATH=C:/Users/John/.ssh/id_rsa
DASHBOARD_SECRET_KEY=your_dashboard_secret
```

## 4. Run the FastAPI Server

```sh
cd llamatrama_agent/web
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- The dashboard will be available at `http://localhost:8000/web/index.html` (or via your Tailscale IP)
- For production, remove `--reload` and use a process manager (e.g., systemd, pm2, or gunicorn)

## 5. Tailscale Access
- Ensure your server is in your tailnet and accessible from your other devices.
- You can use Tailscale HTTPS for secure access, or set up your own HTTPS reverse proxy.

## 6. Usage
- Open the dashboard in your browser.
- Login with the default user (`admin`/`admin`). Change this in `main.py` for production.
- Select your device, chat with the agent, approve commands, and manage files.

## 7. Customization & Security
- Change the user/password and secret key in `main.py` and `.env`.
- For multiple devices, extend `/devices` and SSH config logic.
- For production, use HTTPS and strong passwords.

## 8. Troubleshooting
- Check FastAPI logs for errors.
- Ensure your `.env` is correct and SSH works from the server.
- Tailscale must be running and connected.

---

**You now have a TURN KEY, Tailscale-accessible, secure web dashboard for your Llama agent and SSH Pi control!**

# QuickLearn.AI Backend Deployment Guide

## Prerequisites

1. **GitHub Repository**: Push your code to GitHub
2. **Render Account**: Sign up at [render.com](https://render.com)
3. **Worker Setup**: Ensure your worker is running with ngrok

## Local Worker & ngrok Setup (Detailed Guide)

### Overview
The VibeKnowing Worker is a FastAPI service that runs locally (on your laptop, desktop, or a home server) to process YouTube and other video/audio content. It uses a residential IP to bypass YouTube restrictions and exposes its API to the cloud backend via an ngrok tunnel.

### Prerequisites
- Python 3.8 or higher (Python 3.11+ recommended)
- pip (Python package manager)
- ffmpeg (for audio/video processing)
- yt-dlp (for video downloading)
- OpenAI API key (for Whisper transcription)
- ngrok account (free or paid)

### 1. Clone the Worker Repository
```bash
git clone <your-worker-repo-url>
cd vibeknowing-worker
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install ffmpeg
- **macOS:**
  ```bash
  brew install ffmpeg
  ```
- **Ubuntu/Debian:**
  ```bash
  sudo apt update
  sudo apt install ffmpeg
  ```
- **Windows:**
  - Download from https://ffmpeg.org/download.html
  - Add ffmpeg to your system PATH

### 4. Install yt-dlp
```bash
pip install yt-dlp
```
Or download the binary from https://github.com/yt-dlp/yt-dlp/releases and add it to your PATH.

### 5. Set Your OpenAI API Key
- Get your key from https://platform.openai.com/api-keys
- Set it as an environment variable:
  ```bash
  export OPENAI_API_KEY="sk-..."
  ```
  (On Windows: use `set OPENAI_API_KEY=sk-...` in Command Prompt)

### 6. Run the Worker Service
```bash
uvicorn worker:app --host 0.0.0.0 --port 8000
```
- The worker will be available at `http://localhost:8000/health`
- Test with: `curl http://localhost:8000/health`

### 7. Expose the Worker with ngrok
- Sign up at https://ngrok.com and download ngrok for your OS.
- Authenticate ngrok (replace YOUR_TOKEN):
  ```bash
  ngrok config add-authtoken YOUR_TOKEN
  ```
- Start the tunnel:
  ```bash
  ngrok http 8000
  ```
- You’ll get a public URL like `https://abc123.ngrok-free.app`.
- The worker API will be at `https://abc123.ngrok-free.app/transcribe`

### 8. Update Backend WORKER_URL
- In your backend’s environment variables, set:
  ```bash
  WORKER_URL=https://abc123.ngrok-free.app/transcribe
  ```
- Restart your backend if needed.

### 9. Troubleshooting
- **Worker not reachable?**
  - Make sure the worker is running and ngrok tunnel is active.
  - Check for firewall or router issues blocking port 8000.
- **yt-dlp or ffmpeg errors?**
  - Ensure both are installed and available in your PATH.
  - Test with `yt-dlp --version` and `ffmpeg -version`.
- **OpenAI API errors?**
  - Double-check your API key and account limits.
- **ngrok tunnel closes?**
  - Free ngrok tunnels may time out after 8 hours. Restart as needed or upgrade to a paid plan for persistent tunnels.

### 10. Security & Best Practices
- Never share your OpenAI API key or ngrok tunnel URL publicly.
- Use a strong ngrok authtoken and consider restricting allowed IPs (ngrok paid feature).
- Monitor worker logs for errors or abuse.
- Restart the worker and ngrok if you change your network or IP address.
- For production, consider running the worker on a dedicated, always-on device (e.g., Raspberry Pi, home server, or cloud VM with residential proxy).

### 11. Updating the Worker
- Pull the latest code:
  ```bash
  git pull origin main
  pip install -r requirements.txt
  ```
- Restart the worker and ngrok tunnel.

### 12. Useful Commands
- Check worker logs: `tail -f worker.log` (if logging enabled)
- Test endpoint: `curl http://localhost:8000/health`
- Test ngrok: `curl https://abc123.ngrok-free.app/health`

## Step 1: Prepare Your Repository

Make sure your repository structure looks like this:
```
quicklearn-ai-backend/
├── main.py
├── config.py
├── requirements.txt
├── Procfile
├── runtime.txt
├── services/
├── utils/
├── exceptions/
└── tests/
```

## Step 2: Create Render Web Service

1. Go to [render.com](https://render.com) and sign in
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Select the `quicklearn-ai-backend` directory
5. Configure the service:

### Basic Settings
- **Name**: `quicklearn-ai-backend` (or your preferred name)
- **Environment**: `Python 3`
- **Region**: Choose closest to your users
- **Branch**: `main` (or your default branch)

### Build & Deploy Settings
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Step 3: Configure Environment Variables

In your Render dashboard, go to "Environment" tab and add these variables:

### Required Variables
```
OPENAI_API_KEY=sk-your-openai-api-key-here
WORKER_URL=https://your-ngrok-url.ngrok-free.app/transcribe
ALLOWED_ORIGINS=https://your-frontend-url.onrender.com,http://localhost:3000
```

### Optional Variables
```
YOUTUBE_API_KEY=your-youtube-api-key-here
API_BASE_URL=https://your-backend-url.onrender.com
```

## Step 4: Deploy

1. Click "Create Web Service"
2. Render will automatically build and deploy your application
3. Monitor the build logs for any issues
4. Once deployed, you'll get a URL like: `https://your-app-name.onrender.com`

## Step 5: Test Your Deployment

1. **Health Check**: Visit `https://your-app-name.onrender.com/health`
2. **API Test**: Test your endpoints using the new URL
3. **Worker Integration**: Ensure your worker is accessible from Render

## Step 6: Update Frontend Configuration

Update your frontend to use the new backend URL:

```javascript
// In your frontend configuration
const API_BASE_URL = 'https://your-app-name.onrender.com';
```

## Troubleshooting

### Common Issues

1. **Build Failures**
   - Check that all dependencies are in `requirements.txt`
   - Ensure Python version in `runtime.txt` is supported by Render

2. **Environment Variables**
   - Double-check all environment variables are set correctly
   - Ensure `WORKER_URL` points to your active ngrok tunnel

3. **CORS Issues**
   - Verify `ALLOWED_ORIGINS` includes your frontend URL
   - Check that URLs don't have trailing slashes

4. **Worker Connection Issues**
   - Ensure your worker is running and accessible
   - Check ngrok tunnel is active and URL is correct
   - Verify worker can handle requests from Render's IP

### Logs and Debugging

1. **View Logs**: In Render dashboard, go to "Logs" tab
2. **Real-time Logs**: Use "Live" button to see real-time logs
3. **Environment**: Check environment variables in "Environment" tab

## Monitoring

1. **Health Checks**: Render automatically checks `/health` endpoint
2. **Uptime**: Monitor service status in dashboard
3. **Performance**: Check response times and error rates

## Scaling

- **Free Tier**: Limited to 750 hours/month
- **Paid Plans**: Start at $7/month for unlimited usage
- **Auto-scaling**: Available on paid plans

## Security Notes

1. **API Keys**: Never commit API keys to your repository
2. **Environment Variables**: Use Render's environment variable system
3. **CORS**: Configure `ALLOWED_ORIGINS` properly
4. **Worker Security**: Ensure your worker is properly secured

## Maintenance

1. **Updates**: Push to GitHub to trigger automatic deployments
2. **Worker Updates**: Restart worker and update ngrok URL if needed
3. **Monitoring**: Regularly check logs and performance metrics

## Support

- **Render Docs**: [docs.render.com](https://docs.render.com)
- **FastAPI Docs**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Community**: Render Discord and GitHub discussions 
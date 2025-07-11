# QuickLearn.AI Backend Deployment Guide

## Prerequisites

1. **GitHub Repository**: Push your code to GitHub
2. **Render Account**: Sign up at [render.com](https://render.com)
3. **Worker Setup**: Ensure your worker is running with ngrok

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
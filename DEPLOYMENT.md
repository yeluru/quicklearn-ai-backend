# QuickLearn.AI Deployment Guide

## Prerequisites
- GitHub repository with your code
- OpenAI API key
- YouTube API key (optional, for enhanced features)

## Environment Variables
Set these in your deployment platform:

```
OPENAI_API_KEY=your_openai_api_key_here
YOUTUBE_API_KEY=your_youtube_api_key_here
ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:3000
API_BASE_URL=https://your-backend-domain.com
```

## Option 1: Railway Deployment (Recommended)

### Backend Deployment
1. Go to [Railway](https://railway.app)
2. Connect your GitHub repository
3. Create a new project
4. Select the `quicklearn-ai-backend` directory
5. Add environment variables
6. Deploy

### Frontend Deployment
1. In Railway, create another service
2. Select the `quicklearn-ai-frontend` directory
3. Set build command: `npm install && npm run build`
4. Set start command: `npm start`
5. Add environment variable: `REACT_APP_API_URL=https://your-backend-url.railway.app`

## Option 2: Render Deployment

### Backend
1. Go to [Render](https://render.com)
2. Create a new Web Service
3. Connect your GitHub repository
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables

### Frontend
1. Create a new Static Site
2. Connect your GitHub repository
3. Set build command: `npm install && npm run build`
4. Set publish directory: `build`

## Option 3: Vercel + Railway

### Frontend (Vercel)
1. Go to [Vercel](https://vercel.com)
2. Import your GitHub repository
3. Set root directory to `quicklearn-ai-frontend`
4. Add environment variable: `REACT_APP_API_URL=https://your-backend-url.railway.app`

### Backend (Railway)
Follow the Railway backend deployment steps above.

## Post-Deployment Checklist

1. ✅ Test video transcript extraction
2. ✅ Test file upload functionality
3. ✅ Test chat functionality
4. ✅ Test summary generation
5. ✅ Verify CORS settings
6. ✅ Check environment variables
7. ✅ Test with different video platforms (YouTube, Vimeo, TED)

## Troubleshooting

### Common Issues:
1. **CORS errors**: Ensure `ALLOWED_ORIGINS` includes your frontend URL
2. **API key errors**: Verify all environment variables are set correctly
3. **yt-dlp issues**: Some platforms may require additional system dependencies
4. **File upload size limits**: Check platform-specific limits

### Performance Optimization:
1. Consider using Redis for caching
2. Implement rate limiting
3. Use CDN for static assets
4. Optimize audio processing for large files

## Monitoring
- Set up logging and monitoring
- Monitor API usage and costs
- Set up alerts for errors
- Track user engagement metrics 
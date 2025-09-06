# Maliev LINE Chatbot Service

A comprehensive LINE chatbot service for 3D printing business with multi-provider AI integration, intelligent caching, and customer management.

## Features

- 🤖 **Multi-AI Provider Support**: Gemini 2.5-flash, OpenAI, DeepSeek with automatic fallback
- 💬 **LINE Messaging API**: Complete webhook handling with signature verification
- 🧠 **Intelligent Caching**: Exact, semantic, and pattern-based response caching
- 👥 **Customer Management**: Automatic profile extraction and management
- 📋 **Dynamic Instructions**: Context-aware instruction system
- 🔒 **Enterprise Security**: Google Cloud Secret Manager integration
- 📊 **Monitoring**: Comprehensive metrics and structured logging
- ⚡ **High Performance**: Async FastAPI with Redis backend

## Quick Start

### Prerequisites

- Python 3.11+
- Redis (via Docker or local installation)
- Git

### 1. Clone and Setup

```bash
git clone https://github.com/maliev/Maliev.LineChatbotService.git
cd Maliev.LineChatbotService
git checkout develop  # Use develop branch for development
```

### 2. Environment Configuration

Copy and configure environment:
```bash
cp .env.example .env
```

The `.env` file is pre-configured with development defaults. For production, update the API keys:
```env
# Replace these with real values for production
GEMINI_API_KEY=your-actual-gemini-api-key
LINE_CHANNEL_ACCESS_TOKEN=your-line-access-token
LINE_CHANNEL_SECRET=your-line-channel-secret
```

### 3. Start Redis

Using Docker Compose (recommended):
```bash
docker-compose up redis -d
```

### 4. Install Dependencies

```bash
cd backend
python -m pip install fastapi uvicorn redis pydantic pydantic-settings structlog aiohttp httpx
```

### 5. Run the Application

```bash
cd backend
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

The application starts at: **http://127.0.0.1:8000**

## Verification

Test the application is working:

```bash
# Health check
curl http://127.0.0.1:8000/health

# API documentation
open http://127.0.0.1:8000/docs

# AI provider status
curl http://127.0.0.1:8000/api/v1/ai/providers

# Test AI provider
curl -X POST http://127.0.0.1:8000/api/v1/ai/test \
  -H "Content-Type: application/json" \
  -d '{"provider": "gemini", "message": "Hello"}'
```

## Architecture

```
├── backend/
│   ├── src/
│   │   ├── main.py              # FastAPI application
│   │   ├── config/settings.py   # Configuration management
│   │   ├── line/                # LINE integration
│   │   │   ├── client.py        # Messaging API client
│   │   │   ├── webhook.py       # Webhook handler
│   │   │   └── models.py        # Data models
│   │   ├── ai/                  # AI provider system
│   │   │   ├── manager.py       # Provider manager
│   │   │   └── providers/       # AI implementations
│   │   ├── database/            # Redis integration
│   │   ├── secrets/             # Secret management
│   │   ├── customers/           # Customer management
│   │   ├── cache/               # Intelligent caching
│   │   └── api/v1/             # REST API endpoints
├── frontend/                    # Admin UI (Next.js)
├── docker-compose.yml           # Development services
└── .env                        # Environment configuration
```

## API Endpoints

Key endpoints available at `/docs`:

- **Health**: `/health` - Application health check
- **LINE Webhook**: `/webhook` - LINE message handling
- **AI Providers**: `/api/v1/ai/providers` - Manage AI providers
- **Customers**: `/api/v1/customers` - Customer management
- **Cache**: `/api/v1/cache` - Cache management
- **Metrics**: `/api/v1/metrics` - Performance monitoring
- **Admin**: `/api/v1/admin` - System administration

## Configuration

### AI Providers

Configure in Redis or via API:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ai/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gemini",
    "provider_type": "gemini", 
    "model": "gemini-2.0-flash-exp",
    "api_key_secret": "env:GEMINI_API_KEY",
    "enabled": true,
    "priority": 10
  }'
```

### LINE Webhook

1. Set up LINE Bot in LINE Developers Console
2. Configure webhook URL: `https://your-domain.com/webhook`
3. Update `.env` with channel access token and secret

## Development

### Working Features ✅

- FastAPI web framework with async support
- Redis integration for caching and storage
- LINE webhook with signature verification
- Multi-provider AI system (Gemini, OpenAI, DeepSeek)
- Intelligent response caching
- Customer profile management
- Structured logging with correlation IDs
- Comprehensive admin API

### Development Workflow

1. **Make changes** on `develop` branch
2. **Test locally** using the endpoints above
3. **Use hot reload** - server restarts automatically
4. **Check logs** in terminal for debugging

### Common Development Tasks

**Add new AI provider:**
```python
# Create provider in backend/src/ai/providers/
class CustomProvider(AIProvider):
    # Implementation
```

**Modify LINE handling:**
```python
# Edit backend/src/line/webhook.py
# Add custom message processing logic
```

## Deployment

### Development Environment
- Use `develop` branch
- Environment: `ENVIRONMENT=development`
- Debug logging enabled

### Staging Environment
- Create `release/v0.0.1` branch
- Environment: `ENVIRONMENT=staging`
- Real API keys required

### Production Environment
- Use `main` branch
- Environment: `ENVIRONMENT=production`
- Google Cloud Secret Manager recommended
- SSL/TLS required for LINE webhook

## Monitoring

The application includes comprehensive monitoring:

- **Health Checks**: `/health` endpoint
- **Metrics API**: Performance and usage statistics
- **Structured Logging**: JSON logs with correlation IDs
- **AI Provider Monitoring**: Response times and error rates
- **Cache Analytics**: Hit rates and performance

## Security

- ✅ LINE webhook signature verification
- ✅ JWT-based authentication
- ✅ Environment variable secret management
- ✅ Optional Google Cloud Secret Manager
- ✅ Public repository security (no secrets committed)
- ✅ Rate limiting and request validation

## Contributing

1. Fork the repository
2. Create feature branch from `develop`
3. Make changes and test locally
4. Submit pull request to `develop` branch

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
- Create an issue on GitHub
- Check the API documentation at `/docs`
- Review logs for debugging information

---

**Ready to build intelligent LINE chatbots! 🚀**

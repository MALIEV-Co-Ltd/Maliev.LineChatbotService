# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive Python LINE chatbot service for a 3D printing business, featuring multi-provider AI integration, dynamic system instructions, intelligent caching, and customer management. The system uses Gemini 2.5-flash as the primary LLM with fallbacks to OpenAI, DeepSeek, and other providers.

## Architecture Overview

### Core Components
- **FastAPI Backend**: Modern async Python web framework
- **Multi-Provider AI System**: Abstracted layer supporting multiple LLM providers
- **LINE Integration**: Webhook-based chatbot using line-bot-sdk-python v3
- **Customer Management**: Persistent customer profiles and interaction history
- **Dynamic Instructions**: Context-aware system prompts for 3D printing business
- **Multi-Level Caching**: Intelligent LLM response caching (40-70% cost reduction)
- **Admin UI**: React/Next.js dashboard for system management
- **Configuration**: Redis + Google Secret Manager hybrid storage

### Technology Stack
- **Backend**: FastAPI, Redis, Google Secret Manager, sentence-transformers
- **AI Providers**: google-genai (Gemini 2.5-flash), openai, custom providers
- **Frontend**: Next.js 14+, Tailwind CSS, shadcn/ui, Monaco Editor
- **Database**: Redis for caching, sessions, and configuration
- **Deployment**: GitOps with GitHub Actions workflows

## Development Environment Setup

### Prerequisites
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r backend/requirements-dev.txt
```

### Environment Variables
Required environment variables (managed via Google Secret Manager):
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `GEMINI_API_KEY`
- `OPENAI_API_KEY`
- `REDIS_URL`
- `GOOGLE_CLOUD_PROJECT`

### Local Development
```bash
# Backend development
cd backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Frontend development
cd frontend
npm run dev

# Full stack with Docker Compose
docker-compose up -d
```

## Common Commands

### Backend Development
- `uvicorn src.main:app --reload` - Start FastAPI development server
- `pytest` - Run all tests
- `pytest tests/test_ai/` - Run AI provider tests
- `pytest --cov=src` - Run tests with coverage
- `ruff check src/` - Lint codebase
- `mypy src/` - Type checking

### Frontend Development
- `npm run dev` - Start Next.js development server
- `npm run build` - Build for production
- `npm run test` - Run frontend tests
- `npm run lint` - Lint frontend code

### Testing
- `pytest tests/test_integration/` - Integration tests
- `pytest tests/test_cache/` - Cache system tests
- `pytest tests/test_customers/` - Customer management tests

## Project Structure

### Backend (`backend/src/`)
```
├── ai/                    # Multi-provider AI abstraction
│   ├── providers/         # Gemini, OpenAI, DeepSeek, Grok providers
│   ├── strategies/        # Routing, fallback, load balancing
│   └── utils/            # Token counting, cost calculation
├── instructions/          # Dynamic system instruction system
├── cache/                # Multi-level LLM caching
├── customers/            # Customer management and analytics
├── api/v1/               # Admin API endpoints
├── handlers/             # LINE webhook handlers
├── services/             # Business logic services
└── config/               # Configuration and secrets management
```

### Frontend (`frontend/src/`)
```
├── components/
│   ├── ai-models/        # AI provider management UI
│   ├── instructions/     # Instruction editor and testing
│   ├── cache/           # Cache analytics and management
│   ├── customers/       # Customer management interface
│   └── dashboard/       # Main dashboard components
└── pages/               # Next.js pages and routing
```

## Key Features

### 1. Multi-Provider AI Management
- **Primary**: Gemini 2.5-flash for main conversations
- **Fallbacks**: OpenAI GPT-4, DeepSeek, Grok for reliability
- **Smart Routing**: Cost and performance-based provider selection
- **Real-time Monitoring**: Provider health and performance tracking

### 2. Dynamic System Instructions
- **Context Analysis**: Detects 3D printing, CNC, scanning domains
- **Business Workflows**: Specialized instructions for quote processes
- **Customer Personalization**: Instructions adapt to customer history
- **Real-time Updates**: Instructions update without restart

### 3. Customer Management
- **Persistent Profiles**: Store customer contact info, preferences
- **Project History**: Track all customer projects and orders
- **Auto-extraction**: Extract customer info from conversations
- **Segmentation**: VIP, active, new customer categorization

### 4. LLM Caching System
- **Exact Match**: Cache identical queries
- **Semantic Match**: Cache similar questions (different wording)
- **Pattern Match**: Cache common question patterns
- **Cost Savings**: 40-70% reduction in LLM API costs

### 5. Admin UI Features
- **AI Provider Dashboard**: Monitor all AI providers
- **Instruction Editor**: Monaco-based editor for system prompts
- **Cache Analytics**: Performance metrics and cost savings
- **Customer Management**: Full customer lifecycle management
- **Real-time Monitoring**: WebSocket updates for live data

## Configuration Management

### Redis Configuration Keys
```
chatbot:config:model:{model_id}        # Model parameters (temperature, etc.)
chatbot:config:routing:{rule_name}     # Routing rules
chatbot:instruction:{instruction_id}   # System instructions
chatbot:customer:{customer_id}         # Customer data
llm_cache:exact:{hash}                # Exact match cache
llm_cache:semantic:{hash}             # Semantic similarity cache
```

### Model Configuration Example
```python
# Dynamic temperature adjustment
await config_service.update_model_config("gemini-2.5-flash", {
    "temperature": 0.8,
    "max_tokens": 2048,
    "top_p": 0.9
})
```

### Instruction Management
```python
# Add new instruction
instruction = SystemInstruction(
    id="3d_printing_quote",
    name="3D Printing Quote Process",
    type="workflow",
    content="When customer asks for quote...",
    triggers=["quote", "price", "cost"],
    domains=["3d_printing"]
)
await instruction_service.save_instruction(instruction)
```

## Monitoring and Analytics

### Health Checks
- `GET /health` - Application health
- `GET /health/redis` - Redis connectivity
- `GET /health/providers` - AI provider status

### Metrics Endpoints
- `GET /metrics` - Prometheus metrics
- `GET /api/v1/analytics/cache` - Cache performance
- `GET /api/v1/analytics/customers` - Customer analytics

### Logging
- Structured JSON logging with correlation IDs
- Customer interaction tracking
- AI provider usage metrics
- Cost tracking per conversation

## Security Considerations

- **API Keys**: Stored in Google Secret Manager
- **Authentication**: JWT tokens for admin UI
- **Validation**: LINE webhook signature verification
- **Rate Limiting**: Configurable limits for API endpoints
- **Customer Data**: Encrypted at rest in Redis

## Troubleshooting

### Common Issues
1. **Redis Connection**: Check `REDIS_URL` environment variable
2. **AI Provider Errors**: Check provider API keys in Secret Manager
3. **LINE Webhook**: Verify webhook URL and signature validation
4. **Cache Performance**: Monitor hit rates in admin dashboard

### Debug Commands
```bash
# Check Redis connectivity
redis-cli -u $REDIS_URL ping

# Test AI provider directly
python -c "from src.ai.providers.gemini_provider import GeminiProvider; print('OK')"

# Validate LINE webhook signature
curl -X POST localhost:8000/webhook -H "X-Line-Signature: ..." -d '{...}'
```

This architecture provides a production-ready, scalable LINE chatbot specifically optimized for 3D printing business operations with comprehensive admin controls and cost optimization features.
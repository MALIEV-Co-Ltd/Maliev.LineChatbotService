# CI/CD Workflows

This directory contains GitHub Actions workflows for the LINE Chatbot Service deployment pipeline.

## Workflow Structure

### 🔧 Development (`dev-deploy.yml`)
- **Trigger**: Push to `develop` branch
- **Environment**: Development
- **Registry**: `maliev-website-artifact-dev`
- **URL**: https://dev.line-chatbot.maliev.com
- **Tag Format**: `dev-YYYYMMDD-{commit-hash}`
- **Purpose**: Continuous deployment for active development

### 🎯 Staging (`staging-deploy.yml`) 
- **Trigger**: Push to `release/v*` branches
- **Environment**: Staging (Release Candidate)
- **Registry**: `maliev-website-artifact-staging`
- **URL**: https://staging.line-chatbot.maliev.com
- **Tag Format**: `{version}-rc-YYYYMMDD-{commit-hash}`
- **Purpose**: Release candidate testing before production

### 🚀 Production (`prod-deploy.yml`)
- **Trigger**: Push to `main` branch or version tags (`v*`)
- **Environment**: Production
- **Registry**: `maliev-website-artifact`
- **URL**: https://line-chatbot.maliev.com
- **Tag Format**: `{version}` or `v{YYYY.MM.DD}-{HHMM}-{commit-hash}`
- **Purpose**: Production deployments with GitHub releases

## Branching Strategy

```
develop ────────────────► Development Environment
    │
    └─► release/v1.0.0 ──► Staging Environment
            │
            └─► main ────► Production Environment
                  │
                  └─► v1.0.0 tag ──► GitHub Release
```

## Required Secrets

Configure these secrets in your GitHub repository:

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | Google Cloud Service Account JSON key |
| `GITOPS_TOKEN` | GitHub Personal Access Token for GitOps repo access |

## Workflow Features

- ✅ **Testing**: Linting, type checking, and unit tests
- 🐳 **Docker**: Multi-stage builds with health checks
- 📦 **Artifact Registry**: Environment-specific registries
- 🔄 **GitOps**: Automatic manifest updates
- 📊 **Coverage**: Codecov integration
- 🏷️ **Releases**: Automatic GitHub releases for production tags
- 🔍 **Verification**: Post-deployment health checks

## Usage Examples

### Development Deployment
```bash
git checkout develop
git add .
git commit -m "feat: add new feature"
git push origin develop
# Triggers dev-deploy.yml → deploys to dev.line-chatbot.maliev.com
```

### Staging Deployment (Release Candidate)
```bash
git checkout -b release/v1.2.0 develop
git push origin release/v1.2.0
# Triggers staging-deploy.yml → deploys to staging.line-chatbot.maliev.com
```

### Production Deployment
```bash
# Option 1: Merge to main
git checkout main
git merge release/v1.2.0
git push origin main
# Triggers prod-deploy.yml → deploys to line-chatbot.maliev.com

# Option 2: Create version tag
git tag v1.2.0
git push origin v1.2.0
# Triggers prod-deploy.yml + creates GitHub release
```

## Registry Naming Convention

- **Development**: `asia-southeast1-docker.pkg.dev/maliev-website/maliev-website-artifact-dev/maliev-line-chatbot-service`
- **Staging**: `asia-southeast1-docker.pkg.dev/maliev-website/maliev-website-artifact-staging/maliev-line-chatbot-service`  
- **Production**: `asia-southeast1-docker.pkg.dev/maliev-website/maliev-website-artifact/maliev-line-chatbot-service`

## GitOps Integration

All workflows automatically update the corresponding Kustomization files in the GitOps repository:
- `3-apps/line-chatbot-service/overlays/development/kustomization.yaml`
- `3-apps/line-chatbot-service/overlays/staging/kustomization.yaml`
- `3-apps/line-chatbot-service/overlays/production/kustomization.yaml`
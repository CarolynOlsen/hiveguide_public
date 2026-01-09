# HiveScribe CI/CD Guide

## Overview

HiveScribe uses GitHub Actions for continuous integration across three platforms:
- **Backend (Python/FastAPI)** - API tests with PostgreSQL + pgvector
- **Web App (React Native Web/Webpack)** - Build and TypeScript validation
- **iOS Mobile (React Native)** - TypeScript checks and iOS build validation

Deployment to Railway happens automatically on merge to `main` (configured in Railway dashboard).

---

## Current Workflows

### 1. `ci.yml` - Cross-Platform CI Pipeline ✅

**Triggers:**
- Pull requests to `main` or `develop` branches
- Pushes to `main` or `develop` branches

**Jobs:**

#### **backend-tests** (Ubuntu)
Tests the FastAPI backend with PostgreSQL database.

**What it does:**
- Sets up Python 3.12.9
- Installs PostgreSQL with pgvector extension
- Installs system dependencies (tesseract-ocr for RAG)
- Installs Python dependencies from `backend/requirements.txt` and `requirements-dev.txt`
- Tests new import structure (`from backend.main import app`)
- Runs code quality checks (flake8)
- Runs Alembic database migrations
- Executes backend test suite (`python backend/tests/run_tests.py`)
- Validates RAG system imports and database tables

**Environment Variables Used:**
- `DATABASE_URL` - PostgreSQL connection (CI uses local instance)
- `OPENAI_API_KEY` - Falls back to fake key if secret not set
- `OPENROUTER_API_KEY` - Falls back to fake key if secret not set

#### **web-build** (Ubuntu)
Builds the React web application.

**What it does:**
- Sets up Node.js 20
- Installs dependencies from `web/package-lock.json` (uses npm cache)
- Runs `npm run build` in web directory
- Verifies `web/dist/` directory exists
- Uploads build artifacts (retained for 7 days)

#### **shared-typecheck** (Ubuntu)
Validates shared TypeScript code.

**What it does:**
- Validates `shared/types.ts` compiles correctly
- Uses strict TypeScript compiler settings
- Ensures type definitions are error-free

#### **mobile-typecheck** (Ubuntu)
Checks mobile app TypeScript compilation.

**What it does:**
- Sets up Node.js 20
- Installs dependencies from `mobile/package-lock.json` (uses npm cache)
- Runs `npx tsc --noEmit` to check TypeScript without building
- Runs Jest tests (currently passes with no tests)

#### **ios-build** (macOS 14)
Validates iOS app builds successfully.

**What it does:**
- Sets up Node.js 20 and installs mobile dependencies
- Sets up Ruby 3.2 with Bundler cache
- Installs CocoaPods dependencies (`pod install --repo-update`)
- Lists available iOS simulators
- Builds app in Debug configuration for iPhone 15 simulator
- Uses `CODE_SIGNING_ALLOWED=NO` to skip code signing in CI
- Pipes output through xcpretty for readable logs
- Uploads build logs on failure

**Note:** iOS builds may show warnings in CI - this is normal. The job passes if the build completes.

#### **integration-summary** (Ubuntu)
Final check that all critical jobs passed.

**What it does:**
- Runs after all other jobs complete (uses `needs` and `if: always()`)
- Prints status of each job
- Fails if any critical job failed
- Provides clear summary for PR status checks

---

## Required GitHub Secrets

### Optional (Backend Testing)
These secrets enable full backend functionality in CI. If not set, fake keys are used (tests still pass).

| Secret Name | Purpose | How to Get |
|------------|---------|------------|
| `OPENAI_API_KEY` | OpenAI API for RAG embeddings | https://platform.openai.com/api-keys |
| `OPENROUTER_API_KEY` | OpenRouter for LLM calls | https://openrouter.ai/keys |

**To add secrets:**
```
GitHub Repository → Settings → Secrets and variables → Actions → New repository secret
```

**Current Behavior:**
- If secrets are set: Full RAG testing with real API calls
- If secrets are NOT set: Tests use fake keys (RAG operations skipped)

---

## Workflow Status Badges

Add these to your `README.md` to show build status:

```markdown
[![CI Status](https://github.com/CarolynOlsen/hivescribe/actions/workflows/ci.yml/badge.svg)](https://github.com/CarolynOlsen/hivescribe/actions/workflows/ci.yml)
```

---

## Testing Locally Before Push

### Backend Tests
```bash
# From project root
cd backend
python tests/run_tests.py
```

### Web Build
```bash
cd web
npm ci
npm run build
```

### Mobile TypeScript Check
```bash
cd mobile
npm ci
npx tsc --noEmit
```

### iOS Build (macOS only)
```bash
cd mobile/ios
pod install
xcodebuild \
  -workspace HiveScribeiOS.xcworkspace \
  -scheme HiveScribeiOS \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 15' \
  clean build \
  CODE_SIGNING_ALLOWED=NO
```

---

## Deployment Process

### Web App to Railway 🚀

**Automatic on merge to `main`:**
1. Railway detects push to `main` branch
2. Railway builds backend and web app
3. Web build copied to `backend/static/`
4. Backend deployed with new static files
5. Available at production URL

**Railway Configuration:**
- Build command: `cd web && npm install && npm run build && cp -r dist/* ../backend/static/`
- Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Environment variables set in Railway dashboard

**No GitHub Actions workflow needed** - Railway handles deployment automatically.

---

## Troubleshooting

### Backend Tests Fail

**Issue:** `ModuleNotFoundError: No module named 'backend'`

**Solution:** Ensure all imports use the new structure:
```python
# Correct
from backend.main import User, Hive
from backend.rag.config import RAG_CONFIG

# Incorrect (old structure)
from main import User, Hive
from rag.config import RAG_CONFIG
```

---

**Issue:** Database connection fails

**Solution:** The PostgreSQL service may be slow to start. The workflow includes a health check and retry logic. If issues persist, increase the wait time in the workflow.

---

**Issue:** RAG tests fail

**Solution:** 
- RAG tests are non-blocking in CI (warnings only)
- Ensure `SKIP_RAG_INIT=1` environment variable is set for import tests
- Real RAG functionality requires actual API keys

---

### Web Build Fails

**Issue:** Build completes but `dist/` directory missing

**Solution:**
- Check Webpack configuration in `web-rn/webpack.config.js`
- Ensure build script is `webpack --mode production` in `web-rn/package.json`
- Check for TypeScript errors blocking build

---

**Issue:** Dependencies fail to install

**Solution:**
- Delete `web-rn/package-lock.json` locally and run `npm install --legacy-peer-deps`
- Commit new `package-lock.json`
- CI uses `npm ci` which requires a valid lockfile

---

### Mobile TypeScript Fails

**Issue:** TypeScript compilation errors

**Solution:**
- Run `cd mobile && npx tsc --noEmit` locally to see errors
- Check `mobile/tsconfig.json` configuration
- Ensure `shared/types.ts` is valid
- Verify all imports resolve correctly

---

### iOS Build Fails

**Issue:** Pod install fails

**Solution:**
```bash
cd mobile/ios
rm -rf Pods Podfile.lock
pod install --repo-update
```

---

**Issue:** Xcode build fails with signing errors

**Solution:** CI uses `CODE_SIGNING_ALLOWED=NO` to skip signing. If this fails:
- Check Xcode project settings
- Ensure no hardcoded signing configurations
- Verify scheme is set to "Automatically manage signing"

---

**Issue:** Simulator not found

**Solution:**
- The workflow lists available simulators before building
- Check the log output for available devices
- Update the `-destination` parameter to match available simulator

---

### Integration Summary Fails

**Issue:** Summary shows "Some checks failed"

**Solution:**
- Check the status of each individual job
- Click on failed job to see detailed logs
- Fix the underlying issue in that specific platform

---

## Best Practices

### 1. Branch Protection Rules

Configure in **Repository Settings → Branches → Branch protection rules** for `main`:

- ✅ Require pull request before merging
- ✅ Require status checks to pass before merging
  - Select: `backend-tests`, `web-build`, `mobile-typecheck`, `shared-typecheck`
- ✅ Require branches to be up to date before merging
- ✅ Require conversation resolution before merging
- ⚠️ Optional: Require signed commits

### 2. Commit Messages

Use conventional commits for clarity:
```
feat: add hive sharing to mobile app
fix: resolve iOS build issue with CocoaPods
chore: update dependencies
docs: improve README with setup instructions
test: add backend API tests
```

### 3. Pull Request Workflow

1. Create feature branch from `main`
2. Make changes and commit
3. Push to GitHub
4. Open pull request
5. **Wait for CI to pass** ✅
6. Request review
7. Address feedback
8. Merge when approved and CI passes

### 4. Dependency Updates

**Backend (Python):**
```bash
pip install --upgrade -r backend/requirements.txt
pip freeze > backend/requirements.txt
```

**Web (npm):**
```bash
cd web
npm update
npm audit fix
```

**Mobile (npm):**
```bash
cd mobile
npm update
npm audit fix
cd ios && pod update && cd ..
```

### 5. Database Migrations

Always test migrations locally before pushing:
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Test upgrade
alembic upgrade head

# Test downgrade
alembic downgrade -1

# Re-upgrade
alembic upgrade head
```

CI automatically tests migrations on every push.

---

## Monitoring & Debugging

### View Workflow Runs
1. Go to **Actions** tab in GitHub repository
2. Click on workflow run to see details
3. Click on individual jobs to see logs
4. Download artifacts (build logs, compiled apps) if available

### Build Artifacts
- **Web build** artifacts available for 7 days
- **iOS build logs** available only on failure
- Download from workflow run page

### Notifications
Set up notifications in **Profile → Settings → Notifications**:
- ✅ Email on workflow failure
- ✅ GitHub UI notifications

---

## Future Enhancements

### Planned Additions
- [ ] Android build validation
- [ ] E2E testing with Detox (mobile)
- [ ] Visual regression testing (web)
- [ ] Performance benchmarks
- [ ] Security scanning (Dependabot, CodeQL)
- [ ] TestFlight deployment workflow (manual trigger)
- [ ] Automated version bumping

### TestFlight Deployment (Future)
When ready for iOS distribution, we'll add:
- Manual workflow trigger
- App Store Connect API integration
- Automatic IPA generation and upload
- Build number auto-increment

---

## Questions & Support

**CI failing?** Check this guide's troubleshooting section.

**New to GitHub Actions?** See [GitHub Actions Documentation](https://docs.github.com/en/actions)

**iOS build issues?** See [React Native iOS Setup](https://reactnative.dev/docs/environment-setup)

**Need help?** Check workflow logs for detailed error messages.

---

## Changelog

### 2025-10-01: Cross-Platform CI Update
- ✅ Split monolithic job into platform-specific jobs
- ✅ Added iOS build validation on macOS runners
- ✅ Added shared TypeScript validation
- ✅ Updated backend imports for new structure
- ✅ Added integration summary job
- ✅ Improved caching for faster builds
- ✅ Added build artifact uploads

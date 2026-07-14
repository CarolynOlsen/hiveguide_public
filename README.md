# HiveGuide

A cross-platform beekeeping management application with voice transcription, AI analysis, and intelligent advising. Available as a web app and native iOS app, both powered by a shared FastAPI backend.

After the original author's family developed severe bee allergies, this project transitioned from private to open source. The app has been used on a trial basis for several months to manage multiple hives and inspections, and was released to internal testers on TestFlight (iOS).

**What makes this unique:** HiveGuide solves the practical challenges of field inspections -- your hands are full, covered in propolis, or wearing thick gloves, yet you need to capture detailed observations for later analysis. Voice transcription enables hands-free data entry, AI extraction structures that data automatically (identifying queen sightings, brood patterns, pest signs), and an intelligent advisor helps you apply domain-specific knowledge when you need it most.

The AI advisor uses a multi-source RAG architecture that routes queries between personal inspection history and authoritative literature. The routing strategy was systematically evaluated against six alternatives and documented in `publications/strategies_comparison.pdf`.

**Beyond beekeeping:** While built for beekeeping, this architecture could be applied to any domain requiring field inspections that rely heavily on past data and niche domain knowledge -- agriculture, equipment maintenance, environmental monitoring, etc.

## Demos

These recordings are shown at 2x speed, for those of us with short attention spans.

### Homepage and New Inspection

Here you can see a new inspection with near-real-time transcription. When the user clicks "Analyze," the AI reviews their field notes and auto-populates selections for structured fields. 

https://github.com/user-attachments/assets/13b0f68b-c19e-4221-bd21-0bfc1d7a3c28

### AI Assistant Use

This recording has been edited to reduce the time waiting for a response. The recording was made with the app using the `gpt-oss-120b` model via OpenRouter, for its balance of low cost with high quality -- but the latency is slow.

https://github.com/user-attachments/assets/9a7c07f5-b7e5-44ad-bf7d-9a030a54bfb5


At the end of the recording you can see that a clicked reference link takes the user to the specific relevant page in that source.

## Platform Support

This project started as a web app only. However, keeping your hands free during a beehive inspection is key: you're handling bees, may have gloves on, may have fingers covered in propolis. That made the transcription aspect especially important. With the web app, we aren't able to stream audio to the service for near-real-time transcription, meaning it all sends at once and then transcribes. That can cause issues for long inspections. Using a native iOS app, we can send audio in short chunks and provide near-real-time transcription, giving the user rapid feedback and reducing the risk of a failure to send one of those chunks (vs. the entire inspection). And thus the iOS app was born, and we migrated from React.js to React Native.

The app has not yet been expanded to Android.

- **Web App**: React Native Web (unified with iOS codebase)
- **iOS App**: React Native app for iPhone and iPad  
- **Shared Backend**: FastAPI REST API serves both platforms
- **Code Sharing**: Screens and components are shared between web and iOS

## Features

### Core Features
- **Voice Recording**: Record hive inspections using your device's microphone
- **Near Real-time Streaming Transcription (iOS)**: See your speech transcribed with ~2 second delay as you speak during inspections
- **AI Transcription**: Near real-time streaming speech-to-text via AssemblyAI (iOS), with OpenAI Whisper for batch transcription (web, and as the iOS fallback)
- **Smart Analysis**: AI-powered extraction of hive data (eggs, brood, resources)
- **Photo Uploads**: Attach photos to inspections (camera or library on iOS)
- **AI Advisor**: Intelligent RAG chatbot that combines personal hive data with beekeeping knowledge
- **Hives & Inspections**: Organize inspections by hive; hives belong to users, inspections belong to hives
- **Hive Sharing**: Create circles to share hives with other beekeepers
- **Authentication**: Secure password authentication with admin approval
- **Admin Panel**: Manage user approvals (iOS only currently)
- **Mobile Optimized**: Native iOS app and responsive web design

### Streaming Transcription Features (iOS Only)
- **Near Real-time Transcription**: Words appear with ~2 second delay as you speak, powered by AssemblyAI's streaming speech-to-text API
- **Direct Streaming**: Audio streams from the app straight to AssemblyAI over a WebSocket. The backend only mints short-lived access tokens (`POST /api/assembly-ai-token`), so raw audio never passes through our server
- **Automatic Fallback**: Gracefully switches to batch transcription (OpenAI Whisper via `POST /transcribe`) if streaming is unavailable
- **Network Resilient**: Handles connection issues with automatic reconnection and token refresh

See `mobile/AUDIO_TESTING_GUIDE.md` for setup instructions.

## AI Assistant Architecture

The HiveGuide AI Assistant uses an advanced RAG (Retrieval-Augmented Generation) system that intelligently combines your personal hive data with authoritative beekeeping knowledge to provide personalized advice.

### Why This Design?

Multi-source RAG systems face a fundamental routing problem: given a query, which data source(s) should be queried—structured databases, unstructured document corpora, or both? This system uses an **LLM-based intent classifier** that pre-classifies queries before routing them to specialized tools.

This design was validated through systematic comparison of seven routing strategies (LLM classifier, heuristic classifier, embedding similarity router, supervised classifier, agent-based approaches, and always-both baseline) across 501 validation queries. The evaluation measured retrieval accuracy, response quality, latency, and cost. Key findings:

- **LLM classifiers** provide a solid balance of context relevance and response groundedness
- **Supervised classifiers** achieve highest classification accuracy (97.8%) when training data is available
- **Heuristic classifiers** minimize latency and cost with acceptable accuracy
- **Agent-based approaches** achieve highest context relevance but require significant engineering effort to address reliability issues

The LLM classifier approach was selected for HiveGuide because it provides strong semantic understanding without requiring training data, achieves competitive latency (~1s classification overhead), and delivers well-grounded responses that properly cite sources. See `publications/strategies_comparison.pdf` for the full evaluation.

### System Flow

```mermaid
flowchart TD
    A[User Query: Is my hive at normal weight for October?] --> B[Intent Classifier LLM]
    
    B --> C{Question Type?}
    C -->|Personal Data| D[User Hive Data Tool]
    C -->|General Knowledge| E[Document Search Tool]  
    C -->|Combined| F[Both Tools]
    
    D --> G[PostgreSQL Database]
    G --> H[Personal Hive Data: Inspection records, Weights, Queen status, Action items, Photos]
    
    E --> I[Vector Database pgvector]
    I --> J[Beekeeping Documents: Extension guidelines, Best practices, Technical references]
    
    F --> K[LangChain Agent gpt-oss-120b]
    H --> K
    J --> K
    
    K --> L[Response Validation]
    L --> M{Valid Response?}
    M -->|No| N[Retry with Enhanced Prompt]
    M -->|Yes| O[Strategic Response Generation]
    
    N --> K
    O --> P[Final Answer with Sources]
```

### How It Works

1. **Intent Classification**: Every question is analyzed by the configured LLM (`gpt-oss-120b` via OpenRouter by default, set in `backend/rag/config.py`) to understand what type of information you're seeking:
   - **Personal queries**: "Which of my hives need attention?" 
   - **General knowledge**: "What are signs of varroa mites?"
   - **Combined queries**: "Is the weight of my Franksville 4 hive adequate for winter?"

2. **Smart Tool Selection**: Based on your question, the system chooses the right data sources:
   - **User Hive Data Tool**: SQL queries to PostgreSQL for your inspection records, weights, photos, and notes
   - **Document Search Tool**: Vector similarity search through authoritative beekeeping literature
   - **Combined Approach**: Uses both when you need personal recommendations based on factual criteria

3. **LangChain Agent Processing**: An intelligent agent processes your question using:
   - Strategic reasoning about what information to gather first
   - Multiple tool calls if needed for complex questions
   - Context awareness from previous conversation turns

4. **Response Validation**: Every answer is validated to ensure:
   - Personal questions include specific hive names, dates, and measurements
   - Factual claims are properly cited with document sources
   - No generic advice when specific data is available

5. **Source Attribution**: All responses include structured citations:
   - Document sources with page numbers and titles
   - Relevance-based ranking of sources
   - Only sources above similarity threshold are displayed

### Example Interactions

**Personal Data Query:**
- **You ask**: "Which of my hives should I be worried about for winter weight?"
- **System**: Uses User Hive Data Tool → finds Franksville 4 (74 lbs) and Franksville 5 (68 lbs)
- **Response**: "Franksville 4 (74 lbs) and Franksville 5 (68 lbs) are below the recommended 80-100 lb range..."

**Combined Knowledge Query:**
- **You ask**: "What's the recommended winter weight and how do my hives compare?"
- **System**: Uses Document Search Tool for standards + User Hive Data Tool for your data
- **Response**: "The recommended winter weight is 80-100 pounds (Source: Virginia Tech Extension). Your Franksville 4 (74 lbs)..."

## Project Architecture

### Component Platform Matrix

This table shows which components are used by each platform, helping you understand the impact of changes:

**Note:** The repository includes some scaffolded Android files in `mobile/android/`, but there is no functional Android app at this time.

| Component | Web | iOS | Description |
|-----------|-----|-----|-------------|
| **Backend** |
| `backend/main.py` | ✓ | ✓ | FastAPI REST API - all endpoints |
| `backend/rag/` | ✓ | ✓ | AI Advisor/RAG system (via API) |
| `backend/utils/llm_analyzer.py` | ✓ | ✓ | Inspection analysis (via API) |
| `backend/alembic/` | ✓ | ✓ | Database migrations |
| `backend/scripts/` | ✓ | ✓ | Admin utilities (DB-level) |
| `backend/tests/` | ✓ | ✓ | API endpoint tests |
| **Frontend - React Native (Shared Screens & Logic)** |
| `mobile/src/` | ✓ | ✓ | **Shared React Native code (Web + iOS):** |
| `├─ screens/` | ✓ | ✓ | Screen components **shared by web and mobile** |
| `├─ components/` | ✓ | ✓ | Reusable UI components |
| `├─ navigation/` | ✓ | ✓ | Navigation configuration |
| `├─ contexts/` | ✓ | ✓ | React contexts for state management |
| `├─ services/` | ✓ | ✓ | API integration layer |
| `├─ hooks/` | ✓ | ✓ | Custom React hooks |
| `mobile/ios/` | | ✓ | **iOS-specific native code:** |
| `├─ HiveGuideiOS.xcworkspace` | | ✓ | Xcode workspace file |
| `├─ HiveGuideiOS.xcodeproj/` | | ✓ | Xcode project configuration |
| `├─ HiveGuideiOS/` | | ✓ | Native iOS source files |
| `│  ├─ AppDelegate.swift` | | ✓ | iOS app lifecycle |
| `│  ├─ AudioStreamingModule.swift/.m` | | ✓ | Native audio capture bridge for streaming transcription |
| `│  ├─ Info.plist` | | ✓ | iOS app permissions & config |
| `│  ├─ Images.xcassets` | | ✓ | App icons & launch images |
| `├─ Podfile` | | ✓ | CocoaPods dependency management |
| `├─ Pods/` | | ✓ | iOS native dependencies |
| `mobile/package.json` | | ✓ | React Native dependencies |
| `mobile/metro.config.js` | | ✓ | Metro bundler configuration |
| `mobile/babel.config.js` | | ✓ | Babel transpiler configuration |
| `mobile/tsconfig.json` | | ✓ | TypeScript configuration |
| **Shared Code** |
| `shared/types.ts` | ✓ | ✓ | TypeScript type definitions |
| `shared/api-client.ts` | ✓ | ✓ | API client interface |
| `shared/platform/` | ✓ | ✓ | Platform adapters (storage, audio) |
| `shared/components/` | ✓ | ✓ | Platform-aware components (DatePicker, ImagePicker) |
| `shared/theme/` | ✓ | ✓ | Unified design system |
| `config.yaml` | ✓ | | Local dev config (gitignored) |
| `alembic.ini` | ✓ | ✓ | Database migration config |
| `requirements.txt` | ✓ | ✓ | Python backend dependencies |
| **Deployment** |
| `Procfile` | ✓ | ✓ | Railway deployment config |
| `Dockerfile` | ✓ | ✓ | Docker container config |
| `backend/scripts/launch_app.sh` | ✓ | | Local web dev launcher (Mac) |
| `backend/scripts/launch_app.bat` | ✓ | | Local web dev launcher (Windows) |

### Understanding the Matrix

**Platform Support Indicators:**
- ✓ = Currently supported and actively used
- (empty) = Not applicable to this platform

**Backend components:**
- All backend components support all platforms since they provide a unified REST API
- Database schema changes require migrations that affect all platforms
- API endpoint changes need coordinated updates across all client platforms

**Shared React Native code (`mobile/src/`):**
- **NOW USED BY BOTH WEB AND IOS** via React Native Web
- Written in TypeScript with React Native primitives
- Changes here affect **both web and mobile platforms**
- Platform-specific features use Platform API or platform adapters
- Screens, navigation, state management fully shared

**Platform adapters (`shared/platform/`, `shared/components/`):**
- Provide unified APIs with platform-specific implementations
- Examples: DatePicker (HTML5 input vs native), ImagePicker (file input vs camera)
- Web build automatically uses `.web.tsx`, mobile uses `.native.tsx`
- Changes require testing on both platforms

**Platform-specific native code:**
- `mobile/ios/`: iOS-only (Xcode projects, CocoaPods, Swift/Objective-C bridges)
- `web-rn/`: Web-specific build configuration (Webpack, entry point)
- Changes here only affect the specific platform

**Shared TypeScript code:**
- Type definitions and API client used by all platforms
- Changes require testing on web and iOS

## Quick Start

### Web App (React Native Web) - Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/CarolynOlsen/hiveguide_public.git
   cd hiveguide_public
   ```

2. **Install Python dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Mac/Linux
   # OR: venv\Scripts\activate  # On Windows
   
   pip install -r backend/requirements.txt
   pip install -r backend/requirements-dev.txt  # For testing
   ```

3. **Set up local configuration**
   ```bash
   # Create config.yaml in project root (this file is gitignored)
   # See config.yaml.example for all supported keys
   cat > config.yaml << EOF
   database_url: postgresql://user:pass@host:port/dbname
   openai_api_key: sk-your-key-here          # Whisper batch transcription + inspection analysis
   openrouter_api_key: sk-or-your-key-here   # AI Advisor / RAG LLM
   assembly_ai_api_key: your-assemblyai-key  # iOS near real-time streaming transcription
   EOF
   ```

4. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

5. **Launch the web application**
   ```bash
   # Mac/Linux:
   ./backend/scripts/launch_app.sh
   
   # Windows:
   backend\scripts\launch_app.bat
   ```
   
   This script will:
   - Build the React Native Web frontend (web-rn/)
   - Copy built files to `backend/static/`
   - Start the FastAPI backend
   - Open at http://127.0.0.1:8000

6. **Create admin user** (first time only)
   ```bash
   python backend/scripts/create_admin.py
   ```

### iOS App (React Native) - Local Development

1. **Prerequisites**
   - Xcode 15+ installed
   - iOS Simulator or physical iOS device
   - Node.js and npm installed

2. **Install dependencies**
   ```bash
   cd mobile
   npm ci
   cd ios
   pod install
   cd ../..
   ```

3. **Configure API endpoint**
   - For local testing: Update API base URL in mobile app to `http://localhost:8000`
   - For production: Use Railway backend URL

4. **Build and run**
   ```bash
   cd mobile
   npx react-native run-ios --simulator="iPhone 15"
   # OR for physical device:
   npx react-native run-ios --device="Your Device Name"
   ```

## Testing

### Backend Tests

```bash
# Run all backend tests with coverage
pytest backend/tests -q

# Run specific test file
pytest backend/tests/test_main.py -v

# Run with coverage report
pytest backend/tests/ --cov=backend --cov-report=html
```

### Web Frontend Tests

```bash
cd web-rn
npm run test:ci
```

### iOS App Tests

```bash
cd mobile
npm test

# Or in Xcode: Cmd+U
```

## Deployment

### Railway Deployment (Backend + Web)

1. **Set environment variables in Railway:**
   ```
   DATABASE_URL=postgresql://...  (automatically set by Railway)
   OPENAI_API_KEY=sk-...          (Whisper batch transcription + inspection analysis)
   OPENROUTER_API_KEY=sk-or-...   (AI Advisor / RAG LLM)
   ASSEMBLY_AI_API_KEY=...        (mints tokens for iOS near real-time streaming transcription)
   ```

2. **Deploy:**
   - Push to `main` branch triggers auto-deploy
   - Railway builds both backend and web frontend
   - `Procfile` specifies: `web: uvicorn backend.main:app --host=0.0.0.0 --port=8000`

3. **Migrations:**
   ```bash
   # Run migrations on Railway
   railway run alembic upgrade head
   ```

### iOS App Deployment

1. **Update backend URL** in `mobile/src/config` or environment
2. **Build in Xcode:**
   - Open `mobile/ios/HiveGuideiOS.xcworkspace`
   - Select "Any iOS Device" or connected device
   - Product > Archive
3. **Distribute via TestFlight or App Store**

## Platform-Specific Features

### Web Only
- Drag-and-drop file uploads
- Browser-based audio recording
- Responsive desktop layouts

### iOS Only
- Native camera integration
- Photo library picker
- Native navigation (bottom tabs, stack navigation)
- Haptic feedback
- iOS permissions (camera, photo library)
- Admin approval panel (not yet implemented on web)
- Near real-time streaming transcription

### Shared Features
- User authentication & sessions
- Hive management with photos
- Inspection recording with voice transcription
- AI-powered analysis
- AI Advisor/RAG chatbot
- Hive sharing via circles
- Past inspection viewing

## Project Structure

```
hiveguide_public/
├── backend/                    # Python FastAPI backend (Web ✓ iOS ✓)
│   ├── main.py                # REST API endpoints
│   ├── requirements.txt       # Python dependencies
│   ├── rag/                   # RAG/AI Advisor system
│   │   ├── langchain_service.py  # LangChain agent implementation
│   │   ├── user_data_tool.py     # SQL tool for personal data
│   │   └── config.py             # RAG configuration
│   ├── utils/                 # Utility functions
│   │   └── llm_analyzer.py   # Inspection analysis
│   ├── alembic/               # Database migrations
│   ├── scripts/               # Admin & dev tools
│   │   ├── launch_app.sh     # Web dev launcher (builds web-rn)
│   │   ├── launch_app.bat    # Windows launcher
│   │   ├── create_admin.py
│   │   └── ...
│   ├── tests/                 # Backend tests
│   └── static/                # Built React Native Web app (from web-rn/dist/)
│
├── web-rn/                     # React Native Web frontend (Web ✓)
│   ├── src/
│   │   ├── index.web.tsx     # Web entry point
│   │   └── navigation/       # Web-specific navigation setup
│   ├── tests/                 # Playwright smoke tests
│   ├── public/
│   │   └── index.html        # HTML template
│   ├── webpack.config.js      # Webpack build config
│   ├── tsconfig.json          # TypeScript config
│   └── package.json           # Web dependencies
│
├── mobile/                     # React Native app (iOS ✓)
│   ├── src/                   # **SHARED WITH WEB** (via React Native Web)
│   │   ├── screens/          # ✓ Shared screens (web + iOS)
│   │   ├── components/       # ✓ Shared components
│   │   ├── navigation/       # ✓ Shared navigation logic
│   │   ├── contexts/         # ✓ Shared state management
│   │   ├── services/         # ✓ Shared API client
│   │   └── hooks/            # ✓ Shared custom hooks
│   ├── ios/                   # iOS native code (iOS only)
│   │   ├── HiveGuideiOS.xcodeproj
│   │   ├── HiveGuideiOS.xcworkspace
│   │   ├── HiveGuideiOS/     # AppDelegate, AudioStreamingModule (streaming transcription), Info.plist
│   │   ├── Podfile           # CocoaPods dependencies
│   │   └── ...
│   ├── android/               # Android starter files (not functional)
│   ├── App.tsx               # Root component (iOS)
│   └── package.json           # React Native dependencies
│
├── shared/                     # Shared code (Web ✓ iOS ✓)
│   ├── types.ts              # TypeScript type definitions
│   ├── api-client.ts         # API client interface
│   ├── platform/             # Platform adapters
│   │   ├── storage.ts        # localStorage (web) vs AsyncStorage (native)
│   │   └── audio/            # MediaRecorder (web) vs native recording
│   ├── components/           # Platform-aware components
│   │   ├── DatePicker.web.tsx    # HTML5 date input
│   │   ├── DatePicker.native.tsx # Native picker
│   │   ├── ImagePicker.web.tsx   # File input
│   │   └── ImagePicker.native.tsx# Camera/library
│   └── theme/                # Unified design system
│       └── index.ts
│
├── validation/                 # RAG strategy evaluation
│   ├── run_strategy_validation.py  # Evaluation harness
│   ├── queries/               # Test queries
│   ├── results/               # Evaluation results
│   └── services/              # Strategy implementations
│
├── publications/               # Research papers
│   └── strategies_comparison.pdf  # RAG routing evaluation
│
├── config.yaml                 # Local dev config (gitignored)
├── alembic.ini                # Database migration config
├── nixpacks.toml              # Railway build config
├── requirements-dev.txt       # Dev dependencies
├── Procfile                   # Railway deployment
└── README.md                  # This file
```

**Key Architecture Points:**

1. **`mobile/src/screens/`** → Used by BOTH web and iOS
2. **`web-rn/`** → Web build configuration only (Webpack, entry point)
3. **`shared/components/`** → Platform-specific implementations with shared API
4. **100% screen code sharing** between web and iOS

### Development Workflow

**For Screen/UI Changes (Affects Both Web & iOS!):**
1. Modify files in `mobile/src/screens/` or `mobile/src/components/`
2. **Test on BOTH platforms:**
   - Web: `cd web-rn && npm run dev` → http://localhost:3000
   - iOS: `cd mobile && npm run ios` → iOS Simulator
3. Changes appear on both platforms automatically!

**For Web-Specific Changes:**
1. Modify `web-rn/webpack.config.js`, `web-rn/src/navigation/`, etc.
2. Run `cd web-rn && npm run dev`
3. Test at http://localhost:3000

**For iOS-Specific Changes:**
1. Modify files in `mobile/ios/` (native code)
2. Run `npx react-native run-ios` 
3. Test in iOS Simulator or device

**For Platform Adapters:**
1. Modify `shared/components/*.web.tsx` or `*.native.tsx`
2. **Test both implementations:**
   - Web: Browser testing
   - iOS: Simulator/device testing
3. Ensure API compatibility between platforms

**For Backend/API Changes:**
1. Modify files in `backend/`
2. Update `shared/types.ts` if API contracts change
3. **Test ALL platforms** (web, iOS)
4. Run backend tests: `pytest backend/tests -q`

**For Shared Code Changes:**
1. Modify files in `shared/`
2. **Test both web and iOS apps**
3. Ensure TypeScript types are compatible with both platforms

### API Endpoints

All endpoints are shared between web and iOS platforms.

#### Authentication
- `POST /register` — Register new user (requires admin approval)
- `POST /login` — Login with email/password (sets session cookie)
- `POST /logout` — Logout current user
- `GET /auth/status` — Check authentication status
- `GET /auth/me` — Get current user info

#### Hives
- `POST /hives` — Create a new hive (**multipart/form-data**: nickname, location, description, photo)
- `GET /hives` — List hives for the current user
- `GET /hives/{hive_id}` — Get specific hive details
- `PUT /hives/{hive_id}` — Update hive
- `DELETE /hives/{hive_id}` — Delete hive

#### Inspections
- `POST /inspections` — Create inspection (**multipart/form-data**: hive_id, transcription, notes, photos[], etc.)
- `GET /inspections` — List inspections (optional `?hive_id=...` filter)
- `GET /inspections/{inspection_id}` — Get specific inspection
- `POST /analyze_text` — Analyze transcription text with AI

#### Circles (Hive Sharing)
- `GET /circles` — List user's circles
- `POST /circles` — Create new circle
- `DELETE /circles/{circle_id}` — Delete circle
- `POST /circles/{circle_id}/members` — Add member to circle
- `DELETE /circles/{circle_id}/members/{user_id}` — Remove member

#### AI Advisor
- `GET /rag/status` — Check RAG system status
- `POST /rag/query` — Query AI Advisor with question

#### Admin (Admin users only)
- `GET /admin/users` — List all users
- `POST /admin/users/{user_id}/approve` — Approve user
- `POST /admin/users/{user_id}/reject` — Reject user

## Known Issues & Roadmap

### Current Issues
- **Circles (Hive Sharing)**: Circles let beekeepers share hives and inspections. The backend endpoints are fully implemented, and the iOS app can create, list, and delete circles (**More → Hive Sharing**). However, adding and removing circle *members* is not yet wired up in the app UI, so end-to-end sharing isn't functional yet. This feature originated in the earlier React.js web version.
- **Web App Navigation**: Some pages are missing the bottom navigation bar. Web only.

### Potential Future Development

Contributors could tackle these roadmap items:
- Android app support
- Web admin panel
- Offline mode for mobile
- Push notifications for action items
- Hive analytics dashboard
- Export inspection reports

## Contributing & Cross-Platform Development

### Making Changes That Affect Multiple Platforms

When developing features that touch both web and iOS:

1. **Define API contract first** in `shared/types.ts`
2. **Implement backend endpoint** in `backend/main.py`
3. **Add backend tests** in `backend/tests/`
4. **Update API client** interface in `shared/api-client.ts`
5. **Implement shared UI** in `mobile/src/screens/` (affects both platforms!)
6. **Test both platforms** thoroughly

### Common Pitfalls

**Don't:**
- Change API response format without updating both frontends
- Add platform-specific logic to shared code
- Skip testing on one platform
- Use platform-specific dependencies in shared code

**Do:**
- Keep backend and frontends in sync
- Use feature flags for gradual rollouts
- Document platform differences
- Test API changes with both clients

## Additional Documentation

- `mobile/README.md` - Mobile app development guide
- `mobile/AUDIO_TESTING_GUIDE.md` - Audio/transcription testing
- `backend/rag/README_SOURCES.md` - RAG document sources
- `backend/scripts/README_TEST_DATA.md` - Test data generation
- `publications/strategies_comparison.pdf` - RAG routing evaluation research

## License

Creative Commons No Commercial - see [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Carolyn Olsen

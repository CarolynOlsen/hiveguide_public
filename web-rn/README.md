# HiveGuide React Native Web

This directory contains the React Native Web implementation of HiveGuide, consolidating the web and mobile apps into a single codebase.

## Architecture

- **Platform**: React Native Web (shares code with iOS app)
- **Build Tool**: Webpack 5
- **TypeScript**: Full type safety
- **State Management**: React Query + Context
- **Navigation**: React Navigation v7
- **Styling**: React Native StyleSheet (cross-platform)

## Development

```bash
# Install dependencies
npm install --legacy-peer-deps

# Start development server (port 3000)
npm run dev

# Build for production
npm run build

# TypeScript check
npm run typecheck

# Lint
npm run lint
```

## Platform Adapters

The `shared/platform/` directory contains adapters for platform-specific features:

- **Storage**: `localStorage` (web) vs `AsyncStorage` (native)
- **Audio Recording**: `MediaRecorder` (web) vs native iOS streaming

## Shared Code

- **Screens**: Reused from `mobile/src/screens/`
- **Components**: Reused from `mobile/src/`
- **API Client**: Shared via `shared/api-client.ts`
- **Types**: Shared via `shared/types.ts`
- **Theme**: Unified design system in `shared/theme/`

## Migration Status

### Phase 1: Foundation ✅
- [x] React Native Web dependencies installed
- [x] Webpack build system configured
- [x] Platform adapters created (storage, audio)
- [x] Unified theme system
- [x] CI pipeline integration
- [x] TypeScript configuration

### Phase 2: Screen Migration (In Progress)
- [ ] Login screen
- [ ] Dashboard screen
- [ ] Hives screen
- [ ] Inspection form screen
- [ ] Chat screen
- [ ] Admin screen
- [ ] Add hive screen

### Phase 3: Navigation
- [ ] App navigator setup
- [ ] Auth flow
- [ ] Tab navigation
- [ ] Stack navigation

### Phase 4: Production
- [ ] Deployment scripts
- [ ] Railway configuration
- [ ] Archive old web app
- [ ] Performance optimization

## Known Issues

### Build Issues (In Progress)
- Some mobile dependencies (DateTimePicker, ImagePicker) need web alternatives
- Need to create platform-specific component stubs for native-only features

### Solutions
- DateTimePicker: Use `<input type="date">` for web
- ImagePicker: Use `<input type="file">` for web
- Native modules: Platform.OS checks with web fallbacks

## Browser Support

- Chrome/Edge (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)

## Dependencies

Aligned with mobile app to maximize code sharing:
- React 19.1.0
- React Native Web 0.19.12
- React Navigation 7.x
- React Query 5.x
- React Hook Form 7.x

# Shared Platform-Aware Components

This directory contains components with **platform-specific implementations** but a **unified API**.

## How It Works

### Automatic Platform Selection

Webpack (web) and Metro (mobile) automatically select the correct file based on extension:

```
DatePicker.web.tsx    ← Used in web builds
DatePicker.native.tsx ← Used in iOS/Android builds
DatePicker.d.ts       ← Shared TypeScript types (optional)
```

### Usage (Same for All Platforms)

```typescript
// In any screen (web or mobile):
import { DateTimePicker } from '@shared/components';

// Use the same API:
<DateTimePicker
  value={date}
  onChange={handleDateChange}
  mode="date"
/>
```

## Components

### DatePicker

**Web Implementation** (`DatePicker.web.tsx`):
- Uses HTML5 `<input type="date">` 
- Native browser date picker
- No external dependencies

**Native Implementation** (`DatePicker.native.tsx`):
- Uses `@react-native-community/datetimepicker`
- Native iOS/Android date picker
- Platform-specific styling

**Shared Props:**
```typescript
interface DatePickerProps {
  value: Date;
  onChange: (event: any, date?: Date) => void;
  mode?: 'date' | 'time' | 'datetime';
  maximumDate?: Date;
  minimumDate?: Date;
}
```

### ImagePicker

**Web Implementation** (`ImagePicker.web.tsx`):
- Uses HTML5 `<input type="file" accept="image/*">`
- Supports camera capture via `capture` attribute
- Returns blob URLs for preview

**Native Implementation** (`ImagePicker.native.tsx`):
- Uses `react-native-image-picker`
- Native camera and photo library access
- Returns local file URIs

**Shared API:**
```typescript
launchCamera(options, callback)
launchImageLibrary(options, callback)
```

## Why This Structure?

### Alternative Approaches Considered

❌ **Option 1: Platform checks in consuming code**
```typescript
// BAD: Duplicated logic in every screen
import DatePicker from 'react-native-web' ? WebDatePicker : NativeDatePicker;
```

❌ **Option 2: Separate import paths**
```typescript
// BAD: Different imports for each platform
import { DatePicker } from '@web/components';  // Web
import { DatePicker } from '@mobile/components'; // iOS
```

✅ **Option 3: Shared location with platform extensions** (Current)
```typescript
// GOOD: Single import, automatic selection
import { DatePicker } from '@shared/components';
```

### Benefits

1. **DRY**: No duplicated import statements across screens
2. **Maintainable**: Change implementation without touching consuming code
3. **Type-safe**: Shared TypeScript interfaces ensure API compatibility
4. **Automatic**: Build tools handle platform selection
5. **Testable**: Can mock imports for testing

## Adding New Platform-Aware Components

1. **Create both implementations:**
   ```
   shared/components/
   ├── MyComponent.web.tsx      # Web implementation
   ├── MyComponent.native.tsx   # iOS/Android implementation
   └── MyComponent.d.ts         # Shared types (optional)
   ```

2. **Export from index.ts:**
   ```typescript
   export * from './MyComponent';
   ```

3. **Use in screens:**
   ```typescript
   import { MyComponent } from '@shared/components';
   ```

## Testing

### Web (Jest + Testing Library)
```bash
cd web-rn
npm test -- MyComponent.web.test.tsx
```

### Mobile (Jest + React Native Testing Library)
```bash
cd mobile
npm test -- MyComponent.native.test.tsx
```

## When NOT to Use This Pattern

Use regular shared components (no .web/.native suffix) when:
- ✅ Component works identically on all platforms
- ✅ Only uses cross-platform React Native primitives (View, Text, etc.)
- ✅ No platform-specific APIs needed

Examples: Simple UI components like cards, buttons, text formatters.

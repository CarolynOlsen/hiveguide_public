# iOS Audio Testing Guide

This guide explains the automated testing workflow for debugging iOS audio functionality in HiveGuide.

## The Problem We're Solving

Previously, testing audio on iOS required:
1. Make code change
2. Build in Xcode (~5 min)
3. Install on physical device (~2 min)
4. Manually test by clicking Record
5. App crashes
6. Manually hunt for crash logs in Xcode
7. Repeat

**Total time per iteration: ~15 minutes** 😫

## The Solution

Three automated scripts that reduce feedback loop to **~2 minutes**:

1. **Pre-flight checks** - Catch configuration issues before building
2. **Enhanced logging** - Automatic crash diagnosis
3. **Automated device testing** - One command to build, install, test, and capture diagnostics

## Quick Start

### Option 1: Full Automated Test (Recommended)

```bash
# From mobile/ directory
bash scripts/test_audio_on_device.sh
```

This single command:
- ✅ Checks device connection
- ✅ Builds the app
- ✅ Installs on device
- ✅ Captures runtime logs
- ✅ Takes screenshot
- ✅ Detects and exports crash reports
- ✅ Saves everything to `~/Desktop/hiveguide_test_results/`

**Time: ~2 minutes**

### Option 2: Pre-flight Checks Only

```bash
# From mobile/ directory
bash ios/scripts/audio_preflight.sh
```

Quick validation (10 seconds) to catch:
- Missing files
- Permission configuration
- TypeScript errors
- Module registration issues
- CocoaPods problems

### Option 3: Manual Test with Log Streaming

```bash
# Terminal 1: Start log streaming
xcrun devicectl device log stream \
  --device 00008140-000E49991E63001C \
  --predicate 'subsystem == "com.hiveguide.audio"' \
  | tee ~/Desktop/audio_logs.txt

# Terminal 2: Build and install normally
cd mobile && npm run ios:device
```

## Understanding the Output

### When Tests Complete Successfully

You'll see output saved to `~/Desktop/hiveguide_test_results/TIMESTAMP/`:

```
hiveguide_test_results/
└── 20250116_143022/
    ├── TEST_SUMMARY.txt      # Overview of test run
    ├── build_log.txt          # Full Xcode build output
    ├── install_log.txt        # Installation log
    ├── launch_log.txt         # App launch output
    ├── runtime_log.txt        # All logs from the app
    ├── filtered_errors.txt    # Just the error messages
    ├── screenshot.png         # What the app looks like
    ├── crash_report.txt       # Detailed crash analysis (if crashed)
    └── crash_list.txt         # All crashes on device
```

### Reading the Logs

The enhanced logging shows **exactly where** the code gets to before crashing:

```
[AudioInfo] ========== START STREAMING CALLED ==========
[AudioDebug] Parameters - sampleRate: 16000, chunkDuration: 300
[AudioInfo] Running on physical device - attempting audio streaming
[AudioDebug] Streaming check passed, beginning audio session setup
[AudioDebug] Step 1: Getting audio session instance
[AudioDebug] Step 2: Checking microphone permission - status: 3
[AudioInfo] ✅ Microphone permission granted
[AudioDebug] Step 3: Setting audio session category to .record
[AudioInfo] ✅ Audio session category set
[AudioDebug] Step 4: Activating audio session
[AudioInfo] ✅ Audio session activated
[AudioDebug] Step 5: Waiting 0.2s for audio session to stabilize
[AudioDebug] Step 6: Creating AVAudioEngine instance
[AudioInfo] ✅ Audio engine created
[AudioDebug] Step 7: Getting input node from audio engine
[AudioInfo] ✅ Input node obtained
[AudioDebug] Step 8: Verifying input node format and channels
[AudioDebug] Input format - channels: 1, sampleRate: 48000.0, format: ...
[AudioInfo] ✅ Input node has 1 channels at 48000.0Hz
[AudioDebug] Step 9: Creating recording format (PCM Int16, 16000Hz, mono)
[AudioInfo] ✅ Recording format created: ...
[AudioDebug] Step 10: Calculated buffer size: 4800 frames (0.3s chunks)
[AudioDebug] Step 11: Installing audio tap on input node (THIS IS WHERE CRASHES TYPICALLY OCCUR)
[AudioInfo] About to call inputNode.installTap() - buffer: 4800, format: ...
```

**If it crashes**, the last line tells you exactly where. If you see "Step 11" logged but not the next line, the crash happened in `installTap()`.

### Crash Report Analysis

If a crash occurs, `crash_report.txt` will contain:

```
Exception Type:  EXC_BAD_ACCESS (SIGSEGV)
Exception Codes: KERN_INVALID_ADDRESS at 0x0000000000000000
Crashed Thread:  5

Thread 5 Crashed:
0   AVFAudio                     0x1a5e8a3c4 AVAudioInputNode.installTap...
1   HiveGuideiOS                0x102a1b234 AudioStreamingModule.startStreaming...
2   HiveGuideiOS                0x102a1b5c8 @objc AudioStreamingModule.startStreaming...
```

This immediately shows:
1. **What failed**: `AVAudioInputNode.installTap` (the audio tap installation)
2. **Where in our code**: `AudioStreamingModule.startStreaming` at line 177
3. **Why**: `KERN_INVALID_ADDRESS` (null pointer or bad memory access)

## Common Issues and Solutions

### Issue 1: "Device not connected"

**Symptom**: Script fails immediately with "Device not connected"

**Solution**:
```bash
# Check if device is visible
xcrun xctrace list devices

# If not listed, try:
# 1. Unplug and replug USB cable
# 2. Unlock iPhone
# 3. Trust this computer (popup on iPhone)
# 4. Check USB cable is data-capable (not charge-only)
```

### Issue 2: "Build failed"

**Symptom**: Build fails before installation

**Solution**:
```bash
# Run pre-flight checks
bash ios/scripts/audio_preflight.sh

# Common fixes:
cd ios && pod install  # If CocoaPods issue
cd .. && npm install   # If dependencies issue

# Clean build
rm -rf ios/build ios/Pods
cd ios && pod install && cd ..
```

### Issue 3: "Cannot find crash report"

**Symptom**: App crashes but no crash report in output

**Solution**:
1. Wait 30 seconds after crash (crash reports are written async)
2. Re-run the script - it will pick up the crash report
3. Manually check: Settings > Privacy & Security > Analytics & Improvements > Analytics Data on iPhone

### Issue 4: Logs show "Permission denied"

**Symptom**: Logs show microphone permission error

**Solution**:
1. Go to iPhone Settings > Privacy & Security > Microphone
2. Find "Hive Guide" and toggle ON
3. Restart the app

### Issue 5: Metro bundler conflicts

**Symptom**: "Port 8081 already in use"

**Solution**:
```bash
# Kill existing Metro processes
lsof -ti:8081 | xargs kill -9

# Or use the helper
pkill -f metro
```

## Workflow for Debugging a Crash

Here's the recommended debugging workflow:

### 1. First Test Run - Gather Data
```bash
bash scripts/test_audio_on_device.sh
```

Wait for completion, then check:
- `screenshot.png` - What does the UI look like?
- `filtered_errors.txt` - Any obvious errors?
- `crash_report.txt` - Did it crash? Where?

### 2. Analyze the Logs

Open `runtime_log.txt` and find the last checkpoint:
```bash
# Quick way to see the last few log entries
tail -50 ~/Desktop/hiveguide_test_results/*/runtime_log.txt | grep AudioInfo
```

This tells you exactly which step succeeded before the crash.

### 3. Make Targeted Fix

Based on the last successful step, you know:
- **Stopped at Step 2**: Permission issue
- **Stopped at Step 6**: Audio engine creation issue
- **Stopped at Step 11**: Audio tap installation issue (most common)
- **Stopped at Step 12**: Audio engine start issue

### 4. Test the Fix

```bash
# Quick validation before full test
bash ios/scripts/audio_preflight.sh

# Full test
bash scripts/test_audio_on_device.sh
```

### 5. Compare Results

```bash
# Compare before/after logs
diff ~/Desktop/hiveguide_test_results/20250116_143022/runtime_log.txt \
     ~/Desktop/hiveguide_test_results/20250116_144530/runtime_log.txt
```

## Advanced Usage

### Stream Logs in Real-Time

Watch logs as the app runs:
```bash
xcrun devicectl device log stream \
  --device 00008140-000E49991E63001C \
  --predicate 'subsystem == "com.hiveguide.audio"'
```

### Get Only Crash Reports

```bash
# List all crashes
xcrun devicectl device info crashlogs list \
  --device 00008140-000E49991E63001C | grep HiveGuide

# Get specific crash
xcrun devicectl device info crashlogs show \
  --device 00008140-000E49991E63001C \
  <CRASH_NAME>
```

### Take Screenshots During Testing

```bash
xcrun devicectl device info screenshot \
  --device 00008140-000E49991E63001C \
  ~/Desktop/test_screenshot.png
```

### Filter Logs by Severity

```bash
# Only show errors
grep -i "AudioError" runtime_log.txt

# Only show info
grep -i "AudioInfo" runtime_log.txt

# Show progression through steps
grep "Step [0-9]" runtime_log.txt
```

## Integration with Development Workflow

### Add to package.json

```json
{
  "scripts": {
    "test:audio": "bash scripts/test_audio_on_device.sh",
    "preflight": "bash ios/scripts/audio_preflight.sh"
  }
}
```

Then use:
```bash
npm run preflight  # Quick check
npm run test:audio # Full test
```

### Before Every Commit

```bash
# Validate before committing
npm run preflight && git commit -m "Fix audio issue"
```

### Continuous Testing

While developing, keep this running in a terminal:
```bash
# Watch for file changes and auto-test
while true; do
  fswatch -1 ios/HiveGuideiOS/AudioStreamingModule.swift
  echo "File changed, running tests..."
  npm run test:audio
done
```

## Troubleshooting the Scripts

### Script Permission Errors

```bash
# Make scripts executable
chmod +x mobile/scripts/test_audio_on_device.sh
chmod +x mobile/ios/scripts/audio_preflight.sh
```

### devicectl Not Found

```bash
# Requires Xcode 15+ command line tools
xcode-select --install

# Or update Xcode Command Line Tools:
# Xcode > Settings > Locations > Command Line Tools
```

### Logs Are Empty

If `runtime_log.txt` is empty:
1. Check device is unlocked during test
2. Verify subsystem name matches: `com.hiveguide.audio`
3. Try broader predicate: `processImagePath CONTAINS "HiveGuide"`

## Next Steps

Once you have this working:

1. **For each crash**, you'll immediately see:
   - Exact line where crash occurs
   - State of audio system before crash
   - Full stack trace with symbols

2. **For each fix attempt**, you can:
   - Compare before/after logs
   - See exactly how behavior changed
   - Know if fix worked within 2 minutes

3. **Share diagnostics** by sending the test results folder:
   ```bash
   zip -r audio_test_results.zip ~/Desktop/hiveguide_test_results/LATEST/
   ```

## FAQ

**Q: Do I need to run Metro separately?**
A: No, the test script doesn't require Metro. It builds a Release configuration that bundles JS.

**Q: Can I test on simulator?**
A: No, audio hardware requires a physical device. The script will fail if device isn't connected.

**Q: How do I test a specific feature?**
A: Modify the test wait time in the script (currently 10 seconds). Or manually test after the script installs, then check logs.

**Q: Can I automate the "click Record button" part?**
A: Not easily. The script gets you to a running app, then you manually test. Use screenshot to verify state.

**Q: Will this work on someone else's iPhone?**
A: Yes, but update `DEVICE_ID` in both scripts to their device UUID:
```bash
# Find their device UUID
xcrun xctrace list devices | grep iPhone
```

## Summary

**Before**: 15 minutes per test iteration, manual crash hunting
**After**: 2 minutes per test iteration, automatic crash capture and analysis

The key is **enhanced logging** that tells you exactly where the code fails, and **automation** that eliminates manual steps.

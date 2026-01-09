# Audio Testing Quick Reference

## One-Command Full Test
```bash
cd mobile && bash scripts/test_audio_on_device.sh
```
**Results**: `~/Desktop/hiveguide_test_results/TIMESTAMP/`

---

## Pre-Flight Check Only
```bash
cd mobile && bash ios/scripts/audio_preflight.sh
```

---

## Read Latest Test Results
```bash
# Summary
cat ~/Desktop/hiveguide_test_results/*/TEST_SUMMARY.txt | tail -20

# Crash report (if crashed)
cat ~/Desktop/hiveguide_test_results/*/crash_report.txt | tail -50

# Last few log entries
tail -30 ~/Desktop/hiveguide_test_results/*/runtime_log.txt

# View screenshot
open ~/Desktop/hiveguide_test_results/*/screenshot.png

# Errors only
cat ~/Desktop/hiveguide_test_results/*/filtered_errors.txt
```

---

## Live Log Streaming
```bash
xcrun devicectl device log stream \
  --device 00008140-000E49991E63001C \
  --predicate 'subsystem == "com.hiveguide.audio"'
```

---

## Common Fixes

### Device not found
```bash
# Check connection
xcrun xctrace list devices | grep -i iphone

# Reconnect: unplug, unlock phone, replug, trust computer
```

### Build fails
```bash
cd mobile/ios
rm -rf build Pods Podfile.lock
pod install
cd ..
```

### Metro conflict
```bash
lsof -ti:8081 | xargs kill -9
```

---

## Log Interpretation

### What the logs tell you:
```
[AudioDebug] Step 1: ...     ← Setup phase
[AudioInfo] ✅ ...            ← Successful checkpoint
[AudioError] ❌ ...           ← Error occurred
```

### Where it crashed:
**Last log = last successful step before crash**

- Stops at Step 2 → Permission issue
- Stops at Step 7 → Input node issue
- Stops at Step 11 → **Audio tap installation** (most common)
- Stops at Step 12 → Engine start issue

---

## File Locations

- Test script: `mobile/scripts/test_audio_on_device.sh`
- Preflight: `mobile/ios/scripts/audio_preflight.sh`
- Swift code: `mobile/ios/HiveGuideiOS/AudioStreamingModule.swift`
- Results: `~/Desktop/hiveguide_test_results/`
- Full guide: `mobile/AUDIO_TESTING_GUIDE.md`

---

## Debugging Workflow

1. **Run test**: `bash scripts/test_audio_on_device.sh`
2. **Check crash**: `cat ~/Desktop/hiveguide_test_results/*/crash_report.txt`
3. **Find last step**: `grep "Step" ~/Desktop/hiveguide_test_results/*/runtime_log.txt | tail -1`
4. **Make fix** in AudioStreamingModule.swift
5. **Repeat**: Go to step 1

---

## Share Results with Claude

```bash
# Latest test results
LATEST=$(ls -t ~/Desktop/hiveguide_test_results/ | head -1)
echo "Test from: $LATEST"
cat ~/Desktop/hiveguide_test_results/$LATEST/TEST_SUMMARY.txt
cat ~/Desktop/hiveguide_test_results/$LATEST/filtered_errors.txt
cat ~/Desktop/hiveguide_test_results/$LATEST/crash_report.txt
```

Then paste the output to me for analysis.

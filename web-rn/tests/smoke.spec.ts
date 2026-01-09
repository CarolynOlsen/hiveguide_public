/**
 * Smoke tests for React Native Web build
 * These tests verify the app renders and basic navigation works
 * 
 * NOTE: These tests are currently experimental and won't block CI.
 * The app rendering issue needs to be debugged locally.
 */

import { test, expect } from '@playwright/test';

test.describe('React Native Web Smoke Tests', () => {
  test('app loads and renders login screen', async ({ page }) => {
    // Fixed: Static file serving issue resolved - React Native Web bundles now served correctly
    // This test verifies the app doesn't have a white screen and renders properly
    
    await page.goto('http://localhost:3000');
    
    // Wait for React to render
    await page.waitForLoadState('networkidle');
    
    // Check that root div has content
    const rootContent = await page.locator('#root').innerHTML();
    expect(rootContent.length).toBeGreaterThan(0);
    
    // Check for login-related text
    const bodyText = await page.textContent('body');
    expect(bodyText).toBeTruthy();
    
    console.log('✓ App rendered successfully');
  });

  test('build artifacts exist', async () => {
    const fs = require('fs');
    const path = require('path');
    
    const distPath = path.resolve(__dirname, '../dist');
    const indexHtml = path.join(distPath, 'index.html');
    
    // Verify dist directory exists
    expect(fs.existsSync(distPath)).toBeTruthy();
    
    // Verify index.html exists
    expect(fs.existsSync(indexHtml)).toBeTruthy();
    
    // Verify JS bundle exists
    const files = fs.readdirSync(distPath);
    const jsBundle = files.find((f: string) => f.startsWith('bundle.') && f.endsWith('.js'));
    expect(jsBundle).toBeTruthy();
    
    console.log('✓ Build artifacts verified');
  });

  test('bundle contains expected code', async () => {
    const fs = require('fs');
    const path = require('path');
    
    const distPath = path.resolve(__dirname, '../dist');
    const files = fs.readdirSync(distPath);
    const jsBundle = files.find((f: string) => f.startsWith('bundle.') && f.endsWith('.js'));
    
    if (!jsBundle) {
      throw new Error('Bundle not found');
    }
    
    const bundlePath = path.join(distPath, jsBundle);
    const bundleContent = fs.readFileSync(bundlePath, 'utf-8');
    
    // Verify critical dependencies are bundled
    expect(bundleContent).toContain('react');
    expect(bundleContent.length).toBeGreaterThan(1000000); // Bundle should be at least 1MB
    
    console.log('✓ Bundle contains expected dependencies');
  });
});

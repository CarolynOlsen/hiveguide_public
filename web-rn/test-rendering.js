const puppeteer = require('puppeteer');

async function testRendering() {
  let browser;
  try {
    console.log('🚀 Starting browser test...');
    browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    
    // Listen for console messages
    page.on('console', msg => {
      console.log('🟢 Browser console:', msg.text());
    });
    
    // Listen for errors
    page.on('error', err => {
      console.log('❌ Browser error:', err.message);
    });
    
    page.on('pageerror', err => {
      console.log('❌ Page error:', err.message);
    });
    
    console.log('📱 Navigating to app...');
    await page.goto('http://localhost:8000', { waitUntil: 'networkidle2', timeout: 10000 });
    
    // Wait for React to render
    await page.waitForTimeout(2000);
    
    // Check if content rendered
    const content = await page.content();
    const bodyText = await page.evaluate(() => document.body.innerText);
    
    console.log('📄 Page title:', await page.title());
    console.log('🎯 Body text (first 200 chars):', bodyText.substring(0, 200));
    
    // Check for specific elements
    const hasRootDiv = await page.$('#root');
    const hasScript = content.includes('bundle.');
    const hasLoginScreen = bodyText.includes('Login Screen');
    
    console.log(`✅ Root div found: ${!!hasRootDiv}`);
    console.log(`✅ Bundle script loaded: ${hasScript}`);
    console.log(`✅ Login screen rendered: ${hasLoginScreen}`);
    
    if (hasLoginScreen) {
      console.log('🎉 SUCCESS: React Native Web app is rendering!');
      return { success: true, message: 'App rendering successfully' };
    } else {
      console.log('❌ FAILURE: App not rendering properly');
      return { success: false, message: 'App not rendering', bodyText };
    }
    
  } catch (error) {
    console.log('❌ Test failed:', error.message);
    return { success: false, error: error.message };
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

testRendering().then(result => {
  console.log('\n=== FINAL RESULT ===');
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.success ? 0 : 1);
});
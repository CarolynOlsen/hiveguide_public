const puppeteer = require('puppeteer');

async function testRequireErrors() {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  
  const errors = [];
  const logs = [];
  
  // Capture console errors
  page.on('console', (msg) => {
    const text = msg.text();
    logs.push(text);
    if (text.includes('require') || text.includes('ReferenceError')) {
      errors.push(text);
    }
  });
  
  // Capture JavaScript errors
  page.on('pageerror', (err) => {
    errors.push(err.message);
  });
  
  try {
    // Navigate to the page
    await page.goto('http://localhost:8000', { waitUntil: 'networkidle0', timeout: 10000 });
    
    // Wait a bit for any async errors
    await page.waitForTimeout(2000);
    
    // Check if React app rendered
    const hasReactContent = await page.$eval('body', (body) => {
      return body.textContent.includes('React Native Web') || 
             body.textContent.includes('MINIMAL') ||
             body.textContent.length > 10;
    }).catch(() => false);
    
    console.log('=== TEST RESULTS ===');
    console.log(`React content rendered: ${hasReactContent}`);
    console.log(`Total console messages: ${logs.length}`);
    console.log(`Require-related errors: ${errors.length}`);
    
    if (errors.length > 0) {
      console.log('\n=== ERRORS ===');
      errors.forEach((error, i) => {
        console.log(`${i + 1}. ${error}`);
      });
    }
    
    if (logs.length > 0) {
      console.log('\n=== ALL LOGS ===');
      logs.forEach((log, i) => {
        console.log(`${i + 1}. ${log}`);
      });
    }
    
    return { hasContent: hasReactContent, errorCount: errors.length, errors, logs };
    
  } catch (error) {
    console.error('Test failed:', error.message);
    return { hasContent: false, errorCount: 1, errors: [error.message], logs };
  } finally {
    await browser.close();
  }
}

testRequireErrors().then(result => {
  process.exit(result.errorCount > 0 ? 1 : 0);
});
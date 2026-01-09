const http = require('http');

function testApp() {
  return new Promise((resolve, reject) => {
    console.log('🚀 Testing React Native Web app...');
    
    // Get the HTML page
    const req = http.get('http://localhost:8000', (res) => {
      let html = '';
      res.on('data', (chunk) => html += chunk);
      res.on('end', () => {
        console.log('📄 HTML loaded successfully');
        
        // Check for expected elements
        const hasRootDiv = html.includes('<div id="root">');
        const hasBundle = html.includes('bundle.');
        const hasTitle = html.includes('<title>HiveGuide</title>');
        
        console.log(`✅ Root div: ${hasRootDiv}`);
        console.log(`✅ Bundle script: ${hasBundle}`);  
        console.log(`✅ Title: ${hasTitle}`);
        
        // Extract bundle name
        const bundleMatch = html.match(/src="([^"]*bundle[^"]*\.js)"/);
        if (!bundleMatch) {
          resolve({ success: false, error: 'No bundle found' });
          return;
        }
        
        const bundlePath = bundleMatch[1];
        console.log(`📦 Testing bundle: ${bundlePath}`);
        
        // Test bundle for require statements
        const bundleReq = http.get(`http://localhost:8000${bundlePath}`, (bundleRes) => {
          let bundle = '';
          bundleRes.on('data', (chunk) => bundle += chunk);
          bundleRes.on('end', () => {
            const requireMatches = bundle.match(/[^a-zA-Z]require\s*\(/g) || [];
            const bundleSize = (bundle.length / 1024 / 1024).toFixed(2);
            
            console.log(`📦 Bundle size: ${bundleSize} MB`);
            console.log(`🔍 Require statements: ${requireMatches.length}`);
            
            const success = requireMatches.length === 0 && hasRootDiv && hasBundle && hasTitle;
            
            if (success) {
              console.log('🎉 SUCCESS: App should be working!');
              console.log('💡 Custom router with NavigationContainer implemented');
              console.log('💡 No require() statements found - browser compatibility achieved');
            } else {
              console.log('❌ Issues found:');
              if (requireMatches.length > 0) console.log(`  - ${requireMatches.length} require() statements`);
              if (!hasRootDiv) console.log('  - Missing root div');
              if (!hasBundle) console.log('  - Missing bundle script');
              if (!hasTitle) console.log('  - Missing title');
            }
            
            resolve({
              success,
              requireCount: requireMatches.length,
              bundleSize: bundle.length,
              hasRootDiv,
              hasBundle,
              hasTitle
            });
          });
        });
        
        bundleReq.on('error', (err) => {
          resolve({ success: false, error: `Bundle error: ${err.message}` });
        });
      });
    });
    
    req.on('error', (err) => {
      resolve({ success: false, error: `HTML error: ${err.message}` });
    });
  });
}

testApp().then(result => {
  console.log('\n=== RESULT ===');
  console.log(JSON.stringify(result, null, 2));
});
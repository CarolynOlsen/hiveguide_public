const http = require('http');

function checkBundle() {
  return new Promise((resolve, reject) => {
    // First get the HTML to find the bundle name
    const htmlReq = http.get('http://localhost:8000', (res) => {
      let html = '';
      res.on('data', (chunk) => html += chunk);
      res.on('end', () => {
        // Check if HTML contains React content
        const hasReactDiv = html.includes('<div id="root">');
        const hasTitle = html.includes('<title>');
        console.log(`🌐 HTML check: ${hasReactDiv ? '✅' : '❌'} root div, ${hasTitle ? '✅' : '❌'} title`);
        
        // Extract bundle filename
        const bundleMatch = html.match(/src="([^"]*bundle[^"]*\.js)"/);
        if (!bundleMatch) {
          console.log('❌ No bundle found in HTML');
          resolve({ success: false, error: 'No bundle found' });
          return;
        }
        
        const bundlePath = bundleMatch[1];
        console.log(`📦 Found bundle: ${bundlePath}`);
        
        // Now check the bundle for require statements
        const bundleReq = http.get(`http://localhost:8000${bundlePath}`, (bundleRes) => {
          let bundle = '';
          bundleRes.on('data', (chunk) => bundle += chunk);
          bundleRes.on('end', () => {
            // Check for problematic patterns
            const requireMatches = bundle.match(/[^a-zA-Z]require\s*\(/g) || [];
            const outputMatches = bundle.match(/[^a-zA-Z]output[^a-zA-Z]/g) || [];
            
            console.log(`🔍 Bundle size: ${(bundle.length / 1024 / 1024).toFixed(2)} MB`);
            console.log(`🔍 Require statements found: ${requireMatches.length}`);
            console.log(`🔍 Output references found: ${outputMatches.length}`);
            
            if (requireMatches.length > 0) {
              console.log('❌ Found require() statements in bundle');
              // Show a few examples
              const lines = bundle.split('\n');
              const requireLines = lines.filter(line => line.includes('require('));
              requireLines.slice(0, 3).forEach((line, i) => {
                console.log(`   ${i + 1}. ${line.substring(0, 100)}...`);
              });
            }
            
            if (outputMatches.length > 0) {
              console.log('❌ Found output references in bundle');
            }
            
            const success = requireMatches.length === 0 && outputMatches.length === 0;
            console.log(success ? '✅ Bundle looks clean' : '❌ Bundle has issues');
            
            resolve({
              success,
              requireCount: requireMatches.length,
              outputCount: outputMatches.length,
              bundleSize: bundle.length
            });
          });
        });
        
        bundleReq.on('error', (err) => {
          console.log('❌ Failed to fetch bundle:', err.message);
          resolve({ success: false, error: err.message });
        });
      });
    });
    
    htmlReq.on('error', (err) => {
      console.log('❌ Failed to fetch HTML:', err.message);
      resolve({ success: false, error: err.message });
    });
  });
}

checkBundle().then(result => {
  console.log('\n=== RESULT ===');
  console.log(JSON.stringify(result, null, 2));
});
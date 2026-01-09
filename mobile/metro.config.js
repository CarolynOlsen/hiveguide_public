const { getDefaultConfig, mergeConfig } = require('@react-native/metro-config');
const path = require('path');

// Get the project root (mobile directory)
const projectRoot = __dirname;
// Get the monorepo root (parent directory)
const monorepoRoot = path.resolve(projectRoot, '..');
// Path to shared directory
const sharedPath = path.resolve(monorepoRoot, 'shared');

/**
 * Metro configuration for monorepo with @shared alias
 * https://reactnative.dev/docs/metro
 *
 * @type {import('@react-native/metro-config').MetroConfig}
 */
const config = {
  // Watch the entire monorepo to detect changes in shared
  watchFolders: [monorepoRoot],
  
  resolver: {
    // Map @shared alias to the shared directory
    extraNodeModules: new Proxy(
      {},
      {
        get: (target, name) => {
          if (name === '@shared') {
            return sharedPath;
          }
          // For other modules, use default node_modules resolution
          return path.join(projectRoot, `node_modules/${name}`);
        },
      }
    ),
    
    // Ensure TypeScript files are resolved
    sourceExts: ['js', 'jsx', 'ts', 'tsx', 'json'],
    
    // Look for modules in both mobile and monorepo node_modules
    nodeModulesPaths: [
      path.resolve(projectRoot, 'node_modules'),
      path.resolve(monorepoRoot, 'node_modules'),
    ],
  },
  
  // Ensure Metro processes files from shared directory
  transformer: {
    getTransformOptions: async () => ({
      transform: {
        experimentalImportSupport: false,
        inlineRequires: true,
      },
    }),
  },
};

module.exports = mergeConfig(getDefaultConfig(__dirname), config);

const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const webpack = require('webpack');

module.exports = {
  mode: process.env.NODE_ENV || 'development',
  entry: './src/index.web.tsx',
  
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.[contenthash].js',
    publicPath: '/',
  },
  
  optimization: {
    minimize: process.env.NODE_ENV === 'production',
  },
  
  resolve: {
    extensions: ['.web.tsx', '.web.ts', '.tsx', '.ts', '.web.jsx', '.web.js', '.jsx', '.js', '.mjs', '.json'],
    alias: {
      'react-native$': 'react-native-web',
      'react-native-safe-area-context': path.resolve(__dirname, 'src/mocks/react-native-safe-area-context.js'),
      'react-native-screens': path.resolve(__dirname, 'src/mocks/react-native-screens.js'),
      'react-native-image-picker': path.resolve(__dirname, 'src/mocks/react-native-image-picker.js'),
      'react-native-markdown-display': path.resolve(__dirname, 'src/mocks/react-native-markdown-display.js'),
      '@shared': path.resolve(__dirname, '../shared'),
    },
    modules: [
      path.resolve(__dirname, 'node_modules'), // Prioritize web-rn node_modules
      'node_modules', // Fall back to default resolution
    ],
    fullySpecified: false, // Disable the fully specified requirement for ESM imports
  },
  
  module: {
    rules: [
      {
        test: /\.m?js$/,
        resolve: {
          fullySpecified: false, // Fix ESM imports in node_modules
        },
      },
      {
        test: /\.(tsx?|jsx?|mjs|cjs)$/,
        exclude: /node_modules\/(?!(@react-navigation|react-native-|@react-native-community|react-native-markdown-display))/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: [
              '@babel/preset-env',
              ['@babel/preset-react', { runtime: 'automatic' }],
              ['@babel/preset-typescript', { isTSX: true, allExtensions: true }],
              '@babel/preset-flow',
            ],
          },
        },
      },
      {
        test: /\.(png|jpg|gif|svg)$/,
        type: 'asset/resource',
      },
    ],
  },
  
  plugins: [
    new HtmlWebpackPlugin({
      template: './public/index.html',
    }),
    new webpack.DefinePlugin({
      __DEV__: JSON.stringify(process.env.NODE_ENV !== 'production'),
    }),
  ],
  
  devServer: {
    port: 3000,
    historyApiFallback: true,
    proxy: [{
      context: ['/api', '/login', '/logout', '/auth', '/hives', '/inspections', '/transcribe', '/rag', '/circles', '/admin'],
      target: 'http://localhost:8000',
    }],
  },
};

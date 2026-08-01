#!/usr/bin/env node
// Patches angular.json to add/update an environment configuration
// Usage: node scripts/patch-angular-config.mjs <envName> <envFilePath>

import { readFileSync, writeFileSync } from 'fs';

const [,, envName, envFilePath] = process.argv;

if (!envName || !envFilePath) {
  console.error('Usage: patch-angular-config.mjs <envName> <envFilePath>');
  process.exit(1);
}

const angularJsonPath = 'angular.json';
const config = JSON.parse(readFileSync(angularJsonPath, 'utf8'));

const project = config.projects['unops-ai-playbook'];

// Add build configuration
project.architect.build.configurations[envName] = {
  budgets: [
    { type: 'initial', maximumWarning: '500kB', maximumError: '1MB' },
    { type: 'anyComponentStyle', maximumWarning: '8kB', maximumError: '50kB' }
  ],
  outputHashing: 'all',
  fileReplacements: [
    { replace: 'src/environments/environment.ts', with: envFilePath }
  ]
};

// Add serve configuration
project.architect.serve.configurations[envName] = {
  buildTarget: `unops-ai-playbook:build:${envName}`
};

writeFileSync(angularJsonPath, JSON.stringify(config, null, 2) + '\n');
console.log(`Added/updated configuration '${envName}' in angular.json`);

#!/usr/bin/env node
/**
 * Firestore Restore Script
 *
 * Reads test data from JSON files in test-data/firestore/ and restores to a real Firestore database.
 * Uses credentials from `firebase login` for authentication (via firebase-tools).
 *
 * Usage:
 *   node scripts/restore-firestore.mjs [options]
 *
 * Options:
 *   --project <id>     Firebase project ID (required, or set FIREBASE_PROJECT_ID env var)
 *   --database <name>  Firestore database ID (default: "(default)")
 *   --data-dir <path>  Path to test data directory (default: ./test-data)
 *   --dry-run          Show what would be restored without making changes
 *   --clear            Clear existing data before restoring (use with caution!)
 *   --help             Show this help message
 *
 * Authentication:
 *   Run `firebase login` before using this script to authenticate.
 *
 * Example:
 *   firebase login
 *   node scripts/restore-firestore.mjs --project my-project --database my-db
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import {
  fileExists,
  getDirectoryContents,
  toFirestoreDocument,
  loadFirestoreCollections,
} from './lib/firestore-utils.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Firestore REST API base URL
const FIRESTORE_API_BASE = 'https://firestore.googleapis.com/v1';

// ============================================
// Parse Command Line Arguments
// ============================================

function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    project: process.env.FIREBASE_PROJECT_ID || null,
    database: process.env.FIRESTORE_DATABASE_ID || '(default)',
    dataDir: path.resolve(__dirname, '../test-data'),
    dryRun: false,
    clear: false,
    help: false,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--project':
      case '-p':
        options.project = args[++i];
        break;
      case '--database':
      case '-d':
        options.database = args[++i];
        break;
      case '--data-dir':
        options.dataDir = path.resolve(args[++i]);
        break;
      case '--dry-run':
        options.dryRun = true;
        break;
      case '--clear':
        options.clear = true;
        break;
      case '--help':
      case '-h':
        options.help = true;
        break;
      default:
        if (args[i].startsWith('-')) {
          console.error(`Unknown option: ${args[i]}`);
          process.exit(1);
        }
    }
  }

  return options;
}

function showHelp() {
  console.log(`
Firestore Restore Script

Reads test data from JSON files and restores to a real Firestore database.
Uses credentials from 'firebase login' for authentication.

Usage:
  node scripts/restore-firestore.mjs [options]

Options:
  --project, -p <id>     Firebase project ID (required, or set FIREBASE_PROJECT_ID)
  --database, -d <name>  Firestore database ID (default: "(default)")
  --data-dir <path>      Path to test data directory (default: ./test-data)
  --dry-run              Show what would be restored without making changes
  --clear                Clear existing data before restoring (use with caution!)
  --help, -h             Show this help message

Environment Variables:
  FIREBASE_PROJECT_ID    Default project ID
  FIRESTORE_DATABASE_ID  Default database ID

Example:
  firebase login
  node scripts/restore-firestore.mjs --project my-project --database my-db
  node scripts/restore-firestore.mjs -p my-project -d my-db --dry-run
`);
}

// ============================================
// Firebase Authentication
// ============================================

async function getAccessToken() {
  // Use firebase-tools to get the access token from stored credentials
  const { getAccessToken: fbGetToken } = await import('firebase-tools');

  try {
    const result = await fbGetToken();
    return result.access_token;
  } catch (error) {
    // Try alternative method - read from configstore directly
    const os = await import('os');
    const configPath = path.join(os.homedir(), '.config', 'configstore', 'firebase-tools.json');

    try {
      const configContent = await fs.readFile(configPath, 'utf-8');
      const config = JSON.parse(configContent);

      if (config.tokens?.refresh_token) {
        // Exchange refresh token for access token
        const response = await fetch('https://oauth2.googleapis.com/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({
            client_id: '563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com',
            client_secret: 'j9iVZfS8kkCEFUPaAeJV0sAi',
            refresh_token: config.tokens.refresh_token,
            grant_type: 'refresh_token',
          }),
        });

        if (response.ok) {
          const data = await response.json();
          return data.access_token;
        }
      }
    } catch {
      // Config file doesn't exist or is invalid
    }

    throw new Error('Could not get access token. Please run "firebase login" first.');
  }
}

// ============================================
// Firestore REST API Functions
// ============================================

/**
 * Build the Firestore REST API URL for a document
 */
function buildDocumentUrl(project, database, collectionPath, documentId) {
  const encodedDocId = encodeURIComponent(documentId);
  return `${FIRESTORE_API_BASE}/projects/${project}/databases/${database}/documents/${collectionPath}/${encodedDocId}`;
}

/**
 * Create a document creator function for the given context
 */
function createDocumentCreator(accessToken, project, database, dryRun) {
  return async function createDocument(collectionPath, documentId, data) {
    const firestoreDoc = toFirestoreDocument(data);
    const url = buildDocumentUrl(project, database, collectionPath, documentId);

    if (dryRun) {
      console.log(`      [DRY RUN] Would create: ${collectionPath}/${documentId}`);
      return true;
    }

    const response = await fetch(url, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(firestoreDoc),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to create document ${collectionPath}/${documentId}: ${error}`);
    }

    return true;
  };
}

/**
 * List documents in a collection (for clearing)
 */
async function listDocuments(accessToken, project, database, collectionPath) {
  const url = `${FIRESTORE_API_BASE}/projects/${project}/databases/${database}/documents/${collectionPath}?pageSize=500`;

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    if (response.status === 404) {
      return []; // Collection doesn't exist
    }
    const error = await response.text();
    throw new Error(`Failed to list documents in ${collectionPath}: ${error}`);
  }

  const data = await response.json();
  return data.documents || [];
}

/**
 * Delete a document
 */
async function deleteDocument(accessToken, documentName) {
  const url = `${FIRESTORE_API_BASE}/${documentName}`;

  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok && response.status !== 404) {
    const error = await response.text();
    throw new Error(`Failed to delete document ${documentName}: ${error}`);
  }

  return true;
}

/**
 * Clear a collection recursively
 */
async function clearCollection(accessToken, project, database, collectionPath, dryRun) {
  console.log(`   🗑️  Clearing collection: ${collectionPath}`);

  if (dryRun) {
    console.log(`      [DRY RUN] Would delete all documents in ${collectionPath}`);
    return 0;
  }

  const documents = await listDocuments(accessToken, project, database, collectionPath);
  let deleted = 0;

  for (const doc of documents) {
    await deleteDocument(accessToken, doc.name);
    deleted++;
  }

  // If we got 500 documents, there might be more
  if (documents.length === 500) {
    deleted += await clearCollection(accessToken, project, database, collectionPath, dryRun);
  }

  return deleted;
}

// ============================================
// Main Entry Point
// ============================================

async function restoreFirestore() {
  const options = parseArgs();

  if (options.help) {
    showHelp();
    process.exit(0);
  }

  if (!options.project) {
    console.error('❌ Error: Project ID is required.');
    console.error('   Use --project <id> or set FIREBASE_PROJECT_ID environment variable.');
    console.error('   Run with --help for more information.');
    process.exit(1);
  }

  console.log('\n🚀 Firestore Restore Script');
  console.log('='.repeat(60));
  console.log(`   Project ID:    ${options.project}`);
  console.log(`   Database ID:   ${options.database}`);
  console.log(`   Data Dir:      ${options.dataDir}`);
  console.log(`   Dry Run:       ${options.dryRun ? 'Yes (no changes will be made)' : 'No'}`);
  console.log(`   Clear First:   ${options.clear ? 'Yes' : 'No'}`);
  console.log('='.repeat(60));

  // Verify data directory exists
  const firestoreDir = path.join(options.dataDir, 'firestore');
  if (!(await fileExists(firestoreDir))) {
    console.error(`\n❌ Error: Firestore data directory not found: ${firestoreDir}`);
    process.exit(1);
  }

  // Get access token from firebase login
  console.log('\n🔐 Getting access token from firebase login...');
  let accessToken;
  try {
    accessToken = await getAccessToken();
    console.log('   ✅ Authenticated successfully\n');
  } catch (error) {
    console.error('\n❌ Authentication failed:', error.message);
    console.error('\n💡 Tip: Run "firebase login" to authenticate first.');
    process.exit(1);
  }

  try {
    // Step 1: Clear existing data if requested
    if (options.clear) {
      console.log('\n⚠️  Clearing existing Firestore data...');
      const collections = await getDirectoryContents(firestoreDir);
      let totalDeleted = 0;
      for (const collection of collections) {
        if (collection.isDirectory()) {
          const deleted = await clearCollection(
            accessToken,
            options.project,
            options.database,
            collection.name,
            options.dryRun
          );
          totalDeleted += deleted;
        }
      }
      console.log(`   ✅ Deleted ${totalDeleted} documents\n`);
    }

    // Step 2: Load Firestore data
    console.log('📦 Loading Firestore data from', firestoreDir, '...\n');

    // Create a document creator function with the current context
    const createDocument = createDocumentCreator(
      accessToken,
      options.project,
      options.database,
      options.dryRun
    );

    const totalDocuments = await loadFirestoreCollections(firestoreDir, createDocument);

    // Summary
    console.log('\n' + '='.repeat(60));
    if (options.dryRun) {
      console.log('✅ Dry run complete!\n');
      console.log('Summary (no changes made):');
    } else {
      console.log('✅ Firestore restore complete!\n');
      console.log('Summary:');
    }
    console.log(`   - Documents ${options.dryRun ? 'would be' : ''} restored: ${totalDocuments}`);
    console.log(`   - Target project: ${options.project}`);
    console.log(`   - Target database: ${options.database}`);
    console.log('\n');
  } catch (error) {
    console.error('\n❌ Restore failed:', error.message);

    if (error.message.includes('PERMISSION_DENIED')) {
      console.error(
        '\n💡 Tip: Make sure your account has write access to Firestore in project:',
        options.project
      );
    }

    console.error('\nStack trace:', error.stack);
    process.exit(1);
  }
}

// Run the restore script
restoreFirestore();

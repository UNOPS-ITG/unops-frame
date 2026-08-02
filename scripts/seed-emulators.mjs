#!/usr/bin/env node
/**
 * Firebase Emulator Seed Script
 *
 * Reads test data from JSON files in test-data/ and populates Firebase emulators.
 *
 * Usage: node scripts/seed-emulators.mjs
 *
 * Data sources:
 * - test-data/auth/users.json - Firebase Auth users (with Google provider)
 * - test-data/firestore/     - Firestore collections and documents
 *
 * Configuration is loaded from scripts/emulator-config.json
 *
 * @see https://firebase.google.com/docs/emulator-suite/connect_firestore#import_and_export_data
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import {
  fileExists,
  readJsonFile,
  toFirestoreDocument,
  loadFirestoreCollections,
} from './lib/firestore-utils.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Load configuration from emulator-config.json
const CONFIG_FILE = path.join(__dirname, 'emulator-config.json');
const config = JSON.parse(await fs.readFile(CONFIG_FILE, 'utf-8'));

// Resolve paths and build URLs from config
const TEST_DATA_DIR = path.resolve(__dirname, config.testDataDir);
const AUTH_EMULATOR_URL = `http://${config.emulators.auth.host}:${config.emulators.auth.port}`;
const FIRESTORE_EMULATOR_URL = `http://${config.emulators.firestore.host}:${config.emulators.firestore.port}`;
const PROJECT_ID = config.projectId;
const FIRESTORE_DATABASE_ID = config.firestoreDatabaseId;

// ============================================
// Auth Emulator Functions
// ============================================

async function clearAuthUsers() {
  console.log('🗑️  Clearing existing auth users...');
  try {
    const response = await fetch(
      `${AUTH_EMULATOR_URL}/emulator/v1/projects/${PROJECT_ID}/accounts`,
      { method: 'DELETE' }
    );
    if (response.ok) {
      console.log('   ✅ Auth users cleared');
    }
  } catch {
    console.log('   ℹ️  No existing auth users to clear');
  }
}

async function createAuthUser(user) {
  console.log(`   📝 Creating auth user: ${user.email}`);

  // ALWAYS create users with email/password first so E2E tests can sign in
  // Then link Google provider for production-like behavior
  return await createAuthUserWithEmailPassword(user);
}

/**
 * Fallback: Create user with email/password if Google IdP fails
 */
async function createAuthUserWithEmailPassword(user) {
  const signUpResponse = await fetch(
    `${AUTH_EMULATOR_URL}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: user.email,
        password: user.password,
        displayName: user.displayName,
        returnSecureToken: true,
      }),
    }
  );

  if (!signUpResponse.ok) {
    const error = await signUpResponse.text();
    if (error.includes('EMAIL_EXISTS')) {
      console.log(`      ℹ️  User ${user.email} already exists`);
      return null;
    }
    throw new Error(`Failed to create auth user ${user.email}: ${error}`);
  }

  const signUpData = await signUpResponse.json();
  const actualUid = signUpData.localId;

  // Try to link Google provider
  const fakeGoogleIdToken = JSON.stringify({
    sub: user.email.replace(/[@.]/g, '_'),
    email: user.email,
    email_verified: true,
    name: user.displayName,
    picture: user.photoUrl || '',
  });

  const linkResponse = await fetch(
    `${AUTH_EMULATOR_URL}/identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=fake-api-key`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        idToken: signUpData.idToken,
        postBody: `id_token=${encodeURIComponent(fakeGoogleIdToken)}&providerId=google.com`,
        requestUri: 'http://localhost',
        returnSecureToken: true,
      }),
    }
  );

  if (!linkResponse.ok) {
    console.log(`      ✅ Created (email only): ${user.email} (UID: ${actualUid})`);
  } else {
    console.log(`      ✅ Created (email+Google): ${user.email} (UID: ${actualUid})`);
  }

  return actualUid;
}

async function loadAuthUsers() {
  const authFile = path.join(TEST_DATA_DIR, 'auth', 'users.json');

  if (!(await fileExists(authFile))) {
    console.log('   ⚠️  No auth/users.json found, skipping auth setup');
    return [];
  }

  const data = await readJsonFile(authFile);
  const users = data.users || [];

  console.log(`\n📦 Creating ${users.length} auth users from test-data/auth/users.json...\n`);

  const uidMapping = {};
  for (const user of users) {
    const actualUid = await createAuthUser(user);
    if (actualUid) {
      uidMapping[user.localId] = actualUid;
    }
  }

  return { users, uidMapping };
}

// ============================================
// Firestore Emulator Functions
// ============================================

async function clearFirestoreData() {
  console.log('🗑️  Clearing existing Firestore data...');
  try {
    const response = await fetch(
      `${FIRESTORE_EMULATOR_URL}/emulator/v1/projects/${PROJECT_ID}/databases/${FIRESTORE_DATABASE_ID}/documents`,
      { method: 'DELETE' }
    );
    if (response.ok) {
      console.log('   ✅ Firestore data cleared');
    }
  } catch {
    console.log('   ℹ️  No existing Firestore data to clear');
  }
}

/**
 * Create a document in Firestore emulator via REST API
 */
async function createFirestoreDocument(collectionPath, documentId, data) {
  const firestoreDoc = toFirestoreDocument(data);

  // Handle document IDs with special characters (like emails)
  const encodedDocId = encodeURIComponent(documentId);

  const response = await fetch(
    `${FIRESTORE_EMULATOR_URL}/v1/projects/${PROJECT_ID}/databases/${FIRESTORE_DATABASE_ID}/documents/${collectionPath}/${encodedDocId}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(firestoreDoc),
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to create document ${collectionPath}/${documentId}: ${error}`);
  }

  return true;
}

async function loadFirestoreData() {
  const firestoreDir = path.join(TEST_DATA_DIR, 'firestore');

  if (!(await fileExists(firestoreDir))) {
    console.log('   ⚠️  No firestore/ directory found, skipping Firestore setup');
    return 0;
  }

  console.log('\n📦 Loading Firestore data from test-data/firestore/...\n');

  return await loadFirestoreCollections(firestoreDir, createFirestoreDocument);
}

// ============================================
// Main Entry Point
// ============================================

async function seedEmulators() {
  console.log('\n🚀 Firebase Emulator Seed Script');
  console.log('='.repeat(50));
  console.log(`   Config File: ${CONFIG_FILE}`);
  console.log(`   Project ID: ${PROJECT_ID}`);
  console.log(`   Auth Emulator: ${AUTH_EMULATOR_URL}`);
  console.log(`   Firestore Emulator: ${FIRESTORE_EMULATOR_URL}`);
  console.log(`   Firestore Database: ${FIRESTORE_DATABASE_ID}`);
  console.log(`   Test Data: ${TEST_DATA_DIR}`);
  console.log('='.repeat(50));

  try {
    // Step 1: Clear existing data
    await clearAuthUsers();
    await clearFirestoreData();

    // Step 2: Load Auth users
    const { users } = await loadAuthUsers();

    // Step 3: Load Firestore data
    const docCount = await loadFirestoreData();

    // Summary
    console.log('\n' + '='.repeat(50));
    console.log('✅ Emulator seeding complete!\n');
    console.log('Summary:');
    console.log(`   - Auth users created: ${users?.length || 0}`);
    console.log(`   - Firestore documents: ${docCount}`);
    console.log('\n');

    if (users && users.length > 0) {
      console.log('Test Users:');
      console.log('-'.repeat(60));
      console.log('  Role         | Email                    | Password');
      console.log('-'.repeat(60));
      for (const user of users) {
        const role = (user.role || 'user').padEnd(12);
        const email = user.email.padEnd(24);
        console.log(`  ${role} | ${email} | ${user.password}`);
      }
      console.log('-'.repeat(60));
    }

    console.log('\nYou can now run E2E tests with these users.\n');
  } catch (error) {
    console.error('\n❌ Seeding failed:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

// Run the seed script
seedEmulators();

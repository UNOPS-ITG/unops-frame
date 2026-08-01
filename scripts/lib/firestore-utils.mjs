/**
 * Shared utilities for Firestore scripts
 *
 * Common functions used by both:
 * - seed-emulators.mjs (for local emulator)
 * - restore-firestore.mjs (for real Firestore)
 */

import fs from 'fs/promises';
import path from 'path';

// ============================================
// File System Utilities
// ============================================

export async function fileExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

export async function readJsonFile(filePath) {
  const content = await fs.readFile(filePath, 'utf-8');
  return JSON.parse(content);
}

export async function getDirectoryContents(dirPath) {
  try {
    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    return entries;
  } catch {
    return [];
  }
}

// ============================================
// Firestore Value Conversion
// ============================================

/**
 * Convert a JavaScript object to Firestore REST API field format
 */
export function toFirestoreValue(value) {
  if (value === null || value === undefined) {
    return { nullValue: null };
  }

  if (typeof value === 'string') {
    return { stringValue: value };
  }

  if (typeof value === 'number') {
    if (Number.isInteger(value)) {
      return { integerValue: value.toString() };
    }
    return { doubleValue: value };
  }

  if (typeof value === 'boolean') {
    return { booleanValue: value };
  }

  if (Array.isArray(value)) {
    return {
      arrayValue: {
        values: value.map(toFirestoreValue),
      },
    };
  }

  if (typeof value === 'object') {
    // Check for timestamp format { _seconds, _nanoseconds }
    if ('_seconds' in value && '_nanoseconds' in value) {
      const date = new Date(value._seconds * 1000);
      return { timestampValue: date.toISOString() };
    }

    // Regular object/map
    const fields = {};
    for (const [k, v] of Object.entries(value)) {
      fields[k] = toFirestoreValue(v);
    }
    return { mapValue: { fields } };
  }

  return { stringValue: String(value) };
}

/**
 * Convert a document object to Firestore REST API format
 */
export function toFirestoreDocument(doc) {
  const fields = {};
  for (const [key, value] of Object.entries(doc)) {
    fields[key] = toFirestoreValue(value);
  }
  return { fields };
}

// ============================================
// Collection Loading
// ============================================

/**
 * Recursively load a Firestore collection from a directory
 *
 * Directory structure:
 * - Folders = Collections (or subcollections if matching a document name)
 * - JSON files = Documents (filename without .json is document ID)
 *
 * Convention for subcollections:
 * - If a folder has the same name as a JSON file (minus .json),
 *   that folder contains subcollections for that document.
 *
 * @param {string} dirPath - Path to the directory containing the collection data
 * @param {string} collectionPath - Firestore collection path
 * @param {Function} createDocument - Async function(collectionPath, documentId, data) to create a document
 * @returns {Promise<number>} Number of documents created
 */
export async function loadCollection(dirPath, collectionPath, createDocument) {
  const entries = await getDirectoryContents(dirPath);
  let documentCount = 0;

  // First, identify which folders are subcollection containers (match a .json file)
  const jsonFiles = entries.filter((e) => e.isFile() && e.name.endsWith('.json'));
  const documentNames = new Set(jsonFiles.map((f) => f.name.replace('.json', '')));

  for (const entry of entries) {
    const entryPath = path.join(dirPath, entry.name);

    if (entry.isFile() && entry.name.endsWith('.json')) {
      // This is a document
      const documentId = entry.name.replace('.json', '');
      const data = await readJsonFile(entryPath);

      await createDocument(collectionPath, documentId, data);
      documentCount++;
      console.log(`      ✅ ${collectionPath}/${documentId}`);

      // Check for subcollections (folder with same name as this document)
      const subcollectionsDir = path.join(dirPath, documentId);
      if (await fileExists(subcollectionsDir)) {
        const subcollections = await getDirectoryContents(subcollectionsDir);
        for (const subcol of subcollections) {
          if (subcol.isDirectory()) {
            const subcolPath = `${collectionPath}/${documentId}/${subcol.name}`;
            console.log(`      📁 Subcollection: ${subcolPath}`);
            documentCount += await loadCollection(
              path.join(subcollectionsDir, subcol.name),
              subcolPath,
              createDocument
            );
          }
        }
      }
    } else if (entry.isDirectory()) {
      // Check if this folder is a subcollection container (matches a document name)
      // If so, skip it here - it will be processed when we handle the matching document
      if (documentNames.has(entry.name)) {
        continue; // Skip - will be handled as subcollection of the document
      }

      // This is a regular collection folder
      const newCollectionPath = collectionPath ? `${collectionPath}/${entry.name}` : entry.name;
      documentCount += await loadCollection(entryPath, newCollectionPath, createDocument);
    }
  }

  return documentCount;
}

/**
 * Load all Firestore collections from a directory
 *
 * @param {string} firestoreDir - Path to the firestore data directory
 * @param {Function} createDocument - Async function(collectionPath, documentId, data) to create a document
 * @returns {Promise<number>} Total number of documents created
 */
export async function loadFirestoreCollections(firestoreDir, createDocument) {
  const collections = await getDirectoryContents(firestoreDir);
  let totalDocuments = 0;

  for (const collection of collections) {
    if (collection.isDirectory()) {
      console.log(`   📁 Collection: ${collection.name}`);
      const count = await loadCollection(
        path.join(firestoreDir, collection.name),
        collection.name,
        createDocument
      );
      totalDocuments += count;
    }
  }

  return totalDocuments;
}

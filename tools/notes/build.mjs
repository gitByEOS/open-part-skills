import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { renderNotes } from './render.mjs';

const docs = new URL('../../docs/', import.meta.url);
const output = new URL('dist/', import.meta.url);
const source = await readFile(new URL('note.md', docs), 'utf8');
const html = renderNotes(source);

await mkdir(output, { recursive: true });
await Promise.all([
  writeFile(new URL('index.html', output), html),
  cp(new URL('notes.css', import.meta.url), new URL('notes.css', output)),
  cp(new URL('notes.js', import.meta.url), new URL('notes.js', output)),
  cp(new URL('images/', docs), new URL('images/', output), { recursive: true }),
]);

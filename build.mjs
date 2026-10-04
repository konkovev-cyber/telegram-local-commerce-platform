import { mkdirSync, copyFileSync, cpSync } from 'fs';
import { dirname } from 'path';
import { fileURLToPath } from 'url';
import { join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = join(__dirname);
const out = '/vercel/output';

mkdirSync(out, { recursive: true });
copyFileSync(join(src, 'index.html'), join(out, 'index.html'));
cpSync(join(src, 'assets'), join(out, 'assets'), { recursive: true });
cpSync(join(src, 'api'), join(out, 'api'), { recursive: true });
console.log('Copied static files to /vercel/output');

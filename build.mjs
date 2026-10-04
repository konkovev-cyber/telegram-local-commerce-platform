import { mkdirSync, copyFileSync, cpSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const root = dirname(fileURLToPath(import.meta.url));
const out = join(root, 'output');

mkdirSync(join(out, 'assets'), { recursive: true });
mkdirSync(join(out, 'api'), { recursive: true });
copyFileSync(join(root, 'index.html'), join(out, 'index.html'));
cpSync(join(root, 'assets'), join(out, 'assets'), { recursive: true });
cpSync(join(root, 'api'), join(out, 'api'), { recursive: true });
console.log('Copied static files to ./output');

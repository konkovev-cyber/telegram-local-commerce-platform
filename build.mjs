import { copyFileSync, cpSync, mkdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const root = dirname(fileURLToPath(import.meta.url));

mkdirSync(join(root, 'public', 'assets'), { recursive: true });
copyFileSync(join(root, 'index.html'), join(root, 'public', 'index.html'));
cpSync(join(root, 'assets'), join(root, 'public', 'assets'), { recursive: true });

console.log('Static files synced into public/');

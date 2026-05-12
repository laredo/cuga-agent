import type { Plugin } from 'vite';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';

type Options = {
  // Directory containing skill .md files. Defaults to ../sidecar/skills
  // relative to the Vite cwd (which is the presentation/ directory).
  skillsDir?: string;
};

export default function sidecarSkills(opts: Options = {}): Plugin {
  const skillsDir =
    opts.skillsDir ??
    path.resolve(process.cwd(), '..', 'sidecar', 'skills');

  return {
    name: 'sidecar-skills',
    configureServer(server) {
      server.config.logger.info(`[sidecar-skills] serving ${skillsDir}`);

      server.middlewares.use('/api/skills', async (req, res) => {
        if (req.method !== 'GET') {
          res.statusCode = 405;
          res.end();
          return;
        }

        try {
          const entries = await readdir(skillsDir, { withFileTypes: true });
          const mdFiles = entries.filter(
            (e) => e.isFile() && e.name.endsWith('.md'),
          );
          const skills = await Promise.all(
            mdFiles.map(async (e) => {
              const source = await readFile(
                path.join(skillsDir, e.name),
                'utf-8',
              );
              return {
                name: e.name.replace(/\.md$/, ''),
                filename: e.name,
                source,
              };
            }),
          );
          skills.sort((a, b) => a.name.localeCompare(b.name));

          res.writeHead(200, {
            'content-type': 'application/json',
            'cache-control': 'no-store',
          });
          res.end(JSON.stringify({ skills }));
        } catch (err) {
          res.writeHead(500, { 'content-type': 'application/json' });
          res.end(
            JSON.stringify({
              error: (err as Error).message,
              skillsDir,
            }),
          );
        }
      });
    },
  };
}

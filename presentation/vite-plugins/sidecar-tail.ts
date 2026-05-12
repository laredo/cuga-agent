import type { Plugin } from 'vite';
import {
  statSync,
  openSync,
  readSync,
  closeSync,
  existsSync,
} from 'node:fs';
import path from 'node:path';

// Keep these shapes in sync with src/lib/sidecar-events.ts on the client.
type Trigger =
  | { kind: 'file'; path: string; glob: string }
  | {
      kind: 'github';
      target: string;
      resource: string;
      event: string;
      interval: number;
    };

export type ParsedEvent =
  | {
      kind: 'skill-registered';
      at: string;
      skill: string;
      trigger: Trigger;
    }
  | { kind: 'trigger'; at: string; skill: string; detail: string }
  | { kind: 'invoke'; at: string; size: number }
  | {
      kind: 'fired';
      at: string;
      hook: string;
      effect: string;
      summary: string;
    }
  | {
      kind: 'skipped';
      at: string;
      hook: string;
      effect: string;
      when: string;
    }
  | {
      kind: 'failed';
      at: string;
      hook: string;
      effect: string;
      error: string;
    };

const LINE =
  /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+)\s+(\S+)\s+(.*)$/;

function parseLine(line: string): ParsedEvent | null {
  const m = line.match(LINE);
  if (!m) return null;
  const [, at, , logger, msg] = m;
  if (!logger.startsWith('sidecar.')) return null;

  let mm: RegExpMatchArray | null;

  if (
    (mm = msg.match(
      /^watching (\S+) \(glob=([^,]+), skill=([\w.-]+)\)\s*$/,
    ))
  ) {
    return {
      kind: 'skill-registered',
      at,
      skill: mm[3],
      trigger: { kind: 'file', path: mm[1], glob: mm[2] },
    };
  }
  if (
    (mm = msg.match(
      /^polling (\S+) \(([^,]+), ([^,]+), every (\d+)s, skill=([\w.-]+)\)\s*$/,
    ))
  ) {
    return {
      kind: 'skill-registered',
      at,
      skill: mm[5],
      trigger: {
        kind: 'github',
        target: mm[1],
        resource: mm[2].trim(),
        event: mm[3].trim(),
        interval: Number(mm[4]),
      },
    };
  }
  // Older format without the explicit event: fall through to catch repos
  // without that field (pre-upgrade sidecar versions).
  if (
    (mm = msg.match(
      /^polling (\S+) \(([^,]+), every (\d+)s, skill=([\w.-]+)\)\s*$/,
    ))
  ) {
    return {
      kind: 'skill-registered',
      at,
      skill: mm[4],
      trigger: {
        kind: 'github',
        target: mm[1],
        resource: mm[2].trim(),
        event: 'any',
        interval: Number(mm[3]),
      },
    };
  }
  if (
    (mm = msg.match(
      /^file event (\S+) \(skill=([\w.-]+), \d+ chars\)\s*$/,
    ))
  ) {
    return { kind: 'trigger', at, skill: mm[2], detail: mm[1] };
  }
  if (
    (mm = msg.match(
      /^github event (\S+#\d+) (.+) \(skill=([\w.-]+)\)\s*$/,
    ))
  ) {
    const title = mm[2].replace(/^['"]|['"]$/g, '');
    return {
      kind: 'trigger',
      at,
      skill: mm[3],
      detail: `${mm[1]} — ${title}`,
    };
  }
  if ((mm = msg.match(/^invoking cuga \((\d+) chars\)\s*$/))) {
    return { kind: 'invoke', at, size: Number(mm[1]) };
  }
  if (
    (mm = msg.match(/^✓ FIRED\s+\[(\w+)\] (\w+)\s*(?:→|->)\s*(.*)$/))
  ) {
    return {
      kind: 'fired',
      at,
      hook: mm[1],
      effect: mm[2],
      summary: mm[3].trim(),
    };
  }
  if (
    (mm = msg.match(
      /^⊘ SKIPPED\s+\[(\w+)\] effect=(\w+)\s+\(when='([^']*)'\)/,
    ))
  ) {
    return {
      kind: 'skipped',
      at,
      hook: mm[1],
      effect: mm[2],
      when: mm[3],
    };
  }
  if (
    (mm = msg.match(/^✗ FAILED\s*\[(\w+)\] effect=(\S+)(?:\s*—\s*(.*))?/))
  ) {
    return {
      kind: 'failed',
      at,
      hook: mm[1],
      effect: mm[2],
      error: (mm[3] ?? '').trim(),
    };
  }
  return null;
}

type Options = {
  logPath?: string;
  // How far back to read on first connect (bytes).
  tailBytes?: number;
  // Poll interval (ms) for new log lines.
  pollMs?: number;
};

export default function sidecarTail(opts: Options = {}): Plugin {
  const logPath =
    opts.logPath ??
    path.resolve(process.cwd(), '..', 'demo-data', 'sidecar.log');
  // Default: read the entire file on first connect. These logs are small
  // (single MB) and the user relies on seeing the most recent startup block
  // even if the sidecar isn't running right now.
  const tailBytes = opts.tailBytes ?? Number.POSITIVE_INFINITY;
  const pollMs = opts.pollMs ?? 500;

  return {
    name: 'sidecar-tail',
    configureServer(server) {
      server.config.logger.info(`[sidecar-tail] watching ${logPath}`);
      server.middlewares.use('/api/sidecar-events', (req, res) => {
        res.writeHead(200, {
          'content-type': 'text/event-stream',
          'cache-control': 'no-cache',
          connection: 'keep-alive',
          'x-accel-buffering': 'no',
        });

        let offset = 0;
        let alive = true;

        function emit(ev: ParsedEvent | { kind: 'status'; message: string }) {
          if (!alive) return;
          try {
            res.write(`data: ${JSON.stringify(ev)}\n\n`);
          } catch {
            alive = false;
          }
        }

        function readNew() {
          if (!alive) return;
          if (!existsSync(logPath)) {
            emit({ kind: 'status', message: 'log file not found' });
            return;
          }
          try {
            const stat = statSync(logPath);
            // Handle truncation / rotation: if file shrunk, reset offset.
            if (stat.size < offset) offset = 0;
            if (stat.size <= offset) return;
            const len = stat.size - offset;
            const buf = Buffer.alloc(len);
            const fd = openSync(logPath, 'r');
            readSync(fd, buf, 0, len, offset);
            closeSync(fd);
            offset = stat.size;
            const lines = buf.toString('utf-8').split('\n');
            for (const line of lines) {
              if (!line.trim()) continue;
              const ev = parseLine(line);
              if (ev) emit(ev);
            }
          } catch (err) {
            emit({
              kind: 'status',
              message: `read error: ${(err as Error).message}`,
            });
          }
        }

        // Seed from the end of the file for context.
        try {
          if (existsSync(logPath)) {
            const stat = statSync(logPath);
            offset = Math.max(0, stat.size - tailBytes);
          }
        } catch {
          /* ignore */
        }

        emit({ kind: 'status', message: 'connected' });
        readNew();
        const interval = setInterval(readNew, pollMs);

        // Heartbeat so the browser doesn't consider the stream stale.
        const heartbeat = setInterval(() => {
          if (!alive) return;
          try {
            res.write(': heartbeat\n\n');
          } catch {
            alive = false;
          }
        }, 15_000);

        req.on('close', () => {
          alive = false;
          clearInterval(interval);
          clearInterval(heartbeat);
        });
      });
    },
  };
}

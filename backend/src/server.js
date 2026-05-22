import bcrypt from 'bcryptjs';
import express from 'express';
import jwt from 'jsonwebtoken';
import pg from 'pg';

const {
  DATABASE_URL,
  JWT_SECRET,
  PORT = '5000',
  SPAINZA_ADMIN_EMAIL = 'admin@spainza.com',
  SPAINZA_ADMIN_PASSWORD = 'change-me',
  SPAINZA_ADMIN_NAME = 'Spainza Admin'
} = process.env;

if (!DATABASE_URL) {
  throw new Error('DATABASE_URL is required');
}
if (!JWT_SECRET) {
  throw new Error('JWT_SECRET is required');
}

const pool = new pg.Pool({ connectionString: DATABASE_URL });
const app = express();

app.use(express.json());

function publicUser(row) {
  return {
    id: row.id,
    email: row.email,
    name: row.name,
    avatar: row.avatar,
    created_at: row.created_at,
    role: {
      name: row.role_name,
      name_ru: row.role_name_ru
    },
    permissions: row.permissions || [],
    case_status: row.case_status,
    case_status_ru: row.case_status_ru
  };
}

async function initDatabase() {
  await pool.query(`
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    CREATE TABLE IF NOT EXISTS users (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      email text UNIQUE NOT NULL,
      password_hash text NOT NULL,
      name text NOT NULL,
      avatar text,
      role_name text NOT NULL DEFAULT 'Admin',
      role_name_ru text NOT NULL DEFAULT 'Администратор',
      permissions text[] NOT NULL DEFAULT ARRAY['full_access']::text[],
      case_status text NOT NULL DEFAULT 'active',
      case_status_ru text NOT NULL DEFAULT 'Активен',
      created_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS documents (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      title text NOT NULL,
      status text NOT NULL DEFAULT 'pending',
      icon text NOT NULL DEFAULT 'description',
      file_type text NOT NULL DEFAULT 'PDF',
      file_size text NOT NULL DEFAULT '—',
      is_priority boolean NOT NULL DEFAULT false,
      last_action_at timestamptz NOT NULL DEFAULT now(),
      created_at timestamptz NOT NULL DEFAULT now()
    );
  `);

  const existingUser = await pool.query('SELECT id FROM users WHERE email = $1', [
    SPAINZA_ADMIN_EMAIL
  ]);
  if (existingUser.rowCount === 0) {
    const passwordHash = await bcrypt.hash(SPAINZA_ADMIN_PASSWORD, 12);
    await pool.query(
      `INSERT INTO users (email, password_hash, name)
       VALUES ($1, $2, $3)`,
      [SPAINZA_ADMIN_EMAIL, passwordHash, SPAINZA_ADMIN_NAME]
    );
  }

  const existingDocuments = await pool.query('SELECT id FROM documents LIMIT 1');
  if (existingDocuments.rowCount === 0) {
    await pool.query(
      `INSERT INTO documents (title, status, icon, file_type, file_size, is_priority)
       VALUES
       ('Passport scan', 'pending', 'badge', 'PDF', '—', true),
       ('Proof of address', 'pending', 'home', 'PDF', '—', false),
       ('Application form', 'uploaded', 'description', 'PDF', '1.2 MB', false)`
    );
  }
}

function authenticate(req, res, next) {
  const header = req.get('authorization') || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : '';
  if (!token) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  try {
    req.session = jwt.verify(token, JWT_SECRET);
    return next();
  } catch {
    return res.status(401).json({ error: 'Unauthorized' });
  }
}

app.get('/api/health', (_req, res) => {
  res.json({ ok: true });
});

app.post('/api/login', async (req, res) => {
  const email = String(req.body?.email || '').trim().toLowerCase();
  const password = String(req.body?.password || '');

  const result = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
  const user = result.rows[0];
  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return res.status(401).json({ success: false, error: 'Invalid email or password' });
  }

  const token = jwt.sign({ sub: user.id, email: user.email }, JWT_SECRET, {
    expiresIn: '7d'
  });

  return res.json({ success: true, token, user: publicUser(user) });
});

app.get('/api/lk/session', authenticate, (_req, res) => {
  res.json({ ok: true });
});

app.get('/api/user', authenticate, async (req, res) => {
  const result = await pool.query('SELECT * FROM users WHERE id = $1', [req.session.sub]);
  const user = result.rows[0];
  if (!user) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  return res.json(publicUser(user));
});

app.get('/api/documents', authenticate, async (_req, res) => {
  const result = await pool.query(
    `SELECT id, title, status, icon, file_type, file_size, is_priority, last_action_at
     FROM documents
     ORDER BY is_priority DESC, created_at DESC`
  );

  res.json({ documents: result.rows });
});

app.use('/api', (_req, res) => {
  res.status(404).json({ error: 'Not found' });
});

initDatabase()
  .then(() => {
    app.listen(Number(PORT), '0.0.0.0', () => {
      console.log(`Spainza API listening on ${PORT}`);
    });
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

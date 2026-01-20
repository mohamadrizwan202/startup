-- Creates contact_messages table for admin inbox
CREATE TABLE IF NOT EXISTS public.contact_messages (
  id            BIGSERIAL PRIMARY KEY,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  name          TEXT,
  email         TEXT,
  subject       TEXT,
  message       TEXT NOT NULL,
  ip            TEXT,
  user_agent    TEXT,
  status        TEXT NOT NULL DEFAULT 'new',
  internal_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_contact_messages_created_at ON public.contact_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_contact_messages_status ON public.contact_messages(status);

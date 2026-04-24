-- =============================================================================
-- PetChat-2.0  Supabase Schema
-- =============================================================================
-- Run this once in the Supabase SQL editor (or via supabase db push).
-- Tables: users, sessions, messages, user_summaries
-- RLS is enabled on every table; add your own policies as needed.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()


-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.users (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username    TEXT        NOT NULL UNIQUE,
    full_name   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.users              IS 'One row per PetChat user.';
COMMENT ON COLUMN public.users.username     IS 'Unique login handle.';
COMMENT ON COLUMN public.users.full_name    IS 'Display name shown in the UI.';

-- Index for the frequent ensure_user() lookup
CREATE UNIQUE INDEX IF NOT EXISTS users_username_idx ON public.users (username);


-- ---------------------------------------------------------------------------
-- sessions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.sessions (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    title       TEXT,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at    TIMESTAMPTZ
);

COMMENT ON TABLE  public.sessions            IS 'One row per chat session.';
COMMENT ON COLUMN public.sessions.title      IS 'Optional label set by the app (e.g. first user message).';
COMMENT ON COLUMN public.sessions.ended_at   IS 'NULL while session is active; stamped by end_session().';

CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON public.sessions (user_id);


-- ---------------------------------------------------------------------------
-- messages
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.messages (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES public.sessions (id) ON DELETE CASCADE,
    role            TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT        NOT NULL,

    -- ESConv plan metadata (populated for assistant turns; empty string for user turns)
    risk_level      TEXT        NOT NULL DEFAULT '',
    primary_emotion TEXT        NOT NULL DEFAULT '',
    problem_hint    TEXT        NOT NULL DEFAULT '',
    support_stage   TEXT        NOT NULL DEFAULT '',
    response_style  TEXT        NOT NULL DEFAULT '',
    emoji_used      TEXT        NOT NULL DEFAULT '',

    -- Free-form JSON extras (RAG used, rag_chars, draft_reply, etc.)
    meta            JSONB,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.messages                IS 'Every chat turn, both user and assistant.';
COMMENT ON COLUMN public.messages.role           IS '"user" or "assistant".';
COMMENT ON COLUMN public.messages.risk_level     IS 'low | medium | high — from safety.detect_risk_level.';
COMMENT ON COLUMN public.messages.support_stage  IS 'exploration | comforting | action — from esc_support.';
COMMENT ON COLUMN public.messages.meta           IS 'Arbitrary JSON logged by pipeline (rag_used, draft_reply, etc.).';

-- Indexes for load_recent_turns() (session + time)
CREATE INDEX IF NOT EXISTS messages_session_id_idx  ON public.messages (session_id);
CREATE INDEX IF NOT EXISTS messages_created_at_idx  ON public.messages (created_at DESC);


-- ---------------------------------------------------------------------------
-- user_summaries
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.user_summaries (
    user_id     UUID        PRIMARY KEY REFERENCES public.users (id) ON DELETE CASCADE,
    summary     TEXT        NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.user_summaries          IS 'One compressed long-term summary per user.';
COMMENT ON COLUMN public.user_summaries.summary  IS 'Produced by memory/summarizer.py and stored via upsert_user_summary().';


-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
-- Enable RLS on every table.  The policies below are permissive stubs;
-- tighten them to (auth.uid() = user_id) once you wire Supabase Auth.
-- ---------------------------------------------------------------------------

ALTER TABLE public.users           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_summaries  ENABLE ROW LEVEL SECURITY;

-- Permissive stub policies (replace with user-scoped policies in production)
CREATE POLICY IF NOT EXISTS "allow_all_users"          ON public.users          FOR ALL USING (true);
CREATE POLICY IF NOT EXISTS "allow_all_sessions"       ON public.sessions       FOR ALL USING (true);
CREATE POLICY IF NOT EXISTS "allow_all_messages"       ON public.messages       FOR ALL USING (true);
CREATE POLICY IF NOT EXISTS "allow_all_user_summaries" ON public.user_summaries FOR ALL USING (true);


-- ---------------------------------------------------------------------------
-- Helpful view: recent_turns
-- Joins messages -> sessions -> users so load_recent_turns() can query
-- this view directly if you prefer a single-query approach later.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW public.recent_turns AS
SELECT
    m.id,
    m.created_at,
    u.id            AS user_id,
    u.username,
    s.id            AS session_id,
    m.role,
    m.content,
    m.risk_level,
    m.primary_emotion,
    m.problem_hint,
    m.support_stage,
    m.response_style,
    m.emoji_used,
    m.meta
FROM public.messages   m
JOIN public.sessions   s ON s.id = m.session_id
JOIN public.users      u ON u.id = s.user_id
ORDER BY m.created_at DESC;

COMMENT ON VIEW public.recent_turns IS
    'Denormalised view of all messages with user and session context.';


-- ---------------------------------------------------------------------------
-- Done
-- ---------------------------------------------------------------------------
-- Tables  : users, sessions, messages, user_summaries
-- View    : recent_turns
-- RLS     : enabled (permissive stubs — tighten before production)
-- =============================================================================

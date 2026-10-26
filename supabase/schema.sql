-- ============================================================
-- Soran 教材 · Supabase 初始化脚本
-- 使用方式：Supabase Dashboard → SQL Editor → 粘贴本文件全部内容 → Run
-- 说明：
--   1. annotations 存用户的划线/下划线/笔记，RLS 强制每个用户只能读写自己的行
--   2. heartbeat 仅用于免费项目保活，只开放 select，不开放写入
-- ============================================================

create extension if not exists pgcrypto;

-- ------------------------------------------------------------
-- 标注表
-- ------------------------------------------------------------
create table if not exists public.annotations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  page_id text not null,
  start_block integer not null check (start_block >= 0),
  end_block integer not null,
  start_offset integer not null check (start_offset >= 0),
  end_offset integer not null check (end_offset >= 0),
  quote text not null,
  style text not null default 'highlight' check (style in ('highlight', 'underline')),
  color text not null default 'green' check (color in ('green', 'clay', 'gold', 'blue', 'rose', 'violet', 'gray')),
  note text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint annotations_block_range check (end_block >= start_block),
  constraint annotations_quote_len check (char_length(quote) between 1 and 2000)
);

-- 兼容已建好的项目：把旧的 3 色约束升级为 7 色（整段脚本可重复执行）
alter table public.annotations drop constraint if exists annotations_color_check;
alter table public.annotations add constraint annotations_color_check
  check (color in ('green', 'clay', 'gold', 'blue', 'rose', 'violet', 'gray'));

create index if not exists annotations_user_page_idx
  on public.annotations (user_id, page_id, created_at);

alter table public.annotations enable row level security;

drop policy if exists "annotations_own" on public.annotations;
create policy "annotations_own"
  on public.annotations
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

revoke all on public.annotations from anon;
grant select, insert, update, delete on public.annotations to authenticated;

-- ------------------------------------------------------------
-- 学习进度表
-- kind: read 阅读小节 / quiz 自测对错 / chk 清单勾选 / rate 评分
-- value 为 jsonb；null 表示该条记录已被用户重置（墓碑）
-- ------------------------------------------------------------
create table if not exists public.learning_state (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  kind text not null check (kind in ('read', 'quiz', 'chk', 'rate')),
  item_key text not null check (char_length(item_key) between 1 and 200),
  value jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, kind, item_key),
  constraint learning_state_value_type check (
    value is null or jsonb_typeof(value) in ('array', 'boolean', 'object')
  )
);

alter table public.learning_state enable row level security;

drop policy if exists "learning_state_own" on public.learning_state;
create policy "learning_state_own"
  on public.learning_state
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

revoke all on public.learning_state from anon;
grant select, insert, update, delete on public.learning_state to authenticated;

-- 每次写入由服务端刷新 updated_at，避免设备时钟偏差影响合并顺序
create or replace function public.learning_state_touch()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists learning_state_touch on public.learning_state;
create trigger learning_state_touch
  before insert or update on public.learning_state
  for each row execute function public.learning_state_touch();

-- ------------------------------------------------------------
-- 保活心跳表
-- 外部定时器每天请求一次：
--   GET https://<project-ref>.supabase.co/rest/v1/heartbeat?select=id&limit=1
--   Header: apikey: <anon public key>
-- 请求会命中一次真实数据库查询，用于避免免费项目因 7 天无活动被暂停。
-- ------------------------------------------------------------
create table if not exists public.heartbeat (
  id integer primary key check (id = 1),
  last_ping timestamptz not null default now()
);

insert into public.heartbeat (id)
values (1)
on conflict (id) do nothing;

alter table public.heartbeat enable row level security;

drop policy if exists "heartbeat_read" on public.heartbeat;
create policy "heartbeat_read"
  on public.heartbeat
  for select
  to anon, authenticated
  using (true);

revoke all on public.heartbeat from anon, authenticated;
grant select on public.heartbeat to anon, authenticated;

-- 刷新 PostgREST 的 schema 缓存，让新表立即可用
notify pgrst, 'reload schema';

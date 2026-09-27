-- Phase 05, price side: what the batch pipeline loads and what anyone may read.
--
-- The design rule holds by schema, not by convention: a price row cannot exist
-- without a source, and a source cannot exist without a date. Only
-- `ratecard load` (connecting as the database owner) writes here; the public
-- roles can read, and only rows the matcher trusted.

create extension if not exists postgis with schema extensions;
create extension if not exists pg_trgm with schema extensions;

create type public.provider_kind as enum ('hospital', 'lab', 'imaging', 'clinic');

-- none: prices only, from its published documents; never bookable.
-- demo: fictional, seeded, badged "Demo" everywhere it appears.
-- live: a real provider that signed up and runs the staff dashboard.
create type public.partner_status as enum ('none', 'demo', 'live');

create type public.source_doc_type as enum (
  'published_rate_card',  -- extracted by the pipeline from a public document
  'provider_submitted',   -- a live partner's own list, dated when submitted
  'demo_seed'             -- fictional, and only ever attached to a demo provider
);

create table public.provider (
  id             bigint generated always as identity primary key,
  slug           text not null unique,
  name           text not null,
  brand          text,
  kind           public.provider_kind not null,
  city           text not null,
  locality       text,
  address        text,
  phone          text,
  -- Not null: a price with no location cannot answer "near me".
  geom           extensions.geography(point, 4326) not null,
  rating         numeric(2, 1) check (rating between 0 and 5),
  partner_status public.partner_status not null default 'none'
);
create index provider_geom_idx on public.provider using gist (geom);

create table public.source (
  id              text primary key,
  provider_id     bigint not null references public.provider (id) on delete cascade,
  publisher       text not null,
  unit            text,
  city            text not null,
  url             text,
  doc_type        public.source_doc_type not null,
  sha256          text,
  as_of           date not null,
  retrieved       date,
  licence_note    text not null check (length(btrim(licence_note)) > 0),
  -- Tier vocabulary is per-document, so this is the source's own column name.
  comparison_tier text not null,
  -- A published document must be pinned, or a reissue cannot be told from a
  -- cached copy and "what did it say in March?" stops being answerable.
  constraint published_is_pinned check (
    doc_type <> 'published_rate_card' or (sha256 is not null and url is not null)
  )
);

create table public.canonical_test (
  id         text primary key,
  name       text not null,
  category   text not null,
  kind       text not null,
  loinc_code text,
  specimen   text,
  is_panel   boolean not null default false
);
create index canonical_test_name_trgm
  on public.canonical_test using gin (lower(name) extensions.gin_trgm_ops);

-- Every indexed surface form from the taxonomy, already normalised. Search
-- resolves through these and nothing fuzzier: the matcher never runs at query
-- time, so a user can be shown a list to pick from but never a guess.
create table public.test_alias (
  surface           text primary key,
  canonical_test_id text not null references public.canonical_test (id) on delete cascade
);
create index test_alias_surface_trgm
  on public.test_alias using gin (surface extensions.gin_trgm_ops);

create table public.price_observation (
  id                bigint generated always as identity primary key,
  source_id         text not null references public.source (id) on delete cascade,
  canonical_test_id text references public.canonical_test (id),
  -- Kept forever beside the resolved id: when the taxonomy improves, every
  -- observation can be re-matched without re-fetching anything.
  raw_test_name     text not null,
  service_code      text,
  price_inr         integer not null check (price_inr >= 0),
  price_tier        text not null,
  match_confidence  real not null,
  match_method      text not null,
  -- The matcher's own flag, never recomputed. Only an exact alias hit is false.
  needs_review      boolean not null,
  constraint price_row_identity
    unique nulls not distinct (source_id, raw_test_name, price_tier, service_code)
);
create index price_observation_public_idx
  on public.price_observation (canonical_test_id) where not needs_review;

-- Demo data may never pass for real data, in either direction.
create function public.check_source_provider() returns trigger
language plpgsql set search_path = public as $$
declare
  status public.partner_status;
begin
  select partner_status into status from public.provider where id = new.provider_id;
  if (new.doc_type = 'demo_seed') <> (status = 'demo') then
    raise exception 'source % is %, provider % is %: demo_seed sources belong only to demo providers, and demo providers only carry demo_seed sources',
      new.id, new.doc_type, new.provider_id, status;
  end if;
  return new;
end $$;

create trigger source_matches_provider
  before insert or update of provider_id, doc_type on public.source
  for each row execute function public.check_source_provider();

create function public.check_provider_status() returns trigger
language plpgsql set search_path = public as $$
begin
  if exists (
    select 1 from public.source s
    where s.provider_id = new.id and (s.doc_type = 'demo_seed') <> (new.partner_status = 'demo')
  ) then
    raise exception 'provider % cannot become % while its sources say otherwise',
      new.slug, new.partner_status;
  end if;
  return new;
end $$;

create trigger provider_status_matches_sources
  before update of partner_status on public.provider
  for each row execute function public.check_provider_status();

-- Read access. Nobody but the owner writes to these tables.
alter table public.provider          enable row level security;
alter table public.source            enable row level security;
alter table public.canonical_test    enable row level security;
alter table public.test_alias        enable row level security;
alter table public.price_observation enable row level security;

create policy "read providers" on public.provider for select to anon, authenticated using (true);
create policy "read sources"   on public.source   for select to anon, authenticated using (true);
create policy "read tests"     on public.canonical_test for select to anon, authenticated using (true);
create policy "read aliases"   on public.test_alias for select to anon, authenticated using (true);

-- The rule everything else follows: a row the matcher was not sure about is
-- held back, not shown wrong.
create policy "read trusted prices" on public.price_observation
  for select to anon, authenticated
  using (canonical_test_id is not null and not needs_review);

-- Autocomplete. Suggests canonical tests for the user to pick; never resolves
-- a free-text query to a test on its own.
create function public.search_tests(q text, max_results int default 8)
returns table (id text, name text, category text, matched text, score real)
language sql stable set search_path = public, extensions as $$
  with query as (
    select btrim(regexp_replace(lower(q), '[^a-z0-9]+', ' ', 'g')) as k
  ),
  hits as (
    select a.canonical_test_id as id, a.surface as matched,
           greatest(similarity(a.surface, query.k), word_similarity(query.k, a.surface)) as score
      from public.test_alias a, query
     where length(query.k) > 0 and (a.surface % query.k or query.k <% a.surface)
    union all
    select t.id, lower(t.name),
           greatest(similarity(lower(t.name), query.k), word_similarity(query.k, lower(t.name)))
      from public.canonical_test t, query
     where length(query.k) > 0 and (lower(t.name) % query.k or query.k <% lower(t.name))
  ),
  best as (
    select distinct on (h.id) h.id, h.matched, h.score from hits h order by h.id, h.score desc
  )
  select t.id, t.name, t.category, best.matched, best.score::real
    from best join public.canonical_test t on t.id = best.id
   order by best.score desc, t.name
   limit greatest(1, least(max_results, 25));
$$;

-- The core query: one test, providers near a point, cheapest first. One row
-- per provider (its cheapest trusted observation), each carrying its source.
-- security invoker, so the "read trusted prices" policy still applies.
create function public.prices_near(
  p_test_id   text,
  p_lat       double precision,
  p_lng       double precision,
  p_radius_km double precision default 25,
  p_limit     int default 50
)
returns table (
  provider_id    bigint,
  provider_slug  text,
  provider_name  text,
  brand          text,
  kind           public.provider_kind,
  locality       text,
  address        text,
  phone          text,
  rating         numeric,
  partner_status public.partner_status,
  lat            double precision,
  lng            double precision,
  distance_m     double precision,
  price_inr      integer,
  price_tier     text,
  raw_test_name  text,
  source_id      text,
  publisher      text,
  source_url     text,
  doc_type       public.source_doc_type,
  as_of          date
)
language sql stable security invoker set search_path = public, extensions as $$
  with here as (
    select st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography as g
  ),
  cheapest as (
    select distinct on (p.id)
           p.id, p.slug, p.name, p.brand, p.kind, p.locality, p.address, p.phone,
           p.rating, p.partner_status,
           st_y(p.geom::geometry) as lat, st_x(p.geom::geometry) as lng,
           st_distance(p.geom, here.g) as distance_m,
           po.price_inr, po.price_tier, po.raw_test_name,
           s.id as source_id, s.publisher, s.url, s.doc_type, s.as_of
      from public.price_observation po
      join public.source s   on s.id = po.source_id
      join public.provider p on p.id = s.provider_id
      cross join here
     where po.canonical_test_id = p_test_id
       and not po.needs_review  -- the policy says so too; this holds for the owner role
       and st_dwithin(p.geom, here.g, least(p_radius_km, 100) * 1000)
     order by p.id, po.price_inr
  )
  select * from cheapest
   order by price_inr, distance_m
   limit greatest(1, least(p_limit, 100));
$$;

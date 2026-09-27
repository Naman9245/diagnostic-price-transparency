-- Specialties: the list a doctor is filed under and a patient searches by.
--
-- Reference data like canonical_test: `ratecard load` writes it from
-- src/ratecard/specialties/data/specialties.yaml, where it is validated. The
-- same two kinds of surface form carry through:
--
--   specialty_alias  names exactly one specialty. surface is the primary key,
--                    so the database cannot hold an alias two specialties share.
--   specialty_term   "kidney", "oncologist": points at several specialties and
--                    only ever suggests. Keyed on (term, specialty).
--
-- doctor.specialty was free text, so "Cardiology", "Cardiologist" and "Cardiac
-- Sciences" would have been three specialties to a search. It becomes a foreign
-- key. Partner staff pick from the list; they cannot type a new one.

create table public.specialty (
  id           text primary key,
  name         text not null unique,
  practitioner text not null,
  category     text not null check (category in ('medical', 'surgical', 'dental', 'allied_health'))
);

create table public.specialty_alias (
  surface      text primary key,
  specialty_id text not null references public.specialty (id) on delete cascade
);
create index specialty_alias_surface_trgm
  on public.specialty_alias using gin (surface extensions.gin_trgm_ops);

create table public.specialty_term (
  term         text not null,
  specialty_id text not null references public.specialty (id) on delete cascade,
  primary key (term, specialty_id)
);
create index specialty_term_trgm
  on public.specialty_term using gin (term extensions.gin_trgm_ops);

-- No database has doctors yet. If one does, set not null fails loudly and the
-- existing rows need mapping to a specialty by hand first - never by guessing.
alter table public.doctor add column specialty_id text references public.specialty (id);
alter table public.doctor alter column specialty_id set not null;
alter table public.doctor drop column specialty;
create index doctor_specialty_idx on public.doctor (specialty_id);

alter table public.specialty       enable row level security;
alter table public.specialty_alias enable row level security;
alter table public.specialty_term  enable row level security;

create policy "read specialties" on public.specialty
  for select to anon, authenticated using (true);
create policy "read specialty aliases" on public.specialty_alias
  for select to anon, authenticated using (true);
create policy "read specialty terms" on public.specialty_term
  for select to anon, authenticated using (true);

-- Autocomplete, like search_tests: it suggests and the user picks. `via` says
-- why each row is there - 'alias' when the query names that specialty, 'term'
-- when it only points at it ("kidney" returns nephrology and urology, both
-- via 'term', and the user chooses).
create function public.search_specialties(q text, max_results int default 8)
returns table (id text, name text, practitioner text, category text, matched text,
               via text, score real)
language sql stable set search_path = public, extensions as $$
  with query as (
    select btrim(regexp_replace(lower(q), '[^a-z0-9]+', ' ', 'g')) as k
  ),
  hits as (
    select a.specialty_id as id, a.surface as matched, 'alias'::text as via,
           greatest(similarity(a.surface, query.k), word_similarity(query.k, a.surface)) as score
      from public.specialty_alias a, query
     where length(query.k) > 0 and (a.surface % query.k or query.k <% a.surface)
    union all
    select t.specialty_id, t.term, 'term',
           greatest(similarity(t.term, query.k), word_similarity(query.k, t.term))
      from public.specialty_term t, query
     where length(query.k) > 0 and (t.term % query.k or query.k <% t.term)
  ),
  best as (
    select distinct on (h.id) h.id, h.matched, h.via, h.score
      from hits h
     order by h.id, h.score desc, (h.via = 'alias') desc
  )
  select s.id, s.name, s.practitioner, s.category, best.matched, best.via, best.score::real
    from best join public.specialty s on s.id = best.id
   order by best.score desc, (best.via = 'alias') desc, s.name
   limit greatest(1, least(max_results, 25));
$$;

-- One specialty, partner doctors near a point, cheapest consultation first.
-- Carries what a patient decides on: the fee, today's hours from the weekly
-- schedule, and today's status as staff set it. today_state is null when
-- nobody has updated it today - unknown is shown as unknown, not as "not
-- arrived". security invoker, so "read partner doctors" still applies.
create function public.doctors_near(
  p_specialty_id text,
  p_lat          double precision,
  p_lng          double precision,
  p_radius_km    double precision default 25,
  p_limit        int default 50
)
returns table (
  doctor_id      bigint,
  doctor_name    text,
  qualifications text,
  fee_inr        integer,
  provider_id    bigint,
  provider_slug  text,
  provider_name  text,
  partner_status public.partner_status,
  locality       text,
  address        text,
  phone          text,
  lat            double precision,
  lng            double precision,
  distance_m     double precision,
  hours_today    text,
  today_state    public.doctor_state,
  delay_min      smallint
)
language sql stable security invoker set search_path = public, extensions as $$
  with here as (
    select st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography as g,
           (now() at time zone 'Asia/Kolkata')::date as today
  ),
  found as (
    select d.id, d.name as doctor_name, d.qualifications, d.fee_inr,
           p.id as provider_id, p.slug, p.name as provider_name, p.partner_status,
           p.locality, p.address, p.phone,
           st_y(p.geom::geometry) as lat, st_x(p.geom::geometry) as lng,
           st_distance(p.geom, here.g) as distance_m,
           (select string_agg(to_char(r.starts, 'HH24:MI') || '-' || to_char(r.ends, 'HH24:MI'),
                              ', ' order by r.starts)
              from public.schedule_rule r
             where r.doctor_id = d.id and r.weekday = extract(dow from here.today)) as hours_today,
           s.state, s.delay_min
      from public.doctor d
      join public.provider p on p.id = d.provider_id
      cross join here
      left join public.doctor_day_status s on s.doctor_id = d.id and s.day = here.today
     where d.specialty_id = p_specialty_id
       and d.active
       and p.partner_status <> 'none'  -- the policy says so too; this holds for the owner role
       and st_dwithin(p.geom, here.g, least(p_radius_km, 100) * 1000)
  )
  select * from found
   order by fee_inr, distance_m
   limit greatest(1, least(p_limit, 100));
$$;

-- Phases 07-09, partner side: doctors, schedules, live OPD status, one patient
-- profile reused everywhere, booking, the queue, and payment records.
--
-- Booking exists only for partner providers. That is enforced here, twice -
-- in book_appointment and again by a trigger on the table - so no client,
-- however written, can put a Book button in front of a provider that did not
-- sign up.
--
-- Times: schedules are local wall-clock times in Asia/Kolkata; slot_start is a
-- timestamptz. `day` is always the IST date of slot_start.

create type public.doctor_state as enum ('not_arrived', 'in_opd', 'delayed', 'on_leave', 'done');
create type public.appointment_status as enum (
  'booked', 'checked_in', 'in_consult', 'done', 'cancelled', 'no_show'
);
create type public.pay_mode as enum ('online', 'at_counter');

-- ---------------------------------------------------------------- staff ----

create table public.provider_staff (
  user_id     uuid not null references auth.users (id) on delete cascade,
  provider_id bigint not null references public.provider (id) on delete cascade,
  role        text not null default 'staff' check (role in ('admin', 'staff')),
  primary key (user_id, provider_id)
);

-- security definer so policies can call it without recursing through
-- provider_staff's own policy.
create function public.is_staff_of(p_provider_id bigint) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.provider_staff
     where user_id = auth.uid() and provider_id = p_provider_id
  );
$$;

-- --------------------------------------------------------------- doctors ----

create table public.doctor (
  id             bigint generated always as identity primary key,
  provider_id    bigint not null references public.provider (id) on delete cascade,
  name           text not null,
  specialty      text not null,
  qualifications text,
  fee_inr        integer not null check (fee_inr >= 0),
  active         boolean not null default true
);
create index doctor_provider_idx on public.doctor (provider_id);

create table public.schedule_rule (
  id           bigint generated always as identity primary key,
  doctor_id    bigint not null references public.doctor (id) on delete cascade,
  weekday      smallint not null check (weekday between 0 and 6),  -- 0 = Sunday, as extract(dow)
  starts       time not null,
  ends         time not null,
  slot_minutes smallint not null check (slot_minutes between 5 and 120),
  per_slot     smallint not null default 1 check (per_slot between 1 and 20),
  check (ends > starts)
);
create index schedule_rule_doctor_idx on public.schedule_rule (doctor_id, weekday);

-- Today's truth, set by staff: has the doctor arrived, are they running late.
-- queue_version is bumped on every appointment change for that doctor-day, so
-- a patient can subscribe to this one row instead of to other patients' rows,
-- which they are not allowed to see.
create table public.doctor_day_status (
  doctor_id     bigint not null references public.doctor (id) on delete cascade,
  day           date not null,
  state         public.doctor_state not null default 'not_arrived',
  delay_min     smallint not null default 0 check (delay_min between 0 and 600),
  now_serving   integer,
  queue_version integer not null default 0,
  updated_at    timestamptz not null default now(),
  updated_by    uuid references auth.users (id) on delete set null,
  primary key (doctor_id, day)
);

-- ------------------------------------------------------------- patients ----

-- Filled once, reused at every partner. This is the fix for registering again
-- at every counter. Demo build: no real patient data.
create table public.patient_profile (
  user_id      uuid primary key references auth.users (id) on delete cascade,
  full_name    text not null check (length(btrim(full_name)) > 0),
  dob          date not null check (dob <= current_date),
  sex          text not null check (sex in ('female', 'male', 'other')),
  phone        text,
  abha_address text,
  consent_at   timestamptz not null
);

-- ---------------------------------------------------------- appointments ----

create table public.appointment (
  id           bigint generated always as identity primary key,
  patient_id   uuid not null references public.patient_profile (user_id) on delete cascade,
  doctor_id    bigint not null references public.doctor (id),
  provider_id  bigint not null references public.provider (id),
  day          date not null,
  slot_start   timestamptz not null,
  slot_minutes smallint not null,
  seat         smallint not null,
  token_no     integer not null,
  status       public.appointment_status not null default 'booked',
  pay_mode     public.pay_mode not null,
  fee_inr      integer not null check (fee_inr >= 0),
  paid         boolean not null default false,
  created_at   timestamptz not null default now()
);
-- No double booking: a seat in a slot is held by at most one live appointment.
create unique index appointment_seat_taken
  on public.appointment (doctor_id, slot_start, seat) where status <> 'cancelled';
create unique index appointment_token_unique on public.appointment (doctor_id, day, token_no);
create index appointment_patient_idx on public.appointment (patient_id);
create index appointment_doctor_day_idx on public.appointment (doctor_id, day);

create function public.check_appointment_partner() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  status public.partner_status;
begin
  select partner_status into status from public.provider where id = new.provider_id;
  if status is distinct from 'demo' and status is distinct from 'live' then
    raise exception 'provider % is not a partner and cannot take bookings', new.provider_id;
  end if;
  if not exists (select 1 from public.doctor where id = new.doctor_id and provider_id = new.provider_id) then
    raise exception 'doctor % does not work at provider %', new.doctor_id, new.provider_id;
  end if;
  return new;
end $$;

create trigger appointment_partner_only
  before insert or update of provider_id, doctor_id on public.appointment
  for each row execute function public.check_appointment_partner();

-- Any change to a doctor-day's appointments bumps its status row, which is
-- what patients' queue screens listen to.
create function public.bump_queue() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.doctor_day_status (doctor_id, day, queue_version, now_serving)
  values (new.doctor_id, new.day, 1,
          case when new.status = 'in_consult' then new.token_no end)
  on conflict (doctor_id, day) do update
     set queue_version = public.doctor_day_status.queue_version + 1,
         now_serving   = case when new.status = 'in_consult' then new.token_no
                              else public.doctor_day_status.now_serving end,
         updated_at    = now();
  return new;
end $$;

create trigger appointment_bumps_queue
  after insert or update of status on public.appointment
  for each row execute function public.bump_queue();

-- -------------------------------------------------------------- payments ----

-- Written only by the server (Razorpay webhook, service role), after it has
-- verified the signature. Test mode only in this build.
create table public.payment (
  id                  bigint generated always as identity primary key,
  appointment_id      bigint not null references public.appointment (id) on delete cascade,
  razorpay_order_id   text not null unique,
  razorpay_payment_id text unique,
  amount_inr          integer not null check (amount_inr > 0),
  status              text not null default 'created'
                        check (status in ('created', 'paid', 'failed', 'refunded')),
  created_at          timestamptz not null default now()
);

-- ------------------------------------------------------------- functions ----

-- The only way a patient creates an appointment. Validates the slot against
-- the doctor's schedule, serialises per doctor so two taps cannot take one
-- seat, and hands out the next token for the day.
create function public.book_appointment(
  p_doctor_id  bigint,
  p_slot_start timestamptz,
  p_pay_mode   public.pay_mode default 'at_counter'
)
returns public.appointment
language plpgsql security definer set search_path = public as $$
declare
  uid     uuid := auth.uid();
  doc     public.doctor;
  v_rule    public.schedule_rule;
  local_ts timestamp;
  today   public.doctor_state;
  free    smallint;
  token   integer;
  booked  public.appointment;
begin
  if uid is null then
    raise exception 'sign in to book' using errcode = '28000';
  end if;
  if not exists (select 1 from public.patient_profile where user_id = uid) then
    raise exception 'complete your profile before booking';
  end if;

  select * into doc from public.doctor where id = p_doctor_id and active;
  if not found then
    raise exception 'no such doctor';
  end if;
  if p_slot_start <= now() then
    raise exception 'that slot has already started';
  end if;
  if p_slot_start > now() + interval '30 days' then
    raise exception 'bookings open 30 days ahead';
  end if;

  local_ts := p_slot_start at time zone 'Asia/Kolkata';
  select * into v_rule from public.schedule_rule r
   where r.doctor_id = p_doctor_id
     and r.weekday = extract(dow from local_ts)
     and local_ts::time >= r.starts and local_ts::time < r.ends
     and extract(epoch from (local_ts::time - r.starts))::int % (r.slot_minutes * 60) = 0
   limit 1;
  if not found then
    raise exception 'not a bookable slot for this doctor';
  end if;

  select s.state into today from public.doctor_day_status s
   where s.doctor_id = p_doctor_id and s.day = local_ts::date;
  if today = 'on_leave' then
    raise exception 'the doctor is on leave that day';
  end if;

  perform pg_advisory_xact_lock(p_doctor_id);

  if exists (
    select 1 from public.appointment
     where patient_id = uid and doctor_id = p_doctor_id and day = local_ts::date
       and status not in ('cancelled', 'no_show')
  ) then
    raise exception 'you already have a booking with this doctor that day';
  end if;

  select min(seat_no)::smallint into free
    from generate_series(1, v_rule.per_slot) as seat_no
   where seat_no not in (
     select a.seat from public.appointment a
      where a.doctor_id = p_doctor_id and a.slot_start = p_slot_start
        and a.status <> 'cancelled'
   );
  if free is null then
    raise exception 'that slot is full';
  end if;

  select coalesce(max(token_no), 0) + 1 into token
    from public.appointment where doctor_id = p_doctor_id and day = local_ts::date;

  insert into public.appointment
    (patient_id, doctor_id, provider_id, day, slot_start, slot_minutes, seat, token_no,
     pay_mode, fee_inr)
  values
    (uid, p_doctor_id, doc.provider_id, local_ts::date, p_slot_start, v_rule.slot_minutes, free,
     token, p_pay_mode, doc.fee_inr)
  returning * into booked;
  return booked;
end $$;

create function public.cancel_appointment(p_appointment_id bigint)
returns public.appointment
language plpgsql security definer set search_path = public as $$
declare
  result public.appointment;
begin
  update public.appointment
     set status = 'cancelled'
   where id = p_appointment_id and patient_id = auth.uid()
     and status = 'booked' and slot_start > now()
  returning * into result;
  if not found then
    raise exception 'nothing to cancel: not yours, already started, or not in booked state';
  end if;
  return result;
end $$;

-- Staff move a patient through the day. Transitions are checked so a no-show
-- cannot quietly become "done".
create function public.set_appointment_status(
  p_appointment_id bigint,
  p_status         public.appointment_status
)
returns public.appointment
language plpgsql security definer set search_path = public as $$
declare
  appt public.appointment;
  result  public.appointment;
begin
  select * into appt from public.appointment where id = p_appointment_id;
  if not found or not public.is_staff_of(appt.provider_id) then
    raise exception 'no such appointment at your provider';
  end if;
  if not (
    (appt.status = 'booked'     and p_status in ('checked_in', 'no_show', 'cancelled')) or
    (appt.status = 'checked_in' and p_status in ('in_consult', 'no_show')) or
    (appt.status = 'in_consult' and p_status = 'done')
  ) then
    raise exception 'cannot move an appointment from % to %', appt.status, p_status;
  end if;
  update public.appointment set status = p_status where id = p_appointment_id
  returning * into result;
  return result;
end $$;

-- "Dr X is in OPD - 4 ahead of you - about 25 min". The estimate is labelled
-- as one in the UI; it is arithmetic, not a promise.
create function public.queue_position(p_appointment_id bigint)
returns table (
  token_no      integer,
  status        public.appointment_status,
  people_ahead  integer,
  doctor_state  public.doctor_state,
  delay_min     smallint,
  now_serving   integer,
  estimated_at  timestamptz
)
language plpgsql stable security definer set search_path = public as $$
declare
  a public.appointment;
  s public.doctor_day_status;
  ahead integer;
begin
  select * into a from public.appointment where id = p_appointment_id;
  if not found or (a.patient_id <> auth.uid() and not public.is_staff_of(a.provider_id)) then
    raise exception 'no such appointment';
  end if;
  select * into s from public.doctor_day_status where doctor_id = a.doctor_id and day = a.day;

  select count(*)::int into ahead from public.appointment b
   where b.doctor_id = a.doctor_id and b.day = a.day
     and b.status in ('booked', 'checked_in')
     and (b.slot_start, b.seat) < (a.slot_start, a.seat);

  return query select
    a.token_no, a.status, ahead,
    coalesce(s.state, 'not_arrived'::public.doctor_state),
    coalesce(s.delay_min, 0::smallint),
    s.now_serving,
    greatest(
      a.slot_start + make_interval(mins => coalesce(s.delay_min, 0)),
      now() + make_interval(mins => ahead * a.slot_minutes)
    );
end $$;

-- ------------------------------------------------------------------ RLS ----

alter table public.provider_staff    enable row level security;
alter table public.doctor            enable row level security;
alter table public.schedule_rule     enable row level security;
alter table public.doctor_day_status enable row level security;
alter table public.patient_profile   enable row level security;
alter table public.appointment       enable row level security;
alter table public.payment           enable row level security;

create policy "staff see their own memberships" on public.provider_staff
  for select to authenticated using (user_id = auth.uid());

-- Doctors, schedules and today's status are public for partner providers:
-- they are what a patient looks at before booking.
create policy "read partner doctors" on public.doctor
  for select to anon, authenticated
  using (active and exists (
    select 1 from public.provider p where p.id = provider_id and p.partner_status <> 'none'
  ));
create policy "staff read own doctors" on public.doctor
  for select to authenticated using (public.is_staff_of(provider_id));
create policy "staff add doctors" on public.doctor
  for insert to authenticated with check (public.is_staff_of(provider_id));
create policy "staff edit doctors" on public.doctor
  for update to authenticated
  using (public.is_staff_of(provider_id)) with check (public.is_staff_of(provider_id));

create policy "read schedules" on public.schedule_rule
  for select to anon, authenticated using (true);
create policy "staff write schedules" on public.schedule_rule
  for all to authenticated
  using (exists (select 1 from public.doctor d where d.id = doctor_id and public.is_staff_of(d.provider_id)))
  with check (exists (select 1 from public.doctor d where d.id = doctor_id and public.is_staff_of(d.provider_id)));

create policy "read doctor status" on public.doctor_day_status
  for select to anon, authenticated using (true);
create policy "staff set doctor status" on public.doctor_day_status
  for insert to authenticated
  with check (exists (select 1 from public.doctor d where d.id = doctor_id and public.is_staff_of(d.provider_id)));
create policy "staff update doctor status" on public.doctor_day_status
  for update to authenticated
  using (exists (select 1 from public.doctor d where d.id = doctor_id and public.is_staff_of(d.provider_id)))
  with check (exists (select 1 from public.doctor d where d.id = doctor_id and public.is_staff_of(d.provider_id)));

create policy "patients read own profile" on public.patient_profile
  for select to authenticated using (user_id = auth.uid());
create policy "patients create own profile" on public.patient_profile
  for insert to authenticated with check (user_id = auth.uid());
create policy "patients update own profile" on public.patient_profile
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
-- Registration sharing: a partner sees the profile of a patient who booked
-- with it, and nobody else's.
create policy "staff read their patients" on public.patient_profile
  for select to authenticated
  using (exists (
    select 1 from public.appointment a
     where a.patient_id = user_id and public.is_staff_of(a.provider_id)
  ));

-- No insert or update policies: appointments change only through the
-- functions above.
create policy "patients read own appointments" on public.appointment
  for select to authenticated using (patient_id = auth.uid());
create policy "staff read their appointments" on public.appointment
  for select to authenticated using (public.is_staff_of(provider_id));

create policy "patients read own payments" on public.payment
  for select to authenticated
  using (exists (
    select 1 from public.appointment a where a.id = appointment_id and a.patient_id = auth.uid()
  ));

-- ------------------------------------------------------------- realtime ----

do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table public.doctor_day_status, public.appointment;
  end if;
end $$;

import 'package:flutter/painting.dart';

import 'format.dart';

// Plain classes for what the API returns, each built from its JSON.

/// A diagnostic test, with its price range across every hospital.
class TestItem {
  TestItem.fromJson(Map<String, dynamic> json)
    : id = json['id'],
      name = json['name'],
      shortName = json['short_name'],
      category = json['category'],
      about = json['about'],
      preparation = json['preparation'],
      reportIn = json['report_in'],
      homeCollection = json['home_collection'],
      aliases = List<String>.from(json['aliases']),
      labCount = json['lab_count'],
      minPrice = json['min_price'],
      maxPrice = json['max_price'];

  final String id, name, shortName, category, about, preparation, reportIn;

  /// Whether the sample can be taken at home. Never true for an X-ray.
  final bool homeCollection;

  /// Other names the test goes by, so "haemogram" finds the CBC.
  final List<String> aliases;

  final int labCount;
  final int? minPrice, maxPrice;

  /// Whether the text in the search box matches any name this test goes by.
  bool matches(String query) => _mentions([name, shortName, category, ...aliases], query);

  bool get hasPreparation => needsPreparation(preparation);
}

/// A price, and where and when it came from. No price is shown without both.
class Price {
  Price.fromJson(Map<String, dynamic> json)
    : amount = json['amount'],
      source = json['source'],
      asOf = DateTime.parse(json['as_of']);

  final int amount;
  final String source;
  final DateTime asOf;
}

class Hospital {
  Hospital.fromJson(Map<String, dynamic> json)
    : id = json['id'],
      name = json['name'],
      area = json['area'],
      address = json['address'],
      rating = (json['rating'] as num).toDouble(),
      reviews = json['reviews'],
      distanceKm = (json['distance_km'] as num).toDouble(),
      nabl = json['nabl'],
      homeCollection = json['home_collection'],
      homeCollectionFee = json['home_collection_fee'],
      partner = json['partner'],
      openHours = json['open_hours'],
      brandColor = _hexColor(json['brand_color']),
      prices = {
        for (final entry in (json['prices'] as Map<String, dynamic>).entries)
          entry.key: Price.fromJson(entry.value),
      };

  final String id, name, area, address, openHours;
  final double rating, distanceKm;
  final int reviews;

  /// Accredited by India's National Accreditation Board for labs.
  final bool nabl;

  final bool homeCollection;
  final int? homeCollectionFee;

  /// Partners signed up to take bookings. Everyone else is listed so you can
  /// compare prices, but can't be booked.
  final bool partner;

  /// The colour of the tree the hospital is named after.
  final Color brandColor;

  final Map<String, Price> prices;

  /// What this hospital charges for a test, or null if it doesn't offer it.
  int? priceOf(String testId) => prices[testId]?.amount;
}

/// A kind of doctor, such as Cardiology.
class Specialty {
  Specialty.fromJson(Map<String, dynamic> json) : id = json['id'], name = json['name'];

  final String id, name;

  /// The name's first word, for tight spaces: "Diabetes & Endocrinology" ->
  /// "Diabetes".
  String get shortName => name.split(' ').first;
}

/// A consultant at a partner hospital. Every one of them is made up.
class Doctor {
  Doctor.fromJson(Map<String, dynamic> json)
    : id = json['id'],
      name = json['name'],
      specialty = json['specialty'],
      specialtyName = json['specialty_name'],
      qualifications = json['qualifications'],
      about = json['about'],
      experienceYears = json['experience_years'],
      languages = List<String>.from(json['languages']),
      days = List<String>.from(json['days']),
      slots = {
        for (final entry in (json['slots'] as Map<String, dynamic>).entries)
          entry.key: List<String>.from(entry.value),
      },
      fee = Price.fromJson(json['fee']),
      rating = (json['rating'] as num).toDouble(),
      reviews = json['reviews'],
      hospital = HospitalSummary.fromJson(json['hospital']);

  /// [specialty] is the specialty's id, [specialtyName] what it's called.
  final String id, name, specialty, specialtyName, qualifications, about;
  final int experienceYears, reviews;
  final List<String> languages;

  /// The days they see patients: "Mon", "Wed"...
  final List<String> days;

  /// The time slots in each of their sessions: {"Morning": ["09:00", ...]}.
  final Map<String, List<String>> slots;

  /// The consultation fee, with where it came from.
  final Price fee;

  final double rating;
  final HospitalSummary hospital;

  /// [days] as [DateTime.weekday] numbers, for the booking day strip.
  Set<int> get weekdays => {for (final day in days) weekdayNumber(day)};

  /// Whether the text in the search box matches their name or specialty.
  bool matches(String query) => _mentions([name, specialtyName], query);
}

/// Where a doctor works: just enough of the hospital to say where it is.
class HospitalSummary {
  HospitalSummary.fromJson(Map<String, dynamic> json)
    : id = json['id'],
      name = json['name'],
      area = json['area'],
      brandColor = _hexColor(json['brand_color']),
      distanceKm = (json['distance_km'] as num).toDouble();

  final String id, name, area;
  final Color brandColor;
  final double distanceKm;
}

/// A booked test, or an appointment with a doctor.
class Booking {
  Booking.fromJson(Map<String, dynamic> json)
    : id = json['id'],
      isDoctor = json['kind'] == 'doctor',
      title = json['title'],
      subtitle = json['subtitle'],
      hospitalName = json['hospital_name'],
      hospitalArea = json['hospital_area'],
      brandColor = _hexColor(json['brand_color']),
      date = DateTime.parse(json['date']),
      time = json['time'],
      homeCollection = json['home_collection'],
      price = json['price'],
      homeCollectionFee = json['home_collection_fee'],
      total = json['total'],
      preparation = json['preparation'];

  /// Whether it's an appointment with a doctor rather than a test.
  final bool isDoctor;

  /// [title] is the test's or the doctor's name; [subtitle] the test's short
  /// name or the doctor's specialty.
  final String id, title, subtitle, hospitalName, hospitalArea, time, preparation;
  final Color brandColor;
  final DateTime date;
  final bool homeCollection;
  final int price, homeCollectionFee, total;

  bool get hasPreparation => needsPreparation(preparation);
}

/// Whether a test's preparation note asks for something, like fasting,
/// rather than saying there's nothing to do ("No fasting needed").
bool needsPreparation(String note) => !note.toLowerCase().startsWith('no ');

/// Whether [query], as typed in a search box, appears in any of [names].
bool _mentions(Iterable<String> names, String query) {
  final q = query.trim().toLowerCase();
  return names.any((name) => name.toLowerCase().contains(q));
}

/// "#7C5CD6" -> an opaque Color.
Color _hexColor(String hex) => Color(int.parse(hex.substring(1), radix: 16) | 0xFF000000);

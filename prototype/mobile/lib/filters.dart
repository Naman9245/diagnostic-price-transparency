import 'models.dart';

/// The orders a list of labs can be put in.
enum SortBy {
  cheapest('Price: low to high', 'Cheapest first'),
  priciest('Price: high to low', 'Priciest first'),
  nearest('Distance', 'Nearest first'),
  rating('Rating', 'Top rated first');

  const SortBy(this.label, this.chipLabel);

  final String label, chipLabel;

  /// Orders two labs that both offer [testId].
  int compare(Hospital a, Hospital b, String testId) => switch (this) {
    cheapest => a.priceOf(testId)!.compareTo(b.priceOf(testId)!),
    priciest => b.priceOf(testId)!.compareTo(a.priceOf(testId)!),
    nearest => nearestFirst(a, b),
    rating => b.rating.compareTo(a.rating),
  };
}

/// The filter chips. Each keeps only the labs that pass its test.
enum LabFilter {
  rated4('Rating 4.0+'),
  near('Within 5 km'),
  bookable('Book online'),
  homeCollection('Home collection'),
  nabl('NABL accredited');

  const LabFilter(this.label);

  final String label;

  bool keeps(Hospital hospital) => switch (this) {
    rated4 => hospital.rating >= 4.0,
    near => hospital.distanceKm <= 5,
    bookable => hospital.partner,
    homeCollection => hospital.homeCollection,
    nabl => hospital.nabl,
  };
}

/// For sorting labs by distance: `labs.sort(nearestFirst)`.
int nearestFirst(Hospital a, Hospital b) => a.distanceKm.compareTo(b.distanceKm);

extension LabList on Iterable<Hospital> {
  /// The labs that pass every one of [filters].
  List<Hospital> passing(Set<LabFilter> filters) => [
    for (final lab in this)
      if (filters.every((filter) => filter.keeps(lab))) lab,
  ];
}

extension Toggle<T> on Set<T> {
  /// Adds [value] if it's missing, removes it if it's there.
  void toggle(T value) {
    if (!remove(value)) add(value);
  }
}

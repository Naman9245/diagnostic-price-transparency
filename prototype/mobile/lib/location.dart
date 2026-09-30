import 'package:flutter/foundation.dart';

/// A neighbourhood you can pick as "where I am". Distances are measured from
/// its centre, as the crow flies.
class Area {
  const Area(this.name, this.lat, this.lng);

  final String name;
  final double lat, lng;
}

const areas = [
  Area('Koramangala', 12.9352, 77.6245),
  Area('Indiranagar', 12.9719, 77.6412),
  Area('Jayanagar', 12.9299, 77.5826),
  Area('Whitefield', 12.9698, 77.7500),
  Area('Hebbal', 13.0358, 77.5970),
];

/// Where you are. The home screen changes it; every search reads it.
final currentArea = ValueNotifier<Area>(areas.first);

/// The time in Bengaluru, whatever the phone's own time zone, because
/// bookings are made in India Standard Time (UTC+5:30, no daylight saving).
DateTime istNow() => istAt(DateTime.now());

/// [instant] as a clock in India reads it: a plain local DateTime whose
/// fields are Indian time.
DateTime istAt(DateTime instant) =>
    instant.toUtc().add(const Duration(hours: 5, minutes: 30)).copyWith(isUtc: false);

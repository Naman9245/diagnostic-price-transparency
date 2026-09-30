import 'package:flutter/material.dart';

import '../format.dart';
import '../models.dart';
import '../theme.dart';
import 'pressable.dart';

/// A tappable surface: fill, shape, ripple and press animation in one. The
/// app's chips, pills and small buttons are all built on it.
class TapSurface extends StatelessWidget {
  const TapSurface({
    super.key,
    required this.onTap,
    required this.child,
    this.color = Colors.transparent,
    this.shape = const StadiumBorder(),
    this.scale = 0.95,
    this.selected,
  });

  final VoidCallback? onTap;
  final Widget child;
  final Color color;
  final ShapeBorder shape;

  /// How far it shrinks when pressed. 1 means it doesn't: rows use that,
  /// because the buttons inside them animate on their own.
  final double scale;

  /// For screen readers: whether this is the chosen option.
  final bool? selected;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      enabled: onTap != null,
      selected: selected,
      child: Pressable(
        scale: scale,
        enabled: onTap != null && scale < 1,
        child: Material(
          color: color,
          shape: shape,
          child: InkWell(customBorder: shape, onTap: onTap, child: child),
        ),
      ),
    );
  }
}

/// The main button on a screen: full width and filled teal, with a spinner
/// in place of the label while [busy].
class PrimaryButton extends StatelessWidget {
  const PrimaryButton({super.key, required this.label, required this.onPressed, this.busy = false});

  final String label;
  final VoidCallback? onPressed;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      enabled: onPressed != null && !busy,
      child: SizedBox(
        width: double.infinity,
        child: FilledButton(
          onPressed: busy ? null : onPressed,
          child: busy
              ? const SizedBox.square(
                  dimension: 22,
                  child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white),
                )
              : Text(label),
        ),
      ),
    );
  }
}

/// The small button at the end of a list row: filled for the main action
/// ("Book Now"), outlined for everything else ("View").
class RowButton extends StatelessWidget {
  const RowButton({super.key, required this.label, required this.onPressed, this.filled = true});

  final String label;
  final VoidCallback onPressed;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    const size = Size(0, 32);
    const padding = EdgeInsets.symmetric(horizontal: 14);
    const shape = RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(8)));
    const text = TextStyle(fontFamily: kFontFamily, fontSize: 12.5, fontWeight: FontWeight.w700);
    return Pressable(
      child: filled
          ? FilledButton(
              onPressed: onPressed,
              style: FilledButton.styleFrom(
                minimumSize: size,
                padding: padding,
                shape: shape,
                textStyle: text,
              ),
              child: Text(label),
            )
          : OutlinedButton(
              onPressed: onPressed,
              style: OutlinedButton.styleFrom(
                minimumSize: size,
                padding: padding,
                shape: shape,
                textStyle: text,
              ),
              child: Text(label),
            ),
    );
  }
}

/// A round, outlined icon button, like the ones in the design's headers. The
/// circle is 40 wide, but a tap anywhere in the 48 around it counts: the
/// smallest touch target the accessibility guidelines allow.
class CircleIconButton extends StatelessWidget {
  const CircleIconButton({
    super.key,
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.color = AppColors.ink,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: TapSurface(
        onTap: onPressed,
        shape: const CircleBorder(),
        scale: 0.9,
        child: SizedBox.square(
          dimension: 48,
          child: Center(
            // Ink, not a plain box, so the ripple shows over the circle too.
            child: Ink(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
                border: Border.all(color: AppColors.line),
              ),
              child: Icon(icon, size: 19, color: color),
            ),
          ),
        ),
      ),
    );
  }
}

/// The back button on every page that opens on top of the tabs.
class BackCircle extends StatelessWidget {
  const BackCircle({super.key});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: CircleIconButton(
        icon: Icons.arrow_back_ios_new_rounded,
        tooltip: 'Back',
        onPressed: () => Navigator.maybePop(context),
      ),
    );
  }
}

/// The app bar of a page that opens on top of the tabs: a round back button,
/// a centred title and, on a page about something made up, the DEMO badge.
AppBar pageBar({Widget? title, bool demo = false}) => AppBar(
  leading: const BackCircle(),
  leadingWidth: 64,
  title: title,
  actions: [if (demo) const Padding(padding: EdgeInsets.only(right: 16), child: DemoBadge())],
);

/// A rating the way booking apps show it: a yellow star, the score and how
/// many people rated, as in "★ 4.4 (2.1K)". Scores under 3.5 turn coral, so
/// a cheap but poorly rated lab doesn't look as good as it sounds.
class Rating extends StatelessWidget {
  const Rating(this.rating, {super.key, this.count});

  final double rating;
  final int? count;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.star_rounded, size: 16, color: AppColors.star),
        const SizedBox(width: 3),
        Text(
          rating.toStringAsFixed(1),
          style: TextStyle(
            fontSize: 12.5,
            fontWeight: FontWeight.w700,
            color: rating < 3.5 ? AppColors.coral : AppColors.ink,
          ),
        ),
        if (count != null)
          Text(
            ' (${compactCount(count!)})',
            style: const TextStyle(fontSize: 12.5, color: AppColors.slate),
          ),
      ],
    );
  }
}

/// The yellow badge on everything that's made up. Every hospital in this
/// prototype is fictional, so it's on every hospital.
class DemoBadge extends StatelessWidget {
  const DemoBadge({super.key});

  @override
  Widget build(BuildContext context) {
    return const DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.demo,
        borderRadius: BorderRadius.all(Radius.circular(5)),
      ),
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        child: Text(
          'DEMO',
          style: TextStyle(
            fontSize: 9.5,
            fontWeight: FontWeight.w800,
            letterSpacing: 1,
            color: AppColors.ink,
          ),
        ),
      ),
    );
  }
}

/// A yellow strip with the DEMO badge, saying what's made up: under the
/// search box on Home, and wherever the demo behaves unlike a real app.
class DemoNotice extends StatelessWidget {
  const DemoNotice({
    super.key,
    this.text = 'Every hospital, doctor and price here is made up for this demo.',
  });

  final String text;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: Color(0xFFFFF8E1),
        borderRadius: BorderRadius.all(Radius.circular(12)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            const DemoBadge(),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                text,
                style: const TextStyle(fontSize: 12.5, color: AppColors.ink, height: 1.3),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The DEMO badge and one line of muted text: where a made-up lab or doctor
/// is, as in "DEMO Koramangala · 1.2 km".
class DemoLine extends StatelessWidget {
  const DemoLine(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const DemoBadge(),
        const SizedBox(width: 6),
        Flexible(
          child: Text(text, style: AppText.muted, maxLines: 1, overflow: TextOverflow.ellipsis),
        ),
      ],
    );
  }
}

/// The top of a profile page, as in the design: a round picture, then the
/// name, one line about them and the rating.
class ProfileHeader extends StatelessWidget {
  const ProfileHeader({
    super.key,
    required this.picture,
    required this.name,
    required this.detail,
    required this.rating,
    required this.reviews,
  });

  final Widget picture;
  final String name, detail;
  final double rating;
  final int reviews;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        picture,
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: AppText.heading),
              const SizedBox(height: 4),
              Text(detail, style: AppText.muted),
              const SizedBox(height: 6),
              Rating(rating, count: reviews),
            ],
          ),
        ),
      ],
    );
  }
}

/// A section's title, with an optional link on the right:
/// "Labs near you                    See all ›"
class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.action, this.onAction});

  final String title;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: Text(title, style: AppText.section)),
        if (action != null)
          TapSurface(
            onTap: onAction,
            shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(8))),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              child: Row(
                children: [
                  Text(
                    action!,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppColors.teal,
                    ),
                  ),
                  const Icon(Icons.chevron_right_rounded, size: 18, color: AppColors.teal),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

/// A small tinted label with an icon: "✓ NABL accredited".
class MintPill extends StatelessWidget {
  const MintPill({super.key, required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppColors.mint,
        borderRadius: BorderRadius.all(Radius.circular(20)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: AppColors.tealDark),
            const SizedBox(width: 5),
            Flexible(
              child: Text(
                text,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppColors.tealDark,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A rounded filter chip: mint with a teal outline when it's on.
class FilterPill extends StatelessWidget {
  const FilterPill({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
    this.icon,
    this.trailingIcon,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final IconData? icon, trailingIcon;

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppColors.tealDark : AppColors.ink;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: TapSurface(
        onTap: onTap,
        selected: selected,
        color: selected ? AppColors.mint : Colors.white,
        shape: StadiumBorder(side: BorderSide(color: selected ? AppColors.teal : AppColors.line)),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[Icon(icon, size: 16, color: color), const SizedBox(width: 6)],
              Text(
                label,
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color),
              ),
              if (trailingIcon != null) ...[
                const SizedBox(width: 2),
                Icon(trailingIcon, size: 18, color: color),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// A row of options inside one pill, the chosen one filled teal:
/// ( Morning | Afternoon | Evening )
class SegmentedPills<T> extends StatelessWidget {
  const SegmentedPills({
    super.key,
    required this.options,
    required this.selected,
    required this.onChanged,
  });

  /// Each option's value and its label, in order.
  final Map<T, String> options;
  final T selected;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppColors.cloud,
        borderRadius: BorderRadius.all(Radius.circular(26)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(4),
        child: Row(
          children: [
            for (final MapEntry(key: value, value: label) in options.entries)
              Expanded(
                child: TapSurface(
                  onTap: () => onChanged(value),
                  selected: value == selected,
                  color: value == selected ? AppColors.teal : Colors.transparent,
                  scale: 0.96,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Text(
                      label,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: value == selected ? Colors.white : AppColors.slate,
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// A dashed line, used above totals the way receipts separate them.
class DashedDivider extends StatelessWidget {
  const DashedDivider({super.key});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) => Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: List.filled(
          (constraints.maxWidth / 7).floor(),
          const SizedBox(width: 4, height: 1, child: ColoredBox(color: Color(0xFFD5DADD))),
        ),
      ),
    );
  }
}

/// A yellow note about what to do before a test, like fasting.
class PrepNote extends StatelessWidget {
  const PrepNote(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppColors.caution,
        borderRadius: BorderRadius.all(Radius.circular(12)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            const Icon(Icons.info_outline_rounded, size: 18, color: AppColors.cautionInk),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                text,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.cautionInk,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Where a price came from and when, as in "Jacaranda rate card · 12 Sep
/// 2026". Lists stay compact, so it's shown on each price's own page, where
/// you book: the test's price card and the doctor's fee card.
class SourceLine extends StatelessWidget {
  const SourceLine(this.price, {super.key});

  final Price price;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(Icons.receipt_long_outlined, size: 16, color: AppColors.slate),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            '${price.source} · ${longDate(price.asOf)}',
            style: const TextStyle(fontSize: 12, color: AppColors.slate),
          ),
        ),
      ],
    );
  }
}

/// What a screen shows when there's nothing to list yet: an icon, a title,
/// a line of explanation and, optionally, a button that does something
/// about it.
class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.action,
    this.onAction,
  });

  final IconData icon;
  final String title, message;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircleAvatar(
              radius: 34,
              backgroundColor: AppColors.mint,
              child: Icon(icon, size: 32, color: AppColors.teal),
            ),
            const SizedBox(height: 14),
            Text(title, textAlign: TextAlign.center, style: AppText.section),
            const SizedBox(height: 6),
            Text(message, textAlign: TextAlign.center, style: AppText.muted),
            if (action != null) ...[
              const SizedBox(height: 18),
              PrimaryButton(label: action!, onPressed: onAction),
            ],
          ],
        ),
      ),
    );
  }
}

/// What a screen shows when a request fails, with a way to try again.
class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 48, 24, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.cloud_off_rounded, size: 44, color: AppColors.slate),
          const SizedBox(height: 12),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 14.5, height: 1.45, color: AppColors.ink),
          ),
          const SizedBox(height: 16),
          Pressable(
            child: OutlinedButton(onPressed: onRetry, child: const Text('Try again')),
          ),
        ],
      ),
    );
  }
}

/// Placeholder rows that gently pulse while a list loads.
class LoadingRows extends StatefulWidget {
  const LoadingRows({super.key, this.count = 4});

  final int count;

  @override
  State<LoadingRows> createState() => _LoadingRowsState();
}

class _LoadingRowsState extends State<LoadingRows> with SingleTickerProviderStateMixin {
  late final _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
    lowerBound: 0.45,
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Hold still when the phone is set to reduce motion.
    if (MediaQuery.disableAnimationsOf(context)) {
      _pulse.value = 1;
    } else {
      _pulse.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _pulse,
      child: Column(children: List.filled(widget.count, const _PlaceholderRow())),
    );
  }
}

class _PlaceholderRow extends StatelessWidget {
  const _PlaceholderRow();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: Row(
        children: [
          CircleAvatar(radius: 26, backgroundColor: AppColors.cloud),
          SizedBox(width: 12),
          Expanded(
            child: SizedBox(
              height: 44,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: AppColors.cloud,
                  borderRadius: BorderRadius.all(Radius.circular(10)),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;

/// Etiketli açılır liste (saat, uzunluk vb.). [onChanged] null ise pasif.
class LabeledDropdown<T> extends StatelessWidget {
  const LabeledDropdown({
    super.key,
    required this.label,
    required this.value,
    required this.items,
    required this.itemLabel,
    required this.onChanged,
  });

  final String label;
  final T value;
  final List<T> items;
  final String Function(T) itemLabel;
  final ValueChanged<T>? onChanged;

  @override
  Widget build(BuildContext context) {
    return InputDecorator(
      decoration: InputDecoration(
        labelText: label,
        isDense: true,
        enabled: onChanged != null,
        border: const OutlineInputBorder(),
        contentPadding: const EdgeInsets.fromLTRB(10, 6, 4, 6),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<T>(
          value: items.contains(value) ? value : null,
          isExpanded: true,
          isDense: true,
          items: [
            for (final v in items)
              DropdownMenuItem<T>(value: v, child: Text(itemLabel(v), overflow: TextOverflow.ellipsis)),
          ],
          onChanged: onChanged == null ? null : (v) => onChanged!(v as T),
        ),
      ),
    );
  }
}

class HourDropdown extends StatelessWidget {
  const HourDropdown({super.key, required this.label, required this.value, required this.onChanged});
  final String label;
  final int value;
  final ValueChanged<int>? onChanged;

  @override
  Widget build(BuildContext context) => LabeledDropdown<int>(
        label: label,
        value: value,
        items: List.generate(24, (h) => h),
        itemLabel: fmt.hour,
        onChanged: onChanged,
      );
}

/// 24 saatlik kısıtlı saat çipleri (8 sütun). İşaretli saat kırmızı.
class HourChips extends StatelessWidget {
  const HourChips({super.key, required this.selected, required this.onToggle});
  final Set<int> selected;
  final ValueChanged<int>? onToggle;

  @override
  Widget build(BuildContext context) {
    final enabled = onToggle != null;
    return LayoutBuilder(builder: (context, c) {
      const gap = 4.0;
      final w = (c.maxWidth - gap * 7) / 8;
      return Wrap(
        spacing: gap,
        runSpacing: gap,
        children: [
          for (var h = 0; h < 24; h++)
            SizedBox(
              width: w,
              height: 32,
              child: Material(
                color: !enabled
                    ? const Color(0xFFF8F9FA)
                    : selected.contains(h)
                        ? th.bad
                        : const Color(0xFFF6F8FA),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(5),
                  side: BorderSide(
                    color: !enabled
                        ? const Color(0xFFE8ECF0)
                        : selected.contains(h)
                            ? th.bad
                            : const Color(0xFFD6DDE4),
                  ),
                ),
                child: InkWell(
                  borderRadius: BorderRadius.circular(5),
                  onTap: enabled ? () => onToggle!(h) : null,
                  child: Center(
                    child: Text(
                      h.toString().padLeft(2, '0'),
                      style: TextStyle(
                        fontSize: 13,
                        color: !enabled
                            ? const Color(0xFFB7BFC7)
                            : selected.contains(h)
                                ? Colors.white
                                : th.text,
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      );
    });
  }
}

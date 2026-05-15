#!/usr/bin/env python3
"""
Add HiDPI cursor sizes to .cursor config files.

New sizes (all clean integer scale factors):
  From _24.svg (24px base): 72px (x3), 96px (x4)  ->  name_24_72.png, name_24_96.png
  From base.svg (32px base): 128px (x4), 192px (x6), 256px (x8) ->  name_128.png, name_192.png, name_256.png

Each cursor frame consists of 4 lines (24, 32, 48, 64).
New size entries are inserted after each frame block.
"""

import os
import re
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE, "config")
BACKUP_DIR = os.path.join(BASE, "config_backup")

# New size sources: (new_size, svg_type, scale_factor)
# svg_type "24" = from _24.svg, "base" = from base .svg
NEW_BY_SVG = {
    "24": [(72, 3), (96, 4)],
    "base": [(128, 4), (192, 6), (256, 8)],
}

LINE_RE = re.compile(r'^(\d+)\s+(\d+)\s+(\d+)\s+(\S+?)(?:\s+(\d+))?\s*$')
FILENAME_RE = re.compile(r'^(.+?)_24_(\d+)\.png$')
FILENAME_RE_BASE = re.compile(r'^(.+?)_(\d+)\.png$')


def parse_entry(line):
    """Parse one line -> (size, hx, hy, fname, svg_type, base_name, delay) or None"""
    m = LINE_RE.match(line)
    if not m:
        return None
    size = int(m.group(1))
    hx = int(m.group(2))
    hy = int(m.group(3))
    fname = m.group(4)
    delay = int(m.group(5)) if m.group(5) else None

    m2 = FILENAME_RE.match(fname)
    if m2:
        return (size, hx, hy, fname, "24", m2.group(1), delay)
    m2 = FILENAME_RE_BASE.match(fname)
    if m2:
        bn = m2.group(1)
        # If the number is "24", that's ambiguous - could be name_24.png
        # But we handle _24_ explicitly above, so this is the base variant
        return (size, hx, hy, fname, "base", bn, delay)
    return None


def format_entry(size, hx, hy, fname, delay):
    if delay is not None:
        return f"{size} {hx} {hy} {fname} {delay}"
    return f"{size} {hx} {hy} {fname}"


def make_new_fname(base_name, svg_type, new_size):
    if svg_type == "24":
        return f"{base_name}_24_{new_size}.png"
    return f"{base_name}_{new_size}.png"


def process_file(filepath):
    with open(filepath, 'r') as f:
        raw_lines = f.readlines()

    entries = []
    for line in raw_lines:
        entry = parse_entry(line.strip())
        if entry:
            entries.append(entry)
        else:
            entries.append(None)

    if not any(e is not None for e in entries):
        return False

    # Build new output: group consecutive related entries into "frames"
    # A frame is a set of entries sharing the same base_name
    # We process entries in order, inserting new sizes after each frame.
    new_lines = []
    i = 0
    n = len(entries)
    frame_emitted = set()  # (base_name,) already had new sizes added

    while i < n:
        entry = entries[i]
        raw = raw_lines[i].rstrip('\n')

        if entry is None:
            new_lines.append(raw)
            i += 1
            continue

        size, hx, hy, fname, svg_type, base_name, delay = entry

        # Emit the original line
        new_lines.append(raw)

        # Determine frame key (base_name+delay for animated frames)
        frame_key = (base_name, delay if delay is not None else 0, svg_type)

        # Check if this is the LAST line of its SVG type in this frame block.
        # Strategy: Look ahead: if the next entry has different base_name or
        # a size LARGER than the current one (meaning same frame, bigger size),
        # or if the next entry is for a different frame (same base_name, same size), 
        # then we should insert new sizes AFTER completing all existing sizes for
        # this SVG type in this frame.
        #
        # Actually simpler: For each frame block (same base_name), we process
        # all 4 size lines, then add new sizes. A frame block ends when
        # the base_name changes or we hit end-of-file.
        #
        # But we need to emit new sizes for each SVG type once per frame.
        # Track which SVG types have had their new sizes added per frame.

        # Let me use a different approach: first group entries into frames.
        i += 1

    # OK, let me restart with a cleaner approach.
    return process_file_clean(filepath)


def process_file_clean(filepath):
    """Clean approach: group entries into frames, add new sizes per frame."""
    with open(filepath, 'r') as f:
        raw_lines = f.readlines()

    # Parse all entries, preserving original text for non-matching lines
    frames = []  # Each frame is a list of tuples (orig_line, entry_dict or None)
    current_frame = []

    for line in raw_lines:
        stripped = line.rstrip('\n')
        entry = parse_entry(stripped)
        current_frame.append((stripped, entry))

    # Since all entries follow the pattern, we'll split by base_name groups.
    # Entries look like:
    #   Frame 1: 24 hx hy name_24_24.png [delay], 32 hx hy name_32.png [delay],
    #            48 hx hy name_24_48.png [delay], 64 hx hy name_64.png [delay]
    #   Frame 2: 24 hx hy name2_24_24.png [delay], ...
    # Empty lines or comments separate frames in animated cursors (none here)

    # Build the output:
    new_all = []
    # Track which base_name+svg_type combos we've already emitted new
    # entries for within the current logical block.
    # A "logical block" is a group of lines where base_name stays the same.
    # When base_name changes, the block is complete.

    # Actually, let me just group lines into "frames" where each frame
    # has 4 consecutive lines with sizes 24, 32, 48, 64.

    block_done = {}  # (base_name, svg_type) -> True if already emitted new sizes

    for orig_line, entry in current_frame:
        new_all.append(orig_line)

        if entry is None:
            continue

        size, hx, hy, fname, svg_type, base_name, delay = entry
        key = (base_name, svg_type)

        if key in block_done:
            continue

        # Check if this is the last line for this SVG type in this frame block.
        # Since all frames have sizes in order 24, 32, 48, 64, and _24.svg
        # entries have sizes 24 and 48, while base entries have 32 and 64,
        # the LAST entry of a type would be the one with the larger size.
        is_last_for_type = False
        if svg_type == "24" and size == 48:
            is_last_for_type = True
        elif svg_type == "base" and size == 64:
            is_last_for_type = True

        if not is_last_for_type:
            # Check if this is the only entry for this svg_type in the frame
            # e.g., some frames might not have all 4 sizes
            # Look ahead to see if a larger size for the same type exists
            idx = current_frame.index((orig_line, entry))
            has_larger = False
            for j in range(idx + 1, len(current_frame)):
                nj = current_frame[j][1]
                if nj is None:
                    continue
                ns, _, _, _, nst, nbn, _ = nj
                if nbn != base_name:
                    break
                if nst == svg_type and ns > size:
                    has_larger = True
                    break
            is_last_for_type = not has_larger

        if not is_last_for_type:
            continue

        block_done[key] = True

        # Add new size entries for this SVG type
        if svg_type in NEW_BY_SVG:
            # Find reference hotspot from the SMALLEST entry of this svg_type
            ref_hx, ref_hy, ref_size = None, None, None
            size_24 = None
            delay_val = None
            for orig2, e2 in current_frame:
                if e2 is None:
                    continue
                s2, hx2, hy2, f2, st2, bn2, d2 = e2
                if bn2 == base_name and st2 == svg_type:
                    if ref_size is None or s2 < ref_size:
                        ref_hx, ref_hy, ref_size = hx2, hy2, s2
                        delay_val = d2

            if ref_size is not None:
                for new_size, scale in NEW_BY_SVG[svg_type]:
                    new_hx = round(ref_hx * scale)
                    new_hy = round(ref_hy * scale)
                    new_fname = make_new_fname(base_name, svg_type, new_size)
                    new_all.append(format_entry(new_size, new_hx, new_hy, new_fname, delay_val))

    if len(new_all) == sum(1 for l in raw_lines if l.strip()):
        return False  # no change

    # Backup
    rel = os.path.relpath(filepath, CONFIG_DIR)
    bk = os.path.join(BACKUP_DIR, rel)
    os.makedirs(os.path.dirname(bk), exist_ok=True)
    shutil.copy2(filepath, bk)

    # Write
    with open(filepath, 'w') as f:
        f.write('\n'.join(new_all) + '\n')

    n_old = sum(1 for l in raw_lines if l.strip())
    n_new = len(new_all)
    print(f"  ok {os.path.basename(filepath)}: {n_old} -> {n_new}")
    return True


def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    files = sorted(f for f in os.listdir(CONFIG_DIR) if f.endswith('.cursor'))
    print(f"Found {len(files)} cursor config files\n")

    mod = 0
    for fname in files:
        if process_file_clean(os.path.join(CONFIG_DIR, fname)):
            mod += 1

    print(f"\nModified {mod}/{len(files)} files, backups in {BACKUP_DIR}")


if __name__ == "__main__":
    main()

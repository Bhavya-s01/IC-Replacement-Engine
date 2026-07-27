"""
fix_placement.py — Moves the Supply Chain button from its current
wrong location into the expanded alternative card block.

Run once: python fix_placement.py
Then delete: del fix_placement.py
"""

import os

path = os.path.join("..", "ic-finder-ui", "src", "App.tsx")
if not os.path.exists(path):
    path = os.path.join("ic-finder-ui", "src", "App.tsx")
if not os.path.exists(path):
    # Try relative paths
    for p in ["../ic-finder-ui/src/App.tsx", "src/App.tsx"]:
        if os.path.exists(p):
            path = p
            break

print("Reading:", path)

with open(path, "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

print("Total lines:", len(lines))

# Step 1: Find the supply chain block boundaries
sc_start = None
sc_end = None
sc_block = []

for i, line in enumerate(lines):
    if "{/* Supply Chain Data */}" in line or "Supply Chain Data" in line and "button" not in line.lower():
        if "px-4 pb-4" in lines[i + 1] if i + 1 < len(lines) else False:
            sc_start = i
        elif sc_start is None:
            sc_start = i

if sc_start is not None:
    # Find the end of the supply chain block by counting braces
    depth = 0
    started = False
    for i in range(sc_start, len(lines)):
        line = lines[i]
        for ch in line:
            if ch == '{':
                depth += 1
                started = True
            elif ch == '}':
                depth -= 1
        sc_block.append(line)
        if started and depth <= 0:
            sc_end = i
            break

    if sc_end is None:
        # Fallback: take next 50 lines
        sc_end = min(sc_start + 50, len(lines) - 1)
        sc_block = lines[sc_start:sc_end + 1]

print("Supply chain block found: lines {}-{}".format(sc_start + 1, sc_end + 1))

# Step 2: Find the expanded alt block closing
# Look for the pattern: expandedAlt === idx && Object.keys(alt.spec_scores)
expanded_start = None
for i, line in enumerate(lines):
    if "expandedAlt === idx" in line and i > sc_end:
        expanded_start = i
        break

if expanded_start is None:
    print("ERROR: Could not find expandedAlt === idx block after line {}".format(sc_end))
    print("Searching all occurrences:")
    for i, line in enumerate(lines):
        if "expandedAlt === idx" in line:
            print("  Line {}: {}".format(i + 1, line.strip()[:80]))
    exit(1)

print("Expanded block starts at line:", expanded_start + 1)

# Find the closing of the expanded block
# It ends with )}  before </Card>
insert_point = None
depth = 0
for i in range(expanded_start, len(lines)):
    line = lines[i]
    for ch in line:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
    if depth <= 0 and i > expanded_start + 2:
        # This is the closing )} of the expandedAlt block
        insert_point = i
        break

if insert_point is None:
    # Fallback: find </Card> after expanded_start
    for i in range(expanded_start, len(lines)):
        if "</Card>" in lines[i]:
            insert_point = i - 1
            break

if insert_point is None:
    print("ERROR: Could not find insertion point")
    exit(1)

print("Will insert supply chain block before line:", insert_point + 1)

# Step 3: Remove the supply chain block from its current position
new_lines = []
skip = False
for i, line in enumerate(lines):
    if i == sc_start:
        skip = True
    if skip:
        if i > sc_end:
            skip = False
            new_lines.append(line)
    else:
        new_lines.append(line)

print("Removed {} lines from position {}".format(sc_end - sc_start + 1, sc_start + 1))

# Adjust insert_point since we removed lines
offset = sc_end - sc_start + 1
if insert_point > sc_end:
    insert_point -= offset

# Step 4: Insert the supply chain block at the correct position
final_lines = new_lines[:insert_point] + sc_block + new_lines[insert_point:]

# Step 5: Write back
with open(path, "w", encoding="utf-8") as f:
    f.writelines(final_lines)

print("DONE — Supply chain block moved to inside expanded card")
print("New file has {} lines (was {})".format(len(final_lines), len(lines)))
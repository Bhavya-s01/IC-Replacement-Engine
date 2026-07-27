"""
fix_supply_chain.py — Moves supply chain code into the expanded alt block.
Run: python fix_supply_chain.py
"""

import os

path = os.path.join("..", "ic-finder-ui", "src", "App.tsx")
if not os.path.exists(path):
    path = os.path.join("ic-finder-ui", "src", "App.tsx")
if not os.path.exists(path):
    print("ERROR: App.tsx not found")
    exit(1)

with open(path, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()
    lines = content.split("\n")

print("Total lines:", len(lines))

# Step 1: Find ALL supply chain blocks and remove them
# Look for "{/* Supply Chain Data */}" markers
sc_blocks = []
i = 0
while i < len(lines):
    if "Supply Chain Data" in lines[i] and ("/*" in lines[i] or "button" in lines[i].lower() or "showSupplyChain" in lines[i]):
        # Found start of a supply chain block
        start = i
        # Find the containing div - go back to find the opening <div
        while start > 0 and "<div" not in lines[start]:
            start -= 1
        # If we went back too far, just use the comment line
        if i - start > 3:
            start = i

        # Find end by counting braces
        depth = 0
        end = start
        started = False
        for j in range(start, min(start + 80, len(lines))):
            for ch in lines[j]:
                if ch == "{":
                    depth += 1
                    started = True
                elif ch == "}":
                    depth -= 1
            if started and depth <= 0:
                end = j
                break

        # Only remove if it looks like a substantial block
        if end > start + 2:
            sc_blocks.append((start, end))
            print("Found supply chain block: lines {}-{}".format(start + 1, end + 1))
            i = end + 1
        else:
            i += 1
    else:
        i += 1

if not sc_blocks:
    print("No supply chain blocks found to move")
    exit(0)

# Save the first block's content (we'll re-insert it)
first_block = sc_blocks[0]
sc_code = "\n".join(lines[first_block[0]:first_block[1] + 1])

# Step 2: Remove all supply chain blocks from the file
# Work backwards to preserve line numbers
for start, end in reversed(sc_blocks):
    del lines[start:end + 1]
    print("Removed block at lines {}-{}".format(start + 1, end + 1))

# Step 3: Find the expanded alt section and insert supply chain code there
# Look for: expandedAlt === idx && Object.keys(alt.spec_scores)
insert_line = None
for i, line in enumerate(lines):
    if "expandedAlt === idx" in line and "spec_scores" in line:
        # Find the closing of this expanded block
        depth = 0
        for j in range(i, min(i + 200, len(lines))):
            for ch in lines[j]:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
            if depth <= 0 and j > i + 5:
                insert_line = j
                break
        break

if insert_line is None:
    # Fallback: find </Card> after the expanded section
    for i, line in enumerate(lines):
        if "expandedAlt === idx" in line:
            for j in range(i, min(i + 200, len(lines))):
                if "</Card>" in lines[j]:
                    insert_line = j - 1
                    break
            break

if insert_line is None:
    print("ERROR: Could not find insertion point")
    exit(1)

print("Inserting supply chain code at line", insert_line + 1)

# Build the supply chain code to insert
supply_chain_jsx = '''
                    {/* Supply Chain Data */}
                    <div className="px-4 pb-4">
                      <button
                        onClick={(e) => { e.stopPropagation(); loadSupplyChain(alt.mpn, idx) }}
                        className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md border transition-colors hover:bg-slate-50"
                        style={{ borderColor: T.border, color: T.primary }}>
                        <Layers className="w-3.5 h-3.5" />
                        {showSupplyChain === idx ? 'Hide' : 'View'} Supply Chain Data
                      </button>

                      {showSupplyChain === idx && supplyChainData[alt.mpn] && (
                        <div className="mt-3">
                          {!supplyChainData[alt.mpn].available ? (
                            <p className="text-xs text-slate-400 italic">No supply chain data available for this part.</p>
                          ) : (
                            <div className="border rounded-lg p-4" style={{ borderColor: T.border, backgroundColor: T.bgAlt }}>
                              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-3">
                                Supply Chain Data
                              </p>
                              <div className="grid grid-cols-3 gap-3">
                                {supplyChainData[alt.mpn].entries.map((entry: any, i: number) => (
                                  <React.Fragment key={i}>
                                    <div className="p-3 rounded-lg bg-white border" style={{ borderColor: T.border }}>
                                      <p className="text-[10px] text-slate-400 uppercase font-medium">Sourcing</p>
                                      <p className="text-sm font-semibold mt-1" style={{
                                        color: (entry.sourcing || '').toLowerCase().includes('multi') ? T.success
                                             : (entry.sourcing || '').toLowerCase() === 'sole' ? T.danger
                                             : T.warning
                                      }}>{entry.sourcing || 'Unknown'}</p>
                                    </div>
                                    {entry.lead_time_days && (
                                      <div className="p-3 rounded-lg bg-white border" style={{ borderColor: T.border }}>
                                        <p className="text-[10px] text-slate-400 uppercase font-medium">Lead Time</p>
                                        <p className="text-sm font-semibold mt-1">{entry.lead_time_days} days</p>
                                      </div>
                                    )}
                                    {entry.moq && (
                                      <div className="p-3 rounded-lg bg-white border" style={{ borderColor: T.border }}>
                                        <p className="text-[10px] text-slate-400 uppercase font-medium">MOQ</p>
                                        <p className="text-sm font-semibold mt-1">{Number(entry.moq).toLocaleString()}</p>
                                      </div>
                                    )}
                                    {entry.pin_count && (
                                      <div className="p-3 rounded-lg bg-white border" style={{ borderColor: T.border }}>
                                        <p className="text-[10px] text-slate-400 uppercase font-medium">Pin Count</p>
                                        <p className="text-sm font-semibold mt-1">{entry.pin_count} pins</p>
                                      </div>
                                    )}
                                    <div className="p-3 rounded-lg bg-white border" style={{ borderColor: T.border }}>
                                      <p className="text-[10px] text-slate-400 uppercase font-medium">Dual Fab</p>
                                      <p className="text-sm font-semibold mt-1" style={{
                                        color: entry.dual_fab_plan === 'Y' ? T.success : T.warning
                                      }}>{entry.dual_fab_plan === 'Y' ? 'Yes' : 'No'}</p>
                                    </div>
                                    {entry.fab1 && (
                                      <div className="p-3 rounded-lg bg-white border" style={{ borderColor: T.border }}>
                                        <p className="text-[10px] text-slate-400 uppercase font-medium">Primary Fab</p>
                                        <p className="text-xs font-medium mt-1">{entry.fab1.supplier}</p>
                                        <p className="text-[10px] text-slate-500">{entry.fab1.country}</p>
                                      </div>
                                    )}
                                    {entry.p2p_solution && (
                                      <div className="p-3 rounded-lg border col-span-3"
                                           style={{ borderColor: '#BBF7D0', backgroundColor: T.successBg }}>
                                        <p className="text-[10px] uppercase font-medium" style={{ color: T.success }}>
                                          P2P Solution Available
                                        </p>
                                        <p className="text-xs font-medium mt-1" style={{ color: T.success }}>
                                          {entry.p2p_solution.supplier}: {entry.p2p_solution.mpn}
                                        </p>
                                      </div>
                                    )}
                                    <div className="col-span-3 flex justify-between text-[10px] text-slate-400 italic mt-1">
                                      <span>ODM: {entry.odm}</span>
                                      <span>* Based on template data dated {entry.template_date}</span>
                                    </div>
                                  </React.Fragment>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>'''

# Insert before the closing of the expanded block
lines.insert(insert_line, supply_chain_jsx)

# Step 4: Write back
new_content = "\n".join(lines)
with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("DONE - Supply chain code moved inside expanded card block")
print("New file has {} lines".format(len(lines)))
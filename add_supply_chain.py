"""
add_supply_chain.py — Inserts the Supply Chain button + panel
directly inside the expanded alternative card in App.tsx.

Run: python add_supply_chain.py
"""

import os

# Find App.tsx
for path in ["../ic-finder-ui/src/App.tsx", "ic-finder-ui/src/App.tsx"]:
    if os.path.exists(path):
        break
else:
    print("ERROR: App.tsx not found")
    exit(1)

print("Reading:", path)

with open(path, "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

print("Total lines:", len(lines))

# Check if supply chain code already exists inside expanded block
# Find expandedAlt === idx line
expanded_line = None
for i, line in enumerate(lines):
    if "expandedAlt === idx" in line and "spec_scores" in line:
        expanded_line = i
        break

if expanded_line is None:
    print("ERROR: Could not find expandedAlt === idx block")
    exit(1)

print("Found expanded block at line:", expanded_line + 1)

# Check if supply chain is already inside expanded block
has_sc_after = False
for i in range(expanded_line, min(expanded_line + 200, len(lines))):
    if "Supply Chain" in lines[i]:
        has_sc_after = True
        print("Supply chain code already inside expanded block at line", i + 1)
        break

if has_sc_after:
    print("Nothing to do — supply chain code is already in the right place")
    exit(0)

# Find the closing of the expanded block
# Look for the pattern: </div> followed by )} that closes expandedAlt
depth = 0
insert_line = None
for i in range(expanded_line, min(expanded_line + 300, len(lines))):
    for ch in lines[i]:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
    if depth <= 0 and i > expanded_line + 5:
        insert_line = i
        break

if insert_line is None:
    # Fallback: find </Card> after expanded block
    for i in range(expanded_line, min(expanded_line + 300, len(lines))):
        if "</Card>" in lines[i]:
            insert_line = i - 1
            break

if insert_line is None:
    print("ERROR: Could not find insertion point")
    exit(1)

print("Will insert supply chain code before line:", insert_line + 1)

# The supply chain JSX to insert
sc_code = '''
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
                    </div>
'''

# Insert the supply chain code
lines.insert(insert_line, sc_code + "\n")

# Now check if state variables and loader function exist
content = "".join(lines)

# Add state variables if missing
if "supplyChainData" not in content:
    # Find where other useState declarations are
    for i, line in enumerate(lines):
        if "useState<number | null>(null)" in line and "expandedAlt" in line:
            lines.insert(i + 1, "  const [supplyChainData, setSupplyChainData] = useState<Record<string, any>>({})\n")
            lines.insert(i + 2, "  const [showSupplyChain, setShowSupplyChain] = useState<number | null>(null)\n")
            print("Added supplyChainData and showSupplyChain state variables")
            break

# Add loader function if missing
content = "".join(lines)
if "loadSupplyChain" not in content:
    # Find a good insertion point - after other handler functions
    for i, line in enumerate(lines):
        if "const loadBrowse" in line or "const runCompare" in line or "const selectPart" in line:
            # Find the end of this function
            depth = 0
            for j in range(i, min(i + 30, len(lines))):
                for ch in lines[j]:
                    if ch == "{": depth += 1
                    elif ch == "}": depth -= 1
                if depth <= 0 and j > i + 2:
                    loader = '''
  const loadSupplyChain = async (mpn: string, idx: number) => {
    if (supplyChainData[mpn]) {
      setShowSupplyChain(showSupplyChain === idx ? null : idx)
      return
    }
    try {
      const r = await api.supplyChain(mpn)
      setSupplyChainData((prev: any) => ({ ...prev, [mpn]: r.data }))
      setShowSupplyChain(idx)
    } catch (e) { console.error(e) }
  }

'''
                    lines.insert(j + 1, loader)
                    print("Added loadSupplyChain function")
                    break
            break

# Check React import
content = "".join(lines)
if "import React" not in content and "React.Fragment" in content:
    for i, line in enumerate(lines):
        if "import {" in line and "useState" in line:
            lines[i] = line.replace("import {", "import React, {")
            print("Added React to import")
            break

# Write back
with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("DONE — Supply chain code inserted inside expanded card block")
print("New file has {} lines".format(len(lines)))
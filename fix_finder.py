"""fix_finder.py - Fixes the is_drop_in syntax error in finder.py"""

with open("finder.py", "r", encoding="utf-8") as f:
    code = f.read()

# Find and replace the broken block
old_block = '''        result.is_drop_in = (
            # ── PIN COUNT CHECK ──
            target_pins = self._pin_count_from_package(target.package)
            cand_pins = self._pin_count_from_package(result.package)
            pin_count_match = False
            if target_pins and cand_pins:
                pin_count_match = (target_pins == cand_pins)
                pin_weight = 8.0
                pin_score = pin_weight if pin_count_match else 0
                total_score += pin_score
                max_score += pin_weight
                result.spec_scores["Pin Count"] = {
                    "target": str(target_pins), "candidate": str(cand_pins),
                    "score": pin_score, "max": pin_weight,'''

if old_block in code:
    # Find the entire broken block up to the next method or return
    start = code.find('        result.is_drop_in = (\n            # ── PIN COUNT CHECK ──')
    if start < 0:
        start = code.find('        result.is_drop_in = (\n            #')
    
    if start >= 0:
        # Find where the broken block ends - look for "return result"
        end = code.find('        return result', start)
        if end < 0:
            end = code.find('    def _get_spec', start)
        
        if end > start:
            broken = code[start:end]
            
            fixed = '''        # ── PIN COUNT CHECK ──
        target_pins = self._pin_count_from_package(target.package)
        cand_pins = self._pin_count_from_package(result.package)
        pin_count_match = False
        if target_pins and cand_pins:
            pin_count_match = (target_pins == cand_pins)
            pin_weight = 8.0
            pin_score = pin_weight if pin_count_match else 0
            total_score += pin_score
            max_score += pin_weight
            result.spec_scores["Pin Count"] = {
                "target": str(target_pins), "candidate": str(cand_pins),
                "score": pin_score, "max": pin_weight,
                "status": "MATCH" if pin_count_match else "FAIL",
                "required": True,
            }

        # ── PACKAGE MATCH ──
        pkg_exact = (target.package or "").lower() == (result.package or "").lower()

        # ── MOUNTING MATCH ──
        mount_exact = True
        if target.mounting_type and result.mounting_type:
            mount_exact = target.mounting_type.lower() == result.mounting_type.lower()

        # ── ALL REQUIRED SPECS PASS ──
        all_req_pass = all(
            v["status"] != "FAIL"
            for v in result.spec_scores.values()
            if v.get("required")
        )

        # ── FINAL SCORES ──
        result.total_score = total_score
        result.max_possible_score = max_score
        result.compatibility_pct = (total_score / max_score * 100) if max_score > 0 else 0

        # ── DROP-IN = ALL conditions must pass ──
        result.is_drop_in = (
            all_req_pass
            and pkg_exact
            and mount_exact
            and pin_count_match
        )

'''
            code = code[:start] + fixed + code[end:]
            print("[OK] Fixed the is_drop_in block")
        else:
            print("[!] Could not find end of broken block")
    else:
        print("[!] Could not find start of broken block")
else:
    # Try a simpler fix - just find the malformed is_drop_in line
    print("[INFO] Exact block not found, trying line-by-line fix...")
    
    lines = code.split("\n")
    fixed_lines = []
    skip_until_return = False
    inserted_fix = False
    
    for i, line in enumerate(lines):
        # Detect the start of the broken block
        if "result.is_drop_in = (" in line and not inserted_fix:
            # Check if next lines have assignment statements (= sign) inside the expression
            if i + 1 < len(lines) and ("target_pins = " in lines[i+1] or "PIN COUNT" in lines[i+1]):
                # This is the broken block - skip it and insert the fix
                skip_until_return = True
                inserted_fix = True
                
                fixed_lines.append("        # ── PIN COUNT CHECK ──")
                fixed_lines.append("        target_pins = self._pin_count_from_package(target.package)")
                fixed_lines.append("        cand_pins = self._pin_count_from_package(result.package)")
                fixed_lines.append("        pin_count_match = False")
                fixed_lines.append("        if target_pins and cand_pins:")
                fixed_lines.append("            pin_count_match = (target_pins == cand_pins)")
                fixed_lines.append("            pin_weight = 8.0")
                fixed_lines.append("            pin_score = pin_weight if pin_count_match else 0")
                fixed_lines.append("            total_score += pin_score")
                fixed_lines.append("            max_score += pin_weight")
                fixed_lines.append('            result.spec_scores["Pin Count"] = {')
                fixed_lines.append('                "target": str(target_pins), "candidate": str(cand_pins),')
                fixed_lines.append('                "score": pin_score, "max": pin_weight,')
                fixed_lines.append('                "status": "MATCH" if pin_count_match else "FAIL",')
                fixed_lines.append('                "required": True,')
                fixed_lines.append("            }")
                fixed_lines.append("")
                fixed_lines.append("        # ── PACKAGE MATCH ──")
                fixed_lines.append('        pkg_exact = (target.package or "").lower() == (result.package or "").lower()')
                fixed_lines.append("")
                fixed_lines.append("        # ── MOUNTING MATCH ──")
                fixed_lines.append("        mount_exact = True")
                fixed_lines.append("        if target.mounting_type and result.mounting_type:")
                fixed_lines.append("            mount_exact = target.mounting_type.lower() == result.mounting_type.lower()")
                fixed_lines.append("")
                fixed_lines.append("        # ── ALL REQUIRED SPECS PASS ──")
                fixed_lines.append("        all_req_pass = all(")
                fixed_lines.append('            v["status"] != "FAIL"')
                fixed_lines.append("            for v in result.spec_scores.values()")
                fixed_lines.append('            if v.get("required")')
                fixed_lines.append("        )")
                fixed_lines.append("")
                fixed_lines.append("        # ── FINAL SCORES ──")
                fixed_lines.append("        result.total_score = total_score")
                fixed_lines.append("        result.max_possible_score = max_score")
                fixed_lines.append("        result.compatibility_pct = (total_score / max_score * 100) if max_score > 0 else 0")
                fixed_lines.append("")
                fixed_lines.append("        # ── DROP-IN = ALL conditions must pass ──")
                fixed_lines.append("        result.is_drop_in = (")
                fixed_lines.append("            all_req_pass")
                fixed_lines.append("            and pkg_exact")
                fixed_lines.append("            and mount_exact")
                fixed_lines.append("            and pin_count_match")
                fixed_lines.append("        )")
                fixed_lines.append("")
                continue
            else:
                fixed_lines.append(line)
                continue
        
        if skip_until_return:
            if line.strip().startswith("return result"):
                skip_until_return = False
                fixed_lines.append(line)
            # Skip all lines in the broken block
            continue
        
        fixed_lines.append(line)
    
    if inserted_fix:
        code = "\n".join(fixed_lines)
        print("[OK] Fixed via line-by-line replacement")
    else:
        print("[SKIP] No broken is_drop_in block found")

with open("finder.py", "w", encoding="utf-8") as f:
    f.write(code)

# Syntax check
print("\n=== Syntax Check ===")
import py_compile
try:
    py_compile.compile("finder.py", doraise=True)
    print("[OK] No syntax errors!")
except py_compile.PyCompileError as e:
    print(f"[ERROR] {e}")
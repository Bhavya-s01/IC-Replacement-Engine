"""
app.py - Streamlit UI for IC Alternative Finder
Run: python -m streamlit run app.py
"""

import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from finder import AlternativeFinder
from config import CATEGORIES, DB_PATH

st.set_page_config(page_title="IC Alternative Finder", page_icon="🔌", layout="wide")

@st.cache_resource
def get_finder():
    return AlternativeFinder()

finder = get_finder()

# Sidebar navigation
st.sidebar.title("🔌 IC Finder")
page = st.sidebar.radio("Navigate", [
    "🔍 Search",
    "🔄 Find Alternatives",
    "⚖️ Compare Parts",
    "📊 Dashboard",
    "📋 Browse Category",
])

# ── SEARCH PAGE ──
if page == "🔍 Search":
    st.title("Search Components")
    query = st.text_input("Enter part number or keyword", placeholder="e.g. MIC5501 or LDO 3.3V")

    if query:
        results = finder.search(query, limit=50)
        if results:
            st.success("Found {} parts".format(len(results)))
            for r in results:
                with st.expander("{} — {} ({})".format(r.mpn, r.manufacturer, r.category)):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Stock", r.stock)
                    col2.metric("Price", "${:.4f}".format(r.unit_price))
                    col3.metric("Status", r.lifecycle_status)
                    st.text("Package: {} | Mount: {}".format(r.package, r.mounting_type))
                    if r.specs:
                        st.dataframe(pd.DataFrame(
                            list(r.specs.items()), columns=["Spec", "Value"]
                        ))
        else:
            st.warning("No parts found.")

# ── FIND ALTERNATIVES PAGE ──
elif page == "🔄 Find Alternatives":
    st.title("Find Alternatives")
    mpn = st.text_input("Enter target part number", placeholder="e.g. MIC5501-3.0YM5-TR")
    top_n = st.slider("Number of results", 5, 50, 10)
    min_compat = st.slider("Minimum compatibility %", 0, 100, 30)

    if mpn and st.button("Find Alternatives"):
        target = finder.lookup(mpn)
        if not target:
            st.error("Part not found: {}".format(mpn))
        else:
            st.info("Target: {} | {} | {}".format(target.mpn, target.manufacturer, target.category))
            alternatives = finder.find_alternatives(
                target, top_n=top_n, min_compatibility_pct=min_compat
            )
            if alternatives:
                for i, alt in enumerate(alternatives):
                    icon = "🟢" if alt.is_drop_in else ("🟡" if alt.compatibility_pct > 70 else "🔴")
                    with st.expander("{} #{} — {} ({:.1f}% compatible)".format(
                            icon, i + 1, alt.mpn, alt.compatibility_pct)):
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Compatibility", "{:.1f}%".format(alt.compatibility_pct))
                        col2.metric("Stock", alt.stock)
                        col3.metric("Price", "${:.4f}".format(alt.unit_price))
                        col4.metric("Status", alt.lifecycle_status)

                        if alt.spec_scores:
                            spec_data = []
                            for name, d in sorted(alt.spec_scores.items()):
                                spec_data.append({
                                    "Spec": ("* " if d.get("required") else "") + name,
                                    "Target": str(d["target"]),
                                    "Candidate": str(d["candidate"]),
                                    "Status": d["status"],
                                    "Score": "{:.0f}/{:.0f}".format(d["score"], d["max"]),
                                })
                            st.dataframe(pd.DataFrame(spec_data), use_container_width=True)
            else:
                st.warning("No alternatives found.")

# ── COMPARE PAGE ──
elif page == "⚖️ Compare Parts":
    st.title("Compare Parts Side-by-Side")
    col1, col2 = st.columns(2)
    mpn1 = col1.text_input("Part 1", placeholder="e.g. MIC5501-3.0YM5-TR")
    mpn2 = col2.text_input("Part 2", placeholder="e.g. AP2112K-3.3TRG1")

    if mpn1 and mpn2 and st.button("Compare"):
        a = finder.lookup(mpn1)
        b = finder.lookup(mpn2)
        if not a:
            st.error("Not found: {}".format(mpn1))
        elif not b:
            st.error("Not found: {}".format(mpn2))
        else:
            compare_data = []
            for field in ["manufacturer", "description", "category", "package",
                          "mounting_type", "lifecycle_status"]:
                va = getattr(a, field, "")
                vb = getattr(b, field, "")
                compare_data.append({
                    "Field": field, mpn1: va, mpn2: vb,
                    "Match": "✅" if str(va).lower() == str(vb).lower() else "❌"
                })
            compare_data.append({"Field": "stock", mpn1: a.stock, mpn2: b.stock, "Match": ""})
            compare_data.append({"Field": "price", mpn1: a.unit_price, mpn2: b.unit_price, "Match": ""})
            st.dataframe(pd.DataFrame(compare_data), use_container_width=True)

            all_specs = sorted(set(list(a.specs.keys()) + list(b.specs.keys())))
            spec_data = []
            for s in all_specs:
                va = a.specs.get(s, "-")
                vb = b.specs.get(s, "-")
                spec_data.append({
                    "Spec": s, mpn1: va, mpn2: vb,
                    "Match": "✅" if va == vb else "❌"
                })
            st.dataframe(pd.DataFrame(spec_data), use_container_width=True)

# ── DASHBOARD ──
elif page == "📊 Dashboard":
    st.title("Database Dashboard")
    stats = finder.stats()
    total = finder.total_parts()
    st.metric("Total Components", "{:,}".format(total))

    cat_data = []
    for slug, count in sorted(stats.items()):
        name = CATEGORIES[slug].name if slug in CATEGORIES else slug
        cat_data.append({"Category": name, "Count": count})
    df = pd.DataFrame(cat_data)

    st.bar_chart(df.set_index("Category"))
    st.dataframe(df, use_container_width=True)

# ── BROWSE CATEGORY ──
elif page == "📋 Browse Category":
    st.title("Browse by Category")
    import sqlite3
    cat_names = {CATEGORIES[k].name: k for k in sorted(CATEGORIES.keys())}
    selected = st.selectbox("Select Category", list(cat_names.keys()))

    if selected:
        slug = cat_names[selected]
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT manufacturer_part_number as MPN, manufacturer as Manufacturer, "
            "description as Description, stock as Stock, unit_price as Price, "
            "package as Package, lifecycle_status as Status "
            "FROM components WHERE category=? ORDER BY stock DESC LIMIT 500",
            conn, params=(slug,)
        )
        conn.close()
        st.info("{} parts in {}".format(len(df), selected))
        st.dataframe(df, use_container_width=True)
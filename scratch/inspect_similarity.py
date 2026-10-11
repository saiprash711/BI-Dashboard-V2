import os
import re
import difflib
import pandas as pd

p = r"C:\Users\TC100\Downloads\Conversion_Data_Jan_Aug2026_Analytics_GST Calculations_normalised.xlsx"
df = pd.read_excel(p, sheet_name=0)

def find_similar_pairs(series, min_ratio=0.84):
    vals = sorted(series.dropna().astype(str).unique())
    pairs = []
    for i, v1 in enumerate(vals):
        for v2 in vals[i+1:]:
            c1 = re.sub(r"[^A-Z0-9]", "", v1.upper())
            c2 = re.sub(r"[^A-Z0-9]", "", v2.upper())
            if c1 == c2:
                pairs.append((v1, v2, 1.0, "exact_clean"))
                continue
            r = difflib.SequenceMatcher(None, c1, c2).ratio()
            if r >= min_ratio:
                pairs.append((v1, v2, r, "fuzzy"))
    return pairs

print("=== SELLER SIMILAR PAIRS ===")
s_pairs = find_similar_pairs(df["Seller Name"], 0.84)
print(f"Total seller pairs: {len(s_pairs)}")
for v1, v2, r, t in s_pairs:
    c1 = int((df["Seller Name"] == v1).sum())
    c2 = int((df["Seller Name"] == v2).sum())
    print(f"  [{t}:{r:.2f}] \"{v1}\" ({c1}) <-> \"{v2}\" ({c2})")

print("\n=== BUYER SIMILAR PAIRS ===")
b_pairs = find_similar_pairs(df["Buyer Name"], 0.86)
print(f"Total buyer pairs: {len(b_pairs)}")
for v1, v2, r, t in b_pairs:
    c1 = int((df["Buyer Name"] == v1).sum())
    c2 = int((df["Buyer Name"] == v2).sum())
    print(f"  [{t}:{r:.2f}] \"{v1}\" ({c1}) <-> \"{v2}\" ({c2})")

print("\n=== MODEL SIMILAR PAIRS ===")
m_pairs = find_similar_pairs(df["Model"], 0.80)
print(f"Total model pairs: {len(m_pairs)}")
for v1, v2, r, t in m_pairs:
    c1 = int((df["Model"] == v1).sum())
    c2 = int((df["Model"] == v2).sum())
    print(f"  [{t}:{r:.2f}] \"{v1}\" ({c1}) <-> \"{v2}\" ({c2})")

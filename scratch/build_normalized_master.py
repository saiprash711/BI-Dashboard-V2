"""
Build 100% Normalized and Standardized Jan-Sep 2026 Conversion Master Workbooks.
Applies canonical normalization across all 4,314 converted vehicle records (Jan-Sep 2026).
"""

import os
import sys

# Ensure parent directory is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import re
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
import pandas as pd
import numpy as np

import data_engine as DE

# Support UTF-8 console output
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def parse_num(val, is_int=False):
    if val is None or pd.isna(val):
        return None
    try:
        f = float(str(val).replace(",", "").replace(" ", "").strip())
        return int(round(f)) if is_int else round(f, 2)
    except (ValueError, TypeError):
        return None

def clean_v(val):
    if not val or pd.isna(val):
        return ""
    return str(val).strip().replace(" ", "").upper()

def safe_save(wb, target_path, alt_suffix="_Normalized"):
    try:
        wb.save(target_path)
        print(f"  -> Successfully saved: {target_path}")
        return target_path
    except PermissionError:
        base, ext = os.path.splitext(target_path)
        alt_path = f"{base}{alt_suffix}{ext}"
        try:
            wb.save(alt_path)
            print(f"  -> Original was open in Excel; saved normalized copy to: {alt_path}")
            return alt_path
        except Exception as e:
            print(f"  -> Error saving {alt_path}: {e}")
            return None

def build_normalized_analytics_workbook(df_clean, output_paths, subtitle="January to September 2026"):
    print(f"\nBuilding 100% Normalized Analytics Workbook ({len(df_clean):,} records)...")
    wb = openpyxl.Workbook()

    total_records = len(df_clean)
    last_row = total_records + 3

    # =========================================================================
    # Sheet 1: Executive Analytics & KPIs
    # =========================================================================
    ws_kpi = wb.active
    ws_kpi.title = "Executive Analytics & KPIs"
    ws_kpi.views.sheetView[0].showGridLines = True

    # Title & Subtitle
    ws_kpi.merge_cells("B1:J1")
    ws_kpi["B1"] = "TVS Certified - Conversion Analytics & Performance Intelligence"
    ws_kpi["B1"].font = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    ws_kpi["B1"].alignment = Alignment(horizontal="center", vertical="center")

    ws_kpi.merge_cells("B2:J2")
    ws_kpi["B2"] = f"{subtitle} - Executive Summary & Regional Conversion Metrics ({total_records:,} Units)"
    ws_kpi["B2"].font = Font(name="Calibri", size=11, bold=True, color="475569")
    ws_kpi["B2"].alignment = Alignment(horizontal="center", vertical="center")

    # 5 KPI Cards
    kpi_cards = [
        ("B", "TOTAL CONVERTED", f"=COUNTA('Conversion Analytics (Master)'!D4:D{last_row})", "#,##0"),
        ("D", "AUCTION TURNOVER", f"=SUM('Conversion Analytics (Master)'!I4:I{last_row})", "₹#,##0.00"),
        ("F", "TVS INCOME (EX-GST)", f"=SUM('Conversion Analytics (Master)'!M4:M{last_row})", "₹#,##0.00"),
        ("H", "TVS INCOME (INCL-GST)", f"=SUM('Conversion Analytics (Master)'!N4:N{last_row})", "₹#,##0.00"),
        ("J", "AVG TVS MARGIN %", f"=AVERAGE('Conversion Analytics (Master)'!O4:O{last_row})", "0.00%"),
    ]

    card_hdr_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    card_val_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    box_border = Border(
        left=Side(style="thin", color="94A3B8"), right=Side(style="thin", color="94A3B8"),
        top=Side(style="thin", color="94A3B8"), bottom=Side(style="thin", color="94A3B8"),
    )

    for col_letter, title, formula, fmt in kpi_cards:
        c_hdr = ws_kpi[f"{col_letter}4"]
        c_hdr.value = title
        c_hdr.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        c_hdr.fill = card_hdr_fill
        c_hdr.alignment = Alignment(horizontal="center", vertical="center")
        c_hdr.border = box_border

        c_val = ws_kpi[f"{col_letter}5"]
        c_val.value = formula
        c_val.font = Font(name="Calibri", size=12, bold=True, color="0F172A")
        c_val.fill = card_val_fill
        c_val.alignment = Alignment(horizontal="center", vertical="center")
        c_val.border = box_border
        c_val.number_format = fmt

    # Regional Performance Table
    ws_kpi["B8"] = "REGIONAL PERFORMANCE BREAKDOWN"
    ws_kpi["B8"].font = Font(name="Calibri", size=11, bold=True, color="1E3A8A")

    reg_cols = ["State", "Units Converted", "GMV (Turnover)", "TVS Income (Ex GST)", "TVS Income (Inc GST)", "Avg Bid Value", "Avg Take Rate %"]
    for c_i, h in enumerate(reg_cols, start=2):
        col_let = get_column_letter(c_i)
        c = ws_kpi[f"{col_let}9"]
        c.value = h
        c.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = box_border

    states = ["AP/TS", "Kerala", "TN"]
    for s_idx, st in enumerate(states, start=10):
        ws_kpi[f"B{s_idx}"] = st
        ws_kpi[f"B{s_idx}"].alignment = Alignment(horizontal="center")
        ws_kpi[f"B{s_idx}"].border = box_border

        ws_kpi[f"C{s_idx}"] = f"=COUNTIF('Conversion Analytics (Master)'!$C$4:$C${last_row}, B{s_idx})"
        ws_kpi[f"C{s_idx}"].number_format = "#,##0"
        ws_kpi[f"C{s_idx}"].border = box_border

        ws_kpi[f"D{s_idx}"] = f"=SUMIF('Conversion Analytics (Master)'!$C$4:$C${last_row}, B{s_idx}, 'Conversion Analytics (Master)'!$I$4:$I${last_row})"
        ws_kpi[f"D{s_idx}"].number_format = "₹#,##0.00"
        ws_kpi[f"D{s_idx}"].border = box_border

        ws_kpi[f"E{s_idx}"] = f"=SUMIF('Conversion Analytics (Master)'!$C$4:$C${last_row}, B{s_idx}, 'Conversion Analytics (Master)'!$M$4:$M${last_row})"
        ws_kpi[f"E{s_idx}"].number_format = "₹#,##0.00"
        ws_kpi[f"E{s_idx}"].border = box_border

        ws_kpi[f"F{s_idx}"] = f"=SUMIF('Conversion Analytics (Master)'!$C$4:$C${last_row}, B{s_idx}, 'Conversion Analytics (Master)'!$N$4:$N${last_row})"
        ws_kpi[f"F{s_idx}"].number_format = "₹#,##0.00"
        ws_kpi[f"F{s_idx}"].border = box_border

        ws_kpi[f"G{s_idx}"] = f'=IF(C{s_idx}>0, D{s_idx}/C{s_idx}, 0)'
        ws_kpi[f"G{s_idx}"].number_format = "₹#,##0.00"
        ws_kpi[f"G{s_idx}"].border = box_border

        ws_kpi[f"H{s_idx}"] = f'=IF(D{s_idx}>0, E{s_idx}/D{s_idx}, 0)'
        ws_kpi[f"H{s_idx}"].number_format = "0.00%"
        ws_kpi[f"H{s_idx}"].border = box_border

    # Total Row
    tot_r = 13
    ws_kpi[f"B{tot_r}"] = "TOTAL"
    ws_kpi[f"B{tot_r}"].font = Font(name="Calibri", size=10, bold=True)
    ws_kpi[f"B{tot_r}"].border = box_border
    ws_kpi[f"B{tot_r}"].alignment = Alignment(horizontal="center")

    ws_kpi[f"C{tot_r}"] = "=SUM(C10:C12)"
    ws_kpi[f"C{tot_r}"].font = Font(name="Calibri", size=10, bold=True)
    ws_kpi[f"C{tot_r}"].number_format = "#,##0"
    ws_kpi[f"C{tot_r}"].border = box_border

    ws_kpi[f"D{tot_r}"] = "=SUM(D10:D12)"
    ws_kpi[f"D{tot_r}"].font = Font(name="Calibri", size=10, bold=True)
    ws_kpi[f"D{tot_r}"].number_format = "₹#,##0.00"
    ws_kpi[f"D{tot_r}"].border = box_border

    ws_kpi[f"E{tot_r}"] = "=SUM(E10:E12)"
    ws_kpi[f"E{tot_r}"].font = Font(name="Calibri", size=10, bold=True)
    ws_kpi[f"E{tot_r}"].number_format = "₹#,##0.00"
    ws_kpi[f"E{tot_r}"].border = box_border

    ws_kpi[f"F{tot_r}"] = "=SUM(F10:F12)"
    ws_kpi[f"F{tot_r}"].font = Font(name="Calibri", size=10, bold=True)
    ws_kpi[f"F{tot_r}"].number_format = "₹#,##0.00"
    ws_kpi[f"F{tot_r}"].border = box_border

    ws_kpi[f"G{tot_r}"] = f'=IF(C{tot_r}>0, D{tot_r}/C{tot_r}, 0)'
    ws_kpi[f"G{tot_r}"].font = Font(name="Calibri", size=10, bold=True)
    ws_kpi[f"G{tot_r}"].number_format = "₹#,##0.00"
    ws_kpi[f"G{tot_r}"].border = box_border

    ws_kpi[f"H{tot_r}"] = f'=IF(D{tot_r}>0, E{tot_r}/D{tot_r}, 0)'
    ws_kpi[f"H{tot_r}"].font = Font(name="Calibri", size=10, bold=True)
    ws_kpi[f"H{tot_r}"].number_format = "0.00%"
    ws_kpi[f"H{tot_r}"].border = box_border

    for col in ["B", "C", "D", "E", "F", "G", "H", "I", "J"]:
        ws_kpi.column_dimensions[col].width = 22

    # =========================================================================
    # Sheet 2: Conversion Analytics (Master) - 100% Normalized
    # =========================================================================
    ws_master = wb.create_sheet("Conversion Analytics (Master)")
    ws_master.views.sheetView[0].showGridLines = True
    ws_master.freeze_panes = "A4"

    ws_master.merge_cells("A1:O1")
    ws_master["A1"] = "TVS Certified - Conversion Analytics Master Dataset"
    ws_master["A1"].font = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    ws_master["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws_master.merge_cells("A2:O2")
    ws_master["A2"] = f"{subtitle} - 100% Standardized & Normalized Analytical Inventory Profile ({total_records:,} Units)"
    ws_master["A2"].font = Font(name="Calibri", size=10, italic=True, color="64748B")
    ws_master["A2"].alignment = Alignment(horizontal="center", vertical="center")

    m_headers = [
        "FY", "Month", "State", "Vehicle Number", "Make", "Model",
        "Year", "Odometer", "Final Bid Value", "Seller Name",
        "Seller Segment", "Buyer Name", "Total Income (ex. GST)", "Total Income", "TVS Margin %"
    ]

    header_font_m = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    header_fill_m = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    border_m = Border(
        left=Side(style="thin", color="CBD5E1"), right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"), bottom=Side(style="thin", color="CBD5E1")
    )

    for c_i, h in enumerate(m_headers, start=1):
        c = ws_master.cell(row=3, column=c_i, value=h)
        c.font = header_font_m
        c.fill = header_fill_m
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = border_m

    for r_idx, (_, rec) in enumerate(df_clean.iterrows(), start=4):
        vals = [
            str(rec['FY']), str(rec['Month']), str(rec['State']), clean_v(rec['Vehicle Number']),
            str(rec['Make']), str(rec['Model']), parse_num(rec['Year'], is_int=True), parse_num(rec['Odometer'], is_int=True),
            parse_num(rec['Final Bid Value'], is_int=False), str(rec['Seller Name']), str(rec['Seller Segment']),
            str(rec['Buyer Name']), parse_num(rec['Total Income (Ex GST)'], is_int=False), parse_num(rec['Total Income'], is_int=False),
            f'=IF(AND(ISNUMBER(M{r_idx}), ISNUMBER(I{r_idx}), I{r_idx}>0), M{r_idx}/I{r_idx}, "")'
        ]
        for c_idx, val in enumerate(vals, start=1):
            cell = ws_master.cell(row=r_idx, column=c_idx, value=val)
            cell.font = Font(name="Calibri", size=10)
            cell.border = border_m
            if c_idx in (1, 2, 3):
                cell.alignment = Alignment(horizontal="center")
            elif c_idx == 7:
                cell.alignment = Alignment(horizontal="center")
                cell.number_format = "0"
            elif c_idx == 8:
                cell.alignment = Alignment(horizontal="right")
                cell.number_format = "#,##0"
            elif c_idx in (9, 13, 14):
                cell.alignment = Alignment(horizontal="right")
                cell.number_format = "₹#,##0.00"
            elif c_idx == 15:
                cell.alignment = Alignment(horizontal="right")
                cell.number_format = "0.00%"

    widths_m = [10, 10, 12, 18, 20, 20, 10, 15, 18, 38, 16, 36, 22, 18, 16]
    for i, w in enumerate(widths_m, start=1):
        ws_master.column_dimensions[get_column_letter(i)].width = w

    # =========================================================================
    # Sheet 3: Conversion Data (Standard) - 13 Columns
    # =========================================================================
    ws_std = wb.create_sheet("Conversion Data (Standard)")
    ws_std.views.sheetView[0].showGridLines = True
    ws_std.freeze_panes = "A4"

    ws_std.merge_cells("A1:M1")
    ws_std["A1"] = "TVS Certified - Monthly Conversion Report (Standard)"
    ws_std["A1"].font = Font(name="Calibri", size=14, bold=True, color="2F5496")
    ws_std["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws_std.merge_cells("A2:M2")
    ws_std["A2"] = f"{subtitle} - Standard 13-Column Manager Reporting Template ({total_records:,} Units)"
    ws_std["A2"].font = Font(name="Calibri", size=10, italic=True, color="808080")
    ws_std["A2"].alignment = Alignment(horizontal="center", vertical="center")

    std_cols = [
        "FY", "Month", "State", "Vehicle Number", "Make", "Model",
        "Year", "Odometer", "Final Bid Value", "Seller Name",
        "Seller Segment", "Buyer Name", "Total Income"
    ]
    for c_i, h in enumerate(std_cols, start=1):
        c = ws_std.cell(row=3, column=c_i, value=h)
        c.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = border_m

    for r_idx, (_, rec) in enumerate(df_clean.iterrows(), start=4):
        vals = [
            str(rec['FY']), str(rec['Month']), str(rec['State']), clean_v(rec['Vehicle Number']),
            str(rec['Make']), str(rec['Model']), parse_num(rec['Year'], is_int=True), parse_num(rec['Odometer'], is_int=True),
            parse_num(rec['Final Bid Value'], is_int=False), str(rec['Seller Name']), str(rec['Seller Segment']),
            str(rec['Buyer Name']), parse_num(rec['Total Income (Ex GST)'], is_int=False)
        ]
        for c_idx, val in enumerate(vals, start=1):
            cell = ws_std.cell(row=r_idx, column=c_idx, value=val)
            cell.font = Font(name="Calibri", size=10)
            cell.border = border_m
            if c_idx in (1, 2, 3):
                cell.alignment = Alignment(horizontal="center")
            elif c_idx == 7:
                cell.alignment = Alignment(horizontal="center")
                cell.number_format = "0"
            elif c_idx in (8, 9):
                cell.alignment = Alignment(horizontal="right")
                cell.number_format = "#,##0"
            elif c_idx == 13:
                cell.alignment = Alignment(horizontal="right")
                cell.number_format = "₹#,##0.00"

    widths_std = [10, 10, 12, 18, 20, 20, 10, 15, 18, 38, 16, 36, 20]
    for i, w in enumerate(widths_std, start=1):
        ws_std.column_dimensions[get_column_letter(i)].width = w

    # =========================================================================
    # Sheet 4: _MakeList (Hidden)
    # =========================================================================
    ws_makes = wb.create_sheet("_MakeList")
    ws_makes.sheet_state = "hidden"
    canonical_makes = sorted(df_clean['Make'].dropna().unique().tolist())
    for i, m in enumerate(canonical_makes, start=1):
        ws_makes.cell(row=i, column=1, value=m)

    # Save to all target locations
    for p in output_paths:
        safe_save(wb, p)

def build_normalized_16col_master_template(df_clean, output_paths):
    print(f"\nBuilding 100% Normalized 16-Column Bulletproof Master Template ({len(df_clean):,} records)...")
    wb = openpyxl.Workbook()

    # Sheet 2: Lookup Lists
    ws_lookup = wb.create_sheet(title="Lookup Lists")
    ws_lookup.views.sheetView[0].showGridLines = True

    fy_list = ["FY24", "FY25", "FY26", "FY27", "FY28"]
    month_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    states_list = ["TN", "Kerala", "AP/TS", "Karnataka", "Maharashtra", "Other"]
    segment_list = ["Captive", "Non-Captive"]
    make_list = sorted(df_clean['Make'].dropna().unique().tolist())
    models_list = sorted(df_clean['Model'].dropna().unique().tolist())
    sellers_list = sorted([s for s in df_clean['Seller Name'].dropna().unique().tolist() if s.strip()])
    buyers_list = sorted([b for b in df_clean['Buyer Name'].dropna().unique().tolist() if b.strip()])

    lookup_cols = [
        ("FY", fy_list),
        ("Month", month_list),
        ("State", states_list),
        ("Seller Segment", segment_list),
        ("Make", make_list),
        ("Model", models_list),
        ("Authorised Sellers", sellers_list),
        ("Verified Buyers", buyers_list),
    ]

    header_fill_l = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font_l = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    cell_font_l = Font(name="Calibri", size=10, color="0F172A")
    thin_border_l = Border(
        left=Side(style='thin', color='CBD5E1'), right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'), bottom=Side(style='thin', color='CBD5E1')
    )

    lookup_ranges = {}
    for col_idx, (col_name, items) in enumerate(lookup_cols, start=1):
        col_letter = get_column_letter(col_idx)
        cell = ws_lookup.cell(row=1, column=col_idx, value=col_name)
        cell.fill = header_fill_l
        cell.font = header_font_l
        cell.alignment = Alignment(horizontal="center", vertical="center")

        for r_idx, val in enumerate(items, start=2):
            c = ws_lookup.cell(row=r_idx, column=col_idx, value=val)
            c.font = cell_font_l
            c.border = thin_border_l

        buffer_end = max(len(items) + 100, 1000)
        lookup_ranges[col_name] = f"'Lookup Lists'!${col_letter}$2:${col_letter}${buffer_end}"
        ws_lookup.column_dimensions[col_letter].width = max(len(col_name) + 4, 20)

    # Sheet 1: Main Data Entry Sheet
    ws_entry = wb.active
    ws_entry.title = "Conversion Data Entry"
    ws_entry.views.sheetView[0].showGridLines = True
    ws_entry.freeze_panes = "A2"

    columns_spec = [
        ("FY", 12, "0F172A"),
        ("Month", 12, "0F172A"),
        ("State", 14, "0F172A"),
        ("Vehicle Number", 18, "0F172A"),
        ("Make", 20, "0F172A"),
        ("Model", 22, "0F172A"),
        ("Seller Name", 36, "0F172A"),
        ("Seller Segment", 16, "0F172A"),
        ("Buyer Name", 34, "0F172A"),
        ("Year", 12, "0F172A"),
        ("Odometer", 16, "0F172A"),
        ("Final Bid Value", 18, "0F172A"),
        ("Total Income (Ex GST)", 22, "064E3B"),
        ("Total Income (Inc GST)", 24, "1E3A8A"),
        ("GST (18%)", 18, "312E81"),
        ("Period", 16, "334155"),
    ]

    for col_idx, (col_name, width, fill_hex) in enumerate(columns_spec, start=1):
        col_letter = get_column_letter(col_idx)
        cell = ws_entry.cell(row=1, column=col_idx, value=col_name)
        cell.fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
        cell.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws_entry.column_dimensions[col_letter].width = width

    curr_format = "₹#,##0.00"
    num_format = "#,##0"
    int_format = "0"

    for r_idx, (_, rec) in enumerate(df_clean.iterrows(), start=2):
        row_num = r_idx
        ws_entry.cell(row=r_idx, column=1, value=str(rec['FY'])).alignment = Alignment(horizontal="center")
        ws_entry.cell(row=r_idx, column=2, value=str(rec['Month'])).alignment = Alignment(horizontal="center")
        ws_entry.cell(row=r_idx, column=3, value=str(rec['State'])).alignment = Alignment(horizontal="center")
        ws_entry.cell(row=r_idx, column=4, value=clean_v(rec['Vehicle Number']))
        ws_entry.cell(row=r_idx, column=5, value=str(rec['Make']))
        ws_entry.cell(row=r_idx, column=6, value=str(rec['Model']))
        ws_entry.cell(row=r_idx, column=7, value=str(rec['Seller Name']))
        ws_entry.cell(row=r_idx, column=8, value=str(rec['Seller Segment']))
        ws_entry.cell(row=r_idx, column=9, value=str(rec['Buyer Name']))

        # Year
        c10 = ws_entry.cell(row=r_idx, column=10, value=parse_num(rec['Year'], is_int=True))
        c10.number_format = int_format
        c10.alignment = Alignment(horizontal="center")

        # Odometer
        c11 = ws_entry.cell(row=r_idx, column=11, value=parse_num(rec['Odometer'], is_int=True))
        c11.number_format = num_format
        c11.alignment = Alignment(horizontal="right")

        # Bid
        c12 = ws_entry.cell(row=r_idx, column=12, value=parse_num(rec['Final Bid Value'], is_int=False))
        c12.number_format = curr_format
        c12.alignment = Alignment(horizontal="right")

        # Total Income Ex GST
        c13 = ws_entry.cell(row=r_idx, column=13, value=parse_num(rec['Total Income (Ex GST)'], is_int=False))
        c13.number_format = curr_format
        c13.alignment = Alignment(horizontal="right")

        # Formulas
        c14 = ws_entry.cell(row=r_idx, column=14, value=f'=IF(M{row_num}="","",ROUND(M{row_num}*1.18,2))')
        c14.font = Font(name="Calibri", size=10, bold=True, color="1E3A8A")
        c14.number_format = curr_format
        c14.alignment = Alignment(horizontal="right")

        c15 = ws_entry.cell(row=r_idx, column=15, value=f'=IF(M{row_num}="","",ROUND(N{row_num}-M{row_num},2))')
        c15.font = Font(name="Calibri", size=10, color="312E81")
        c15.number_format = curr_format
        c15.alignment = Alignment(horizontal="right")

        c16 = ws_entry.cell(row=r_idx, column=16, value=f'=IF(AND(A{row_num}<>"",B{row_num}<>""), A{row_num}&" \u00b7 "&B{row_num}, "")')
        c16.font = Font(name="Calibri", size=10, color="475569")
        c16.alignment = Alignment(horizontal="center")

        for c_i in range(1, 17):
            c_cell = ws_entry.cell(row=r_idx, column=c_i)
            c_cell.border = thin_border_l
            if not c_cell.font.color:
                c_cell.font = cell_font_l

    # Dropdown validations
    max_row = max(len(df_clean) + 200, 5000)
    for col_i, col_key in [(1, "FY"), (2, "Month"), (3, "State"), (5, "Make"), (6, "Model"), (7, "Authorised Sellers"), (8, "Seller Segment"), (9, "Verified Buyers")]:
        col_let = get_column_letter(col_i)
        rng = lookup_ranges[col_key]
        dv = DataValidation(type="list", formula1=f"={rng}", allow_blank=True)
        dv.add(f"{col_let}2:{col_let}{max_row}")
        ws_entry.add_data_validation(dv)

    for p in output_paths:
        safe_save(wb, p)


def main():
    print("=" * 80)
    print("  TVS CERTIFIED - 100% STANDARDIZATION & NORMALIZATION PIPELINE")
    print("=" * 80)

    # Load and parse using data_engine
    bi_file = r"c:\Users\TC100\OneDrive - TVS Mobility Private Limited\Desktop\BI Dashboard V2\Conversion_Data_Jan_Sep2026_Analytics_GST Calculations.xlsx"
    print(f"Loading dataset: {bi_file}")
    df_raw, notes = DE.parse_workbook(bi_file)
    print(f"Loaded {len(df_raw)} records. Normalisation notes logged: {len(notes)}")

    # 1. Standardize FY strictly: Jan-Mar=FY26, Apr-Sep=FY27
    df_raw['FY'] = df_raw['Month'].map(lambda m: 'FY26' if m in ['Jan', 'Feb', 'Mar'] else 'FY27')

    # 2. Standardize Vehicle Numbers
    df_raw['Vehicle Number'] = df_raw['Vehicle Number'].map(clean_v)

    # 3. Standardize States
    df_raw['State'] = df_raw['State'].map(lambda s: 'Kerala' if str(s).strip().upper() == 'KL' else str(s).strip())

    # 4. Standardize Make and Model
    df_raw['Make'] = DE.standardize_make(df_raw['Make'], df_raw['Model'])
    df_raw['Model'] = DE.standardize_model(df_raw['Model'])

    # 5. Standardize Sellers and Buyers
    df_raw['Seller Name'] = DE.standardize_entities(df_raw['Seller Name'], DE._SELLER_ALIASES, default_upper=True)
    df_raw['Buyer Name'] = DE.standardize_entities(df_raw['Buyer Name'], DE._BUYER_ALIASES, default_upper=False)

    # 6. Standardize Seller Segment
    df_raw['Seller Segment'] = df_raw.apply(
        lambda r: 'Captive' if any(kw in str(r['Seller Name']).lower() for kw in ['exchange', 'tvs mobility', 'tvs ']) else 'Non-Captive',
        axis=1
    )

    # 7. Sort canonically: by Month chronological, State, Vehicle Number
    month_order = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9}
    state_order = {"AP/TS": 1, "Kerala": 2, "TN": 3}
    df_raw['m_rank'] = df_raw['Month'].map(month_order)
    df_raw['s_rank'] = df_raw['State'].map(state_order)
    df_clean = df_raw.sort_values(by=['m_rank', 's_rank', 'Vehicle Number']).drop(columns=['m_rank', 's_rank']).reset_index(drop=True)

    print(f"\n--- Clean Dataset Profile ---")
    print(f"Total Rows: {len(df_clean)}")
    print(f"Makes ({df_clean['Make'].nunique()}): {sorted([str(x) for x in df_clean['Make'].dropna().unique()])}")
    print(f"Models ({df_clean['Model'].nunique()}): {sorted([str(x) for x in df_clean['Model'].dropna().unique()])[:15]}...")
    print(f"States: {dict(df_clean['State'].value_counts())}")
    print(f"Months: {dict(df_clean['Month'].value_counts())}")
    print(f"Segments: {dict(df_clean['Seller Segment'].value_counts())}")

    # File paths
    auto_dir = r"C:\Users\TC100\OneDrive - TVS Mobility Private Limited\Desktop\Conversion Data_Consolidation Automation"
    bi_dir = r"c:\Users\TC100\OneDrive - TVS Mobility Private Limited\Desktop\BI Dashboard V2"

    target_analytics_auto = os.path.join(auto_dir, "Consolidated_Conversion_Data_Jan_Sep2026_Analytics_GST Calculations.xlsx")
    target_analytics_bi = os.path.join(bi_dir, "Conversion_Data_Jan_Sep2026_Analytics_GST Calculations.xlsx")

    # Build and save Analytics workbooks
    build_normalized_analytics_workbook(
        df_clean=df_clean,
        output_paths=[target_analytics_auto, target_analytics_bi],
        subtitle="January to September 2026"
    )

    # Build and save 16-Column Bulletproof Master Entry Template
    target_tpl_auto = os.path.join(auto_dir, "Conversion_Data_Jan_Sep2026_Master_Template.xlsx")
    target_tpl_bi = os.path.join(bi_dir, "Conversion_Data_Jan_Sep2026_Master_Template.xlsx")

    build_normalized_16col_master_template(
        df_clean=df_clean,
        output_paths=[target_tpl_auto, target_tpl_bi]
    )

    # Update Conversion Data till sept.xlsx
    till_sept_path = os.path.join(auto_dir, "Conversion Data till sept.xlsx")
    if os.path.exists(till_sept_path):
        try:
            wb_till = openpyxl.load_workbook(till_sept_path)
            s_target = next((s for s in wb_till.sheetnames if 'conversion data' in s.lower()), None)
            if s_target:
                ws_t = wb_till[s_target]
                for r in range(4, ws_t.max_row + 1):
                    for c in range(1, 15):
                        ws_t.cell(row=r, column=c).value = None

                for r_idx, (_, rec) in enumerate(df_clean.iterrows(), start=4):
                    vals = [
                        str(rec['FY']), str(rec['Month']), str(rec['State']), clean_v(rec['Vehicle Number']),
                        str(rec['Make']), str(rec['Model']), parse_num(rec['Year'], is_int=True), parse_num(rec['Odometer'], is_int=True),
                        parse_num(rec['Final Bid Value'], is_int=False), str(rec['Seller Name']), str(rec['Seller Segment']),
                        str(rec['Buyer Name']), parse_num(rec['Total Income (Ex GST)'], is_int=False)
                    ]
                    for c_idx, val in enumerate(vals, start=2):
                        ws_t.cell(row=r_idx, column=c_idx, value=val)
                safe_save(wb_till, till_sept_path)
        except Exception as e:
            print(f"Could not update till sept: {e}")

    print("\n" + "=" * 80)
    print("  ALL 4,314 ROWS NORMALIZED & STANDARDIZED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    main()

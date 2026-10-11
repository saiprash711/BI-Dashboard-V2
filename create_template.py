"""
Generator for the standard error-proof Conversion Data Entry Template.
Includes strict dropdown data validations (stop-mode), auto-calculating Excel formulas,
and comprehensive master lookup lists for Excel and Google Sheets.
"""
import io
import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
import pandas as pd
import data_engine as DE

def build_template_workbook(source_df: pd.DataFrame | None = None) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    
    # -------------------------------------------------------------
    # 1. Master Lookup Data Preparation
    # -------------------------------------------------------------
    fy_list = ["FY24", "FY25", "FY26", "FY27", "FY28"]
    month_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    states_list = [
        "TN", "Kerala", "AP/TS", "Karnataka", "Maharashtra", 
        "Delhi", "Telangana", "Andhra Pradesh", "Gujarat", 
        "Rajasthan", "Uttar Pradesh", "West Bengal", "Other"
    ]
    
    segment_list = ["Captive", "Non-Captive"]
    
    make_list = [
        "MARUTI SUZUKI", "HYUNDAI", "TATA", "TOYOTA", "HONDA",
        "MAHINDRA", "RENAULT", "VOLKSWAGEN", "FORD", "NISSAN",
        "DATSUN", "SKODA", "KIA", "MG MOTORS", "CHEVROLET",
        "FIAT", "BMW", "MITSUBISHI", "JEEP", "CITROEN",
        "ASHOK LEYLAND", "SML ISUZU", "VOLVO", "HINDUSTAN MOTORS", "OPEL"
    ]
    
    # Base canonical models list (Swift and Dzire strictly separated!)
    models_list = [
        # Maruti Suzuki
        "Swift", "Dzire", "Alto", "Alto 800", "Alto K10", "800",
        "Wagon R", "Baleno", "Celerio", "Celerio X", "Ciaz", 
        "Vitara Brezza", "Grand Vitara", "S-Presso", "S-Cross", 
        "Ertiga", "XL6", "Ignis", "Ritz", "Fronx", "Jimny", 
        "Zen", "Zen Estilo", "A-Star", "SX4", "Esteem", "Eeco", "Omni",
        # Hyundai
        "i10", "Grand i10", "Grand i10 Nios", "i20", "Santro", "Eon", 
        "Getz", "Xcent", "Aura", "Verna", "Accent", "Venue", "Creta", 
        "Alcazar", "Tucson",
        # Tata Motors
        "Tiago", "Tiago EV", "Tigor", "Tigor EV", "Indica", "Indigo", 
        "Bolt", "Zest", "Altroz", "Punch", "Nexon", "Nexon EV", 
        "Harrier", "Safari", "Hexa", "Nano", "Aria",
        # Toyota
        "Etios", "Etios Liva", "Innova", "Innova Crysta", "Corolla Altis", 
        "Glanza", "Urban Cruiser", "Hyryder", "Yaris", "Camry", "Qualis",
        # Honda
        "City", "Amaze", "Brio", "Jazz", "Civic", "Accord", 
        "WR-V", "BR-V", "CR-V", "Mobilio", "Elevate",
        # Ford
        "Figo", "Aspire", "EcoSport", "Endeavour", "Fiesta", "Fiesta Classic", "Freestyle", "Ikon",
        # Volkswagen & Skoda
        "Polo", "Vento", "Ameo", "Virtus", "Taigun", "Jetta", "Passat",
        "Fabia", "Rapid", "Slavia", "Kushaq", "Octavia", "Laura", "Superb",
        # Datsun & Nissan
        "Go", "Go Plus", "Redi-GO", "Micra", "Micra Active", "Sunny", "Magnite", "Kicks", "Terrano",
        # Mahindra
        "Bolero", "Scorpio", "Thar", "XUV300", "XUV400", "XUV500", "XUV700", 
        "KUV100", "TUV300", "Xylo", "Verito", "Quanto", "Marazzo",
        # Renault
        "Kwid", "Triber", "Kiger", "Duster", "Lodgy", "Pulse", "Scala",
        # Others
        "Seltos", "Sonet", "Carens", "Carnival",
        "Hector", "Hector Plus", "Astor", "ZS EV",
        "Compass", "Punto", "Linea", "Avventura",
        "Beat", "Spark", "Sail", "Cruze", "Tavera",
        "Dost", "Load King", "Samrat"
    ]
    
    # Merge all models from source dataset if provided
    if source_df is not None and "Model" in source_df.columns:
        dataset_models = [m for m in source_df["Model"].dropna().unique().tolist() if m.strip()]
        models_list = sorted(list(set(models_list + dataset_models)))
    else:
        models_list = sorted(list(set(models_list)))
    
    # Complete list of Seller accounts from actual data
    if source_df is not None and "Seller Name" in source_df.columns:
        sellers_list = sorted([s for s in source_df["Seller Name"].dropna().unique().tolist() if s.strip()])
    else:
        sellers_list = [
            "AADHI CARS PRIVATE LIMITED", "AA CARS", "EXCHANGE ROTN", "KHIVRAJ MOTOR",
            "POPULAR MARUTI", "POPULAR HYUNDAI", "POPULAR MOTORWORLD PVT LTD", "POPULAR VEHICLES",
            "CASTLE TRADERS MARUTI", "CASTLE TRADERS HONDA", "CASTLE TRADERS MAHINDRA",
            "STEER AUTO TECHNOLOGIES PRIVATE LIMITED", "VISHNU CARS PRIVATE LIMITED",
            "EXCHANGE CHENNAI", "EXCHANGE HYDERABAD", "EXCHANGE VIJAYAWADA", "EXCHANGE VIZAG",
            "CARS INDIA", "ABT LIMITED", "KALYANI MOTORS MARUTI", "NIPPON MOTOR CORPORATION PVT LTD",
            "EVM CITROEN", "LUXON TATA", "KVR TATA", "JAIKRISHNAA AUTOSALES PRIVATE LIMITED",
            "BALAJI CARS", "KRISH TOYOTA", "KAIRALI TOYOTA", "INCHEON KIA", "PINNACLE NISSAN"
        ]
        
    # Complete list of Buyer accounts from actual data (NO TRUNCATION!)
    if source_df is not None and "Buyer Name" in source_df.columns:
        buyers_list = sorted([b for b in source_df["Buyer Name"].dropna().unique().tolist() if b.strip()])
    else:
        buyers_list = [
            "AAA Cars", "Aitos Cars", "Cars24", "Dream Drive", "Essar Preowned Cars",
            "Grid 33", "Gugha Cars", "Kamal Cars", "Madhura Cars", "Maxx Motors",
            "Nirmal Cars", "Pine Autos", "Popular Thrissur", "S2 Cars", "Sai Cars",
            "Santhosh Cars", "Shakthi Cars", "Uzhavan Enterprise", "Yes Cars"
        ]

    # -------------------------------------------------------------
    # 2. Sheet 2: Master Lookup Lists
    # -------------------------------------------------------------
    ws_lookup = wb.create_sheet(title="Lookup Lists")
    ws_lookup.views.sheetView[0].showGridLines = True
    
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
    
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    cell_font = Font(name="Calibri", size=10, color="0F172A")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    
    lookup_buffered_limits = {
        "FY": 30,
        "Month": 20,
        "State": 60,
        "Seller Segment": 10,
        "Make": 100,
        "Model": 500,
        "Authorised Sellers": 1000,
        "Verified Buyers": 2000,
    }

    lookup_ranges = {}
    for col_idx, (col_name, items) in enumerate(lookup_cols, start=1):
        col_letter = get_column_letter(col_idx)
        cell = ws_lookup.cell(row=1, column=col_idx, value=col_name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
        for r_idx, val in enumerate(items, start=2):
            c = ws_lookup.cell(row=r_idx, column=col_idx, value=val)
            c.font = cell_font
            c.border = thin_border
            
        buffer_end = max(len(items) + 100, lookup_buffered_limits.get(col_name, len(items) + 100))
        # Direct range reference: 100% native in Excel & Google Sheets.
        # In-cell dropdown arrow is guaranteed to show, and any newly added item at the bottom is immediately included!
        lookup_ranges[col_name] = f"'Lookup Lists'!${col_letter}$2:${col_letter}${buffer_end}"
        ws_lookup.column_dimensions[col_letter].width = max(len(col_name) + 4, max((len(str(x)) for x in items[:50]), default=10) + 4)



    # -------------------------------------------------------------
    # 3. Sheet 1: Main Data Entry Sheet
    # -------------------------------------------------------------
    ws_entry = wb.active
    ws_entry.title = "Conversion Data Entry"
    ws_entry.views.sheetView[0].showGridLines = True
    ws_entry.freeze_panes = "A2"
    
    columns_spec = [
        # (Header, Width, Fill, Type/Note)
        ("FY", 12, "0F172A", "dropdown_fy"),
        ("Month", 12, "0F172A", "dropdown_month"),
        ("State", 14, "0F172A", "dropdown_state"),
        ("Vehicle Number", 18, "0F172A", "text_veh"),
        ("Make", 20, "0F172A", "dropdown_make"),
        ("Model", 22, "0F172A", "dropdown_model"),
        ("Seller Name", 34, "0F172A", "dropdown_seller"),
        ("Seller Segment", 16, "0F172A", "dropdown_segment"),
        ("Buyer Name", 32, "0F172A", "dropdown_buyer"),
        ("Year", 12, "0F172A", "num_year"),
        ("Odometer", 16, "0F172A", "num_odo"),
        ("Final Bid Value", 18, "0F172A", "num_bid"),
        ("Total Income (Ex GST)", 22, "064E3B", "num_ex_gst"), # Dark Emerald (Entry)
        ("Total Income (Inc GST)", 24, "1E3A8A", "formula_inc_gst"), # Dark Navy (Auto-calculated formula)
        ("GST (18%)", 18, "312E81", "formula_gst"), # Indigo (Auto-calculated formula)
        ("Period", 16, "334155", "formula_period"), # Slate (Auto-calculated formula)
    ]
    
    for col_idx, (col_name, width, fill_hex, spec_type) in enumerate(columns_spec, start=1):
        col_letter = get_column_letter(col_idx)
        cell = ws_entry.cell(row=1, column=col_idx, value=col_name)
        cell.fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
        cell.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws_entry.column_dimensions[col_letter].width = width

    # Sample pre-filled demo rows demonstrating strictly valid inputs
    sample_rows = [
        ("FY26", "Jan", "TN", "TN01BU4318", "MARUTI SUZUKI", "Swift", "AADHI CARS PRIVATE LIMITED", "Captive", "Santhosh Cars", 2018, 54200, 485000, 10000.00),
        ("FY26", "Jan", "TN", "TN09CD5542", "MARUTI SUZUKI", "Dzire", "CASTLE TRADERS MARUTI", "Captive", "Nirmal Cars", 2019, 62100, 520000, 12500.00),
        ("FY26", "Feb", "Kerala", "KL07CV0988", "HYUNDAI", "Grand i10", "POPULAR HYUNDAI", "Non-Captive", "Popular Thrissur", 2017, 71500, 340000, 8500.00),
        ("FY26", "Feb", "AP/TS", "AP31DL4542", "DATSUN", "Go", "AA CARS", "Captive", "Aitos Cars", 2016, 48000, 210000, 6000.00),
        ("FY26", "Mar", "TN", "TN38BZ1234", "TOYOTA", "Innova Crysta", "KRISH TOYOTA", "Non-Captive", "Grid 33", 2020, 88000, 1650000, 25000.00),
    ]

    total_entry_rows = 2500
    curr_format = "₹#,##0.00"
    num_format = "#,##0"
    int_format = "0"
    
    for r_idx in range(2, total_entry_rows + 2):
        row_num = r_idx
        is_sample = (r_idx - 2 < len(sample_rows))
        
        if is_sample:
            sample = sample_rows[r_idx - 2]
            for c_i, val in enumerate(sample, start=1):
                cell = ws_entry.cell(row=r_idx, column=c_i, value=val)
                cell.font = Font(name="Calibri", size=10, color="0F172A")
                cell.border = thin_border
                if c_i in (10,): # Year
                    cell.number_format = int_format
                    cell.alignment = Alignment(horizontal="center")
                elif c_i in (11,): # Odometer
                    cell.number_format = num_format
                    cell.alignment = Alignment(horizontal="right")
                elif c_i in (12, 13): # Final Bid, Ex GST
                    cell.number_format = curr_format
                    cell.alignment = Alignment(horizontal="right")
                elif c_i in (1, 2, 3):
                    cell.alignment = Alignment(horizontal="center")
                    
            # For sample rows, pre-calculate values in formulas so readers see clean numbers
            ex_val = sample[12]
            inc_val = round(ex_val * 1.18, 2)
            gst_val = round(inc_val - ex_val, 2)
            period_val = f"{sample[0]} · {sample[1]}"
            
            cell_n = ws_entry.cell(row=r_idx, column=14, value=f'=IF(M{row_num}="","",ROUND(M{row_num}*1.18,2))')
            cell_n.font = Font(name="Calibri", size=10, bold=True, color="1E3A8A")
            cell_n.number_format = curr_format
            cell_n.alignment = Alignment(horizontal="right")
            cell_n.border = thin_border
            
            cell_o = ws_entry.cell(row=r_idx, column=15, value=f'=IF(M{row_num}="","",ROUND(N{row_num}-M{row_num},2))')
            cell_o.font = Font(name="Calibri", size=10, color="312E81")
            cell_o.number_format = curr_format
            cell_o.alignment = Alignment(horizontal="right")
            cell_o.border = thin_border
            
            cell_p = ws_entry.cell(row=r_idx, column=16, value=f'=IF(AND(A{row_num}<>"",B{row_num}<>""), A{row_num}&" · "&B{row_num}, "")')
            cell_p.font = Font(name="Calibri", size=10, color="475569")
            cell_p.alignment = Alignment(horizontal="center")
            cell_p.border = thin_border
        else:
            # Set formatting for empty entry rows
            for c_i in range(1, 14):
                cell = ws_entry.cell(row=r_idx, column=c_i)
                cell.font = Font(name="Calibri", size=10, color="0F172A")
                cell.border = thin_border
                if c_i == 10:
                    cell.number_format = int_format
                    cell.alignment = Alignment(horizontal="center")
                elif c_i == 11:
                    cell.number_format = num_format
                    cell.alignment = Alignment(horizontal="right")
                elif c_i in (12, 13):
                    cell.number_format = curr_format
                    cell.alignment = Alignment(horizontal="right")
                elif c_i in (1, 2, 3):
                    cell.alignment = Alignment(horizontal="center")

            # Auto-calculated formulas (Col N: Total Income, Col O: GST, Col P: Period)
            cell_n = ws_entry.cell(row=r_idx, column=14, value=f'=IF(M{row_num}="","",ROUND(M{row_num}*1.18,2))')
            cell_n.font = Font(name="Calibri", size=10, bold=True, color="1E3A8A")
            cell_n.number_format = curr_format
            cell_n.alignment = Alignment(horizontal="right")
            cell_n.border = thin_border
            
            cell_o = ws_entry.cell(row=r_idx, column=15, value=f'=IF(M{row_num}="","",ROUND(N{row_num}-M{row_num},2))')
            cell_o.font = Font(name="Calibri", size=10, color="312E81")
            cell_o.number_format = curr_format
            cell_o.alignment = Alignment(horizontal="right")
            cell_o.border = thin_border
            
            cell_p = ws_entry.cell(row=r_idx, column=16, value=f'=IF(AND(A{row_num}<>"",B{row_num}<>""), A{row_num}&" · "&B{row_num}, "")')
            cell_p.font = Font(name="Calibri", size=10, color="475569")
            cell_p.alignment = Alignment(horizontal="center")
            cell_p.border = thin_border

    # Enable Excel auto-filter on the data range
    ws_entry.auto_filter.ref = f"A1:P{total_entry_rows + 1}"

    # -------------------------------------------------------------
    # 4. Data Validations (STRICT BULLETPROOF RULES)
    # Every single validation uses errorStyle='stop' so typos like
    # 'Normal Cars' are strictly rejected and cannot be entered!
    # -------------------------------------------------------------
    
    # 1. FY Dropdown (Strict)
    dv_fy = DataValidation(type="list", formula1=lookup_ranges["FY"], allow_blank=True)
    dv_fy.errorStyle = 'stop'
    dv_fy.errorTitle = 'Invalid Financial Year'
    dv_fy.error = 'Please select an authorized FY from the dropdown (e.g. FY26).'
    dv_fy.promptTitle = 'Financial Year'
    dv_fy.prompt = 'Select FY from dropdown (FY24..FY28).'
    dv_fy.showErrorMessage = True
    dv_fy.showInputMessage = True
    ws_entry.add_data_validation(dv_fy)
    dv_fy.add(f"A2:A{total_entry_rows + 1}")

    # 2. Month Dropdown (Strict)
    dv_month = DataValidation(type="list", formula1=lookup_ranges["Month"], allow_blank=True)
    dv_month.errorStyle = 'stop'
    dv_month.errorTitle = 'Invalid Month'
    dv_month.error = 'Please select a valid month from the dropdown (Jan..Dec). Custom casing like JAN or January is not permitted.'
    dv_month.promptTitle = 'Month'
    dv_month.prompt = 'Select standard 3-letter month.'
    dv_month.showErrorMessage = True
    dv_month.showInputMessage = True
    ws_entry.add_data_validation(dv_month)
    dv_month.add(f"B2:B{total_entry_rows + 1}")

    # 3. State Dropdown (Strict)
    dv_state = DataValidation(type="list", formula1=lookup_ranges["State"], allow_blank=True)
    dv_state.errorStyle = 'stop'
    dv_state.errorTitle = 'Invalid State'
    dv_state.error = 'Please choose a standard state or cluster code from the dropdown.'
    dv_state.promptTitle = 'State / Cluster'
    dv_state.prompt = 'Select state code (TN, Kerala, AP/TS, etc.).'
    dv_state.showErrorMessage = True
    dv_state.showInputMessage = True
    ws_entry.add_data_validation(dv_state)
    dv_state.add(f"C2:C{total_entry_rows + 1}")

    # 4. Vehicle Number (Strict length 6..14)
    dv_veh = DataValidation(type="textLength", operator="between", formula1=6, formula2=14, allow_blank=True)
    dv_veh.errorStyle = 'stop'
    dv_veh.errorTitle = 'Invalid Vehicle Registration'
    dv_veh.error = 'Vehicle registration number must be 6 to 14 characters without spaces or symbols (e.g. TN01BU4318).'
    dv_veh.promptTitle = 'Vehicle Number'
    dv_veh.prompt = 'Enter standard registration number (6 to 14 characters).'
    dv_veh.showErrorMessage = True
    dv_veh.showInputMessage = True
    ws_entry.add_data_validation(dv_veh)
    dv_veh.add(f"D2:D{total_entry_rows + 1}")

    # 5. Make Dropdown (Strict)
    dv_make = DataValidation(type="list", formula1=lookup_ranges["Make"], allow_blank=True)
    dv_make.errorStyle = 'stop'
    dv_make.errorTitle = 'Invalid Vehicle Make'
    dv_make.error = 'Please choose an official manufacturer from the dropdown (e.g. MARUTI SUZUKI, HYUNDAI, TATA). Custom spellings are blocked.'
    dv_make.promptTitle = 'Manufacturer'
    dv_make.prompt = 'Pick manufacturer from dropdown.'
    dv_make.showErrorMessage = True
    dv_make.showInputMessage = True
    ws_entry.add_data_validation(dv_make)
    dv_make.add(f"E2:E{total_entry_rows + 1}")

    # 6. Model Dropdown (Strict - Swift & Dzire distinct!)
    dv_model = DataValidation(type="list", formula1=lookup_ranges["Model"], allow_blank=True)
    dv_model.errorStyle = 'stop'
    dv_model.errorTitle = 'Invalid Vehicle Model'
    dv_model.error = 'Please select a verified model from the dropdown. Note: Swift (Hatchback) and Dzire (Sedan) are strictly separate models.'
    dv_model.promptTitle = 'Model'
    dv_model.prompt = 'Pick verified model (Swift and Dzire are strictly separate).'
    dv_model.showErrorMessage = True
    dv_model.showInputMessage = True
    ws_entry.add_data_validation(dv_model)
    dv_model.add(f"F2:F{total_entry_rows + 1}")

    # 7. Seller Name Dropdown (Strict Stop)
    dv_seller = DataValidation(type="list", formula1=lookup_ranges["Authorised Sellers"], allow_blank=True)
    dv_seller.errorStyle = 'stop'
    dv_seller.errorTitle = 'Invalid Dealership Account'
    dv_seller.error = 'Unrecognised Seller. Please pick from the dropdown list. To add a new dealership, add their legal entity name to the Lookup Lists tab first.'
    dv_seller.promptTitle = 'Authorised Dealer Account'
    dv_seller.prompt = 'Start typing to search authorized dealership accounts.'
    dv_seller.showErrorMessage = True
    dv_seller.showInputMessage = True
    ws_entry.add_data_validation(dv_seller)
    dv_seller.add(f"G2:G{total_entry_rows + 1}")

    # 8. Seller Segment Dropdown (Strict)
    dv_segment = DataValidation(type="list", formula1=lookup_ranges["Seller Segment"], allow_blank=True)
    dv_segment.errorStyle = 'stop'
    dv_segment.errorTitle = 'Invalid Segment'
    dv_segment.error = 'Seller Segment must be either Captive or Non-Captive.'
    dv_segment.promptTitle = 'Segment'
    dv_segment.prompt = 'Pick Captive or Non-Captive.'
    dv_segment.showErrorMessage = True
    dv_segment.showInputMessage = True
    ws_entry.add_data_validation(dv_segment)
    dv_segment.add(f"H2:H{total_entry_rows + 1}")

    # 9. Buyer Name Dropdown (Strict Stop - NO TYPOS ALLOWED!)
    # Blocks 'Normal Cars' and auto-suggests 'Nirmal Cars' as user types
    dv_buyer = DataValidation(type="list", formula1=lookup_ranges["Verified Buyers"], allow_blank=True)
    dv_buyer.errorStyle = 'stop'
    dv_buyer.errorTitle = 'Invalid Buyer Account'
    dv_buyer.error = "Unrecognised Buyer Account. Typos (such as 'Normal Cars' instead of 'Nirmal Cars') are blocked. Please pick a verified buyer from the dropdown list or register new buyers in the Lookup Lists tab."
    dv_buyer.promptTitle = 'Verified Buyer'
    dv_buyer.prompt = "Start typing to search verified buyer accounts (e.g. typing 'Nir' will suggest 'Nirmal Cars')."
    dv_buyer.showErrorMessage = True
    dv_buyer.showInputMessage = True
    ws_entry.add_data_validation(dv_buyer)
    dv_buyer.add(f"I2:I{total_entry_rows + 1}")

    # 10. Year Whole Number (Strict: 1990 - 2035)
    dv_year = DataValidation(type="whole", operator="between", formula1=1990, formula2=2035, allow_blank=True)
    dv_year.errorStyle = 'stop'
    dv_year.errorTitle = 'Invalid Manufacturing Year'
    dv_year.error = 'Year must be a 4-digit manufacturing year between 1990 and 2035.'
    dv_year.promptTitle = 'Year'
    dv_year.prompt = 'Enter 4-digit year (1990 - 2035).'
    dv_year.showErrorMessage = True
    dv_year.showInputMessage = True
    ws_entry.add_data_validation(dv_year)
    dv_year.add(f"J2:J{total_entry_rows + 1}")

    # 11. Odometer (Strict >= 0)
    dv_odo = DataValidation(type="whole", operator="greaterThanOrEqual", formula1=0, allow_blank=True)
    dv_odo.errorStyle = 'stop'
    dv_odo.errorTitle = 'Invalid Odometer'
    dv_odo.error = 'Odometer reading cannot be negative.'
    dv_odo.promptTitle = 'Odometer (km)'
    dv_odo.prompt = 'Enter distance in km (>= 0).'
    dv_odo.showErrorMessage = True
    dv_odo.showInputMessage = True
    ws_entry.add_data_validation(dv_odo)
    dv_odo.add(f"K2:K{total_entry_rows + 1}")

    # 12. Final Bid Value (Strict >= 1000)
    dv_bid = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1=1000, allow_blank=True)
    dv_bid.errorStyle = 'stop'
    dv_bid.errorTitle = 'Invalid Bid Value'
    dv_bid.error = 'Winning bid value must be at least ₹1,000.'
    dv_bid.promptTitle = 'Final Bid Value'
    dv_bid.prompt = 'Enter winning bid in INR (>= 1,000).'
    dv_bid.showErrorMessage = True
    dv_bid.showInputMessage = True
    ws_entry.add_data_validation(dv_bid)
    dv_bid.add(f"L2:L{total_entry_rows + 1}")

    # 13. Total Income (Ex GST) (Strict >= 0)
    dv_ex_gst = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1=0, allow_blank=True)
    dv_ex_gst.errorStyle = 'stop'
    dv_ex_gst.errorTitle = 'Invalid Platform Fee'
    dv_ex_gst.error = 'Total Income (Ex GST) must be a positive number or 0.'
    dv_ex_gst.promptTitle = 'Commission (Ex GST)'
    dv_ex_gst.prompt = 'Enter platform commission excluding GST (>= 0).'
    dv_ex_gst.showErrorMessage = True
    dv_ex_gst.showInputMessage = True
    ws_entry.add_data_validation(dv_ex_gst)
    dv_ex_gst.add(f"M2:M{total_entry_rows + 1}")

    # -------------------------------------------------------------
    # 5. Sheet 3: User Guide & Instructions
    # -------------------------------------------------------------
    ws_guide = wb.create_sheet(title="User Instructions")
    ws_guide.views.sheetView[0].showGridLines = True
    
    ws_guide["A1"] = "CONVERSION ANALYTICS — BULLETPROOF DATA ENTRY TEMPLATE GUIDE"
    ws_guide["A1"].font = Font(name="Calibri", size=14, bold=True, color="0F172A")
    
    guide_sections = [
        ("Purpose", "This template is engineered to prevent human typos, spelling discrepancies, casing mismatches, and mathematical rounding errors. All inputs match the Single Source of Truth schema."),
        ("1. Search & Autocomplete", "As you start typing in any dropdown cell (such as Make, Model, Seller Name, or Buyer Name), Excel and Google Sheets will automatically filter and suggest matching names. For example, typing 'Nir' in Buyer Name will immediately suggest 'Nirmal Cars'."),
        ("2. Strict Stop Enforcement (No Typos Allowed)", "Every dropdown is locked with Stop-level validation. If an accidental typo like 'Normal Cars' is entered instead of 'Nirmal Cars', Excel will immediately block the entry with an error dialog and require you to pick the verified name."),
        ("3. Body Style Integrity", "Swift and Dzire are strictly separate models: 'Swift' represents the hatchback, while 'Dzire' represents the sedan. Similarly, Tiago (Hatch) and Tigor (Sedan), Etios Liva (Hatch) and Etios (Sedan), Figo (Hatch) and Aspire (Sedan), and Polo (Hatch) and Vento (Sedan) are strictly separated."),
        ("4. Auto-Calculated Formulas", "Columns N (Total Income Inc GST), O (GST 18%), and P (Period) are automated formulas. Simply enter 'Final Bid Value' and 'Total Income (Ex GST)'. Excel / Google Sheets will automatically calculate 18% GST and gross billing without any rounding mistakes."),
        ("5. Registering New Buyers or Sellers", "If you need to enter a genuine new dealership or buyer that is not yet in the system, switch to the 'Lookup Lists' tab and add the name to the bottom of the Verified Buyers or Authorised Sellers column. It will immediately become available in the dropdown!"),
        ("6. Copy-Pasting Data", "When copying rows from external files, use 'Paste Values' (Ctrl+Shift+V or Right-Click -> Paste Values). This avoids overwriting the cell dropdown validations."),
        ("7. Google Sheets Compatibility", "You can upload this file directly to Google Drive and open with Google Sheets. All dropdowns, autocomplete rules, data validations, and formulas are 100% compatible with Google Sheets."),
    ]
    
    curr_r = 3
    for title, text in guide_sections:
        ws_guide.cell(row=curr_r, column=1, value=f"◈  {title}").font = Font(name="Calibri", size=11, bold=True, color="1E293B")
        curr_r += 1
        ws_guide.cell(row=curr_r, column=1, value=text).font = Font(name="Calibri", size=10, color="475569")
        ws_guide.row_dimensions[curr_r].height = 24
        curr_r += 2
        
    ws_guide.column_dimensions["A"].width = 110
    
    return wb

def create_template_file(output_path: str = "Conversion_Data_Template_Master.xlsx") -> str:
    source_df = None
    sample_files = [
        r"C:\Users\TC100\Downloads\Conversion_Data_Jan_Aug2026_Analytics_GST Calculations_normalised.xlsx",
        "Conversion_Data_Jan_Aug2026_Analytics_GST Calculations.xlsx"
    ]
    for p in sample_files:
        if os.path.exists(p):
            try:
                df, _ = DE.parse_workbook(p)
                if df is not None and not df.empty:
                    source_df = df
                    break
            except Exception:
                pass
                
    wb = build_template_workbook(source_df)
    
    saved_path = None
    # Save to Master first, then try updating any previous versions that may not be locked
    candidates = [
        output_path,
        "Conversion_Data_Template_Master.xlsx",
        "Conversion_Data_Template_Dynamic.xlsx",
        "Conversion_Data_Template_Bulletproof.xlsx",
        "Conversion_Data_Template_Dropdowns.xlsx"
    ]
    for p in candidates:
        try:
            wb.save(p)
            if saved_path is None:
                saved_path = p
        except Exception:
            pass # File is locked by Excel
            
    return saved_path or output_path

def get_template_bytes(path: str = "Conversion_Data_Template_Master.xlsx") -> bytes:
    candidates = [
        "Conversion_Data_Template_Master.xlsx",
        path,
        "Conversion_Data_Template_Dynamic.xlsx",
        "Conversion_Data_Template_Bulletproof.xlsx",
        "Conversion_Data_Template_Dropdowns.xlsx"
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                with open(candidate, "rb") as f:
                    return f.read()
            except Exception:
                pass
    p = create_template_file(path)
    with open(p, "rb") as f:
        return f.read()

if __name__ == "__main__":
    out = create_template_file()
    print("Created template:", out)


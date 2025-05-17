import streamlit as st
import json # For potential debugging or displaying raw dicts, not primary for UI

# --- Streamlit App UI ---
st.set_page_config(page_title="CISKO - Kalkulátor Příjmů", layout="wide", initial_sidebar_state="expanded") 

# --- Constants for 2024 (Czech Republic) ---
# Sources for updates: Ministry of Finance CZ (mfcr.cz),
# Czech Social Security Administration (cssz.cz), Health Insurance Companies (e.g., VZP).

# --- General ---
PERSONAL_TAX_CREDIT_ANNUAL_2024 = 30840.0  # Sleva na poplatníka (2570 CZK/month)
INCOME_TAX_THRESHOLD_ANNUAL_2024 = 1582812.0 # Threshold for 23% tax rate
INCOME_TAX_RATE_LOWER_2024 = 0.15
INCOME_TAX_RATE_HIGHER_2024 = 0.23
DEFAULT_WORK_DAYS_PER_YEAR = 252 # Approximate, can be adjusted by user in advanced settings
DEFAULT_MANDAYS_PER_YEAR_ICO = 220 # Default for man-day calculation

# --- HPP (Zaměstnanec - Employee) Constants 2024 ---
HPP_HEALTH_INSURANCE_RATE_EMPLOYEE_2024 = 0.045
HPP_SOCIAL_SECURITY_RATE_EMPLOYEE_2024 = 0.071 
HPP_HEALTH_INSURANCE_RATE_EMPLOYER_2024 = 0.09
HPP_SOCIAL_SECURITY_RATE_EMPLOYER_2024 = 0.248 

# --- IČO (OSVČ - Self-Employed) Constants 2024 ---
ICO_SOCIAL_SECURITY_RATE_2024 = 0.292
ICO_HEALTH_INSURANCE_RATE_2024 = 0.135
ICO_SICKNESS_INSURANCE_RATE_2024 = 0.021 
ICO_PROFIT_ASSESSMENT_BASE_FACTOR_2024 = 0.50 
ICO_MIN_SOCIAL_MONTHLY_MAIN_ACTIVITY_2024 = 3852.0
ICO_MIN_HEALTH_MONTHLY_2024 = 2968.0
ICO_MIN_SICKNESS_MONTHLY_2024 = 168.0 
MIN_ICO_SICKNESS_ASSESSMENT_BASE_MONTHLY_2024 = 8000.0 
PAUSALNI_DAN_BAND_1_MONTHLY_2024 = 7498.0
PAUSALNI_DAN_BAND_2_MONTHLY_2024 = 16745.0
PAUSALNI_DAN_BAND_3_MONTHLY_2024 = 27139.0
PAUSALNI_DAN_MAX_REVENUE_2024 = 2000000.0

# --- Calculation Functions ---
def calculate_hpp_income(
    gross_monthly_income: float, 
    other_annual_tax_credits: float = 0.0,
    work_days_per_year_input: int = DEFAULT_WORK_DAYS_PER_YEAR
) -> dict:
    gross_annual_income = gross_monthly_income * 12
    # Initialize values for zero income case
    net_annual_income = 0
    net_monthly_income = 0
    net_daily_income = 0
    health_insurance_employee = 0
    social_security_employee = 0
    final_income_tax = 0
    total_employer_cost_annual = 0

    if gross_monthly_income < 0:
         return {"error": "Hrubý měsíční příjem nemůže být záporný."}
    elif gross_monthly_income > 0:
        health_insurance_employee = gross_annual_income * HPP_HEALTH_INSURANCE_RATE_EMPLOYEE_2024
        social_security_employee = gross_annual_income * HPP_SOCIAL_SECURITY_RATE_EMPLOYEE_2024
        health_insurance_employer = gross_annual_income * HPP_HEALTH_INSURANCE_RATE_EMPLOYER_2024
        social_security_employer = gross_annual_income * HPP_SOCIAL_SECURITY_RATE_EMPLOYER_2024
        total_employer_contributions = health_insurance_employer + social_security_employer
        total_employer_cost_annual = gross_annual_income + total_employer_contributions
        taxable_income_for_tax_calc = gross_annual_income
        income_tax_before_credits = 0
        if taxable_income_for_tax_calc <= INCOME_TAX_THRESHOLD_ANNUAL_2024:
            income_tax_before_credits = taxable_income_for_tax_calc * INCOME_TAX_RATE_LOWER_2024
        else:
            income_tax_before_credits = (INCOME_TAX_THRESHOLD_ANNUAL_2024 * INCOME_TAX_RATE_LOWER_2024) + \
                                      ((taxable_income_for_tax_calc - INCOME_TAX_THRESHOLD_ANNUAL_2024) * INCOME_TAX_RATE_HIGHER_2024)
        total_tax_credits = PERSONAL_TAX_CREDIT_ANNUAL_2024 + other_annual_tax_credits
        final_income_tax = max(0, income_tax_before_credits - total_tax_credits)
        net_annual_income = gross_annual_income - health_insurance_employee - social_security_employee - final_income_tax
        net_monthly_income = net_annual_income / 12 
        net_daily_income = net_annual_income / work_days_per_year_input if work_days_per_year_input > 0 else 0

    return {
        "typ": "HPP (Zaměstnanec)", "rok_kalkulace": 2024,
        "hruby_mesicni_prijem": round(gross_monthly_income, 2),
        "hruby_rocni_prijem": round(gross_annual_income, 2),
        "zamestnanec_rocni_zdravotni_pojisteni": round(health_insurance_employee, 2),
        "zamestnanec_rocni_socialni_pojisteni": round(social_security_employee, 2),
        "zamestnanec_konecna_rocni_dan_z_prijmu": round(final_income_tax, 2),
        "cisty_rocni_prijem_zamestnanec": round(net_annual_income, 2),
        "cisty_mesicni_prijem_zamestnanec": round(net_monthly_income, 2),
        "cisty_denni_prijem_zamestnanec": round(net_daily_income, 2),
        "zamestnavatel_celkove_rocni_naklady_na_zamestnance": round(total_employer_cost_annual, 2),
        "zamestnavatel_celkove_mesicni_naklady_na_zamestnance": round(total_employer_cost_annual / 12 if gross_annual_income > 0 else 0, 2),
    }

def calculate_ico_pausalni_vydaje_income(
    gross_annual_revenue: float, 
    expense_percentage: float, 
    realne_rocni_provozni_naklady: float = 0.0, 
    other_annual_tax_credits: float = 0.0, 
    participate_sickness_insurance: bool = False, 
    sickness_insurance_assessment_base_monthly: float = MIN_ICO_SICKNESS_ASSESSMENT_BASE_MONTHLY_2024,
    paid_vacation_days_by_client: int = 0, 
    paid_sick_days_by_client: int = 0,    
    actual_unpaid_vacation_days_taken: int = 0,
    actual_unpaid_sick_days_taken: int = 0,
    work_days_per_year_input: int = DEFAULT_WORK_DAYS_PER_YEAR
) -> dict:
    # Initialize values for zero revenue case
    net_annual_income_tax_method = 0
    net_monthly_income_tax_method = 0
    net_daily_income_tax_method_effective = 0
    net_annual_disposable_income = 0
    net_monthly_disposable_income = 0
    net_daily_disposable_income_effective = 0
    annual_expenses_for_tax = 0
    profit_for_tax_purposes = 0
    annual_social_security = 0
    annual_health_insurance = 0
    annual_sickness_insurance = 0
    final_income_tax = 0
    # Calculate effective work days based on all day inputs for the daily rate of *achieved* revenue
    effective_work_days_for_achieved_revenue_rate = work_days_per_year_input - actual_unpaid_vacation_days_taken - actual_unpaid_sick_days_taken


    if gross_annual_revenue < 0:
        return {"error": "Hrubý roční příjem (obrat) nemůže být záporný."}
    elif gross_annual_revenue > 0:
        max_revenue_for_lump_sum_application = 2000000.0
        applicable_revenue_for_lump_sum = min(gross_annual_revenue, max_revenue_for_lump_sum_application)
        max_expense_claim_amount = 0
        if expense_percentage == 0.80: max_expense_claim_amount = 1600000.0
        elif expense_percentage == 0.60: max_expense_claim_amount = 1200000.0
        elif expense_percentage == 0.40: max_expense_claim_amount = 800000.0
        elif expense_percentage == 0.30: max_expense_claim_amount = 600000.0
        else: return {"error": "Neplatné procento paušálních výdajů."}

        calculated_expenses_for_tax = applicable_revenue_for_lump_sum * expense_percentage
        annual_expenses_for_tax = min(calculated_expenses_for_tax, max_expense_claim_amount)
        profit_for_tax_purposes = (gross_annual_revenue - annual_expenses_for_tax) if gross_annual_revenue <= max_revenue_for_lump_sum_application \
                                    else (applicable_revenue_for_lump_sum - annual_expenses_for_tax) + (gross_annual_revenue - max_revenue_for_lump_sum_application)
        assessment_base_insurance = profit_for_tax_purposes * ICO_PROFIT_ASSESSMENT_BASE_FACTOR_2024
        min_annual_social_payment = ICO_MIN_SOCIAL_MONTHLY_MAIN_ACTIVITY_2024 * 12
        effective_social_assessment_base = max(assessment_base_insurance, 131901.0 if profit_for_tax_purposes > 0 else 0)
        annual_social_security = effective_social_assessment_base * ICO_SOCIAL_SECURITY_RATE_2024
        annual_social_security = max(annual_social_security, min_annual_social_payment if profit_for_tax_purposes > 0 else 0)
        min_annual_health_payment = ICO_MIN_HEALTH_MONTHLY_2024 * 12
        effective_health_assessment_base = max(assessment_base_insurance, 226800.0 if profit_for_tax_purposes > 0 else 0)
        annual_health_insurance = effective_health_assessment_base * ICO_HEALTH_INSURANCE_RATE_2024
        annual_health_insurance = max(annual_health_insurance, min_annual_health_payment if profit_for_tax_purposes > 0 else 0)
        annual_sickness_insurance = 0
        if participate_sickness_insurance and profit_for_tax_purposes > 0:
            actual_sickness_assessment_base_monthly = max(sickness_insurance_assessment_base_monthly, MIN_ICO_SICKNESS_ASSESSMENT_BASE_MONTHLY_2024)
            monthly_sickness_payment = actual_sickness_assessment_base_monthly * ICO_SICKNESS_INSURANCE_RATE_2024
            annual_sickness_insurance = max(monthly_sickness_payment, ICO_MIN_SICKNESS_MONTHLY_2024) * 12
        tax_base_for_income_tax = profit_for_tax_purposes
        income_tax_before_credits = 0
        if tax_base_for_income_tax <= INCOME_TAX_THRESHOLD_ANNUAL_2024:
            income_tax_before_credits = tax_base_for_income_tax * INCOME_TAX_RATE_LOWER_2024
        else:
            income_tax_before_credits = (INCOME_TAX_THRESHOLD_ANNUAL_2024 * INCOME_TAX_RATE_LOWER_2024) + \
                                      ((tax_base_for_income_tax - INCOME_TAX_THRESHOLD_ANNUAL_2024) * INCOME_TAX_RATE_HIGHER_2024)
        total_tax_credits = PERSONAL_TAX_CREDIT_ANNUAL_2024 + other_annual_tax_credits
        final_income_tax = max(0, income_tax_before_credits - total_tax_credits)
        net_annual_income_tax_method = profit_for_tax_purposes - annual_social_security - annual_health_insurance - annual_sickness_insurance - final_income_tax
        net_monthly_income_tax_method = net_annual_income_tax_method / 12
        total_annual_deductions_tax_method = annual_social_security + annual_health_insurance + annual_sickness_insurance + final_income_tax
        net_annual_disposable_income = gross_annual_revenue - realne_rocni_provozni_naklady - total_annual_deductions_tax_method
        net_monthly_disposable_income = net_annual_disposable_income / 12
        
        net_daily_income_tax_method_effective = net_annual_income_tax_method / effective_work_days_for_achieved_revenue_rate if effective_work_days_for_achieved_revenue_rate > 0 else 0
        net_daily_disposable_income_effective = net_annual_disposable_income / effective_work_days_for_achieved_revenue_rate if effective_work_days_for_achieved_revenue_rate > 0 else 0

    return {
        "typ": "IČO (Paušální výdaje)", "rok_kalkulace": 2024,
        "hruby_rocni_prijem_obrat": round(gross_annual_revenue, 2),
        "hruby_mesicni_prijem_obrat_prumer": round(gross_annual_revenue / 12 if gross_annual_revenue > 0 else 0, 2),
        "procento_pausalnich_vydaju": expense_percentage if gross_annual_revenue > 0 else 0,
        "rocni_pausalni_vydaje_pro_dane": round(annual_expenses_for_tax, 2),
        "zisk_pro_danove_ucely": round(profit_for_tax_purposes, 2),
        "rocni_socialni_pojisteni": round(annual_social_security, 2),
        "rocni_zdravotni_pojisteni": round(annual_health_insurance, 2),
        "rocni_nemocenske_pojisteni": round(annual_sickness_insurance, 2),
        "konecna_rocni_dan_z_prijmu": round(final_income_tax, 2),
        "cisty_rocni_prijem_dle_pausalu": round(net_annual_income_tax_method, 2),
        "cisty_mesicni_prijem_dle_pausalu": round(net_monthly_income_tax_method, 2),
        "cisty_denni_prijem_dle_pausalu_efektivni": round(net_daily_income_tax_method_effective, 2),
        "info_k_realnym_nakladum": {
            "vstup_realne_rocni_provozni_naklady": round(realne_rocni_provozni_naklady, 2),
            "cisty_rocni_prijem_disponibilni_po_realnych_nakladech": round(net_annual_disposable_income, 2),
            "cisty_mesicni_prijem_disponibilni_po_realnych_nakladech": round(net_monthly_disposable_income, 2),
            "cisty_denni_prijem_disponibilni_efektivni": round(net_daily_disposable_income_effective, 2)
        },
        "info_k_efektivite_dnu": { # For the primary calculation based on achieved revenue
            "uvazovane_pracovni_dny_pro_denni_sazbu": effective_work_days_for_achieved_revenue_rate if effective_work_days_for_achieved_revenue_rate > 0 else work_days_per_year_input,
            "paid_vacation_days_by_client": paid_vacation_days_by_client, # Keep for context
            "paid_sick_days_by_client": paid_sick_days_by_client # Keep for context
        }
    }

def calculate_ico_pausalni_dan_income(
    gross_annual_revenue: float,
    pausalni_dan_band: int,
    actual_unpaid_vacation_days_taken: int = 0, 
    actual_unpaid_sick_days_taken: int = 0,    
    work_days_per_year_input: int = DEFAULT_WORK_DAYS_PER_YEAR
) -> dict:
    net_annual_income = 0
    net_monthly_income = 0
    net_daily_income_effective = 0
    monthly_payment = 0
    # Calculate effective work days based on *only unpaid* days for this mode
    effective_work_days_for_rate = work_days_per_year_input - actual_unpaid_vacation_days_taken - actual_unpaid_sick_days_taken

    if gross_annual_revenue < 0:
        return {"error": "Hrubý roční příjem (obrat) nemůže být záporný."}
    elif gross_annual_revenue == 0:
        pass # All values remain 0
    elif gross_annual_revenue > PAUSALNI_DAN_MAX_REVENUE_2024: 
        return {"error": f"Příjem přesahuje limit {PAUSALNI_DAN_MAX_REVENUE_2024:,.0f} CZK pro paušální daň."}
    else:
        if pausalni_dan_band == 1: monthly_payment = PAUSALNI_DAN_BAND_1_MONTHLY_2024
        elif pausalni_dan_band == 2: monthly_payment = PAUSALNI_DAN_BAND_2_MONTHLY_2024
        elif pausalni_dan_band == 3: monthly_payment = PAUSALNI_DAN_BAND_3_MONTHLY_2024
        else: return {"error": "Neplatné pásmo paušální daně."}
        
        annual_pausalni_dan_payment = monthly_payment * 12
        net_annual_income = gross_annual_revenue - annual_pausalni_dan_payment
        net_monthly_income = net_annual_income / 12
        net_daily_income_effective = net_annual_income / effective_work_days_for_rate if effective_work_days_for_rate > 0 else 0
    
    return {
        "typ": "IČO (Paušální daň)", "rok_kalkulace": 2024,
        "hruby_rocni_prijem_obrat": round(gross_annual_revenue, 2),
        "hruby_mesicni_prijem_obrat_prumer": round(gross_annual_revenue / 12 if gross_annual_revenue > 0 else 0, 2),
        "zvolene_pasmo_pausalni_dane": pausalni_dan_band if gross_annual_revenue > 0 else "-",
        "mesicni_platba_pausalni_dane": round(monthly_payment, 2),
        "cisty_rocni_prijem": round(net_annual_income, 2),
        "cisty_mesicni_prijem": round(net_monthly_income, 2),
        "cisty_denni_prijem_efektivni": round(net_daily_income_effective, 2),
        "info_k_efektivite_dnu": { 
            "uvazovane_pracovni_dny_pro_denni_sazbu": effective_work_days_for_rate if effective_work_days_for_rate > 0 else work_days_per_year_input
        }
    }

# --- Streamlit App UI ---
st.title("CISKO - Čistý Srovnávací Kalkulátor Osoby (pro rok 2024)")
st.caption("Porovnání příjmů HPP vs. IČO v České republice. Výpočty jsou orientační, konzultujte s daňovým poradcem.")

# --- Globální nastavení ---
with st.sidebar.expander("⚙️ Globální nastavení", expanded=True):
    work_days_per_year_input = st.number_input("Počet pracovních dní v roce (základ)", min_value=200, max_value=300, value=DEFAULT_WORK_DAYS_PER_YEAR, step=1, help="Celkový počet potenciálních pracovních dní v roce. Používá se pro výpočet denních sazeb a pro odhad ušlého příjmu z neplaceného volna.", key="global_work_days")
    other_annual_tax_credits_input = st.number_input("Jiné roční slevy na dani (mimo slevy na poplatníka)", value=0.0, min_value=0.0, step=100.0, format="%.0f", key="global_other_credits", help="Např. na děti, manželku/manžela bez vlastních příjmů, školkovné, úroky z hypotéky. Základní sleva na poplatníka je již zahrnuta automaticky.")

# --- Scénář 1: HPP (Zaměstnanec) ---
st.header("👤 Scénář 1: HPP (Zaměstnanec)")
hpp_gross_monthly_income = st.number_input("Hrubá měsíční mzda (HPP)", value=50000.0, min_value=0.0, step=1000.0, format="%.0f", key="hpp_gross", help="Zadejte vaši hrubou měsíční mzdu.")

# --- Scénář 2: IČO (OSVČ) ---
st.header("💼 Scénář 2: IČO (OSVČ)")
st.markdown("Zadejte váš **očekávaný/cílový hrubý roční obrat**, pokud byste pracoval(a) všechny plánované dny.")
col_ico_input_type, col_ico_input_value = st.columns([1,2])
with col_ico_input_type:
    ico_input_period = st.selectbox("Zadat příjem IČO jako:", ("Roční obrat", "Měsíční fakturace", "Denní sazba (man-day rate)"), index=1, key="ico_input_period_select") # Default to Monthly
with col_ico_input_value:
    if ico_input_period == "Roční obrat":
        ico_input_value_annual = st.number_input("Cílový hrubý roční obrat (IČO)", value=1200000.0, min_value=0.0, step=10000.0, format="%.0f", key="ico_revenue_annual_input", help="Celkový roční příjem před odečtením jakýchkoli výdajů, pokud byste pracoval(a) všechny plánované dny.")
        ico_potential_gross_annual_revenue = ico_input_value_annual # This is the potential revenue
    elif ico_input_period == "Měsíční fakturace":
        ico_monthly_billing = st.number_input("Cílová průměrná měsíční fakturace (IČO)", value=100000.0, min_value=0.0, step=1000.0, format="%.0f", key="ico_revenue_monthly_input", help="Průměrná částka, kterou cílíte fakturovat za měsíc, pokud byste pracoval(a) všechny plánované dny.")
        ico_potential_gross_annual_revenue = ico_monthly_billing * 12
    elif ico_input_period == "Denní sazba (man-day rate)":
        ico_daily_rate = st.number_input("Vaše denní sazba (man-day rate)", value=5000.0, min_value=0.0, step=100.0, format="%.0f", key="ico_daily_rate_input")
        ico_mandays_per_year = st.number_input("Plánovaný počet fakturovaných člověkodní za rok", value=DEFAULT_MANDAYS_PER_YEAR_ICO, min_value=0, max_value=work_days_per_year_input, step=1, key="ico_mandays_input", help=f"Kolik dní v roce plánujete fakturovat. Max: {work_days_per_year_input} (dle globálního nastavení).")
        ico_potential_gross_annual_revenue = ico_daily_rate * ico_mandays_per_year
    else: 
        ico_potential_gross_annual_revenue = 0.0

st.markdown(f"**Cílový roční obrat IČO (před zohledněním neplaceného volna): {ico_potential_gross_annual_revenue:,.0f} CZK**")

# --- Společná nastavení pro IČO - Optimalizace dnů ---
st.subheader("Optimalizace dnů IČO")
st.markdown("Tyto dny ovlivní váš **skutečný obrat** a **efektivní denní sazbu**.")
col1_days_ico, col2_days_ico = st.columns(2) 
with col1_days_ico:
    # Removed 'paid_by_client' days from this section to simplify the "lost potential" calculation
    # They are complex to factor into a simple reduction of potential revenue if revenue is already a target.
    # Their main impact is on the daily rate of *achieved* revenue.
    ico_unpaid_vacation = st.number_input("Vaše skutečná neplacená dovolená (dny)", value=20, min_value=0, max_value=work_days_per_year_input, step=1, key="ico_unpaid_vac_user_days_common", help="Dny, kdy si berete volno a nefakturujete. Snižuje váš skutečný obrat a počet dní, na které se rozpočítává čistý příjem.")
with col2_days_ico:
    ico_unpaid_sick = st.number_input("Vaše skutečné neplacené dny nemoci (dny)", value=5, min_value=0, max_value=work_days_per_year_input, step=1, key="ico_unpaid_sick_user_days_common", help="Dny, kdy jste nemocní a nefakturujete. Snižuje váš skutečný obrat a počet dní pro efektivní sazbu.")

# Calculate the revenue adjusted for unpaid days BEFORE specific IČO mode settings
days_not_earning = ico_unpaid_vacation + ico_unpaid_sick
earning_days_ratio = max(0, work_days_per_year_input - days_not_earning) / work_days_per_year_input if work_days_per_year_input > 0 else 0
ico_revenue_adjusted_for_unpaid_days = ico_potential_gross_annual_revenue * earning_days_ratio

st.markdown(f"**Skutečný roční obrat IČO (po zohlednění neplaceného volna): {ico_revenue_adjusted_for_unpaid_days:,.0f} CZK**")


ico_calculation_mode = st.radio("Režim výpočtu odvodů pro IČO:", 
                                ("Paušální výdaje", "Paušální daň"), 
                                key="ico_mode", horizontal=True, help="Zvolte, zda chcete počítat s procentuálními paušálními výdaji nebo se zjednodušenou paušální daní.")

# --- Nastavení specifická pro režim IČO ---
if ico_calculation_mode == "Paušální výdaje":
    st.subheader("Nastavení pro IČO - Paušální výdaje")
    col1_ico_pv, col2_ico_pv = st.columns(2)
    with col1_ico_pv:
        # Dynamic max expense display in format_func
        current_revenue_for_expense_display = ico_revenue_adjusted_for_unpaid_days # Use adjusted revenue for this display
        ico_expense_percentage = st.selectbox("Procento paušálních výdajů", (0.60, 0.40, 0.80, 0.30), 
                                            format_func=lambda x: f"{int(x*100)}% (max. {min(2000000, current_revenue_for_expense_display if current_revenue_for_expense_display else 0)*x:,.0f} Kč výdajů)", 
                                            key="ico_expense_perc", 
                                            help="60% pro většinu živností, 40% pro některá svobodná povolání, 80% pro řemesla a zemědělství.")
        ico_realne_rocni_naklady = st.number_input("Reálné roční provozní náklady (IČO)", value=60000.0, min_value=0.0, step=1000.0, format="%.0f", key="ico_real_costs", help="Vaše skutečné náklady na podnikání (software, nájem, telefon atd.). Používá se pro výpočet 'disponibilního' čistého příjmu, který vám reálně zbyde.")
    with col2_ico_pv:
        ico_participate_sickness = st.checkbox("Účastnit se dobrovolného nemocenského pojištění OSVČ?", value=False, key="ico_sickness_insurance", help="Poskytuje nárok na nemocenskou dávku v případě pracovní neschopnosti.")
        ico_sickness_base = 0.0 
        if ico_participate_sickness:
            ico_sickness_base = st.number_input("Měsíční vyměřovací základ pro nemocenské", value=float(MIN_ICO_SICKNESS_ASSESSMENT_BASE_MONTHLY_2024), min_value=float(MIN_ICO_SICKNESS_ASSESSMENT_BASE_MONTHLY_2024), step=100.0, format="%.0f", key="ico_sickness_base", help=f"Minimálně {MIN_ICO_SICKNESS_ASSESSMENT_BASE_MONTHLY_2024:,.0f} CZK. Ovlivňuje výši případné nemocenské dávky.")

elif ico_calculation_mode == "Paušální daň":
    st.subheader("Nastavení pro IČO - Paušální daň")
    ico_pausalni_dan_band = st.selectbox("Pásmo paušální daně", (1, 2, 3), key="ico_pausal_band", help="Výběr pásma závisí na výši a charakteru vašich příjmů. Ověřte si podmínky.")
    
    band_descriptions = {
        1: f"**1. pásmo (cca {PAUSALNI_DAN_BAND_1_MONTHLY_2024:,.0f} Kč/měs.):** Pro OSVČ s ročními příjmy do 1 mil. Kč (bez ohledu na typ výdajového paušálu, který by jinak uplatnily), NEBO do 1,5 mil. Kč, pokud alespoň 75 % jejich příjmů by spadalo pod 80% nebo 60% výdajový paušál, NEBO do 2 mil. Kč, pokud alespoň 75 % příjmů by spadalo pod 80% výdajový paušál.",
        2: f"**2. pásmo (cca {PAUSALNI_DAN_BAND_2_MONTHLY_2024:,.0f} Kč/měs.):** Pro OSVČ s ročními příjmy do 1,5 mil. Kč (pokud nesplňují podmínky pro 1. pásmo při tomto příjmu), NEBO do 2 mil. Kč, pokud alespoň 75 % jejich příjmů by spadalo pod 80% nebo 60% výdajový paušál.",
        3: f"**3. pásmo (cca {PAUSALNI_DAN_BAND_3_MONTHLY_2024:,.0f} Kč/měs.):** Pro OSVČ s ročními příjmy do 2 mil. Kč (pokud nesplňují podmínky pro 1. nebo 2. pásmo při tomto příjmu)."
    }
    st.info(band_descriptions.get(ico_pausalni_dan_band, "Zvolte pásmo pro zobrazení popisu."))
    st.markdown("Podmínkou pro paušální daň je také nebýt plátcem DPH (a další specifické podmínky).")


# --- Tlačítko pro výpočet a zobrazení výsledků ---
if st.button("📊 Spočítat a porovnat", type="primary", use_container_width=True):
    results_hpp = {}
    # This will store results based on revenue_adjusted_for_unpaid_days
    results_ico_adjusted = {} 

    # Výpočet HPP
    if hpp_gross_monthly_income >= 0: 
        results_hpp = calculate_hpp_income(
            gross_monthly_income=hpp_gross_monthly_income,
            other_annual_tax_credits=other_annual_tax_credits_input,
            work_days_per_year_input=work_days_per_year_input
        )
    
    # Výpočet IČO (použije se revenue_adjusted_for_unpaid_days)
    if ico_revenue_adjusted_for_unpaid_days >= 0: 
        if ico_calculation_mode == "Paušální výdaje":
            sickness_base_to_pass = ico_sickness_base if ico_participate_sickness else 0.0
            results_ico_adjusted = calculate_ico_pausalni_vydaje_income(
                gross_annual_revenue=ico_revenue_adjusted_for_unpaid_days, # Use adjusted revenue
                expense_percentage=ico_expense_percentage,
                realne_rocni_provozni_naklady=ico_realne_rocni_naklady,
                other_annual_tax_credits=other_annual_tax_credits_input,
                participate_sickness_insurance=ico_participate_sickness,
                sickness_insurance_assessment_base_monthly=sickness_base_to_pass,
                # For this "true net" calculation, paid_by_client days are less relevant as we reduced gross revenue
                actual_unpaid_vacation_days_taken=ico_unpaid_vacation, 
                actual_unpaid_sick_days_taken=ico_unpaid_sick,
                work_days_per_year_input=work_days_per_year_input 
            )
        elif ico_calculation_mode == "Paušální daň":
            results_ico_adjusted = calculate_ico_pausalni_dan_income(
                gross_annual_revenue=ico_revenue_adjusted_for_unpaid_days, # Use adjusted revenue
                pausalni_dan_band=ico_pausalni_dan_band,
                actual_unpaid_vacation_days_taken=ico_unpaid_vacation, 
                actual_unpaid_sick_days_taken=ico_unpaid_sick,       
                work_days_per_year_input=work_days_per_year_input
            )
    
    # --- Zobrazení výsledků ---
    st.divider()
    st.header("📈 Výsledky porovnání")

    col_hpp_res, col_ico_res = st.columns(2)

    with col_hpp_res:
        st.subheader("HPP (Zaměstnanec)")
        if results_hpp and "error" not in results_hpp:
            st.metric("Čistý měsíční příjem (HPP)", f"{results_hpp.get('cisty_mesicni_prijem_zamestnanec', 0):,.0f} CZK")
            # ... (ostatní HPP detaily jako dříve) ...
            st.markdown(f"**Hrubá měsíční mzda:** {results_hpp.get('hruby_mesicni_prijem', 0):,.0f} CZK")
            st.markdown(f"**Roční čistý příjem:** {results_hpp.get('cisty_rocni_prijem_zamestnanec', 0):,.0f} CZK")
            st.markdown(f"**Denní čistý příjem (průměr):** {results_hpp.get('cisty_denni_prijem_zamestnanec', 0):,.0f} CZK ({work_days_per_year_input} prac. dní)")
            with st.expander("Více detailů pro HPP"):
                st.write(f"Roční ZP (zaměstnanec): {results_hpp.get('zamestnanec_rocni_zdravotni_pojisteni', 0):,.0f} CZK")
                st.write(f"Roční SP (zaměstnanec): {results_hpp.get('zamestnanec_rocni_socialni_pojisteni', 0):,.0f} CZK")
                st.write(f"Roční daň z příjmů: {results_hpp.get('zamestnanec_konecna_rocni_dan_z_prijmu', 0):,.0f} CZK")
                st.markdown("---")
                st.write(f"**Celkové měsíční náklady zaměstnavatele:** {results_hpp.get('zamestnavatel_celkove_mesicni_naklady_na_zamestnance', 0):,.0f} CZK")
                st.write(f"**Celkové roční náklady zaměstnavatele:** {results_hpp.get('zamestnavatel_celkove_rocni_naklady_na_zamestnance', 0):,.0f} CZK")

        elif results_hpp and "error" in results_hpp : 
            st.error(f"Chyba HPP: {results_hpp['error']}")
        elif hpp_gross_monthly_income <= 0 and st.session_state.get("calculate_button_clicked", False):
             st.info("Zadejte kladnou hrubou mzdu pro HPP.")
        
            
    with col_ico_res:
        st.subheader(f"IČO (OSVČ) - {ico_calculation_mode}")
        # Display results based on revenue_adjusted_for_unpaid_days
        if results_ico_adjusted and "error" not in results_ico_adjusted:
            main_ico_metric_label = "Skutečný čistý měsíční příjem (IČO)"
            main_ico_metric_value = 0
            daily_ico_metric_label = "Skutečný čistý denní příjem (IČO - efektivní)"
            daily_ico_metric_value = 0
            
            if ico_calculation_mode == "Paušální výdaje":
                main_ico_metric_value = results_ico_adjusted.get('info_k_realnym_nakladum', {}).get('cisty_mesicni_prijem_disponibilni_po_realnych_nakladech', 0)
                daily_ico_metric_value = results_ico_adjusted.get('info_k_realnym_nakladum', {}).get('cisty_denni_prijem_disponibilni_efektivni', 0)
            elif ico_calculation_mode == "Paušální daň":
                main_ico_metric_value = results_ico_adjusted.get('cisty_mesicni_prijem', 0)
                daily_ico_metric_value = results_ico_adjusted.get('cisty_denni_prijem_efektivni', 0)

            st.metric(main_ico_metric_label, f"{main_ico_metric_value:,.0f} CZK", help="Čistý příjem po zaplacení odvodů, vypočítaný z obratu sníženého o neplacené volno.")
            st.markdown(f"**Cílový roční obrat (před úpravou):** {ico_potential_gross_annual_revenue:,.0f} CZK")
            st.markdown(f"**Skutečný roční obrat (po úpravě o neplac. volno):** {results_ico_adjusted.get('hruby_rocni_prijem_obrat',0):,.0f} CZK")
            st.markdown(f"**{daily_ico_metric_label}:** {daily_ico_metric_value:,.0f} CZK ({results_ico_adjusted.get('info_k_efektivite_dnu', {}).get('uvazovane_pracovni_dny_pro_denni_sazbu', 'N/A')} prac. dní)")
            
            with st.expander(f"Více detailů pro IČO ({ico_calculation_mode} - po úpravě obratu)"):
                if ico_calculation_mode == "Paušální výdaje":
                    st.write(f"Roční SP: {results_ico_adjusted.get('rocni_socialni_pojisteni', 0):,.0f} CZK")
                    st.write(f"Roční ZP: {results_ico_adjusted.get('rocni_zdravotni_pojisteni', 0):,.0f} CZK")
                    st.write(f"Roční NP: {results_ico_adjusted.get('rocni_nemocenske_pojisteni', 0):,.0f} CZK")
                    st.write(f"Roční daň: {results_ico_adjusted.get('konecna_rocni_dan_z_prijmu', 0):,.0f} CZK")
                    st.write(f"Zisk pro daň. účely: {results_ico_adjusted.get('zisk_pro_danove_ucely', 0):,.0f} CZK")
                    st.write(f"Reálné roční náklady: {results_ico_adjusted.get('info_k_realnym_nakladum', {}).get('vstup_realne_rocni_provozni_naklady', 0):,.0f} CZK")
                elif ico_calculation_mode == "Paušální daň":
                    st.write(f"Zvolené pásmo: {results_ico_adjusted.get('zvolene_pasmo_pausalni_dane', 'N/A')}")
                    st.write(f"Měsíční platba paušální daně: {results_ico_adjusted.get('mesicni_platba_pausalni_dane', 0):,.0f} CZK")
                st.write(f"Efektivní pracovní dny: {results_ico_adjusted.get('info_k_efektivite_dnu', {}).get('uvazovane_pracovni_dny_pro_denni_sazbu', 'N/A')}")

        elif results_ico_adjusted and "error" in results_ico_adjusted: 
            st.error(f"Chyba IČO: {results_ico_adjusted['error']}")
        elif ico_potential_gross_annual_revenue <= 0 and st.session_state.get("calculate_button_clicked", False):
            st.info("Zadejte kladný cílový obrat pro IČO.")


    # --- Grafické srovnání ---
    if results_hpp and "error" not in results_hpp and results_ico_adjusted and "error" not in results_ico_adjusted:
        st.divider()
        st.subheader("📊 Grafické srovnání čistých měsíčních příjmů")
        
        hpp_net_monthly = results_hpp.get('cisty_mesicni_prijem_zamestnanec', 0)
        
        ico_net_monthly_adjusted = 0
        if ico_calculation_mode == "Paušální výdaje":
            info_realne_naklady = results_ico_adjusted.get('info_k_realnym_nakladum', {})
            if isinstance(info_realne_naklady, dict):
                 ico_net_monthly_adjusted = info_realne_naklady.get('cisty_mesicni_prijem_disponibilni_po_realnych_nakladech', 0)
        elif ico_calculation_mode == "Paušální daň":
            ico_net_monthly_adjusted = results_ico_adjusted.get('cisty_mesicni_prijem', 0)
            
        chart_data_list = [
            {"Typ příjmu": "HPP", "Čistý měsíční příjem (CZK)": hpp_net_monthly},
            # For the graph, we show the "true clear income" after unpaid days adjustment
            {"Typ příjmu": f"IČO ({ico_calculation_mode}) - Skutečný", "Čistý měsíční příjem (CZK)": ico_net_monthly_adjusted}
        ]
        
        try:
            import pandas as pd
            df_chart = pd.DataFrame(chart_data_list)
            st.bar_chart(df_chart.set_index("Typ příjmu"))
        except ImportError: 
            st.bar_chart(chart_data_list, x="Typ příjmu", y="Čistý měsíční příjem (CZK)")


    elif (results_hpp and "error" in results_hpp) or (results_ico_adjusted and "error" in results_ico_adjusted):
        st.warning("Opravte prosím chyby ve vstupech pro zobrazení grafu.")
    
    st.session_state.calculate_button_clicked = True


if "calculate_button_clicked" not in st.session_state:
    st.session_state.calculate_button_clicked = False

st.markdown("---")
st.caption("Data a výpočty jsou platné pro rok 2024 a mají pouze orientační charakter. Pro přesné finanční plánování a daňové poradenství se vždy obraťte na kvalifikovaného daňového poradce.")

# --- Footer ---
st.markdown("---")
st.markdown("Vytvořeno pro šišku ❤️")

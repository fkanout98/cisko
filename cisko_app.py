import streamlit as st
import json # For potential debugging or displaying raw dicts, not primary for UI

# --- Streamlit App UI ---
# THIS MUST BE THE FIRST STREAMLIT COMMAND if used.
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

# --- Calculation Functions (Copied and adapted from python_income_calculator_2024_v3) ---
def calculate_hpp_income(
    gross_monthly_income: float, 
    other_annual_tax_credits: float = 0.0,
    work_days_per_year_input: int = DEFAULT_WORK_DAYS_PER_YEAR
) -> dict:
    gross_annual_income = gross_monthly_income * 12
    if gross_annual_income <= 0:
        return {"error": "Hrubý roční příjem musí být kladný."}

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
    net_monthly_income = net_annual_income / 12 if gross_annual_income > 0 else 0 # Avoid division by zero if income is zero
    net_daily_income = net_annual_income / work_days_per_year_input if work_days_per_year_input > 0 and gross_annual_income > 0 else 0


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
    if gross_annual_revenue <= 0:
        return {"error": "Hrubý roční příjem (obrat) musí být kladný."}

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
    net_monthly_income_tax_method = net_annual_income_tax_method / 12 if gross_annual_revenue > 0 else 0
    total_annual_deductions_tax_method = annual_social_security + annual_health_insurance + annual_sickness_insurance + final_income_tax
    net_annual_disposable_income = gross_annual_revenue - realne_rocni_provozni_naklady - total_annual_deductions_tax_method
    net_monthly_disposable_income = net_annual_disposable_income / 12 if gross_annual_revenue > 0 else 0
    effective_work_days_for_rate = work_days_per_year_input - actual_unpaid_vacation_days_taken - actual_unpaid_sick_days_taken
    net_daily_income_tax_method_effective = net_annual_income_tax_method / effective_work_days_for_rate if effective_work_days_for_rate > 0 and gross_annual_revenue > 0 else 0
    net_daily_disposable_income_effective = net_annual_disposable_income / effective_work_days_for_rate if effective_work_days_for_rate > 0 and gross_annual_revenue > 0 else 0

    return {
        "typ": "IČO (Paušální výdaje)", "rok_kalkulace": 2024,
        "hruby_rocni_prijem_obrat": round(gross_annual_revenue, 2),
        "hruby_mesicni_prijem_obrat_prumer": round(gross_annual_revenue / 12 if gross_annual_revenue > 0 else 0, 2),
        "procento_pausalnich_vydaju": expense_percentage,
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
        "info_k_efektivite_dnu": {
            "uvazovane_pracovni_dny_pro_denni_sazbu": effective_work_days_for_rate if effective_work_days_for_rate > 0 else work_days_per_year_input
        }
    }

def calculate_ico_pausalni_dan_income(
    gross_annual_revenue: float,
    pausalni_dan_band: int,
    work_days_per_year_input: int = DEFAULT_WORK_DAYS_PER_YEAR
) -> dict:
    if gross_annual_revenue <= 0: return {"error": "Hrubý roční příjem (obrat) musí být kladný."}
    if gross_annual_revenue > PAUSALNI_DAN_MAX_REVENUE_2024: 
        return {"error": f"Příjem přesahuje limit {PAUSALNI_DAN_MAX_REVENUE_2024:,.0f} CZK pro paušální daň."}
    monthly_payment = 0
    if pausalni_dan_band == 1: monthly_payment = PAUSALNI_DAN_BAND_1_MONTHLY_2024
    elif pausalni_dan_band == 2: monthly_payment = PAUSALNI_DAN_BAND_2_MONTHLY_2024
    elif pausalni_dan_band == 3: monthly_payment = PAUSALNI_DAN_BAND_3_MONTHLY_2024
    else: return {"error": "Neplatné pásmo paušální daně."}
    
    annual_pausalni_dan_payment = monthly_payment * 12
    net_annual_income = gross_annual_revenue - annual_pausalni_dan_payment
    net_monthly_income = net_annual_income / 12 if gross_annual_revenue > 0 else 0
    net_daily_income = net_annual_income / work_days_per_year_input if work_days_per_year_input > 0 and gross_annual_revenue > 0 else 0

    return {
        "typ": "IČO (Paušální daň)", "rok_kalkulace": 2024,
        "hruby_rocni_prijem_obrat": round(gross_annual_revenue, 2),
        "hruby_mesicni_prijem_obrat_prumer": round(gross_annual_revenue / 12 if gross_annual_revenue > 0 else 0, 2),
        "zvolene_pasmo_pausalni_dane": pausalni_dan_band,
        "mesicni_platba_pausalni_dane": round(monthly_payment, 2),
        "cisty_rocni_prijem": round(net_annual_income, 2),
        "cisty_mesicni_prijem": round(net_monthly_income, 2),
        "cisty_denni_prijem_prumer": round(net_daily_income, 2)
    }

# --- Streamlit App UI ---
st.title("CISKO - Čistý Srovnávací Kalkulátor Osoby (pro rok 2024)")
st.caption("Porovnání příjmů HPP vs. IČO v České republice. Výpočty jsou orientační, konzultujte s daňovým poradcem.")

# --- Globální nastavení ---
with st.sidebar.expander("⚙️ Globální nastavení", expanded=True):
    work_days_per_year_input = st.number_input("Počet pracovních dní v roce", min_value=200, max_value=300, value=DEFAULT_WORK_DAYS_PER_YEAR, step=1, help="Používá se pro výpočet denních sazeb. Obvykle cca 250-252 dní.", key="global_work_days")
    other_annual_tax_credits_input = st.number_input("Jiné roční slevy na dani", value=0.0, min_value=0.0, step=100.0, format="%.2f", key="global_other_credits", help="Např. na děti, manželku/manžela bez vlastních příjmů, školkovné, úroky z hypotéky. Základní sleva na poplatníka je již zahrnuta automaticky.")

# --- Scénář 1: HPP (Zaměstnanec) ---
st.header("👤 Scénář 1: HPP (Zaměstnanec)")
hpp_gross_monthly_income = st.number_input("Hrubá měsíční mzda (HPP)", value=50000.0, min_value=0.0, step=1000.0, format="%.0f", key="hpp_gross", help="Zadejte vaši hrubou měsíční mzdu.")

# --- Scénář 2: IČO (OSVČ) ---
st.header("💼 Scénář 2: IČO (OSVČ)")

col_ico_input_type, col_ico_input_value = st.columns([1,2])
with col_ico_input_type:
    ico_input_period = st.selectbox("Zadat příjem IČO jako:", ("Roční obrat", "Měsíční fakturace", "Denní sazba (man-day rate)"), key="ico_input_period_select")
with col_ico_input_value:
    if ico_input_period == "Roční obrat":
        ico_input_value = st.number_input("Hrubý roční příjem/obrat (IČO)", value=1200000.0, min_value=0.0, step=10000.0, format="%.0f", key="ico_revenue_annual_input", help="Celkový roční příjem před odečtením jakýchkoli výdajů.")
        ico_gross_annual_revenue = ico_input_value
    elif ico_input_period == "Měsíční fakturace":
        ico_monthly_billing = st.number_input("Průměrná měsíční fakturace (IČO)", value=100000.0, min_value=0.0, step=1000.0, format="%.0f", key="ico_revenue_monthly_input", help="Průměrná částka, kterou fakturujete za měsíc.")
        ico_gross_annual_revenue = ico_monthly_billing * 12
    elif ico_input_period == "Denní sazba (man-day rate)":
        ico_daily_rate = st.number_input("Vaše denní sazba (man-day rate)", value=5000.0, min_value=0.0, step=100.0, format="%.0f", key="ico_daily_rate_input")
        ico_mandays_per_year = st.number_input("Počet fakturovaných člověkodní za rok", value=DEFAULT_MANDAYS_PER_YEAR_ICO, min_value=0, max_value=work_days_per_year_input, step=1, key="ico_mandays_input", help=f"Kolik dní v roce průměrně fakturujete. Max: {work_days_per_year_input} (dle globálního nastavení).")
        ico_gross_annual_revenue = ico_daily_rate * ico_mandays_per_year

st.markdown(f"**Celkový předpokládaný roční obrat IČO: {ico_gross_annual_revenue:,.0f} CZK**")


ico_calculation_mode = st.radio("Režim výpočtu odvodů pro IČO:", 
                                ("Paušální výdaje", "Paušální daň"), 
                                key="ico_mode", horizontal=True, help="Zvolte, zda chcete počítat s procentuálními paušálními výdaji nebo se zjednodušenou paušální daní.")

# Sub-options for IČO Paušální výdaje
if ico_calculation_mode == "Paušální výdaje":
    st.subheader("Nastavení pro IČO - Paušální výdaje")
    col1_ico_pv, col2_ico_pv = st.columns(2)
    with col1_ico_pv:
        ico_expense_percentage = st.selectbox("Procento paušálních výdajů", (0.60, 0.40, 0.80, 0.30), format_func=lambda x: f"{int(x*100)}% (max. {2000000*x:,.0f} Kč výdajů z 2M Kč obratu)", key="ico_expense_perc", help="60% pro většinu živností, 40% pro některá svobodná povolání, 80% pro řemesla a zemědělství.")
        ico_realne_rocni_naklady = st.number_input("Reálné roční provozní náklady (IČO)", value=60000.0, min_value=0.0, step=1000.0, format="%.0f", key="ico_real_costs", help="Vaše skutečné náklady na podnikání (software, nájem, telefon atd.). Používá se pro výpočet 'disponibilního' čistého příjmu, který vám reálně zbyde.")
    with col2_ico_pv:
        ico_participate_sickness = st.checkbox("Účastnit se dobrovolného nemocenského pojištění OSVČ?", value=False, key="ico_sickness_insurance", help="Poskytuje nárok na nemocenskou dávku v případě pracovní neschopnosti.")
        ico_sickness_base = 0.0 
        if ico_participate_sickness:
            ico_sickness_base = st.number_input("Měsíční vyměřovací základ pro nemocenské", value=float(MIN_ICO_SICKNESS_ASSESSMENT_BASE_MONTHLY_2024), min_value=float(MIN_ICO_SICKNESS_ASSESSMENT_BASE_MONTHLY_2024), step=100.0, format="%.0f", key="ico_sickness_base", help=f"Minimálně {MIN_ICO_SICKNESS_ASSESSMENT_BASE_MONTHLY_2024:,.0f} CZK. Ovlivňuje výši případné nemocenské dávky.")

    st.markdown("###### Optimalizace dnů (pro výpočet efektivní denní sazby):")
    col1_days, col2_days = st.columns(2) 
    with col1_days:
        ico_paid_vacation_client = st.number_input("Dovolená 'placená' klientem (dny)", value=0, min_value=0, step=1, key="ico_paid_vac_client_days", help="Dny, za které vám klient fakticky zaplatí, i když nepracujete (pokud máte takovou dohodu).")
        ico_unpaid_vacation = st.number_input("Vaše skutečná neplacená dovolená (dny)", value=20, min_value=0, step=1, key="ico_unpaid_vac_user_days", help="Dny, kdy si berete volno a nefakturujete.")
    with col2_days:
        ico_paid_sick_client = st.number_input("Nemoc 'placená' klientem (dny)", value=0, min_value=0, step=1, key="ico_paid_sick_client_days", help="Dny nemoci, za které vám klient fakticky zaplatí (pokud máte takovou dohodu).")
        ico_unpaid_sick = st.number_input("Vaše skutečné neplacené dny nemoci (dny)", value=5, min_value=0, step=1, key="ico_unpaid_sick_user_days", help="Dny, kdy jste nemocní a nefakturujete (a nemáte placeno od klienta).")

# Sub-options for IČO Paušální daň
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
    results_ico = {}

    # Výpočet HPP
    if hpp_gross_monthly_income >= 0: # Allow zero for calculation, error handled in function
        results_hpp = calculate_hpp_income(
            gross_monthly_income=hpp_gross_monthly_income,
            other_annual_tax_credits=other_annual_tax_credits_input,
            work_days_per_year_input=work_days_per_year_input
        )
    # No explicit warning here, function handles zero input by returning error or zeroed values

    # Výpočet IČO
    if ico_gross_annual_revenue >= 0: # Allow zero for calculation
        if ico_calculation_mode == "Paušální výdaje":
            sickness_base_to_pass = ico_sickness_base if ico_participate_sickness else 0.0
            results_ico = calculate_ico_pausalni_vydaje_income(
                gross_annual_revenue=ico_gross_annual_revenue,
                expense_percentage=ico_expense_percentage,
                realne_rocni_provozni_naklady=ico_realne_rocni_naklady,
                other_annual_tax_credits=other_annual_tax_credits_input,
                participate_sickness_insurance=ico_participate_sickness,
                sickness_insurance_assessment_base_monthly=sickness_base_to_pass,
                paid_vacation_days_by_client=ico_paid_vacation_client,
                paid_sick_days_by_client=ico_paid_sick_client,
                actual_unpaid_vacation_days_taken=ico_unpaid_vacation,
                actual_unpaid_sick_days_taken=ico_unpaid_sick,
                work_days_per_year_input=work_days_per_year_input
            )
        elif ico_calculation_mode == "Paušální daň":
            results_ico = calculate_ico_pausalni_dan_income(
                gross_annual_revenue=ico_gross_annual_revenue,
                pausalni_dan_band=ico_pausalni_dan_band,
                work_days_per_year_input=work_days_per_year_input
            )
    # No explicit warning here

    # --- Zobrazení výsledků ---
    st.divider()
    st.header("📈 Výsledky porovnání")

    col_hpp, col_ico = st.columns(2)

    with col_hpp:
        st.subheader("HPP (Zaměstnanec)")
        if results_hpp and "error" not in results_hpp:
            st.metric("Čistý měsíční příjem (HPP)", f"{results_hpp.get('cisty_mesicni_prijem_zamestnanec', 0):,.0f} CZK")
            st.markdown(f"**Hrubá měsíční mzda:** {results_hpp.get('hruby_mesicni_prijem', 0):,.0f} CZK")
            st.markdown(f"**Roční čistý příjem:** {results_hpp.get('cisty_rocni_prijem_zamestnanec', 0):,.0f} CZK")
            st.markdown(f"**Denní čistý příjem (průměr):** {results_hpp.get('cisty_denni_prijem_zamestnanec', 0):,.0f} CZK")
            with st.expander("Více detailů pro HPP"):
                st.write(f"Roční zdravotní pojištění (zaměstnanec): {results_hpp.get('zamestnanec_rocni_zdravotni_pojisteni', 0):,.0f} CZK")
                st.write(f"Roční sociální pojištění (zaměstnanec): {results_hpp.get('zamestnanec_rocni_socialni_pojisteni', 0):,.0f} CZK")
                st.write(f"Roční daň z příjmů (po slevách): {results_hpp.get('zamestnanec_konecna_rocni_dan_z_prijmu', 0):,.0f} CZK")
                st.markdown("---")
                st.write(f"**Celkové měsíční náklady zaměstnavatele:** {results_hpp.get('zamestnavatel_celkove_mesicni_naklady_na_zamestnance', 0):,.0f} CZK")
                st.write(f"**Celkové roční náklady zaměstnavatele:** {results_hpp.get('zamestnavatel_celkove_rocni_naklady_na_zamestnance', 0):,.0f} CZK")
        elif results_hpp and "error" in results_hpp : 
            st.error(f"Chyba HPP: {results_hpp['error']}")
        else:
            st.info("Výsledky pro HPP se zobrazí po zadání vstupů a kliknutí na 'Spočítat'.")
            
    with col_ico:
        st.subheader(f"IČO (OSVČ) - {ico_calculation_mode}")
        if results_ico and "error" not in results_ico:
            if ico_calculation_mode == "Paušální výdaje":
                st.metric("Čistý měsíční příjem (IČO - disponibilní)", f"{results_ico.get('info_k_realnym_nakladum', {}).get('cisty_mesicni_prijem_disponibilni_po_realnych_nakladech', 0):,.0f} CZK", help="Příjem po zaplacení odvodů (počítaných dle paušálu) a po odečtení vašich reálných provozních nákladů.")
                st.markdown(f"**Průměrný hrubý měsíční obrat:** {results_ico.get('hruby_mesicni_prijem_obrat_prumer', 0):,.0f} CZK")
                st.markdown(f"**Denní čistý příjem (disponibilní, efektivní):** {results_ico.get('info_k_realnym_nakladum', {}).get('cisty_denni_prijem_disponibilni_efektivni', 0):,.0f} CZK")
                
                with st.expander("Více detailů pro IČO (Paušální výdaje)"):
                    st.write(f"Roční sociální pojištění: {results_ico.get('rocni_socialni_pojisteni', 0):,.0f} CZK")
                    st.write(f"Roční zdravotní pojištění: {results_ico.get('rocni_zdravotni_pojisteni', 0):,.0f} CZK")
                    st.write(f"Roční nemocenské pojištění (pokud sjednáno): {results_ico.get('rocni_nemocenske_pojisteni', 0):,.0f} CZK")
                    st.write(f"Roční daň z příjmů (po slevách): {results_ico.get('konecna_rocni_dan_z_prijmu', 0):,.0f} CZK")
                    st.markdown("---")
                    st.write(f"**Čistý měsíční příjem (dle daňové metody pauš. výdajů):** {results_ico.get('cisty_mesicni_prijem_dle_pausalu', 0):,.0f} CZK")
                    st.write(f"Roční paušální výdaje pro daňové účely: {results_ico.get('rocni_pausalni_vydaje_pro_dane', 0):,.0f} CZK")
                    st.write(f"Zadané reálné roční provozní náklady: {results_ico.get('info_k_realnym_nakladum', {}).get('vstup_realne_rocni_provozni_naklady', 0):,.0f} CZK")
            
            elif ico_calculation_mode == "Paušální daň":
                st.metric("Čistý měsíční příjem (IČO)", f"{results_ico.get('cisty_mesicni_prijem', 0):,.0f} CZK")
                st.markdown(f"**Průměrný hrubý měsíční obrat:** {results_ico.get('hruby_mesicni_prijem_obrat_prumer', 0):,.0f} CZK")
                st.markdown(f"**Denní čistý příjem (průměr):** {results_ico.get('cisty_denni_prijem_prumer', 0):,.0f} CZK")
                with st.expander("Více detailů pro IČO (Paušální daň)"):
                    st.write(f"Zvolené pásmo: {results_ico.get('zvolene_pasmo_pausalni_dane', 'N/A')}")
                    st.write(f"Měsíční platba paušální daně: {results_ico.get('mesicni_platba_pausalni_dane', 0):,.0f} CZK")

        elif results_ico and "error" in results_ico: 
            st.error(f"Chyba IČO: {results_ico['error']}")
        else:
            st.info("Výsledky pro IČO se zobrazí po zadání vstupů a kliknutí na 'Spočítat'.")

    # --- Grafické srovnání ---
    if results_hpp and "error" not in results_hpp and results_ico and "error" not in results_ico:
        st.divider()
        st.subheader("📊 Grafické srovnání čistých měsíčních příjmů")
        
        hpp_net_monthly = results_hpp.get('cisty_mesicni_prijem_zamestnanec', 0)
        
        ico_net_monthly = 0
        if ico_calculation_mode == "Paušální výdaje":
            info_realne_naklady = results_ico.get('info_k_realnym_nakladum', {})
            if isinstance(info_realne_naklady, dict):
                 ico_net_monthly = info_realne_naklady.get('cisty_mesicni_prijem_disponibilni_po_realnych_nakladech', 0)
        elif ico_calculation_mode == "Paušální daň":
            ico_net_monthly = results_ico.get('cisty_mesicni_prijem', 0)
            
        # Prepare data for bar chart
        chart_data_list = [
            {"Typ příjmu": "HPP", "Čistý měsíční příjem (CZK)": hpp_net_monthly},
            {"Typ příjmu": f"IČO ({ico_calculation_mode})", "Čistý měsíční příjem (CZK)": ico_net_monthly}
        ]
        
        try:
            import pandas as pd
            df_chart = pd.DataFrame(chart_data_list)
            st.bar_chart(df_chart.set_index("Typ příjmu"))
        except ImportError: # Fallback if pandas is not available
            st.bar_chart(chart_data_list, x="Typ příjmu", y="Čistý měsíční příjem (CZK)")


    elif (results_hpp and "error" in results_hpp) or (results_ico and "error" in results_ico):
        st.warning("Opravte prosím chyby ve vstupech pro zobrazení grafu.")
    
    st.markdown("---")
    st.caption("Data a výpočty jsou platné pro rok 2024 a mají pouze orientační charakter. Pro přesné finanční plánování a daňové poradenství se vždy obraťte na kvalifikovaného daňového poradce.")

# --- Footer ---
st.markdown("---")
st.markdown("Vytvořeno pro šišku ❤️")

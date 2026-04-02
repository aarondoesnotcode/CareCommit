import re

import streamlit as st
from google import genai
from google.cloud import secretmanager
import requests


BASE_URL = "http://localhost:8000"
GATHER_INFO = f"{BASE_URL}/gather_info"
RECOMMENDER = f"{BASE_URL}/recommender"
CREDIT_RISK = f"{BASE_URL}/credit_risk"

secret_client = secretmanager.SecretManagerServiceClient()
gcp_id = "hip-arcadia-464212-v4"

def get_secret_value(secret_id):
    name = f"projects/{gcp_id}/secrets/{secret_id}/versions/latest"
    response = secret_client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

api = get_secret_value("Gemini")

if 'inflow_outflow_result' not in st.session_state:
    st.session_state.inflow_outflow_result = None
if 'mortgage_recommendation_result' not in st.session_state:
    st.session_state.mortgage_recommendation_result = None

st.set_page_config(page_title="Virtual Mortgage Advisor")

if 'step' not in st.session_state:
    st.session_state.step = 0
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}

client = genai.Client(api_key=api)
if st.session_state.step == 0:
    st.title("Virtual Mortgage Advisor")
    st.markdown(
        "Welcome! I'm here to help guide you through your mortgage application process.\n\n**Disclaimer:** This is a"
        " virtual assistant. Final offers depend on full underwriting. This tool provides suggestions, not formal recommendations.")
    if st.button("Start Application"):
        st.session_state.step = 1
        st.rerun()

elif st.session_state.step == 1:
    st.header("Time to gather details.")
    with st.form("user_data"):
        first_time = st.radio("Are you a first-time buyer?", ["Yes", "No"])
        buy_or_remortgage = st.radio("Are you buying, or remortgaging?", ["Buying", "Remortgaging"])
        education = st.radio("What is your highest level of education", ["Bachelor's", "High School", "Other"])
        marital_status = st.radio("What is your marital status?", ["Married", "Divorced", "Other"])
        loan_purpose = st.radio("What is the purpose for this loan?", ["Business", "Home", "Other"])
        age = st.number_input("What is your age?)")
        loan_amount = st.number_input("What is the loan amount required? (£)")
        deposit = st.number_input("How much are you able to deposit? (£)")
        property_value = st.number_input("What is the value of the property you wish to purchase? (£)")
        debt = st.number_input("How much are you in debt? (£)")
        credit_score = st.number_input("What is your current credit score?")
        employment_length = st.number_input("To the nearest month, how many months have you been in current employment?")
        submitted = st.form_submit_button("Submit")
        if submitted:
            st.session_state.user_data.update({
                "age" : age,
                "education" : education,
                "marital_status" : marital_status,
                "loan_purpose" : loan_purpose,
                "first_time": first_time,
                "buy_or_remortgage": buy_or_remortgage,
                "loan_amount": loan_amount,
                "property_value": property_value,
                "deposit": deposit,
                "debt": debt,
                "credit_score": credit_score,
                "employment_length": employment_length
            })
            st.session_state.step = 2
        if st.session_state.step == 2:
            st.rerun()


elif st.session_state.step == 2:
    st.header("Please upload your latest P60, your previous 3 payslips, and your previous 3 bank statements.")
    st.subheader(
        "Please name your files ""P60"", ""Payslip1/2/3"", ""BankStatement1/2/3 "". Do not include any other files in your upload.")
    with st.form("user_data"):
        uploaded_files = st.file_uploader("Upload here", accept_multiple_files=True, type="pdf")
        submitted = st.form_submit_button("Submit")
    if submitted:
        if uploaded_files:
            st.session_state.user_data["uploaded_files"] = uploaded_files
            st.success(f"Successfully prepared {len(uploaded_files)} file(s) for processing.")
            st.session_state.step = 3
            if st.session_state.step == 3:
                st.rerun()
        else:
            st.session_state.user_data["uploaded_files"] = []
            st.info("No files were uploaded.")


elif st.session_state.step == 3:
    st.header("Processing in progress - please wait")
    user_data = st.session_state.user_data
    files = []
    if user_data.get("uploaded_files"):
        for i in user_data["uploaded_files"]:
            files.append(
                ("supporting_info", (i.name, i.getvalue(), i.type))
            )
    else:
        st.write("No uploaded files.")

    input_data = {
        "debt": str(user_data.get("debt")),
        "p60_pay": user_data.get("p60_pay"),
        "p60_tax": user_data.get("p60_tax"),
        "payslips": user_data.get("payslips"),
        "payslips2": user_data.get("payslips2"),
        "payslips3": user_data.get("payslips3"),
        "balance_end1": user_data.get("balance_end1"),
        "balance_end2": user_data.get("balance_end2"),
        "balance_end3": user_data.get("balance_end3"),
        "difference1": user_data.get("difference1"),
        "difference2": user_data.get("difference2"),
        "difference3": user_data.get("difference3"),
    }

    if 'llm_call' not in st.session_state:
        st.session_state.llm_call = False

    if not st.session_state.llm_call:
        try:
            response = requests.post(GATHER_INFO, data=input_data, files=files)
            st.write("Status code: ", response.status_code)
            if response.status_code == 200:
                result = response.json()
                st.success("Information processed successfully.")
                st.session_state.data_gather_result = result
                st.session_state.inflow_outflow_calculation_result = result.get('inflow_outflow')
                if st.session_state.inflow_outflow_calculation_result:
                    st.subheader("AI Mortgage Advisor's Initial Assessment:")
                    st.markdown(st.session_state.inflow_outflow_calculation_result)
                if 'response' in result and 'extracted_text' in result['response']:
                    extracted_text = result["response"]["extracted_text"]
                st.session_state.llm_call = True
        except:
            st.error(f"An error occurred")
            st.stop()

    if st.button("Next"):
        st.session_state.step = 4
    if st.session_state.step == 4:
        st.rerun()


elif st.session_state.step == 4:
    st.header("Data gathered")

    user_data = st.session_state.user_data

    if user_data:
        st.subheader("Summary of Your Financial Situation")

        first_time_text = "Yes" if user_data['first_time'] == "Yes" else "No"
        st.markdown(f"**First-time buyer:** {first_time_text}")
        st.markdown(f"**Purchase type:** {user_data['buy_or_remortgage']}")
        st.markdown(f"**Loan amount:** £{user_data['loan_amount']:,.2f}")
        st.markdown(f"**Deposit available:** £{user_data['deposit']:,.2f}")
        st.markdown(f"**Current debt:** £{user_data['debt']:,.2f}")

        st.divider()

        if st.button("Get Mortgage Advice"):
            st.session_state.step = 5
            st.rerun()

elif st.session_state.step == 5:
    st.header("Generating Mortgage Advice...")

    with st.spinner("Analyzing your profile for the best mortgage options..."):
        user_data = st.session_state.user_data

        text = st.session_state.inflow_outflow_calculation_result

        match = re.search(r"Total Annual Inflow: £([\d,.]+)", text)

        total_annual_inflow = match.group(1)

        total_annual_inflow_float = float(total_annual_inflow)

        print(f"Extracted Total Annual Inflow: £{total_annual_inflow_float:,.2f}")

        credit_risk_payload = {
            "loan_amount": str(user_data.get("loan_amount")),
            "credit_score": str(user_data.get("credit_score")),
            "age": str(user_data.get("age")),
            "employment_length": str(user_data.get("employment_length")),
            "marital_status": str(user_data.get("marital_status")),
            "loan_purpose": str(user_data.get("loan_purpose")),
            "inflow": total_annual_inflow_float,
        }

        r = requests.post(CREDIT_RISK, data=credit_risk_payload)

        if r.status_code == 200:
            res = r.json()
            print(res)
            st.session_state.credit_risk_result = res.get("credit_risk")
            if st.session_state.credit_risk_result == 0:

                print("Deposit: ", str(user_data.get("deposit")))
                print("Loan: ", str(user_data.get("loan_amount")))

                payload = {
                    "first_time": str(user_data.get("first_time")),
                    "buy_or_remortgage": str(user_data.get("buy_or_remortgage")),
                    "deposit": str(user_data.get("deposit")),
                    "debt": str(user_data.get("debt")),
                    "loan_amount": str(user_data.get("loan_amount")),
                    "property_value": str(user_data.get("property_value")),
                    "credit_score": str(user_data.get("credit_score")),
                    "inflow_outflow_summary": st.session_state.inflow_outflow_calculation_result,
                    "credit_risk": st.session_state.credit_risk_result,
                    "employment_length": str(user_data.get("employment_length")),
                    "age": str(user_data.get("age")),
                    "employment_length": str(user_data.get("employment_length")),
                    "marital_status": str(user_data.get("marital_status")),
                    "loan_purpose": str(user_data.get("loan_purpose")),
                }

                response = requests.post(RECOMMENDER, data=payload)

                if response.status_code == 200:
                    result = response.json()
                    st.success("Mortgage advice generated successfully!")
                    st.session_state.mortgage_recommendation_result = result.get('mortgage_recommendation')
            else:
                st.error("You are at risk of defaulting. We cannot provide mortgage advice to you at this time.")

        else:
            st.error("Status: {response.status_code}. Error: {response.text}")
        st.session_state.recommendation_processed = True

    if st.session_state.get("recommendation_processed") and st.session_state.get("mortgage_recommendation_result"):
        st.subheader("Your Personalized Mortgage Advice:")
        st.markdown(st.session_state.mortgage_recommendation_result)

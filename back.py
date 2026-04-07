import io

import requests
from crewai import Agent, Task, Crew, Process, LLM
from typing import Optional, List, Annotated
import asyncio
from fastapi import FastAPI, UploadFile, File, Form
from google.cloud import secretmanager
from google import genai
# for loading model
import joblib
import numpy as np


app = FastAPI()

interest_url = 'https://api.api-ninjas.com/v1/interestrate?country=United Kingdom'

# loading saved model and scaler
model = joblib.load("model.pkl")
scaler = joblib.load("scaler.pkl")

secret_client = secretmanager.SecretManagerServiceClient()
gcp_id = "hip-arcadia-464212-v4"

def get_secret_value(secret_id):
    name = f"projects/{gcp_id}/secrets/{secret_id}/versions/latest"
    response = secret_client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

api = get_secret_value("Gemini")
interest = get_secret_value("Interest_Rate_BOE")

# 0 - low default risk, 1 - high default risk
def predict_default(loan_amount: float, credit_score: float, income: float, age: float, employment_length: float, marital_status: str, loan_purpose: str) -> int:
    try:
        # defining the features
        X = np.array([[age, income, loan_amount, credit_score, employment_length, marital_status, loan_purpose]])
        X_scaled = scaler.transform(X)
        prediction = model.predict(X_scaled)[0]
        print("Prediction made:", prediction)
        return int(prediction)
    except Exception as e:
        print("Error when making predicition", e)
        return -1


def use_llm():
    return LLM(
        model="gemini/gemini-2.5-flash",
        provider="google",
        api_key=api
    )

client = genai.Client(api_key=api)

async def extract_info_with_gemini(files: List[UploadFile]) -> str:

    try:
        gemini_files = []
        uploaded_ids = []

        for file in files:
            file_bytes = await file.read()
            file_obj = io.BytesIO(file_bytes)

            uploaded = client.files.upload(
                file=file_obj,
                config=dict(mime_type=file.content_type)
            )
            gemini_files.append(uploaded)
            uploaded_ids.append(uploaded.name)

        prompt = (
            "You are an expert financial data extractor. Analyze the following uploaded financial documents (P60, "
            "payslips, and bank statements). Your task is to extract the following specific financial figures. "
            "If a specific piece of information is not found, state 'N/A'.\n\n"
            "Return values in this format:\n"
            "- P60 Total Pay: £[value or N/A]\n"
            "- P60 Total Tax Deducted: £[value or N/A]\n"
            "- Recent Payslip Net Pay: £[value or N/A]\n"
            "- 2nd Recent Payslip Net Pay: £[value or N/A]\n"
            "- 3rd Recent Payslip Net Pay: £[value or N/A]\n"
            "- Balance end of 1st bank statement: £[value or N/A]\n"
            "- Balance end of 2nd bank statement: £[value or N/A]\n"
            "- Balance end of 3rd bank statement: £[value or N/A]\n"
            "- Inflow/outflow of 1st bank statement: £[value or N/A]\n"
            "- Inflow/outflow of 2nd bank statement: £[value or N/A]\n"
            "- Inflow/outflow of 3rd bank statement: £[value or N/A]"
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[*gemini_files, prompt]
        )
        output = response.text.strip()

        for file_id in uploaded_ids:
            client.files.delete(name=file_id)

        return output

    except Exception as e:
        import traceback
        traceback.print_exc()


async def getRecommendation(data_type, user_data):
    llm = use_llm()

    if data_type == "info_gather":
        role = "Financial Analyst, expert in calculating personal income and expenses"
        goal = "Accurately calculate the user's total annual inflow and outflow based on provided financial data and documents. Do NOT make a mortgage recommendation."
        backstory = "An AI expert capable of meticulous financial data analysis to determine net disposable income."

        description = f"""
        You are provided with financial data extracted from official documents including P60s, payslips, and bank statements.

        The extracted data is:
        {user_data['extracted_text']}

        Additional user detail:
        - Existing debt: £{user_data['debt']}

        Your task:
        1. Analyze the extracted financial data and calculate:
            - Total Annual Inflow (sum of all income sources).
            - Total Annual Outflow (estimated based on taxes and bank statement activity).
        2. Consider all available figures and give your reasoning.
        3. Assume the extracted data is complete and accurate.
        4. DO NOT make any mortgage recommendations.

        At the end, clearly present:
        Total Annual Inflow: £XXX
        Total Annual Outflow: £YYY
        """


    elif data_type == "recommender":
        role = "Senior Mortgage Underwriter and Specialist Mortgage Advisor in the UK, expert in risk evaluation and mortgage product recommendation"
        goal = "Summarize the user's financial inflow and outflow, apply risk evaluation, and propose suitable mortgage terms (term, interest rate, loan amount) that a bank could offer. Justify the recommendation."
        backstory = "An experienced AI underwriter with deep knowledge of mortgage products, risk assessment, and financial regulations, capable of synthesizing complex financial data into actionable mortgage advice."
        interest_rate = requests.get(interest_url, headers={'X-Api-Key': interest})
        data = interest_rate.json()
        current_rate = data["central_bank_rates"][0]["rate_pct"]
        print("Current rate: ", current_rate)

        description = f"""
        Based on the previously calculated inflow/outflow, and the following user details, perform a comprehensive risk evaluation and provide a mortgage recommendation.
        User details:
        - Purpose: {user_data['buy_or_remortgage']}
        - First-time buyer: {user_data['first_time']}
        - Financial Analyst Summary of Inflow/Outflow: {user_data.get('inflow_outflow_summary', 'N/A')}
        - Credit score: {user_data['credit_score']}
        - Logistic Regression Model Credit Risk Prediction (0 = Low risk, 1 = High risk): {user_data.get('credit_risk')}
        - Deposit: {user_data['deposit']}
        - Loan required: {user_data['loan_amount']}
        - Property value: {user_data['property_value']}
        - Current Bank of England Interest Rate (%): {current_rate}
        - Current employment length (years): {user_data['employment_length']}

        IMPORTANT: Assume that inflow and outflow calculations have already been performed by a qualified financial analyst.

        Your task involves:
        1.  Calculate loan to value ratio (LTV) and debt-to-income ratio.
        2.  **Summarizing** the key financial data (inflow, outflow, income, debt, deposit) concisely.
        3.  **Applying Risk Evaluation**: Assess the user's financial stability, debt-to-income ratio, loan-to-value (LTV) potential based on deposit, and general affordability. Identify any red flags or strengths.
        4.  **Recommending Mortgage Terms**: Based on your summary and risk evaluation, recommend a suitable:
            * **Mortgage Term:** Justify why this term is appropriate.
            * **Indicative Interest Rate (e.g., X.X%):** State a realistic indicative rate.
            * **Maximum Loan Amount (e.g., £X,XXX):** Provide a clear maximum loan amount, based on what the user requested.
        5.  **Justify your recommendations** with clear reasoning based on the financial data and risk assessment.
        Offer a clear explanation of affordability range, and state high level particular risks.
        """

    agent = Agent(role=role, goal=goal, backstory=backstory, verbose=True, llm=llm)
    task = Task(description=description, agent=agent, expected_output=f"A structured mortgage recommendation")
    crew = Crew(tasks=[task], agents=[agent], verbose=False, process=Process.sequential)

    try:
        result = await asyncio.to_thread(crew.kickoff)
        print("CrewAI result:", result)

        if hasattr(result, '__str__'):
            result_str = str(result)
            print(result_str)
            return result_str

        else:
            return "Could not compute inflow/outflow."

    except Exception as e:
        return "Error during inflow/outflow calculation"


@app.post("/gather_info")
async def gather_info(
        debt: Annotated[float, Form(...)],
        supporting_info: Optional[List[UploadFile]] = File(None)
):

    extracted_text = "No documents provided."

    if supporting_info:
        extracted_text = await extract_info_with_gemini(supporting_info)

    summary = {
        "extracted_text": extracted_text,
        "debt": debt
    }

    inflow_outflow = await getRecommendation("info_gather", summary)
    return {"inflow_outflow": inflow_outflow, "extracted_text": extracted_text}


@app.post("/credit_risk")
async def recommend_mortgage(
        loan_amount: Annotated[float, Form(...)],
        credit_score: Annotated[float, Form(...)],
        age: Annotated[float, Form(...)],
        employment_length: Annotated[float, Form(...)],
        marital_status: Annotated[float, Form(...)],
        loan_purpose: Annotated[float, Form(...)],
        inflow: Annotated[float, Form(...)],
):
    credit_risk = predict_default(loan_amount, credit_score, inflow, age, employment_length, marital_status, loan_purpose)

    return {"credit_risk": credit_risk}


@app.post("/recommender")
async def recommend_mortgage(
        loan_amount: Annotated[float, Form(...)],
        first_time: Annotated[str, Form(...)],
        buy_or_remortgage: Annotated[str, Form(...)],
        deposit: Annotated[float, Form(...)],
        property_value: Annotated[float, Form(...)],
        debt: Annotated[float, Form(...)],
        credit_score: Annotated[float, Form(...)],
        credit_risk: Annotated[float, Form(...)],
        employment_length: Annotated[float, Form(...)],
        inflow_outflow_summary: Optional[str] = Form(...),
):

    summary = {
        "loan_amount": loan_amount,
        "first_time": first_time,
        "buy_or_remortgage": buy_or_remortgage,
        "deposit": deposit,
        "debt": debt,
        "property_value": property_value,
        "credit_score": credit_score,
        "inflow_outflow_summary": inflow_outflow_summary,
        "credit_risk": credit_risk,
        "employment_length": employment_length
    }

    print("User data received by recommender endpoint: ", summary)
    mortgage_recommendation_result = await getRecommendation("recommender", summary)
    return {"mortgage_recommendation": mortgage_recommendation_result}

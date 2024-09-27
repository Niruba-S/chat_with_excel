import streamlit as st
import json
import uuid
import os
from datetime import datetime
from dotenv import load_dotenv
import boto3
import pandas as pd
import plotly.express as px
import plotly.io as pio

load_dotenv()

# Set up the AWS Bedrock client
aws_access_key_id = os.getenv('aws_access_key')
aws_secret_access_key = os.getenv('aws_secret_key')
aws_region = os.getenv('region_name', 'us-east-1')

bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=aws_region,
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key
)

CLAUDE_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

def invoke_claude(prompt, max_tokens=1000):
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7
    })
    
    response = bedrock.invoke_model(
        body=body,
        modelId=CLAUDE_MODEL_ID,
        accept="application/json",
        contentType="application/json"
    )
    
    response_body = json.loads(response.get('body').read())
    return response_body['content'][0]['text']

class Agent:
    def __init__(self, name, system_message):
        self.name = name
        self.system_message = system_message

    def process(self, message):
        prompt = f"{self.system_message}\n\nHuman: {message}\n\nAssistant:"
        return invoke_claude(prompt)

class UserProxy(Agent):
    def __init__(self):
        super().__init__("User_proxy", "A human admin.")

    def initiate_chat(self, manager, message):
        return manager.process(message)

class DataEngineer(Agent):
    def __init__(self):
        super().__init__("Data_engineer", "As a data engineer, your job is to analyze the uploaded CSV file, extract its metadata, and pass it to the coder. The coder can then write and execute the code to fetch relevant data to answer the query.")

class Coder(Agent):
    def __init__(self):
        super().__init__("Coder", "I am a coder. I will write and execute the code to fetch relevant data from the CSV to answer the query. I will always mention the file used for it in the print statement. I will use pandas for data manipulation and Plotly for visualization. For your information, today's date is {current_date_time}.")

class Critic(Agent):
    def __init__(self):
        super().__init__("Critic", "Critic. You are a helpful assistant highly skilled in evaluating the quality of a given answer based on the CSV data extractor code for giving the answer by providing a score from 1 (bad) - 10 (good) while providing clear rationale. Show me the response or output and if the right answer for the question is obtained and also share the output in the terminal. Pass the output of the code to code_assistant for displaying.")

class Analyst(Agent):
    def __init__(self):
        super().__init__("Analyst", "Analyst. Your role is to make the data analysis and chart description for the chart produced and save it in a text file.")

class Manager:
    def __init__(self, agents):
        self.agents = agents

    def process(self, message):
        for agent in self.agents:
            response = agent.process(message)
            message += f"\n\n{agent.name}: {response}"
        return response

def autogen_solution(query, df):
    uuid_name = uuid.uuid4()
    current_date_time = datetime.now()
    
    metadata = {
        'file_name': 'uploaded_file.csv',
        'columns': df.columns.tolist(),
        'row_count': len(df),
        'file_size': df.memory_usage(deep=True).sum()
    }
    
    user_proxy = UserProxy()
    data_engineer = DataEngineer()
    coder = Coder()
    critic = Critic()
    analyst = Analyst()
    
    manager = Manager([data_engineer, coder, critic, analyst])
    
    message = f"""
    Analyze the uploaded CSV file and create a plot or chart for the query.
    For your info, today's date is {current_date_time}. Give me the plot only for this user query: {query} with proper date reference.
    Save the file as a Plotly JSON '{uuid_name}.json' so I should be able to put it in st.plotly_chart.
    Write a description along with chart analysis for the query and store it in {uuid_name}.txt.
    The CSV file metadata: {metadata}

    Here's a sample of the data (first 5 rows):
    {df.head().to_json(orient='records')}
    """
    
    response = user_proxy.initiate_chat(manager, message)
    
    # Read the generated text file
    with open(f"{uuid_name}.txt", "r") as f:
        text = f.read()
    os.remove(f"{uuid_name}.txt")
    
    # Read the generated JSON file
    with open(f"{uuid_name}.json", "r") as f:
        data = json.load(f)
    os.remove(f"{uuid_name}.json")
    
    return text, data

def read_csv_with_multiple_encodings(file):
    encodings = ['utf-8', 'iso-8859-1', 'cp1252', 'latin1']
    for encoding in encodings:
        try:
            return pd.read_csv(file, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to read the CSV file with any of the attempted encodings.")

def main():
    st.title("Data Analysis with Claude 3.5 Sonnet")

    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    
    if uploaded_file is not None:
        try:
            df = read_csv_with_multiple_encodings(uploaded_file)
            st.write("Data Preview:")
            st.dataframe(df.head())

            query = st.text_input("Enter your query about the data:")
            
            if query:
                with st.spinner("Analyzing data..."):
                    text, plot_data = autogen_solution(query, df)
                
                st.subheader("Analysis Results:")
                st.write(text)
                
                st.subheader("Visualization:")
                fig = pio.from_json(json.dumps(plot_data))
                st.plotly_chart(fig)
        except ValueError as e:
            st.error(f"Error reading the CSV file: {str(e)}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()
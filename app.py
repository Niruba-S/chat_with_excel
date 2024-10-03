import streamlit as st
import pandas as pd
import boto3
import json
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv
import re
import plotly.express as px
from streamlit_lottie import st_lottie
import requests
import streamlit.components.v1 as components
import pygwalker as pyg
import time
import numpy as np
import base64

# Load the .env file
load_dotenv()

# Access variables from the .env file
aws_access_key_id = os.getenv('aws_access_key')
aws_secret_access_key = os.getenv('aws_secret_key')
aws_region = os.getenv('region_name', 'us-east-1')

BEDROCK_MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"

if not aws_access_key_id or not aws_secret_access_key:
    st.error("AWS credentials are not set. Please set the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.")
    st.stop()

# Initialize AWS Bedrock client
try:
    bedrock = boto3.client(
        service_name='bedrock-runtime',
        region_name=aws_region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
except Exception as e:
    st.error(f"Error initializing AWS Bedrock client: {str(e)}")
    st.stop()

def invoke_claude(prompt):
    try:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "top_p": 0.9
        })
        
        response = bedrock.invoke_model(
            body=body,
            modelId=BEDROCK_MODEL_ID,
            accept="application/json",
            contentType="application/json",
        )
        
        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text']
    except ClientError as e:
        st.error(f"An error occurred: {e}")
        return None

# Set page configuration
st.set_page_config(page_title="Sales Data Analysis App", page_icon="📊", layout="wide")

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:ital,wght@0,200..1000;1,200..1000&display=swap');
    
    /* Add orange outline to all text inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stChatInputContainer > div > textarea
    div[data-baseweb="input"] > div > input  {
        border: 1px solid #f3782b !important;
        border-radius: 10px !important;
        box-shadow: 0 0 5px rgba(255, 165, 0, 0.5) !important;
        
    }   
    .st-cp {
        border: 1px solid rgba(243, 120, 43, 0.7) !important;
        border-radius: 10px !important;
    }
    section[data-testid="stSidebar"] {
        background-color:#EEE6E1;
         box-shadow: 0px 0px 15px 5px rgba(243, 120, 43, 0.5);     /* Adds a glowing orange shadow around the sidebar */
        
    }
    .st-emotion-cache-1pajqs2 {
        border: 1px solid rgb(243, 120, 43); /* Adds orange border */
        box-shadow: 0 0 5px rgba(255, 165, 0, 0.1) !important;
        background-color: #FFFFFF;
    }
    .st-emotion-cache-ugcgyn.eczjsme11 {
    background-color: white;
}
    .st-emotion-cache-10trblm{
        font-size: 27px;
        font-weight: bold;
        color: rgb(243, 120, 43);  /* Matches the orange color */
        font-family: 'Nunito Sans', sans-serif;  /* Adjust this to match the font style */
        font-style: normal;
            

    }      
    .assistant-message {
        font-family: Arial, sans-serif;  /* Set your desired font here */
        font-size: 16px;  /* Adjust the font size if needed */
        color: #333333;
    }
</style>
""", unsafe_allow_html=True)

# Function to load Lottie animation
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()



# Load Lottie animations
lottie_data = load_lottieurl("https://lottie.host/8e51e39d-b1c1-4065-9d55-d5ef3fb38ad5/Bq1n4KYdqv.json")
lottie_analysis = load_lottieurl("https://assets5.lottiefiles.com/private_files/lf30_skwgamub.json")
chart_loading_animation = load_lottieurl("https://lottie.host/04354def-9aea-4fca-8633-85a6ced9c043/EStsxuRiMy.json")


# Function to load data
def load_data(file):
    if file.name.endswith('.csv'):
        encodings = ['utf-8', 'iso-8859-1', 'cp1252', 'utf-16']
        for encoding in encodings:
            try:
                file.seek(0)
                df = pd.read_csv(file, encoding=encoding)
                if df.empty:
                    st.error("The uploaded file is empty.")
                    return None
                
                return df
            except UnicodeDecodeError:
                continue
            except Exception as e:
                st.error(f"Error loading file with {encoding} encoding: {str(e)}")
                continue
        st.error("Unable to read the file with any of the attempted encodings. Please check the file format and try again.")
        return None
    elif file.name.endswith(('.xls', '.xlsx')):
        try:
            df = pd.read_excel(file)
            if df.empty:
                st.error("The uploaded Excel file is empty.")
                return None
            return df
        except Exception as e:
            st.error(f"Error loading Excel file: {str(e)}")
            return None
    else:
        st.error("Unsupported file format. Please upload a CSV or Excel file.")
        return None


def generate_chart(df, prompt):
    columns = df.columns.tolist()
    data_types = {col: str(dtype) for col, dtype in df.dtypes.to_dict().items()}  # Simplified data types
    data_sample = df.head(5).to_string(index=False)  # Readable string format for data sample

 
    # Define custom color palette
    custom_colors = [
        'rgb(243, 120, 43)',  # Main orange
        'rgb(245, 150, 90)',  # Lighter shade
        'rgb(247, 180, 137)', # Even lighter
        'rgb(249, 210, 184)', # Very light (close to beige)
        'rgb(251, 240, 231)'  # Beige
    ]

    # Construct the prompt for the OpenAI API
    system_message = """You are a data visualization expert. Your task is to generate Python code using Plotly Express to create a chart based on the given data and user prompt. 
    The code should be executable and create a chart that best represents the data according to the user's request."""

    user_message = f"""
    Data columns: {columns}
    Data types: {data_types}
    Data sample: {data_sample}

    User request: {prompt}

     IMPORTANT: Always use the DataFrame named 'df' as the data_frame argument in all Plotly Express functions. Do not change the name or assume any other DataFrame.

    Generate Python code using Plotly Express to create the requested chart. Follow these guidelines:
    - Use 'df' exclusively for any data operations while generating the code for the chart.
    - pass df:{df} as the data_frame argument .
    - Ensure 'x' and 'y' parameters refer to column names in 'df'.
    - If data manipulation is needed, perform it before the Plotly Express function call and store the result in a new variable.
    - Use only Plotly Express (px) functions for creating the chart.
    - Always use fig.update_layout() for modifying chart properties, including axes.
    - Do not use fig.update_xaxis(), fig.update_yaxis(), or similar methods directly.
    - For axis modifications, include them within fig.update_layout() like this:
       fig.update_layout(xaxis=dict(title='X Title', tickangle=45), yaxis=dict(title='Y Title'))
    - Generate **only** Python code using Plotly Express to create the requested chart.
    - The code should be complete and executable without any comments, explanations, or markdown syntax.
    - Do not include any print statements, return values, or extra text.
    - Ensure that the code creates a figure using 'df' and assigns it to a variable named 'fig'.
    - Use the custom color palette provided: {custom_colors}.
    - Double-check that all parentheses, brackets, and curly braces are properly closed before submitting the code.
    - Ensure that each line of code is properly indented and formatted.
    - If a line of code is too long, break it into multiple lines for better readability.

    Example:
    custom_colors = ['rgb(243, 120, 43)', 'rgb(245, 150, 90)', 'rgb(247, 180, 137)', 'rgb(249, 210, 184)', 'rgb(251, 240, 231)']
    fig = px.bar(df.nlargest(5, 'SALES'), x='SALES', y='CUSTOMERNAME', orientation='h', title='Top 5 Sales Customers', color_discrete_sequence=custom_colors)
    fig.update_layout(
        xaxis=dict(title='Sales'),
        yaxis=dict(title='Customer Name'),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    """

    full_prompt = f"Human: {system_message}\n\n{user_message}\n\nAssistant:"
    
    # Assuming invoke_claude is the function that sends this prompt to the AI and receives a response.
    generated_code = invoke_claude(full_prompt)

    if generated_code:
        # Clean and validate code
        cleaned_code = clean_and_validate_code(df,generated_code)
        if cleaned_code:
            return cleaned_code
        else:
            return None
    else:
        return None



def clean_and_validate_code(df,code):
    # Remove any markdown code block syntax
    code = re.sub(r'```python\n?', '', code)
    code = re.sub(r'```\n?', '', code)
    
    # Remove any leading/trailing whitespace
    code = code.strip()
    
    # Extract only the Python code (remove any explanatory text)
    code_lines = code.split('\n')
    python_code = []
    for line in code_lines:
        if line.strip().startswith('#') or '=' in line or line.strip().startswith('fig.'):
            python_code.append(line)
    
    cleaned_code = '\n'.join(python_code)
    
    # Ensure the code starts with 'fig ='
    if not cleaned_code.startswith('fig ='):
        cleaned_code = 'fig = ' + cleaned_code
    
    # Use Claude to validate and potentially fix parentheses
    prompt = f"""
    Please check the following Python code for unbalanced parentheses, brackets, or braces. 
    If you find any errors, correct them and return the fixed code. 
    Use 'df'  exclusively for any data operations while generating the code for the chart.
    Name 'df' as the data_frame argument in all Plotly Express functions.
    Remove any unnecessary comments.(```python,```)
    Make sure {df} is passed as the data_frame argument and name it as "df".
    If there are no errors, simply return the original code.


    
    Here's the code:

    {cleaned_code}

    Please provide your response in the following format:
    VALIDATION_RESULT: [OK if no errors, ERROR if errors found]
    FIXED_CODE: [The original or corrected code]
    EXPLANATION: [Brief explanation of any changes made, if any]
    """

    response = invoke_claude(prompt)
    
    # Parse Claude's response
    validation_result = re.search(r'VALIDATION_RESULT: (OK|ERROR)', response)
    fixed_code = re.search(r'FIXED_CODE:\s*(.*?)(?=EXPLANATION:)', response, re.DOTALL)
    explanation = re.search(r'EXPLANATION:\s*(.*)', response, re.DOTALL)
    
    if validation_result and fixed_code:
        if validation_result.group(1) == 'OK':
            return cleaned_code
        else:
            print(explanation.group(1))
            return fixed_code.group(1).strip()
    else:
        st.error("Failed to validate code structure. Please try again.")
        return None
    

def generate_dataset_overview(df):
    # Generate basic information about the dataset
    num_rows, num_cols = df.shape
    column_names = df.columns.tolist()
    sample_data = df.head().to_string()

    # Prepare the prompt for Claude
    prompt = f"""You are a data analyst providing a brief overview of a dataset. Given the following information about a dataset, provide a concise 3-4 line overview that describes what this data is about and its potential use:

    - Number of rows: {num_rows}
    - Number of columns: {num_cols}
    - Column names: {', '.join(column_names)}
    - Sample data (first 5 rows):
    {sample_data}

    Please provide a brief, informative overview that gives the user a quick understanding of what this dataset represents, what kind of information it contains, and what it might be used for. Focus on the nature and context of the data rather than just its structure.

    Your response should be in the following format:
    OVERVIEW: [Your 3-4 line overview here]
    """

    # Get response from Claude
    response = invoke_claude(prompt)

    # Extract the overview from Claude's response
    overview_match = re.search(r'OVERVIEW:(.*)', response, re.DOTALL)
    if overview_match:
        overview = overview_match.group(1).strip()
    else:
        overview = "Unable to generate overview. Please check the dataset and try again."

    return overview


def query_data(df, query):
 
    # Prepare basic dataset information
    total_rows = len(df)
    total_columns = len(df.columns)
    column_names = ", ".join(df.columns)
    
    
    
    



    prompt = f"""You are a data analyst providing concise answers to queries about a dataset. Use the following information about the dataset to answer the query:

    Dataset Info:
    - Total rows: {total_rows}
    - Total columns: {total_columns}
    - Columns: {column_names}



    

    Respond to this query: {query}
    Guidelines for your response:
    Assume full access to the dataset and perform any necessary analysis on the actual data values.
    1. Thoroughly analyze the entire dataset before answering the query.
    2. Perform relevant statistical analyses based on the query.
    3.Tailor your response to the type of query:
        -Statistical Queries: Perform relevant calculations (e.g., mean, median, distribution, correlations) and provide direct insights based on the dataset.
        -Recommendation Queries: Use the dataset to suggest actionable steps, such as strategies to improve sales, customer retention, or operational efficiency.
        -Customer Satisfaction/Performance Queries: Analyze satisfaction or performance-related columns, identifying trends, averages, and potential areas for improvement.
        -Data Quality Queries: Assess completeness, missing data, or potential outliers in the dataset.
    4. Provide a direct, concise answer without unnecessary explanations.
    5. Include relevant numbers and statistics from the data.
    6. Keep your response to 2-3 sentences maximum.
    7. Speak as a data analyst would, focusing on facts and insights.Let the answer be more human like rather than a chatbot.
    8. Identify key patterns and trends that could help improve sales.
    9. Provide data-driven recommendations that are directly actionable.
    10. Structure the recommendations to focus on how different aspects of the dataset can boost sales (e.g., targeting specific customer segments, optimizing product offerings, etc.).
    11. Cite specific data from the DataFrame when answering the query (e.g., referencing actual values from columns).
    12. Provide the answer for the query and then cite the data source.
    13.If the query cannot be answered with the available data, clearly state why, but focus on using the available dataset as much as possible.

    Format:
    [Your answer here]
    **SOURCE**: [Citation of the data source]

    Your response:
    """

    response = invoke_claude(prompt)
    
    # Remove any markdown formatting if present
    response = re.sub(r'\*\*|\*|#|`', '', response)
    
    return response.strip()

# Function to create PyGWalker visualization
def create_pygwalker_viz(df):
    config = {
        "theme": {
            "backgroundColor": "white",
            "textColor": "black",
            "toggler": {
                "backgroundColor": "#f0f0f0",
                "borderColor": "#d9d9d9",
                "color": "black"
            }
        }
    }

    pyg_html = pyg.to_html(df,config=config)
    components.html(pyg_html, height=1000, scrolling=False)


def generate_chart_explanation(chart_code, user_input):
    prompt = f"""
    Based on the following Python Plotly code and the user's request, provide a simple 2-3 line explanation of the chart for easy understanding.
    Explain on the data part..avoid explanations on colours used in the chart
    
    User Request: {user_input}
    
    Plotly Code:
    {chart_code}
    
    Please provide your response in the following format:
    
    EXPLANATION: [Brief 2-3 line explanation of the chart]
    """
    
    response = invoke_claude(prompt)
    
    # Extract the explanation from the response
    explanation = re.search(r'EXPLANATION:\s*(.*)', response)
    
    if explanation:
        return explanation.group(1).strip()
    else:
        return "No explanation available."

# Main Streamlit app

def get_binary_file_downloader_html(bin_file, file_label='File'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    file_ext = bin_file.split('.')[-1].lower()
    
    if file_ext == 'csv':
        mime_type = 'text/csv'
    elif file_ext == 'docx':
        mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        mime_type = 'application/octet-stream'
    
    href = f'<a href="data:{mime_type};base64,{bin_str}" download="{bin_file}">Download {file_label}</a>'
    return href

def main():
    sample_queries = """
1.	What is the highest-selling product line in the dataset?
2.	Identify the top 5 customers based on total sales.

"""
    if not aws_access_key_id or not aws_secret_access_key:
        st.error("AWS credentials are not set. Please set the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.")
        st.stop()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "file_uploaded" not in st.session_state:
        st.session_state.file_uploaded = False
    if "welcome_message_shown" not in st.session_state:
        st.session_state.welcome_message_shown = False
    if "upload_success_message_shown" not in st.session_state:
        st.session_state.upload_success_message_shown = False
    if "user_input_given" not in st.session_state:
        st.session_state.user_input_given = False
    if "response_generated" not in st.session_state:
        st.session_state.response_generated = False
    if "user_input_given_chart" not in st.session_state:
        st.session_state.user_input_given_chart= False
    if "response_generated_chart" not in st.session_state:
        st.session_state.response_generated_chart = False
    user_input = " "


    uploaded_file = st.sidebar.file_uploader("File Uploader", type=["csv", "xlsx", "xls"])
    
    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Choose a page", ["Chatbot Query", "Chart Generation", "Data Visualization"])

    st.sidebar.markdown("### Sample Dataset and Queries")
    
    st.sidebar.markdown(get_binary_file_downloader_html('sales_data_sample.csv', 'Sample Data (CSV)'), unsafe_allow_html=True)
    
    # DOCX file
    st.sidebar.markdown(sample_queries  )
    # if st.sidebar.button("Clear Chat"):
    #     st.session_state.messages = []
    #     st.session_state.welcome_message_shown = False
    #     st.session_state.upload_success_message_shown = False
    #     st.session_state.file_uploaded = False
    #     st.success("Chat history cleared!")
    #     st.rerun()

    if page == "Chatbot Query":
        col1, col2 = st.columns([2, 1.1])

        with col1:
            st.title("Sales Insights and Recommendation Engine")
        
        with col2:
            st_lottie(lottie_data, height=120, key="lottie_animation")

        # Display welcome message only once
        if not st.session_state.welcome_message_shown:
            welcome_message = "👋 Welcome to the Sales Data Analysis App! To get started, please upload your sales dataset using the file uploader in the sidebar. Once uploaded, I'll be here to answer any questions you have about your data!"
            # with st.chat_message("assistant"):
                
            st.session_state.messages.append({"role": "assistant", "content": welcome_message})
            st.session_state.welcome_message_shown = True

        # Handle file upload
        if uploaded_file is not None:
            df = load_data(uploaded_file)
            if df is not None:
                st.session_state.df = df
                if not st.session_state.file_uploaded:
                    st.session_state.file_uploaded = True
                    # Display upload success message only once
                    if not st.session_state.upload_success_message_shown:
                        success_message = "✅ Great! Your sales dataset has been successfully uploaded. "
                        
                            
                        st.session_state.messages.append({"role": "assistant", "content": success_message})
                        st.session_state.upload_success_message_shown = True
                        overview = generate_dataset_overview(df)
                        st.session_state.messages.append({"role": "assistant", "content": f"<b>Data Overview</b>:\n{overview}\n\nNow, feel free to ask me any questions about your data!"})
                

            

             
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
               st.markdown(f'<div class="assistant-message">{message["content"]}</div>', unsafe_allow_html=True)

        # Handle user input
        if prompt := st.chat_input("What would you like to know about the data?"):
            st.session_state.user_input_given = True
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            if not st.session_state.file_uploaded:
                response = "Please upload a file to start the analysis."
            else:
                with st.spinner("Analyzing ..."):
                    response = query_data(st.session_state.df, prompt)
            st.session_state.response_generated = True
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                 st.markdown(f'<div class="assistant-message">{response}</div>', unsafe_allow_html=True)
        if st.session_state.user_input_given and st.session_state.response_generated:
            if st.button("Clear Chat"):
                    st.session_state.messages = []
                    st.session_state.welcome_message_shown = False
                    st.session_state.upload_success_message_shown = False
                    st.session_state.file_uploaded = False
                    st.rerun()

            
        
    elif page == "Chart Generation":
        if "chart_welcome_shown" not in st.session_state:
         st.session_state.chart_welcome_shown = False
        st.title("Chart Generation")
        # Initialize chat history in session state if it doesn't exist
        if 'chart_chat_history' not in st.session_state:
            st.session_state.chart_chat_history = []

        if 'df' in st.session_state and st.session_state.df is not None:
          
          st.session_state.chart_welcome_shown = False

        if not st.session_state.chart_welcome_shown:
            welcome_message = """
            👋 Welcome to the Chart Generation page! 
            
            Here, you can create custom charts based on your uploaded data. Simply describe the chart you want, and I'll generate it for you.

            Sample Queries for Chart Generation:
            1. Show total sales per country.
            2. Create a histogram of order quantities.

            Feel free to ask for any chart you need, and I'll do my best to create it!
            """
            
            
            
            st.session_state.chart_chat_history.append({
                "role": "assistant",
                "content": welcome_message
            })
            
            st.session_state.chart_welcome_shown = True
            
        

        if 'df' not in st.session_state or st.session_state.df is None:
            st.warning("Please upload a file on the Chatbot Query page to generate charts.")
        else:
            # Display chat history
            for message in st.session_state.chart_chat_history:
                with st.chat_message(message["role"]):
                    st.write(message["content"])
                    if "chart" in message:
                        st.plotly_chart(message["chart"])

            # Chat input
            user_input = st.chat_input("Describe the chart you want to create:")
            
            if user_input:
                st.session_state.user_input_given_chart = True
                # Add user message to chat history
                st.session_state.chart_chat_history.append({"role": "user", "content": user_input})

                # Display user message
                with st.chat_message("user"):
                    st.write(user_input)

                # Create an empty placeholder for the animation
                with st.chat_message("assistant"):
                    gif_placeholder = st.empty()
                    with gif_placeholder:
                        st_lottie(chart_loading_animation, height=200, key="chart_loading")

                    # Generate the chart code using OpenAI
                    chart_code = generate_chart(st.session_state.df, user_input)

                    if chart_code:
                        try:
                            # Create a new local namespace to execute the code
                            local_vars = {'df': st.session_state.df, 'px': px}

                            # Execute the code
                            exec(chart_code, globals(), local_vars)

                            # Check if 'fig' is in the local namespace
                            if 'fig' in local_vars:
                                # Once the chart is generated, clear the GIF
                                gif_placeholder.empty()
                                # Display the generated chart
                                st.plotly_chart(local_vars['fig'])
                                # Add to chat history
                                st.session_state.chart_chat_history.append({
                                    "role": "assistant",
                                    "content": "Here's the chart you requested:",
                                    "chart": local_vars['fig']
                                })
                                explanation = generate_chart_explanation(chart_code, user_input)

                                # Display the explanation
                                st.write(explanation)
                                st.session_state.response_generated_chart = True
                            else:
                                st.error("The generated code did not produce a 'fig' object.")
                                st.code(chart_code, language="python")
                                # Add to chat history
                                st.session_state.chart_chat_history.append({
                                    "role": "assistant",
                                    "content": "I encountered an error while generating the chart. Here's the code I attempted to use:"
                                })
                                st.write("I encountered an error while generating the chart. Here's the code I attempted to use:")

                        except Exception as e:
                            st.error(f"Error generating chart: {str(e)}")
                            st.code(chart_code, language="python")
                            # Add to chat history
                            st.session_state.chart_chat_history.append({
                                "role": "assistant",
                                "content": f"I encountered an error while generating the chart: {str(e)}\nHere's the code I attempted to use:"
                            })
                            st.write(f"I encountered an error while generating the chart: {str(e)}\nHere's the code I attempted to use:")

                    else:
                        st.error("Failed to generate valid chart code. Please try again with a different prompt.")
                        # Add to chat history
                        st.session_state.chart_chat_history.append({
                            "role": "assistant",
                            "content": "I'm sorry, but I couldn't generate a valid chart code based on your description. Could you please try rephrasing your request or providing more details?"
                        })
                        st.write("I'm sorry, but I couldn't generate a valid chart code based on your description. Could you please try rephrasing your request or providing more details?")

                    gif_placeholder.empty()  # Ensure the GIF is cleared in all cases

            # Clear chat history button
            if st.session_state.user_input_given_chart and st.session_state.response_generated_chart:
                if st.button("Clear History"):
                    st.session_state.chart_chat_history = []
                    st.session_state.user_input_given_chart = False
                    st.session_state.response_generated_chart = False
                    st.rerun()
                    
    elif page == "Data Visualization":
        st.title("Data Visualization")
        if 'df' not in st.session_state or st.session_state.df is None:
            st.warning("Please upload a file on the Chatbot Query page to explore data.")
        else:
            # Only show PyGWalker visualization, remove all other content
            create_pygwalker_viz(st.session_state.df)
    

if __name__ == "__main__":
    main()
import hashlib
import logging
import re
import base64
import requests
import psycopg2
import os
import random
import string
import streamlit as st
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import boto3
from botocore.exceptions import ClientError
import json


if "conversation" not in st.session_state:
    st.session_state.conversation = []
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "text" not in st.session_state:
    st.session_state.text = " "
if "page" not in st.session_state:
    st.session_state.page = "login"
if "Image_text" not in st.session_state:
    st.session_state.Image_text = ""
if "sum" not in st.session_state:
    st.session_state.sum = ""
if "content_generated" not in st.session_state:
    st.session_state.content_generated = False
if "sidebar_message" not in st.session_state:
    st.session_state.sidebar_message = "Welcome!"
if "login_success" not in st.session_state:
    st.session_state.login_success = False
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "show_account_menu" not in st.session_state:
    st.session_state.show_account_menu = False

def get_secret(secret_name, region_name):
    # Create a session using the loaded environment variables
    session = boto3.session.Session(
        aws_access_key_id=os.getenv("aws_access_key"),
        aws_secret_access_key=os.getenv("aws_secret_key"),
        region_name=region_name
    )
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        # Fetch the secret value
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        
        # Return SecretString if available
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            secret = get_secret_value_response['SecretBinary']
        
        secret_dict = json.loads(secret)  # Parse secret JSON string
        return secret_dict

    except ClientError as e:
        print(f"Error retrieving secret: {e}")
        raise e

secret_name = "rds!db-1edec54a-39ae-4434-bc86-34b44cff4f1f"  # Replace with your secret name
region_name = "us-east-1"  # Replace with your AWS region

    # Get the secret
credentials = get_secret(secret_name, region_name)

    # Print credentials or do something with them
RDS_DB_USER = credentials.get("username")
RDS_DB_PASSWORD = credentials.get("password")
print(RDS_DB_USER, RDS_DB_PASSWORD)

secret_name = "marketplace1" 
credentials=get_secret(secret_name, region_name)

RDS_DB_NAME = credentials.get("dbname")
RDS_DB_HOST = credentials.get("host")
RDS_DB_PORT = credentials.get("port")

def get_db_connection():
    try:
        return psycopg2.connect(
            dbname=RDS_DB_NAME,
            user=RDS_DB_USER,
            password=RDS_DB_PASSWORD,
            host=RDS_DB_HOST,
            port=RDS_DB_PORT
        )
        
    except Exception as e:
        logging.error(f"Error connecting to database: {e}")
        return None
    
   
# Create users table

def create_users_table():
    try:
        conn = get_db_connection()
        print("Creating users table...")
        if not conn:
            logging.error("Database connection failed.")
            return
        
        cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL
                )
            """)
            conn.commit()
            logging.info("Users table created or already exists")
        except Exception as e:
            logging.error(f"Error creating users table: {e}")
        finally:
            cur.close()
            logging.info("Cursor closed.")
    except Exception as db_error:
        logging.error(f"Database error: {db_error}")
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")

# create_users_table()

def update_user_customer_id():
    atrs = st.query_params.get("atrs")
    if atrs:
        conn = get_db_connection()
        if not conn:
            st.error("Database connection failed")
            return
        
        cur = conn.cursor()
        try:
            # First get the customer_id from product_customers table using atrs (which is the id)
            cur.execute("""
                SELECT id FROM product_customers 
                WHERE id = %s
            """, (atrs,))
            
            customer_result = cur.fetchone()
            
            if customer_result:
                # Update the user table with the customer_id
                cur.execute("""
                    UPDATE users 
                    SET customer_id = %s 
                    WHERE id = (SELECT id FROM users LIMIT 1)
                """, (customer_result[0],))
                
                conn.commit()
                st.success("AWS Marketplace connection successful!")
            else:
                st.error("Customer not found in marketplace records")
                
        except Exception as e:
            conn.rollback()
            st.error(f"Error updating customer ID: {e}")
        finally:
            cur.close()
            conn.close()
    else:
        st.error("This application is available only on AWS Market Place. Please try to sign up through AWS Marketplace portal")

# Call this function at the start of your app
update_user_customer_id()

def add_logo(image_url, image_size="100px"):
    try:
        response = requests.get(image_url)
        img_data = response.content
        b64_encoded = base64.b64encode(img_data).decode()
        logo_html = f"""
            <div style=" top: 10px; left: 10px; width: {image_size}; height: auto; z-index: 1000;">
                <img src="data:image/png;base64,{b64_encoded}" style="width: {image_size}; height: auto;">
            </div>
        """
        st.markdown(logo_html, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading logo image: {e}")


def is_valid_email(email):
    regex = r'^\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.match(regex, email)

def is_valid_password(password):
    if len(password) < 8:
        return False
    if not re.search(r'\d', password):
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True

def signup(username, email, password, confirm_password):
    # atrs = st.query_params.get("atrs")
    # if not atrs:
    #     st.error("This application is available only on AWS Market Place. Please try to sign up through AWS Marketplace portal")
    #     return False
    if not is_valid_email(email):
        st.error("Please enter a valid email address")
        return False
    elif not is_valid_password(password):
        st.error("Password must be at least 8 characters long and include a number, an uppercase letter, a lowercase letter, and a special character")
        return False
    elif password != confirm_password:
        st.error("Passwords do not match")
        return False
    elif not username or not email or not password:
        st.error("Please fill in all fields")
        return False
    else:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # # Get the atrs value from URL query parameters
        # atrs = st.query_params.get("atrs")
        # if not atrs:
        #     st.error("Invalid signup link. Please use the correct URL.")
        #     return False

        # Ensure atrs is converted to integer
        # try:
        #     customer_id = int(atrs)
        # except ValueError:
        #     st.error("Invalid customer ID format.")
        #     return False

        conn = get_db_connection()
        if not conn:
            st.error("Unable to connect to the database")
            return False
        
        cur = conn.cursor()
        
        try:
            # Check if email already exists
            cur.execute(
                "SELECT email FROM users WHERE email = %s",
                (email,)
            )
            existing_email = cur.fetchone()
            if existing_email:
                st.error("Email already exists")
                return False

            # Check if the customer_id exists in product_customers table
            # cur.execute(
            #     "SELECT id FROM product_customers WHERE id = %s",
            #     (customer_id,)
            # )
            # if cur.fetchone() is None:
            #     st.error("This customer ID does not exist in the product_customers table.")
            #     return False

            # If all checks pass, proceed with user insertion
            cur.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed_password)# customer_id)
            )
            conn.commit()
            st.session_state.user_email = email
            st.info("Signup successful, You can Login now! ")
            if send_welcome_email(email, username):
                logging.info(f"Welcome email sent to {email}")
            else:
                logging.error(f"Failed to send welcome email to {email}")
            
            return True
        except psycopg2.IntegrityError as e:
            logging.error(f"IntegrityError during signup: {e}")
            st.error(f"An error occurred during signup: {e}")
            return False
        except Exception as e:
            logging.error(f"Error during signup: {e}")
            st.error(f"An unexpected error occurred during signup: {e}")
            return False
        finally:
            cur.close()
            conn.close()


            
def verify_login(email, password):
    conn = get_db_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        cur.execute("SELECT email FROM users WHERE email=%s AND password=%s", (email, hashed_password))
        user = cur.fetchone()
        return user[0] if user else None
    except Exception as e:
        logging.error(f"Error verifying login: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for i in range(length))

def reset_password(email):
    conn = get_db_connection()
    if not conn:
        st.error("Unable to connect to the database")
        return False
    
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT email FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        if user:
            new_password = generate_random_password()
            hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
            
            cur.execute("UPDATE users SET password=%s WHERE email=%s", (hashed_password, email))
            conn.commit()
            
            if send_reset_email(email, new_password):
                return True
            else:
                st.error("Failed to send reset email")
                return False
        else:
            st.error("Email not found")
            return False
    except Exception as e:
        logging.error(f"Error during password reset: {e}")
        st.error("An error occurred during password reset")
        return False
    finally:
        cur.close()
        conn.close()


def send_reset_email(email, new_password):
    SENDER_EMAIL="subscriptions@goml.io"
    sender_email = SENDER_EMAIL
    
    message = MIMEMultipart("alternative")
    message["Subject"] = "Password Reset"
    message["From"] = sender_email
    message["To"] = email

    text = f"""
    Dear User,Your temporary password is: {new_password}
    For security reasons, please log in and change this password immediately.
    """

    html = f"""
    <p>Dear User, Your temporary password is: <strong>{new_password}</strong><br>
    For security reasons, please log in and change this password immediately.<br>
    </p>
    """
    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")

    message.attach(part1)
    message.attach(part2)

    # AWS credentials should be set in environment variables or AWS configuration files
    session = boto3.Session(
        aws_access_key_id=os.getenv('aws_access_key'),
        aws_secret_access_key=os.getenv('aws_secret_key'),
        region_name='us-east-1'
    )
    
    client = session.client('ses')

    try:
        response = client.send_raw_email(
            Source=sender_email,
            Destinations=[email],
            RawMessage={'Data': message.as_string()}
        )
    except ClientError as e:
        logging.error(f"Error sending reset email to {email}: {e.response['Error']['Message']}")
        return False
    else:
        logging.info(f"Email sent! Message ID: {response['MessageId']}")
        return True
    


# Initialize session state variables
if "conversation" not in st.session_state:
    st.session_state.conversation = []
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "text" not in st.session_state:
    st.session_state.text = " "
if "page" not in st.session_state:
    st.session_state.page = "login"
if "Image_text" not in st.session_state:
    st.session_state.Image_text = ""
if "sum" not in st.session_state:
    st.session_state.sum = ""
if "content_generated" not in st.session_state:
    st.session_state.content_generated = False
if "sidebar_message" not in st.session_state:
    st.session_state.sidebar_message = "Welcome!"
if "login_success" not in st.session_state:
    st.session_state.login_success = False
if "user_email" not in st.session_state:
    st.session_state.user_email = None
    
def get_user_name(email):
    conn = get_db_connection()
    if not conn:
        return None
    
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT username FROM users WHERE email = %s", (email,))
        result = cur.fetchone()
        return result[0] if result else None
    except Exception as e:
        logging.error(f"Error fetching user name for email {email}: {e}")
        return None
    finally:
        cur.close()
        conn.close()      
    
if st.session_state.login_success and st.session_state.user_email:

    user_name = get_user_name(st.session_state.user_email)
    if user_name:
        st.session_state.sidebar_message = f"Welcome, {user_name}!"


def login_page():
    
        add_logo("https://www.goml.io/wp-content/smush-webp/2023/10/GoML_logo.png.webp", image_size="200px")
        st.title("GenAI powered Sales Analytics Engine")
        
        tab1, tab2 = st.tabs(["Login", "Sign Up"])

        with tab1:
            col1, col2 = st.columns([1, 1])
            with col1:
                with st.form(key='login_form'):
                    email = st.text_input("Email", key="login_email")
                    password = st.text_input("Password", type="password", key="login_password")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        login_button = st.form_submit_button(label='Login')
                    with col2:
                        forgot_password_button = st.form_submit_button(label='Forgot Password')
                    
                    if login_button:
                        login_result = verify_login(email, password)
                        if login_result:
                            st.session_state.page = "home"
                            st.session_state.login_success = True
                            st.session_state.logged_in = True 
                            st.session_state.user_email = login_result
                            st.rerun()
                        else:
                            st.error("Invalid email or password")
                        
                        
                
                    
                    if forgot_password_button:
                        if email:
                            if reset_password(email):
                                st.success(f"New password sent to {email}. Please check your email.")
                            else:
                                st.error("Failed to reset password. Please try again.")
                        else:
                            st.error("Please enter your email to reset your password")
            
            with col2:
                st.write("")
                st.write("")
        
        with tab2:
            col1, col2 = st.columns([1, 1])
            with col1:
                with st.form(key='signup_form'):
                    signup_username = st.text_input("Username", key="signup_username")
                    signup_email = st.text_input("Email", key="signup_email")
                    signup_password = st.text_input("Password", type="password", key="signup_password")
                    signup_confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm_password")
                    signup_button = st.form_submit_button(label='Sign Up')
                    
                    if signup_button:
                        if signup(signup_username, signup_email, signup_password, signup_confirm_password):
                            
                            st.rerun()
            
            with col2:
                st.write("")
                st.write("")

        
            
        
       
            
            
            
            
def send_welcome_email(email, username):
    SENDER_EMAIL="subscriptions@goml.io"
    sender_email = SENDER_EMAIL
    
    message = MIMEMultipart("alternative")
    message["Subject"] = "Welcome to GenAI powered Sales Analytics Engine - Let's Get Started!"
    message["From"] = sender_email
    message["To"] = email

    text = f"""
            Dear {username},

            Welcome, and thank you for subscribing to GoML's Gen AI Capability - Sales Analytics Engine on AWS Marketplace! You’re now ready to unlock powerful Gen-AI-driven insights that will take your sales performance to new heights. Dive into your dashboard, upload your data, and start making smarter decisions today.

            Click to Login - https://salesanalyticsengine.goml.io/

            For more updates - Please visit https://www.goml.io/
            For assistance, contact contact@goml.io

            Warm regards,

            Team GoML
            https://www.goml.io/
            """

    html = f"""
            <html>
            <body>
            <p>Dear {username},</p>

            <p>Welcome, and thank you for subscribing to GoML's Gen AI Capability - Sales Analytics Engine on AWS Marketplace! You’re now ready to unlock powerful Gen-AI-driven insights that will take your sales performance to new heights. Dive into your dashboard, upload your data, and start making smarter decisions today.</p>

            <p>Click to Login - <a href="https://salesanalyticsengine.goml.io/">https://salesanalyticsengine.goml.io/</a></p>

            <p>For more updates - Please visit <a href="https://www.goml.io/">https://www.goml.io/</a></p>
            <p>For assistance, contact <a href="mailto:contact@goml.io">contact@goml.io</a></p>

            <p>Warm regards,<br>
            Team GoML<br>
            <a href="https://www.goml.io/">https://www.goml.io/</a></p>
            </body>
            </html>
            """



    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")

    message.attach(part1)
    message.attach(part2)

    session = boto3.Session(
        aws_access_key_id=os.getenv('aws_access_key'),
        aws_secret_access_key=os.getenv('aws_secret_key'),
        region_name='us-east-1'
    )
    
    client = session.client('ses')

    try:
        response = client.send_raw_email(
            Source=sender_email,
            Destinations=[email],
            RawMessage={'Data': message.as_string()}
        )
    except ClientError as e:
        logging.error(f"Error sending welcome email to {email}: {e.response['Error']['Message']}")
        return False
    else:
        logging.info(f"Welcome email sent! Message ID: {response['MessageId']}")
        return True
            

def reset_password_page():
    display_sidebar() 
    st.title("Reset Password")
    user_email = st.session_state.get('user_email')
    if user_email:
        user_name = get_user_name(user_email)
        if user_name:
            st.markdown(f"Hi {user_name}! You can reset your password below.")
        else:
            st.markdown(f"Hi! You can reset your password below.")
    col1, col2 = st.columns([2, 1])
    with col1:
        email = st.text_input("Email", key="reset_email")
        
        new_password = st.text_input("New Password", type="password", key="new_password")
        
        confirm_password = st.text_input("Confirm New Password", type="password", key="confirm_password")
        
        if st.button("Reset Password",key="reset_password_button"):
            if not email or not new_password or not confirm_password:
                st.error("Please fill in all fields")
            elif new_password != confirm_password:
                st.error("Passwords do not match")
            elif not is_valid_password(new_password):
                st.error("Password must be at least 8 characters long and include a number, an uppercase letter, a lowercase letter, and a special character")
            else:
                if update_password(email, new_password):
                    st.success("Password successfully reset. You can now log in with your new password.")
                else:
                    st.error("Failed to reset password. Please try again.")
        st.write("")
        st.write("")
        
        # Add the "Go Home" button at the bottom left
        if st.button("🏠 Go Home"):
            st.session_state.page = "home"
            st.rerun()
    with col2:
        st.write("")  # This empty column helps to make the layout more compact

def update_password(email, new_password):
    conn = get_db_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    
    try:
        hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
        
        cur.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))
        
        if cur.rowcount == 0:
            logging.error(f"No user found with email: {email}")
            return False
        
        conn.commit()
        logging.info(f"Password updated successfully for email: {email}")
        return True
    except Exception as e:
        logging.error(f"Error updating password for email {email}: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def display_sidebar():
    st.sidebar.header(st.session_state.sidebar_message)
    
    # Profile button at the very top
    if st.sidebar.button("👤 Profile", key="profile_button"):
        st.session_state.show_account_menu = not st.session_state.get('show_account_menu', False)
    
    # Show account menu if the profile button was clicked
    if st.session_state.get('show_account_menu', False):
        st.sidebar.subheader("Account Options")
        if st.sidebar.button("Reset Password"):
            st.session_state.page = "reset_password"
            
            st.rerun()
        if st.sidebar.button("   Logout  "):
            # Reset all session state variables
            st.session_state.page = "login"
            st.session_state.login_success = False
            st.session_state.logged_in = False
            st.session_state.conversation = []
            st.session_state.uploaded_file = None
            st.session_state.text = " "
            st.session_state.Image_text = ""
            st.session_state.sum = ""
            st.session_state.content_generated = False
            st.session_state.user_email = None
            st.rerun()
        if st.sidebar.button("  Close Menu  "):
            st.session_state.show_account_menu = False
            st.rerun()
        # customer_id = get_marketplace_customer_id(st.session_state.user_email)

        # result = get_entitlements(customer_id)
        
        # if result and result["status"] == "success":
        #         date = result["entitlements"]["ResponseMetadata"]["HTTPHeaders"]["date"]
        #         st.sidebar.subheader(f"Subscription ends on: {date}")            
        
            
        
        # else:
        #         st.error("Unable to retrieve entitlements.")

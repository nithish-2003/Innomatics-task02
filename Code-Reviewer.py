import requests
import streamlit as st
import google.generativeai as genai
import subprocess
from streamlit_ace import st_ace
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv 
# Load environment variables from .env file
load_dotenv()

# Retrieve Gemini API key from environment variable
key = os.getenv("GEMINI_API_KEY")

if not key:
    st.error("Gemini API key not found. Please set GEMINI_API_KEY as an environment variable or in a .env file.")
    st.stop()

# Configure Gemini API
genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-pro")

# Function to Run Code
def run_code(code):
    """Execute Python code and capture output."""
    try:
        # Create a temporary file to execute the code
        temp_file = f"temp_{uuid.uuid4()}.py"
        with open(temp_file, "w") as f:
            f.write(code)
        
        # Run the code and capture output
        result = subprocess.run(
            ["python3", temp_file],
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )
        
        # Clean up temp file
        os.remove(temp_file)
        
        # Return both stdout and stderr
        output = result.stdout
        if result.stderr:
            output += "\nErrors:\n" + result.stderr
        
        return output
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out (30 second limit)"
    except FileNotFoundError:
        return "Error: Python interpreter not found. Ensure Python is installed."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        # Ensure temp file is removed even if there's an error
        if os.path.exists(temp_file):
            os.remove(temp_file)

# Function to Review Code
def review_code(code):
    """Send code to Gemini AI for review."""
    if not code.strip():
        return "Error: Please enter valid Python code."
    
    prompt = f"""
    Analyze the following Python code and identify any potential bugs, errors, or areas of improvement.
    Provide a fixed version of the code along with explanations for the corrections.
    Code:
    ```python
    {code}
    ```
    """
    try:
        response = model.generate_content(prompt)
        return response.text if response else "Error: No response received."
    except requests.exceptions.RequestException as e:
        return f"Network error while communicating with the AI model: {str(e)}"
    except Exception as e:
        return f"Unexpected error during code review: {str(e)}"

# Initialize session state
def init_session_state():
    if "tabs" not in st.session_state:
        new_tab_id = str(uuid.uuid4())
        st.session_state["tabs"] = {
            new_tab_id: {
                "code": "",
                "review_output": "",
                "run_output": "",
                "fixed_code": "",
                "editor_key": 0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        st.session_state["current_tab"] = new_tab_id

# Core application functions
def create_new_tab():
    new_tab_id = str(uuid.uuid4())
    st.session_state["current_tab"] = new_tab_id
    st.session_state["tabs"][new_tab_id] = {
        "code": "",
        "review_output": "",
        "run_output": "",
        "fixed_code": "",
        "editor_key": 0,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def delete_tab(tab_id):
    if tab_id in st.session_state["tabs"]:
        if tab_id == st.session_state["current_tab"]:
            remaining_tabs = [t for t in st.session_state["tabs"].keys() if t != tab_id]
            if remaining_tabs:
                st.session_state["current_tab"] = remaining_tabs[0]
            else:
                create_new_tab()
        del st.session_state["tabs"][tab_id]

def apply_fixed_code(tab_id):
    if st.session_state["tabs"][tab_id]["fixed_code"]:
        st.session_state["tabs"][tab_id]["code"] = st.session_state["tabs"][tab_id]["fixed_code"]
        st.session_state["tabs"][tab_id]["editor_key"] += 1

def get_sorted_tabs():
    return dict(sorted(
        st.session_state["tabs"].items(),
        key=lambda x: x[1]['timestamp'],
        reverse=True
    ))

# Initialize application
init_session_state()

# Sidebar
with st.sidebar:
    st.title("Code Review History")
    
    if st.button("New Review", type="primary"):
        create_new_tab()
        st.rerun()
    
    st.divider()
    
    # Display history
    sorted_tabs = get_sorted_tabs()
    for tab_id, tab_data in sorted_tabs.items():
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(
                f"Review from {tab_data['timestamp']}",
                key=f"history_{tab_id}",
                use_container_width=True
            ):
                st.session_state["current_tab"] = tab_id
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"delete_{tab_id}"):
                delete_tab(tab_id)
                st.rerun()

    # File upload section
    st.divider()
    uploaded_file = st.file_uploader("Upload a Python file", type=["py"])
    if uploaded_file is not None:
        # Read the content of the uploaded file
        code = uploaded_file.read().decode("utf-8")
        # Set the code in the current tab
        st.session_state["tabs"][st.session_state["current_tab"]]["code"] = code
        st.session_state["tabs"][st.session_state["current_tab"]]["editor_key"] += 1

# Main content area
if "tabs" in st.session_state and st.session_state["tabs"]:
    current_tab = st.session_state.get("current_tab", None)
    
    if current_tab in st.session_state["tabs"]:
        current_tab_data = st.session_state["tabs"][current_tab]
    else:
        st.error("The selected tab no longer exists. Creating a new tab.")
        create_new_tab()  # Create a new tab if the current one is invalid
        current_tab = st.session_state["current_tab"]
        current_tab_data = st.session_state["tabs"][current_tab]
else:
    st.error("No tabs available. Creating a new tab.")
    create_new_tab()
    current_tab = st.session_state["current_tab"]
    current_tab_data = st.session_state["tabs"][current_tab]

st.title("Python Code Reviewer 🚀")

# Code Editor
code = st_ace(
    language="python",
    theme="monokai",
    height=300,
    value=current_tab_data["code"],
    key=f"editor_{current_tab}_{current_tab_data['editor_key']}"
)

# Update code in session state
st.session_state["tabs"][current_tab]["code"] = code

# Chat-like interface
chat_container = st.container()

with chat_container:
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Run Code 🏃‍♂️", key=f"run_{current_tab}"):
            if code.strip():
                with st.spinner("Running code..."):
                    result = run_code(code)
                st.session_state["tabs"][current_tab]["run_output"] = result
                st.success("Code executed successfully!")
            else:
                st.warning("Please enter some code.")

    with col2:
        if st.button("Review Code 🔍", key=f"review_{current_tab}"):
            if code.strip():
                with st.spinner("Reviewing code..."):
                    review_result = review_code(code)
                st.session_state["tabs"][current_tab]["review_output"] = review_result
                
                # Extract fixed code if available
                if "```python" in review_result:
                    fixed_code = review_result.split("```python")[1].split("```")[0].strip()
                    if fixed_code:
                        st.session_state["tabs"][current_tab]["fixed_code"] = fixed_code
                st.success("Code reviewed successfully!")
            else:
                st.warning("Please enter some code.")

    # Output Section
    if current_tab_data["run_output"]:
        st.markdown("#### Output:")
        st.code(current_tab_data["run_output"])

    if current_tab_data["review_output"]:
        st.markdown("#### Review Feedback:")
        st.markdown(current_tab_data["review_output"])
        
        if current_tab_data["fixed_code"]:
            st.markdown("#### Fixed Code:")
            st.code(current_tab_data["fixed_code"])
            
            if st.button("Apply Fixed Code ✅", key=f"apply_{current_tab}"):
                apply_fixed_code(current_tab)
                st.success("Fixed code applied successfully!")
                st.rerun()
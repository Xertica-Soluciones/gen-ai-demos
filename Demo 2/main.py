import pandas as pd         # Used for data manipulation, especially with BigQuery results
import pandas_gbq           # Integrates pandas with Google BigQuery
import os                   # Used to access environment variables
import flask                # Required for defining Google Cloud Function
# contains a dictionary for structuring HTTP responses for Conversational Agent
from response_format import response

# Google Cloud Vertex AI SDK for interacting with Generative Models (Gemini)
from vertexai import generative_models as vertex_gm
from vertexai.generative_models import GenerationConfig, Part
import vertexai

# --- Configuration Variables ---
# Retrieve environment variables for project settings and model configuration.
# These variables should be set in the Cloud Function environment.
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
DATASET = os.getenv("DATASET")
TABLE = os.getenv("TABLE")
# The base prompt for the Gemini model
PROMPT_TEMPLATE = os.getenv("PROMPT_TEMPLATE")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

# --- Vertex AI Initialization ---
# Initialize the Vertex AI SDK with your project ID and location.
vertexai.init(project=PROJECT_ID, location=LOCATION)

# --- Gemini Model Configuration ---
# Load the specified Generative Model (e.g., "gemini-pro").
model = vertex_gm.GenerativeModel(GEMINI_MODEL)

# Define safety settings for the Gemini model.
# This configuration aims to block no content for these categories,
# allowing maximum flexibility for judicial document analysis
SAFETY_SETTINGS = {
    vertex_gm.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: vertex_gm.HarmBlockThreshold.BLOCK_NONE,
    vertex_gm.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: vertex_gm.HarmBlockThreshold.BLOCK_NONE,
    vertex_gm.HarmCategory.HARM_CATEGORY_HATE_SPEECH: vertex_gm.HarmBlockThreshold.BLOCK_NONE,
    vertex_gm.HarmCategory.HARM_CATEGORY_HARASSMENT: vertex_gm.HarmBlockThreshold.BLOCK_NONE,
    vertex_gm.HarmCategory.HARM_CATEGORY_UNSPECIFIED: vertex_gm.HarmBlockThreshold.BLOCK_NONE,
}

# Define generation configuration for the Gemini model.
# These parameters control the output quality and creativity.
# temperature: Lower values make outputs more deterministic; higher values more creative.
# top_p: Controls diversity via nucleus sampling.
# top_k: Controls diversity via top-k sampling.
# candidate_count: Number of response candidates to generate (usually 1 for direct answers).
# max_output_tokens: Maximum length of the generated response.
GENERATION_CONFIG = vertexai.generative_models.GenerationConfig(
    temperature=0.1,
    top_p=0.9,
    top_k=40,
    candidate_count=1,
    max_output_tokens=2048,
)

# --- Helper Functions ---

def get_document_uri(process_number: int) -> str:
    """
    Retrieves the Google Cloud Storage (GCS) URI of a document
    associated with a given process number from a BigQuery table.

    Args:
        process_number (int): The unique identifier for the judicial process.

    Returns:
        str: The GCS URI of the document.

    Raises:
        Exception: If the document URI cannot be retrieved (e.g., process number not found).
    """
    bq_query = f"""
        SELECT gcs_uri FROM `{PROJECT_ID}.{DATASET}.{TABLE}` WHERE id = {process_number};
    """

    try:
        # Execute the BigQuery query using pandas_gbq
        df = pandas_gbq.read_gbq(
            bq_query,
            project_id=PROJECT_ID,
            dialect="standard"
        )

        # Check if any row was returned
        if df.empty:
            raise ValueError(f"No document found for process number: {process_number}")

        # Return the GCS URI from the first row (assuming 'id' is unique)
        return df.loc[0, 'gcs_uri']
    except Exception as e:
        print(f"Error fetching GCS URI from BigQuery: {e}")
        # Re-raise or handle appropriately based on desired error flow
        raise

def answer_with_llm(question: str, process_number: int) -> str:
    """
    Uses a Large Language Model (LLM) to answer a question based on a document
    retrieved from GCS, identified by a process number.

    Args:
        question (str): The user's question to be answered.
        process_number (int): The identifier for the judicial process document.

    Returns:
        str: The LLM's answer to the question, or an error message if something goes wrong.
    """
    try:
        # 1. Retrieve the GCS URI for the relevant document
        relevant_document_uri = get_document_uri(process_number)

        # 2. Format the prompt with the user's question
        prompt_formatted = PROMPT_TEMPLATE.format(question)

        # 3. Create a Part object for the document from its GCS URI
        document_part = Part.from_uri(uri=relevant_document_uri, mime_type='application/pdf')

        # 4. Assemble the content parts for the Gemini model
        # The content includes the formatted prompt and the document itself.
        contents = [prompt_formatted, document_part]

        # 5. Generate content using the Gemini model
        gemini_response = model.generate_content(
            contents,
            generation_config=GENERATION_CONFIG,
            safety_settings=SAFETY_SETTINGS
        )

        # Extract the text from the Gemini response
        return gemini_response.text

    except Exception as e:
        print(f"An error occurred during LLM interaction: {e}")
        # Return a user-friendly error message
        return "Sorry, an internal error occurred while processing your request. Could you please try again?"

# --- Google Cloud Function Entry Point ---

app = flask.Flask(__name__)

@app.route('/', methods=['POST'])
def main():

    """
    Main entry point for the Google Cloud Function.
    Handles incoming HTTP requests, extracts the user's question,
    calls the LLM to get an answer, and returns it in a structured format.

    Args:
        request (flask.Request): The HTTP request object.

    Returns:
        tuple: A tuple containing (response_body, status_code, headers).
    """
    # Default values for testing
    default_process_number = 1
    default_question = 'What is the current status of the case?'

    # Parse the JSON body of the incoming request
    request_json = flask.request.json

    question = default_question
    process_number = default_process_number

    if request_json:
        # Extract the 'text' field which contains the user's question
        question = request_json.get("text", default_question)
        # Extract 'process_number' if provided in the request
        process_number = request_json.get("process_number", default_process_number)
    else:
        print("Warning: Request body is empty or not JSON. Using default question and process number.")

    # Define HTTP headers for the response
    headers = {'Content-Type': 'application/json'}
    print(f"Analyzing question: {question} for process number {process_number}")
    # Get the answer from the LLM based on the question and document
    llm_answer = answer_with_llm(question, process_number)

    # Print the full LLM response to Cloud Function logs for debugging
    print(f"Full LLM response: {llm_answer}")

    # Prepare the final response dictionary.
    # The 'response' object imported from 'response_format' is used as template.
    response["fulfillment_response"]["messages"][0]["text"]["text"][0] = llm_answer

    # Return the structured response, HTTP status code 200 (OK), and headers
    return (response, 200, headers)
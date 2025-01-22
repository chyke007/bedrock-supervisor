import boto3
from botocore.exceptions import ClientError
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Environment variables
try:
    agentId = os.environ["BEDROCK_AGENT_ID"]
    agentAliasId = os.environ["BEDROCK_AGENT_ALIAS_ID"]
    region = os.environ["AWS_REGION"]
except KeyError as e:
    logging.error(f"Missing required environment variable: {e}")
    raise

def askQuestion(question, endSession=False, sessionId=""):
    """
    Sends a prompt for the agent to process and respond to.

    :param question: The prompt/question to send to the agent.
    :param endSession: Boolean flag to indicate whether the session should be ended.
    :param sessionId: The unique identifier of the session. Use the same value across requests to continue the conversation.
    :return: The completion response from the agent.
    """
    try:
        client = boto3.client('bedrock-agent-runtime', region_name=region)
        logging.info(f"Invoking agent with question: '{question}' (Session ID: {sessionId}, End Session: {endSession})")
        
        # Invoke agent
        response = client.invoke_agent(
            agentId=agentId,
            agentAliasId=agentAliasId,
            sessionId=sessionId,
            inputText=question,
            endSession=endSession,
            enableTrace=True
        )

        # Extract completion
        completion = ""
        for event in response.get("completion", []):
            chunk = event.get("chunk")
            if chunk:
                completion += chunk["bytes"].decode()

        logging.info(f"Agent response: {completion}")
        return completion

    except ClientError as e:
        logging.error(f"ClientError while invoking agent: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise

def agent_handler(event, context):
    """
    Handles incoming requests, processes the question, and invokes the agent.

    :param event: A dict containing the user prompt and session ID.
    :param context: The context of the invocation (not used in this implementation).
    :return: The response from the agent or an error message.
    """
    try:
        # Extract parameters from the event
        sessionId = event.get("sessionId", "")
        question = event.get("question", "")
        endSession = event.get("endSession", "false").lower() == "true"

        if not sessionId:
            raise ValueError("Missing sessionId in the event data.")
        if not question:
            raise ValueError("Missing question in the event data.")

        logging.info(f"Session ID: {sessionId} | Question: {question} | End Session: {endSession}")

        # Invoke the agent
        response = askQuestion(question, endSession, sessionId)
        return {"status": "success", "response": response}

    except ValueError as e:
        logging.error(f"ValueError: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        return {"status": "error", "message": "An error occurred. Please adjust the question and try again."}

import json
from datetime import datetime
import uuid
import boto3
from  helper import get_named_parameter, get_booking_details

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('steakhouse_bookings')

def create_ticket_booking(name, creation_date, incident_date, reason):
    """
    Create a new steakhouse ticket booking

    Args:
        name (string): Name of customer creating the ticket
        creation_date (string): Ticket creation date
        incident_date(string): Date of incident
        reason (string): The reason for raising a ticket
    """
    try:
        booking_id = str(uuid.uuid4())[:8]
        item = {
            'booking_id': booking_id,
            'name': name,
            'creation_date': creation_date,
            'incident_date': incident_date,
            'reason': reason
        }

        table.put_item(Item=item)

        return {'booking_id': booking_id}
    except Exception as e:
        return {'error': str(e)}


def delete_ticket_booking(booking_id):
    """
    Delete an existing steakhouse ticket booking

    Args:
        booking_id (str): The ID of the booking to delete
    """
    try:
        response = table.delete_item(Key={'booking_id': booking_id})
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            return {'message': f'Booking with ID {booking_id} deleted successfully'}
        else:
            return {'message': f'Failed to delete booking with ID {booking_id}'}
    except Exception as e:
        return {'error': str(e)}


def lambda_handler(event, context):
    # get the action group used during the invocation of the lambda function
    actionGroup = event.get('actionGroup', '')

    # name of the function that should be invoked
    function = event.get('function', '')

    if function == 'get_ticket_booking_details':
        booking_id = get_named_parameter(event, "booking_id")
        if booking_id:
            response = str(get_booking_details(booking_id))
            responseBody = {'TEXT': {'body': json.dumps(response)}}
        else:
            responseBody = {'TEXT': {'body': 'Missing booking_id parameter'}}

    elif function == 'create_ticket_booking':
        name = get_named_parameter(event, "name")
        creation_date = datetime.today().strftime("%d/%m/%Y")
        incident_date = get_named_parameter(event, "incident_date")
        reason = get_named_parameter(event, "reason")
        
        if name and creation_date and incident_date and reason:
            response = str(create_ticket_booking(name, creation_date, incident_date, reason))
            responseBody = {'TEXT': {'body': json.dumps(response)}}
        else:
            responseBody = {'TEXT': {'body': 'Missing required parameters'}}

    elif function == 'delete_ticket_booking':
        booking_id = get_named_parameter(event, "booking_id")
        if booking_id:
            response = str(delete_ticket_booking(booking_id))
            responseBody = {'TEXT': {'body': json.dumps(response)}}
        else:
            responseBody = {'TEXT': {'body': 'Missing booking_id parameter'}}

    else:
        responseBody = {'TEXT': {'body': 'Invalid function'}}

    action_response = {
        'actionGroup': actionGroup,
        'function': function,
        'functionResponse': {
            'responseBody': responseBody
        }
    }

    function_response = {'response': action_response,
                         'messageVersion': event.get('messageVersion', '1.0')}
    print("Response: {}".format(function_response))

    return function_response

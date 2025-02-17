import json
import uuid
import boto3
from  helper import get_named_parameter, get_booking_details

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('steakhouse_bookings')

def create_shortlet_booking(person_name, date, number_days, shortlet_type, num_guests):
    """
    Create a new steakhouse shortlet booking

    Args:
        person_name (string): Name of customer making reservation
        date (string): The check in date
        number_days(integer): The number of days to stay
        shortlet_type (string): The Shortlet apartment type
        num_guests (integer): Number of guest
    """
    try:
        booking_id = str(uuid.uuid4())[:8]
        item = {
            'booking_id': booking_id,
            'person_name': person_name,
            'date': date,
            'number_days': number_days,
            'shortlet_type': shortlet_type,
            'num_guests': num_guests
        }

        table.put_item(Item=item)

        return {'booking_id': booking_id}
    except Exception as e:
        return {'error': str(e)}


def delete_shortlet_booking(booking_id):
    """
    Delete an existing steakhouse shortlet booking

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

    if function == 'get_shortlet_booking_details':
        booking_id = get_named_parameter(event, "booking_id")
        if booking_id:
            response = str(get_booking_details(booking_id))
            responseBody = {'TEXT': {'body': json.dumps(response)}}
        else:
            responseBody = {'TEXT': {'body': 'Missing booking_id parameter'}}

    elif function == 'create_shortlet_booking':
        person_name = get_named_parameter(event, "person_name")
        date = get_named_parameter(event, "date")
        number_days = get_named_parameter(event, "number_days")
        shortlet_type = get_named_parameter(event, "shortlet_type")
        num_guests = get_named_parameter(event, "num_guests")

        if person_name and date and number_days and shortlet_type and num_guests:
            response = str(create_shortlet_booking(person_name, date, number_days, shortlet_type, num_guests))
            responseBody = {'TEXT': {'body': json.dumps(response)}}
        else:
            responseBody = {'TEXT': {'body': 'Missing required parameters'}}

    elif function == 'delete_shortlet_booking':
        booking_id = get_named_parameter(event, "booking_id")
        if booking_id:
            response = str(delete_shortlet_booking(booking_id))
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

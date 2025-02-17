import json
import uuid
import boto3
from  helper import get_named_parameter, get_booking_details

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('steakhouse_bookings')

def create_time_off_booking(staff_name, start_date, end_date, reason, comment=None):
    """
    Create a new steakhouse hr booking

    Args:
        staff_name (string): Name of staff taking a time off
        start_date (string): The intended start date of the time off
        end_date (string): The intended end date of the time off
        reason (string): The reason for taking a time off
        comment (string, optional): Detailed description of time off reason. Defaults to None.
    """
    try:
        booking_id = str(uuid.uuid4())[:8]
        item = {
            'booking_id': booking_id,
            'staff_name': staff_name,
            'start_date': start_date,
            'end_date': end_date,
            'reason': reason,
        }

        # Only add comment if it's not None or empty
        if comment:
            item['comment'] = comment
        
        table.put_item(Item=item)

        return {'booking_id': booking_id}
    except Exception as e:
        return {'error': str(e)}


def delete_time_off_booking(booking_id):
    """
    Delete an existing steakhouse hr time off booking

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

    if function == 'get_time_off_booking_details':
        booking_id = get_named_parameter(event, "booking_id")
        if booking_id:
            response = str(get_booking_details(booking_id))
            responseBody = {'TEXT': {'body': json.dumps(response)}}
        else:
            responseBody = {'TEXT': {'body': 'Missing booking_id parameter'}}

    elif function == 'create_time_off_booking':
        staff_name = get_named_parameter(event, "staff_name")
        start_date = get_named_parameter(event, "start_date")
        end_date = get_named_parameter(event, "end_date")
        reason = get_named_parameter(event, "reason")
        comment = get_named_parameter(event, "comment") or ""

        if staff_name and start_date and end_date and reason:
            response = str(create_time_off_booking(staff_name, start_date, end_date, reason, comment))
            responseBody = {'TEXT': {'body': json.dumps(response)}}
        else:
            responseBody = {'TEXT': {'body': 'Missing required parameters'}}

    elif function == 'delete_time_off_booking':
        booking_id = get_named_parameter(event, "booking_id")
        if booking_id:
            response = str(delete_time_off_booking(booking_id))
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

import json
import uuid
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('steakhouse_bookings')


def get_named_parameter(event, name):
    """
    Get a parameter from the lambda event
    """
    return next((item['value'] for item in event.get('parameters', []) if item['name'] == name), None)

def get_booking_details(booking_id):
    """
    Retrieve details of a restaurant booking

    Args:
        booking_id (string): The ID of the booking to retrieve
    """
    try:
        response = table.get_item(Key={'booking_id': booking_id})
        if 'Item' in response:
            return response['Item']
        else:
            return {'message': f'No booking found with ID {booking_id}'}
    except Exception as e:
        return {'error': str(e)}


def create_booking(date, name, time, num_guests, desired_food=None):
    """
    Create a new restaurant booking

    Args:
        date (string): The date of the booking
        name (string): Name to idenfity your reservation
        time (string): The time of the booking
        desired_food (string, optional): The choosen menu/desserts/special. Defaults to None.
        num_guests (integer): The number of guests for the booking
    """
    try:
        booking_id = str(uuid.uuid4())[:8]
        item = {
            'booking_id': booking_id,
            'date': date,
            'name': name,
            'time': time,
            'num_guests': num_guests,
        }

        # Only add desired_food if it's not None or empty
        if desired_food:
            item['desired_food'] = desired_food
        
        table.put_item(Item=item)

        return {'booking_id': booking_id}
    except Exception as e:
        return {'error': str(e)}


def delete_booking(booking_id):
    """
    Delete an existing restaurant booking

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

    if function == 'get_booking_details':
        booking_id = get_named_parameter(event, "booking_id")
        if booking_id:
            response = str(get_booking_details(booking_id))
            responseBody = {'TEXT': {'body': json.dumps(response)}}
        else:
            responseBody = {'TEXT': {'body': 'Missing booking_id parameter'}}

    elif function == 'create_booking':
        date = get_named_parameter(event, "date")
        name = get_named_parameter(event, "name")
        time = get_named_parameter(event, "time")
        num_guests = get_named_parameter(event, "num_guests")
        desired_food = get_named_parameter(event, "desired_food") or ""

        if date and name and time and num_guests:
            response = str(create_booking(date, name, time, num_guests, desired_food))
            responseBody = {'TEXT': {'body': json.dumps(response)}}
        else:
            responseBody = {'TEXT': {'body': 'Missing required parameters'}}

    elif function == 'delete_booking':
        booking_id = get_named_parameter(event, "booking_id")
        if booking_id:
            response = str(delete_booking(booking_id))
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
